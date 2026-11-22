from godotkit.engine import GodotVersion
from godotkit.project import GodotProject
from kq_icon_engine import FillMode, IconStyle, KQCustomIcon, KQIcon
from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QContextMenuEvent, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gogo.core import engines, launcher, projects
from gogo.core.config import config
from gogo.core.constants import GODOT_ICON_PATH
from gogo.core.stats import StatsManager
from gogo.ui.busy import busy_until_app_inactive
from gogo.ui.components.elided_label import ElidedLabel
from gogo.ui.components.emblem_widget import EmblemWidget
from gogo.ui.components.sliding_label import SlidingLabel
from gogo.ui.components.version_selector import choose_engine_version
from gogo.ui.dialogs.disk_usage import ProjectDiskUsageDialog
from gogo.ui.dialogs.install_engine import install_engine, installed_binary
from gogo.ui.dialogs.project_properties.dialog import ProjectPropertiesDialog
from gogo.ui.graphics.icon_generator import IconGenerator


class ProjectListItem(QWidget):
    """One project in the projects list."""

    favourite_toggled = Signal()
    forget_requested = Signal()
    delete_requested = Signal()

    def __init__(
        self,
        godot_project: GodotProject,
    ):
        super().__init__()
        self.project = godot_project

        self.is_favourite = projects.is_favourite(self.project.dir_path)

        self.setAutoFillBackground(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QHBoxLayout(self)

        self.icon_label = QLabel()
        self._set_icon_label(self.icon_label)

        details_layout = self._create_details_layout()

        self.meta_layout = self._create_meta_layout()

        inset = (
            self.fav_button.sizeHint().width() - self.fav_button.iconSize().width()
        ) // 2
        m = self.main_layout.contentsMargins()
        self.main_layout.setContentsMargins(
            max(0, m.left() - inset), m.top(), m.right(), m.bottom()
        )
        self.main_layout.addWidget(self.fav_button)
        self.main_layout.addWidget(self.icon_label)
        self.main_layout.addLayout(details_layout, 1)
        self.main_layout.addLayout(self.meta_layout)

        self.setLayout(self.main_layout)

    def _set_icon_label(self, label):
        icon_size = 48

        if self.project.icon_path and self.project.icon_path.exists():
            pixmap = QPixmap(self.project.icon_path).scaled(
                icon_size,
                icon_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            pixmap = KQCustomIcon(GODOT_ICON_PATH).pixmap(icon_size)

        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedWidth(icon_size + 2)

    def _create_details_layout(self):
        """Creates the layout containing project name, description, and path."""
        details_layout = QVBoxLayout()
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(2)

        self.name_label = QLabel(f"<h3>{self._name}</h3>")

        self.desc_label = SlidingLabel(self.project.description or "")
        self.desc_label.set_italic(False)
        self.desc_label.set_max_width(self.width() / 2 if self.width() > 0 else 200)
        self.desc_label.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )

        project_path_layout = self._create_project_path_layout()

        details_layout.addWidget(self.name_label)
        details_layout.addWidget(self.desc_label)
        details_layout.addLayout(project_path_layout)

        return details_layout

    def _create_project_path_layout(self):
        """Creates the QHBoxLayout for the folder icon and sliding path label."""
        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(2)

        folder_icon = QLabel(pixmap=QIcon.fromTheme("folder-open").pixmap(16, 16))
        folder_icon.setStyleSheet("QLabel { padding-right: 4px; }")
        path_layout.addWidget(folder_icon)

        self.path_label = ElidedLabel(str(self.project.file_path))
        path_layout.addWidget(self.path_label)
        path_layout.addStretch(1)

        return path_layout

    def _create_meta_layout(self):
        """Badges: engine version and favourite."""
        meta_layout = QVBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(4)

        self.version_emblem = EmblemWidget(*self._version_badge())
        self.version_emblem.setToolTip("Preferred engine version")
        meta_layout.addWidget(self.version_emblem)

        self._fav_icons = (
            KQIcon("heart", style=IconStyle.REGULAR),
            KQIcon("heart", QColor("red"), IconStyle.FILL, FillMode.GRADIENT),
        )
        self.fav_button = QToolButton()
        self.fav_button.setIconSize(QSize(18, 18))
        self.fav_button.setAutoRaise(True)
        self.fav_button.clicked.connect(self._toggle_favourite)
        self._sync_fav_button()

        return meta_layout

    def mouseDoubleClickEvent(self, event):
        """Launches the project on a left button double-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_project()

        event.accept()

    def start_project(self):
        """Open the project in its engine, offering to fix a missing engine."""
        engine_version = self.project.engine_version
        binary_path = installed_binary(engine_version) if engine_version else None
        if not binary_path:
            self._resolve_missing_engine(engine_version)
            return
        try:
            launcher.start_project(binary_path, self.project.file_path, self._name)
        except Exception as e:
            QMessageBox.warning(self, "Cannot Open Project", str(e))
            return
        busy_until_app_inactive()
        projects.mark_opened(self.project.dir_path)

        StatsManager.track_project_launch()
        StatsManager.track_engine_usage(str(engine_version))

        instance = QApplication.instance()
        if not instance:
            return
        if config.get("close_on_project_open"):
            instance.quit()
        elif config.get("minimize_on_project_open"):
            self.window().showMinimized()

    def _resolve_missing_engine(self, engine_version: GodotVersion | None) -> None:
        """Offer to install the project's engine or switch it to an installed one."""
        installed = list(engines.list_installed())
        box = QMessageBox(self.window())
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Engine Not Installed")
        if engine_version:
            box.setText(
                f"{self._name} uses Godot {engine_version.display_name}, "
                "which isn't installed."
            )
            install_btn = box.addButton(
                f"Install Godot {engine_version.display_name}",
                QMessageBox.ButtonRole.AcceptRole,
            )
        else:
            box.setText(f"{self._name} has no engine version set.")
            install_btn = None
        other_btn = (
            box.addButton("Use Another Version...", QMessageBox.ButtonRole.ActionRole)
            if installed
            else None
        )
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()

        if box.clickedButton() is install_btn and engine_version:

            def after_install(installed_ok: bool) -> None:
                if installed_ok:
                    self.start_project()

            install_engine(self, engine_version, after_install)
        elif box.clickedButton() is other_btn:
            choice = choose_engine_version(
                self.window(),
                "Choose Engine Version",
                f"Open {self._name} with:",
            )
            if choice:
                self.project.engine_version = GodotVersion.parse(choice)
                self._refresh_meta()
                self.start_project()

    def contextMenuEvent(self, event: QContextMenuEvent):
        menu = QMenu(self)
        self._populate_context_menu(menu)
        menu.exec(event.globalPos())

    def _populate_context_menu(self, menu: QMenu):
        launch_action = menu.addAction("Launch in Godot")
        launch_action.setIcon(QIcon.fromTheme("document-open"))
        launch_action.triggered.connect(self.start_project)

        menu.addSeparator()

        favourite_action_text = (
            "Remove from Favourites" if self.is_favourite else "Add to Favourites"
        )
        favourite_action = menu.addAction(favourite_action_text)
        favourite_action.setIcon(QIcon.fromTheme("emblem-favorite"))
        favourite_action.triggered.connect(self._toggle_favourite)

        menu.addSeparator()

        remove_action = menu.addAction("Delete Project...")
        remove_action.setToolTip("Delete the project folder")
        remove_action.setIcon(QIcon.fromTheme("edit-delete"))
        remove_action.triggered.connect(self.delete_requested.emit)

        forget_action = menu.addAction("Forget Project...")
        forget_action.setToolTip("Remove from the list. Files stay on disk.")
        forget_action.setIcon(KQIcon("eye-slash", style=IconStyle.REGULAR).pixmap(24))
        forget_action.triggered.connect(self.forget_requested.emit)

        menu.addSeparator()

        open_folder_action = menu.addAction("Open in File Manager")
        open_folder_action.setIcon(QIcon.fromTheme("folder-open"))
        open_folder_action.triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.project.dir_path))
            )
        )

        self._add_copy_action(menu, "Copy Project Path", str(self.project.file_path))

        menu.addSeparator()

        tools_menu = menu.addMenu(
            KQIcon("wrench", style=IconStyle.REGULAR).pixmap(24), "Tools"
        )

        project_properties_action = tools_menu.addAction(
            KQIcon("gear", style=IconStyle.REGULAR).pixmap(24), "Project Properties..."
        )
        project_properties_action.triggered.connect(self._show_project_properties)

        disk_usage_action = tools_menu.addAction(
            KQIcon("chart-pie", style=IconStyle.REGULAR).pixmap(24), "Disk Usage..."
        )
        disk_usage_action.triggered.connect(self._show_disk_usage)

    def _show_project_properties(self):
        dialog = ProjectPropertiesDialog(self.project, self)
        if dialog.exec():
            self.project.update(dialog.metadata)
            self._refresh_ui()

    def _version_badge(self) -> tuple[str, QPixmap]:
        """Text and icon of the engine version badge."""
        version = self.project.engine_version
        text = version.display_name if version else "None"
        return text, IconGenerator.get_version_pin(str(version))

    def _refresh_meta(self):
        self.version_emblem.set_content(*self._version_badge())
        self._sync_fav_button()

    def _sync_fav_button(self):
        self.fav_button.setIcon(self._fav_icons[self.is_favourite])
        text = "Remove from Favourites" if self.is_favourite else "Add to Favourites"
        self.fav_button.setToolTip(text)
        self.fav_button.setAccessibleName(text)

    def _refresh_ui(self):
        self.name_label.setText(f"<h3>{self._name}</h3>")
        self.desc_label.setText(self.project.description or "")
        self._set_icon_label(self.icon_label)

        self._refresh_meta()

    @property
    def _name(self) -> str:
        return self.project.name or projects.UNNAMED_PROJECT

    def _show_disk_usage(self):
        dialog = ProjectDiskUsageDialog(self.project.file_path.parent)
        dialog.exec()

    def _toggle_favourite(self):
        self.is_favourite = not self.is_favourite
        projects.set_favourite(self.project.dir_path, self.is_favourite)
        self._sync_fav_button()
        self.favourite_toggled.emit()

    def _add_copy_action(self, menu: QMenu, text: str, path_to_copy: str):
        copy_action = menu.addAction(text)
        copy_action.setIcon(QIcon.fromTheme("edit-copy"))
        copy_action.triggered.connect(
            lambda: QApplication.clipboard().setText(path_to_copy)
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "desc_label"):
            self.desc_label.set_max_width(self.width() * 0.5)
            self.path_label.setFixedWidth(int(self.width() * 0.5))
