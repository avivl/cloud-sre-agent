# tests/ingestion/test_integration.py

"""
Integration tests for the log ingestion system.
"""

import os
import tempfile

import pytest

from gemini_sre_agent.config.ingestion_config import FileSystemConfig, SourceType
from gemini_sre_agent.ingestion.adapters.file_system import FileSystemAdapter
from gemini_sre_agent.ingestion.interfaces.core import LogEntry, LogSeverity


class TestFileSystemIntegration:
    """Test file system log ingestion integration."""

    @pytest.fixture
    def temp_log_file(self):
        """Create a temporary log file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("2024-01-01 10:00:00 INFO Test log message 1\n")
            f.write("2024-01-01 10:00:01 WARN Test warning message\n")
            f.write("2024-01-01 10:00:02 ERROR Test error message\n")
            temp_file = f.name

        yield temp_file

        # Cleanup
        try:
            os.unlink(temp_file)
        except OSError:
            pass

    def test_file_system_adapter_creation(self):
        """Test creating a file system adapter."""
        config = FileSystemConfig(
            name="test-file-source",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test.log",
            file_pattern="*.log",
        )

        adapter = FileSystemAdapter(config)
        assert adapter.config == config
        assert adapter.config.file_path == "/tmp/test.log"

    @pytest.mark.asyncio
    async def test_file_system_health_check(self):
        """Test file system adapter health check."""
        config = FileSystemConfig(
            name="test-file-source",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test.log",
            file_pattern="*.log",
        )

        adapter = FileSystemAdapter(config)
        health = await adapter.health_check()

        assert hasattr(health, "is_healthy")
        assert hasattr(health, "last_success")
        assert hasattr(health, "error_count")
        assert hasattr(health, "last_error")
        assert hasattr(health, "metrics")

    @pytest.mark.asyncio
    async def test_file_system_config_update(self):
        """Test updating file system adapter configuration."""
        config = FileSystemConfig(
            name="test-file-source",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test.log",
            file_pattern="*.log",
        )

        adapter = FileSystemAdapter(config)

        new_config = FileSystemConfig(
            name="test-file-source-new",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/new.log",
            file_pattern="*.txt",
        )

        await adapter.update_config(new_config)
        # Note: The actual update logic would need to be implemented
        assert adapter.config == config  # Currently no-op


class TestLogEntryIntegration:
    """Test LogEntry dataclass integration."""

    def test_log_entry_creation(self):
        """Test creating a LogEntry instance."""
        from datetime import datetime

        entry = LogEntry(
            id="test-123",
            timestamp=datetime.fromisoformat("2024-01-01T10:00:00"),
            message="Test log message",
            source="test-source",
            severity=LogSeverity.INFO,
            metadata={"key": "value"},
        )

        assert entry.id == "test-123"
        assert entry.timestamp.year == 2024
        assert entry.source == "test-source"
        assert entry.severity == LogSeverity.INFO
        assert entry.message == "Test log message"
        assert entry.metadata["key"] == "value"

    def test_log_severity_enum(self):
        """Test LogSeverity enum values."""
        assert LogSeverity.DEBUG == "DEBUG"
        assert LogSeverity.INFO == "INFO"
        assert LogSeverity.WARN == "WARN"
        assert LogSeverity.ERROR == "ERROR"
        assert LogSeverity.CRITICAL == "CRITICAL"


class TestConfigurationIntegration:
    """Test configuration system integration."""

    def test_source_type_enum(self):
        """Test SourceType enum values."""
        assert SourceType.FILE_SYSTEM == "file_system"
        assert SourceType.GCP_PUBSUB == "gcp_pubsub"
        assert SourceType.GCP_LOGGING == "gcp_logging"
        assert SourceType.AWS_CLOUDWATCH == "aws_cloudwatch"
        assert SourceType.KUBERNETES == "kubernetes"
        assert SourceType.SYSLOG == "syslog"


if __name__ == "__main__":
    pytest.main([__file__])
