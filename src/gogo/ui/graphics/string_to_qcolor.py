import hashlib

from PySide6.QtGui import QColor


def string_to_qcolor(string: str) -> QColor:
    """The same string always gives the same colour."""
    digest = hashlib.md5(string.encode("utf-8")).digest()

    hue = int(digest[0] / 255 * 359)
    saturation = 160 + int(digest[1] / 255 * 60)
    value = 140 + int(digest[2] / 255 * 50)

    return QColor.fromHsv(hue, saturation, value)
