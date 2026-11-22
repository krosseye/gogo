from typing import NamedTuple

from godotkit.engine import GodotVersion
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gogo.core import engines
from gogo.ui.graphics.icon_generator import IconGenerator


class VersionEntry(NamedTuple):
    """Container for version data to ensure type safety during sorting."""

    name: str
    obj: GodotVersion
    is_default: bool


class VersionSelector(QComboBox):
    """A QComboBox specialized for selecting an installed Godot version."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._populate_versions()

    def _populate_versions(self) -> None:
        self.clear()

        default_godot_path = engines.get_default()
        versions = engines.list_installed()

        if not versions:
            self.addItem("No Godot versions found")
            self.setEnabled(False)
            return

        items = [
            VersionEntry(name, GodotVersion.parse(name), path == default_godot_path)
            for name, path in versions.items()
        ]
        items.sort(key=lambda x: not x.is_default)  # list_installed is newest first

        for item in items:
            display_name = item.obj.display_name
            if item.is_default:
                display_name += " [Default]"
            icon = IconGenerator.get_version_pin(item.name, 16)
            self.addItem(icon, display_name, userData=item.name)

    def get_selected_version(self) -> str | None:
        return self.currentData()

    def set_selected_version(self, version: GodotVersion | None) -> None:
        index = self.findData(str(version))
        if index != -1:
            self.setCurrentIndex(index)


def choose_engine_version(
    parent: QWidget,
    title: str,
    text: str,
    preselect: GodotVersion | None = None,
) -> str | None:
    """Ask the user to pick an installed version; returns its name, or None if cancelled.

    `preselect` is chosen initially when it is installed; otherwise the default engine is.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    selector = VersionSelector(dialog)
    if preselect:
        selector.set_selected_version(preselect)
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(selector.isEnabled())

    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(text))
    layout.addWidget(selector)
    layout.addWidget(buttons)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return selector.get_selected_version()
