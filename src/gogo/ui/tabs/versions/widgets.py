import os
from pathlib import Path

from godotkit.engine import GodotVersion
from kq_icon_engine import IconStyle, KQIcon
from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QBoxLayout,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from gogo.core import engines
from gogo.ui.components.worker import Worker
from gogo.ui.dialogs.install_engine import install_events

from .controller import GodotReleasesController
from .release_list_item import ReleaseListItem


class InstalledVersionsList(QListWidget):
    """Installed engines, with the default one first."""

    def populate(self):
        self.clear()
        default_engine_path = engines.get_default()

        try:
            versions_dict = engines.list_installed()
            if not versions_dict:
                return

            if not default_engine_path and len(versions_dict) == 1:
                only_path = next(iter(versions_dict.values()))
                engines.set_default(only_path)
                return self.populate()

            default_item = None

            for version_name, version_path in versions_dict.items():
                size = self._calculate_dir_size(Path(version_path))
                is_default = bool(default_engine_path) and (
                    Path(default_engine_path).resolve() == Path(version_path).resolve()
                )

                item_widget = ReleaseListItem(
                    GodotVersion.parse(version_name),
                    str(version_path),
                    size,
                    self.populate,
                )
                item = QListWidgetItem()
                item.setSizeHint(item_widget.sizeHint())

                if is_default:
                    default_item = (item, item_widget)
                else:
                    self.addItem(item)
                    self.setItemWidget(item, item_widget)

            if default_item:
                item, widget = default_item
                self.insertItem(0, item)
                self.setItemWidget(item, widget)

        except Exception as e:
            QMessageBox.warning(
                self, "Load Failed", f"Couldn't load installed versions.\n\n{e}"
            )

    @staticmethod
    def _calculate_dir_size(path: Path) -> int:
        total = 0
        for root, _, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                if os.path.isfile(fp):
                    total += os.path.getsize(fp)
        return total


class OnlineReleasesList(QListWidget):
    """Downloadable releases; `on_change` refreshes the installed list."""

    def __init__(self, user_platform: str, on_change, parent=None):
        super().__init__(parent)
        self.user_platform = user_platform
        self.on_change = on_change
        self.releases: list[dict] = []

    def populate(self):
        self.clear()

        for release in self.releases:
            download = release["download_links"].get(self.user_platform, {})
            url = download.get("url", "N/A")
            size = download.get("size", 0)

            item_widget = ReleaseListItem(
                GodotVersion.from_url(url),
                url,
                size,
                self.on_change,
                release.get("published_at"),
            )
            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())

            self.addItem(item)
            self.setItemWidget(item, item_widget)


