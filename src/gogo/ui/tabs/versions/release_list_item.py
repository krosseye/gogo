import webbrowser
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from godotkit.engine import GodotVersion, utils
from kq_icon_engine import FillMode, IconStyle, KQIcon
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QIcon,
    QMouseEvent,
    QPalette,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from gogo.core import engines, launcher
from gogo.ui.busy import busy_until_app_inactive
from gogo.ui.components.elided_label import ElidedLabel
from gogo.ui.components.emblem_widget import EmblemWidget
from gogo.ui.dialogs.install_engine import install_engine, install_events
from gogo.ui.graphics.icon_generator import IconGenerator

from .changelog_dialog import ChangelogDialog


def asset_url_to_release_url(asset_url: str) -> str:
    """GitHub asset download URL -> its release page URL."""
    parsed = urlparse(asset_url)
    parts = parsed.path.rstrip("/").split("/")[:-1]
    if "download" in parts:
        parts.remove("download")
    return urlunparse((parsed.scheme, parsed.netloc, "/".join(parts) + "/", "", "", ""))


class ReleaseListItem(QWidget):
    """One Godot release: either a download (`source` is a URL) or an installed
    engine (`source` is its install folder). `on_change` runs after install,
    uninstall or set-default, to refresh the list.
    """

    def __init__(
        self,
        version: GodotVersion,
        source: str,
        size_bytes: int,
        on_change: Callable[[], None],
        published_at: str | None = None,
    ) -> None:
        super().__init__()
        self.version = version
        self.source = source
        self.on_change = on_change
        self.is_remote = source.startswith("http")
        self.title = version.display_name
        self.published_at = published_at

        if self.is_remote:
            self.is_installed = str(version) in engines.list_installed()
            self.is_default = False
        else:
            self.is_installed = True
            self.is_default = engines.get_default() == Path(source)

        details_layout = QVBoxLayout()
        details_layout.setSpacing(2)
        details_layout.setContentsMargins(5, 5, 5, 5)
        version_label = QLabel(f"<h3>{self.title}</h3>")
        version_label.setToolTip("Version")
        details_layout.addWidget(version_label)
        source_layout = self._create_source_layout()
        if source_layout:
            details_layout.addLayout(source_layout)
        if size_bytes:
            details_layout.addLayout(self._create_size_layout(size_bytes))

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.addWidget(self._create_icon_label())
        main_layout.addLayout(details_layout, 1)
        main_layout.addLayout(self._create_meta_layout())

    def _create_icon_label(self) -> QLabel:
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedWidth(50)
        icon_label.setPixmap(
            IconGenerator.get_version_icon(str(self.version)).scaled(
                48,
                48,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        return icon_label

    def _create_source_layout(self) -> QHBoxLayout | None:
        """Release date for downloads, install folder for installed engines."""
        if self.is_remote:
            try:
                published = datetime.fromisoformat(self.published_at)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None
            label = QLabel(f"Released {published:%d %b %Y}")
            label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
            icon_label = QLabel(
                pixmap=KQIcon("calendar-blank", style=IconStyle.REGULAR).pixmap(16)
            )
        else:
            label = self.path_label = ElidedLabel(self.source)
            icon_label = QLabel(pixmap=QIcon.fromTheme("folder-open").pixmap(16, 16))
        icon_label.setStyleSheet("QLabel { padding-right: 4px; }")

        layout = QHBoxLayout()
        layout.addWidget(icon_label)
        layout.addWidget(label)
        layout.addStretch(1)
        return layout

    def _create_size_layout(self, size_bytes: int) -> QHBoxLayout:
        icon_label = QLabel()
        icon_name = "file-zip" if self.is_remote else "disc"
        icon_label.setPixmap(KQIcon(icon_name, style=IconStyle.REGULAR).pixmap(16))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedWidth(16)
        icon_label.setStyleSheet("QLabel { padding-right: 4px; }")

        size_label = QLabel(f"{size_bytes / (1024 * 1024):.2f} MB")
        size_label.setToolTip("Download size" if self.is_remote else "Size on disk")

        layout = QHBoxLayout()
        layout.addWidget(icon_label)
        layout.addWidget(size_label)
        return layout

    def _create_meta_layout(self) -> QVBoxLayout:
        """Badges: Default and/or Installed."""
        meta_layout = QVBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(4)

        if self.is_default:
            pixmap = KQIcon(
                "star", QColor("gold"), IconStyle.FILL, FillMode.GRADIENT
            ).pixmap(18)
            emblem = EmblemWidget("Default", pixmap)
            emblem.setToolTip("Default engine")
            meta_layout.addWidget(emblem)

        if self.is_installed and self.is_remote:
            pixmap = KQIcon(
                "check-circle", QColor("green"), IconStyle.FILL, FillMode.GRADIENT
            ).pixmap(18)
            emblem = EmblemWidget("Installed", pixmap)
            emblem.setToolTip("Installed on this computer")
            meta_layout.addWidget(emblem)

        return meta_layout

    def _install(self) -> None:
        if (
            QMessageBox.question(
                self,
                "Install Godot",
                f"Install Godot {self.title}?\n\nSource: {self.source}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            on_change = self.on_change  # this widget is rebuilt by the refresh
            install_engine(self, self.version, lambda _ok: on_change())

    def _launch(self) -> None:
        binary_path = utils.find_binary(Path(self.source))
        if not binary_path:
            QMessageBox.critical(
                self,
                "Launch Failed",
                f"Couldn't find the Godot executable in:\n\n{self.source}",
            )
            return
        try:
            launcher.start_engine(binary_path, self.title)
        except OSError as e:
            QMessageBox.critical(self, "Launch Failed", str(e))
            return
        busy_until_app_inactive()

    def _uninstall(self) -> None:
        if (
            QMessageBox.question(
                self,
                "Uninstall Godot",
                f"Uninstall Godot {self.title}?\n\n{self.source}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            try:
                utils.remove(Path(self.source))
                install_events.changed.emit()
                self.on_change()
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Uninstall Failed",
                    f"Couldn't uninstall Godot {self.title}.\n\n{e}",
                )

    def _set_default(self) -> None:
        engines.set_default(Path(self.source))
        self.on_change()

    def _add_remote_actions(self, menu: QMenu) -> None:
        verb = "Reinstall" if self.is_installed else "Install"
        install_action = menu.addAction(f"{verb} Godot {self.title}...")
        install_action.setIcon(QIcon.fromTheme("emblem-downloads"))
        install_action.triggered.connect(self._install)
        menu.addSeparator()

        release_url = asset_url_to_release_url(self.source)
        github_action = menu.addAction("Open on GitHub")
        github_action.setIcon(QIcon.fromTheme("emblem-symbolic-link"))
        github_action.triggered.connect(lambda: webbrowser.open(release_url))

        changelog_action = menu.addAction("View Changelog...")
        changelog_action.setIcon(QIcon.fromTheme("emblem-documents"))
        changelog_action.triggered.connect(
            lambda: ChangelogDialog(self.version, self).exec()
        )

        copy_action = menu.addAction("Copy Download Link")
        copy_action.setIcon(QIcon.fromTheme("edit-copy"))
        copy_action.triggered.connect(
            lambda: QApplication.clipboard().setText(self.source)
        )

    def _add_local_actions(self, menu: QMenu) -> None:
        launch_action = menu.addAction(f"Launch Godot {self.title}")
        launch_action.setIcon(QIcon.fromTheme("document-open"))
        launch_action.triggered.connect(self._launch)

        default_action = menu.addAction("Set as Default Engine")
        default_action.setIcon(QIcon.fromTheme("emblem-favorite"))
        default_action.setEnabled(not self.is_default)
        default_action.triggered.connect(self._set_default)
        menu.addSeparator()

        uninstall_action = menu.addAction("Uninstall...")
        uninstall_action.setIcon(QIcon.fromTheme("edit-delete"))
        uninstall_action.triggered.connect(self._uninstall)
        menu.addSeparator()

        open_folder_action = menu.addAction("Open in File Manager")
        open_folder_action.setIcon(QIcon.fromTheme("folder-open"))
        open_folder_action.triggered.connect(
            lambda: utils.open_directory(Path(self.source))
        )

        copy_action = menu.addAction("Copy Engine Path")
        copy_action.setIcon(QIcon.fromTheme("edit-copy"))
        binary = utils.find_binary(Path(self.source))
        if binary:
            copy_action.triggered.connect(
                lambda: QApplication.clipboard().setText(str(binary))
            )
        else:
            copy_action.setEnabled(False)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_remote:
                self._install()
            else:
                self._launch()
        event.accept()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        if self.is_remote:
            self._add_remote_actions(menu)
        else:
            self._add_local_actions(menu)
        menu.exec(event.globalPos())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "path_label"):
            self.path_label.setFixedWidth(int(self.width() * 0.5))
