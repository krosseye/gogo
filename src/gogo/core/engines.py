import logging
from collections.abc import Callable
from pathlib import Path

from godotkit.engine import (
    GodotAsset,
    GodotFetcher,
    GodotVersion,
    ReleaseNotFoundError,
    utils,
)

from gogo.core import paths

Progress = Callable[[str, int, int | None], None]

logger = logging.getLogger(__name__)


def fetcher() -> GodotFetcher:
    """A release fetcher that keeps its cache in gogo's cache folder."""
    return GodotFetcher(cache_dir=paths.cache_dir())


def list_installed() -> dict[str, Path]:
    """Installed versions, newest first, keyed by `str(version)`."""
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


def install_dir(version: GodotVersion) -> Path:
    """Where `version` is (or would be) installed."""
    return paths.versions_dir() / str(version)


def find_asset(version: GodotVersion) -> GodotAsset:
    """The download of `version` for this machine (network).

    Retries once with a fresh release list, for releases newer than the cache.

    Raises:
        ReleaseNotFoundError: If no release matches `version`.
        AssetNotFoundError: If the release has no build for this machine.
    """
    with fetcher() as f:
        try:
            return f.find_asset(version)
        except ReleaseNotFoundError:
            f.fetch_releases(stable_only=False, refresh_cache=True)
            return f.find_asset(version)


def install(
    version: GodotVersion,
    *,
    target: Path | None = None,
    overwrite: bool = False,
    progress: Progress | None = None,
    cancel: Callable[[], bool] | None = None,
) -> Path:
    """Download and install `version` for this machine; returns its folder.

    `target` overrides the folder; gogo doesn't track installs made there.

    `progress(phase, done, total)` and `cancel()` are passed to godotkit's
    `download_and_extract`.

    Raises:
        ReleaseNotFoundError, AssetNotFoundError: If there is no such download.
        FileExistsError: If it's installed and `overwrite` is False.
        DownloadCancelled: If `cancel()` returned True.
        DownloadError, ExtractError: If the download or extraction failed.
    """
    asset = find_asset(version)
    target = target or install_dir(version)
    utils.download_and_extract(
        asset.url,
        target,
        overwrite=overwrite,
        progress_callback=progress,
        cancel=cancel,
    )
    return target
