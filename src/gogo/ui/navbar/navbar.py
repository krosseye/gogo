from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QHBoxLayout

from gogo.core.constants import APP_ICON_PATH
from gogo.ui.components.bouncy_icon import BouncyIcon
from gogo.ui.dialogs.about import AboutDialog

from .tab import Tab


class TabbedNavbar(QFrame):
    """A horizontal tabbed navigation bar, docked at the bottom of the window."""

    tab_changed = Signal(int)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setObjectName("navbar_container")
        self._update_stylesheet()

        self.tabs: list[Tab] = []

        grid = QGridLayout(self)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 1)
        left, centre, self._right = QHBoxLayout(), QHBoxLayout(), QHBoxLayout()
        for column, row in enumerate((left, centre, self._right)):
            row.setSpacing(5)
            grid.addLayout(row, 0, column)
        self._tab_row = centre

        self.icon_label = BouncyIcon(APP_ICON_PATH)
        self.icon_label.easter_egg_triggered.connect(lambda: AboutDialog(self).exec())
        left.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        left.addStretch()
        self._right.addStretch()

    def add_tab(self, tab: Tab) -> None:
        index = len(self.tabs)
        tab.nav_button.clicked.connect(lambda: self.select_tab(index))
        self.tabs.append(tab)
        self._tab_row.addWidget(tab.nav_button)

    def add_spacer(self) -> None:
        """Tabs added after this sit at the far end of the navbar."""
        self._tab_row = self._right

    def select_tab(self, index: int) -> None:
        """Select the tab at `index` and emit `tab_changed`."""
        if not 0 <= index < len(self.tabs):
            return
        for i, tab in enumerate(self.tabs):
            tab.nav_button.set_selected(i == index)
        self.tab_changed.emit(index)

    def set_initial_tab(self, index: int = 0) -> None:
        """Mark a tab as selected without emitting `tab_changed`."""
        if 0 <= index < len(self.tabs):
            self.tabs[index].nav_button.set_selected(True)

    def get_tab(self, index: int) -> Tab | None:
        return self.tabs[index] if 0 <= index < len(self.tabs) else None

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ApplicationPaletteChange:
            self._update_stylesheet()
        return super().event(event)

    def _update_stylesheet(self) -> None:
        palette = QApplication.palette()
        is_dark_text = palette.color(palette.ColorRole.WindowText).lightness() < 128

        bg = "palette(midlight)" if is_dark_text else "palette(mid)"
        border = "palette(mid)" if is_dark_text else "palette(midlight)"

        self.setStyleSheet(f"""
        QFrame#navbar_container {{
            background-color: {bg};
            border-top: 1px solid {border};
        }}
        """)
