import shutil
from collections.abc import Callable
from pathlib import Path

from godotkit.engine import GodotFetcher, GodotVersion, utils
from godotkit.engine.release_fetcher import detect_architecture, detect_platform
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from gogo.core import paths
from gogo.ui.components.worker import Worker


class _InstallEvents(QObject):
    changed = Signal()


install_events = _InstallEvents()


def find_download_url(version: GodotVersion) -> str:
    """Look up the download URL of `version` for this machine (network; call off the UI thread)."""
    platform, arch = detect_platform(), detect_architecture()
    for release in GodotFetcher().fetch_releases(stable_only=False, platform_only=True):
        try:
            tag_version = GodotVersion.from_tag(release.version, version.csharp_enabled)
        except ValueError:
            continue
        if tag_version == version:
            asset = release.get_asset(platform, arch, version.csharp_enabled)
            if asset:
                return asset.url
    raise LookupError(f"No download of Godot {version} was found for this computer.")


def _progress_dialog(parent: QWidget, text: str) -> QProgressDialog:
    dialog = QProgressDialog(text, "Cancel", 0, 0, parent.window())
    dialog.setWindowTitle("Installing Godot")
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(0)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    return dialog


def install_engine(
    parent: QWidget,
    title: str,
    url: str | None,
    on_done: Callable[[bool], None],
    version: GodotVersion | None = None,
) -> None:
    """Download and install Godot `title` from `url` without blocking the UI.

    If `url` is None it is looked up for `version` first. `on_done(installed)`
    runs afterwards; the caller's widget may already be gone by then, so
    nothing here touches `parent` after starting.
    """
    window = parent.window()
    install_directory = paths.versions_dir() / title
    existed = install_directory.exists()
    failure: list[str] = []
    dialog = _progress_dialog(
        window, f"Finding a download for Godot {title}..." if url is None else ""
    )

    def install(worker: Worker) -> None:
        download_url = url or find_download_url(version)  # type: ignore[arg-type]

        def report(done: int, total: int | None) -> None:
            if worker.cancelled:
                raise InterruptedError  # aborts godotkit's download loop
            worker.progress.emit(done, total or 0)

        utils.download_and_extract(
            download_url, install_directory, overwrite=True, progress_callback=report
        )

    def on_progress(done: int, total: int) -> None:
        if worker.cancelled:
            return
        mib = done / (1024 * 1024)
        if not total:
            dialog.setLabelText(f"Downloading Godot {title}... {mib:.1f} MiB")
        elif done < total:
            dialog.setMaximum(total)
            dialog.setValue(done)
            dialog.setLabelText(
                f"Downloading Godot {title}... "
                f"{mib:.1f} / {total / (1024 * 1024):.1f} MiB"
            )
        else:
            dialog.setMaximum(0)
            dialog.setLabelText(f"Extracting Godot {title}...")
            dialog.setCancelButton(None)  # type: ignore[arg-type]

    def on_cancel() -> None:
        worker.cancelled = True
        dialog.show()
        dialog.setLabelText("Cancelling...")

    def on_finished() -> None:
        dialog.canceled.disconnect(on_cancel)
        dialog.close()
        dialog.deleteLater()
        if failure:
            if not existed and install_directory.is_dir():
                shutil.rmtree(install_directory, ignore_errors=True)
            if not worker.cancelled:
                QMessageBox.critical(
                    window,
                    "Installation Failed",
                    f"Could not install Godot {title}:\n\n{failure[0]}",
                )
        if not failure:
            install_events.changed.emit()
        on_done(not failure)

    if url is not None:
        dialog.setLabelText(f"Downloading Godot {title}...")
    worker = Worker(install, dialog)
    worker.progress.connect(on_progress)
    worker.failed.connect(failure.append)
    worker.finished.connect(on_finished)
    dialog.canceled.connect(on_cancel)
    dialog.show()
    worker.start()


def installed_binary(version: str) -> Path | None:
    """Binary of an installed engine version, or None if it isn't installed."""
    directory = paths.versions_dir() / version
    return utils.find_binary(directory) if directory.is_dir() else None
