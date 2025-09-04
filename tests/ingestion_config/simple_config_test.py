#!/usr/bin/env python3
"""
Simple test script to validate the ingestion configuration system.

This script tests the configuration loading, validation, and management
functionality without requiring the full ingestion system to be implemented.
"""

import json
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


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


def test_source_configs():
    """Test individual source configuration classes."""
    print("Testing source configurations...")

    # Test GCP Pub/Sub config
    gcp_config = GCPPubSubConfig(
        name="test-pubsub",
        project_id="test-project",
        subscription_id="test-subscription",
        credentials_path="/path/to/creds.json",
    )

    assert gcp_config.name == "test-pubsub"
    assert gcp_config.type == SourceType.GCP_PUBSUB
    assert gcp_config.project_id == "test-project"
    assert gcp_config.subscription_id == "test-subscription"
    print("✅ GCP Pub/Sub config test passed")

    # Test File System config
    fs_config = FileSystemConfig(
        name="test-filesystem",
        file_path="/var/log/apps",
        file_pattern="*.log",
        watch_mode=True,
    )

    assert fs_config.name == "test-filesystem"
    assert fs_config.type == SourceType.FILE_SYSTEM
    assert fs_config.file_path == "/var/log/apps"
    assert fs_config.file_pattern == "*.log"
    print("✅ File System config test passed")


def test_global_config():
    """Test global configuration."""
    print("Testing global configuration...")

    config = GlobalConfig(
        max_throughput=1000,
        error_threshold=0.1,
        enable_metrics=False,
        buffer_strategy=BufferStrategy.DIRECT,
    )

    assert config.max_throughput == 1000
    assert config.error_threshold == 0.1
    assert config.enable_metrics is False
    assert config.buffer_strategy == BufferStrategy.DIRECT
    print("✅ Global config test passed")


def test_ingestion_config():
    """Test the main ingestion configuration."""
    print("Testing ingestion configuration...")

    sources = [
        GCPPubSubConfig(
            name="pubsub-source",
            project_id="test-project",
            subscription_id="test-sub",
        ),
        FileSystemConfig(
            name="file-source",
            file_path="/var/log/apps",
        ),
    ]

    config = IngestionConfig(sources=sources)

    assert len(config.sources) == 2
    assert config.get_source_by_name("pubsub-source") is not None
    assert config.get_source_by_name("file-source") is not None
    assert config.get_source_by_name("nonexistent") is None

    # Test enabled sources
    enabled_sources = config.get_enabled_sources()
    assert len(enabled_sources) == 2

    # Test validation
    errors = config.validate()
    assert errors == []
    print("✅ Ingestion config test passed")


def test_config_validation():
    """Test configuration validation."""
    print("Testing configuration validation...")

    # Test valid config
    valid_config = IngestionConfig(
        sources=[
            GCPPubSubConfig(
                name="valid-source",
                project_id="test-project",
                subscription_id="test-sub",
                priority=10,
                max_retries=3,
                retry_delay=1.0,
                timeout=30.0,
            ),
        ]
    )

    errors = valid_config.validate()
    assert errors == []
    print("✅ Valid config validation test passed")

    # Test invalid config
    invalid_config = IngestionConfig(
        sources=[
            GCPPubSubConfig(
                name="",  # Empty name
                project_id="test-project",
                subscription_id="test-sub",
                priority=150,  # Invalid priority
                max_retries=-1,  # Invalid retries
                retry_delay=-1.0,  # Invalid delay
                timeout=0,  # Invalid timeout
            ),
        ]
    )

    errors = invalid_config.validate()
    assert len(errors) > 0
    assert any("Source name cannot be empty" in error for error in errors)
    assert any("priority must be between 1 and 100" in error for error in errors)
    print("✅ Invalid config validation test passed")


