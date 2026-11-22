import os
import shutil
import sys
from pathlib import Path

from godotkit import project as gdk_project
from godotkit.engine import GodotVersion
from godotkit.project import ProjectMetadata, VersionFileError
from kq_icon_engine import IconStyle, KQIcon
from PySide6.QtCore import QFile, QSize, Qt
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QInputDialog,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from gogo.core import engines, git, projects
from gogo.core.config import config
from gogo.ui.components.search_bar import SearchBarWidget
from gogo.ui.components.version_selector import choose_engine_version
from gogo.ui.components.worker import Worker
from gogo.ui.dialogs.create_project import CreateProjectDialog

from .project_list_item import ProjectListItem
from .project_list_view import ProjectListView


class ProjectsTabContent(QFrame):
    """The Projects tab: search, project list, and create/import/clone/remove actions."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setAcceptDrops(True)

        self._setup_ui()
        self._setup_buttons()
        self.load_projects()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.search_bar = SearchBarWidget(self)
        self.project_list_view = ProjectListView(self)

        layout.addWidget(self.search_bar)
        layout.addWidget(self.project_list_view)

        self.search_bar.search_text_changed.connect(
            self.project_list_view.filter_projects
        )
        self.project_list_view.project_delete_requested.connect(self.remove_project)
        self.project_list_view.project_forget_requested.connect(self.forget_project)

        QShortcut(QKeySequence.StandardKey.Find, self, self._focus_search)
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            QShortcut(
                QKeySequence(key),
                self.project_list_view,
                self._open_selected_project,
                context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
            )
        QShortcut(
            QKeySequence.StandardKey.Delete,
            self.project_list_view,
            self.forget_project,
            context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )

    def _focus_search(self) -> None:
        self.search_bar.search_bar.setFocus()
        self.search_bar.search_bar.selectAll()

    def _open_selected_project(self) -> None:
        if item := self.project_list_view.get_selected_project_item():
            item.start_project()

    @staticmethod
    def _last_activity(entry: projects.ProjectEntry) -> float:
        """When the project was last opened from GoGo, else last saved by Godot."""
        if entry.last_opened:
            return entry.last_opened
        try:
            return os.path.getmtime(entry.project_file)
        except OSError:
            return 0.0

    def _setup_buttons(self) -> None:
        def _create_button(icon_name: str, tooltip: str, callback):
            button = QPushButton(KQIcon(icon_name, style=IconStyle.REGULAR), "")
            button.setToolTip(tooltip)
            button.setIconSize(QSize(24, 24))
            button.setFixedSize(QSize(32, 32))
            button.clicked.connect(callback)
            return button

        self.new_project_button = _create_button(
            "folder-plus",
            "Create a new project",
            self.create_new_project,
        )
        self.import_project_button = _create_button(
            "folder-open",
            "Import an existing project",
            self.import_project,
        )
        self.git_clone_button = _create_button(
            "git-branch",
            "Clone a project from a Git repository",
            self._on_git_clone_clicked,
        )
        if not git.git_installed():
            self.git_clone_button.setEnabled(False)
            self.git_clone_button.setToolTip("Git isn't installed")

    def create_tools(self):
        """Titlebar widgets."""
        return [
            self.new_project_button,
            self.import_project_button,
            self.git_clone_button,
        ]

    def _on_git_clone_clicked(self):
        dest = Path(config["default_project_path"]).expanduser()
        url, ok = QInputDialog.getText(
            self, "Clone Repository", f"Repository URL:\n\nClones into {dest}"
        )
        url = url.strip()
        if not ok or not url:
            return

        dest.mkdir(parents=True, exist_ok=True)
        existing = set(dest.iterdir())
        busy = QProgressDialog(f"Cloning {url}...", None, 0, 0, self.window())  # type: ignore[arg-type]
        busy.setWindowTitle("Clone Repository")
        busy.setWindowModality(Qt.WindowModality.WindowModal)
        busy.setMinimumDuration(0)

        worker = Worker(lambda _w: git.clone(url, dest), busy)
        worker.succeeded.connect(lambda repo: self._on_cloned(repo, existing))
        worker.failed.connect(
            lambda err: QMessageBox.critical(self, "Clone Failed", err)
        )
        worker.finished.connect(busy.close)
        worker.finished.connect(busy.deleteLater)
        busy.show()
        worker.start()

    def _on_cloned(self, repo: Path, existing: set[Path]) -> None:
        if repo in existing:
            QMessageBox.warning(
                self,
                "Clone Repository",
                f"A folder named '{repo.name}' already exists, so nothing was cloned:\n\n{repo}",
            )
            return
        matches = [*repo.glob("project.godot"), *repo.glob("*/project.godot")]
        project_file = matches[0] if matches else None
        if project_file is None:
            QMessageBox.warning(
                self,
                "Clone Repository",
                f"The repository was cloned, but no Godot project was found in it:\n\n{repo}",
            )
            return
        self._import_project_from_path(str(project_file))

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent):
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())

            godot_file: Path | None = None

            if path.is_dir():
                godot_file = path / "project.godot"
            elif path.name.endswith(".godot"):
                godot_file = path

            if godot_file and godot_file.exists():
                self._import_project_from_path(str(godot_file))

        event.acceptProposedAction()

    def load_projects(self):
        """Reads the saved project list and populates the list view."""
        self.project_list_view.clear_projects()

        broken = []
        for entry in sorted(projects.load(), key=self._last_activity, reverse=True):
            if not entry.project_file.exists():
                continue
            try:
                project = gdk_project.GodotProject(entry.project_file)
            except VersionFileError as e:
                broken.append((entry.project_file, e))
                continue
            self.project_list_view.add_project(project)

        if broken:
            self._offer_pin_repair(broken)

    def create_new_project(self):
        dialog = CreateProjectDialog(self.load_projects, self)
        dialog.exec()

    def _import_project_from_path(self, project_file: str):
        try:
            versions_dict = engines.list_installed()
            if not versions_dict:
                QMessageBox.critical(
                    self,
                    "Import Failed",
                    "No Godot versions are installed. Install one first.",
                )
                return

            project_path = Path(project_file).resolve()
            _project = gdk_project.parse.read(project_path)

            selected_version_name = self._select_engine_version(_project)
            if not selected_version_name:
                return

            projects.add(project_path)
            gdk_project.parse.set_engine_version(
                project_path, GodotVersion.parse(selected_version_name)
            )
            self.load_projects()

        except Exception as e:
            QMessageBox.critical(
                self, "Import Failed", f"Couldn't import the project.\n\n{e}"
            )

    def _select_engine_version(self, project_info: ProjectMetadata) -> str | None:
        lines = ["Choose the engine version to use:"]
        pinned = project_info.get("engine_version")
        if pinned:
            lines.append(f"Pinned version (.godot-version): {pinned.display_name}")
        if compat := project_info.get("compatibility_version"):
            lines.append(f"Made with Godot {compat.display_name}")
        return choose_engine_version(
            self,
            "Choose Engine Version",
            "\n\n".join(lines),
            preselect=pinned,
        )

    def _offer_pin_repair(self, broken: list[tuple[Path, VersionFileError]]) -> None:
        """Projects with an unreadable .godot-version: offer to clear their pins."""
        details = "\n".join(f"{path.parent.name}: {error}" for path, error in broken)
        reply = QMessageBox.warning(
            self,
            "Broken Engine Pins",
            f"{len(broken)} project(s) have an unreadable .godot-version file and "
            "aren't shown. Clear their pinned engine version? You can pick a "
            f"version again when you open them.\n\n{details}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for path, _ in broken:
            gdk_project.parse.update(path, {"engine_version": None})
        self.load_projects()

    def import_project(self):
        project_file, _ = QFileDialog.getOpenFileName(
            self, "Import Project", "", "Godot Project (*.godot)"
        )
        if not project_file:
            return

        self._import_project_from_path(project_file)

    def remove_project(self, project_item: ProjectListItem | None = None):
        """Move the project folder to the trash (or delete it) and drop it from the list."""
        if project_item is None:
            project_item = self.project_list_view.get_selected_project_item()

        if not project_item:
            QMessageBox.warning(
                self, "No Project Selected", "Select a project to delete."
            )
            return

        project_path = project_item.project.file_path
        project_dir = project_item.project.dir_path
        trash = "Recycle Bin" if sys.platform == "win32" else "Trash"
        reply = QMessageBox.warning(
            self,
            "Delete Project",
            f"Move this project folder to the {trash}?\n\n{project_dir}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if not QFile.moveToTrash(str(project_dir)):
                permanent = QMessageBox.warning(
                    self,
                    "Delete Project",
                    f"The project couldn't be moved to the {trash}.\n\n"
                    "Delete it permanently instead? This can't be undone.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if permanent != QMessageBox.StandardButton.Yes:
                    return
                shutil.rmtree(project_dir)
        except Exception as e:
            QMessageBox.critical(
                self, "Delete Failed", f"Couldn't delete the project.\n\n{e}"
            )
            return

        projects.remove(project_path)
        self.load_projects()

    def forget_project(self, project_item: ProjectListItem | None = None):
        """Drop a project from the list, keeping its files."""
        if project_item is None:
            project_item = self.project_list_view.get_selected_project_item()

        if not project_item:
            QMessageBox.warning(
                self, "No Project Selected", "Select a project to forget."
            )
            return

        project_path = project_item.project.file_path

        reply = QMessageBox.question(
            self,
            "Forget Project",
            f"Remove {project_item.project.name or projects.UNNAMED_PROJECT} from the list?\n\nIts files will stay on disk.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                projects.remove(project_path)
                self.load_projects()
            except Exception as e:
                QMessageBox.critical(
                    self, "Forget Failed", f"Couldn't update the project list.\n\n{e}"
                )
