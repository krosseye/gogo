from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy


class EmblemWidget(QFrame):
    """A small rounded badge with an icon and bold text."""

    def __init__(self, text: str, pixmap: QPixmap, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(18, 18)

        self.label = QLabel()
        font = self.label.font()
        font.setBold(True)
        self.label.setFont(font)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.label)

        self.setStyleSheet("""
            EmblemWidget {
                background-color: rgba(128, 128, 128, 0.15);
                border-radius: 14px;
                border: 1px solid rgba(128, 128, 128, 0.5);
            }
            EmblemWidget QLabel {
                background-color: transparent;
                border: none;
            }
        """)

        self.set_content(text, pixmap)

    def set_content(self, text: str, pixmap: QPixmap) -> None:
        self.icon_label.setPixmap(pixmap)
        self.label.setText(text)
