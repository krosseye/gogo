from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

LAUNCH_TIMEOUT_MS = 10_000


def busy_until_app_inactive(timeout_ms: int = LAUNCH_TIMEOUT_MS) -> None:
    """Show a busy cursor until another window takes focus (e.g. the launched
    editor) or the timeout passes, so a slow-starting launch doesn't look ignored."""
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
    restored = False

    def restore() -> None:
        nonlocal restored
        if restored:
            return
        restored = True
        app.applicationStateChanged.disconnect(on_state)
        QApplication.restoreOverrideCursor()

    def on_state(state: Qt.ApplicationState) -> None:
        if state != Qt.ApplicationState.ApplicationActive:
            restore()

    app.applicationStateChanged.connect(on_state)
    QTimer.singleShot(timeout_ms, restore)
