import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths

logger = logging.getLogger(__name__)


class Config:
    config_path: Path | None
    user_config: dict[str, Any] | None

    def __init__(self) -> None:
        self.config_path = None
        self.user_config = None
        self.default_font_family = "Arial"

    @property
    def default_config(self) -> dict[str, Any]:
        return {
            "theme": "default",
            "font_family": self.default_font_family,
            "font_size": 9,
            "reduced_motion": False,
            "minimize_on_project_open": True,
            "close_on_project_open": False,
            "default_project_path": str(
                Path(
                    QStandardPaths.writableLocation(
                        QStandardPaths.StandardLocation.AppLocalDataLocation
                    )
                )
                .joinpath("projects")
                .resolve()
            ),
        }

    def has_config(self) -> bool:
        return self.config_path is not None and self.user_config is not None

    def set_config_file(self, config_file_path: str | Path):
        self.config_path = Path(config_file_path)
        self.user_config = self._load_user_config()

    def _load_user_config(self) -> dict[str, Any]:
        """Load user config if exists, otherwise return empty dict"""
        if self.config_path is None:
            # This shouldn't happen if set_config_file is called correctly
            return {}

        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning(
                    "Corrupted config file at %s; using defaults.", self.config_path
                )
                return {}

        return {}

    def get(self, key: str) -> Any:
        """Get a config value, falling back to default if not in user config"""
        if self.user_config is None:
            raise RuntimeError("Config file not set. Call set_config_file first.")

        return self.user_config.get(key, self.default_config.get(key))

    def set(self, key: str, value: Any):
        """Set a user config value"""
        if self.user_config is None:
            raise RuntimeError("Config file not set. Call set_config_file first.")

        self.user_config[key] = value

    def save(self):
        """Save user config to file"""
        if self.config_path is None or self.user_config is None:
            raise RuntimeError(
                "Config file path or user config not set. Call set_config_file first."
            )

        self.config_path.parent.mkdir(parents=True, exist_ok=True)  # first run
        with open(self.config_path, "w") as f:
            json.dump(self.user_config, f, indent=4)

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any):
        self.set(key, value)

    def copy(self) -> dict[str, Any]:
        """Return a full config dict combining defaults with user overrides"""
        combined = self.default_config.copy()

        if self.user_config is None:
            return combined

        combined.update(self.user_config)
        return combined


config = Config()
