# tests/ingestion/manager/test_log_manager.py

"""
Tests for the LogManager.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from gemini_sre_agent.config.ingestion_config import FileSystemConfig, SourceType
from gemini_sre_agent.ingestion.interfaces.core import (
    LogEntry,
    LogSeverity,
    SourceHealth,
)
from gemini_sre_agent.ingestion.interfaces.errors import (
    SourceAlreadyRunningError,
    SourceNotFoundError,
)
from gemini_sre_agent.ingestion.manager.log_manager import LogManager


class MockAdapter:
    """Mock adapter for testing."""

    def __init__(self, name: str, running: bool = False):
        self.name = name
        self.running = running
        self.logs = []
        self.health = SourceHealth(
            is_healthy=True,
            last_success=datetime.now(timezone.utc).isoformat(),
            error_count=0,
            last_error=None,
            metrics={},
        )

    async def start(self):
        self.running = True

    async def stop(self):
        self.running = False

    async def get_logs(self):
        for log in self.logs:
            yield log

    async def health_check(self) -> SourceHealth:
        return self.health

    async def update_config(self, config):
        pass

    async def handle_error(self, error, context):
        return True

    async def get_health_metrics(self):
        return {"status": "healthy"}

    def get_config(self):
        return FileSystemConfig(
            name=self.name,
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test",
            file_pattern="*.log",
            watch_mode=True,
        )


class TestLogManager:
    """Test cases for LogManager."""

    @pytest.fixture
    def log_manager(self):
        """Create a test LogManager instance."""
        return LogManager()

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock adapter."""
        return MockAdapter("test_adapter")

    def test_init(self, log_manager):
        """Test LogManager initialization."""
        assert log_manager.sources == {}
        assert log_manager.running is False
        assert log_manager._shutdown is False

    @pytest.mark.asyncio
    async def test_add_source(self, log_manager, mock_adapter):
        """Test adding a source."""
        await log_manager.add_source(mock_adapter)

        assert "test_adapter" in log_manager.sources
        assert log_manager.sources["test_adapter"] == mock_adapter

    @pytest.mark.asyncio
    async def test_add_source_duplicate(self, log_manager, mock_adapter):
        """Test adding a duplicate source."""
        await log_manager.add_source(mock_adapter)

        with pytest.raises(SourceAlreadyRunningError):
            await log_manager.add_source(mock_adapter)

    @pytest.mark.asyncio
    async def test_remove_source(self, log_manager, mock_adapter):
        """Test removing a source."""
        await log_manager.add_source(mock_adapter)

        await log_manager.remove_source("test_source")

        assert "test_source" not in log_manager.sources

    @pytest.mark.asyncio
    async def test_remove_source_not_found(self, log_manager):
        """Test removing a non-existent source."""
        with pytest.raises(SourceNotFoundError):
            await log_manager.remove_source("nonexistent_source")

    @pytest.mark.asyncio
    async def test_start_all_sources(self, log_manager):
        """Test starting all sources."""
        # Create multiple mock adapters
        adapter1 = MockAdapter("adapter1")
        adapter2 = MockAdapter("adapter2")

        await log_manager.add_source(adapter1)
        await log_manager.add_source(adapter2)

        await log_manager.start_all_sources()

        assert adapter1.running
        assert adapter2.running
        assert log_manager.running

    @pytest.mark.asyncio
    async def test_stop_all_sources(self, log_manager):
        """Test stopping all sources."""
        # Create and start mock adapters
        adapter1 = MockAdapter("adapter1", running=True)
        adapter2 = MockAdapter("adapter2", running=True)

        await log_manager.add_source(adapter1)
        await log_manager.add_source(adapter2)
        log_manager.running = True

        await log_manager.stop_all_sources()

        assert not adapter1.running
        assert not adapter2.running
        assert not log_manager.running

    @pytest.mark.asyncio
    async def test_get_all_logs(self, log_manager):
        """Test getting logs from all sources."""
        # Create mock adapters with logs
        adapter1 = MockAdapter("adapter1")
        adapter1.logs = [
            LogEntry(
                id="log1",
                timestamp=datetime.now(timezone.utc),
                message="Log from adapter1",
                source="adapter1",
                severity=LogSeverity.INFO,
                metadata={},
            )
        ]

        adapter2 = MockAdapter("adapter2")
        adapter2.logs = [
            LogEntry(
                id="log2",
                timestamp=datetime.now(timezone.utc),
                message="Log from adapter2",
                source="adapter2",
                severity=LogSeverity.ERROR,
                metadata={},
            )
        ]

        await log_manager.add_source(adapter1)
        await log_manager.add_source(adapter2)

        # Collect logs
        all_logs = []
        async for log in log_manager.get_all_logs():
            all_logs.append(log)
            if len(all_logs) >= 2:  # Limit to prevent infinite loop
                break

        assert len(all_logs) >= 1
        for log in all_logs:
            assert isinstance(log, LogEntry)

    @pytest.mark.asyncio
    async def test_get_source_health(self, log_manager, mock_adapter):
        """Test getting health status for a source."""
        await log_manager.add_source(mock_adapter)

        health = await log_manager.get_source_health("test_source")

        assert isinstance(health, SourceHealth)
        assert health.is_healthy

    @pytest.mark.asyncio
    async def test_get_source_health_not_found(self, log_manager):
        """Test getting health for non-existent source."""
        with pytest.raises(SourceNotFoundError):
            await log_manager.get_source_health("nonexistent_source")

    @pytest.mark.asyncio
    async def test_get_all_health_status(self, log_manager):
        """Test getting health status for all sources."""
        adapter1 = MockAdapter("adapter1")
        adapter2 = MockAdapter("adapter2")

        await log_manager.add_source(adapter1)
        await log_manager.add_source(adapter2)

        health_status = await log_manager.get_all_health_status()

        assert "source1" in health_status
        assert "source2" in health_status
        assert isinstance(health_status["source1"], SourceHealth)
        assert isinstance(health_status["source2"], SourceHealth)

    @pytest.mark.asyncio
    async def test_update_source_config(self, log_manager, mock_adapter):
        """Test updating source configuration."""
        await log_manager.add_source(mock_adapter)

        new_config = FileSystemConfig(
            name="updated_adapter",
            type=SourceType.FILE_SYSTEM,
            file_path="/new/path",
            file_pattern="*.txt",
            watch_mode=False,
        )

        await log_manager.update_source_config("test_source", new_config)

        # Verify the adapter's update_config was called
        # (In a real test, we'd mock this method)

    @pytest.mark.asyncio
    async def test_update_source_config_not_found(self, log_manager):
        """Test updating config for non-existent source."""
        new_config = FileSystemConfig(
            name="updated_adapter",
            type=SourceType.FILE_SYSTEM,
            file_path="/new/path",
            file_pattern="*.txt",
            watch_mode=False,
        )

        with pytest.raises(SourceNotFoundError):
            await log_manager.update_source_config("nonexistent_source", new_config)

    @pytest.mark.asyncio
    async def test_handle_source_error(self, log_manager, mock_adapter):
        """Test handling errors from sources."""
        await log_manager.add_source(mock_adapter)

        error = Exception("Test error")
        context = {"operation": "test"}

        result = await log_manager.handle_source_error("test_source", error, context)

        # Should return True (error was handled)
        assert result is True

    @pytest.mark.asyncio
    async def test_handle_source_error_not_found(self, log_manager):
        """Test handling error for non-existent source."""
        error = Exception("Test error")
        context = {"operation": "test"}

        with pytest.raises(SourceNotFoundError):
            await log_manager.handle_source_error("nonexistent_source", error, context)

    @pytest.mark.asyncio
    async def test_get_source_metrics(self, log_manager, mock_adapter):
        """Test getting metrics for a source."""
        await log_manager.add_source(mock_adapter)

        metrics = await log_manager.get_source_metrics("test_source")

        assert isinstance(metrics, dict)
        assert "status" in metrics

    @pytest.mark.asyncio
    async def test_get_source_metrics_not_found(self, log_manager):
        """Test getting metrics for non-existent source."""
        with pytest.raises(SourceNotFoundError):
            await log_manager.get_source_metrics("nonexistent_source")

    @pytest.mark.asyncio
    async def test_get_all_metrics(self, log_manager):
        """Test getting metrics for all sources."""
        adapter1 = MockAdapter("adapter1")
        adapter2 = MockAdapter("adapter2")

        await log_manager.add_source(adapter1)
        await log_manager.add_source(adapter2)

        all_metrics = await log_manager.get_all_metrics()

        assert "source1" in all_metrics
        assert "source2" in all_metrics
        assert isinstance(all_metrics["source1"], dict)
        assert isinstance(all_metrics["source2"], dict)

    @pytest.mark.asyncio
    async def test_list_sources(self, log_manager):
        """Test listing all sources."""
        adapter1 = MockAdapter("adapter1")
        adapter2 = MockAdapter("adapter2")

        await log_manager.add_source(adapter1)
        await log_manager.add_source(adapter2)

        sources = log_manager.list_sources()

        assert "source1" in sources
        assert "source2" in sources
        assert len(sources) == 2

    @pytest.mark.asyncio
    async def test_context_manager(self, log_manager):
        """Test using LogManager as async context manager."""
        adapter = MockAdapter("test_adapter")
        log_manager.add_source("test_source", adapter)

        async with log_manager:
            assert log_manager.running
            assert adapter.running

        assert not log_manager.running
        assert not adapter.running

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, log_manager):
        """Test concurrent operations on LogManager."""
        # Create multiple adapters
        adapters = [MockAdapter(f"adapter{i}") for i in range(5)]

        # Add all adapters concurrently
        tasks = []
        for _i, adapter in enumerate(adapters):
            task = asyncio.create_task(await log_manager.add_source(adapter))
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Verify all sources were added
        assert len(log_manager.sources) == 5

        # Start all sources concurrently
        await log_manager.start_all_sources()

        # Verify all are running
        for adapter in adapters:
            assert adapter.running

    @pytest.mark.asyncio
    async def test_error_handling_in_get_logs(self, log_manager):
        """Test error handling when getting logs from sources."""
        # Create adapter that raises an error
        error_adapter = MockAdapter("error_adapter")
        error_adapter.get_logs = AsyncMock(side_effect=Exception("Source error"))

        await log_manager.add_source(error_adapter)

        # Should handle errors gracefully
        logs = []
        async for log in log_manager.get_all_logs():
            logs.append(log)
            if len(logs) >= 1:  # Limit to prevent infinite loop
                break

        # Should not crash, even with source errors
        assert isinstance(logs, list)

    @pytest.mark.asyncio
    async def test_shutdown_handling(self, log_manager):
        """Test shutdown handling."""
        adapter = MockAdapter("test_adapter")
        log_manager.add_source("test_source", adapter)

        await log_manager.start_all_sources()
        assert log_manager.running

        # Simulate shutdown
        log_manager._shutdown = True
        await log_manager.stop_all_sources()

        assert not log_manager.running
        assert not adapter.running
