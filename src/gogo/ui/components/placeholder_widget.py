from kq_icon_engine import KQCustomIcon
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
)

from gogo.core.constants import GODOT_ICON_PATH


class PlaceholderWidget(QFrame):
    def __init__(
        self,
        parent=None,
        title: str = "Hello, World!",
        hint: str | None = None,
        icon: QPixmap | None = None,
    ):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setSpacing(12)

        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setObjectName("panel")
        self.setLayout(layout)

        self.title_label = QLabel(
            f"<h2>{title}</h2>",
            parent=self,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        self.graphic_label = QLabel(parent=self, alignment=Qt.AlignmentFlag.AlignCenter)
        if icon:
            self.graphic_label.setPixmap(icon)
        else:
            self.graphic_label.setPixmap(KQCustomIcon(GODOT_ICON_PATH).pixmap(128))

        self.hint_label = QLabel(
            f"<em>{hint or ''}</em>",
            parent=self,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        layout.addStretch()
        layout.addWidget(self.title_label)
        layout.addWidget(self.graphic_label)
        layout.addWidget(self.hint_label)
        layout.addStretch()

    @property
    def title(self) -> str:
        return self.title_label.text()

    @title.setter
    def title(self, value: str):
        self.title_label.setText(f"<h2>{value}</h2>")

    @property
    def hint(self) -> str:
        return self.hint_label.text()

    @hint.setter
    def hint(self, value: str | None):
        self.hint_label.setText(f"<em>{value or ''}</em>")

    @property
    def icon(self) -> QPixmap | None:
        return self.graphic_label.pixmap()

    @icon.setter
    def icon(self, value: QPixmap):
        self.graphic_label.setPixmap(value)
