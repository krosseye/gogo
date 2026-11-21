import tempfile
from collections.abc import Callable
from pathlib import Path

from godotkit.engine import GodotVersion
from godotkit.project.parse import create
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from gogo.core import projects

from .project_config_group import ProjectConfigGroup
from .project_details_group import ProjectDetailsGroup
from .success_dialog import ProjectCreatedDialog


class CreateProjectDialog(QDialog):
    """Create a new Godot project; `callback` runs after it is created."""

    def __init__(self, callback: Callable | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._callback = callback

        self.setWindowTitle("Create New Project")
        self.setMinimumWidth(450)

        self._setup_ui()
        self._details_group.details_changed.connect(self._validate_project)
        self._config_group.config_changed.connect(self._validate_project)

        self._validate_project()
        self._details_group.set_name_focus()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)

        self._details_group = ProjectDetailsGroup()

        icon_widget = self._details_group.get_icon_widget()
        icon_layout = QVBoxLayout()
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        icon_layout.addWidget(icon_widget)
        icon_layout.addStretch()

        self._config_group = ProjectConfigGroup()

        right_layout = QVBoxLayout()
        right_layout.addWidget(self._details_group)
        right_layout.addWidget(self._config_group)
        right_layout.addStretch()
        right_layout.addLayout(self._create_button_layout())

        main_layout.addLayout(icon_layout)
        main_layout.addLayout(right_layout)

    def _create_button_layout(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        self._create_button = QPushButton("Create Project")
        self._create_button.setDefault(True)
        self._create_button.setEnabled(False)
        self._create_button.clicked.connect(self._create_project)

        layout.addStretch()
        layout.addWidget(cancel_btn)
        layout.addWidget(self._create_button)

        return layout

    def _validate_project(self) -> None:
        """Enable Create only for a name and an existing location with no non-empty folder of that name."""
        raw_name = self._details_group.get_name()
        sanitized_name = self._details_group.get_sanitized_name()
        location_str = self._config_group.get_location()

        is_valid = False
        if raw_name and location_str:
            location_path = Path(location_str)
            if location_path.exists():
                project_path = location_path / sanitized_name
                if not (project_path.exists() and any(project_path.iterdir())):
                    is_valid = True

        self._create_button.setEnabled(is_valid)

    def _create_project(self) -> None:
        name = self._details_group.get_name()
        sanitized_name = self._details_group.get_sanitized_name()
        description = self._details_group.get_description() or "A new Godot project."

        base_location = Path(self._config_group.get_location())
        project_path = (base_location / sanitized_name).resolve()
        version_name = self._config_group.get_selected_version()
        if not version_name:
            return

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_icon = Path(temp_dir) / "icon.png"
                self._details_group.get_icon_pixmap().save(str(temp_icon), "PNG")

                create(
                    project_path,
                    name,
                    description,
                    icon_path=temp_icon,
                    engine_version=GodotVersion.parse(version_name),
                    git_init=self._config_group.is_git_enabled(),
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Creation Failed", f"Couldn't create the project.\n\n{e}"
            )
            return

        projects.add(project_path)
        ProjectCreatedDialog(
            name, str(project_path), project_path / "icon.png", self
        ).exec()

        if self._callback:
            self._callback()
        self.accept()
