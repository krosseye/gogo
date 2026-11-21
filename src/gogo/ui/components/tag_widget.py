from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class FlowLayout(QLayout):
    """Layout that wraps its child widgets automatically."""

    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.item_list = []

    def addItem(self, item):
        self.item_list.append(item)

    def count(self):
        return len(self.item_list)

    def itemAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins().left() + self.contentsMargins().right()
        size += QSize(margin, margin)
        return size

    def do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()
        for item in self.item_list:
            style = item.widget().style() if item.widget() else None
            space_x = spacing + (
                style.pixelMetric(QStyle.PM_LayoutHorizontalSpacing) if style else 0
            )
            space_y = spacing + (
                style.pixelMetric(QStyle.PM_LayoutVerticalSpacing) if style else 0
            )
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y()


class TagChip(QFrame):
    """A single tag chip with a label and a remove button."""

    removed = Signal(object)

    def __init__(self, tag_text, parent=None):
        super().__init__(parent)
        self.tag_text = tag_text
        self.setObjectName("TagChip")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(5)

        self.label = QLabel(tag_text)
        self.label.setObjectName("TagLabel")
        layout.addWidget(self.label)

        self.close_btn = QToolButton()
        self.close_btn.setObjectName("TagCloseButton")
        self.close_btn.setMouseTracking(True)

        self.close_btn.setIcon(
            QIcon.fromTheme(
                "window-close",
                self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton),
            )
        )
        self.close_btn.setIconSize(QSize(10, 10))
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.close_btn)

        self.close_btn.clicked.connect(self._emit_removed)

    def _emit_removed(self):
        self.removed.emit(self)


class TagEditor(QWidget):
    """Comma-separated tag input that shows each tag as a removable chip."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tags: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.line_edit = QLineEdit()
        self.line_edit.setFixedHeight(26)
        self.line_edit.setPlaceholderText("Separate tags with commas, then press Enter")
        self.line_edit.setObjectName("TagLineEdit")
        layout.addWidget(self.line_edit)

        self.tags_container = QWidget()
        self.tags_container.setMinimumHeight(32)
        self.tags_container.setObjectName("TagsContainer")
        self.flow_layout = FlowLayout(self.tags_container, margin=2, spacing=5)
        self.tags_container.setLayout(self.flow_layout)
        layout.addWidget(self.tags_container)

        self.line_edit.returnPressed.connect(self._process_input)
        self.setStyleSheet("""
        QFrame#TagChip {
            border:1px solid palette(accent);
            border-radius: 12px;
        }
        QFrame#TagChip:hover {
            background-color: palette(highlight);
        }
        QToolButton#TagCloseButton {
            background: transparent;
            border: none;
            padding: 0px;
            margin: 0px;
        }
        QWidget#TagsContainer {
            background: transparent;
            border: none;
        }
        """)

    def set_tags(self, tags: list[str]) -> None:
        """Replace all tags with a new list."""
        self._clear_tags()
        for tag in tags:
            self._add_tag(tag)

    def get_tags(self) -> list[str]:
        return self.tags.copy()

    def _clear_tags(self) -> None:
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(self.flow_layout.count() - 1)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.tags.clear()

    def _add_tag(self, tag):
        """Add a single tag if it's non‑empty and not a duplicate."""
        tag = tag.strip()
        if not tag or tag in self.tags:
            return
        self.tags.append(tag)
        chip = TagChip(tag)
        chip.removed.connect(self._remove_tag)
        self.flow_layout.addWidget(chip)

    def _remove_tag(self, chip: TagChip) -> None:
        tag = chip.tag_text
        if tag in self.tags:
            self.tags.remove(tag)
            self.flow_layout.removeWidget(chip)
            chip.deleteLater()

    def _process_input(self):
        """Parse the line edit content as CSV and add all resulting tags."""
        text = self.line_edit.text().strip()
        if not text:
            return
        parts = [p.strip() for p in text.split(",") if p.strip()]
        for tag in parts:
            self._add_tag(tag)
        self.line_edit.clear()
