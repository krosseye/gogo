from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import QLabel, QSizePolicy


class ElidedLabel(QLabel):
    """A dimmed single-line label for paths: shrinks to fit by eliding the middle,
    with the full text in its tooltip."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:
        super().setText(text)
        self.setToolTip(text)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        text = self.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideMiddle, self.contentsRect().width()
        )
        painter.drawText(
            self.contentsRect(),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )
