import platform

from godotkit.engine.release_fetcher import detect_architecture
from PySide6.QtCore import Qt, QThread, QTimer, Signal, qVersion
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gogo.core.constants import APP_ICON_PATH, APP_TITLE, APP_VERSION, DEVELOPER
from gogo.core.stats import StatsManager, UsageStats

_HTML_DESCRIPTION = """
<p>
    A project and version manager for the <a href="https://godotengine.org/" target="_blank">Godot Engine</a>.
    {app_title} is free and open-source software licensed under the <a href="https://opensource.org/licenses/MIT" target="_blank">MIT License</a>.
</p>
"""

_HTML_VERSION_INFO = """
<p>You are currently using <strong>{app_title} v{app_version}</strong>, as well as:</p>
<ul>
    <li><strong>Python:</strong> {python_ver}</li>
    <li><strong>Qt:</strong> {qt_ver}</li>
    <li><strong>OS:</strong> {os_sys} {os_rel}</li>
    <li><strong>Architecture:</strong> {arch}</li>
</ul>
"""

_HTML_THIRD_PARTY = """
<p>This application is made possible by the following open-source projects:</p>
<ul>
    <li>
        <strong>Godot Engine:</strong> Downloaded and managed by {app_title} (not bundled).
        Licensed under <a href="https://opensource.org/licenses/MIT" target="_blank">MIT License</a>
    </li>
    <li>
        <strong>Godot Logo:</strong> Used for application branding.
        Licensed under <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank">CC-BY 4.0</a>
    </li>
    <li>
        <strong>PySide6 (Qt for Python):</strong> GUI framework.
        Licensed under <a href="https://www.gnu.org/licenses/lgpl-3.0.html" target="_blank">LGPLv3 License</a>
    </li>
    <li>
        <strong>Phosphor Icons:</strong> Used for UI elements.
        Licensed under <a href="https://opensource.org/licenses/MIT" target="_blank">MIT License</a>
    </li>
    <li>
        <strong>GodotKit:</strong> Powers Godot related functionality.
        Licensed under <a href="https://opensource.org/licenses/MIT" target="_blank">MIT License</a>
    </li>
</ul>
"""

_HTML_STATS = """
<table width="100%" cellpadding="5">
    <tr>
        <td align="center">Secret Discovered<br><b>{dialog_first_found}</b></td>
        <td align="center">Secret Visits<br><b>{dialog_views}</b></td>
    </tr>
    <tr>
        <td width="50%" align="center">First Opened<br><b>{first_opened}</b></td>
        <td width="50%" align="center">Total Launches<br><b>{open_count}</b></td>
    </tr>
    <tr>
        <td align="center">Projects Launched<br><b>{project_launches}</b> 🚀</td>
        <td align="center">Favourite Engine<br><b>{most_used_engine}</b> 🤖</td>
    </tr>
    <tr>
        <td align="center">Current Streak<br><b>{current_streak}</b> {emoji}</td>
        <td align="center">Best Streak<br><b>{longest_streak}</b> 🏆</td>
    </tr>
</table>
"""

_HTML_COPYRIGHT = """
<div align="center">
    <em>Copyright © 2025 {developer}. All rights reserved.</em>
</div>
"""


def _os_release() -> str:
    release = platform.release()
    # Windows 11 still reports itself as 10
    if platform.system() == "Windows" and release == "10":
        build = platform.version().split(".")[-1]
        if build.isdigit() and int(build) >= 22000:
            return "11"
    return release


class StatsWorker(QThread):
    stats_ready = Signal(object)

    def run(self):
        self.stats_ready.emit(StatsManager.register_dialog_view())


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setFixedSize(500, 450)
        self._stats: UsageStats | None = None
        self._setup_ui()

        self.worker = StatsWorker()
        self.worker.stats_ready.connect(self._on_stats_ready)
        self.worker.finished.connect(self.worker.deleteLater)
        QTimer.singleShot(1000, self.worker.start)

    def _on_stats_ready(self, stats: UsageStats) -> None:
        self._stats = stats
        self.stats_label.setText(self._get_stats_html())

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        content_layout.addWidget(
            self._create_icon_label(),
            0,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
        )

        content_layout.addWidget(self._create_info_scroll_area(), 1)

        main_layout.addLayout(content_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.setFixedWidth(100)
        close_button.clicked.connect(self.accept)

        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)

    def _create_icon_label(self) -> QLabel:
        """Creates the application icon label."""
        icon_label = QLabel()
        pixmap = QPixmap(APP_ICON_PATH)
        if not pixmap.isNull():
            icon_label.setPixmap(
                pixmap.scaled(
                    96,
                    96,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        return icon_label

    def _create_info_scroll_area(self) -> QScrollArea:
        """Creates the scrollable area containing the about information."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)

        title_label = QLabel(f"<h2>About {APP_TITLE}</h2>")
        layout.addWidget(title_label)

        layout.addWidget(
            self._create_panel("Description", self._get_description_html())
        )
        layout.addWidget(
            self._create_panel("Version Information", self._get_version_html())
        )
        layout.addWidget(
            self._create_panel("Third-Party Notices", self._get_third_party_html())
        )

        stats_frame, self.stats_label = self._create_panel_with_label(
            "Secret Stats", self._get_stats_html()
        )
        layout.addWidget(stats_frame)

        copyright_label = QLabel(_HTML_COPYRIGHT.format(developer=DEVELOPER))
        layout.addStretch()
        layout.addWidget(copyright_label)

        scroll_area.setWidget(container)
        return scroll_area

    def _create_panel(self, title: str, content: str) -> QFrame:
        frame, _ = self._create_panel_with_label(title, content)
        return frame

    def _create_panel_with_label(
        self, title: str, content: str
    ) -> tuple[QFrame, QLabel]:
        """Creates a styled frame with a title and content label."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Plain)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        if title:
            title_label = QLabel(f"<h3>{title}</h3>")
            layout.addWidget(title_label)

        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setOpenExternalLinks(True)
        content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        layout.addWidget(content_label)

        return frame, content_label

    def _get_description_html(self) -> str:
        return _HTML_DESCRIPTION.format(app_title=APP_TITLE)

    def _get_version_html(self) -> str:
        return _HTML_VERSION_INFO.format(
            app_title=APP_TITLE,
            app_version=APP_VERSION,
            python_ver=platform.python_version(),
            qt_ver=qVersion(),
            os_sys=platform.system(),
            os_rel=_os_release(),
            arch=detect_architecture(),
        )

    def _get_third_party_html(self) -> str:
        return _HTML_THIRD_PARTY.format(app_title=APP_TITLE)

    def _get_stats_html(self) -> str:
        if self._stats is None:
            return "<p align='center'>Calculating...</p>"
        return _HTML_STATS.format(
            **self._stats._asdict(),
            emoji=StatsManager.get_emoji(self._stats.current_streak),
        )
