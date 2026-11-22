from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal


class Worker(QThread):
    """Runs `fn` off the UI thread and reports the result through signals.

    `fn` receives the worker itself, so it can emit `progress` or check
    `cancelled`. Signals are delivered on the UI thread.
    """

    progress = Signal(str, int, int)  # phase, done, total (0 if unknown)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[["Worker"], Any], parent: QObject) -> None:
        super().__init__(parent)
        self._fn = fn
        self.cancelled = False

    def run(self) -> None:
        try:
            result = self._fn(self)
        except Exception as e:
            self.failed.emit(str(e) or type(e).__name__)
        else:
            self.succeeded.emit(result)
