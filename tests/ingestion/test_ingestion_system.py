"""
Tests for the log ingestion system components.

This module tests the core ingestion functionality including
LogManager, adapters, and processing components.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from gemini_sre_agent.config.ingestion_config import FileSystemConfig, SourceType
from gemini_sre_agent.ingestion import LogManager
from gemini_sre_agent.ingestion.adapters import FileSystemAdapter
from gemini_sre_agent.ingestion.interfaces.core import (
    LogEntry,
    LogSeverity,
    SourceHealth,
)


class TestLogEntry:
    """Test LogEntry model."""

    def test_log_entry_creation(self):
        """Test creating a LogEntry."""
        log_entry = LogEntry(
            id="test-123",
            message="Test log message",
            timestamp=datetime.fromisoformat("2024-01-01T10:00:00Z"),
            severity=LogSeverity.INFO,
            source="test-source",
            flow_id="flow-123",
            metadata={"key": "value"},
        )

        assert log_entry.message == "Test log message"
        assert log_entry.severity == LogSeverity.INFO
        assert log_entry.source == "test-source"
        assert log_entry.timestamp == datetime.fromisoformat("2024-01-01T10:00:00Z")
        assert log_entry.flow_id == "flow-123"
        assert log_entry.metadata == {"key": "value"}

    def test_log_entry_defaults(self):
        """Test LogEntry with default values."""
        log_entry = LogEntry(
            id="test-456",
            message="Test message",
            timestamp=datetime.now(),
            severity=LogSeverity.INFO,
            source="test-source",
        )

        assert log_entry.message == "Test message"
        assert log_entry.severity == LogSeverity.INFO
        assert log_entry.source == "test-source"
        assert log_entry.timestamp is not None
        assert log_entry.flow_id is None
        assert log_entry.metadata == {}


class TestSourceHealth:
    """Test SourceHealth model."""

    def test_source_health_creation(self):
        """Test creating a SourceHealth."""
        health = SourceHealth(
            is_healthy=True,
            last_success="2024-01-01T10:00:00Z",
            error_count=0,
            metrics={"success_count": 100},
        )

        assert health.is_healthy is True
        assert health.last_success == "2024-01-01T10:00:00Z"
        assert health.error_count == 0
        assert health.metrics["success_count"] == 100

    def test_source_health_defaults(self):
        """Test SourceHealth with default values."""
        health = SourceHealth(is_healthy=False)

        assert health.is_healthy is False
        assert health.error_count == 0


class TestLogManager:
    """Test LogManager functionality."""

    @pytest.fixture
    def mock_callback(self):
        """Create a mock callback function."""
        return AsyncMock()

    @pytest.fixture
    def log_manager(self, mock_callback):
        """Create a LogManager instance."""
        return LogManager(callback=mock_callback)

    def test_log_manager_creation(self, mock_callback):
        """Test creating a LogManager."""
        manager = LogManager(callback=mock_callback)

        assert manager.callback == mock_callback
        assert manager.sources == {}
        assert manager.running is False

    def test_log_manager_creation_without_callback(self):
        """Test creating a LogManager without callback."""
        manager = LogManager()

        assert manager.callback is None
        assert manager.sources == {}
        assert manager.running is False

    @pytest.mark.asyncio
    async def test_add_source(self, log_manager):
        """Test adding a source to the manager."""
        config = FileSystemConfig(
            name="test-source",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test-logs",
        )

        adapter = FileSystemAdapter(config)

        await log_manager.add_source(adapter)

        assert "test-source" in log_manager.sources
        assert log_manager.sources["test-source"] == adapter

    @pytest.mark.asyncio
    async def test_add_duplicate_source(self, log_manager):
        """Test adding a duplicate source name."""
        config1 = FileSystemConfig(
            name="duplicate-source",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test-logs1",
        )
        config2 = FileSystemConfig(
            name="duplicate-source",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test-logs2",
        )

        adapter1 = FileSystemAdapter(config1)
        adapter2 = FileSystemAdapter(config2)

        await log_manager.add_source(adapter1)

        # Adding a duplicate should raise an exception
        with pytest.raises(ValueError):
            await log_manager.add_source(adapter2)

    @pytest.mark.asyncio
    async def test_remove_source(self, log_manager):
        """Test removing a source from the manager."""
        config = FileSystemConfig(
            name="test-source",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test-logs",
        )

        adapter = FileSystemAdapter(config)

        await log_manager.add_source(adapter)
        assert "test-source" in log_manager.sources

        await log_manager.remove_source("test-source")
        assert "test-source" not in log_manager.sources

    @pytest.mark.asyncio
    async def test_remove_nonexistent_source(self, log_manager):
        """Test removing a non-existent source."""
        # Should not raise an exception
        await log_manager.remove_source("nonexistent-source")

    @pytest.mark.asyncio
    async def test_start_manager(self, log_manager):
        """Test starting the manager."""
        config = FileSystemConfig(
            name="test-source",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test-logs",
        )

        adapter = FileSystemAdapter(config)

        # Mock the adapter's start method
        adapter.start = AsyncMock()

        await log_manager.add_source(adapter)
        await log_manager.start()

        assert log_manager.is_running is True
        adapter.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_manager(self, log_manager):
        """Test stopping the manager."""
        config = FileSystemConfig(
            name="test-source",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test-logs",
        )

        adapter = FileSystemAdapter(config)

        # Mock the adapter's stop method
        adapter.stop = AsyncMock()

        await log_manager.add_source(adapter)
        await log_manager.start()
        await log_manager.stop()

        assert log_manager.is_running is False
        adapter.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_health_status(self, log_manager):
        """Test getting health status of all sources."""
        config = FileSystemConfig(
            name="test-source",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test-logs",
        )

        adapter = FileSystemAdapter(config)

        # Mock the adapter's get_health method
        mock_health = SourceHealth(is_healthy=True, status="healthy")
        adapter.get_health = AsyncMock(return_value=mock_health)

        await log_manager.add_source(adapter)

        health_status = await log_manager.get_health_status()

        assert "test-source" in health_status
        assert health_status["test-source"] == mock_health
        adapter.get_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metrics(self, log_manager):
        """Test getting metrics from all sources."""
        config = FileSystemConfig(
            name="test-source",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test-logs",
        )

        adapter = FileSystemAdapter(config)

        # Mock the adapter's get_metrics method
        mock_metrics = {"processed": 100, "errors": 5}
        adapter.get_metrics = AsyncMock(return_value=mock_metrics)

        await log_manager.add_source(adapter)

        metrics = await log_manager.get_metrics()

        assert "sources" in metrics
        assert "test-source" in metrics["sources"]
        assert metrics["sources"]["test-source"] == mock_metrics
        adapter.get_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_log_entry(self, log_manager, mock_callback):
        """Test processing a log entry through the callback."""
        log_entry = LogEntry(
            message="Test message",
            severity=LogSeverity.INFO,
            source="test-source",
        )

        await log_manager.process_log_entry(log_entry)

        mock_callback.assert_called_once_with(log_entry)

    @pytest.mark.asyncio
    async def test_process_log_entry_no_callback(self):
        """Test processing a log entry without a callback."""
        manager = LogManager()  # No callback

        log_entry = LogEntry(
            message="Test message",
            severity=LogSeverity.INFO,
            source="test-source",
        )

        # Should not raise an exception
        await manager.process_log_entry(log_entry)

    @pytest.mark.asyncio
    async def test_process_log_entry_callback_error(self, mock_callback):
        """Test processing a log entry when callback raises an error."""
        manager = LogManager(callback=mock_callback)

        # Make the callback raise an exception
        mock_callback.side_effect = Exception("Callback error")

        log_entry = LogEntry(
            message="Test message",
            severity=LogSeverity.INFO,
            source="test-source",
        )

        # Should not raise an exception (error should be handled)
        await manager.process_log_entry(log_entry)

        mock_callback.assert_called_once_with(log_entry)


class TestFileSystemAdapter:
    """Test FileSystemAdapter functionality."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary directory for test logs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def fs_config(self, temp_log_dir):
        """Create a FileSystemConfig for testing."""
        return FileSystemConfig(
            name="test-fs-adapter",
            file_path=str(temp_log_dir),
            file_pattern="*.log",
            watch_mode=False,  # Don't watch for changes in tests
            encoding="utf-8",
            buffer_size=100,
            max_memory_mb=10,
        )

    @pytest.fixture
    def fs_adapter(self, fs_config):
        """Create a FileSystemAdapter for testing."""
        return FileSystemAdapter(fs_config)

    def test_fs_adapter_creation(self, fs_adapter, fs_config):
        """Test creating a FileSystemAdapter."""
        assert fs_adapter.config == fs_config
        assert fs_adapter.name == "test-fs-adapter"
        assert fs_adapter.is_running is False

    @pytest.mark.asyncio
    async def test_fs_adapter_start_stop(self, fs_adapter):
        """Test starting and stopping the adapter."""
        # Mock the file processing
        with patch.object(fs_adapter, "_process_files") as mock_process:
            mock_process.return_value = []

            await fs_adapter.start()
            assert fs_adapter.is_running is True

            await fs_adapter.stop()
            assert fs_adapter.is_running is False

    @pytest.mark.asyncio
    async def test_fs_adapter_get_health(self, fs_adapter):
        """Test getting health status from the adapter."""
        health = await fs_adapter.get_health()

        assert isinstance(health, SourceHealth)
        assert health.is_healthy is True
        assert health.status == "healthy"

    @pytest.mark.asyncio
    async def test_fs_adapter_get_metrics(self, fs_adapter):
        """Test getting metrics from the adapter."""
        metrics = await fs_adapter.get_metrics()

        assert isinstance(metrics, dict)
        assert "processed" in metrics
        assert "errors" in metrics
        assert "last_processed" in metrics

    @pytest.mark.asyncio
    async def test_fs_adapter_process_files(self, fs_adapter, temp_log_dir):
        """Test processing log files."""
        # Create a test log file
        test_log_file = temp_log_dir / "test.log"
        with open(test_log_file, "w") as f:
            f.write("2024-01-01 10:00:00 INFO Test message 1\n")
            f.write("2024-01-01 10:01:00 ERROR Test error message\n")
            f.write("2024-01-01 10:02:00 WARNING Test warning message\n")

        # Mock the callback
        mock_callback = AsyncMock()
        fs_adapter.callback = mock_callback

        # Process the files
        await fs_adapter._process_files()

        # Check that the callback was called for each log line
        assert mock_callback.call_count == 3

        # Check the log entries
        calls = mock_callback.call_args_list
        assert calls[0][0][0].message == "Test message 1"
        assert calls[0][0][0].level == LogSeverity.INFO
        assert calls[1][0][0].message == "Test error message"
        assert calls[1][0][0].level == LogSeverity.ERROR
        assert calls[2][0][0].message == "Test warning message"
        assert calls[2][0][0].level == LogSeverity.WARNING

    @pytest.mark.asyncio
    async def test_fs_adapter_process_files_with_callback_error(
        self, fs_adapter, temp_log_dir
    ):
        """Test processing files when callback raises an error."""
        # Create a test log file
        test_log_file = temp_log_dir / "test.log"
        with open(test_log_file, "w") as f:
            f.write("2024-01-01 10:00:00 INFO Test message\n")

        # Mock the callback to raise an exception
        mock_callback = AsyncMock(side_effect=Exception("Callback error"))
        fs_adapter.callback = mock_callback

        # Process the files - should not raise an exception
        await fs_adapter._process_files()

        # Check that the callback was called
        mock_callback.assert_called_once()

        # Check that error count increased
        metrics = await fs_adapter.get_metrics()
        assert metrics["errors"] > 0

    @pytest.mark.asyncio
    async def test_fs_adapter_process_files_no_files(self, fs_adapter, temp_log_dir):
        """Test processing when no log files exist."""
        # Mock the callback
        mock_callback = AsyncMock()
        fs_adapter.callback = mock_callback

        # Process the files
        await fs_adapter._process_files()

        # Callback should not be called
        mock_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_fs_adapter_process_files_invalid_encoding(
        self, fs_adapter, temp_log_dir
    ):
        """Test processing files with invalid encoding."""
        # Create a test log file with invalid encoding
        test_log_file = temp_log_dir / "test.log"
        with open(test_log_file, "wb") as f:
            f.write(b"\xff\xfe\x00\x00")  # Invalid UTF-8

        # Mock the callback
        mock_callback = AsyncMock()
        fs_adapter.callback = mock_callback

        # Process the files - should handle encoding errors gracefully
        await fs_adapter._process_files()

        # Callback should not be called due to encoding error
        mock_callback.assert_not_called()

        # Check that error count increased
        metrics = await fs_adapter.get_metrics()
        assert metrics["errors"] > 0


