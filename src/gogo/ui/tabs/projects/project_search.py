import os
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any, NamedTuple

from godotkit.engine import GodotVersion
from godotkit.project import GodotProject


class Filter(NamedTuple):
    key: str
    op: str
    value: str


class SearchQuery(NamedTuple):
    term: str
    filters: list[Filter]


class SearchParser:
    FILTER_RE = re.compile(r"\[\s*(\w+)\s*([<>=!]+)\s*(.*?)\s*\]")

    def parse(self, query_str: str) -> SearchQuery:
        """Parses a search string into a term and a list of filters."""
        filters = []

        def repl(m: re.Match) -> str:
            key, op, value = m.groups()
            filters.append(Filter(key.lower(), op, value.strip()))
            return ""

        term = self.FILTER_RE.sub(repl, query_str).strip().lower()
        return SearchQuery(term, filters)


class ProjectSearchEngine:
    def __init__(self):
        self._parser = SearchParser()
        self._filter_methods: dict[str, Callable[[GodotProject, str, str], bool]] = {
            "engine": self._filter_by_engine,
            "tag": self._filter_by_tag,
            "modified": self._filter_by_modified,
            "favorite": self._filter_by_favorite,
            "favourite": self._filter_by_favorite,
        }
        self._current_favorites: set[str] = set()

    def _compare(self, val1: Any, op: str, val2: Any) -> bool:
        """Generic comparison function."""
        op_map = {
            "=": lambda a, b: a == b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            "<": lambda a, b: a < b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            ">=": lambda a, b: a >= b,
        }
        if op in op_map:
            try:
                return op_map[op](val1, val2)
            except (TypeError, ValueError):
                return False
        return False

    def _filter_by_engine(self, project: GodotProject, op: str, value: str) -> bool:
        """Filters by Godot engine version."""
        version_file = project.file_path.parent / ".godot-version"
        if not version_file.exists():
            return False

        try:
            project_version_str = version_file.read_text().strip()
            project_version = GodotVersion.parse(project_version_str)
            filter_version = GodotVersion.parse(value)
            return self._compare(project_version, op, filter_version)
        except Exception:
            return False

    def _filter_by_tag(self, project: GodotProject, op: str, value: str) -> bool:
        """Filters by project tags."""
        try:
            tags = project.tags
            if tags is None:
                tags = []
            value = value.lower()

            if op in ("=", "=="):
                return value in tags
            if op == "!=":
                return value not in tags
        except AttributeError:
            return False
        return False

    def _filter_by_modified(self, project: GodotProject, op: str, value: str) -> bool:
        """Filters by modification date in yy/mm/dd format."""
        try:
            filter_date = datetime.strptime(value, "%y/%m/%d").date()
            project_mtime = datetime.fromtimestamp(
                os.path.getmtime(project.file_path)
            ).date()
            return self._compare(project_mtime, op, filter_date)
        except (ValueError, OSError):
            return False

    def _filter_by_favorite(self, project: GodotProject, op: str, value: str) -> bool:
        """Filters by favorite status."""
        is_fav = str(project.file_path) in self._current_favorites
        target = value.lower() == "true"

        if op in ("=", "=="):
            return is_fav == target
        if op == "!=":
            return is_fav != target
        return False

    def _apply_filters(self, project: GodotProject, filters: list[Filter]) -> bool:
        """Checks if a project matches all provided filters."""
        for f in filters:
            filter_func = self._filter_methods.get(f.key)
            if not filter_func or not filter_func(project, f.op, f.value):
                return False
        return True

    def run(
        self,
        projects: list[GodotProject],
        query_str: str,
        favorites: set[str] | None = None,
    ) -> list[GodotProject]:
        """Filters a list of GodotProjects based on a search query."""
        self._current_favorites = favorites or set()
        query = self._parser.parse(query_str)

        results = []
        for project in projects:
            if query.term and query.term not in project.name.strip().lower():
                continue

            if not self._apply_filters(project, query.filters):
                continue

            results.append(project)

        return results
