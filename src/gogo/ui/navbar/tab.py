from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QLayout,
    QVBoxLayout,
    QWidget,
)

from gogo.ui.components.titlebar import TitleBar

from .buttons import create_nav_button


class Tab(QWidget):
    def __init__(
        self,
        title: str,
        icon_normal: QIcon,
        icon_selected: QIcon,
        tab_content: QWidget,
        toolbar_items: list[QLayout | QWidget] | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.title = title
        self.tab_content = tab_content
        self.nav_button = create_nav_button(title, icon_normal, icon_selected)

        self.titlebar = TitleBar(title, children=toolbar_items)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.titlebar)
        layout.addWidget(self.tab_content)
        self.setLayout(layout)
