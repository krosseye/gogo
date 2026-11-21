from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from gogo.core.config import config

_system_style: str | None = None


def apply_appearance() -> None:
    """Apply the theme and font settings to the running app (startup and live changes)."""
    global _system_style
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    if _system_style is None:  # first call: remember what "default" means
        _system_style = app.style().name()
        config.default_font_family = app.font().family()

    font = QFont(config["font_family"])
    font.setPointSize(config["font_size"])
    app.setFont(font)

    theme = config["theme"]
    target = _system_style if theme == "default" else theme
    if app.style().name().lower() != target.lower():
        app.setStyle(target)
