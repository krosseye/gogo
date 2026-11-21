from pathlib import Path

from godotkit.common import git_installed
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
)

from gogo.core import config
from gogo.ui.components.version_selector import VersionSelector


class ProjectConfigGroup(QGroupBox):
    """Widget for project configuration (location, version, git)."""

    config_changed = Signal()

    def __init__(self, parent=None):
        super().__init__("Configuration", parent)

        self._setup_ui()
        self._load_defaults()

    def _setup_ui(self) -> None:
        form_layout = QFormLayout(self)

        self._location_edit = QLineEdit()
        self._location_edit.setPlaceholderText("Project location")
        self._location_edit.textChanged.connect(self.config_changed)

        browse_btn = QPushButton("Browse")
        browse_btn.setIcon(QIcon.fromTheme("folder-open"))
        browse_btn.clicked.connect(self._browse_location)

        location_layout = QHBoxLayout()
        location_layout.addWidget(self._location_edit)
        location_layout.addWidget(browse_btn)

        self._version_combo = VersionSelector()
        self._version_combo.currentIndexChanged.connect(self.config_changed)

        self._git_checkbox = QCheckBox("Initialise Git Repository")
        if not git_installed():
            self._git_checkbox.setEnabled(False)
            self._git_checkbox.setToolTip("Git isn't installed.")
        else:
            self._git_checkbox.setChecked(True)

        form_layout.addRow("<b>Location:</b>", location_layout)
        form_layout.addRow("<b>Godot Version:</b>", self._version_combo)
        form_layout.addRow(self._git_checkbox)

    def _load_defaults(self) -> None:
        default_path = Path(config["default_project_path"]).expanduser()
        if not default_path.exists():
            try:
                default_path.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        self._location_edit.setText(str(default_path.resolve()))

    def _browse_location(self) -> None:
        current_path = self._location_edit.text()
        directory = QFileDialog.getExistingDirectory(
            self, "Select Project Location", current_path
        )
        if directory:
            self._location_edit.setText(directory)

    def get_location(self) -> str:
        return self._location_edit.text().strip()

    def get_selected_version(self) -> str | None:
        return self._version_combo.get_selected_version()

    def is_git_enabled(self) -> bool:
        return self._git_checkbox.isChecked()
