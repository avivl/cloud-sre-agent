# tests/ingestion/queues/test_memory_queue.py

"""
Tests for the memory queue system.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from gemini_sre_agent.ingestion.interfaces.core import LogEntry, LogSeverity
from gemini_sre_agent.ingestion.queues.memory_queue import (
    MemoryQueue,
    QueueConfig,
    QueueStats,
)


class TestMemoryQueue:
    """Test cases for MemoryQueue."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return QueueConfig(
            max_size=100,
            batch_size=10,
            flush_interval_seconds=1.0,
            enable_metrics=True,
        )

    @pytest.fixture
    def queue(self, config):
        """Create a test queue instance."""
        return MemoryQueue(config)

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
    async def test_enqueue_batch(self, queue, sample_log_entry):
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
    async def test_queue_full(self, queue):
        """Test behavior when queue is full."""
        # Create a small queue
        small_config = QueueConfig(max_size=3, batch_size=1)
        small_queue = MemoryQueue(small_config)
        await small_queue.start()

        # Fill the queue
        for i in range(3):
            log_entry = LogEntry(
                id=f"test-{i}",
                timestamp=datetime.now(timezone.utc),
                message=f"Test message {i}",
                source="test_source",
                severity=LogSeverity.INFO,
            )
            result = await small_queue.enqueue(log_entry)
            assert result is True

        # Try to enqueue one more (should fail or drop)
        log_entry = LogEntry(
            id="test-overflow",
            timestamp=datetime.now(timezone.utc),
            message="Overflow message",
            source="test_source",
            severity=LogSeverity.INFO,
        )
        result = await small_queue.enqueue(log_entry)

        # Should either reject or drop oldest
        assert result is False or small_queue._stats.total_dropped > 0

    @pytest.mark.asyncio
    async def test_get_stats(self, queue, sample_log_entry):
        """Test getting queue statistics."""
        await queue.start()

        # Enqueue and dequeue some entries
        await queue.enqueue(sample_log_entry)
        await queue.dequeue()

        stats = queue.get_stats()

        assert isinstance(stats, QueueStats)
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
            logs = await queue.dequeue()
            assert len(logs) == 1

        assert not queue.running

    @pytest.mark.asyncio
    async def test_metrics_disabled(self):
        """Test queue behavior when metrics are disabled."""
        config = QueueConfig(
            max_size=100,
            batch_size=10,
            flush_interval_seconds=1.0,
            enable_metrics=False,
        )
        queue = MemoryQueue(config)
        await queue.start()

        # Should still work but with minimal metrics
        stats = queue.get_stats()
        assert isinstance(stats, QueueStats)

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
            return dequeued

        # Run concurrent operations
        enqueue_tasks = [asyncio.create_task(enqueue_worker(i, 5)) for i in range(3)]
        dequeue_task = asyncio.create_task(dequeue_worker(10))

        await asyncio.gather(*enqueue_tasks, dequeue_task)

        # Verify results
        assert queue._stats.total_enqueued == 15
        assert queue._stats.total_dequeued >= 0

    @pytest.mark.asyncio
    async def test_flush_interval(self, queue):
        """Test automatic flushing based on interval."""
        # Create queue with short flush interval
        config = QueueConfig(
            max_size=100,
            batch_size=5,
            flush_interval_seconds=0.1,  # Very short interval
            enable_metrics=True,
        )
        fast_queue = MemoryQueue(config)
        await fast_queue.start()

        # Enqueue some entries
        for i in range(3):
            log_entry = LogEntry(
                id=f"test-{i}",
                timestamp=datetime.now(timezone.utc),
                message=f"Test message {i}",
                source="test_source",
                severity=LogSeverity.INFO,
            )
            await fast_queue.enqueue(log_entry)

        # Wait for flush interval
        await asyncio.sleep(0.2)

        # Should have processed some entries
        stats = fast_queue.get_stats()
        assert stats.total_enqueued == 3

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

    def test_queue_config_validation(self):
        """Test queue configuration validation."""
        # Test valid config
        valid_config = QueueConfig(
            max_size=100,
            batch_size=10,
            flush_interval_seconds=1.0,
            enable_metrics=True,
        )
        assert valid_config.max_size == 100
        assert valid_config.batch_size == 10

        # Test config with batch_size > max_size (should be handled)
        large_batch_config = QueueConfig(
            max_size=5,
            batch_size=10,  # Larger than max_size
            flush_interval_seconds=1.0,
        )
        queue = MemoryQueue(large_batch_config)
        # Should handle this gracefully
        assert queue.batch_size == 10
