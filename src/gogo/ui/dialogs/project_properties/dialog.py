from pathlib import Path

from godotkit.engine import GodotVersion
from godotkit.project import GodotProject
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gogo.ui.components.tag_widget import TagEditor
from gogo.ui.components.version_selector import VersionSelector


class ClickableLabel(QLabel):
    """A QLabel that emits a `clicked` signal on a left-mouse-button press."""

    clicked = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ProjectPropertiesDialog(QDialog):
    """Edit a project's metadata; on accept, the caller saves `self.metadata`."""

    def __init__(self, project: GodotProject, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = project
        self.metadata = project.metadata.copy()
        self.setWindowTitle("Project Properties")
        self.setMinimumWidth(500)
        self._setup_ui()
        self._load_metadata()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        content_layout.addLayout(self._create_icon_section())
        details_group = QGroupBox("Project Details")
        details_group.setLayout(self._create_details_section())
        content_layout.addWidget(details_group, 1)
        main_layout.addLayout(content_layout)

        buttons_layout = self._create_buttons_section()
        main_layout.addStretch()
        main_layout.addLayout(buttons_layout)

    def _create_icon_section(self) -> QVBoxLayout:
        icon_layout = QVBoxLayout()
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.icon_label = ClickableLabel()
        self.icon_label.setFixedSize(96, 96)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setObjectName("IconPreviewLabel")
        self.icon_label.setToolTip("Click to change icon")
        self.icon_label.setStyleSheet(
            """
            #IconPreviewLabel {
                border: 2px dashed #ccc;
                border-radius: 8px;
                background-color: palette(base);
            }
            #IconPreviewLabel:hover {
                border-color: palette(highlight);
                background-color: palette(light);
            }
            """
        )
        self.icon_label.clicked.connect(self._choose_icon)

        self.icon_path_label = QLabel("No icon selected")
        self.icon_path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_path_label.setWordWrap(True)
        self.icon_path_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)

        icon_layout.addWidget(self.icon_label)
        icon_layout.addWidget(self.icon_path_label)

        return icon_layout

    def _create_details_section(self) -> QVBoxLayout:
        details_layout = QVBoxLayout()
        details_layout.setSpacing(10)

        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("My Game")
        self.version_edit = QLineEdit()
        self.version_edit.setPlaceholderText("1.0.0")
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText("A short description of the project")
        self.description_edit.setFixedHeight(80)

        self.engine_version_selector = VersionSelector(self)

        self.tags_edit = TagEditor(parent=self)

        form_layout.addRow("Name:", self.name_edit)
        form_layout.addRow("Version:", self.version_edit)
        form_layout.addRow("Engine version:", self.engine_version_selector)
        form_layout.addRow("Description:", self.description_edit)
        form_layout.addRow("Tags:", self.tags_edit)

        details_layout.addLayout(form_layout)

        details_layout.addStretch()

        return details_layout

    def _create_buttons_section(self) -> QHBoxLayout:
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)

        self.save_button = QPushButton("Save Changes")
        self.save_button.setAutoDefault(False)
        self.save_button.setDefault(False)
        self.save_button.clicked.connect(self._save_metadata)

        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.save_button)
        return buttons_layout

    def _load_metadata(self):
        self.name_edit.setText(self.metadata.get("name", ""))
        self.version_edit.setText(self.metadata.get("version", ""))
        self.description_edit.setPlainText(self.metadata.get("description", ""))
        self.tags_edit.set_tags(list(self.metadata.get("tags") or []))

        engine_version = self.project.engine_version
        if engine_version:
            self.engine_version_selector.set_selected_version(engine_version)
        icon_path = self.metadata.get("icon_path")
        self._update_icon_display(icon_path)

    def _update_icon_display(self, icon_path: Path | None):
        if icon_path and Path(icon_path).exists():
            pixmap = QPixmap(str(icon_path))
            self.icon_label.setPixmap(
                pixmap.scaled(
                    64,
                    64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.icon_path_label.setText(Path(icon_path).name)
            self.icon_path_label.setToolTip(str(icon_path))
        else:
            self.icon_label.setPixmap(QPixmap())
            self.icon_path_label.setText("No icon selected")
            self.icon_path_label.setToolTip("")

    def _choose_icon(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Icon",
            str(self.project.dir_path),
            "Images (*.png *.jpg *.ico *.svg)",
        )
        if path:
            icon_path = Path(path)
            self.metadata["icon_path"] = icon_path
            self._update_icon_display(icon_path)

    def _save_metadata(self):
        """Copy the fields into `self.metadata`, confirming risky engine changes."""
        self.metadata["name"] = self.name_edit.text() or None
        self.metadata["version"] = self.version_edit.text() or None
        self.metadata["description"] = self.description_edit.toPlainText() or None
        self.metadata["tags"] = list(self.tags_edit.get_tags() or []) or None

        selected_engine_str = self.engine_version_selector.get_selected_version()
        if not selected_engine_str:
            self.accept()
            return

        current_engine_version = self.project.engine_version
        current_engine_str = (
            str(current_engine_version) if current_engine_version else None
        )

        if selected_engine_str != current_engine_str:
            try:
                selected_version = GodotVersion.parse(selected_engine_str)
                current_version = current_engine_version or GodotVersion(0, 0, 0)

                if selected_version < current_version:
                    reply = QMessageBox.warning(
                        self,
                        "Engine Version Downgrade",
                        f"You are about to downgrade from Godot {current_version.display_name} to {selected_version.display_name}.\n\n"
                        "This can cause compatibility issues or project corruption. "
                        "Back up your project before continuing.\n\n"
                        "Continue?",
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.Cancel,
                        QMessageBox.StandardButton.Cancel,
                    )
                    if reply == QMessageBox.StandardButton.Cancel:
                        return

                elif (
                    selected_version.major > current_version.major
                    and current_version.major > 0
                ):
                    reply = QMessageBox.warning(
                        self,
                        "Major Engine Upgrade",
                        f"You are about to upgrade from Godot {current_version.major}.x to {selected_version.major}.x.\n\n"
                        "Major version upgrades can introduce breaking changes. "
                        "Check the official Godot migration guides first.\n\n"
                        "Continue?",
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.Cancel,
                        QMessageBox.StandardButton.Cancel,
                    )
                    if reply == QMessageBox.StandardButton.Cancel:
                        return

                self.metadata["engine_version"] = selected_version

            except Exception as e:
                QMessageBox.critical(
                    self, "Save Failed", f"Couldn't set the engine version.\n\n{e}"
                )
                return

        self.accept()
