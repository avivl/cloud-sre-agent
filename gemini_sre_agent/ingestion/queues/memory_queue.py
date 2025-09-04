# gemini_sre_agent/ingestion/queues/memory_queue.py

"""
In-memory queue system for log buffering and backpressure management.
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..interfaces.core import LogEntry

logger = logging.getLogger(__name__)


@dataclass
class QueueConfig:
    """Configuration for memory queue."""

    max_size: int = 10000
    max_memory_mb: int = 100
    batch_size: int = 100
    flush_interval_seconds: float = 1.0
    enable_metrics: bool = True


@dataclass
class QueueStats:
    """Statistics for queue performance."""

    total_enqueued: int = 0
    total_dequeued: int = 0
    current_size: int = 0
    max_size_reached: int = 0
    dropped_count: int = 0
    last_enqueue_time: Optional[datetime] = None
    last_dequeue_time: Optional[datetime] = None
    average_processing_time_ms: float = 0.0
    memory_usage_mb: float = 0.0


class MemoryQueue:
    """Thread-safe in-memory queue for log entries with backpressure management."""

    def __init__(self, config: QueueConfig):
        self.config = config
        self._queue: deque = deque(maxlen=config.max_size)
        self._lock = asyncio.Lock()
        self._stats = QueueStats()
        self._processing_times: deque = deque(
            maxlen=100
        )  # Keep last 100 processing times
        self._shutdown = False

        # Start background tasks
        self._flush_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the queue and background tasks."""
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())

        if self._metrics_task is None and self.config.enable_metrics:
            self._metrics_task = asyncio.create_task(self._metrics_loop())

        logger.info(f"Started memory queue with max_size={self.config.max_size}")

    async def stop(self) -> None:
        """Stop the queue and background tasks."""
        self._shutdown = True

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped memory queue")

    async def enqueue(self, log_entry: LogEntry) -> bool:
        """
        Enqueue a log entry.

        Returns:
            True if enqueued successfully, False if dropped due to backpressure
        """
        if self._shutdown:
            return False

        async with self._lock:
            # Check if queue is full
            if len(self._queue) >= self.config.max_size:
                self._stats.dropped_count += 1
                logger.warning(f"Queue full, dropping log entry: {log_entry.id}")
                return False

            # Add to queue
            self._queue.append(log_entry)
            self._stats.total_enqueued += 1
            self._stats.current_size = len(self._queue)
            self._stats.max_size_reached = max(
                self._stats.max_size_reached, len(self._queue)
            )
            self._stats.last_enqueue_time = datetime.now(timezone.utc)

            return True

    async def dequeue(self, max_items: Optional[int] = None) -> list[LogEntry]:
        """
        Dequeue log entries.

        Args:
            max_items: Maximum number of items to dequeue (defaults to batch_size)

        Returns:
            List of dequeued log entries
        """
        if max_items is None:
            max_items = self.config.batch_size

        start_time = datetime.now(timezone.utc)

        async with self._lock:
            items = []
            for _ in range(min(max_items, len(self._queue))):
                if self._queue:
                    items.append(self._queue.popleft())

            if items:
                self._stats.total_dequeued += len(items)
                self._stats.current_size = len(self._queue)
                self._stats.last_dequeue_time = datetime.now(timezone.utc)

                # Track processing time
                processing_time = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds() * 1000
                self._processing_times.append(processing_time)

                # Update average processing time
                if self._processing_times:
                    self._stats.average_processing_time_ms = sum(
                        self._processing_times
                    ) / len(self._processing_times)

        return items

    async def peek(self, count: int = 1) -> list[LogEntry]:
        """Peek at the next items without removing them."""
        async with self._lock:
            return list(self._queue)[:count]

    async def clear(self) -> int:
        """Clear the queue and return the number of items cleared."""
        async with self._lock:
            cleared_count = len(self._queue)
            self._queue.clear()
            self._stats.current_size = 0
            return cleared_count

    def get_stats(self) -> QueueStats:
        """Get current queue statistics."""
        return QueueStats(
            total_enqueued=self._stats.total_enqueued,
            total_dequeued=self._stats.total_dequeued,
            current_size=self._stats.current_size,
            max_size_reached=self._stats.max_size_reached,
            dropped_count=self._stats.dropped_count,
            last_enqueue_time=self._stats.last_enqueue_time,
            last_dequeue_time=self._stats.last_dequeue_time,
            average_processing_time_ms=self._stats.average_processing_time_ms,
            memory_usage_mb=self._stats.memory_usage_mb,
        )

    def is_full(self) -> bool:
        """Check if the queue is full."""
        return len(self._queue) >= self.config.max_size

    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return len(self._queue) == 0

    def size(self) -> int:
        """Get current queue size."""
        return len(self._queue)

    async def _flush_loop(self) -> None:
        """Background task to periodically flush metrics and perform maintenance."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.flush_interval_seconds)

                # Perform any periodic maintenance here
                # For now, just log stats periodically
                if self._stats.current_size > 0:
                    logger.debug(
                        f"Queue stats: size={self._stats.current_size}, "
                        f"enqueued={self._stats.total_enqueued}, "
                        f"dequeued={self._stats.total_dequeued}"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")

    async def _metrics_loop(self) -> None:
        """Background task to update memory usage metrics."""
        while not self._shutdown:
            try:
                await asyncio.sleep(5.0)  # Update every 5 seconds

                # Estimate memory usage (rough calculation)
                # Each LogEntry is roughly 1KB, so multiply by queue size
                estimated_memory_kb = len(self._queue) * 1.0
                self._stats.memory_usage_mb = estimated_memory_kb / 1024.0

                # Check if we're approaching memory limit
                if self._stats.memory_usage_mb > self.config.max_memory_mb * 0.8:
                    logger.warning(
                        f"Queue memory usage high: {self._stats.memory_usage_mb:.2f}MB "
                        f"(limit: {self.config.max_memory_mb}MB)"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics loop: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
