from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)


class SearchBarWidget(QFrame):
    """A search field with an icon and a clear button."""

    search_text_changed = Signal(str)
    return_key_pressed = Signal(str)
    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 5, 0)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("panel")

        search_icon = QIcon.fromTheme("edit-find")
        icon_label = QLabel(self)
        icon_label.setPixmap(search_icon.pixmap(16, 16))
        icon_label.setFixedSize(16, 16)

        self.search_bar = QLineEdit(self)
        self.search_bar.setStyleSheet(
            "QLineEdit{background-color: transparent; border: none;}"
        )
        self.search_bar.setPlaceholderText("Search by project name...")
        self.search_bar.setFixedHeight(32)

        self.clear_button = QPushButton(self, icon=QIcon.fromTheme("window-close"))
        self.clear_button.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                font-size: 14px;
            }
        """)
        self.clear_button.setIconSize(QSize(8, 8))
        self.clear_button.setFixedSize(24, 24)
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.clear_button.hide()

        self.search_bar.textChanged.connect(self._on_text_changed)
        self.search_bar.returnPressed.connect(self._on_return_pressed)
        self.clear_button.clicked.connect(self.clear)

        layout.addWidget(icon_label)
        layout.addWidget(self.search_bar)
        layout.addWidget(self.clear_button)

        self.setLayout(layout)

    def text(self) -> str:
        return self.search_bar.text()

    def clear(self) -> None:
        self.search_bar.clear()
        self.search_bar.setFocus()
        self.cleared.emit()

    def _on_text_changed(self, text: str) -> None:
        self.search_text_changed.emit(text)
        self.clear_button.setVisible(bool(text))

    def _on_return_pressed(self) -> None:
        self.return_key_pressed.emit(self.search_bar.text().strip())
