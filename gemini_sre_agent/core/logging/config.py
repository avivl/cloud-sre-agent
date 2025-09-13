"""Configuration management for the logging system."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .exceptions import ConfigurationError


class LogLevel(Enum):
    """Log levels for the logging system."""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


class LogFormat(Enum):
    """Log formats for the logging system."""

    TEXT = "text"
    JSON = "json"
    STRUCTURED = "structured"
    FLOW = "flow"


class OutputDestination(Enum):
    """Output destinations for logs."""

    CONSOLE = "console"
    FILE = "file"
    SYSLOG = "syslog"
    REMOTE = "remote"


@dataclass
class HandlerConfig:
    """Configuration for a log handler."""

    name: str
    destination: OutputDestination
    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.TEXT
    enabled: bool = True

    # File-specific settings
    file_path: str | None = None
    max_file_size_mb: int = 10
    backup_count: int = 5
    encoding: str = "utf-8"

    # Console-specific settings
    colorize: bool = True

    # Syslog-specific settings
    syslog_facility: str = "local0"
    syslog_address: str | None = None

    # Remote-specific settings
    remote_url: str | None = None
    remote_headers: dict[str, str] = field(default_factory=dict)
    remote_timeout: float = 5.0

    # Common settings
    buffer_size: int = 8192
    flush_interval: float = 1.0


@dataclass
class FlowTrackingConfig:
    """Configuration for flow tracking."""

    enabled: bool = True
    generate_flow_ids: bool = True
    track_duration: bool = True
    track_metadata: bool = True
    max_flow_depth: int = 10
    flow_id_format: str = "flow-{timestamp}-{random}"
    include_context: bool = True


@dataclass
class MetricsConfig:
    """Configuration for logging metrics."""

    enabled: bool = True
    collect_performance: bool = True
    collect_errors: bool = True
    collect_flows: bool = True
    metrics_interval: float = 60.0  # seconds
    max_metrics_history: int = 1000
    export_metrics: bool = False
    export_endpoint: str | None = None


@dataclass
class LoggingConfig:
    """Main configuration for the logging system."""

    # Basic settings
    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.STRUCTURED
    environment: str = "development"

    # Handlers
    handlers: list[HandlerConfig] = field(default_factory=list)

    # Flow tracking
    flow_tracking: FlowTrackingConfig = field(default_factory=FlowTrackingConfig)

    # Metrics
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    # Performance settings
    async_logging: bool = False
    max_queue_size: int = 10000
    flush_timeout: float = 5.0

    # Security settings
    sanitize_sensitive_data: bool = True
    sensitive_fields: list[str] = field(
        default_factory=lambda: ["password", "token", "key", "secret", "auth"]
    )

    # Context settings
    include_timestamp: bool = True
    include_logger_name: bool = True
    include_module: bool = True
    include_function: bool = True
    include_line_number: bool = True

    def validate(self) -> None:
        """Validate the logging configuration.

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        # Validate log level
        if not isinstance(self.level, LogLevel):
            raise ConfigurationError(
                f"Invalid log level: {self.level}",
                config_key="level",
                config_value=self.level,
            )

        # Validate log format
        if not isinstance(self.format, LogFormat):
            raise ConfigurationError(
                f"Invalid log format: {self.format}",
                config_key="format",
                config_value=self.format,
            )

        # Validate handlers
        if not self.handlers:
            raise ConfigurationError(
                "At least one handler must be configured", config_key="handlers"
            )

        for handler in self.handlers:
            self._validate_handler(handler)

        # Validate flow tracking
        if self.flow_tracking.enabled and self.flow_tracking.max_flow_depth <= 0:
            raise ConfigurationError(
                "max_flow_depth must be positive when flow tracking is enabled",
                config_key="flow_tracking.max_flow_depth",
                config_value=self.flow_tracking.max_flow_depth,
            )

        # Validate metrics
        if self.metrics.enabled and self.metrics.metrics_interval <= 0:
            raise ConfigurationError(
                "metrics_interval must be positive when metrics are enabled",
                config_key="metrics.metrics_interval",
                config_value=self.metrics.metrics_interval,
            )

        # Validate performance settings
        if self.max_queue_size <= 0:
            raise ConfigurationError(
                "max_queue_size must be positive",
                config_key="max_queue_size",
                config_value=self.max_queue_size,
            )

        if self.flush_timeout <= 0:
            raise ConfigurationError(
                "flush_timeout must be positive",
                config_key="flush_timeout",
                config_value=self.flush_timeout,
            )

    def _validate_handler(self, handler: HandlerConfig) -> None:
        """Validate a handler configuration.

        Args:
            handler: Handler configuration to validate

        Raises:
            ConfigurationError: If the handler configuration is invalid
        """
        if not handler.name:
            raise ConfigurationError(
                "Handler name cannot be empty", config_key="handler.name"
            )

        if not isinstance(handler.destination, OutputDestination):
            raise ConfigurationError(
                f"Invalid handler destination: {handler.destination}",
                config_key="handler.destination",
                config_value=handler.destination,
            )

        # Validate file handler
        if handler.destination == OutputDestination.FILE:
            if not handler.file_path:
                raise ConfigurationError(
                    "File path is required for file handler",
                    config_key="handler.file_path",
                )

            if handler.max_file_size_mb <= 0:
                raise ConfigurationError(
                    "max_file_size_mb must be positive",
                    config_key="handler.max_file_size_mb",
                    config_value=handler.max_file_size_mb,
                )

            if handler.backup_count < 0:
                raise ConfigurationError(
                    "backup_count must be non-negative",
                    config_key="handler.backup_count",
                    config_value=handler.backup_count,
                )

        # Validate remote handler
        if handler.destination == OutputDestination.REMOTE:
            if not handler.remote_url:
                raise ConfigurationError(
                    "Remote URL is required for remote handler",
                    config_key="handler.remote_url",
                )

            if handler.remote_timeout <= 0:
                raise ConfigurationError(
                    "remote_timeout must be positive",
                    config_key="handler.remote_timeout",
                    config_value=handler.remote_timeout,
                )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation of the configuration
        """
        return {
            "level": self.level.value,
            "format": self.format.value,
            "environment": self.environment,
            "handlers": [
                {
                    "name": h.name,
                    "destination": h.destination.value,
                    "level": h.level.value,
                    "format": h.format.value,
                    "enabled": h.enabled,
                    "file_path": h.file_path,
                    "max_file_size_mb": h.max_file_size_mb,
                    "backup_count": h.backup_count,
                    "encoding": h.encoding,
                    "colorize": h.colorize,
                    "syslog_facility": h.syslog_facility,
                    "syslog_address": h.syslog_address,
                    "remote_url": h.remote_url,
                    "remote_headers": h.remote_headers,
                    "remote_timeout": h.remote_timeout,
                    "buffer_size": h.buffer_size,
                    "flush_interval": h.flush_interval,
                }
                for h in self.handlers
            ],
            "flow_tracking": {
                "enabled": self.flow_tracking.enabled,
                "generate_flow_ids": self.flow_tracking.generate_flow_ids,
                "track_duration": self.flow_tracking.track_duration,
                "track_metadata": self.flow_tracking.track_metadata,
                "max_flow_depth": self.flow_tracking.max_flow_depth,
                "flow_id_format": self.flow_tracking.flow_id_format,
                "include_context": self.flow_tracking.include_context,
            },
            "metrics": {
                "enabled": self.metrics.enabled,
                "collect_performance": self.metrics.collect_performance,
                "collect_errors": self.metrics.collect_errors,
                "collect_flows": self.metrics.collect_flows,
                "metrics_interval": self.metrics.metrics_interval,
                "max_metrics_history": self.metrics.max_metrics_history,
                "export_metrics": self.metrics.export_metrics,
                "export_endpoint": self.metrics.export_endpoint,
            },
            "async_logging": self.async_logging,
            "max_queue_size": self.max_queue_size,
            "flush_timeout": self.flush_timeout,
            "sanitize_sensitive_data": self.sanitize_sensitive_data,
            "sensitive_fields": self.sensitive_fields,
            "include_timestamp": self.include_timestamp,
            "include_logger_name": self.include_logger_name,
            "include_module": self.include_module,
            "include_function": self.include_function,
            "include_line_number": self.include_line_number,
        }


class LoggingConfigManager:
    """Manager for logging configuration."""

    def __init__(self, config: LoggingConfig | None = None):
        """Initialize the configuration manager.

        Args:
            config: Optional initial configuration
        """
        self._config = config or self._create_default_config()
        self._config.validate()

    def _create_default_config(self) -> LoggingConfig:
        """Create default logging configuration.

        Returns:
            Default logging configuration
        """
        return LoggingConfig(
            handlers=[
                HandlerConfig(
                    name="console",
                    destination=OutputDestination.CONSOLE,
                    level=LogLevel.INFO,
                    format=LogFormat.STRUCTURED,
                    colorize=True,
                )
            ]
        )

    def get_config(self) -> LoggingConfig:
        """Get the current configuration.

        Returns:
            Current logging configuration
        """
        return self._config

    def update_config(self, config: LoggingConfig) -> None:
        """Update the configuration.

        Args:
            config: New configuration

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        config.validate()
        self._config = config

    def load_from_dict(self, config_dict: dict[str, Any]) -> None:
        """Load configuration from dictionary.

        Args:
            config_dict: Configuration dictionary

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        try:
            # Convert string values to enums
            if "level" in config_dict:
                config_dict["level"] = LogLevel(config_dict["level"])

            if "format" in config_dict:
                config_dict["format"] = LogFormat(config_dict["format"])

            # Convert handlers
            if "handlers" in config_dict:
                handlers = []
                for handler_dict in config_dict["handlers"]:
                    handler_dict = handler_dict.copy()
                    handler_dict["destination"] = OutputDestination(
                        handler_dict["destination"]
                    )
                    handler_dict["level"] = LogLevel(handler_dict["level"])
                    handler_dict["format"] = LogFormat(handler_dict["format"])
                    handlers.append(HandlerConfig(**handler_dict))
                config_dict["handlers"] = handlers

            # Convert flow tracking
            if "flow_tracking" in config_dict:
                config_dict["flow_tracking"] = FlowTrackingConfig(
                    **config_dict["flow_tracking"]
                )

            # Convert metrics
            if "metrics" in config_dict:
                config_dict["metrics"] = MetricsConfig(**config_dict["metrics"])

            config = LoggingConfig(**config_dict)
            self.update_config(config)

        except Exception as e:
            raise ConfigurationError(
                f"Failed to load configuration from dictionary: {e!s}",
                context={"config_dict": config_dict},
            ) from e

    def load_from_file(self, file_path: str | Path) -> None:
        """Load configuration from file.

        Args:
            file_path: Path to configuration file

        Raises:
            ConfigurationError: If the configuration file is invalid
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {file_path}",
                config_key="file_path",
                config_value=str(file_path),
            )

        try:
            import json

            with open(file_path, encoding="utf-8") as f:
                config_dict = json.load(f)

            self.load_from_dict(config_dict)

        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in configuration file: {e!s}",
                config_key="file_path",
                config_value=str(file_path),
            ) from e
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load configuration from file: {e!s}",
                config_key="file_path",
                config_value=str(file_path),
            ) from e

    def save_to_file(self, file_path: str | Path) -> None:
        """Save configuration to file.

        Args:
            file_path: Path to save configuration file

        Raises:
            ConfigurationError: If saving fails
        """
        file_path = Path(file_path)

        try:
            import json

            config_dict = self._config.to_dict()

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)

        except Exception as e:
            raise ConfigurationError(
                f"Failed to save configuration to file: {e!s}",
                config_key="file_path",
                config_value=str(file_path),
            ) from e
