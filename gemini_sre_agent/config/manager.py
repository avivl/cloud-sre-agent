# gemini_sre_agent/config/manager.py

"""
Central configuration manager with hot reloading and monitoring.
"""

import threading
import time
from typing import Any, Dict, Optional

from .app_config import AppConfig
from .errors import ConfigError
from .loader import ConfigLoader


class ConfigManager:
    """Central configuration manager with hot reloading."""

    def __init__(self, config_dir: str = "config"):
        self.loader = ConfigLoader(config_dir)
        self._config: Optional[AppConfig] = None
        self._lock = threading.RLock()
        self._last_modified: Optional[float] = None
        self._auto_reload = True
        self._reload_interval = 30  # seconds

    def get_config(self) -> AppConfig:
        """Get current configuration with auto-reload."""
        with self._lock:
            if self._should_reload():
                self._reload_config()
            if self._config is None:
                raise ConfigError("Configuration not loaded")
            return self._config

    def reload_config(self) -> AppConfig:
        """Manually reload configuration."""
        with self._lock:
            self._reload_config()
            if self._config is None:
                raise ConfigError("Configuration not loaded")
            return self._config

    def _should_reload(self) -> bool:
        """Check if configuration should be reloaded."""
        if not self._auto_reload or not self._config:
            return False

        # Check file modification times
        config_files = [
            self.loader.config_dir / "config.yaml",
            self.loader.config_dir / f"config.{self._config.environment}.yaml",
        ]

        for config_file in config_files:
            if config_file.exists():
                mtime = config_file.stat().st_mtime
                if self._last_modified is None or mtime > self._last_modified:
                    return True

        return False

    def _reload_config(self):
        """Reload configuration from files."""
        try:
            self._config = self.loader.load_config(AppConfig)
            self._last_modified = time.time()
        except Exception as e:
            # Log error but don't crash
            print(f"Failed to reload config: {e}")

    def set_auto_reload(self, enabled: bool):
        """Enable or disable automatic configuration reloading."""
        self._auto_reload = enabled

    def get_config_info(self) -> Dict[str, Any]:
        """Get information about the current configuration."""
        if not self._config:
            return {"status": "not_loaded"}

        return {
            "status": "loaded",
            "environment": self._config.environment,
            "schema_version": self._config.schema_version,
            "last_modified": self._last_modified,
            "auto_reload": self._auto_reload,
            "checksum": self._config.calculate_checksum(),
            "checksum_valid": self._config.validate_checksum(),
        }
