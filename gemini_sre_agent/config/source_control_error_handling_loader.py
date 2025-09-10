# gemini_sre_agent/config/source_control_error_handling_loader.py

"""
Configuration loader for source control error handling.

This module provides utilities to load and validate error handling configurations
from various sources (YAML, JSON, environment variables).
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from .source_control_error_handling import ErrorHandlingConfig
from .source_control_error_handling_validation import ErrorHandlingConfigValidator


class ErrorHandlingConfigLoader:
    """Loader for error handling configuration."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the configuration loader."""
        self.logger = logger or logging.getLogger(__name__)
        self.validator = ErrorHandlingConfigValidator(logger)

    def load_from_file(self, file_path: Union[str, Path]) -> ErrorHandlingConfig:
        """Load error handling configuration from a file."""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        if file_path.suffix.lower() not in [".yaml", ".yml", ".json"]:
            raise ValueError(
                f"Unsupported configuration file format: {file_path.suffix}"
            )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                if file_path.suffix.lower() in [".yaml", ".yml"]:
                    config_data = yaml.safe_load(f)
                else:  # JSON
                    import json

                    config_data = json.load(f)

            return self._load_from_dict(config_data)

        except Exception as e:
            self.logger.error(f"Failed to load configuration from {file_path}: {e}")
            raise

    def load_from_dict(self, config_data: Dict[str, Any]) -> ErrorHandlingConfig:
        """Load error handling configuration from a dictionary."""
        return self._load_from_dict(config_data)

    def load_from_env(self, prefix: str = "ERROR_HANDLING_") -> ErrorHandlingConfig:
        """Load error handling configuration from environment variables."""
        config_data = {}

        # Load basic settings
        config_data["enabled"] = os.getenv(f"{prefix}ENABLED", "true").lower() == "true"

        # Load circuit breaker settings
        config_data["circuit_breaker"] = self._load_circuit_breaker_from_env(prefix)

        # Load retry settings
        config_data["retry"] = self._load_retry_from_env(prefix)

        # Load graceful degradation settings
        config_data["graceful_degradation"] = self._load_graceful_degradation_from_env(
            prefix
        )

        # Load health check settings
        config_data["health_checks"] = self._load_health_checks_from_env(prefix)

        # Load metrics settings
        config_data["metrics"] = self._load_metrics_from_env(prefix)

        return self._load_from_dict(config_data)

    def load_default(self) -> ErrorHandlingConfig:
        """Load default error handling configuration."""
        return ErrorHandlingConfig()

    def load_with_validation(self, config_data: Dict[str, Any]) -> ErrorHandlingConfig:
        """Load configuration with validation and return any issues found."""
        config = self._load_from_dict(config_data)
        issues = self.validator.validate_config(config)

        if issues:
            self.logger.warning(f"Configuration validation found {len(issues)} issues:")
            for issue in issues:
                self.logger.warning(f"  - {issue}")

        return config

    def _load_from_dict(self, config_data: Dict[str, Any]) -> ErrorHandlingConfig:
        """Internal method to load configuration from dictionary."""
        # Extract error handling configuration
        error_handling_data = config_data.get("error_handling", {})

        # If error_handling is not present, use the entire config_data
        if not error_handling_data:
            error_handling_data = config_data

        return ErrorHandlingConfig(**error_handling_data)

    def _load_circuit_breaker_from_env(self, prefix: str) -> Dict[str, Any]:
        """Load circuit breaker configuration from environment variables."""
        cb_config = {}

        # Default circuit breaker settings
        cb_config["default"] = {
            "failure_threshold": int(
                os.getenv(f"{prefix}CB_DEFAULT_FAILURE_THRESHOLD", "5")
            ),
            "recovery_timeout": float(
                os.getenv(f"{prefix}CB_DEFAULT_RECOVERY_TIMEOUT", "60.0")
            ),
            "success_threshold": int(
                os.getenv(f"{prefix}CB_DEFAULT_SUCCESS_THRESHOLD", "3")
            ),
            "timeout": float(os.getenv(f"{prefix}CB_DEFAULT_TIMEOUT", "30.0")),
        }

        # File operations
        cb_config["file_operations"] = {
            "failure_threshold": int(
                os.getenv(f"{prefix}CB_FILE_FAILURE_THRESHOLD", "10")
            ),
            "recovery_timeout": float(
                os.getenv(f"{prefix}CB_FILE_RECOVERY_TIMEOUT", "30.0")
            ),
            "success_threshold": int(
                os.getenv(f"{prefix}CB_FILE_SUCCESS_THRESHOLD", "2")
            ),
            "timeout": float(os.getenv(f"{prefix}CB_FILE_TIMEOUT", "60.0")),
        }

        # Branch operations
        cb_config["branch_operations"] = {
            "failure_threshold": int(
                os.getenv(f"{prefix}CB_BRANCH_FAILURE_THRESHOLD", "5")
            ),
            "recovery_timeout": float(
                os.getenv(f"{prefix}CB_BRANCH_RECOVERY_TIMEOUT", "45.0")
            ),
            "success_threshold": int(
                os.getenv(f"{prefix}CB_BRANCH_SUCCESS_THRESHOLD", "3")
            ),
            "timeout": float(os.getenv(f"{prefix}CB_BRANCH_TIMEOUT", "45.0")),
        }

        # Pull request operations
        cb_config["pull_request_operations"] = {
            "failure_threshold": int(
                os.getenv(f"{prefix}CB_PR_FAILURE_THRESHOLD", "5")
            ),
            "recovery_timeout": float(
                os.getenv(f"{prefix}CB_PR_RECOVERY_TIMEOUT", "90.0")
            ),
            "success_threshold": int(
                os.getenv(f"{prefix}CB_PR_SUCCESS_THRESHOLD", "3")
            ),
            "timeout": float(os.getenv(f"{prefix}CB_PR_TIMEOUT", "30.0")),
        }

        # Batch operations
        cb_config["batch_operations"] = {
            "failure_threshold": int(
                os.getenv(f"{prefix}CB_BATCH_FAILURE_THRESHOLD", "15")
            ),
            "recovery_timeout": float(
                os.getenv(f"{prefix}CB_BATCH_RECOVERY_TIMEOUT", "20.0")
            ),
            "success_threshold": int(
                os.getenv(f"{prefix}CB_BATCH_SUCCESS_THRESHOLD", "2")
            ),
            "timeout": float(os.getenv(f"{prefix}CB_BATCH_TIMEOUT", "120.0")),
        }

        # Auth operations
        cb_config["auth_operations"] = {
            "failure_threshold": int(
                os.getenv(f"{prefix}CB_AUTH_FAILURE_THRESHOLD", "10")
            ),
            "recovery_timeout": float(
                os.getenv(f"{prefix}CB_AUTH_RECOVERY_TIMEOUT", "300.0")
            ),
            "success_threshold": int(
                os.getenv(f"{prefix}CB_AUTH_SUCCESS_THRESHOLD", "5")
            ),
            "timeout": float(os.getenv(f"{prefix}CB_AUTH_TIMEOUT", "15.0")),
        }

        return cb_config

    def _load_retry_from_env(self, prefix: str) -> Dict[str, Any]:
        """Load retry configuration from environment variables."""
        return {
            "max_retries": int(os.getenv(f"{prefix}RETRY_MAX_RETRIES", "3")),
            "base_delay": float(os.getenv(f"{prefix}RETRY_BASE_DELAY", "1.0")),
            "max_delay": float(os.getenv(f"{prefix}RETRY_MAX_DELAY", "60.0")),
            "backoff_factor": float(os.getenv(f"{prefix}RETRY_BACKOFF_FACTOR", "2.0")),
            "jitter": os.getenv(f"{prefix}RETRY_JITTER", "true").lower() == "true",
        }

    def _load_graceful_degradation_from_env(self, prefix: str) -> Dict[str, Any]:
        """Load graceful degradation configuration from environment variables."""
        strategies_str = os.getenv(
            f"{prefix}GD_FALLBACK_STRATEGIES",
            "cached_response,simplified_operation,offline_mode",
        )
        strategies = [s.strip() for s in strategies_str.split(",")]

        return {
            "enabled": os.getenv(f"{prefix}GD_ENABLED", "true").lower() == "true",
            "fallback_strategies": strategies,
            "cache_ttl": float(os.getenv(f"{prefix}GD_CACHE_TTL", "300.0")),
            "simplified_operation_timeout": float(
                os.getenv(f"{prefix}GD_SIMPLIFIED_TIMEOUT", "10.0")
            ),
            "offline_mode_enabled": os.getenv(
                f"{prefix}GD_OFFLINE_MODE", "true"
            ).lower()
            == "true",
        }

    def _load_health_checks_from_env(self, prefix: str) -> Dict[str, Any]:
        """Load health check configuration from environment variables."""
        return {
            "enabled": os.getenv(f"{prefix}HC_ENABLED", "true").lower() == "true",
            "check_interval": float(os.getenv(f"{prefix}HC_CHECK_INTERVAL", "30.0")),
            "timeout": float(os.getenv(f"{prefix}HC_TIMEOUT", "10.0")),
            "failure_threshold": int(os.getenv(f"{prefix}HC_FAILURE_THRESHOLD", "3")),
            "success_threshold": int(os.getenv(f"{prefix}HC_SUCCESS_THRESHOLD", "2")),
            "metrics_retention_hours": int(
                os.getenv(f"{prefix}HC_METRICS_RETENTION", "24")
            ),
        }

    def _load_metrics_from_env(self, prefix: str) -> Dict[str, Any]:
        """Load metrics configuration from environment variables."""
        return {
            "enabled": os.getenv(f"{prefix}METRICS_ENABLED", "true").lower() == "true",
            "collection_interval": float(
                os.getenv(f"{prefix}METRICS_COLLECTION_INTERVAL", "60.0")
            ),
            "retention_hours": int(
                os.getenv(f"{prefix}METRICS_RETENTION_HOURS", "168")
            ),
            "max_series": int(os.getenv(f"{prefix}METRICS_MAX_SERIES", "1000")),
            "max_points_per_series": int(
                os.getenv(f"{prefix}METRICS_MAX_POINTS_PER_SERIES", "10000")
            ),
            "background_processing": os.getenv(
                f"{prefix}METRICS_BACKGROUND_PROCESSING", "true"
            ).lower()
            == "true",
        }

    def save_to_file(
        self, config: ErrorHandlingConfig, file_path: Union[str, Path]
    ) -> None:
        """Save error handling configuration to a file."""
        file_path = Path(file_path)

        # Convert config to dictionary with proper serialization
        config_dict = config.model_dump(mode="json")

        # Create directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                if file_path.suffix.lower() in [".yaml", ".yml"]:
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
                else:  # JSON
                    import json

                    json.dump(config_dict, f, indent=2)

            self.logger.info(f"Configuration saved to {file_path}")

        except Exception as e:
            self.logger.error(f"Failed to save configuration to {file_path}: {e}")
            raise

    def get_configuration_summary(self, config: ErrorHandlingConfig) -> Dict[str, Any]:
        """Get a summary of the configuration for logging/debugging."""
        return {
            "enabled": config.enabled,
            "circuit_breaker_operations": len(config.circuit_breaker.__dict__),
            "retry_max_retries": config.retry.max_retries,
            "graceful_degradation_enabled": config.graceful_degradation.enabled,
            "health_checks_enabled": config.health_checks.enabled,
            "metrics_enabled": config.metrics.enabled,
            "provider_overrides": list(config.provider_overrides.keys()),
        }
