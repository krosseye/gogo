from pathlib import Path

from PySide6.QtWidgets import QStyleFactory

from gogo import __version__
from gogo.core.paths import construct_path

APP_TITLE = "GoGo"
APP_VERSION = __version__
DEVELOPER = "Killian W (krosseye)"
GITHUB_URL = "https://github.com/krosseye/gogo"

APP_ICON_PATH = construct_path(["raster", "icon.png"])
GODOT_ICON_PATH = Path(construct_path(["vector", "godot.svg"]))  # not in Phosphor

THEME_OPTIONS = ["default"] + list(QStyleFactory.keys())

FEED_CACHE_LIFETIME = 1440  # 1 day
STABLE_RELEASES_CACHE_LIFETIME = 10080  # 7 days
ALL_RELEASES_CACHE_LIFETIME = 1440

USAGE_STREAK_TIMEOUT = 30
