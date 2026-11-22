import logging
from pathlib import Path

import mistune
from godotkit.engine import GodotVersion
from PySide6.QtCore import QSize, Qt, QUrl, Slot
from PySide6.QtGui import (
    QFontMetrics,
    QIcon,
    QKeySequence,
    QPalette,
    QShortcut,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from gogo.core import paths

logger = logging.getLogger(__name__)

WINDOW_TITLE_TEMPLATE = "Changelog - {version}"
GITHUB_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/godotengine/godot/refs/tags/{tag}/CHANGELOG.md"
)
CACHE_DIR_NAME = "changelogs"
SEARCH_PLACEHOLDER = "Find"
NO_RESULTS_TEXT = "No results"
RESULTS_TEMPLATE = "{current} of {total}"
LONGEST_RESULT_STRING = "0000 of 0000"

ICON_PREVIOUS = "go-up"
ICON_NEXT = "go-down"

SHORTCUT_FIND = "Ctrl+F"
SHORTCUT_NEXT = "Enter"
SHORTCUT_PREV = "Shift+Enter"
SHORTCUT_MATCH_CASE = "Alt+C"
SHORTCUT_MATCH_WHOLE_WORD = "Alt+W"

TOOLTIP_MATCH_CASE = f"Match Case ({SHORTCUT_MATCH_CASE})"
TOOLTIP_MATCH_WHOLE_WORD = f"Match Whole Word ({SHORTCUT_MATCH_WHOLE_WORD})"
TOOLTIP_PREV = f"Previous Match ({SHORTCUT_PREV})"
TOOLTIP_NEXT = f"Next Match ({SHORTCUT_NEXT})"


