import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from .constants import CATEGORY_EXTENSIONS, EXTENSION_TO_CATEGORY, FILENAME_TO_CATEGORY

StatsData = dict[str, dict[str, Any]]


class ProjectScanner(QThread):
    """Walks a project folder off the UI thread and totals file sizes per category."""

    scan_finished = Signal(dict)
    scan_progress = Signal(str)

    def __init__(self, root_path: Path):
        super().__init__()
        self._root_path = root_path

    def run(self) -> None:
        stats: StatsData = {
            str(cat): {"size": 0, "count": 0, "files": []}
            for cat in CATEGORY_EXTENSIONS
        }

        stats.update(
            {
                "Godot Data": {"size": 0, "count": 0, "files": []},
                "Git Data": {"size": 0, "count": 0, "files": []},
                "Other": {"size": 0, "count": 0, "files": []},
                "Total": {"size": 0, "count": 0, "files": []},
            }
        )

        if not os.path.exists(self._root_path):
            self.scan_finished.emit(stats)
            return

        for root, _, files in os.walk(self._root_path):
            rel_path = os.path.relpath(root, self._root_path)

            top_dir = rel_path.split(os.sep, 1)[0]
            is_git = top_dir == ".git"
            is_godot = top_dir in (".godot", ".import", ".mono")

            self.scan_progress.emit(f"Scanning: {os.path.basename(root)}")

            for filename in files:
                full_path = os.path.join(root, filename)
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    continue

                stats["Total"]["size"] += size
                stats["Total"]["count"] += 1

                category = self._categorize_file(filename, is_git, is_godot)

                if category in stats:
                    stats[category]["size"] += size
                    stats[category]["count"] += 1
                    stats[category]["files"].append((full_path, size))

        self.scan_finished.emit(stats)

    def _categorize_file(
        self, filename: str, is_git_dir: bool, is_godot_dir: bool
    ) -> str:
        """Category by folder first, then exact filename, then extension."""
        if is_git_dir:
            return "Git Data"

        if is_godot_dir:
            return "Godot Data"

        if filename in FILENAME_TO_CATEGORY:
            return FILENAME_TO_CATEGORY[filename]

        ext = os.path.splitext(filename)[1].lower()

        if ext in EXTENSION_TO_CATEGORY:
            return EXTENSION_TO_CATEGORY[ext]

        if ext in {".import", ".uid", ".remap", ".pck"}:
            return "Godot Data"

        return "Other"