class TestIntegration:
    """Integration tests for the ingestion system."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary directory for test logs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.mark.asyncio
    async def test_full_ingestion_workflow(self, temp_log_dir):
        """Test a complete ingestion workflow."""
        # Create test log files
        test_log_file = temp_log_dir / "app.log"
        with open(test_log_file, "w") as f:
            f.write("2024-01-01 10:00:00 INFO Application started\n")
            f.write("2024-01-01 10:01:00 ERROR Database connection failed\n")
            f.write("2024-01-01 10:02:00 INFO User login successful\n")

        # Create configuration
        config = FileSystemConfig(
            name="integration-test",
            type=SourceType.FILE_SYSTEM,
            file_path=str(temp_log_dir),
            file_pattern="*.log",
            watch_mode=False,
        )

        # Create adapter
        adapter = FileSystemAdapter(config)

        # Create manager with callback
        processed_logs = []

        async def log_callback(log_entry):
            processed_logs.append(log_entry)

        manager = LogManager(callback=log_callback)
        await manager.add_source(adapter)

        # Start the manager
        await manager.start()

        # Process logs
        await adapter._process_files()

        # Stop the manager
        await manager.stop()

        # Verify results
        assert len(processed_logs) == 3

        # Check first log entry
        assert processed_logs[0].message == "Application started"
        assert processed_logs[0].level == LogSeverity.INFO
        assert processed_logs[0].source == "integration-test"

        # Check second log entry
        assert processed_logs[1].message == "Database connection failed"
        assert processed_logs[1].level == LogSeverity.ERROR

        # Check third log entry
        assert processed_logs[2].message == "User login successful"
        assert processed_logs[2].level == LogSeverity.INFO

        # Verify all entries have flow IDs
        for log_entry in processed_logs:
            assert log_entry.flow_id is not None
            assert log_entry.timestamp is not None

    @pytest.mark.asyncio
    async def test_multiple_sources_integration(self, temp_log_dir):
        """Test integration with multiple sources."""
        # Create multiple test log files
        app_log = temp_log_dir / "app.log"
        error_log = temp_log_dir / "error.log"

        with open(app_log, "w") as f:
            f.write("2024-01-01 10:00:00 INFO App message\n")

        with open(error_log, "w") as f:
            f.write("2024-01-01 10:00:00 ERROR Error message\n")

        # Create configurations for different sources
        app_config = FileSystemConfig(
            name="app-logs",
            type=SourceType.FILE_SYSTEM,
            file_path=str(temp_log_dir),
            file_pattern="app.log",
            watch_mode=False,
        )

        error_config = FileSystemConfig(
            name="error-logs",
            type=SourceType.FILE_SYSTEM,
            file_path=str(temp_log_dir),
            file_pattern="error.log",
            watch_mode=False,
        )

        # Create adapters
        app_adapter = FileSystemAdapter(app_config)
        error_adapter = FileSystemAdapter(error_config)

        # Create manager
        processed_logs = []

        async def log_callback(log_entry):
            processed_logs.append(log_entry)

        manager = LogManager(callback=log_callback)
        await manager.add_source(app_adapter)
        await manager.add_source(error_adapter)

        # Start the manager
        await manager.start()

        # Process logs from both sources
        await app_adapter._process_files()
        await error_adapter._process_files()

        # Stop the manager
        await manager.stop()

        # Verify results
        assert len(processed_logs) == 2

        # Check that logs from both sources were processed
        sources = {log.source for log in processed_logs}
        assert "app-logs" in sources
        assert "error-logs" in sources

        # Check health status
        health = await manager.get_health_status()
        assert "app-logs" in health
        assert "error-logs" in health
        assert health["app-logs"].is_healthy is True
        assert health["error-logs"].is_healthy is True

        # Check metrics
        metrics = await manager.get_metrics()
        assert "app-logs" in metrics["sources"]
        assert "error-logs" in metrics["sources"]
        assert metrics["sources"]["app-logs"]["processed"] == 1
        assert metrics["sources"]["error-logs"]["processed"] == 1
