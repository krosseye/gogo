from typing import cast

from godotkit.project import GodotProject
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gogo.ui.components.placeholder_widget import PlaceholderWidget

from .project_list_item import ProjectListItem
from .project_search import ProjectSearchEngine


class ProjectListView(QWidget):
    """The project list with search filtering, or a placeholder when it's empty."""

    project_delete_requested = Signal(ProjectListItem)
    project_forget_requested = Signal(ProjectListItem)
    project_favourite_toggled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[tuple[QListWidgetItem, ProjectListItem]] = []
        self._search_engine = ProjectSearchEngine()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list_widget = QListWidget()
        self._list_widget.setSpacing(4)

        self._empty_state_placeholder = PlaceholderWidget(
            self,
            "Nothing's here...",
            "Try creating a project or importing an existing one!",
        )

        layout.addWidget(self._list_widget)
        layout.addWidget(self._empty_state_placeholder)

        self._update_view_state()

    def clear_projects(self) -> None:
        self._list_widget.clear()
        self._items.clear()
        self._update_view_state()

    def add_project(self, project: GodotProject) -> None:
        project_widget = ProjectListItem(project)
        project_widget.delete_requested.connect(
            lambda: self.project_delete_requested.emit(project_widget)
        )
        project_widget.forget_requested.connect(
            lambda: self.project_forget_requested.emit(project_widget)
        )
        project_widget.favourite_toggled.connect(self.project_favourite_toggled.emit)

        list_item = QListWidgetItem(self._list_widget)
        list_item.setSizeHint(project_widget.sizeHint())

        self._list_widget.addItem(list_item)
        self._list_widget.setItemWidget(list_item, project_widget)

        self._items.append((list_item, project_widget))
        self._update_view_state()

    def filter_projects(self, search_term: str) -> None:
        """Show only projects matching `search_term` (see ProjectSearchEngine)."""
        all_projects = []
        favorites: set[str] = set()

        for _, widget in self._items:
            all_projects.append(widget.project)
            if widget.is_favourite:
                favorites.add(str(widget.project.file_path))

        filtered_projects = self._search_engine.run(
            all_projects, search_term, favorites
        )

        filtered_paths = {p.file_path for p in filtered_projects}

        visible_count = 0
        for list_item, project_widget in self._items:
            should_show = project_widget.project.file_path in filtered_paths
            list_item.setHidden(not should_show)

            if should_show:
                visible_count += 1

        self._update_view_state(visible_count, search_term)

    def get_selected_project_item(self) -> ProjectListItem | None:
        current_item = self._list_widget.currentItem()
        if not current_item:
            return None
        return cast(ProjectListItem, self._list_widget.itemWidget(current_item))

    def _update_view_state(
        self, visible_count: int = -1, search_term: str = ""
    ) -> None:
        """Show the list, or the placeholder when nothing is visible (-1 = all items)."""
        if visible_count == -1:
            visible_count = len(self._items)

        has_items = visible_count > 0

        self._list_widget.setVisible(has_items)
        self._empty_state_placeholder.setVisible(not has_items)

        if not has_items:
            if search_term:
                self._empty_state_placeholder.hint = (
                    f"No projects found for: '{search_term}'"
                )
            else:
                self._empty_state_placeholder.hint = (
                    "Try creating a project or importing an existing one!"
                )
