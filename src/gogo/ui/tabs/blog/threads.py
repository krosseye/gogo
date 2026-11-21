import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QEventLoop, QThread, QUrl, Signal
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from gogo.core.constants import FEED_CACHE_LIFETIME

logger = logging.getLogger(__name__)


class ImageLoader(QThread):
    """
    Loads an image from a URL using Qt Networking.
    Uses a disk cache. Emits a QImage (QPixmap is GUI-thread only);
    a null QImage means loading failed.
    """

    image_loaded = Signal(QImage)

    def __init__(self, url: str, cache_path: Path):
        super().__init__()
        self.url = url
        self.cache_path = cache_path

        self.image_filename = self._get_cache_filename(url)
        self.image_cache_path = self.cache_path / self.image_filename

    @staticmethod
    def _get_cache_filename(url: str) -> str:
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        extension = Path(QUrl(url).path()).suffix
        return f"{url_hash}{extension}" if extension else url_hash

    def _load_from_cache(self) -> QImage | None:
        if not self.image_cache_path.exists():
            return None

        image = QImage(str(self.image_cache_path))
        return image if not image.isNull() else None

    def _write(self, data: bytes, path: Path):
        with open(path, "wb") as f:
            f.write(data)

    def run(self):
        cached = self._load_from_cache()
        if cached:
            self.image_loaded.emit(cached)
            return

        try:
            manager = QNetworkAccessManager()
            request = QNetworkRequest(QUrl(self.url))
            request.setTransferTimeout(10000)

            reply = manager.get(request)
            loop = QEventLoop()
            reply.finished.connect(loop.quit)
            loop.exec()

            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise OSError(f"Network error: {reply.errorString()}")

            data = reply.readAll()
            image = QImage()
            if image.loadFromData(data):
                self.cache_path.mkdir(parents=True, exist_ok=True)
                self._write(data.data(), self.image_cache_path)
                self.image_loaded.emit(image)
            else:
                logger.warning("Failed to decode image: %s", self.url)
                self.image_loaded.emit(QImage())

            reply.deleteLater()

        except Exception:
            logger.exception("Image load error: %s", self.url)
            self.image_loaded.emit(QImage())


class RSSFetcherThread(QThread):
    """
    Thread that loads RSS feeds from cache or remote source.
    Uses atomic cache writes, consistent datetime parsing, and unified logic.
    """

    feed_loaded = Signal(list)
    feed_failed = Signal(str)

    def __init__(self, cache_file: Path, fetcher_cls):
        """
        fetcher_cls: class that provides `fetch_feed()` and works as a context manager.
        """
        super().__init__()
        self.cache_file = cache_file
        self.fetcher_cls = fetcher_cls

    def _write(self, data, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def _serialize(self, data: list) -> list:
        """
        Convert article objects/dicts to JSON-safe dicts with ISO timestamps.
        """
        serializable = []
        for article in data:
            d = dict(article)
            dt_obj = d.get("date")

            if isinstance(dt_obj, datetime):
                d["date"] = dt_obj.isoformat()
            elif dt_obj is None:
                d["date"] = None

            serializable.append(d)

        return serializable

    def _deserialize(self, raw: list) -> list:
        """
        Convert JSON dicts back to expected structure with datetime objects.
        """
        results = []
        for item in raw:
            d = dict(item)
            date_value = d.get("date")

            if isinstance(date_value, str):
                try:
                    d["date"] = datetime.fromisoformat(date_value)
                except ValueError:
                    d["date"] = None

            results.append(d)

        return results

    def _load_from_cache(self, freshness_minutes: int | None) -> list | None:
        if not self.cache_file.exists():
            return None

        if freshness_minutes is not None:
            mtime = datetime.fromtimestamp(self.cache_file.stat().st_mtime)
            if datetime.now() - mtime > timedelta(minutes=freshness_minutes):
                return None

        try:
            raw = json.loads(self.cache_file.read_text("utf-8"))
            return self._deserialize(raw)
        except Exception:
            logger.exception("Cache read failed")
            return None

    def _save_to_cache(self, data: list):
        try:
            self._write(self._serialize(data), self.cache_file)
        except Exception:
            logger.exception("Cache write failed")

    def run(self):
        """Fresh cache, else network, else stale cache."""
        data = self._load_from_cache(freshness_minutes=FEED_CACHE_LIFETIME)

        if data is None:
            try:
                with self.fetcher_cls() as fetcher:
                    data = fetcher.fetch_feed()

                if data:
                    self._save_to_cache(data)

            except Exception:
                logger.exception("RSS fetch failed")
                data = self._load_from_cache(freshness_minutes=None)

        if data is not None:
            self.feed_loaded.emit(data)
        else:
            self.feed_failed.emit("Could not load feed from network or cache.")
