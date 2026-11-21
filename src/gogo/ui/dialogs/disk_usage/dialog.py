import time
from pathlib import Path

from godotkit.project.parse import read as read_project_config
from kq_icon_engine import IconStyle, KQIcon
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gogo.ui.components.sliding_label import SlidingLabel
from gogo.ui.graphics.icon_generator import IconGenerator

from .chart_widget import ChartWidget
from .file_list_widget import FileListWidget
from .scanner import ProjectScanner
from .utils import format_bytes


class ProjectDiskUsageDialog(QDialog):
    """Dialog displaying a breakdown of project file composition and disk usage."""

    MINIMUM_SIZE = (750, 550)
    MIN_SCAN_TIME_MS = 1000

    def __init__(self, project_path: Path, parent: QWidget | None = None):
        """Raises ValueError if `project_path` has no project.godot."""
        super().__init__(parent)
        self._project_path = Path(project_path)
        self._cached_stats: dict | None = None

        config_path = self._project_path / "project.godot"
        if not config_path.exists():
            raise ValueError("Invalid Godot project path. No project.godot found.")

        project_config = read_project_config(config_path)
        self._project_name = project_config.get("name", "Unknown Project")

        icon_path = project_config.get("icon_path", "")
        self.project_icon = (
            QPixmap(icon_path)
            if icon_path
            else IconGenerator.get_project_icon(self._project_name)
        )

        self._setup_window()
        self._setup_ui()
        QTimer.singleShot(500, self._start_scan)

    def _setup_window(self):
        self.setWindowTitle("Project Disk Usage")
        self.setMinimumSize(*self.MINIMUM_SIZE)
        self.resize(850, 600)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._chart_widget = ChartWidget()
        left_layout.addWidget(self._create_info_panel())
        left_layout.addWidget(self._chart_widget, 1)

        self._file_list_widget = FileListWidget(str(self._project_path), self)

        splitter.addWidget(left_panel)
        splitter.addWidget(self._file_list_widget)
        splitter.setSizes([int(self.width() * 0.55), int(self.width() * 0.45)])

        main_layout.addWidget(splitter, 1)
        main_layout.addWidget(self._create_footer_section())

        self._chart_widget.refreshed.connect(self._reset_summary_label)
        self._chart_widget.category_selected.connect(self._on_category_selected)
        self._chart_widget.category_hovered.connect(self._on_slice_hover)

    def _create_labeled_row(
        self, icon: str | QPixmap, widget: QWidget, size: int = 16
    ) -> QHBoxLayout:
        """`widget` with an icon (a Phosphor icon name or a pixmap) on its left."""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        if isinstance(icon, str):
            pixmap = KQIcon(icon, style=IconStyle.BOLD).pixmap(size)
        else:
            pixmap = icon

        icon_label.setPixmap(
            pixmap.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        icon_label.setFixedSize(size, size)

        layout.addWidget(icon_label)
        layout.addWidget(widget)
        return layout

    def _create_info_panel(self) -> QFrame:
        """Header with the project name, git branch and path."""
        container = QFrame()
        container.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QVBoxLayout(container)

        title_label = QLabel(f"<h2>{self._project_name} Disk Usage</h2>")
        title_label.setWordWrap(True)
        layout.addLayout(
            self._create_labeled_row(self.project_icon, title_label, size=32)
        )

        branch = self.get_git_branch(self._project_path)
        if branch:
            branch_label = QLabel(f"<b>Active branch:</b> <i>{branch}</i>")
            layout.addLayout(self._create_labeled_row("git-branch", branch_label))

        self.path_label = SlidingLabel(str(self._project_path))
        self.path_label.setStyleSheet("font-family: 'JetBrains Mono'; color: grey;")
        layout.addLayout(self._create_labeled_row("folder", self.path_label))

        return container

    @staticmethod
    def get_git_branch(project_path: Path) -> str | None:
        """The checked-out branch (or short commit hash), or None if not a git repo."""
        git_path = project_path.resolve() / ".git"
        if not git_path.exists():
            return None

        if git_path.is_file():
            content = git_path.read_text().strip()
            if content.startswith("gitdir:"):
                git_path = (project_path / content.split(":", 1)[1].strip()).resolve()

        head_file = git_path / "HEAD"
        if not head_file.exists():
            return None

        head = head_file.read_text().strip()
        return head.split("/")[-1] if head.startswith("ref:") else head[:7]

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.path_label.set_max_width(self.width() * 0.55)

    def _create_footer_section(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self._summary_label = QLabel("Scanning...")
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(12)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()

        layout.addWidget(self._summary_label, 1)
        layout.addWidget(self._progress_bar)
        return container

    def _start_scan(self):
        self._scan_start_time = time.time()
        self._progress_bar.show()
        self._progress_bar.setRange(0, 0)

        self._scanner = ProjectScanner(self._project_path)
        self._scanner.scan_progress.connect(
            lambda msg: self._summary_label.setText(f"Scanning: {msg}")
        )
        self._scanner.scan_finished.connect(self._on_scan_finished)
        self._scanner.start()

    def _on_scan_finished(self, stats: dict):
        """Show the results, keeping the progress bar up for at least MIN_SCAN_TIME_MS."""
        elapsed_ms = (time.time() - self._scan_start_time) * 1000
        delay = max(0, self.MIN_SCAN_TIME_MS - elapsed_ms)
        QTimer.singleShot(int(delay), lambda: self._finalize_scan(stats))

    def _finalize_scan(self, stats: dict):
        self._cached_stats = stats
        self._progress_bar.hide()
        self._chart_widget.set_stats(stats)

    def _reset_summary_label(self):
        """Show the project totals in the footer."""
        size, count = self._chart_widget.get_display_totals()
        dominant = self._chart_widget.get_dominant_category()

        parts = [
            f"<b>Total size:</b> {format_bytes(size)}",
            f"<b>Files:</b> {count}",
        ]

        if dominant and size > 0:
            name, dom_size = dominant
            percent = (dom_size / size) * 100
            parts.append(
                f"<b>Dominant:</b> {name} ({format_bytes(dom_size)}, {percent:.0f}%)"
            )

        self._summary_label.setText(" &nbsp;|&nbsp; ".join(parts))

    def _on_slice_hover(self, hovered: bool, label: str, size: int, count: int):
        """Show the hovered category in the footer, or the totals when it's left."""
        if not hovered:
            self._reset_summary_label()
            return

        total_size, _ = self._chart_widget.get_display_totals()
        percent = (size / total_size * 100) if total_size > 0 else 0
        self._summary_label.setText(
            f"<b>{label}</b>: {format_bytes(size)} ({percent:.1f}%) &nbsp;|&nbsp; {count} files"
        )

    def _on_category_selected(self, category: str | None):
        if category and self._cached_stats:
            self._file_list_widget.update_list(category, self._cached_stats[category])
        else:
            self._file_list_widget.clear()
