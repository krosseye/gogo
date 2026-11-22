from datetime import datetime

from kq_icon_engine import KQIcon
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gogo.core.feed import RSSArticle

from .threads import ImageLoader


class _ArticleWidget(QWidget):
    """
    Shared behaviour for article widgets: link handling, async thumbnail
    loading, rounded/cropped thumbnail rendering and meta formatting.

    Subclasses must create `self.image_label` in `_build_ui()`.
    """

    article_clicked = Signal(str)

    IMAGE_SIZE = 176, 99
    CORNER_RADIUS = 6
    PADDING = 8
    SPACING = 6
    default_pixmap: QPixmap | None = None
    image_label: QLabel  # created by subclasses in _build_ui()

    def __init__(self, article_data: RSSArticle, image_cache_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.link = article_data["link"]
        self.image_cache_path = image_cache_path
        self.title = article_data["title"]
        self.article_data = article_data

        self._source_pixmap: QPixmap | None = None
        self._source_expand = True

        cls = type(self)
        if cls.default_pixmap is None:
            cls.default_pixmap = KQIcon("image").pixmap(int(self.IMAGE_SIZE[1] * 0.6))

        self.summary = (article_data.get("summary") or "").strip()
        self.setToolTip(f"{self.summary}\n\n{self.link}" if self.summary else self.link)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("ArticleCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            """
            #ArticleCard {
                background-color: palette(base);
                border: 1px solid palette(midlight);
                border-radius: 8px;
            }
            #ArticleCard:hover {
                background-color: palette(midlight);
            }
            """
        )

        self._build_ui()
        self._set_scaled_pixmap(cls.default_pixmap, expand=False)
        if category := article_data.get("category"):
            self._add_category_badge(category)

        if image_url := self.article_data.get("image_url"):
            self.image_loader = ImageLoader(image_url, self.image_cache_path)
            self.image_loader.image_loaded.connect(self._on_image_loaded)
            self.image_loader.start()

    def _build_ui(self) -> None:
        raise NotImplementedError

    def _make_text_labels(self) -> None:
        """Title, author/date and summary, styled the same in every layout."""
        self.title_label = QLabel(self.title)
        title_font = self.title_label.font()
        title_font.setBold(True)
        self.title_label.setFont(title_font)

        self.meta_label = QLabel(self._format_meta_info())
        meta_font = self.meta_label.font()
        if meta_font.pointSizeF() > 0:
            meta_font.setPointSizeF(meta_font.pointSizeF() - 1)
        self.meta_label.setFont(meta_font)
        palette = self.meta_label.palette()
        muted = palette.color(QPalette.ColorRole.WindowText)
        muted.setAlpha(160)
        palette.setColor(QPalette.ColorRole.WindowText, muted)
        self.meta_label.setPalette(palette)

        self.summary_label = QLabel(self.summary)
        self.summary_label.setVisible(bool(self.summary))

        for label in (self.title_label, self.meta_label, self.summary_label):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.title_label.setWordWrap(True)
        self.summary_label.setWordWrap(True)

    def _two_lines(self, label: QLabel) -> int:
        return label.fontMetrics().lineSpacing() * 2 + 2

    def _add_category_badge(self, category: str) -> None:
        """Pin a small solid badge over the thumbnail's top-left corner."""
        badge = QLabel(category, self.image_label)
        badge.setTextFormat(Qt.TextFormat.PlainText)
        font = badge.font()
        font.setBold(True)
        if font.pointSizeF() > 0:
            font.setPointSizeF(font.pointSizeF() - 1)
        badge.setFont(font)
        badge.setStyleSheet(
            """
            background-color: palette(highlight);
            color: palette(highlighted-text);
            border-radius: 4px;
            padding: 1px 6px;
            """
        )
        badge.adjustSize()
        badge.move(6, 6)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            QDesktopServices.openUrl(QUrl(self.link))
            self.article_clicked.emit(self.link)
        super().mousePressEvent(event)

    def _format_meta_info(self) -> str:
        author = self.article_data.get("author") or ""
        date_str = self._format_date(self.article_data.get("date"))

        if author and author.strip():
            return f"{author} • {date_str}"
        return date_str

    def _format_date(self, date: datetime | None) -> str:
        if date and isinstance(date, datetime):
            return date.strftime("%b %d, %Y")
        return "Unknown Date"

    def _set_scaled_pixmap(self, pixmap: QPixmap, expand: bool = True):
        """
        Scale into IMAGE_SIZE with rounded corners.

        expand=True crops to fill (real thumbnails); expand=False fits the
        pixmap centred (placeholder icon).
        """
        if pixmap.isNull():
            return

        self._source_pixmap = pixmap
        self._source_expand = expand

        width, height = self.IMAGE_SIZE
        mode = (
            Qt.AspectRatioMode.KeepAspectRatioByExpanding
            if expand
            else Qt.AspectRatioMode.KeepAspectRatio
        )
        scaled = pixmap.scaled(
            width, height, mode, Qt.TransformationMode.SmoothTransformation
        )

        result = QPixmap(width, height)
        result.fill(Qt.GlobalColor.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, width, height, self.CORNER_RADIUS, self.CORNER_RADIUS)
        painter.setClipPath(path)
        painter.drawPixmap(
            (width - scaled.width()) // 2, (height - scaled.height()) // 2, scaled
        )
        painter.end()

        self.image_label.setPixmap(result)

    def _rescale_image(self):
        """Re-render the current thumbnail after IMAGE_SIZE changed."""
        if self._source_pixmap is not None:
            self._set_scaled_pixmap(self._source_pixmap, self._source_expand)

    def _on_image_loaded(self, image: QImage):
        if image.isNull():
            broken = KQIcon("image-broken").pixmap(int(self.IMAGE_SIZE[1] * 0.6))
            self._set_scaled_pixmap(broken, expand=False)
        else:
            self._set_scaled_pixmap(QPixmap.fromImage(image), expand=True)


