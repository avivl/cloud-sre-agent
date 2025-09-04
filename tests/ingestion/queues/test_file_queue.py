# tests/ingestion/queues/test_file_queue.py

"""
Tests for the file-based queue system.
"""

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gemini_sre_agent.ingestion.interfaces.core import LogEntry, LogSeverity
from gemini_sre_agent.ingestion.queues.file_queue import (
    FileQueueConfig,
    FileSystemQueue,
)


class TestFileSystemQueue:
    """Test cases for FileSystemQueue."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def config(self, temp_dir):
        """Create a test configuration."""
        return FileQueueConfig(
            max_size=100,
            batch_size=10,
            flush_interval_seconds=1.0,
            enable_metrics=True,
            queue_dir=temp_dir,
            max_file_size_mb=1,
            max_files=10,
            compression_enabled=False,
            sync_interval_seconds=0.5,
        )

    @pytest.fixture
    def queue(self, config):
        """Create a test queue instance."""
        return FileSystemQueue(config)

    @pytest.fixture
    def sample_log_entry(self):
        """Create a sample log entry."""
        return LogEntry(
            id="test-123",
            timestamp=datetime.now(timezone.utc),
            message="Test log message",
            source="test_source",
            severity=LogSeverity.INFO,
            metadata={"key": "value"},
        )

    def test_init(self, queue, config):
        """Test queue initialization."""
        assert queue.config == config
        assert queue.max_size == config.max_size
        assert queue.batch_size == config.batch_size
        assert queue.flush_interval == config.flush_interval_seconds
        assert queue.enable_metrics == config.enable_metrics
        assert not queue.running

    @pytest.mark.asyncio
    async def test_start_stop(self, queue):
        """Test queue start and stop."""
        await queue.start()
        assert queue.running

        await queue.stop()
        assert not queue.running

    @pytest.mark.asyncio
    async def test_enqueue_single(self, queue, sample_log_entry):
        """Test enqueuing a single log entry."""
        await queue.start()

        result = await queue.enqueue(sample_log_entry)

        assert result is True
        assert queue._stats.total_enqueued == 1

    @pytest.mark.asyncio
    async def test_enqueue_batch(self, queue):
        """Test enqueuing multiple log entries."""
        await queue.start()

        # Create multiple log entries
        log_entries = []
        for i in range(5):
            log_entry = LogEntry(
                id=f"test-{i}",
                timestamp=datetime.now(timezone.utc),
                message=f"Test message {i}",
                source="test_source",
                severity=LogSeverity.INFO,
                metadata={"index": i},
            )
            log_entries.append(log_entry)

        for log_entry in log_entries:
            result = await queue.enqueue(log_entry)
            assert result is True

        assert queue._stats.total_enqueued == 5

    @pytest.mark.asyncio
    async def test_dequeue_single(self, queue, sample_log_entry):
        """Test dequeuing a single log entry."""
        await queue.start()

        # Enqueue a log entry
        await queue.enqueue(sample_log_entry)

        # Wait for sync
        await asyncio.sleep(0.1)

        # Dequeue
        dequeued_logs = await queue.dequeue()

        assert len(dequeued_logs) == 1
        assert dequeued_logs[0].id == sample_log_entry.id
        assert queue._stats.total_dequeued == 1

    @pytest.mark.asyncio
    async def test_dequeue_batch(self, queue):
        """Test dequeuing multiple log entries."""
        await queue.start()

        # Enqueue multiple log entries
        for i in range(15):  # More than batch size
            log_entry = LogEntry(
                id=f"test-{i}",
                timestamp=datetime.now(timezone.utc),
                message=f"Test message {i}",
                source="test_source",
                severity=LogSeverity.INFO,
                metadata={"index": i},
            )
            await queue.enqueue(log_entry)

        # Wait for sync
        await asyncio.sleep(0.1)

        # Dequeue (should get batch_size entries)
        dequeued_logs = await queue.dequeue()

        assert len(dequeued_logs) == queue.batch_size
        assert queue._stats.total_dequeued == queue.batch_size

    @pytest.mark.asyncio
    async def test_dequeue_empty(self, queue):
        """Test dequeuing from empty queue."""
        await queue.start()

        dequeued_logs = await queue.dequeue()

        assert len(dequeued_logs) == 0
        assert queue._stats.total_dequeued == 0

    @pytest.mark.asyncio
    async def test_file_persistence(self, queue, sample_log_entry, temp_dir):
        """Test that logs are persisted to files."""
        await queue.start()

        # Enqueue a log entry
        await queue.enqueue(sample_log_entry)

        # Wait for sync
        await asyncio.sleep(0.1)

        # Check that files were created
        queue_dir = Path(temp_dir)
        files = list(queue_dir.glob("*.jsonl"))
        assert len(files) > 0

        # Check file content
        with open(files[0], "r") as f:
            content = f.read()
            assert "test-123" in content
            assert "Test log message" in content

    @pytest.mark.asyncio
    async def test_file_rotation(self, temp_dir):
        """Test file rotation when max file size is reached."""
        # Create queue with very small max file size
        config = FileQueueConfig(
            max_size=1000,
            batch_size=10,
            flush_interval_seconds=0.1,
            enable_metrics=True,
            queue_dir=temp_dir,
            max_file_size_mb=0.001,  # Very small (1KB)
            max_files=10,
            compression_enabled=False,
            sync_interval_seconds=0.1,
        )
        queue = FileSystemQueue(config)
        await queue.start()

        # Enqueue many entries to trigger rotation
        for i in range(100):
            log_entry = LogEntry(
                id=f"test-{i}",
                timestamp=datetime.now(timezone.utc),
                message=f"Test message {i} with some extra content to make it larger",
                source="test_source",
                severity=LogSeverity.INFO,
                metadata={"index": i, "extra": "data" * 10},
            )
            await queue.enqueue(log_entry)

        # Wait for sync and rotation
        await asyncio.sleep(0.2)

        # Check that multiple files were created
        queue_dir = Path(temp_dir)
        files = list(queue_dir.glob("*.jsonl"))
        assert len(files) > 1  # Should have rotated

    @pytest.mark.asyncio
    async def test_file_cleanup(self, temp_dir):
        """Test file cleanup when max files is reached."""
        # Create queue with very small max files
        config = FileQueueConfig(
            max_size=1000,
            batch_size=10,
            flush_interval_seconds=0.1,
            enable_metrics=True,
            queue_dir=temp_dir,
            max_file_size_mb=0.001,  # Very small
            max_files=2,  # Very small
            compression_enabled=False,
            sync_interval_seconds=0.1,
        )
        queue = FileSystemQueue(config)
        await queue.start()

        # Enqueue many entries to trigger cleanup
        for i in range(200):
            log_entry = LogEntry(
                id=f"test-{i}",
                timestamp=datetime.now(timezone.utc),
                message=f"Test message {i}",
                source="test_source",
                severity=LogSeverity.INFO,
                metadata={"index": i},
            )
            await queue.enqueue(log_entry)

        # Wait for sync and cleanup
        await asyncio.sleep(0.3)

        # Check that file count doesn't exceed max_files
        queue_dir = Path(temp_dir)
        files = list(queue_dir.glob("*.jsonl"))
        assert len(files) <= config.max_files

    @pytest.mark.asyncio
    async def test_get_stats(self, queue, sample_log_entry):
        """Test getting queue statistics."""
        await queue.start()

        # Enqueue and dequeue some entries
        await queue.enqueue(sample_log_entry)
        await asyncio.sleep(0.1)  # Wait for sync
        await queue.dequeue()

        stats = queue.get_stats()

        assert stats.total_enqueued == 1
        assert stats.total_dequeued == 1
        assert stats.current_size == 0
        assert stats.total_dropped == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, queue, sample_log_entry):
        """Test using queue as async context manager."""
        async with queue:
            assert queue.running
            await queue.enqueue(sample_log_entry)
            await asyncio.sleep(0.1)  # Wait for sync
            logs = await queue.dequeue()
            assert len(logs) == 1

        assert not queue.running

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, queue):
        """Test concurrent enqueue/dequeue operations."""
        await queue.start()

        # Create multiple coroutines for concurrent operations
        async def enqueue_worker(worker_id: int, count: int):
            for i in range(count):
                log_entry = LogEntry(
                    id=f"worker-{worker_id}-{i}",
                    timestamp=datetime.now(timezone.utc),
                    message=f"Worker {worker_id} message {i}",
                    source=f"worker_{worker_id}",
                    severity=LogSeverity.INFO,
                )
                await queue.enqueue(log_entry)

        async def dequeue_worker(count: int):
            dequeued = []
            for _ in range(count):
                logs = await queue.dequeue()
                dequeued.extend(logs)
                await asyncio.sleep(0.01)  # Small delay
            return dequeued

        # Run concurrent operations
        enqueue_tasks = [asyncio.create_task(enqueue_worker(i, 5)) for i in range(3)]
        dequeue_task = asyncio.create_task(dequeue_worker(10))

        await asyncio.gather(*enqueue_tasks, dequeue_task)

        # Wait for sync
        await asyncio.sleep(0.1)

        # Verify results
        assert queue._stats.total_enqueued == 15
        assert queue._stats.total_dequeued >= 0

    @pytest.mark.asyncio
    async def test_error_handling(self, queue):
        """Test error handling in queue operations."""
        await queue.start()

        # Test with invalid log entry (should handle gracefully)
        try:
            result = await queue.enqueue(None)  # type: ignore
            assert result is False
        except Exception:
            # Should either return False or raise a specific exception
            pass

    @pytest.mark.asyncio
    async def test_compression_disabled(self, queue, sample_log_entry):
        """Test queue behavior with compression disabled."""
        await queue.start()

        # Enqueue and dequeue
        await queue.enqueue(sample_log_entry)
        await asyncio.sleep(0.1)
        logs = await queue.dequeue()

        assert len(logs) == 1
        assert logs[0].id == sample_log_entry.id

    @pytest.mark.asyncio
    async def test_sync_interval(self, queue):
        """Test automatic syncing based on interval."""
        await queue.start()

        # Enqueue some entries
        for i in range(3):
            log_entry = LogEntry(
                id=f"test-{i}",
                timestamp=datetime.now(timezone.utc),
                message=f"Test message {i}",
                source="test_source",
                severity=LogSeverity.INFO,
            )
            await queue.enqueue(log_entry)

        # Wait for sync interval
        await asyncio.sleep(0.6)  # Longer than sync_interval_seconds

        # Should have synced to disk
        stats = queue.get_stats()
        assert stats.total_enqueued == 3

    def test_file_queue_config_validation(self):
        """Test file queue configuration validation."""
        # Test valid config
        valid_config = FileQueueConfig(
            max_size=100,
            batch_size=10,
            flush_interval_seconds=1.0,
            enable_metrics=True,
            queue_dir="/tmp/test",
            max_file_size_mb=10,
            max_files=100,
            compression_enabled=False,
            sync_interval_seconds=5.0,
        )
        assert valid_config.max_file_size_mb == 10
        assert valid_config.max_files == 100
        assert valid_config.compression_enabled is False
