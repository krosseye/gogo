import os
from pathlib import Path

from PySide6.QtCore import QFileInfo, Qt, QUrl
from PySide6.QtGui import (
    QDesktopServices,
    QIcon,
    QPalette,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileIconProvider,
    QFrame,
    QHeaderView,
    QLabel,
    QMenu,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from gogo.ui.components.placeholder_widget import PlaceholderWidget

from .utils import format_bytes


class FileListWidget(QWidget):
    """A widget to display a list of files for a selected category."""

    def __init__(self, project_path: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._project_path = project_path
        self._setup_ui()

    def _setup_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._placeholder = PlaceholderWidget(
            title="No Category Selected",
            hint="Select a category in the chart to see its files.",
        )

        self._view = QTreeView()
        self._view.setRootIsDecorated(False)
        self._view.setAlternatingRowColors(True)
        self._view.setSortingEnabled(True)
        self._view.header().setSortIndicator(1, Qt.SortOrder.DescendingOrder)
        self._view.setVisible(False)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._show_context_menu)
        self._view.doubleClicked.connect(self._on_item_double_clicked)

        self._model = QStandardItemModel(0, 3, self)
        self._model.setHorizontalHeaderLabels(["Name", "Size", "Path"])
        self._view.setModel(self._model)
        header = self._view.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self._summary_container = QFrame()
        self._summary_container.setFrameShape(QFrame.Shape.StyledPanel)
        self._summary_container.setFrameShadow(QFrame.Shadow.Raised)
        self._summary_container.setVisible(False)
        summary_layout = QVBoxLayout(self._summary_container)

        self._summary_label = QLabel()
        summary_layout.addWidget(self._summary_label)

        self._layout.addWidget(self._summary_container)
        self._layout.addWidget(self._placeholder, 1)
        self._layout.addWidget(self._view, 1)

    def clear(self):
        """Resets the view to its initial placeholder state."""
        self._placeholder.setVisible(True)
        self._view.setVisible(False)
        self._summary_container.setVisible(False)
        self._model.removeRows(0, self._model.rowCount())

    def update_list(self, category: str, stats: dict):
        """Populates the list with files from a category."""
        self.clear()
        self._placeholder.setVisible(False)
        self._view.setVisible(True)
        self._summary_container.setVisible(True)

        readable_size = format_bytes(stats["size"])
        count = stats["count"]
        self._summary_label.setText(
            f"<h3>{category}</h3> {count} files &nbsp;|&nbsp; {readable_size}"
        )

        files = stats.get("files", [])

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            icon_provider = QFileIconProvider()
            for file_path, size in files:
                p = Path(file_path)
                file_info = QFileInfo(file_path)

                name_item = QStandardItem(p.name)
                name_item.setIcon(icon_provider.icon(file_info))
                name_item.setToolTip(file_path)
                name_item.setEditable(False)

                size_item = QStandardItem()
                size_item.setData(size, Qt.ItemDataRole.EditRole)
                size_item.setText(format_bytes(size))
                size_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                size_item.setEditable(False)

                rel_path = os.path.relpath(p.parent, self._project_path)
                path_item = QStandardItem(
                    f".{os.sep}{rel_path}" if rel_path != "." else f".{os.sep}"
                )
                path_item.setForeground(
                    QApplication.palette().color(QPalette.ColorRole.PlaceholderText)
                )
                path_item.setToolTip(str(p.parent))
                path_item.setEditable(False)

                self._model.appendRow([name_item, size_item, path_item])
        finally:
            QApplication.restoreOverrideCursor()

        self._view.sortByColumn(1, Qt.SortOrder.DescendingOrder)

    def _show_context_menu(self, pos):
        index = self._view.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self)
        open_action = menu.addAction(QIcon.fromTheme("document-open"), "Open File")
        show_action = menu.addAction(
            QIcon.fromTheme("folder-open"), "Open in File Manager"
        )

        action = menu.exec(self._view.viewport().mapToGlobal(pos))
        file_path = self._model.item(index.row(), 0).toolTip()

        if action == show_action:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(file_path)))
        elif action == open_action:
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    def _on_item_double_clicked(self, index):
        """Opens the file when double-clicked."""
        file_path = self._model.item(index.row(), 0).toolTip()
        if file_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