class RSSCard(_ArticleWidget):
    """
    Vertical card (thumbnail on top) for the horizontal Recent strip.

    The card does not size itself: the parent asks `natural_height(image_width)`
    for each candidate width and then calls `apply_size()` so every card in the
    strip shares the same width and height. Content is packed at the top, so
    the title and author/date stay together and any spare space is at the bottom.
    """

    FULL_IMAGE_WIDTH = 244
    MIN_IMAGE_WIDTH = 140
    IMAGE_SIZE = FULL_IMAGE_WIDTH, round(FULL_IMAGE_WIDTH * 9 / 16)
    default_pixmap: QPixmap | None = None

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        p = self.PADDING
        layout.setContentsMargins(p, p, p, p)
        layout.setSpacing(self.SPACING)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label)

        self._make_text_labels()
        layout.addWidget(self.title_label)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.summary_label)

        self.apply_size(
            self.FULL_IMAGE_WIDTH, self.natural_height(self.FULL_IMAGE_WIDTH)
        )

    @staticmethod
    def _image_height(image_width: int) -> int:
        return round(image_width * 9 / 16)

    def _title_height(self, image_width: int) -> int:
        return self._two_lines(self.title_label)

    def _summary_height(self, image_width: int) -> int:
        line = self.summary_label.fontMetrics().lineSpacing()
        needed = self.summary_label.heightForWidth(image_width)
        if needed <= 0:
            needed = line + 2
        return min(needed, self._two_lines(self.summary_label))

    def _summary_shown(self, image_width: int) -> bool:
        return bool(self.summary) and image_width >= self.FULL_IMAGE_WIDTH

    def natural_height(self, image_width: int) -> int:
        """Height this card needs for a given thumbnail width (no layout side effects)."""
        height = (
            self.PADDING * 2
            + self._image_height(image_width)
            + self.SPACING
            + self._title_height(image_width)
            + self.SPACING
            + self.meta_label.sizeHint().height()
        )
        if self._summary_shown(image_width):
            height += self.SPACING + self._summary_height(image_width)
        return height

    def apply_size(self, image_width: int, card_height: int) -> None:
        """Apply a thumbnail width and a (shared) card height."""
        self.IMAGE_SIZE = (image_width, self._image_height(image_width))
        self.image_label.setFixedSize(*self.IMAGE_SIZE)
        self.title_label.setFixedHeight(self._title_height(image_width))

        show_summary = self._summary_shown(image_width)
        self.summary_label.setVisible(show_summary)
        if show_summary:
            self.summary_label.setFixedHeight(self._summary_height(image_width))

        self.setFixedSize(image_width + self.PADDING * 2, card_height)
        self._rescale_image()


class RSSItem(_ArticleWidget):
    """Horizontal card (thumbnail left, text right) for the vertical Older list."""

    IMAGE_SIZE = 176, 99
    default_pixmap: QPixmap | None = None

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        p = self.PADDING
        layout.setContentsMargins(p, p, p, p)
        layout.setSpacing(12)

        self.image_label = QLabel()
        self.image_label.setFixedSize(*self.IMAGE_SIZE)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label, 0, Qt.AlignmentFlag.AlignTop)

        self._make_text_labels()
        self.summary_label.setMaximumHeight(self._two_lines(self.summary_label))
        text = QVBoxLayout()
        text.setSpacing(self.SPACING)
        text.setAlignment(Qt.AlignmentFlag.AlignTop)
        text.addWidget(self.title_label)
        text.addWidget(self.meta_label)
        text.addWidget(self.summary_label)
        layout.addLayout(text, 1)
