import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from gogo.core import paths

logger = logging.getLogger(__name__)

PROJECT_FILE = "project.godot"
UNNAMED_PROJECT = "Unnamed Project"


@dataclass
class ProjectEntry:
    path: Path
    favourite: bool = False
    last_opened: float | None = None

    @property
    def project_file(self) -> Path:
        return self.path / PROJECT_FILE


def _folder(path: Path) -> Path:
    """Accept a project folder or its project.godot; return the resolved folder."""
    path = Path(path).resolve()
    return path.parent if path.name == PROJECT_FILE else path


def load() -> list[ProjectEntry]:
    file_path = paths.projects_file()
    if not file_path.exists():
        return []
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return [
            ProjectEntry(
                Path(d["path"]), bool(d.get("favourite")), d.get("last_opened")
            )
            for d in data
        ]
    except (ValueError, TypeError, KeyError) as e:
        backup = file_path.with_name(f"{file_path.name}.corrupt-{int(time.time())}")
        file_path.replace(backup)
        logger.error(
            "Project list %s is unreadable (%s); moved it to %s", file_path, e, backup
        )
        return []


def save(entries: list[ProjectEntry]) -> None:
    file_path = paths.projects_file()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    data = [{**asdict(e), "path": str(e.path)} for e in entries]
    tmp = file_path.with_name(file_path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=4), encoding="utf-8")
    os.replace(tmp, file_path)


def _find(entries: list[ProjectEntry], path: Path) -> ProjectEntry | None:
    folder = _folder(path)
    return next((e for e in entries if e.path == folder), None)


def add(path: Path) -> None:
    entries = load()
    if not _find(entries, path):
        save([*entries, ProjectEntry(_folder(path))])


def remove(path: Path) -> None:
    entries = load()
    if entry := _find(entries, path):
        entries.remove(entry)
        save(entries)


def is_favourite(path: Path) -> bool:
    entry = _find(load(), path)
    return bool(entry and entry.favourite)


def set_favourite(path: Path, favourite: bool) -> None:
    entries = load()
    if entry := _find(entries, path):
        entry.favourite = favourite
        save(entries)


def mark_opened(path: Path) -> None:
    entries = load()
    if entry := _find(entries, path):
        entry.last_opened = time.time()
        save(entries)
