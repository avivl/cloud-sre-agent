# tests/ingestion/adapters/test_file_system.py

"""
Tests for the file system adapter.
"""

import tempfile
from pathlib import Path

import pytest

from gemini_sre_agent.config.ingestion_config import FileSystemConfig, SourceType
from gemini_sre_agent.ingestion.adapters.file_system import FileSystemAdapter
from gemini_sre_agent.ingestion.interfaces.core import (
    LogEntry,
    SourceHealth,
)
from gemini_sre_agent.ingestion.interfaces.errors import SourceConnectionError


class TestFileSystemAdapter:
    """Test cases for FileSystemAdapter."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def config(self, temp_dir):
        """Create a test configuration."""
        return FileSystemConfig(
            name="test_file_system",
            type=SourceType.FILE_SYSTEM,
            file_path=temp_dir,
            file_pattern="*.log",
            watch_mode=True,
            encoding="utf-8",
            buffer_size=1000,
            max_memory_mb=100,
        )

    @pytest.fixture
    def adapter(self, config):
        """Create a test adapter instance."""
        return FileSystemAdapter(config)

    def test_init(self, adapter, config):
        """Test adapter initialization."""
        assert adapter.config == config
        assert adapter.file_path == config.file_path
        assert adapter.file_pattern == config.file_pattern
        assert adapter.watch_mode == config.watch_mode
        assert not adapter._is_running

    @pytest.mark.asyncio
    async def test_start_success(self, adapter, temp_dir):
        """Test successful adapter start."""
        # Create a test log file
        test_file = Path(temp_dir) / "test.log"
        test_file.write_text("test log line\n")

        await adapter.start()

        assert adapter._is_running
        assert adapter._last_check_time is not None

    @pytest.mark.asyncio
    async def test_start_invalid_path(self, temp_dir):
        """Test adapter start with invalid path."""
        config = FileSystemConfig(
            name="test_file_system",
            type=SourceType.FILE_SYSTEM,
            file_path="/nonexistent/path",
            file_pattern="*.log",
        )
        adapter = FileSystemAdapter(config)

        with pytest.raises(SourceConnectionError):
            await adapter.start()

    @pytest.mark.asyncio
    async def test_stop(self, adapter):
        """Test adapter stop."""
        await adapter.start()
        assert adapter._is_running

        await adapter.stop()
        assert not adapter._is_running

    @pytest.mark.asyncio
    async def test_get_logs_empty(self, adapter, temp_dir):
        """Test getting logs when no files exist."""
        await adapter.start()

        logs = []
        async for log in adapter.get_logs():
            logs.append(log)
            if len(logs) >= 1:  # Limit to prevent infinite loop
                break

        # Should not raise an error even with no logs
        assert isinstance(logs, list)

    @pytest.mark.asyncio
    async def test_get_logs_with_content(self, adapter, temp_dir):
        """Test getting logs from files with content."""
        # Start adapter first
        await adapter.start()

        # Create test log files after starting (so they're detected as new content)
        test_file1 = Path(temp_dir) / "app1.log"
        test_file2 = Path(temp_dir) / "app2.log"

        test_file1.write_text("2024-01-01 10:00:00 INFO Application started\n")
        test_file2.write_text("2024-01-01 10:01:00 ERROR Database connection failed\n")

        logs = []
        async for log in adapter.get_logs():
            logs.append(log)
            if len(logs) >= 2:  # Limit to prevent infinite loop
                break

        assert len(logs) >= 1
        for log in logs:
            assert isinstance(log, LogEntry)
            assert log.source == "test_file_system"
            assert log.timestamp is not None

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, adapter, temp_dir):
        """Test health check when adapter is healthy."""
        await adapter.start()

        health = await adapter.health_check()

        assert isinstance(health, SourceHealth)
        assert health.is_healthy
        assert health.error_count == 0
        assert health.last_error is None

    @pytest.mark.asyncio
    async def test_health_check_stopped(self, adapter):
        """Test health check when adapter is stopped."""
        health = await adapter.health_check()

        assert isinstance(health, SourceHealth)
        assert not health.is_healthy
        assert "unhealthy" in health.last_error.lower()

    @pytest.mark.asyncio
    async def test_update_config(self, adapter):
        """Test configuration update."""
        new_config = FileSystemConfig(
            name="updated_file_system",
            type=SourceType.FILE_SYSTEM,
            file_path="/new/path",
            file_pattern="*.txt",
            watch_mode=False,
            encoding="latin-1",
            buffer_size=2000,
            max_memory_mb=200,
        )

        await adapter.update_config(new_config)

        assert adapter.config == new_config
        assert adapter.file_path == "/new/path"
        assert adapter.file_pattern == "*.txt"
        assert not adapter.watch_mode

    @pytest.mark.asyncio
    async def test_handle_error(self, adapter):
        """Test error handling."""
        error = Exception("Test error")
        context = {"operation": "test"}

        result = await adapter.handle_error(error, context)

        # File system errors are generally recoverable
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_get_health_metrics(self, adapter, temp_dir):
        """Test getting health metrics."""
        await adapter.start()

        metrics = await adapter.get_health_metrics()

        assert isinstance(metrics, dict)
        assert "total_logs_processed" in metrics
        assert "total_logs_failed" in metrics
        assert "last_check_time" in metrics
        assert "watched_files_count" in metrics
        assert "resilience_stats" in metrics

    def test_get_config(self, adapter, config):
        """Test getting configuration."""
        returned_config = adapter.get_config()
        assert returned_config == config

    @pytest.mark.asyncio
    async def test_file_pattern_matching(self, temp_dir):
        """Test file pattern matching functionality."""
        config = FileSystemConfig(
            name="test_file_system",
            type=SourceType.FILE_SYSTEM,
            file_path=temp_dir,
            file_pattern="app*.log",
            watch_mode=True,
        )
        adapter = FileSystemAdapter(config)

        # Create files with different patterns
        Path(temp_dir).joinpath("app1.log").write_text("log1\n")
        Path(temp_dir).joinpath("app2.log").write_text("log2\n")
        Path(temp_dir).joinpath("other.txt").write_text("not a log\n")

        await adapter.start()

        # Should only process files matching the pattern
        files = adapter._get_files_to_process()
        file_names = [Path(f).name for f in files]

        assert "app1.log" in file_names
        assert "app2.log" in file_names
        assert "other.txt" not in file_names

    @pytest.mark.asyncio
    async def test_large_file_handling(self, temp_dir):
        """Test handling of large files."""
        config = FileSystemConfig(
            name="test_file_system",
            type=SourceType.FILE_SYSTEM,
            file_path=temp_dir,
            file_pattern="*.log",
            max_memory_mb=1,  # 1MB limit
        )
        adapter = FileSystemAdapter(config)

        # Create a large file (simulate with a smaller test)
        large_file = Path(temp_dir) / "large.log"
        large_content = "test log line\n" * 1000  # Create substantial content
        large_file.write_text(large_content)

        await adapter.start()

        # Should handle large files gracefully
        health = await adapter.health_check()
        assert health.is_healthy
