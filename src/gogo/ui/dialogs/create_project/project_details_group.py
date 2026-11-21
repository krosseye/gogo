import re
import unicodedata

from kq_icon_engine import IconStyle, KQIcon
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
)

from gogo.core import projects
from gogo.core.name_gen import generate_name
from gogo.ui.graphics.icon_generator import IconGenerator


def sanitize_project_name(name: str) -> str:
    """A filesystem-safe folder name, e.g. 'Copper Lantern!' -> 'copper_lantern'."""
    name = unicodedata.normalize("NFKD", name)
    name = "".join([c for c in name if not unicodedata.combining(c)])

    name = re.sub(r"[^\w\s-]", " ", name)

    name = name.lower().strip()
    name = re.sub(r"[_\s-]+", "_", name)

    return name.strip("_")


class ProjectDetailsGroup(QGroupBox):
    """Widget for entering project details (name, description, icon)."""

    details_changed = Signal()

    def __init__(self, parent=None):
        super().__init__("Project Details", parent)

        self._setup_ui()
        self._generate_random_name()

    def _setup_ui(self) -> None:
        form_layout = QFormLayout(self)
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Project name")
        self._name_edit.textChanged.connect(self._on_name_changed)

        generate_btn = QPushButton()
        generate_btn.setIcon(KQIcon("dice-five", style=IconStyle.BOLD))
        generate_btn.setToolTip("Generate a random project name")
        generate_btn.setIconSize(QSize(16, 16))
        generate_btn.setFixedSize(24, 24)
        generate_btn.clicked.connect(self._generate_random_name)

        name_layout = QHBoxLayout()
        name_layout.addWidget(self._name_edit)
        name_layout.addWidget(generate_btn)

        self._folder_preview_label = QLabel()
        self._folder_preview_label.setStyleSheet("color: gray; font-family: monospace;")

        self._description_edit = QPlainTextEdit()
        self._description_edit.setPlaceholderText("A short description of the project")
        self._description_edit.setFixedHeight(80)

        form_layout.addRow("<b>Name:</b>", name_layout)
        form_layout.addRow("<b>Preview:</b>", self._folder_preview_label)
        form_layout.addRow("<b>Description:</b>", self._description_edit)

        self._icon_preview = QLabel()
        self._icon_preview.setFixedSize(96, 96)
        self._icon_preview.setStyleSheet(
            """
            border: 1px solid #ccc;
            border-radius: 8px;
            background-color: palette(base);
            """
        )
        self._icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _generate_random_name(self) -> None:
        taken = [e.path.name for e in projects.load()]
        self._name_edit.setText(generate_name(taken))

    def _on_name_changed(self, text: str) -> None:
        sanitized = sanitize_project_name(text)
        self._folder_preview_label.setText(sanitized)
        if sanitized:
            self._icon_preview.setPixmap(IconGenerator.get_project_icon(sanitized))

        self.details_changed.emit()

    def get_name(self) -> str:
        return self._name_edit.text().strip()

    def get_sanitized_name(self) -> str:
        return sanitize_project_name(self.get_name())

    def get_description(self) -> str:
        return self._description_edit.toPlainText().strip()

    def get_icon_pixmap(self):
        return self._icon_preview.pixmap()

    def get_icon_widget(self) -> QLabel:
        return self._icon_preview

    def set_name_focus(self):
        self._name_edit.setFocus()
