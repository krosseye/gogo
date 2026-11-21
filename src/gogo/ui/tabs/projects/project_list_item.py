from godotkit import project as gdk_project
from godotkit.engine import GodotVersion
from godotkit.project import GodotProject
from kq_icon_engine import FillMode, IconStyle, KQCustomIcon, KQIcon
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QContextMenuEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gogo.core import engines, launcher, projects
from gogo.core.config import config
from gogo.core.constants import GODOT_ICON_PATH
from gogo.core.stats import StatsManager
from gogo.ui.busy import busy_until_app_inactive
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

        self.main_layout.addWidget(self.icon_label)
        self.main_layout.addLayout(details_layout)
        self.main_layout.addStretch()
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

        self.name_label = QLabel(f"<h3>{self.project.name}</h3>")

        self.desc_label = SlidingLabel(self.project.description)
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

        self.path_label = SlidingLabel(str(self.project.file_path))
        self.path_label.set_max_width(self.width() / 2 if self.width() > 0 else 200)
        self.path_label.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self.path_label.setToolTip("Project Path")
        path_layout.addWidget(self.path_label)

        return path_layout

    def _create_meta_layout(self):
        """Badges: engine version and favourite."""
        meta_layout = QVBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(4)

        version_string = str(self.project.engine_version)

        version_pixmap = IconGenerator.get_version_pin(version_string)

        self.version_emblem = EmblemWidget(version_string, version_pixmap)
        self.version_emblem.setToolTip("Preferred Engine Version")
        meta_layout.addWidget(self.version_emblem)

        fav_pixmap = KQIcon(
            "heart", QColor("red"), IconStyle.FILL, FillMode.GRADIENT
        ).pixmap(18)
        self.fav_emblem = EmblemWidget("Favourite", fav_pixmap)
        self.fav_emblem.setVisible(self.is_favourite)
        meta_layout.addWidget(self.fav_emblem)

        return meta_layout

    def mouseDoubleClickEvent(self, event):
        """Launches the project on a left button double-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_project()

        event.accept()

    def start_project(self):
        """Open the project in its engine, offering to fix a missing engine."""
        engine_version = self.project.engine_version
        version = str(engine_version)
        binary_path = installed_binary(version) if engine_version else None
        if not binary_path:
            self._resolve_missing_engine(engine_version)
            return
        try:
            launcher.start_project(
                binary_path, self.project.file_path, self.project.name
            )
        except Exception as e:
            QMessageBox.warning(self, "Cannot Open Project", str(e))
            return
        busy_until_app_inactive()
        projects.mark_opened(self.project.dir_path)

        StatsManager.track_project_launch()
        StatsManager.track_engine_usage(version)

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
                f"{self.project.name} uses Godot {engine_version}, which isn't installed."
            )
            install_btn = box.addButton(
                f"Install Godot {engine_version}", QMessageBox.ButtonRole.AcceptRole
            )
        else:
            box.setText(f"{self.project.name} has no engine version set.")
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

            install_engine(
                self, str(engine_version), None, after_install, version=engine_version
            )
        elif box.clickedButton() is other_btn:
            choice = choose_engine_version(
                self.window(),
                "Choose Engine Version",
                f"Open {self.project.name} with:",
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

        remove_action = menu.addAction("Remove Project")
        remove_action.setToolTip("Delete files")
        remove_action.setIcon(QIcon.fromTheme("edit-delete"))
        remove_action.triggered.connect(self.delete_requested.emit)

        forget_action = menu.addAction("Forget Project")
        forget_action.setToolTip("Forget files, but don't delete them")
        forget_action.setIcon(KQIcon("folder-minus", style=IconStyle.BOLD).pixmap(24))
        forget_action.triggered.connect(self.forget_requested.emit)

        menu.addSeparator()

        open_folder_action = menu.addAction("Open in File Manager")
        open_folder_action.setIcon(QIcon.fromTheme("folder-open"))
        open_folder_action.triggered.connect(self.project.open_directory)

        self._add_copy_action(menu, "Copy Project Path", str(self.project.file_path))

        menu.addSeparator()

        tools_menu = menu.addMenu(
            KQIcon("wrench", style=IconStyle.BOLD).pixmap(24), "Tools"
        )

        project_properties_action = tools_menu.addAction(
            KQIcon("gear", style=IconStyle.BOLD).pixmap(24), "Project Properties"
        )
        project_properties_action.triggered.connect(self._show_project_properties)

        disk_usage_action = tools_menu.addAction(
            KQIcon("chart-pie", style=IconStyle.BOLD).pixmap(24), "Disk Usage"
        )
        disk_usage_action.triggered.connect(self._show_disk_usage)

    def _show_project_properties(self):
        dialog = ProjectPropertiesDialog(self.project, self)
        if dialog.exec():
            gdk_project.parse.update(self.project.file_path, dialog.metadata)
            self.project = gdk_project.GodotProject(self.project.file_path)
            self._refresh_ui()

    def _refresh_meta(self):
        version_string = str(self.project.engine_version)

        version_pixmap = IconGenerator.get_version_pin(version_string)
        self.version_emblem.set_content(version_string, version_pixmap)

        self.fav_emblem.setVisible(self.is_favourite)

    def _refresh_ui(self):
        self.name_label.setText(f"<h3>{self.project.name}</h3>")
        self.desc_label.setText(self.project.description)
        self._set_icon_label(self.icon_label)

        self._refresh_meta()

    def _show_disk_usage(self):
        dialog = ProjectDiskUsageDialog(self.project.file_path.parent)
        dialog.exec()

    def _toggle_favourite(self):
        self.is_favourite = not self.is_favourite
        projects.set_favourite(self.project.dir_path, self.is_favourite)
        self.fav_emblem.setVisible(self.is_favourite)
        self.favourite_toggled.emit()

    def _add_copy_action(self, menu: QMenu, text: str, path_to_copy: str):
        copy_action = menu.addAction(text)
        copy_action.setIcon(QIcon.fromTheme("edit-copy"))
        copy_action.triggered.connect(
            lambda: QApplication.clipboard().setText(path_to_copy)
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "path_label"):
            self.path_label.set_max_width(self.width() * 0.5)
        if hasattr(self, "desc_label"):
            self.desc_label.set_max_width(self.width() * 0.5)
