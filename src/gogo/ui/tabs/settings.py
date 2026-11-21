import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from kq_icon_engine import IconStyle, KQIcon
from PySide6.QtCore import QProcess, QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gogo.core.config import config
from gogo.core.constants import THEME_OPTIONS
from gogo.ui.appearance import apply_appearance
from gogo.ui.motion import system_prefers_reduced_motion

LIVE_APPEARANCE_KEYS = {"theme", "font_family", "font_size"}
# Read once when the window is built (tab transitions, navbar buttons).
RESTART_REQUIRED_KEYS = {"reduced_motion"}


class BaseSettingField(ABC):
    """One setting: its config key, its input widget and a reset button."""

    def __init__(
        self,
        key: str,
        label: str,
        default: Any,
        tooltip: str | None = None,
        group: str = "General",
    ):
        self.key = key
        self.label = label
        self.default = default
        self.tooltip = tooltip
        self.group = group
        self.widget: Any = None
        self.reset_btn: QPushButton | None = None
        self.locked = False

    @abstractmethod
    def create_widget(self) -> QWidget:
        """Create and return the main widget for this setting."""

    @abstractmethod
    def get_value(self) -> Any:
        """Get the current value from the widget."""

    @abstractmethod
    def set_value(self, value: Any) -> None:
        """Set the widget to the given value."""

    @abstractmethod
    def connect_change_signal(self, callback) -> None:
        """Connect the widget's change signal to a callback."""

    def create_reset_button(self) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(KQIcon("arrow-counter-clockwise", style=IconStyle.BOLD))
        btn.setIconSize(QSize(16, 16))
        btn.setFixedSize(24, 24)
        btn.setToolTip(f"Reset to default {self.label.lower().replace(':', '')} value")
        return btn

    def create_layout(self) -> QHBoxLayout:
        self.widget = self.create_widget()
        self.reset_btn = self.create_reset_button()

        if self.tooltip:
            self.widget.setToolTip(self.tooltip)

        layout = QHBoxLayout()
        layout.addWidget(self.widget)
        layout.addWidget(self.reset_btn)

        return layout

    def reset_to_default(self) -> None:
        self.set_value(self.default)

    def has_changed(self, current_config: dict) -> bool:
        if self.locked:
            return False
        return self.get_value() != current_config.get(self.key)

    def lock(self, value: Any, reason: str) -> None:
        """Show `value`, read-only, without touching the user's saved preference."""
        self.set_value(value)
        self.locked = True
        self.widget.setEnabled(False)
        self.widget.setToolTip(reason)
        if self.reset_btn:
            self.reset_btn.setEnabled(False)


class CheckboxField(BaseSettingField):
    def create_widget(self) -> QCheckBox:
        return QCheckBox()

    def get_value(self) -> bool:
        return self.widget.isChecked()

    def set_value(self, value: bool) -> None:
        self.widget.setChecked(value)

    def connect_change_signal(self, callback) -> None:
        self.widget.stateChanged.connect(callback)


class ComboBoxField(BaseSettingField):
    def __init__(
        self,
        key: str,
        label: str,
        default: Any,
        options: list[str],
        tooltip: str | None = None,
        group: str = "General",
    ):
        super().__init__(key, label, default, tooltip, group)
        self.options = options

    def create_widget(self) -> QComboBox:
        combo = QComboBox()
        combo.addItems(self.options)
        return combo

    def get_value(self) -> str:
        return self.widget.currentText()

    def set_value(self, value: str) -> None:
        self.widget.setCurrentText(value)

    def connect_change_signal(self, callback) -> None:
        self.widget.currentTextChanged.connect(callback)


class FontComboField(BaseSettingField):
    def create_widget(self) -> QFontComboBox:
        combo = QFontComboBox()
        combo.setEditable(False)
        return combo

    def get_value(self) -> str:
        return self.widget.currentFont().family()

    def set_value(self, value: str) -> None:
        self.widget.setCurrentFont(QFont(value))

    def connect_change_signal(self, callback) -> None:
        self.widget.currentFontChanged.connect(callback)


