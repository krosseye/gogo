import logging
from pathlib import Path

from godotkit.engine import GodotVersion

from gogo.core import paths

logger = logging.getLogger(__name__)


def list_installed() -> dict[str, Path]:
    """Installed versions, newest first, mapped to their install folders."""
    versions_dir = paths.versions_dir()
    if not versions_dir.is_dir():
        return {}

    versions = []
    try:
        for folder in versions_dir.iterdir():
            if not folder.is_dir():
                continue
            try:
                versions.append((GodotVersion.parse(folder.name), folder))
            except ValueError:
                logger.warning("Could not parse version from folder %r", folder.name)
    except OSError as e:
        logger.error("Error listing installed versions: %s", e)
        return {}

    versions.sort(key=lambda v: v[0], reverse=True)
    return {str(version): path for version, path in versions}


def get_default() -> Path | None:
    """The default engine's folder, or None if unset or no longer there."""
    default_file = paths.default_engine_file()
    if default_file.exists():
        engine_path_str = default_file.read_text().strip()
        if engine_path_str and Path(engine_path_str).is_dir():
            return Path(engine_path_str)
    return None


def set_default(engine_dir: Path) -> None:
    """Make `engine_dir` the default engine.

    Raises:
        ValueError: If `engine_dir` is not an existing directory.
    """
    if not engine_dir.is_dir():
        raise ValueError("Invalid engine directory")
    default_file = paths.default_engine_file()
    default_file.parent.mkdir(parents=True, exist_ok=True)
    default_file.write_text(str(engine_dir))
