import datetime
import logging
from typing import Any, NamedTuple, cast

from PySide6.QtCore import QCoreApplication, QSettings, QThread

from gogo.core.constants import APP_TITLE, DEVELOPER

logger = logging.getLogger(__name__)


class UsageStats(NamedTuple):
    dialog_views: int
    dialog_first_found: str
    current_streak: int
    longest_streak: int
    open_count: int
    first_opened: str
    project_launches: int
    most_used_engine: str


class StatsManager:
    @staticmethod
    def _get_settings() -> QSettings:
        return QSettings(DEVELOPER, APP_TITLE)

    @staticmethod
    def _get_int(settings: QSettings, key: str, default: int = 0) -> int:
        return int(cast(Any, settings.value(key, default)))

    @staticmethod
    def _get_date(settings: QSettings, key: str) -> datetime.date | None:
        """A date stored as a unix timestamp, or None if missing or invalid."""
        val = settings.value(key)
        if val in (None, ""):
            return None
        try:
            ts = float(cast(Any, val))
        except (ValueError, TypeError):
            return None
        return datetime.date.fromtimestamp(ts) if ts > 0 else None

    @staticmethod
    def _save_date(settings: QSettings, key: str, date: datetime.date) -> None:
        dt = datetime.datetime(date.year, date.month, date.day)
        settings.setValue(key, int(dt.timestamp()))

    @classmethod
    def track_app_open(cls) -> None:
        """Count an app open and update the daily streak."""
        settings = cls._get_settings()
        today = datetime.date.today()

        open_count = cls._get_int(settings, "stats/open_count") + 1
        settings.setValue("stats/open_count", open_count)

        if not cls._get_date(settings, "stats/first_opened"):
            logger.info("First time opening the app! Welcome!")
            cls._save_date(settings, "stats/first_opened", today)

        last_date = cls._get_date(settings, "stats/last_date")
        current_streak = cls._get_int(settings, "stats/current_streak")
        longest_streak = cls._get_int(settings, "stats/longest_streak")

        if last_date == today:
            return
        if last_date == today - datetime.timedelta(days=1):
            current_streak += 1
            logger.info("Streak incremented to %d!", current_streak)
        else:
            current_streak = 1
            logger.info("Streak started.")

        cls._save_date(settings, "stats/last_date", today)
        settings.setValue("stats/current_streak", current_streak)
        settings.setValue("stats/longest_streak", max(longest_streak, current_streak))

    @classmethod
    def track_project_launch(cls) -> int:
        """Count a project launch; returns the new total."""
        settings = cls._get_settings()
        count = cls._get_int(settings, "stats/project_launch_count") + 1
        settings.setValue("stats/project_launch_count", count)
        return count

    @classmethod
    def track_engine_usage(cls, version: str) -> None:
        settings = cls._get_settings()
        key = f"stats/engine_usage/{version}"
        settings.setValue(key, cls._get_int(settings, key) + 1)

    @classmethod
    def register_dialog_view(cls) -> UsageStats:
        """Count a view of the (secret) stats dialog and return all stats."""
        settings = cls._get_settings()
        today = datetime.date.today()

        view_count = cls._get_int(settings, "stats/dialog_view_count") + 1
        settings.setValue("stats/dialog_view_count", view_count)

        first_found = cls._get_date(settings, "stats/first_dialog_discovered")
        if not first_found:
            first_found = today
            cls._save_date(settings, "stats/first_dialog_discovered", first_found)

        settings.beginGroup("stats/engine_usage")
        usage = {key: cls._get_int(settings, key) for key in settings.childKeys()}
        settings.endGroup()
        most_used_engine = max(usage, key=usage.__getitem__) if usage else "None"

        fmt = "%B %d, %Y"
        first_opened = cls._get_date(settings, "stats/first_opened")
        return UsageStats(
            dialog_views=view_count,
            dialog_first_found=first_found.strftime(fmt),
            current_streak=cls._get_int(settings, "stats/current_streak"),
            longest_streak=cls._get_int(settings, "stats/longest_streak"),
            open_count=cls._get_int(settings, "stats/open_count"),
            first_opened=first_opened.strftime(fmt) if first_opened else "Unknown",
            project_launches=cls._get_int(settings, "stats/project_launch_count"),
            most_used_engine=most_used_engine,
        )

    @staticmethod
    def get_emoji(streak: int) -> str:
        """The emoji for a streak milestone."""
        if streak == 420:
            return "🌿"
        if streak == 69:
            return "🍑"
        if streak >= 100:
            return "🐐"
        milestones = ("🌱", "🔥", "⚡️", "🚀", "☄️", "💥", "🌋", "💎", "👑", "🐐")
        return milestones[streak // 10]


class AppOpenWorker(QThread):
    def run(self) -> None:
        StatsManager.track_app_open()


def track_app_open_async() -> None:
    """Track an app open off the UI thread."""
    worker = AppOpenWorker()
    if app := QCoreApplication.instance():
        worker.setParent(app)
    worker.finished.connect(worker.deleteLater)
    worker.start()
