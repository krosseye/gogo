from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLayout, QWidget


class TitleBar(QFrame):
    """Custom title bar for the application."""

    def __init__(
        self,
        title: str,
        icon: QIcon | None = None,
        children: list[QLayout | QWidget] | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.setObjectName("panel")
        self.setFrameStyle(QFrame.Shadow.Plain)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(52)
        self.setMaximumHeight(52)

        self.title_label = QLabel(f"<h2>{title}</h2>", self)

        icon_pixmap = icon.pixmap(24, 24) if icon else None
        if icon_pixmap:
            self.icon_label = QLabel(self)
            self.icon_label.setPixmap(icon_pixmap)
            self.icon_label.setFixedSize(24, 24)

        self._layout = QHBoxLayout(self)
        if icon_pixmap:
            self._layout.addWidget(self.icon_label)
        self._layout.addWidget(self.title_label)
        self._layout.addStretch(1)

        if children:
            for child in children:
                if isinstance(child, QWidget):
                    self._layout.addWidget(child)
                elif isinstance(child, QLayout):
                    self._layout.addLayout(child)

        self.setLayout(self._layout)
