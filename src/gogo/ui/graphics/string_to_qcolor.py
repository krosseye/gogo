import hashlib
import math

from godotkit.engine import GodotVersion
from PySide6.QtGui import QColor

GOLDEN_ANGLE = 137.50776405
_STEPS = (7, 27, 11, 7, 35)
_CHANNELS = ("dev", "alpha", "beta", "rc", "stable")
_LIGHTNESS = (0.55, 0.66)
_CHROMA = 0.14


def string_to_qcolor(string: str) -> QColor:
    """The same string always gives the same colour."""
    try:
        v = GodotVersion.parse(string)
    except ValueError:
        digest = hashlib.md5(string.encode("utf-8")).digest()
        return _oklch(_LIGHTNESS[0], _CHROMA, digest[0] / 256 * 360)

    parts = (v.major, v.minor, v.patch, _CHANNELS.index(v.channel), v.channel_num)
    k = sum(p * w for p, w in zip(parts, _STEPS, strict=True))
    return _oklch(_LIGHTNESS[k % 2], _CHROMA, k * GOLDEN_ANGLE % 360)


def _oklch(lightness: float, chroma: float, hue: float) -> QColor:
    """A colour from OKLCH fitted into sRGB."""
    near_yellow = max(0.0, 1 - abs((hue - 95 + 180) % 360 - 180) / 30)
    lightness += near_yellow * max(0.0, 0.74 - lightness)
    chroma += near_yellow * max(0.0, 0.15 - chroma)

    h = math.radians(hue)
    while True:
        a, b = chroma * math.cos(h), chroma * math.sin(h)
        l, m, s = (
            (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3,
            (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3,
            (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3,
        )
        rgb = (
            4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
        )
        if chroma <= 0 or all(-1e-4 <= c <= 1 + 1e-4 for c in rgb):
            break
        chroma -= 0.005

    def encode(c: float) -> float:
        c = min(1.0, max(0.0, c))
        return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055

    return QColor.fromRgbF(*(encode(c) for c in rgb))
