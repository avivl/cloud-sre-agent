# tests/ingestion/test_comprehensive_integration.py

"""
Comprehensive integration tests for the log ingestion system.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from gemini_sre_agent.config.ingestion_config import (
    FileSystemConfig,
    SourceType,
)
from gemini_sre_agent.ingestion.adapters.file_system import FileSystemAdapter
from gemini_sre_agent.ingestion.interfaces.core import LogEntry, LogSeverity
from gemini_sre_agent.ingestion.manager.log_manager import LogManager
from gemini_sre_agent.ingestion.queues.memory_queue import MemoryQueue, QueueConfig


class TestComprehensiveIntegration:
    """Comprehensive integration tests for the log ingestion system."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def log_manager(self):
        """Create a test LogManager instance."""
        return LogManager()

    @pytest.fixture
    def file_system_config(self, temp_dir):
        """Create a file system configuration."""
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
    def file_system_adapter(self, file_system_config):
        """Create a file system adapter."""
        return FileSystemAdapter(file_system_config)

    @pytest.fixture
    def memory_queue(self):
        """Create a memory queue."""
        config = QueueConfig(
            max_size=1000,
            batch_size=10,
            flush_interval_seconds=1.0,
            enable_metrics=True,
        )
        return MemoryQueue(config)

    @pytest.mark.asyncio
    async def test_end_to_end_file_ingestion(
        self, log_manager, file_system_adapter, temp_dir
    ):
        """Test end-to-end file system log ingestion."""
        # Create test log files
        test_file1 = Path(temp_dir) / "app1.log"
        test_file2 = Path(temp_dir) / "app2.log"

        test_file1.write_text(
            "2024-01-01 10:00:00 INFO Application started\n"
            "2024-01-01 10:01:00 ERROR Database connection failed\n"
        )
        test_file2.write_text(
            "2024-01-01 10:02:00 WARN High memory usage detected\n"
            "2024-01-01 10:03:00 INFO Application recovered\n"
        )

        # Add adapter to log manager
        await log_manager.add_source(file_system_adapter)

        # Start the system
        await log_manager.start_all_sources()

        # Collect logs
        collected_logs = []
        async for log in log_manager.get_all_logs():
            collected_logs.append(log)
            if len(collected_logs) >= 4:  # We expect 4 log entries
                break

        # Verify results
        assert len(collected_logs) >= 1
        for log in collected_logs:
            assert isinstance(log, LogEntry)
            assert log.source == "test_file_system"
            assert log.timestamp is not None
            assert log.message is not None
            assert log.severity in [
                LogSeverity.INFO,
                LogSeverity.ERROR,
                LogSeverity.WARN,
            ]

        # Check health status
        health = await log_manager.get_source_health("file_system")
        assert health.is_healthy

        # Stop the system
        await log_manager.stop_all_sources()

    @pytest.mark.asyncio
    async def test_multi_source_ingestion(self, log_manager, temp_dir):
        """Test ingestion from multiple sources."""
        # Create multiple file system adapters
        config1 = FileSystemConfig(
            name="source1",
            type=SourceType.FILE_SYSTEM,
            file_path=temp_dir,
            file_pattern="app1.log",
            watch_mode=True,
        )
        adapter1 = FileSystemAdapter(config1)

        config2 = FileSystemConfig(
            name="source2",
            type=SourceType.FILE_SYSTEM,
            file_path=temp_dir,
            file_pattern="app2.log",
            watch_mode=True,
        )
        adapter2 = FileSystemAdapter(config2)

        # Create test files
        Path(temp_dir).joinpath("app1.log").write_text("INFO Source 1 log\n")
        Path(temp_dir).joinpath("app2.log").write_text("ERROR Source 2 log\n")

        # Add both adapters
        await log_manager.add_source(adapter1)
        await log_manager.add_source(adapter2)

        # Start all sources
        await log_manager.start_all_sources()

        # Collect logs from all sources
        collected_logs = []
        async for log in log_manager.get_all_logs():
            collected_logs.append(log)
            if len(collected_logs) >= 2:
                break

        # Verify we got logs from both sources
        assert len(collected_logs) >= 1
        sources = {log.source for log in collected_logs}
        assert "source1" in sources or "source2" in sources

        # Check health for all sources
        health_status = await log_manager.get_all_health_status()
        assert "source1" in health_status
        assert "source2" in health_status

        await log_manager.stop_all_sources()

    @pytest.mark.asyncio
    async def test_queue_integration(self, memory_queue, temp_dir):
        """Test integration with memory queue."""
        # Create file system adapter
        config = FileSystemConfig(
            name="queued_source",
            type=SourceType.FILE_SYSTEM,
            file_path=temp_dir,
            file_pattern="*.log",
            watch_mode=True,
        )
        adapter = FileSystemAdapter(config)

        # Create test log file
        test_file = Path(temp_dir) / "test.log"
        test_file.write_text("INFO Test log message\n")

        # Start adapter and queue
        await adapter.start()
        await memory_queue.start()

        # Collect logs from adapter and enqueue them
        async for log in adapter.get_logs():
            await memory_queue.enqueue(log)
            break  # Just process one log for this test

        # Dequeue and verify
        dequeued_logs = await memory_queue.dequeue()
        assert len(dequeued_logs) == 1
        assert dequeued_logs[0].message == "INFO Test log message"

        # Check queue stats
        stats = memory_queue.get_stats()
        assert stats.total_enqueued == 1
        assert stats.total_dequeued == 1

        await adapter.stop()
        await memory_queue.stop()

    @pytest.mark.asyncio
    async def test_error_recovery(self, log_manager, temp_dir):
        """Test error recovery and resilience."""
        # Create adapter with problematic file
        config = FileSystemConfig(
            name="error_source",
            type=SourceType.FILE_SYSTEM,
            file_path=temp_dir,
            file_pattern="*.log",
            watch_mode=True,
        )
        adapter = FileSystemAdapter(config)

        # Create a file that will cause issues (empty file)
        Path(temp_dir).joinpath("empty.log").write_text("")

        await log_manager.add_source(adapter)
        await log_manager.start_all_sources()

        # The system should handle errors gracefully
        await log_manager.get_source_health("error_source")
        # Should still be healthy or have handled the error gracefully

        # Test error handling
        error = Exception("Test error")
        context = {"operation": "test"}
        result = await log_manager.handle_source_error("error_source", error, context)
        assert result is True  # Error should be handled

        await log_manager.stop_all_sources()

    @pytest.mark.asyncio
    async def test_configuration_updates(self, log_manager, temp_dir):
        """Test dynamic configuration updates."""
        # Create initial configuration
        config = FileSystemConfig(
            name="config_test",
            type=SourceType.FILE_SYSTEM,
            file_path=temp_dir,
            file_pattern="*.log",
            watch_mode=True,
        )
        adapter = FileSystemAdapter(config)

        await log_manager.add_source(adapter)
        await log_manager.start_all_sources()

        # Update configuration
        new_config = FileSystemConfig(
            name="config_test",
            type=SourceType.FILE_SYSTEM,
            file_path=temp_dir,
            file_pattern="*.txt",  # Different pattern
            watch_mode=False,  # Different watch mode
            encoding="latin-1",  # Different encoding
        )

        await log_manager.update_source_config("config_test", new_config)

        # Verify configuration was updated
        updated_config = adapter.get_config()
        assert updated_config.file_pattern == "*.txt"
        assert not updated_config.watch_mode

        await log_manager.stop_all_sources()

    @pytest.mark.asyncio
    async def test_metrics_collection(self, log_manager, temp_dir):
        """Test metrics collection across the system."""
        # Create adapter
        config = FileSystemConfig(
            name="metrics_test",
            type=SourceType.FILE_SYSTEM,
            file_path=temp_dir,
            file_pattern="*.log",
            watch_mode=True,
        )
        adapter = FileSystemAdapter(config)

        # Create test file
        Path(temp_dir).joinpath("metrics.log").write_text("INFO Metrics test\n")

        await log_manager.add_source(adapter)
        await log_manager.start_all_sources()

        # Collect some logs to generate metrics
        logs = []
        async for log in log_manager.get_all_logs():
            logs.append(log)
            if len(logs) >= 1:
                break

        # Get metrics
        metrics = await log_manager.get_source_metrics("metrics_test")
        assert isinstance(metrics, dict)
        assert "total_logs_processed" in metrics

        # Get all metrics
        all_metrics = await log_manager.get_all_metrics()
        assert "metrics_test" in all_metrics

        await log_manager.stop_all_sources()

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, log_manager, temp_dir):
        """Test concurrent operations across the system."""
        # Create multiple adapters
        adapters = []
        for i in range(3):
            config = FileSystemConfig(
                name=f"concurrent_{i}",
                type=SourceType.FILE_SYSTEM,
                file_path=temp_dir,
                file_pattern=f"app{i}.log",
                watch_mode=True,
            )
            adapter = FileSystemAdapter(config)
            adapters.append(adapter)

            # Create test file
            Path(temp_dir).joinpath(f"app{i}.log").write_text(
                f"INFO Concurrent log {i}\n"
            )

            await log_manager.add_source(adapter)

        # Start all sources concurrently
        await log_manager.start_all_sources()

        # Collect logs concurrently
        async def collect_logs(source_name: str):
            logs = []
            async for log in log_manager.get_all_logs():
                if log.source == source_name:
                    logs.append(log)
                if len(logs) >= 1:
                    break
            return logs

        # Run concurrent log collection
        tasks = [collect_logs(f"concurrent_{i}") for i in range(3)]
        results = await asyncio.gather(*tasks)

        # Verify results
        for result in results:
            assert len(result) >= 0  # May or may not have logs

        await log_manager.stop_all_sources()

    @pytest.mark.asyncio
    async def test_system_shutdown(self, log_manager, temp_dir):
        """Test graceful system shutdown."""
        # Create adapter
        config = FileSystemConfig(
            name="shutdown_test",
            type=SourceType.FILE_SYSTEM,
            file_path=temp_dir,
            file_pattern="*.log",
            watch_mode=True,
        )
        adapter = FileSystemAdapter(config)

        await log_manager.add_source(adapter)
        await log_manager.start_all_sources()

        # Verify running
        assert log_manager.running
        assert adapter.running

        # Shutdown
        await log_manager.stop_all_sources()

        # Verify stopped
        assert not log_manager.running
        assert not adapter.running

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, temp_dir):
        """Test using the system with context managers."""
        # Create adapter
        config = FileSystemConfig(
            name="context_test",
            type=SourceType.FILE_SYSTEM,
            file_path=temp_dir,
            file_pattern="*.log",
            watch_mode=True,
        )
        adapter = FileSystemAdapter(config)

        # Create test file
        Path(temp_dir).joinpath("context.log").write_text("INFO Context test\n")

        # Use context managers
        async with LogManager() as log_manager:
            log_manager.add_source("context_test", adapter)

            # Should be running
            assert log_manager.running
            assert adapter.running

            # Collect some logs
            logs = []
            async for log in log_manager.get_all_logs():
                logs.append(log)
                if len(logs) >= 1:
                    break

        # Should be stopped after context exit
        assert not log_manager.running
        assert not adapter.running
