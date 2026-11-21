from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRect
from PySide6.QtGui import QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QStackedWidget, QWidget


class SlidingStackedWidget(QStackedWidget):
    """A QStackedWidget that slides horizontally between pages."""

    def __init__(
        self,
        parent: QWidget | None = None,
        duration_ms: int = 300,
        easing: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
    ) -> None:
        super().__init__(parent)
        self._duration_ms = duration_ms
        self._easing = easing

        self._is_sliding = False
        self._progress = 0.0  # 0.0 to 1.0
        self._animation: QPropertyAnimation | None = None
        self._outgoing = QPixmap()
        self._incoming = QPixmap()
        self._target_index = -1
        self._forward = True

    def _get_progress(self) -> float:
        return self._progress

    def _set_progress(self, value: float) -> None:
        self._progress = value
        self.update()

    progress = Property(float, _get_progress, _set_progress)

    def slide_to_index(self, index: int) -> None:
        current_index = self.currentIndex()
        if self._is_sliding or index == current_index or not 0 <= index < self.count():
            return

        current, target = self.currentWidget(), self.widget(index)
        if current is None or target is None:
            return

        self._forward = index > current_index
        self._target_index = index
        self._outgoing = current.grab()
        target.resize(self.contentsRect().size())
        self._incoming = target.grab()
        current.hide()

        self._is_sliding = True
        self._progress = 0.0
        self._animation = QPropertyAnimation(self, b"progress", self)
        self._animation.setDuration(self._duration_ms)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(self._easing)
        self._animation.finished.connect(self._on_slide_finished)
        self._animation.start()

    def _on_slide_finished(self) -> None:
        self._is_sliding = False
        self.setCurrentIndex(self._target_index)
        if widget := self.currentWidget():
            widget.show()
        self._outgoing = QPixmap()
        self._incoming = QPixmap()
        self._animation = None
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._is_sliding:
            super().paintEvent(event)
            return

        rect = self.contentsRect()
        width = rect.width()
        shift = int(width * self._progress)
        if not self._forward:
            shift = -shift

        painter = QPainter(self)
        painter.setClipRect(rect)
        outgoing = QRect(rect.x() - shift, rect.y(), width, rect.height())
        incoming_x = rect.x() + (width if self._forward else -width) - shift
        incoming = QRect(incoming_x, rect.y(), width, rect.height())
        painter.drawPixmap(outgoing, self._outgoing)
        painter.drawPixmap(incoming, self._incoming)
