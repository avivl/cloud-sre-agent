"""
Pytest configuration and fixtures for the test suite.

This module provides common fixtures and configuration for all tests.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def temp_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary file in the temp directory."""
    temp_file = temp_dir / "test_file.txt"
    temp_file.touch()
    yield temp_file


@pytest.fixture
def sample_log_content() -> str:
    """Sample log content for testing."""
    return """2024-01-01 10:00:00 INFO Application started
2024-01-01 10:01:00 ERROR Database connection failed
2024-01-01 10:02:00 WARNING High memory usage detected
2024-01-01 10:03:00 INFO User john.doe@example.com logged in
2024-01-01 10:04:00 ERROR Failed to process payment for user 12345
2024-01-01 10:05:00 INFO Cache cleared successfully
"""


@pytest.fixture
def sample_log_file(temp_dir: Path, sample_log_content: str) -> Path:
    """Create a sample log file with test content."""
    log_file = temp_dir / "sample.log"
    with open(log_file, "w") as f:
        f.write(sample_log_content)
    return log_file


@pytest.fixture
def sample_config_data() -> dict:
    """Sample configuration data for testing."""
    return {
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


@pytest.fixture
def sample_config_file(temp_dir: Path, sample_config_data: dict) -> Path:
    """Create a sample configuration file."""
    import json

    config_file = temp_dir / "test_config.json"
    with open(config_file, "w") as f:
        json.dump(sample_config_data, f, indent=2)
    return config_file


@pytest.fixture
def sample_yaml_config_file(temp_dir: Path, sample_config_data: dict) -> Path:
    """Create a sample YAML configuration file."""
    import yaml

    config_file = temp_dir / "test_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(sample_config_data, f, default_flow_style=False, indent=2)
    return config_file


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add asyncio marker to async tests
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)

        # Add unit marker to non-integration tests
        if "integration" not in item.name and "test_" in item.name:
            item.add_marker(pytest.mark.unit)
