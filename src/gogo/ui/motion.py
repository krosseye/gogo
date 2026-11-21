from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from gogo.core.config import config


def system_prefers_reduced_motion() -> bool:
    """True when the OS asks apps to reduce motion (e.g. Windows "Animation effects" off)."""
    app = QGuiApplication.instance()
    if not isinstance(app, QGuiApplication):
        return False
    hints = app.styleHints()
    preference = hints.accessibility().motionPreference()
    return preference == Qt.MotionPreference.ReducedMotion


def reduced_motion() -> bool:
    """True when animations should be skipped."""
    if system_prefers_reduced_motion():
        return True
    return config.has_config() and bool(config["reduced_motion"])