class ChangelogDialog(QDialog):
    """A Godot release's CHANGELOG.md (fetched once, then cached) with find-in-page."""

    MINIMUM_SIZE = QSize(600, 500)

    def __init__(self, version: GodotVersion, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.version = version

        self.network_manager: QNetworkAccessManager | None = None
        self.pending_cache_path: Path | None = None

        self._configure_window()
        self._setup_ui()
        self._load_changelog()

    def _configure_window(self):
        self.setWindowTitle(
            WINDOW_TITLE_TEMPLATE.format(version=self.version.display_name)
        )
        self.resize(self.MINIMUM_SIZE)
        self.setMinimumSize(self.MINIMUM_SIZE)

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)

        self.search_widget = self._create_search_widget()
        self.main_layout.addWidget(self.search_widget)

        self.content_browser = self._create_content_browser()
        self.main_layout.addWidget(self.content_browser)

        self.setLayout(self.main_layout)

    def _create_content_browser(self) -> QTextBrowser:
        browser = QTextBrowser()
        browser.setViewportMargins(10, 10, 10, 10)
        browser.setOpenExternalLinks(True)
        browser.setReadOnly(True)
        return browser

    def _create_search_widget(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.search_input = self._create_search_input()
        self.results_count_label = self._create_results_label()

        self.match_case_checkbox = self._create_checkbox(
            "Match Case", TOOLTIP_MATCH_CASE, SHORTCUT_MATCH_CASE
        )
        self.match_whole_word_checkbox = self._create_checkbox(
            "Match Whole Word", TOOLTIP_MATCH_WHOLE_WORD, SHORTCUT_MATCH_WHOLE_WORD
        )

        self.btn_prev = self._create_nav_button(
            ICON_PREVIOUS, TOOLTIP_PREV, self.find_prev
        )
        self.btn_next = self._create_nav_button(ICON_NEXT, TOOLTIP_NEXT, self.find_next)

        self._setup_shortcuts()

        layout.addWidget(self.search_input)
        layout.addWidget(self.results_count_label)
        layout.addWidget(self.match_case_checkbox)
        layout.addWidget(self.match_whole_word_checkbox)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.btn_next)

        return widget

    def _create_search_input(self) -> QLineEdit:
        line_edit = QLineEdit()
        line_edit.setClearButtonEnabled(True)
        line_edit.setPlaceholderText(SEARCH_PLACEHOLDER)
        line_edit.textChanged.connect(self._update_search_results_count)
        line_edit.returnPressed.connect(self._on_search_input_return_pressed)
        return line_edit

    def _create_results_label(self) -> QLabel:
        label = QLabel(NO_RESULTS_TEXT)
        label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        label.setContentsMargins(5, 0, 5, 0)
        metrics = QFontMetrics(label.font())
        width = metrics.horizontalAdvance(LONGEST_RESULT_STRING)
        label.setFixedWidth(width)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _create_checkbox(
        self, text: str, tooltip: str, shortcut_sequence: str
    ) -> QCheckBox:
        checkbox = QCheckBox(text)
        checkbox.setToolTip(tooltip)
        checkbox.stateChanged.connect(self._update_search_results_count)

        shortcut = QShortcut(QKeySequence(shortcut_sequence), self)
        shortcut.activated.connect(checkbox.toggle)
        return checkbox

    def _create_nav_button(self, icon_name: str, tooltip: str, callback) -> QPushButton:
        btn = QPushButton()
        btn.setToolTip(tooltip)
        btn.setAutoDefault(False)
        btn.setFixedSize(24, 24)
        btn.setIcon(QIcon.fromTheme(icon_name))
        btn.setIconSize(QSize(12, 12))
        btn.clicked.connect(callback)
        return btn

    def _setup_shortcuts(self):
        shortcut_search = QShortcut(QKeySequence(SHORTCUT_FIND), self)
        shortcut_search.activated.connect(self.search_input.setFocus)
        shortcut_search.activated.connect(self.search_input.selectAll)

        shortcut_next = QShortcut(QKeySequence(SHORTCUT_NEXT), self)
        shortcut_next.activated.connect(self.find_next)

        shortcut_prev = QShortcut(QKeySequence(SHORTCUT_PREV), self)
        shortcut_prev.activated.connect(self.find_prev)

    def _set_content_from_markdown(self, markdown_text: str):
        renderer = mistune.create_markdown(
            plugins=["table", "strikethrough", "task_lists"]
        )
        html = renderer(markdown_text)

        styled_html = f"""
        <body>
            <style>
                code {{ background-color: rgba(128, 128, 128, 0.15); font-family: monospace; }}
            </style>
            {html}
        </body>
        """

        self.content_browser.setHtml(styled_html)

    def _on_search_input_return_pressed(self):
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.find_prev()
        else:
            self.find_next()

    def _get_search_flags(self) -> QTextDocument.FindFlag:
        search_flags = QTextDocument.FindFlag(0)
        if self.match_case_checkbox.isChecked():
            search_flags |= QTextDocument.FindFlag.FindCaseSensitively
        if self.match_whole_word_checkbox.isChecked():
            search_flags |= QTextDocument.FindFlag.FindWholeWords
        return search_flags

    def _update_search_results_count(self):
        """Update the "N of M" label."""
        search_text = self.search_input.text()
        if not search_text:
            self.results_count_label.setText(NO_RESULTS_TEXT)
            return

        search_flags = self._get_search_flags()
        document = self.content_browser.document()
        cursor_position = self.content_browser.textCursor().position()

        total_matches, current_index = self._count_matches(
            document, search_text, search_flags, cursor_position
        )

        if total_matches == 0:
            self.results_count_label.setText(NO_RESULTS_TEXT)
        else:
            display_index = max(1, current_index)
            self.results_count_label.setText(
                RESULTS_TEMPLATE.format(current=display_index, total=total_matches)
            )

    def _count_matches(
        self, document: QTextDocument, text: str, flags, current_pos: int
    ) -> tuple[int, int]:
        count = 0
        current_match_index = 0
        cursor = document.find(text, 0, flags)

        while not cursor.isNull():
            count += 1
            if cursor.position() <= current_pos:
                current_match_index = count
            cursor = document.find(text, cursor, flags)

        return count, current_match_index

    def find_next(self):
        """Select the next match, wrapping to the start."""
        search_text = self.search_input.text()
        if search_text:
            flags = self._get_search_flags()
            found = self.content_browser.find(search_text, flags)

            if not found:
                self.content_browser.moveCursor(QTextCursor.MoveOperation.Start)
                self.content_browser.find(search_text, flags)

            self._update_search_results_count()

    def find_prev(self):
        """Select the previous match, wrapping to the end."""
        search_text = self.search_input.text()
        if search_text:
            flags = self._get_search_flags() | QTextDocument.FindFlag.FindBackward
            found = self.content_browser.find(search_text, flags)

            if not found:
                self.content_browser.moveCursor(QTextCursor.MoveOperation.End)
                self.content_browser.find(search_text, flags)

            self._update_search_results_count()

    def _load_changelog(self):
        version_tag = self._get_version_tag()
        cache_path = self._get_cache_path(version_tag)

        if cache_path.exists() and self._load_from_cache(cache_path):
            return

        url = GITHUB_URL_TEMPLATE.format(tag=version_tag)
        self.content_browser.setHtml(
            f"Fetching changelog from: <a href='{url}'>{url}</a>..."
        )
        self.pending_cache_path = cache_path
        self._start_download(url)

    def _get_version_tag(self) -> str:
        return self.version.to_tag()

    def _get_cache_path(self, version_tag: str) -> Path:
        cache_dir = paths.cache_dir() / CACHE_DIR_NAME
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"{version_tag}.md"

    def _load_from_cache(self, path: Path) -> bool:
        try:
            content = path.read_text("utf-8")
            self._set_content_from_markdown(content)
            return True
        except Exception as e:
            logger.warning("Could not read changelog cache: %s", e)
            return False

    def _start_download(self, url: str):
        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self._on_request_finished)

        request = QNetworkRequest(QUrl(url))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute, True)
        self.network_manager.get(request)

    @Slot(QNetworkReply)
    def _on_request_finished(self, reply: QNetworkReply):
        reply.deleteLater()
        if self.network_manager:
            self.network_manager.deleteLater()
            self.network_manager = None

        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.content_browser.setText(
                f"Couldn't fetch the changelog.\n\n{reply.errorString()}"
            )
            return

        status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if status_code != 200:
            self.content_browser.setText(
                f"Couldn't fetch the changelog (HTTP {status_code})."
            )
            return

        try:
            content = bytes(reply.readAll().data()).decode("utf-8")
            if self.pending_cache_path:
                try:
                    self.pending_cache_path.write_text(content, "utf-8")
                except Exception as e:
                    logger.warning("Could not cache changelog: %s", e)
            self._set_content_from_markdown(content)
        except Exception as e:
            self.content_browser.setText(f"Couldn't read the changelog.\n\n{e}")
