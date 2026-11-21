import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from gogo.core import paths

logger = logging.getLogger(__name__)

MAX_LOGS = 30


def list_logs() -> list[Path]:
    """Engine log files, newest first."""
    return sorted(paths.logs_dir().glob("*.log"), reverse=True)


def launch(binary: Path, args: list[str], label: str, cwd: Path | None = None) -> Path:
    """Start `binary` detached and return the log file its output goes to.

    Raises:
        OSError: If the engine cannot be started.
    """
    logs_dir = paths.logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    safe_label = re.sub(r"[^\w.() -]+", "_", label).strip() or "godot"
    log_path = logs_dir / f"{datetime.now():%Y%m%d-%H%M%S} {safe_label}.log"

    if sys.platform == "win32":
        flags = {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
        }
    else:
        flags = {"start_new_session": True}

    with open(log_path, "wb") as log:
        subprocess.Popen(
            [str(binary), *args],
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            **flags,  # type: ignore[call-overload]
        )

    _prune_logs()
    return log_path


def start_engine(binary: Path, version: str) -> Path:
    """Open the Godot project manager."""
    return launch(binary, [], f"Godot {version}")


def start_project(binary: Path, project_file: Path, name: str) -> Path:
    """Open a project in the Godot editor."""
    return launch(binary, ["-e"], name, cwd=project_file.parent)


def _prune_logs() -> None:
    for old in list_logs()[MAX_LOGS:]:
        try:
            old.unlink()
        except OSError:
            pass
