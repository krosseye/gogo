import logging
import re
from datetime import datetime
from pathlib import Path

from godotkit.engine import utils

from gogo.core import paths

logger = logging.getLogger(__name__)

MAX_LOGS = 30


def list_logs() -> list[Path]:
    """Engine log files, newest first."""
    return sorted(paths.logs_dir().glob("*.log"), reverse=True)


def launch(binary: Path, label: str, project: Path | None = None) -> Path:
    """Start Godot detached (in the editor for `project`) and return its log file.

    Raises:
        OSError: If the engine cannot be started (`FileNotFoundError` if a file is missing).
    """
    logs_dir = paths.logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    safe_label = re.sub(r"[^\w.() -]+", "_", label).strip() or "godot"
    log_path = logs_dir / f"{datetime.now():%Y%m%d-%H%M%S} {safe_label}.log"
    utils.start(binary, project=project, output=log_path)
    _prune_logs()
    return log_path


def start_engine(binary: Path, version: str) -> Path:
    """Open the Godot project manager."""
    return launch(binary, f"Godot {version}")


def start_project(binary: Path, project_file: Path, name: str) -> Path:
    """Open a project in the Godot editor."""
    return launch(binary, name, project=project_file)


def _prune_logs() -> None:
    for old in list_logs()[MAX_LOGS:]:
        try:
            old.unlink()
        except OSError:
            pass
