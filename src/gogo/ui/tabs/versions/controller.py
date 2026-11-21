import json
from datetime import datetime, timedelta

from godotkit.engine import (
    GodotFetcher,
    detect_architecture,
    detect_platform,
)

from gogo.core import paths
from gogo.core.constants import (
    ALL_RELEASES_CACHE_LIFETIME,
    STABLE_RELEASES_CACHE_LIFETIME,
)


class GodotReleasesController:
    """Fetches Godot releases for this machine and caches them on disk."""

    DEFAULT_SORT_BY = "Date"
    DEFAULT_VARIANT = "Standard"
    DEFAULT_CHANNEL = "Stable"
    DEFAULT_LIMIT = 5

    def __init__(self):
        self.user_platform = detect_platform()
        self.user_arch = detect_architecture()
        self.cache_file = paths.cache_dir() / "releases_cache.json"
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.last_updated_string: str | None = None

    def load_cache(self) -> dict | None:
        """The cached releases and filter settings, possibly stale."""
        if not self.cache_file.exists():
            return None
        try:
            with open(self.cache_file, "r") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def is_cache_fresh(self, timestamp_iso: str | None, channel: str) -> bool:
        try:
            cache_time = datetime.fromisoformat(timestamp_iso)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False

        timeout_minutes = (
            STABLE_RELEASES_CACHE_LIFETIME
            if channel == "Stable"
            else ALL_RELEASES_CACHE_LIFETIME
        )
        return datetime.now() - cache_time < timedelta(minutes=timeout_minutes)

    def save_cache(self, settings: dict, releases: list[dict]) -> None:
        self.last_updated_string = datetime.now().isoformat()
        payload = {
            "timestamp": self.last_updated_string,
            "settings": settings,
            "data": releases,
        }
        with open(self.cache_file, "w") as f:
            json.dump(payload, f, indent=4)

    def fetch_releases(
        self, sort_by: str, variant: str, channel: str, limit: int
    ) -> list[dict]:
        """Fetch releases from the network as JSON-ready dicts (blocking)."""
        mono = variant.startswith(".NET")
        results = GodotFetcher().fetch_releases(
            stable_only=channel == "Stable",
            sort_by=sort_by.lower(),  # "Date" / "Version"
            max_releases=limit,
            platform_only=True,
        )

        releases = []
        for release in results:
            asset = release.get_asset(self.user_platform, self.user_arch, mono)
            if not asset:
                continue
            releases.append(
                {
                    "version": release.version,
                    "published_at": release.published_at.isoformat(),
                    "download_links": {
                        self.user_platform: {"url": asset.url, "size": asset.size}
                    },
                }
            )
        return releases

    def friendly_timestamp(self, iso: str | None) -> str | None:
        """e.g. 'Just now', 'Today at 14:05', or None if `iso` isn't a valid time."""
        try:
            dt = datetime.fromisoformat(iso)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

        now = datetime.now()
        delta = now - dt
        if delta < timedelta(minutes=5):
            return "Just now"
        if dt.date() == now.date():
            return f"Today at {dt.strftime('%H:%M')}"
        if dt.date() == now.date() - timedelta(days=1):
            return f"Yesterday at {dt.strftime('%H:%M')}"
        if delta < timedelta(days=7):
            return f"This week on {dt.strftime('%A')} at {dt.strftime('%H:%M')}"
        return dt.strftime("%d %B %Y at %H:%M")
