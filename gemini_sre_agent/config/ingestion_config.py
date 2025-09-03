"""
Configuration management for the log ingestion system.

This module provides configuration classes and validation for the new
pluggable log ingestion architecture.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from ..config.errors import ConfigError

logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    """Supported log source types."""

    GCP_PUBSUB = "gcp_pubsub"
    GCP_LOGGING = "gcp_logging"
    FILE_SYSTEM = "file_system"
    AWS_CLOUDWATCH = "aws_cloudwatch"
    KUBERNETES = "kubernetes"
    SYSLOG = "syslog"


class BufferStrategy(str, Enum):
    """Buffer strategy options."""

    DIRECT = "direct"  # No buffering, direct processing
    MEMORY = "memory"  # In-memory queue/buffer
    EXTERNAL = "external"  # External message broker


class HealthCheckStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class SourceConfig:
    """Base configuration for a log source."""

    name: str
    type: SourceType
    enabled: bool = True
    priority: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    circuit_breaker_enabled: bool = True
    rate_limit_per_second: Optional[int] = None
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GCPPubSubConfig(SourceConfig):
    """Configuration for GCP Pub/Sub source."""

    credentials_path: Optional[str] = None
    max_messages: int = 100
    ack_deadline_seconds: int = 60
    flow_control_max_messages: int = 1000
    flow_control_max_bytes: int = 10 * 1024 * 1024  # 10MB
    project_id: str = ""
    subscription_id: str = ""

    def __post_init__(self):
        self.type = SourceType.GCP_PUBSUB
        self.config = {
            "project_id": self.project_id,
            "subscription_id": self.subscription_id,
            "credentials_path": self.credentials_path,
            "max_messages": self.max_messages,
            "ack_deadline_seconds": self.ack_deadline_seconds,
            "flow_control_max_messages": self.flow_control_max_messages,
            "flow_control_max_bytes": self.flow_control_max_bytes,
        }


@dataclass
class GCPLoggingConfig(SourceConfig):
    """Configuration for GCP Logging source."""

    log_filter: str = "severity>=ERROR"
    credentials_path: Optional[str] = None
    poll_interval: int = 30
    max_results: int = 1000
    project_id: str = ""

    def __post_init__(self):
        self.type = SourceType.GCP_LOGGING
        self.config = {
            "project_id": self.project_id,
            "log_filter": self.log_filter,
            "credentials_path": self.credentials_path,
            "poll_interval": self.poll_interval,
            "max_results": self.max_results,
        }


@dataclass
class FileSystemConfig(SourceConfig):
    """Configuration for file system source."""

    file_pattern: str = "*.log"
    watch_mode: bool = True
    encoding: str = "utf-8"
    buffer_size: int = 1000
    max_memory_mb: int = 100
    file_path: str = ""

    def __post_init__(self):
        self.type = SourceType.FILE_SYSTEM
        self.config = {
            "file_path": self.file_path,
            "file_pattern": self.file_pattern,
            "watch_mode": self.watch_mode,
            "encoding": self.encoding,
            "buffer_size": self.buffer_size,
            "max_memory_mb": self.max_memory_mb,
        }


@dataclass
class AWSCloudWatchConfig(SourceConfig):
    """Configuration for AWS CloudWatch source."""

    log_stream_name: Optional[str] = None
    region: str = "us-east-1"
    credentials_profile: Optional[str] = None
    poll_interval: int = 30
    max_events: int = 1000
    log_group_name: str = ""

    def __post_init__(self):
        self.type = SourceType.AWS_CLOUDWATCH
        self.config = {
            "log_group_name": self.log_group_name,
            "log_stream_name": self.log_stream_name,
            "region": self.region,
            "credentials_profile": self.credentials_profile,
            "poll_interval": self.poll_interval,
            "max_events": self.max_events,
        }


@dataclass
class KubernetesConfig(SourceConfig):
    """Configuration for Kubernetes source."""

    namespace: Optional[str] = None
    label_selector: Optional[str] = None
    container_name: Optional[str] = None
    kubeconfig_path: Optional[str] = None
    poll_interval: int = 30
    max_logs: int = 1000

    def __post_init__(self):
        self.type = SourceType.KUBERNETES
        self.config = {
            "namespace": self.namespace,
            "label_selector": self.label_selector,
            "container_name": self.container_name,
            "kubeconfig_path": self.kubeconfig_path,
            "poll_interval": self.poll_interval,
            "max_logs": self.max_logs,
        }


@dataclass
class SyslogConfig(SourceConfig):
    """Configuration for Syslog source."""

    host: str = "localhost"
    port: int = 514
    protocol: str = "udp"  # udp or tcp
    facility: int = 16  # local0
    severity: int = 6  # info

    def __post_init__(self):
        self.type = SourceType.SYSLOG
        self.config = {
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "facility": self.facility,
            "severity": self.severity,
        }


@dataclass
class GlobalConfig:
    """Global configuration for the ingestion system."""

    max_throughput: int = 500  # logs per second
    error_threshold: float = 0.05  # 5% error rate threshold
    enable_metrics: bool = True
    enable_health_checks: bool = True
    health_check_interval: int = 30  # seconds
    max_message_length: int = 10000  # characters
    enable_pii_detection: bool = True
    enable_flow_tracking: bool = True
    default_buffer_size: int = 1000
    max_memory_mb: int = 500
    backpressure_threshold: float = 0.8  # 80% buffer usage
    drop_oldest_on_full: bool = True
    buffer_strategy: BufferStrategy = BufferStrategy.MEMORY


@dataclass
class IngestionConfig:
    """Complete configuration for the log ingestion system."""

    sources: List[SourceConfig] = field(default_factory=list)
    global_config: GlobalConfig = field(default_factory=GlobalConfig)
    schema_version: str = "1.0.0"

    def validate(self) -> List[str]:
        """Validate the configuration and return any errors."""
        errors = []

        # Check for duplicate source names
        source_names = [source.name for source in self.sources]
        if len(source_names) != len(set(source_names)):
            errors.append("Duplicate source names found")

        # Validate each source
        for source in self.sources:
            if not source.name:
                errors.append("Source name cannot be empty")

            if source.priority < 1 or source.priority > 100:
                errors.append(
                    f"Source '{source.name}' priority must be between 1 and 100"
                )

            if source.max_retries < 0:
                errors.append(
                    f"Source '{source.name}' max_retries must be non-negative"
                )

            if source.retry_delay < 0:
                errors.append(
                    f"Source '{source.name}' retry_delay must be non-negative"
                )

            if source.timeout <= 0:
                errors.append(f"Source '{source.name}' timeout must be positive")

        # Validate global config
        if self.global_config.max_throughput <= 0:
            errors.append("Global max_throughput must be positive")

        if not 0 <= self.global_config.error_threshold <= 1:
            errors.append("Global error_threshold must be between 0 and 1")

        if self.global_config.health_check_interval <= 0:
            errors.append("Global health_check_interval must be positive")

        if self.global_config.max_message_length <= 0:
            errors.append("Global max_message_length must be positive")

        if self.global_config.default_buffer_size <= 0:
            errors.append("Global default_buffer_size must be positive")

        if self.global_config.max_memory_mb <= 0:
            errors.append("Global max_memory_mb must be positive")

        if not 0 <= self.global_config.backpressure_threshold <= 1:
            errors.append("Global backpressure_threshold must be between 0 and 1")

        return errors

    def get_source_by_name(self, name: str) -> Optional[SourceConfig]:
        """Get a source configuration by name."""
        for source in self.sources:
            if source.name == name:
                return source
        return None

    def get_enabled_sources(self) -> List[SourceConfig]:
        """Get all enabled sources sorted by priority."""
        enabled = [source for source in self.sources if source.enabled]
        return sorted(enabled, key=lambda x: x.priority)


class IngestionConfigManager:
    """Manager for ingestion configuration loading and validation."""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """Initialize the config manager."""
        self.config_path = Path(config_path) if config_path else None
        self._config: Optional[IngestionConfig] = None

    def load_config(
        self, config_path: Optional[Union[str, Path]] = None
    ) -> IngestionConfig:
        """Load configuration from file."""
        if config_path:
            self.config_path = Path(config_path)

        if not self.config_path or not self.config_path.exists():
            raise ConfigError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, "r") as f:
                if self.config_path.suffix.lower() in [".yaml", ".yml"]:
                    data = yaml.safe_load(f)
                elif self.config_path.suffix.lower() == ".json":
                    data = json.load(f)
                else:
                    raise ConfigError(
                        f"Unsupported config file format: {self.config_path.suffix}"
                    )

            self._config = self._parse_config(data)
            return self._config

        except Exception as e:
            raise ConfigError(f"Failed to load configuration: {e}") from e

    def _parse_config(self, data: Dict[str, Any]) -> IngestionConfig:
        """Parse configuration data into IngestionConfig object."""
        # Parse global config
        global_data = data.get("global_config", {})
        global_config = GlobalConfig(
            max_throughput=global_data.get("max_throughput", 500),
            error_threshold=global_data.get("error_threshold", 0.05),
            enable_metrics=global_data.get("enable_metrics", True),
            enable_health_checks=global_data.get("enable_health_checks", True),
            health_check_interval=global_data.get("health_check_interval", 30),
            max_message_length=global_data.get("max_message_length", 10000),
            enable_pii_detection=global_data.get("enable_pii_detection", True),
            enable_flow_tracking=global_data.get("enable_flow_tracking", True),
            default_buffer_size=global_data.get("default_buffer_size", 1000),
            max_memory_mb=global_data.get("max_memory_mb", 500),
            backpressure_threshold=global_data.get("backpressure_threshold", 0.8),
            drop_oldest_on_full=global_data.get("drop_oldest_on_full", True),
            buffer_strategy=BufferStrategy(
                global_data.get("buffer_strategy", "memory")
            ),
        )

        # Parse sources
        sources = []
        for source_data in data.get("sources", []):
            source_type = SourceType(source_data["type"])
            source_config = source_data.get("config", {})

            if source_type == SourceType.GCP_PUBSUB:
                source = GCPPubSubConfig(
                    name=source_data["name"],
                    type=source_type,
                    project_id=source_config["project_id"],
                    subscription_id=source_config["subscription_id"],
                    credentials_path=source_config.get("credentials_path"),
                    max_messages=source_config.get("max_messages", 100),
                    ack_deadline_seconds=source_config.get("ack_deadline_seconds", 60),
                    flow_control_max_messages=source_config.get(
                        "flow_control_max_messages", 1000
                    ),
                    flow_control_max_bytes=source_config.get(
                        "flow_control_max_bytes", 10 * 1024 * 1024
                    ),
                    enabled=source_data.get("enabled", True),
                    priority=source_data.get("priority", 10),
                    max_retries=source_data.get("max_retries", 3),
                    retry_delay=source_data.get("retry_delay", 1.0),
                    timeout=source_data.get("timeout", 30.0),
                    circuit_breaker_enabled=source_data.get(
                        "circuit_breaker_enabled", True
                    ),
                    rate_limit_per_second=source_data.get("rate_limit_per_second"),
                )
            elif source_type == SourceType.GCP_LOGGING:
                source = GCPLoggingConfig(
                    name=source_data["name"],
                    type=source_type,
                    project_id=source_config["project_id"],
                    log_filter=source_config.get("log_filter", "severity>=ERROR"),
                    credentials_path=source_config.get("credentials_path"),
                    poll_interval=source_config.get("poll_interval", 30),
                    max_results=source_config.get("max_results", 1000),
                    enabled=source_data.get("enabled", True),
                    priority=source_data.get("priority", 10),
                    max_retries=source_data.get("max_retries", 3),
                    retry_delay=source_data.get("retry_delay", 1.0),
                    timeout=source_data.get("timeout", 30.0),
                    circuit_breaker_enabled=source_data.get(
                        "circuit_breaker_enabled", True
                    ),
                    rate_limit_per_second=source_data.get("rate_limit_per_second"),
                )
            elif source_type == SourceType.FILE_SYSTEM:
                source = FileSystemConfig(
                    name=source_data["name"],
                    type=source_type,
                    file_path=source_config["file_path"],
                    file_pattern=source_config.get("file_pattern", "*.log"),
                    watch_mode=source_config.get("watch_mode", True),
                    encoding=source_config.get("encoding", "utf-8"),
                    buffer_size=source_config.get("buffer_size", 1000),
                    max_memory_mb=source_config.get("max_memory_mb", 100),
                    enabled=source_data.get("enabled", True),
                    priority=source_data.get("priority", 10),
                    max_retries=source_data.get("max_retries", 3),
                    retry_delay=source_data.get("retry_delay", 1.0),
                    timeout=source_data.get("timeout", 30.0),
                    circuit_breaker_enabled=source_data.get(
                        "circuit_breaker_enabled", True
                    ),
                    rate_limit_per_second=source_data.get("rate_limit_per_second"),
                )
            elif source_type == SourceType.AWS_CLOUDWATCH:
                source = AWSCloudWatchConfig(
                    name=source_data["name"],
                    type=source_type,
                    log_group_name=source_config["log_group_name"],
                    log_stream_name=source_config.get("log_stream_name"),
                    region=source_config.get("region", "us-east-1"),
                    credentials_profile=source_config.get("credentials_profile"),
                    poll_interval=source_config.get("poll_interval", 30),
                    max_events=source_config.get("max_events", 1000),
                    enabled=source_data.get("enabled", True),
                    priority=source_data.get("priority", 10),
                    max_retries=source_data.get("max_retries", 3),
                    retry_delay=source_data.get("retry_delay", 1.0),
                    timeout=source_data.get("timeout", 30.0),
                    circuit_breaker_enabled=source_data.get(
                        "circuit_breaker_enabled", True
                    ),
                    rate_limit_per_second=source_data.get("rate_limit_per_second"),
                )
            elif source_type == SourceType.KUBERNETES:
                source = KubernetesConfig(
                    name=source_data["name"],
                    type=source_type,
                    namespace=source_config.get("namespace"),
                    label_selector=source_config.get("label_selector"),
                    container_name=source_config.get("container_name"),
                    kubeconfig_path=source_config.get("kubeconfig_path"),
                    poll_interval=source_config.get("poll_interval", 30),
                    max_logs=source_config.get("max_logs", 1000),
                    enabled=source_data.get("enabled", True),
                    priority=source_data.get("priority", 10),
                    max_retries=source_data.get("max_retries", 3),
                    retry_delay=source_data.get("retry_delay", 1.0),
                    timeout=source_data.get("timeout", 30.0),
                    circuit_breaker_enabled=source_data.get(
                        "circuit_breaker_enabled", True
                    ),
                    rate_limit_per_second=source_data.get("rate_limit_per_second"),
                )
            elif source_type == SourceType.SYSLOG:
                source = SyslogConfig(
                    name=source_data["name"],
                    type=source_type,
                    host=source_config.get("host", "localhost"),
                    port=source_config.get("port", 514),
                    protocol=source_config.get("protocol", "udp"),
                    facility=source_config.get("facility", 16),
                    severity=source_config.get("severity", 6),
                    enabled=source_data.get("enabled", True),
                    priority=source_data.get("priority", 10),
                    max_retries=source_data.get("max_retries", 3),
                    retry_delay=source_data.get("retry_delay", 1.0),
                    timeout=source_data.get("timeout", 30.0),
                    circuit_breaker_enabled=source_data.get(
                        "circuit_breaker_enabled", True
                    ),
                    rate_limit_per_second=source_data.get("rate_limit_per_second"),
                )
            else:
                raise ConfigError(f"Unsupported source type: {source_type}")

            sources.append(source)

        return IngestionConfig(
            sources=sources,
            global_config=global_config,
            schema_version=data.get("schema_version", "1.0.0"),
        )

    def validate_config(self) -> List[str]:
        """Validate the current configuration."""
        if not self._config:
            return ["No configuration loaded"]
        return self._config.validate()

    def save_config(
        self, config: IngestionConfig, output_path: Union[str, Path]
    ) -> None:
        """Save configuration to file."""
        output_path = Path(output_path)

        # Convert config to dictionary
        data = {
            "schema_version": config.schema_version,
            "global_config": {
                "max_throughput": config.global_config.max_throughput,
                "error_threshold": config.global_config.error_threshold,
                "enable_metrics": config.global_config.enable_metrics,
                "enable_health_checks": config.global_config.enable_health_checks,
                "health_check_interval": config.global_config.health_check_interval,
                "max_message_length": config.global_config.max_message_length,
                "enable_pii_detection": config.global_config.enable_pii_detection,
                "enable_flow_tracking": config.global_config.enable_flow_tracking,
                "default_buffer_size": config.global_config.default_buffer_size,
                "max_memory_mb": config.global_config.max_memory_mb,
                "backpressure_threshold": config.global_config.backpressure_threshold,
                "drop_oldest_on_full": config.global_config.drop_oldest_on_full,
                "buffer_strategy": config.global_config.buffer_strategy.value,
            },
            "sources": [],
        }

        for source in config.sources:
            source_data = {
                "name": source.name,
                "type": source.type.value,
                "enabled": source.enabled,
                "priority": source.priority,
                "max_retries": source.max_retries,
                "retry_delay": source.retry_delay,
                "timeout": source.timeout,
                "circuit_breaker_enabled": source.circuit_breaker_enabled,
                "config": source.config,
            }
            if source.rate_limit_per_second:
                source_data["rate_limit_per_second"] = source.rate_limit_per_second
            data["sources"].append(source_data)

        # Save to file
        with open(output_path, "w") as f:
            if output_path.suffix.lower() in [".yaml", ".yml"]:
                yaml.dump(data, f, default_flow_style=False, indent=2)
            elif output_path.suffix.lower() == ".json":
                json.dump(data, f, indent=2)
            else:
                raise ConfigError(f"Unsupported output format: {output_path.suffix}")

    def get_config(self) -> Optional[IngestionConfig]:
        """Get the current configuration."""
        return self._config
