from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import QIcon, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QPushButton,
    QStyle,
    QStyleOptionButton,
)

from gogo.ui.motion import reduced_motion


def create_nav_button(text: str, icon_normal: QIcon, icon_selected: QIcon):
    if reduced_motion():
        return BasicNavButton(text, icon_normal, icon_selected)
    return AnimatedNavButton(text, icon_normal, icon_selected)


class BaseNavButton(QPushButton):
    ICON_SIZE = QSize(24, 24)
    BUTTON_SIZE = QSize(45, 45)

    def __init__(
        self,
        text: str,
        icon_normal: str | QIcon,
        icon_selected: str | QIcon,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.tab_name = text
        self.icon_normal = QIcon(icon_normal)
        self.icon_selected = QIcon(icon_selected)

        self.setIconSize(self.ICON_SIZE)
        self.setFixedSize(self.BUTTON_SIZE)
        self.setCheckable(True)
        self.setChecked(False)
        self.setToolTip(f"{text} Tab")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_styling()

    def _apply_styling(self):
        palette = QApplication.palette()
        accent = palette.color(palette.ColorRole.Highlight).name()
        selected = palette.color(palette.ColorRole.Highlight).darker(125).name()

        text = palette.color(palette.ColorRole.WindowText).name()
        hover = palette.button().color().lighter().name()

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 5px;
                color: {text};
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:checked {{
                background-color: {accent};
                font-weight: bold;
            }}
            QPushButton:pressed {{
                background-color: {selected};
            }}
        """)

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ApplicationPaletteChange:
            self._apply_styling()
        return super().event(event)

    def set_selected(self, selected: bool):
        self.setChecked(selected)
        self.update()


class AnimatedNavButton(BaseNavButton):
    def __init__(
        self,
        text: str,
        icon_normal: str | QIcon,
        icon_selected: str | QIcon,
        *args,
        **kwargs,
    ):
        super().__init__(text, icon_normal, icon_selected, *args, **kwargs)
        self._icon_scale = 1.0
        self._anim = QPropertyAnimation(self, b"icon_scale", self)

    @Property(float)
    def icon_scale(self):
        return self._icon_scale

    @icon_scale.setter  # type: ignore[no-redef]
    def icon_scale(self, value):
        self._icon_scale = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        opt.icon = QIcon()
        self.style().drawControl(
            QStyle.ControlElement.CE_PushButton, opt, painter, self
        )

        current_icon = self.icon_selected if self.isChecked() else self.icon_normal
        pixmap = current_icon.pixmap(self.ICON_SIZE)

        sw = self.ICON_SIZE.width() * self._icon_scale
        sh = self.ICON_SIZE.height() * self._icon_scale
        target = QRectF((self.width() - sw) / 2, (self.height() - sh) / 2, sw, sh)
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))

    def mousePressEvent(self, event):
        self._animate_icon(0.9, duration=100, curve=QEasingCurve.Type.OutQuad)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        target = 1.2 if self.underMouse() else 1.0
        self._animate_icon(target)
        super().mouseReleaseEvent(event)

    def _animate_icon(self, end_value, duration=200, curve=QEasingCurve.Type.OutQuad):
        self._anim.stop()
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(curve)
        self._anim.setStartValue(self._icon_scale)
        self._anim.setEndValue(end_value)
        self._anim.start()


class BasicNavButton(BaseNavButton):
    def __init__(
        self,
        text: str,
        icon_normal: str | QIcon,
        icon_selected: str | QIcon,
        *args,
        **kwargs,
    ):
        super().__init__(text, icon_normal, icon_selected, *args, **kwargs)
        self.setIcon(self.icon_normal)

    def set_selected(self, selected: bool):
        super().set_selected(selected)
        self.setIcon(self.icon_selected if selected else self.icon_normal)
