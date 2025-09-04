# gemini_sre_agent/ingestion/queues/file_queue.py

"""
File-based queue system for persistent log buffering.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..interfaces.core import LogEntry
from .memory_queue import QueueConfig, QueueStats

logger = logging.getLogger(__name__)


@dataclass
class FileQueueConfig(QueueConfig):
    """Configuration for file-based queue."""

    queue_dir: str = "/tmp/log_queue"
    max_file_size_mb: int = 10
    max_files: int = 100
    compression_enabled: bool = False
    sync_interval_seconds: float = 5.0


class FileSystemQueue:
    """File-based persistent queue for log entries."""

    def __init__(self, config: FileQueueConfig):
        self.config = config
        self.queue_dir = Path(config.queue_dir)
        self.current_file: Optional[Path] = None
        self.current_file_size = 0
        self._lock = asyncio.Lock()
        self._stats = QueueStats()
        self._shutdown = False

        # Ensure queue directory exists
        self.queue_dir.mkdir(parents=True, exist_ok=True)

        # Start background tasks
        self._sync_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the file queue and background tasks."""
        if self._sync_task is None:
            self._sync_task = asyncio.create_task(self._sync_loop())

        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Initialize current file
        await self._get_current_file()

        logger.info(f"Started file queue in directory: {self.queue_dir}")

    async def stop(self) -> None:
        """Stop the file queue and background tasks."""
        self._shutdown = True

        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped file queue")

    async def enqueue(self, log_entry: LogEntry) -> bool:
        """
        Enqueue a log entry to file.

        Returns:
            True if enqueued successfully, False if failed
        """
        if self._shutdown:
            return False

        try:
            async with self._lock:
                # Ensure we have a current file
                if not self.current_file:
                    await self._get_current_file()

                # Check if current file is too large
                if self.current_file_size >= self.config.max_file_size_mb * 1024 * 1024:
                    await self._rotate_file()

                # Serialize log entry
                entry_data = {
                    "id": log_entry.id,
                    "timestamp": log_entry.timestamp.isoformat(),
                    "message": log_entry.message,
                    "source": log_entry.source,
                    "severity": log_entry.severity,
                    "metadata": log_entry.metadata,
                }

                # Write to file
                with open(self.current_file, "a") as f:
                    f.write(json.dumps(entry_data) + "\n")

                self.current_file_size = self.current_file.stat().st_size
                self._stats.total_enqueued += 1
                self._stats.last_enqueue_time = datetime.now(timezone.utc)

                return True

        except Exception as e:
            logger.error(f"Error enqueuing log entry: {e}")
            self._stats.dropped_count += 1
            return False

    async def dequeue(self, max_items: Optional[int] = None) -> List[LogEntry]:
        """
        Dequeue log entries from files.

        Args:
            max_items: Maximum number of items to dequeue

        Returns:
            List of dequeued log entries
        """
        if max_items is None:
            max_items = self.config.batch_size

        entries = []

        try:
            async with self._lock:
                # Get all queue files, sorted by modification time
                queue_files = sorted(
                    [f for f in self.queue_dir.glob("queue_*.jsonl")],
                    key=lambda x: x.stat().st_mtime,
                )

                for queue_file in queue_files:
                    if len(entries) >= max_items:
                        break

                    # Read entries from file
                    file_entries = await self._read_file_entries(
                        queue_file, max_items - len(entries)
                    )
                    entries.extend(file_entries)

                    # If we read all entries from this file, remove it
                    if len(file_entries) > 0:
                        # Mark file as processed by moving it
                        processed_file = queue_file.with_suffix(".processed")
                        queue_file.rename(processed_file)

                if entries:
                    self._stats.total_dequeued += len(entries)
                    self._stats.last_dequeue_time = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"Error dequeuing log entries: {e}")

        return entries

    async def peek(self, count: int = 1) -> List[LogEntry]:
        """Peek at the next items without removing them."""
        # For file queue, this is expensive, so we'll just return empty
        # In a production system, you might want to implement a more efficient peek
        return []

    async def clear(self) -> int:
        """Clear all queue files and return the number of files cleared."""
        async with self._lock:
            cleared_count = 0
            for queue_file in self.queue_dir.glob("queue_*.jsonl"):
                queue_file.unlink()
                cleared_count += 1

            for processed_file in self.queue_dir.glob("queue_*.processed"):
                processed_file.unlink()
                cleared_count += 1

            return cleared_count

    def get_stats(self) -> QueueStats:
        """Get current queue statistics."""
        # Count files and estimate size
        queue_files = list(self.queue_dir.glob("queue_*.jsonl"))
        total_size = sum(f.stat().st_size for f in queue_files)

        return QueueStats(
            total_enqueued=self._stats.total_enqueued,
            total_dequeued=self._stats.total_dequeued,
            current_size=len(queue_files),
            max_size_reached=self._stats.max_size_reached,
            dropped_count=self._stats.dropped_count,
            last_enqueue_time=self._stats.last_enqueue_time,
            last_dequeue_time=self._stats.last_dequeue_time,
            average_processing_time_ms=self._stats.average_processing_time_ms,
            memory_usage_mb=total_size / (1024 * 1024),
        )

    def is_full(self) -> bool:
        """Check if the queue is at capacity (based on file count)."""
        queue_files = list(self.queue_dir.glob("queue_*.jsonl"))
        return len(queue_files) >= self.config.max_files

    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        queue_files = list(self.queue_dir.glob("queue_*.jsonl"))
        return len(queue_files) == 0

    def size(self) -> int:
        """Get current queue size (number of files)."""
        queue_files = list(self.queue_dir.glob("queue_*.jsonl"))
        return len(queue_files)

    async def _get_current_file(self) -> None:
        """Get or create the current queue file."""
        if not self.current_file or not self.current_file.exists():
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            self.current_file = self.queue_dir / f"queue_{timestamp}.jsonl"
            self.current_file_size = 0

    async def _rotate_file(self) -> None:
        """Rotate to a new queue file."""
        if self.current_file:
            # Close current file
            self.current_file = None
            self.current_file_size = 0

        # Create new file
        await self._get_current_file()

    async def _read_file_entries(
        self, file_path: Path, max_entries: int
    ) -> List[LogEntry]:
        """Read log entries from a file."""
        entries = []

        try:
            with open(file_path, "r") as f:
                for line_num, line in enumerate(f):
                    if len(entries) >= max_entries:
                        break

                    try:
                        entry_data = json.loads(line.strip())

                        # Convert back to LogEntry
                        entry = LogEntry(
                            id=entry_data["id"],
                            timestamp=datetime.fromisoformat(entry_data["timestamp"]),
                            message=entry_data["message"],
                            source=entry_data["source"],
                            severity=entry_data["severity"],
                            metadata=entry_data["metadata"],
                        )

                        entries.append(entry)

                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.warning(
                            f"Error parsing log entry in {file_path}:{line_num}: {e}"
                        )
                        continue

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")

        return entries

    async def _sync_loop(self) -> None:
        """Background task to sync files periodically."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.sync_interval_seconds)

                # Force sync current file if it exists
                if self.current_file and self.current_file.exists():
                    # This is a no-op on most systems, but ensures data is written
                    os.sync()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")

    async def _cleanup_loop(self) -> None:
        """Background task to clean up old processed files."""
        while not self._shutdown:
            try:
                await asyncio.sleep(60.0)  # Cleanup every minute

                # Remove processed files older than 1 hour
                cutoff_time = datetime.now(timezone.utc).timestamp() - 3600

                for processed_file in self.queue_dir.glob("queue_*.processed"):
                    if processed_file.stat().st_mtime < cutoff_time:
                        processed_file.unlink()
                        logger.debug(f"Cleaned up old processed file: {processed_file}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
