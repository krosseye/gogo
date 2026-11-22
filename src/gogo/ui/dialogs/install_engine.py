from collections.abc import Callable
from pathlib import Path

from godotkit.engine import GodotVersion, utils
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from gogo.core import engines
from gogo.ui.components.worker import Worker


class _InstallEvents(QObject):
    changed = Signal()


install_events = _InstallEvents()


def _progress_dialog(parent: QWidget, text: str) -> QProgressDialog:
    dialog = QProgressDialog(text, "Cancel", 0, 0, parent.window())
    dialog.setWindowTitle("Installing Godot")
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(0)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    return dialog


def install_engine(
    parent: QWidget, version: GodotVersion, on_done: Callable[[bool], None]
) -> None:
    """Download and install Godot `version` without blocking the UI.

    `on_done(installed)` runs afterwards; the caller's widget may already be
    gone by then, so nothing here touches `parent` after starting.
    """
    window = parent.window()
    title = version.display_name
    failure: list[str] = []
    dialog = _progress_dialog(window, f"Finding a download for Godot {title}...")

    def install(worker: Worker) -> None:
        engines.install(
            version,
            overwrite=True,
            progress=lambda phase, done, total: worker.progress.emit(
                phase, done, total or 0
            ),
            cancel=lambda: worker.cancelled,
        )

    def on_progress(phase: str, done: int, total: int) -> None:
        if worker.cancelled:
            return
        if phase == "extract":
            dialog.setCancelButton(None)  # type: ignore[arg-type]
            dialog.setMaximum(total)
            dialog.setValue(done)
            dialog.setLabelText(f"Extracting Godot {title}...")
            return
        mib = done / (1024 * 1024)
        if total:
            dialog.setMaximum(total)
            dialog.setValue(done)
            dialog.setLabelText(
                f"Downloading Godot {title}... "
                f"{mib:.1f} / {total / (1024 * 1024):.1f} MiB"
            )
        else:
            dialog.setLabelText(f"Downloading Godot {title}... {mib:.1f} MiB")

    def on_cancel() -> None:
        worker.cancelled = True
        dialog.show()
        dialog.setLabelText("Cancelling...")

    def on_finished() -> None:
        dialog.canceled.disconnect(on_cancel)
        dialog.close()
        dialog.deleteLater()
        if failure and not worker.cancelled:
            QMessageBox.critical(
                window,
                "Installation Failed",
                f"Couldn't install Godot {title}.\n\n{failure[0]}",
            )
        if not failure:
            install_events.changed.emit()
        on_done(not failure)

    worker = Worker(install, dialog)
    worker.progress.connect(on_progress)
    worker.failed.connect(failure.append)
    worker.finished.connect(on_finished)
    dialog.canceled.connect(on_cancel)
    dialog.show()
    worker.start()


def installed_binary(version: GodotVersion) -> Path | None:
    """Binary of an installed engine version, or None if it isn't installed."""
    directory = engines.list_installed().get(str(version))
    return utils.find_binary(directory) if directory else None
