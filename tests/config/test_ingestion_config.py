"""
Tests for the ingestion configuration system.

This module tests the configuration loading, validation, and management
functionality for the log ingestion system.
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from gemini_sre_agent.config.ingestion_config import (
    AWSCloudWatchConfig,
    BufferStrategy,
    FileSystemConfig,
    GCPLoggingConfig,
    GCPPubSubConfig,
    GlobalConfig,
    HealthCheckStatus,
    IngestionConfig,
    IngestionConfigManager,
    KubernetesConfig,
    SourceType,
    SyslogConfig,
)


class TestSourceConfigs:
    """Test individual source configuration classes."""

    def test_gcp_pubsub_config(self):
        """Test GCP Pub/Sub configuration."""
        config = GCPPubSubConfig(
            name="test-pubsub",
            type=SourceType.GCP_PUBSUB,
            project_id="test-project",
            subscription_id="test-subscription",
            credentials_path="/path/to/creds.json",
            max_messages=50,
            ack_deadline_seconds=30,
            flow_control_max_messages=500,
            flow_control_max_bytes=5 * 1024 * 1024,
        )

        assert config.name == "test-pubsub"
        assert config.type == SourceType.GCP_PUBSUB
        assert config.project_id == "test-project"
        assert config.subscription_id == "test-subscription"
        assert config.credentials_path == "/path/to/creds.json"
        assert config.max_messages == 50
        assert config.ack_deadline_seconds == 30
        assert config.flow_control_max_messages == 500
        assert config.flow_control_max_bytes == 5 * 1024 * 1024

        # Check that config dict is populated
        assert config.config["project_id"] == "test-project"
        assert config.config["subscription_id"] == "test-subscription"

    def test_gcp_logging_config(self):
        """Test GCP Logging configuration."""
        config = GCPLoggingConfig(
            name="test-logging",
            type=SourceType.GCP_LOGGING,
            project_id="test-project",
            log_filter="severity>=WARNING",
            credentials_path="/path/to/creds.json",
            poll_interval=60,
            max_results=200,
        )

        assert config.name == "test-logging"
        assert config.type == SourceType.GCP_LOGGING
        assert config.project_id == "test-project"
        assert config.log_filter == "severity>=WARNING"
        assert config.poll_interval == 60
        assert config.max_results == 200

    def test_file_system_config(self):
        """Test file system configuration."""
        config = FileSystemConfig(
            name="test-filesystem",
            type=SourceType.FILE_SYSTEM,
            file_path="/var/log/apps",
            file_pattern="*.log",
            watch_mode=True,
            encoding="utf-8",
            buffer_size=500,
            max_memory_mb=50,
        )

        assert config.name == "test-filesystem"
        assert config.type == SourceType.FILE_SYSTEM
        assert config.file_path == "/var/log/apps"
        assert config.file_pattern == "*.log"
        assert config.watch_mode is True
        assert config.encoding == "utf-8"
        assert config.buffer_size == 500
        assert config.max_memory_mb == 50

    def test_aws_cloudwatch_config(self):
        """Test AWS CloudWatch configuration."""
        config = AWSCloudWatchConfig(
            name="test-cloudwatch",
            type=SourceType.AWS_CLOUDWATCH,
            log_group_name="/aws/application",
            log_stream_name="stream1",
            region="us-west-2",
            credentials_profile="production",
            poll_interval=45,
            max_events=300,
        )

        assert config.name == "test-cloudwatch"
        assert config.type == SourceType.AWS_CLOUDWATCH
        assert config.log_group_name == "/aws/application"
        assert config.log_stream_name == "stream1"
        assert config.region == "us-west-2"
        assert config.credentials_profile == "production"
        assert config.poll_interval == 45
        assert config.max_events == 300

    def test_kubernetes_config(self):
        """Test Kubernetes configuration."""
        config = KubernetesConfig(
            name="test-k8s",
            type=SourceType.KUBERNETES,
            namespace="production",
            label_selector="app=my-app",
            container_name="main-container",
            kubeconfig_path="/path/to/kubeconfig",
            poll_interval=30,
            max_logs=200,
        )

        assert config.name == "test-k8s"
        assert config.type == SourceType.KUBERNETES
        assert config.namespace == "production"
        assert config.label_selector == "app=my-app"
        assert config.container_name == "main-container"
        assert config.kubeconfig_path == "/path/to/kubeconfig"
        assert config.poll_interval == 30
        assert config.max_logs == 200

    def test_syslog_config(self):
        """Test Syslog configuration."""
        config = SyslogConfig(
            name="test-syslog",
            type=SourceType.SYSLOG,
            host="192.168.1.100",
            port=514,
            protocol="udp",
            facility=16,
            severity=6,
        )

        assert config.name == "test-syslog"
        assert config.type == SourceType.SYSLOG
        assert config.host == "192.168.1.100"
        assert config.port == 514
        assert config.protocol == "udp"
        assert config.facility == 16
        assert config.severity == 6


class TestGlobalConfig:
    """Test global configuration."""

    def test_default_global_config(self):
        """Test default global configuration values."""
        config = GlobalConfig()

        assert config.max_throughput == 500
        assert config.error_threshold == 0.05
        assert config.enable_metrics is True
        assert config.enable_health_checks is True
        assert config.health_check_interval == 30
        assert config.max_message_length == 10000
        assert config.enable_pii_detection is True
        assert config.enable_flow_tracking is True
        assert config.default_buffer_size == 1000
        assert config.max_memory_mb == 500
        assert config.backpressure_threshold == 0.8
        assert config.drop_oldest_on_full is True
        assert config.buffer_strategy == BufferStrategy.MEMORY

    def test_custom_global_config(self):
        """Test custom global configuration values."""
        config = GlobalConfig(
            max_throughput=1000,
            error_threshold=0.1,
            enable_metrics=False,
            enable_health_checks=False,
            health_check_interval=60,
            max_message_length=15000,
            enable_pii_detection=False,
            enable_flow_tracking=False,
            default_buffer_size=2000,
            max_memory_mb=1000,
            backpressure_threshold=0.9,
            drop_oldest_on_full=False,
            buffer_strategy=BufferStrategy.DIRECT,
        )

        assert config.max_throughput == 1000
        assert config.error_threshold == 0.1
        assert config.enable_metrics is False
        assert config.enable_health_checks is False
        assert config.health_check_interval == 60
        assert config.max_message_length == 15000
        assert config.enable_pii_detection is False
        assert config.enable_flow_tracking is False
        assert config.default_buffer_size == 2000
        assert config.max_memory_mb == 1000
        assert config.backpressure_threshold == 0.9
        assert config.drop_oldest_on_full is False
        assert config.buffer_strategy == BufferStrategy.DIRECT


class TestIngestionConfig:
    """Test the main ingestion configuration class."""

    def test_empty_config(self):
        """Test empty configuration."""
        config = IngestionConfig()

        assert config.sources == []
        assert isinstance(config.global_config, GlobalConfig)
        assert config.schema_version == "1.0.0"

    def test_config_with_sources(self):
        """Test configuration with sources."""
        sources = [
            GCPPubSubConfig(
                name="pubsub-source",
                type=SourceType.GCP_PUBSUB,
                project_id="test-project",
                subscription_id="test-sub",
            ),
            FileSystemConfig(
                name="file-source",
                type=SourceType.FILE_SYSTEM,
                file_path="/var/log/apps",
            ),
        ]

        config = IngestionConfig(sources=sources)

        assert len(config.sources) == 2
        assert config.get_source_by_name("pubsub-source") is not None
        assert config.get_source_by_name("file-source") is not None
        assert config.get_source_by_name("nonexistent") is None

    def test_get_enabled_sources(self):
        """Test getting enabled sources sorted by priority."""
        sources = [
            GCPPubSubConfig(
                name="low-priority",
                type=SourceType.GCP_PUBSUB,
                project_id="test-project",
                subscription_id="test-sub",
                priority=20,
                enabled=False,
            ),
            FileSystemConfig(
                name="high-priority",
                type=SourceType.FILE_SYSTEM,
                file_path="/var/log/apps",
                priority=5,
                enabled=True,
            ),
            GCPLoggingConfig(
                name="medium-priority",
                type=SourceType.GCP_LOGGING,
                project_id="test-project",
                priority=10,
                enabled=True,
            ),
        ]

        config = IngestionConfig(sources=sources)
        enabled_sources = config.get_enabled_sources()

        assert len(enabled_sources) == 2
        assert enabled_sources[0].name == "high-priority"  # priority 5
        assert enabled_sources[1].name == "medium-priority"  # priority 10

    def test_validation_success(self):
        """Test successful configuration validation."""
        sources = [
            GCPPubSubConfig(
                name="valid-source",
                type=SourceType.GCP_PUBSUB,
                project_id="test-project",
                subscription_id="test-sub",
                priority=10,
                max_retries=3,
                retry_delay=1.0,
                timeout=30.0,
            ),
        ]

        config = IngestionConfig(sources=sources)
        errors = config.validate()

        assert errors == []

    def test_validation_errors(self):
        """Test configuration validation with errors."""
        sources = [
            GCPPubSubConfig(
                name="",  # Empty name
                type=SourceType.GCP_PUBSUB,
                project_id="test-project",
                subscription_id="test-sub",
                priority=150,  # Invalid priority
                max_retries=-1,  # Invalid retries
                retry_delay=-1.0,  # Invalid delay
                timeout=0,  # Invalid timeout
            ),
        ]

        config = IngestionConfig(sources=sources)
        errors = config.validate()

        assert len(errors) > 0
        assert any("Source name cannot be empty" in error for error in errors)
        assert any("priority must be between 1 and 100" in error for error in errors)
        assert any("max_retries must be non-negative" in error for error in errors)
        assert any("retry_delay must be non-negative" in error for error in errors)
        assert any("timeout must be positive" in error for error in errors)

    def test_duplicate_source_names(self):
        """Test validation with duplicate source names."""
        sources = [
            GCPPubSubConfig(
                name="duplicate",
                type=SourceType.GCP_PUBSUB,
                project_id="test-project",
                subscription_id="test-sub1",
            ),
            FileSystemConfig(
                name="duplicate",
                type=SourceType.FILE_SYSTEM,
                file_path="/var/log/apps",
            ),
        ]

        config = IngestionConfig(sources=sources)
        errors = config.validate()

        assert len(errors) > 0
        assert any("Duplicate source names found" in error for error in errors)

    def test_global_config_validation_errors(self):
        """Test global configuration validation errors."""
        global_config = GlobalConfig(
            max_throughput=0,  # Invalid
            error_threshold=1.5,  # Invalid
            health_check_interval=0,  # Invalid
            max_message_length=0,  # Invalid
            default_buffer_size=0,  # Invalid
            max_memory_mb=0,  # Invalid
            backpressure_threshold=1.5,  # Invalid
        )

        config = IngestionConfig(global_config=global_config)
        errors = config.validate()

        assert len(errors) > 0
        assert any("max_throughput must be positive" in error for error in errors)
        assert any(
            "error_threshold must be between 0 and 1" in error for error in errors
        )
        assert any(
            "health_check_interval must be positive" in error for error in errors
        )
        assert any("max_message_length must be positive" in error for error in errors)
        assert any("default_buffer_size must be positive" in error for error in errors)
        assert any("max_memory_mb must be positive" in error for error in errors)
        assert any(
            "backpressure_threshold must be between 0 and 1" in error
            for error in errors
        )


class TestIngestionConfigManager:
    """Test the configuration manager."""

    def test_load_json_config(self):
        """Test loading configuration from JSON file."""
        config_data = {
            "schema_version": "1.0.0",
            "global_config": {
                "max_throughput": 1000,
                "error_threshold": 0.1,
                "enable_metrics": True,
                "enable_health_checks": True,
                "health_check_interval": 60,
                "max_message_length": 15000,
                "enable_pii_detection": True,
                "enable_flow_tracking": True,
                "default_buffer_size": 2000,
                "max_memory_mb": 1000,
                "backpressure_threshold": 0.9,
                "drop_oldest_on_full": False,
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
                {
                    "name": "test-filesystem",
                    "type": "file_system",
                    "enabled": True,
                    "priority": 20,
                    "config": {
                        "file_path": "/var/log/apps",
                        "file_pattern": "*.log",
                        "watch_mode": True,
                        "encoding": "utf-8",
                        "buffer_size": 1000,
                        "max_memory_mb": 100,
                    },
                    "max_retries": 3,
                    "retry_delay": 1.0,
                    "timeout": 30.0,
                    "circuit_breaker_enabled": True,
                    "rate_limit_per_second": 50,
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name

        try:
            manager = IngestionConfigManager()
            config = manager.load_config(temp_file)

            assert config.schema_version == "1.0.0"
            assert len(config.sources) == 2
            assert config.global_config.max_throughput == 1000
            assert config.global_config.error_threshold == 0.1

            # Check first source
            pubsub_source = config.get_source_by_name("test-pubsub")
            assert pubsub_source is not None
            assert pubsub_source.type == SourceType.GCP_PUBSUB
            assert pubsub_source.project_id == "test-project"
            assert pubsub_source.subscription_id == "test-subscription"

            # Check second source
            fs_source = config.get_source_by_name("test-filesystem")
            assert fs_source is not None
            assert fs_source.type == SourceType.FILE_SYSTEM
            assert fs_source.file_path == "/var/log/apps"
            assert fs_source.file_pattern == "*.log"

        finally:
            Path(temp_file).unlink()

    def test_load_yaml_config(self):
        """Test loading configuration from YAML file."""
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
                "buffer_strategy": "direct",
            },
            "sources": [
                {
                    "name": "test-logging",
                    "type": "gcp_logging",
                    "enabled": True,
                    "priority": 10,
                    "config": {
                        "project_id": "test-project",
                        "log_filter": "severity>=ERROR",
                        "credentials_path": "/path/to/creds.json",
                        "poll_interval": 30,
                        "max_results": 1000,
                    },
                    "max_retries": 3,
                    "retry_delay": 1.0,
                    "timeout": 30.0,
                    "circuit_breaker_enabled": True,
                    "rate_limit_per_second": 30,
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_file = f.name

        try:
            manager = IngestionConfigManager()
            config = manager.load_config(temp_file)

            assert config.schema_version == "1.0.0"
            assert len(config.sources) == 1
            assert config.global_config.max_throughput == 500
            assert config.global_config.buffer_strategy == BufferStrategy.DIRECT

            # Check source
            logging_source = config.get_source_by_name("test-logging")
            assert logging_source is not None
            assert logging_source.type == SourceType.GCP_LOGGING
            assert logging_source.project_id == "test-project"
            assert logging_source.log_filter == "severity>=ERROR"

        finally:
            Path(temp_file).unlink()

    def test_load_config_file_not_found(self):
        """Test loading configuration from non-existent file."""
        manager = IngestionConfigManager()

        with pytest.raises(Exception):  # Should raise ConfigError
            manager.load_config("/nonexistent/file.json")

    def test_load_config_unsupported_format(self):
        """Test loading configuration from unsupported file format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is not a valid config file")
            temp_file = f.name

        try:
            manager = IngestionConfigManager()

            with pytest.raises(Exception):  # Should raise ConfigError
                manager.load_config(temp_file)

        finally:
            Path(temp_file).unlink()

    def test_validate_config(self):
        """Test configuration validation through manager."""
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
                    "name": "valid-source",
                    "type": "gcp_pubsub",
                    "enabled": True,
                    "priority": 10,
                    "config": {
                        "project_id": "test-project",
                        "subscription_id": "test-subscription",
                    },
                    "max_retries": 3,
                    "retry_delay": 1.0,
                    "timeout": 30.0,
                    "circuit_breaker_enabled": True,
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name

        try:
            manager = IngestionConfigManager()
            manager.load_config(temp_file)
            errors = manager.validate_config()

            assert errors == []

        finally:
            Path(temp_file).unlink()

    def test_save_config(self):
        """Test saving configuration to file."""
        sources = [
            GCPPubSubConfig(
                name="test-pubsub",
                type=SourceType.GCP_PUBSUB,
                project_id="test-project",
                subscription_id="test-subscription",
            ),
        ]

        config = IngestionConfig(sources=sources)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_file = f.name

        try:
            manager = IngestionConfigManager()
            manager.save_config(config, temp_file)

            # Load the saved config to verify it was saved correctly
            loaded_config = manager.load_config(temp_file)
            assert len(loaded_config.sources) == 1
            assert loaded_config.get_source_by_name("test-pubsub") is not None

        finally:
            Path(temp_file).unlink()

    def test_save_config_yaml(self):
        """Test saving configuration to YAML file."""
        sources = [
            FileSystemConfig(
                name="test-filesystem",
                type=SourceType.FILE_SYSTEM,
                file_path="/var/log/apps",
            ),
        ]

        config = IngestionConfig(sources=sources)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_file = f.name

        try:
            manager = IngestionConfigManager()
            manager.save_config(config, temp_file)

            # Load the saved config to verify it was saved correctly
            loaded_config = manager.load_config(temp_file)
            assert len(loaded_config.sources) == 1
            assert loaded_config.get_source_by_name("test-filesystem") is not None

        finally:
            Path(temp_file).unlink()

    def test_save_config_unsupported_format(self):
        """Test saving configuration to unsupported file format."""
        config = IngestionConfig()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            temp_file = f.name

        try:
            manager = IngestionConfigManager()

            with pytest.raises(Exception):  # Should raise ConfigError
                manager.save_config(config, temp_file)

        finally:
            Path(temp_file).unlink()

    def test_get_config(self):
        """Test getting current configuration."""
        manager = IngestionConfigManager()

        # Initially no config loaded
        assert manager.get_config() is None

        # Load a config
        config_data = {
            "schema_version": "1.0.0",
            "global_config": {},
            "sources": [],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name

        try:
            config = manager.load_config(temp_file)
            assert manager.get_config() is not None
            assert manager.get_config() == config

        finally:
            Path(temp_file).unlink()


class TestEnums:
    """Test enum classes."""

    def test_source_type_enum(self):
        """Test SourceType enum values."""
        assert SourceType.GCP_PUBSUB == "gcp_pubsub"
        assert SourceType.GCP_LOGGING == "gcp_logging"
        assert SourceType.FILE_SYSTEM == "file_system"
        assert SourceType.AWS_CLOUDWATCH == "aws_cloudwatch"
        assert SourceType.KUBERNETES == "kubernetes"
        assert SourceType.SYSLOG == "syslog"

    def test_buffer_strategy_enum(self):
        """Test BufferStrategy enum values."""
        assert BufferStrategy.DIRECT == "direct"
        assert BufferStrategy.MEMORY == "memory"
        assert BufferStrategy.EXTERNAL == "external"

    def test_health_check_status_enum(self):
        """Test HealthCheckStatus enum values."""
        assert HealthCheckStatus.HEALTHY == "healthy"
        assert HealthCheckStatus.UNHEALTHY == "unhealthy"
        assert HealthCheckStatus.DEGRADED == "degraded"
        assert HealthCheckStatus.UNKNOWN == "unknown"
