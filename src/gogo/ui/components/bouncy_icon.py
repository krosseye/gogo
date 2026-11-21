from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QLabel

from gogo.ui.motion import reduced_motion


class BouncyIcon(QLabel):
    """A clickable icon that bounces, and triggers an easter egg after rapid clicks."""

    easter_egg_triggered = Signal()
    EASTER_EGG_CLICKS = 10

    def __init__(self, icon_path: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pixmap = QPixmap(icon_path).scaledToHeight(
            48, Qt.TransformationMode.SmoothTransformation
        )
        self.setFixedSize(self._pixmap.size())
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._scale = 1.0

        self.click_count = 0
        self.reset_timer = QTimer(self)
        self.reset_timer.setInterval(1000)
        self.reset_timer.timeout.connect(self._reset_clicks)

        self.animation = QPropertyAnimation(self, b"scale")
        self.animation.setEasingCurve(QEasingCurve.Type.OutElastic)

    @Property(float)
    def scale(self):
        return self._scale

    @scale.setter  # type: ignore[no-redef]
    def scale(self, value):
        self._scale = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self._pixmap.width() * self._scale
        h = self._pixmap.height() * self._scale
        x = (self.width() - w) / 2
        y = (self.height() - h) / 2

        painter.drawPixmap(int(x), int(y), int(w), int(h), self._pixmap)

    def _reset_clicks(self) -> None:
        self.click_count = 0
        self.reset_timer.stop()

    def mousePressEvent(self, event) -> None:
        self.click_count += 1
        self.reset_timer.start()

        intensity = min(self.click_count * 0.05, 0.5)

        if not reduced_motion():
            self.animation.stop()
            self.animation.setDuration(500)
            self.animation.setStartValue(self._scale)
            self.animation.setKeyValueAt(0.3, 1.0 + intensity)
            self.animation.setEndValue(1.0)
            self.animation.start()

        if self.click_count >= self.EASTER_EGG_CLICKS:
            self.easter_egg_triggered.emit()
            self._reset_clicks()

        super().mousePressEvent(event)
