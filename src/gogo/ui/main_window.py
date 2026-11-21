from kq_icon_engine import IconStyle, KQIcon
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from gogo.core.constants import APP_TITLE
from gogo.ui.components.sliding_stacked_widget import SlidingStackedWidget
from gogo.ui.motion import reduced_motion
from gogo.ui.navbar import Tab, TabbedNavbar
from gogo.ui.tabs.blog import BlogTabContent
from gogo.ui.tabs.console import ConsoleTabContent
from gogo.ui.tabs.projects import ProjectsTabContent
from gogo.ui.tabs.settings import SettingsTabContent
from gogo.ui.tabs.versions import VersionsTabContent


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.navbar = TabbedNavbar(self)
        self.navbar.tab_changed.connect(self._update_window_title)

        if reduced_motion():
            self.stacked_widget = QStackedWidget()
            self.navbar.tab_changed.connect(self.stacked_widget.setCurrentIndex)
        else:
            self.stacked_widget = SlidingStackedWidget()
            self.navbar.tab_changed.connect(self.stacked_widget.slide_to_index)

        self.stacked_widget.setContentsMargins(12, 12, 12, 12)

        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.stacked_widget, 1)
        main_layout.addWidget(self.navbar, 0)
        self.setCentralWidget(central_widget)

        self._setup_tabs()
        self._setup_shortcuts()

    def _setup_tabs(self) -> None:
        projects_tab_content = ProjectsTabContent(self)
        self.navbar.add_tab(
            Tab(
                "Projects",
                KQIcon("folders", style=IconStyle.REGULAR),
                KQIcon("folders", style=IconStyle.FILL),
                projects_tab_content,
                projects_tab_content.create_tools(),
            )
        )

        versions_tab_content = VersionsTabContent(self)
        self.navbar.add_tab(
            Tab(
                "Versions",
                KQIcon("package", style=IconStyle.REGULAR),
                KQIcon("package", style=IconStyle.FILL),
                versions_tab_content,
                versions_tab_content.create_tools(),
            )
        )

        self.navbar.add_tab(
            Tab(
                "Blog",
                KQIcon("newspaper", style=IconStyle.REGULAR),
                KQIcon("newspaper", style=IconStyle.FILL),
                BlogTabContent(self),
            )
        )

        self.navbar.add_spacer()

        console_tab_content = ConsoleTabContent(self)
        self.navbar.add_tab(
            Tab(
                "Console",
                KQIcon("terminal-window", style=IconStyle.REGULAR),
                KQIcon("terminal-window", style=IconStyle.FILL),
                console_tab_content,
                console_tab_content.create_tools(),
            )
        )

        settings_tab_content = SettingsTabContent(self)
        self.navbar.add_tab(
            Tab(
                "Settings",
                KQIcon("gear", style=IconStyle.REGULAR),
                KQIcon("gear", style=IconStyle.FILL),
                settings_tab_content,
                [settings_tab_content.apply_button],
            )
        )

        for tab in self.navbar.tabs:
            self.stacked_widget.addWidget(tab)

        self.navbar.set_initial_tab(0)
        self.stacked_widget.setCurrentIndex(0)
        self._update_window_title(0)

    def _setup_shortcuts(self) -> None:
        """Ctrl+1..9 switch tabs."""
        for i in range(min(len(self.navbar.tabs), 9)):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self)
            shortcut.activated.connect(lambda index=i: self.navbar.select_tab(index))

    def _update_window_title(self, index: int) -> None:
        tab = self.navbar.get_tab(index)
        if tab:
            self.setWindowTitle(f"{tab.title} - {APP_TITLE}")
