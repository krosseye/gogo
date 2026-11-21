import hashlib
import logging

from kq_icon_engine import FillMode, KQCustomIcon
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPixmap

from gogo.core.constants import GODOT_ICON_PATH
from gogo.ui.graphics.string_to_qcolor import string_to_qcolor

logger = logging.getLogger(__name__)


class _ProjectIconGenerator:
    """Deterministic identicon generator using a symmetric grid."""

    def __init__(
        self, grid_size: int = 5, image_size: int = 128, border_radius: int = 0
    ):
        self.grid_size = grid_size
        self.image_size = image_size
        self.cell_size = image_size // grid_size
        self.border_radius = border_radius

    @staticmethod
    def digest_to_qcolor(digest: bytes) -> QColor:
        """A vivid colour derived from the first bytes of a hash digest."""
        hue = int(digest[0] / 255 * 359)
        saturation = 140 + int(digest[1] / 255 * 70)
        value = 165 + int(digest[2] / 255 * 70)

        return QColor.fromHsv(hue, saturation, value)

    def generate(self, seed: str) -> QImage:
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        foreground = self.digest_to_qcolor(digest)
        background = QColor.fromHsv(
            foreground.hue(),
            int(foreground.saturation() * 0.15),
            min(255, foreground.value() + 60),
        )

        # Paint at one pixel per cell, then scale up.
        base = QImage(
            self.grid_size,
            self.grid_size,
            QImage.Format.Format_ARGB32,
        )
        base.fill(background)

        painter = QPainter(base)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(foreground)

        pattern_bits = self._pattern_bits(digest[3:])

        for row in range(self.grid_size):
            for col in range((self.grid_size + 1) // 2):
                if pattern_bits[row][col]:
                    painter.drawRect(col, row, 1, 1)
                    mirror_col = self.grid_size - col - 1
                    if mirror_col != col:
                        painter.drawRect(mirror_col, row, 1, 1)

        painter.end()

        final_image = base.scaled(
            self.image_size,
            self.image_size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

        if self.border_radius > 0:
            rounded = QImage(final_image.size(), QImage.Format.Format_ARGB32)
            rounded.fill(Qt.GlobalColor.transparent)

            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(255, 255, 255))
            painter.setPen(Qt.PenStyle.NoPen)

            rect = QRectF(0, 0, self.image_size, self.image_size)
            painter.drawRoundedRect(rect, self.border_radius, self.border_radius)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceIn
            )
            painter.drawImage(0, 0, final_image)
            painter.end()

            return rounded

        return final_image

    def _pattern_bits(self, data: bytes) -> list[list[bool]]:
        """Create a 2D boolean grid from hash data."""
        bits = []
        idx = 0
        half = (self.grid_size + 1) // 2

        for _ in range(self.grid_size):
            row = []
            for _ in range(half):
                row.append(bool(data[idx] & 1))
                idx += 1
            bits.append(row)

        return bits


class IconGenerator:
    """Icons generated deterministically from a seed string."""

    @staticmethod
    def get_project_icon(seed: str, size: int = 64) -> QPixmap:
        """An identicon for a project (seed: usually its name)."""
        border_radius = max(0, int(size * (5 / 64)))

        generator = _ProjectIconGenerator(image_size=size, border_radius=border_radius)
        image = generator.generate(seed)
        return QPixmap.fromImage(image)

    @staticmethod
    def get_version_pin(seed: str, size: int = 18) -> QPixmap:
        """A small Godot logo tinted by the version string."""
        color = string_to_qcolor(seed)
        return KQCustomIcon(GODOT_ICON_PATH, color, FillMode.GRADIENT).pixmap(size)

    @staticmethod
    def get_version_icon(seed: str, size: int = 64) -> QPixmap:
        """The Godot logo on a rounded tile coloured by the version string."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        base_color = string_to_qcolor(seed)

        gradient = QLinearGradient(0, 0, 0, size)
        gradient.setColorAt(0.0, base_color.lighter(115))
        gradient.setColorAt(1.0, base_color.darker(105))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))

        radius = size * (12 / 64)
        painter.drawRoundedRect(0, 0, size, size, radius, radius)

        logo_size = int(size * (48 / 64))

        try:
            icon_color = QColor(255, 255, 255, 230)
            godot_logo = KQCustomIcon(GODOT_ICON_PATH, icon_color).pixmap(logo_size)

            offset = (size - logo_size) // 2
            painter.drawPixmap(offset, offset, godot_logo)
        except Exception as e:
            logger.error("Error drawing logo: %s", e)

        painter.end()
        return pixmap
