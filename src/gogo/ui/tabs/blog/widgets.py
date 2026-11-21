import logging
from datetime import UTC, datetime, timedelta

from godotkit.feed import RSSFetcher as GodotKitRSSFetcher
from kq_icon_engine import KQIcon
from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent, QWheelEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gogo.core import paths
from gogo.ui.components.placeholder_widget import PlaceholderWidget

from .article import RSSCard, RSSItem
from .threads import RSSFetcherThread

logger = logging.getLogger(__name__)


def _as_aware(dt: datetime | None) -> datetime:
    """Return a timezone-aware datetime so naive/aware values can be compared."""
    if dt is None:
        return datetime.min.replace(tzinfo=UTC)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class HorizontalScrollArea(QScrollArea):
    """Scroll area that scrolls sideways, including with a regular mouse wheel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta()
        if delta.x() == 0 and delta.y() != 0:
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - delta.y())
            event.accept()
            return
        super().wheelEvent(event)


class BlogTabContent(QWidget):
    """
    Tab widget for displaying Godot Engine RSS feed articles."""

    RECENT_DAYS = 30
    OLDER_MIN_HEIGHT = 110
    CARD_STEP = 8

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.base_cache_path = paths.cache_dir().joinpath("blog")
        self.feed_cache_file = self.base_cache_path.joinpath("feed_cache.json")
        self.image_cache_path = self.base_cache_path.joinpath("images")

        self.base_cache_path.mkdir(parents=True, exist_ok=True)
        self.image_cache_path.mkdir(parents=True, exist_ok=True)

        self._cards: list[RSSCard] = []
        self._has_older = False
        self._strip_state: tuple[int, int] | None = None

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.lists_container = QWidget()
        self.lists_layout = QVBoxLayout(self.lists_container)
        self.lists_layout.setContentsMargins(0, 0, 0, 0)
        self.lists_layout.setSpacing(10)

        self.recent_section = QWidget()
        recent_layout = QVBoxLayout(self.recent_section)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_layout.setSpacing(4)

        self.recent_label = QLabel("<h3>Recent</h3>")
        self.recent_scroll = HorizontalScrollArea()
        self.recent_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self.recent_content = QWidget()
        self.recent_cards_layout = QHBoxLayout(self.recent_content)
        self.recent_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_cards_layout.setSpacing(12)
        self.recent_scroll.setWidget(self.recent_content)

        recent_layout.addWidget(self.recent_label)
        recent_layout.addWidget(self.recent_scroll)

        self.older_section = QWidget()
        older_layout = QVBoxLayout(self.older_section)
        older_layout.setContentsMargins(0, 0, 0, 0)
        older_layout.setSpacing(4)

        self.older_label = QLabel("<h3>Older</h3>")
        self.older_list_widget = self._create_list_widget()

        older_layout.addWidget(self.older_label)
        older_layout.addWidget(self.older_list_widget, 1)

        self.lists_layout.addWidget(self.recent_section, 0)
        self.lists_layout.addWidget(self.older_section, 1)

        self.main_layout.addWidget(self.lists_container)
        self.lists_container.hide()

        self.feed_fetcher: RSSFetcherThread | None = None

        self.loading_widget = PlaceholderWidget(
            title="Loading Feed...",
            icon=KQIcon("newspaper").pixmap(128),
        )
        self.main_layout.addWidget(self.loading_widget)

        self._load_rss_feed()
        self._prune_image_cache()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_recent_strip()

    def _create_list_widget(self) -> QListWidget:
        list_widget = QListWidget()
        list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        list_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        list_widget.setMinimumHeight(self.OLDER_MIN_HEIGHT)
        return list_widget

    def _load_rss_feed(self):
        self.feed_fetcher = RSSFetcherThread(self.feed_cache_file, GodotKitRSSFetcher)
        self.feed_fetcher.feed_loaded.connect(self._on_feed_loaded)
        self.feed_fetcher.feed_failed.connect(self._on_feed_failed)
        self.feed_fetcher.start()

    def _on_feed_loaded(self, rss_data: list):
        logger.info("Loaded %d articles.", len(rss_data))

        if not rss_data:
            self._on_feed_failed("No articles found in the feed.")
            return

        self.loading_widget.hide()
        self.lists_container.show()

        rss_data.sort(key=lambda a: _as_aware(a.get("date")), reverse=True)

        cutoff = datetime.now(UTC) - timedelta(days=self.RECENT_DAYS)
        recent_articles = []
        older_articles = []

        for article in rss_data:
            article_date = article.get("date")
            if article_date and _as_aware(article_date) > cutoff:
                recent_articles.append(article)
            else:
                older_articles.append(article)

        self._populate_older(older_articles)
        self._populate_recent(recent_articles)

    def _populate_recent(self, articles: list):
        while self.recent_cards_layout.count():
            item = self.recent_cards_layout.takeAt(0)
            if item and (widget := item.widget()):
                widget.deleteLater()

        self._cards = []
        self._strip_state = None
        self.recent_section.setVisible(bool(articles))
        if not articles:
            return

        for data in articles:
            card = RSSCard(article_data=data, image_cache_path=self.image_cache_path)
            card.article_clicked.connect(
                lambda link: logger.info("Opened article: %s", link)
            )
            self.recent_cards_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
            self._cards.append(card)

        self.recent_cards_layout.addStretch(1)
        self._fit_recent_strip()

    def _fit_recent_strip(self):
        """
        Pick the largest card size that fits the current tab height."""
        if not self._cards:
            return

        scrollbar_room = (
            self.recent_scroll.horizontalScrollBar().sizeHint().height() + 4
        )
        used = self.recent_label.sizeHint().height() + 4 + scrollbar_room
        if self._has_older:
            used += (
                self.lists_layout.spacing()
                + self.older_label.sizeHint().height()
                + 4
                + self.older_list_widget.minimumHeight()
            )
        available = self.height() - used

        width = RSSCard.FULL_IMAGE_WIDTH
        while width > RSSCard.MIN_IMAGE_WIDTH and (
            max(c.natural_height(width) for c in self._cards) > available
        ):
            width -= self.CARD_STEP
        width = max(width, RSSCard.MIN_IMAGE_WIDTH)
        height = max(c.natural_height(width) for c in self._cards)

        if self._strip_state == (width, height):
            return
        self._strip_state = (width, height)

        for card in self._cards:
            card.apply_size(width, height)
        self.recent_scroll.setFixedHeight(height + scrollbar_room)

    def _populate_older(self, articles: list):
        self.older_list_widget.clear()
        self._has_older = bool(articles)
        self.older_section.setVisible(self._has_older)

        for data in articles:
            item_widget = RSSItem(
                article_data=data,
                image_cache_path=self.image_cache_path,
            )
            item_widget.article_clicked.connect(
                lambda link: logger.info("Opened article: %s", link)
            )
            list_item = QListWidgetItem(self.older_list_widget)
            self.older_list_widget.setItemWidget(list_item, item_widget)
            list_item.setSizeHint(item_widget.sizeHint())

    def _on_feed_failed(self, error_message: str):
        logger.error("Feed loading failed: %s", error_message)

        self.lists_container.hide()
        self.loading_widget.title = "Couldn't Load Feed"
        self.loading_widget.hint = error_message
        self.loading_widget.show()

    def _prune_image_cache(self, max_age_days=90):
        """Delete cached images older than `max_age_days`."""
        prune_time = datetime.now() - timedelta(days=max_age_days)

        for image_file in self.image_cache_path.glob("*"):
            try:
                file_mtime = datetime.fromtimestamp(image_file.stat().st_mtime)
                if file_mtime < prune_time:
                    image_file.unlink()
                    logger.info("Deleted old image: %s", image_file.name)
            except OSError as e:
                logger.error("Error pruning image file %s: %s", image_file, e)