class VersionsTabContent(QWidget):
    BREAKPOINT = 1100

    def __init__(self, parent=None):
        super().__init__(parent)

        self.ctrl = GodotReleasesController()
        self._fetch_worker: Worker | None = None

        self.sort_by_options = QComboBox()
        self.sort_by_options.addItems(["Date", "Version"])
        self.sort_by_options.setCurrentText(self.ctrl.DEFAULT_SORT_BY)

        self.variant_options = QComboBox()
        self.variant_options.addItems(["Standard", ".NET/Mono"])
        self.variant_options.setCurrentText(self.ctrl.DEFAULT_VARIANT)

        self.channel_options = QComboBox()
        self.channel_options.addItems(["Stable", "All"])
        self.channel_options.setCurrentText(self.ctrl.DEFAULT_CHANNEL)

        self.release_limit = QSpinBox()
        self.release_limit.setRange(1, 100)
        self.release_limit.setValue(self.ctrl.DEFAULT_LIMIT)

        self.fetch_button = QPushButton()
        self.fetch_button.setIcon(KQIcon("arrows-clockwise", style=IconStyle.REGULAR))
        self.fetch_button.setIconSize(QSize(24, 24))
        self.fetch_button.setFixedSize(QSize(32, 32))
        self.fetch_button.clicked.connect(self.populate_lists)

        self.installed_list_widget = InstalledVersionsList()
        self.online_list_widget = OnlineReleasesList(
            self.ctrl.user_platform, self.installed_list_widget.populate
        )
        install_events.changed.connect(self._on_installs_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.online_label = QLabel("<h3>Available Online</h3>")
        self.installed_label = QLabel("<h3>Installed Locally</h3>")

        self.lists_container = QWidget()
        self.lists_layout = QBoxLayout(QBoxLayout.TopToBottom, self.lists_container)
        self.lists_layout.setContentsMargins(0, 0, 0, 0)
        self.lists_layout.setSpacing(10)

        online_section = QWidget()
        ol = QVBoxLayout(online_section)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.addWidget(self.online_label)
        ol.addWidget(self.online_list_widget)

        installed_section = QWidget()
        il = QVBoxLayout(installed_section)
        il.setContentsMargins(0, 0, 0, 0)
        il.addWidget(self.installed_label)
        il.addWidget(self.installed_list_widget)

        self.lists_layout.addWidget(online_section, 1)
        self.lists_layout.addWidget(installed_section, 1)

        layout.addWidget(self.lists_container)

        self._load_cached_data()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() >= self.BREAKPOINT:
            self.lists_layout.setDirection(QBoxLayout.LeftToRight)
        else:
            self.lists_layout.setDirection(QBoxLayout.TopToBottom)

    def create_tools(self):
        """Titlebar widgets: the filters menu and the refresh button."""
        self.filters_button = QPushButton("Filters  ")
        self.filters_button.setIcon(KQIcon("funnel", style=IconStyle.REGULAR))
        self.filters_button.setFixedHeight(32)

        self.options_menu = QMenu()
        menu_layout = QFormLayout()

        def add_row(label, widget):
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(QLabel(label))
            h.addWidget(widget)
            menu_layout.addRow(container)

        add_row("Channel:", self.channel_options)
        add_row("Variant:", self.variant_options)
        add_row("Sort by:", self.sort_by_options)
        add_row("Limit:", self.release_limit)

        container = QWidget()
        container.setLayout(menu_layout)

        action = QWidgetAction(self.options_menu)
        action.setDefaultWidget(container)
        self.options_menu.addAction(action)

        self.filters_button.setMenu(self.options_menu)
        return [self.filters_button, self.fetch_button]

    def _load_cached_data(self):
        """Show cached releases if fresh enough; otherwise fetch."""
        cache = self.ctrl.load_cache()
        if not cache:
            self.populate_lists()
            return

        settings = cache.get("settings", {})
        self.sort_by_options.setCurrentText(
            settings.get("sort_by", self.ctrl.DEFAULT_SORT_BY)
        )
        self.variant_options.setCurrentText(
            settings.get("variant", self.ctrl.DEFAULT_VARIANT)
        )
        self.channel_options.setCurrentText(
            settings.get("channel", self.ctrl.DEFAULT_CHANNEL)
        )
        self.release_limit.setValue(settings.get("limit", self.ctrl.DEFAULT_LIMIT))

        timestamp = cache.get("timestamp")
        self.ctrl.last_updated_string = timestamp

        friendly = self.ctrl.friendly_timestamp(timestamp)
        if friendly:
            self.online_label.setToolTip(f"Last updated: {friendly}")

        channel = self.channel_options.currentText()
        if timestamp and self.ctrl.is_cache_fresh(timestamp, channel):
            self.online_list_widget.releases = cache.get("data", [])
            self.installed_list_widget.populate()
            self.online_list_widget.populate()
            return

        self.populate_lists()

    def _on_installs_changed(self) -> None:
        self.installed_list_widget.populate()
        self.online_list_widget.populate()

    def populate_lists(self):
        if self._fetch_worker and self._fetch_worker.isRunning():
            return
        settings = {
            "sort_by": self.sort_by_options.currentText(),
            "variant": self.variant_options.currentText(),
            "channel": self.channel_options.currentText(),
            "limit": self.release_limit.value(),
        }
        self._fetch_worker = Worker(
            lambda _w: self.ctrl.fetch_releases(**settings), self
        )
        self._fetch_worker.succeeded.connect(
            lambda data: self._on_releases_fetched(settings, data)
        )
        self._fetch_worker.failed.connect(
            lambda err: QMessageBox.warning(
                self, "Refresh Failed", f"Couldn't fetch releases.\n\n{err}"
            )
        )
        self._fetch_worker.finished.connect(lambda: self._set_fetching(False))
        self._set_fetching(True)
        self._fetch_worker.start()

    def _set_fetching(self, fetching: bool) -> None:
        self.fetch_button.setEnabled(not fetching)
        self.fetch_button.setToolTip(
            "Fetching releases..." if fetching else "Refresh releases"
        )
        self.online_label.setText(
            "<h3>Available Online (updating...)</h3>"
            if fetching
            else "<h3>Available Online</h3>"
        )

    def _on_releases_fetched(self, settings: dict, release_data: list) -> None:
        self.ctrl.save_cache(settings, release_data)

        friendly = self.ctrl.friendly_timestamp(self.ctrl.last_updated_string)
        if friendly:
            self.online_label.setToolTip(f"Last updated: {friendly}")

        self.online_list_widget.releases = release_data
        self.installed_list_widget.populate()
        self.online_list_widget.populate()
