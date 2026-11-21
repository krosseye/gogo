import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QStandardPaths,
    QTimer,
)
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
)

from gogo.cli.core import app as cli_app
from gogo.core import constants
from gogo.core.config import config

TARGET_WIDTH_RATIO = 2.5
TARGET_HEIGHT_RATIO = 2.0
MAX_SIZE_RATIO = 0.9
MIN_WIDTH, MIN_HEIGHT = 580, 500


def setup_metadata() -> None:
    """Sets the application metadata."""
    QCoreApplication.setApplicationName(constants.APP_TITLE)
    QCoreApplication.setOrganizationName(constants.DEVELOPER)
    QCoreApplication.setApplicationVersion(constants.APP_VERSION)
    QCoreApplication.setOrganizationDomain(constants.GITHUB_URL)


def setup_logging() -> None:
    """Configures the logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def setup_usage_stats(app) -> None:
    """Configures usage stats tracking."""
    from gogo.core.stats import track_app_open_async

    track_app_open_async()

    streak_timer = QTimer(app)
    streak_timer.timeout.connect(track_app_open_async)
    streak_timer.start(constants.USAGE_STREAK_TIMEOUT * 60 * 1000)


def get_config_path() -> Path:
    """Returns the path to the configuration file."""
    base_path = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    return Path(base_path) / "config.json"


def create_main_window(app: QApplication) -> QMainWindow:
    """Creates and configures the main window with resolution-aware scaling."""
    from gogo.ui.appearance import apply_appearance
    from gogo.ui.main_window import MainWindow

    app.setWindowIcon(QIcon(constants.APP_ICON_PATH))

    screen = app.primaryScreen()
    geo = screen.availableGeometry()
    screen_w = geo.width()
    screen_h = geo.height()

    target_w = int(screen_w // TARGET_WIDTH_RATIO)
    target_h = int(screen_h // TARGET_HEIGHT_RATIO)
    max_w = int(screen_w * MAX_SIZE_RATIO)
    max_h = int(screen_h * MAX_SIZE_RATIO)

    final_w = max(MIN_WIDTH, min(target_w, max_w))
    final_h = max(MIN_HEIGHT, min(target_h, max_h))

    apply_appearance()  # before building widgets, so they start with the final font/style
    window = MainWindow()
    window.resize(final_w, final_h)
    window.move(
        (screen_w - final_w) // 2,
        (screen_h - final_h) // 2,
    )
    window.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
    return window


def main() -> None:
    setup_metadata()

    app = QApplication(sys.argv)

    config.set_config_file(get_config_path())

    if len(sys.argv) > 1:
        # Only count interactive CLI use (skip CI, scripts and bots)
        if sys.stdin and sys.stdin.isatty() and not os.environ.get("CI"):
            from gogo.core.stats import StatsManager

            StatsManager.track_app_open()
        cli_app(sys.argv[1:])
        sys.exit(0)

    setup_logging()
    setup_usage_stats(app)

    window = create_main_window(app)
    window.show()

    sys.exit(app.exec())