class SpinBoxField(BaseSettingField):
    def __init__(
        self,
        key: str,
        label: str,
        default: int,
        min_val: int = 0,
        max_val: int = 100,
        tooltip: str | None = None,
        group: str = "General",
    ):
        super().__init__(key, label, default, tooltip, group)
        self.min_val = min_val
        self.max_val = max_val

    def create_widget(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(self.min_val, self.max_val)
        return spin

    def get_value(self) -> int:
        return self.widget.value()

    def set_value(self, value: int) -> None:
        self.widget.setValue(value)

    def connect_change_signal(self, callback) -> None:
        self.widget.valueChanged.connect(callback)


class PathField(BaseSettingField):
    """A folder path with a Browse button."""

    def __init__(
        self,
        key: str,
        label: str,
        default: str,
        placeholder: str = "Select a path",
        tooltip: str | None = None,
        group: str = "General",
    ):
        super().__init__(key, label, default, tooltip, group)
        self.placeholder = placeholder
        self.browse_btn: QPushButton | None = None

    def create_widget(self) -> QLineEdit:
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(self.placeholder)
        return line_edit

    def get_value(self) -> str:
        return self.widget.text()

    def set_value(self, value: str) -> None:
        self.widget.setText(value)

    def connect_change_signal(self, callback) -> None:
        self.widget.textChanged.connect(callback)

    def create_layout(self) -> QHBoxLayout:
        self.widget = self.create_widget()
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setIcon(QIcon.fromTheme("folder-open"))
        self.reset_btn = self.create_reset_button()

        if self.tooltip:
            self.widget.setToolTip(self.tooltip)

        layout = QHBoxLayout()
        layout.addWidget(self.widget)
        layout.addWidget(self.browse_btn)
        layout.addWidget(self.reset_btn)

        return layout

    def browse_path(self, parent: QWidget) -> None:
        path = QFileDialog.getExistingDirectory(
            parent, f"Select {self.label.replace(':', '')}"
        )
        if path:
            self.set_value(path)


class SettingsTabContent(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fields = self._define_settings_fields()
        self._setup_ui()
        self._load_config_values()
        self._apply_system_overrides()
        self._connect_signals()

    def _apply_system_overrides(self) -> None:
        """Lock settings that the operating system currently decides."""
        if system_prefers_reduced_motion():
            field = next(f for f in self.fields if f.key == "reduced_motion")
            field.lock(True, "Enforced by your system's accessibility settings")

    def _define_settings_fields(self) -> list[BaseSettingField]:
        """All settings, in display order. Add new settings here."""
        return [
            ComboBoxField(
                key="theme",
                label="Theme:",
                default=config.default_config["theme"],
                options=THEME_OPTIONS,
                tooltip="Select the application theme",
                group="Appearance",
            ),
            FontComboField(
                key="font_family",
                label="Font family:",
                default=config.default_config["font_family"],
                tooltip="Select the application font",
                group="Appearance",
            ),
            SpinBoxField(
                key="font_size",
                label="Font size:",
                default=config.default_config["font_size"],
                min_val=6,
                max_val=72,
                tooltip="Set the application font size",
                group="Appearance",
            ),
            CheckboxField(
                key="reduced_motion",
                label="Reduced motion:",
                default=config.default_config["reduced_motion"],
                tooltip="Reduce animations and transitions",
                group="Appearance",
            ),
            CheckboxField(
                key="minimize_on_project_open",
                label="Minimize on project open:",
                default=config.default_config["minimize_on_project_open"],
                tooltip="Minimize window when opening a project",
                group="Behavior",
            ),
            CheckboxField(
                key="close_on_project_open",
                label="Close on project open:",
                default=config.default_config["close_on_project_open"],
                tooltip="Close window when opening a project",
                group="Behavior",
            ),
            PathField(
                key="default_project_path",
                label="Default project path:",
                default=config.default_config["default_project_path"],
                placeholder="Select a default project path",
                tooltip="Set the default directory for new projects",
                group="Paths",
            ),
        ]

    def _create_settings_card(self, title: str) -> tuple[QFrame, QFormLayout]:
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.StyledPanel)  # type: ignore
        card.setObjectName("panel")

        card_layout = QVBoxLayout(card)

        title_label = QLabel(f"<h3>{title}</h3>")
        card_layout.addWidget(title_label)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.addLayout(form_layout)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        return card, form_layout

    def _create_group_card(self, group_name: str) -> QFrame:
        card, form_layout = self._create_settings_card(group_name)
        for field in (f for f in self.fields if f.group == group_name):
            layout = field.create_layout()
            form_layout.addRow(QLabel(field.label), layout)

        return card

    def _create_settings_panel(self) -> QWidget:
        """A scrollable, centred column with one card per group."""
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setFrameStyle(QFrame.Shape.NoFrame)  # type: ignore
        scroll_area.setWidgetResizable(True)

        scroll_container = QWidget()
        scroll_layout = QVBoxLayout(scroll_container)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        )

        self.settings_content = QWidget()
        self.settings_content.setMaximumWidth(1660)
        settings_layout = QVBoxLayout(self.settings_content)
        settings_layout.setContentsMargins(0, 0, 0, 0)

        for group in dict.fromkeys(f.group for f in self.fields):
            settings_layout.addWidget(self._create_group_card(group))

        settings_layout.addStretch(1)

        scroll_layout.addWidget(self.settings_content)
        scroll_area.setWidget(scroll_container)
        wrapper_layout.addWidget(scroll_area)

        return wrapper

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.apply_button = QPushButton("Apply")
        self.apply_button.setFixedHeight(32)
        self.apply_button.setIcon(QIcon.fromTheme("document-save"))
        self.apply_button.setEnabled(False)

        main_layout.addWidget(self._create_settings_panel())

    def _connect_signals(self):
        for field in self.fields:
            field.connect_change_signal(self._update_apply_button_state)
            field.reset_btn.clicked.connect(
                lambda checked=False, f=field: f.reset_to_default()
            )

            if isinstance(field, PathField):
                field.browse_btn.clicked.connect(
                    lambda checked=False, f=field: f.browse_path(self)
                )

        self.apply_button.clicked.connect(self._apply_changes)

    def _load_config_values(self):
        for field in self.fields:
            if not field.locked:
                field.set_value(config.get(field.key))
        self._update_apply_button_state()

    def _update_apply_button_state(self):
        current = config.copy()
        has_changes = any(field.has_changed(current) for field in self.fields)
        self.apply_button.setEnabled(has_changes)

    def _apply_changes(self):
        """Validate, save, and apply what can be applied live."""
        for field in self.fields:
            if isinstance(field, PathField):
                new_path = field.get_value()
                if new_path and not Path(new_path).is_dir():
                    QMessageBox.warning(
                        self,
                        "Invalid Path",
                        f"The selected path is not a valid directory:\n{new_path}",
                        QMessageBox.StandardButton.Ok,
                    )
                    return

        current = config.copy()
        changed = {f.key for f in self.fields if f.has_changed(current)}
        for field in self.fields:
            if not field.locked:
                config[field.key] = field.get_value()

        config.save()
        self._update_apply_button_state()
        if changed & LIVE_APPEARANCE_KEYS:
            apply_appearance()
        if changed & RESTART_REQUIRED_KEYS:
            self._offer_restart()

    @staticmethod
    def restart_app():
        QApplication.processEvents()
        QProcess.startDetached(*SettingsTabContent.restart_command())
        QApplication.quit()

    @staticmethod
    def restart_command() -> tuple[str, list[str]]:
        """Program and arguments that relaunch the GUI.

        No extra arguments may reach main(), or it starts in CLI mode. In a frozen
        build sys.argv[0] is the executable itself, so passing sys.argv would do that.
        """
        if getattr(sys, "frozen", False):
            return sys.executable, []
        return sys.executable, ["-c", "from gogo.main import main; main()"]

    def _offer_restart(self):
        """Offer a restart for settings that only take effect at startup."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("Configuration has been updated")
        msg.setInformativeText(
            "Restart GoGo for the reduced motion setting to take effect."
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.button(QMessageBox.StandardButton.Yes).setText("Restart Now")
        msg.button(QMessageBox.StandardButton.No).setText("Later")

        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.restart_app()
