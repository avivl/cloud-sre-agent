#!/usr/bin/env python3
"""
Simple test script to validate the ingestion configuration system.

This script tests the configuration loading, validation, and management
functionality without requiring the full ingestion system to be implemented.
"""

import json
import tempfile
from pathlib import Path

from gemini_sre_agent.config.ingestion_config import (
    BufferStrategy,
    FileSystemConfig,
    GCPLoggingConfig,
    GCPPubSubConfig,
    GlobalConfig,
    IngestionConfig,
    IngestionConfigManager,
    SourceType,
)


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

    # Test GCP Logging config
    logging_config = GCPLoggingConfig(
        name="test-logging",
        project_id="test-project",
        log_filter="severity>=ERROR",
    )

    assert logging_config.name == "test-logging"
    assert logging_config.type == SourceType.GCP_LOGGING
    assert logging_config.project_id == "test-project"
    assert logging_config.log_filter == "severity>=ERROR"
    print("✅ GCP Logging config test passed")


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


def test_config_manager():
    """Test the configuration manager."""
    print("Testing configuration manager...")

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

    # Test JSON config loading
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        temp_file = f.name

    try:
        manager = IngestionConfigManager()
        config = manager.load_config(temp_file)

        assert config.schema_version == "1.0.0"
        assert len(config.sources) == 2
        assert config.global_config.max_throughput == 500

        # Check first source
        pubsub_source = config.get_source_by_name("test-pubsub")
        assert pubsub_source is not None
        assert pubsub_source.type == SourceType.GCP_PUBSUB
        assert pubsub_source.project_id == "test-project"

        # Check second source
        fs_source = config.get_source_by_name("test-filesystem")
        assert fs_source is not None
        assert fs_source.type == SourceType.FILE_SYSTEM
        assert fs_source.file_path == "/var/log/apps"

        # Test validation
        errors = manager.validate_config()
        assert errors == []

        print("✅ Config manager JSON test passed")

    finally:
        Path(temp_file).unlink()

    # Test config saving
    test_config = IngestionConfig(
        sources=[
            GCPPubSubConfig(
                name="save-test",
                project_id="save-project",
                subscription_id="save-sub",
            ),
        ]
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_file = f.name

    try:
        manager.save_config(test_config, temp_file)

        # Load the saved config to verify
        loaded_config = manager.load_config(temp_file)
        assert len(loaded_config.sources) == 1
        assert loaded_config.get_source_by_name("save-test") is not None

        print("✅ Config manager save/load test passed")

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
        test_config_manager()
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
