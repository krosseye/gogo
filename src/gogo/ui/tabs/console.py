import codecs
import re
from collections import deque
from pathlib import Path

from kq_icon_engine import IconStyle, KQIcon
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QKeySequence,
    QShortcut,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gogo.core import launcher, paths
from gogo.ui.components.search_bar import SearchBarWidget

POLL_INTERVAL_MS = 500
MAX_LINES = 20_000

ERROR_RE = re.compile(r"^\s*(USER |SCRIPT )?ERROR\b")
WARNING_RE = re.compile(r"^\s*(USER |SCRIPT )?WARNING\b")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _fmt(color: QColor, bold: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(color)
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    return fmt


class GodotLogHighlighter(QSyntaxHighlighter):
    """Colours Godot's ERROR / WARNING lines and their backtrace context."""

    RULES = (
        (re.compile(r"^\s*(USER |SCRIPT )?ERROR\b.*"), _fmt(QColor(220, 38, 38), True)),
        (re.compile(r"^\s*(USER |SCRIPT )?WARNING\b.*"), _fmt(QColor(217, 119, 6))),
        (
            re.compile(r"^\s+(at:|GDScript backtrace|\[\d+\]).*"),
            _fmt(QColor(128, 128, 128)),
        ),
        (re.compile(r"https?://\S+"), _fmt(QColor(59, 130, 246))),
    )

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self.RULES:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class ConsoleTabContent(QWidget):
    """Tails the engine log of the selected launch session."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._log_path: Path | None = None
        self._offset = 0
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._partial = ""
        self._lines: deque[str] = deque(maxlen=MAX_LINES)
        self._known_logs: list[Path] = []
        self._filter = ""

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(POLL_INTERVAL_MS)
        self._poll()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.filter_input = SearchBarWidget(self)
        self.filter_input.search_bar.setPlaceholderText("Filter output")
        self.filter_input.search_text_changed.connect(self._set_filter)
        QShortcut(
            QKeySequence.StandardKey.Find, self, self.filter_input.search_bar.setFocus
        )
        layout.addWidget(self.filter_input)

        self.output = QPlainTextEdit(readOnly=True)
        self.output.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.output.setMaximumBlockCount(MAX_LINES)
        self.output.setPlaceholderText(
            "Open a project or engine from GoGo to see its output here."
        )
        self.highlighter = GodotLogHighlighter(self.output.document())
        layout.addWidget(self.output)

        stats = QHBoxLayout()
        self.stats_label = QLabel()
        stats.addWidget(self.stats_label)
        stats.addStretch()
        layout.addLayout(stats)

        self.session_combo = QComboBox()
        self.session_combo.setMinimumContentsLength(24)
        self.session_combo.setFixedHeight(32)
        self.session_combo.setToolTip("Launch session")
        self.session_combo.setPlaceholderText("No sessions yet")
        self.session_combo.setEnabled(False)
        self.session_combo.currentIndexChanged.connect(self._on_session_changed)

        self.options_btn = QPushButton("Options  ")
        self.options_btn.setIcon(KQIcon("funnel", style=IconStyle.REGULAR))
        self.options_btn.setFixedHeight(32)
        menu = QMenu(self)
        self.auto_scroll_action = menu.addAction("Auto-Scroll")
        self.auto_scroll_action.setCheckable(True)
        self.auto_scroll_action.setChecked(True)
        wrap_action = menu.addAction("Wrap Text")
        wrap_action.setCheckable(True)
        wrap_action.toggled.connect(
            lambda on: self.output.setLineWrapMode(
                QPlainTextEdit.LineWrapMode.WidgetWidth
                if on
                else QPlainTextEdit.LineWrapMode.NoWrap
            )
        )
        wrap_action.setChecked(True)
        menu.addSeparator()
        menu.addAction("Clear View", self._clear_view)
        menu.addAction("Open Logs Folder", self._open_logs_folder)
        self.options_btn.setMenu(menu)

        self._update_stats()

    def create_tools(self) -> list[QLayout | QWidget]:
        return [self.session_combo, self.options_btn]

    def _poll(self) -> None:
        logs = launcher.list_logs()
        if logs != self._known_logs:
            is_new_launch = bool(logs) and logs[0] not in self._known_logs
            self._known_logs = logs
            self._refresh_sessions(follow_newest=is_new_launch)
        self._read_new_output()

    @staticmethod
    def _open_logs_folder() -> None:
        logs_dir = paths.logs_dir()
        logs_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_dir)))

    def _refresh_sessions(self, follow_newest: bool) -> None:
        current = self._log_path
        self.session_combo.blockSignals(True)
        self.session_combo.clear()
        for path in self._known_logs:
            self.session_combo.addItem(path.stem, path)
        index = (
            0
            if follow_newest or current is None
            else self.session_combo.findData(current)
        )
        self.session_combo.setCurrentIndex(max(index, 0))
        self.session_combo.setEnabled(bool(self._known_logs))
        self.session_combo.blockSignals(False)
        self._on_session_changed()

    def _on_session_changed(self) -> None:
        path = self.session_combo.currentData()
        if path == self._log_path:
            return
        self._log_path = path
        self._offset = 0
        self._decoder.reset()
        self._partial = ""
        self._lines.clear()
        self.output.clear()
        self._read_new_output()

    def _read_new_output(self) -> None:
        if self._log_path is None:
            self._update_stats()
            return
        try:
            with open(self._log_path, "rb") as f:
                f.seek(self._offset)
                data = f.read()
        except OSError:
            return
        if not data:
            return
        self._offset += len(data)

        text = self._partial + self._decoder.decode(data)
        *complete, self._partial = text.split("\n")
        new_lines = [ANSI_RE.sub("", line).rstrip("\r") for line in complete]
        self._lines.extend(new_lines)
        self._append([line for line in new_lines if self._matches(line)])
        self._update_stats()

    def _matches(self, line: str) -> bool:
        return not self._filter or self._filter in line.lower()

    def _append(self, lines: list[str]) -> None:
        if not lines:
            return
        self.output.appendPlainText("\n".join(lines))
        if self.auto_scroll_action.isChecked():
            bar = self.output.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _set_filter(self, text: str) -> None:
        self._filter = text.lower()
        self.output.clear()
        self._append([line for line in self._lines if self._matches(line)])

    def _clear_view(self) -> None:
        self._lines.clear()
        self.output.clear()
        self._update_stats()

    def _update_stats(self) -> None:
        errors = sum(1 for line in self._lines if ERROR_RE.match(line))
        warnings = sum(1 for line in self._lines if WARNING_RE.match(line))
        self.stats_label.setText(
            f"Lines: {len(self._lines)} | Errors: {errors} | Warnings: {warnings}"
        )
