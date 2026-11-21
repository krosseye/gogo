from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel

from gogo.ui.motion import reduced_motion


class SlidingLabel(QLabel):
    """A single-line label that scrolls (marquee-style) when its text is too wide.

    Scrolling pauses while hovered. With reduced motion, the text is elided instead.
    """

    GAP = 20
    SPEED = 20

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._offset = 0
        self._max_width = 200
        self._animation: QPropertyAnimation | None = None
        self._text_width = 0
        self._italic = True
        self._is_hovered = False
        self.setMouseTracking(True)
        self.setFixedWidth(self._max_width)

    def set_max_width(self, width: float) -> None:
        self._max_width = int(width)
        self.setFixedWidth(self._max_width)
        self._start_animation()

    def set_italic(self, italic: bool) -> None:
        self._italic = italic
        self.update()

    def setText(self, text: str) -> None:
        super().setText(text)
        self._text_width = self.fontMetrics().boundingRect(self.text()).width()
        self._start_animation()

    def enterEvent(self, event):
        self._is_hovered = True

        def pause_if_running():
            if (
                self._is_hovered
                and self._animation
                and self._animation.state() == QPropertyAnimation.State.Running
            ):
                self._animation.pause()

        QTimer.singleShot(500, pause_if_running)

    def leaveEvent(self, event):
        self._is_hovered = False
        if (
            self._animation
            and self._animation.state() == QPropertyAnimation.State.Paused
        ):
            self._animation.resume()
        super().leaveEvent(event)

    def _start_animation(self) -> None:
        if self._animation:
            self._animation.stop()

        if reduced_motion():
            self.update()
            return

        self._text_width = self.fontMetrics().boundingRect(self.text()).width()
        if self._text_width <= self._max_width:
            self._offset = 0
            self.update()
            return

        self._animation = QPropertyAnimation(self, b"offset")
        self._animation.setStartValue(0)
        self._animation.setEndValue(self._text_width + self.GAP)
        self._animation.setDuration(int(self._text_width / self.SPEED * 1000))
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._animation.finished.connect(self._restart_animation)
        self._animation.start()

    def _restart_animation(self) -> None:
        self._offset = 0
        QTimer.singleShot(50, self._start_animation)

    def paintEvent(self, event):
        painter = QPainter(self)
        font = self.font()
        font.setItalic(self._italic)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        y = (self.height() + metrics.ascent() - metrics.descent()) // 2

        if reduced_motion():
            elided = metrics.elidedText(
                self.text(), Qt.TextElideMode.ElideRight, self.width()
            )
            painter.drawText(0, y, elided)
            return

        text_width = self._text_width
        if text_width <= self.width():
            painter.drawText(0, y, self.text())
            return

        painter.drawText(-self._offset, y, self.text())
        if self._offset > 0:
            painter.drawText(-self._offset + text_width + self.GAP, y, self.text())
        if self._offset > text_width + self.GAP:
            painter.drawText(
                -self._offset + 2 * (text_width + self.GAP), y, self.text()
            )

    def _get_offset(self) -> int:
        return self._offset

    def _set_offset(self, offset: int) -> None:
        span = self._text_width + self.GAP
        self._offset = offset % span if self._text_width > 0 else 0
        self.update()

    offset = Property(int, _get_offset, _set_offset)
