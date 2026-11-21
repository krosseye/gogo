from pathlib import Path

from PySide6.QtCore import QStandardPaths

RESOURCE_DIR = Path(__file__).resolve().parent.parent / "resources"


def construct_path(parts: list[str]) -> str:
    """Return the absolute path of a file inside the bundled resources folder."""
    return str(RESOURCE_DIR.joinpath(*parts))


def data_dir() -> Path:
    """The per-user data folder (depends on the app/org name set at startup)."""
    location = QStandardPaths.StandardLocation.AppLocalDataLocation
    return Path(QStandardPaths.writableLocation(location)).resolve()


def cache_dir() -> Path:
    return data_dir() / "cache"


def versions_dir() -> Path:
    """Installed engines, one folder per version."""
    return data_dir() / "versions"


def logs_dir() -> Path:
    """Per-launch engine logs."""
    return data_dir() / "logs"


def projects_file() -> Path:
    return data_dir() / "projects.json"


def default_engine_file() -> Path:
    return data_dir() / "default_engine.txt"