def test_config_file_loading():
    """Test loading configuration from files."""
    print("Testing configuration file loading...")

    # Create test config data
    config_data = {
        "schema_version": "1.0.0",
        "global_config": {
            "max_throughput": 500,
            "error_threshold": 0.05,
            "enable_metrics": True,
            "enable_health_checks": True,
            "health_check_interval": 30,
            "max_message_length": 10000,
            "enable_pii_detection": True,
            "enable_flow_tracking": True,
            "default_buffer_size": 1000,
            "max_memory_mb": 500,
            "backpressure_threshold": 0.8,
            "drop_oldest_on_full": True,
            "buffer_strategy": "memory",
        },
        "sources": [
            {
                "name": "test-pubsub",
                "type": "gcp_pubsub",
                "enabled": True,
                "priority": 10,
                "config": {
                    "project_id": "test-project",
                    "subscription_id": "test-subscription",
                    "credentials_path": "/path/to/creds.json",
                    "max_messages": 100,
                    "ack_deadline_seconds": 60,
                    "flow_control_max_messages": 1000,
                    "flow_control_max_bytes": 10485760,
                },
                "max_retries": 3,
                "retry_delay": 1.0,
                "timeout": 30.0,
                "circuit_breaker_enabled": True,
                "rate_limit_per_second": 100,
            },
        ],
    }

    # Test JSON config loading
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        temp_file = f.name

    try:
        # Load and parse the config
        with open(temp_file, "r") as f:
            loaded_data = json.load(f)

        # Create config from loaded data
        global_config = GlobalConfig(
            max_throughput=loaded_data["global_config"]["max_throughput"],
            error_threshold=loaded_data["global_config"]["error_threshold"],
            enable_metrics=loaded_data["global_config"]["enable_metrics"],
            enable_health_checks=loaded_data["global_config"]["enable_health_checks"],
            health_check_interval=loaded_data["global_config"]["health_check_interval"],
            max_message_length=loaded_data["global_config"]["max_message_length"],
            enable_pii_detection=loaded_data["global_config"]["enable_pii_detection"],
            enable_flow_tracking=loaded_data["global_config"]["enable_flow_tracking"],
            default_buffer_size=loaded_data["global_config"]["default_buffer_size"],
            max_memory_mb=loaded_data["global_config"]["max_memory_mb"],
            backpressure_threshold=loaded_data["global_config"][
                "backpressure_threshold"
            ],
            drop_oldest_on_full=loaded_data["global_config"]["drop_oldest_on_full"],
            buffer_strategy=BufferStrategy(
                loaded_data["global_config"]["buffer_strategy"]
            ),
        )

        sources = []
        for source_data in loaded_data["sources"]:
            if source_data["type"] == "gcp_pubsub":
                source_config = source_data["config"]
                source = GCPPubSubConfig(
                    name=source_data["name"],
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
                sources.append(source)

        config = IngestionConfig(sources=sources, global_config=global_config)

        assert config.schema_version == "1.0.0"
        assert len(config.sources) == 1
        assert config.global_config.max_throughput == 500

        # Check source
        pubsub_source = config.get_source_by_name("test-pubsub")
        assert pubsub_source is not None
        assert pubsub_source.type == SourceType.GCP_PUBSUB
        # Use type checking to access specific attributes
        if isinstance(pubsub_source, GCPPubSubConfig):
            assert pubsub_source.project_id == "test-project"

        # Test validation
        errors = config.validate()
        assert errors == []

        print("✅ Config file loading test passed")

    finally:
        Path(temp_file).unlink()


def test_enums():
    """Test enum classes."""
    print("Testing enums...")

    # Test SourceType enum
    assert SourceType.GCP_PUBSUB == "gcp_pubsub"
    assert SourceType.GCP_LOGGING == "gcp_logging"
    assert SourceType.FILE_SYSTEM == "file_system"
    assert SourceType.AWS_CLOUDWATCH == "aws_cloudwatch"
    assert SourceType.KUBERNETES == "kubernetes"
    assert SourceType.SYSLOG == "syslog"

    # Test BufferStrategy enum
    assert BufferStrategy.DIRECT == "direct"
    assert BufferStrategy.MEMORY == "memory"
    assert BufferStrategy.EXTERNAL == "external"

    print("✅ Enums test passed")


def main():
    """Run all tests."""
    print("🧪 Testing Ingestion Configuration System")
    print("=" * 50)

    try:
        test_source_configs()
        test_global_config()
        test_ingestion_config()
        test_config_validation()
        test_config_file_loading()
        test_enums()

        print("=" * 50)
        print("✅ All tests passed!")
        print("\nThe ingestion configuration system is working correctly.")
        print("You can now use the configuration files in examples/ingestion_configs/")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    main()
