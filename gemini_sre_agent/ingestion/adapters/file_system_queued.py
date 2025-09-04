# gemini_sre_agent/ingestion/adapters/file_system_queued.py

"""
Enhanced file system adapter with memory queue for log ingestion.

This adapter implements the LogIngestionInterface for consuming logs
from local file system files with in-memory buffering and backpressure management.
"""

import asyncio
import glob
import logging
import os
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from ...config.ingestion_config import FileSystemConfig
from ..interfaces.core import (
    LogEntry,
    LogIngestionInterface,
    LogSeverity,
    SourceConfig,
    SourceHealth,
)
from ..interfaces.errors import (
    LogParsingError,
    SourceConnectionError,
    SourceNotRunningError,
)
from ..interfaces.resilience import HyxResilientClient, create_resilience_config
from ..queues.memory_queue import MemoryQueue, QueueConfig

logger = logging.getLogger(__name__)


class QueuedFileSystemAdapter(LogIngestionInterface):
    """Enhanced file system adapter with memory queue for log buffering."""

    def __init__(self, config: FileSystemConfig):
        self.config = config
        self.file_path = config.file_path
        self.file_pattern = config.file_pattern
        self.watch_mode = config.watch_mode
        self.encoding = config.encoding
        self.buffer_size = config.buffer_size
        self.max_memory_mb = config.max_memory_mb

        # Initialize resilience client
        resilience_config = create_resilience_config()
        self.resilient_client = HyxResilientClient(resilience_config)

        # Initialize memory queue
        queue_config = QueueConfig(
            max_size=config.max_memory_mb * 1000,  # Rough estimate: 1KB per log entry
            max_memory_mb=config.max_memory_mb,
            batch_size=100,
            flush_interval_seconds=1.0,
            enable_metrics=True,
        )
        self.memory_queue = MemoryQueue(queue_config)

        # State tracking
        self.running = False
        self._processed_files: Set[str] = set()
        self._last_check_time = datetime.now(timezone.utc)
        self._error_count = 0
        self._last_error = None
        self._file_positions: Dict[str, int] = (
            {}
        )  # Track file positions for incremental reading

        # Background tasks
        self._file_watcher_task: Optional[asyncio.Task] = None
        self._queue_processor_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the file system adapter and memory queue."""
        try:
            # Validate file path
            if not os.path.exists(self.file_path):
                raise SourceConnectionError(
                    f"File path does not exist: {self.file_path}"
                )

            # Start memory queue
            await self.memory_queue.start()

            # Start background tasks
            self._file_watcher_task = asyncio.create_task(self._file_watcher_loop())
            self._queue_processor_task = asyncio.create_task(
                self._queue_processor_loop()
            )

            self.running = True
            self._last_check_time = datetime.now(timezone.utc)
            logger.info(f"Started queued file system adapter for: {self.file_path}")

        except Exception as e:
            logger.error(f"Failed to start queued file system adapter: {e}")
            raise SourceConnectionError(
                f"Failed to start file system adapter: {e}"
            ) from e

    async def stop(self) -> None:
        """Stop the file system adapter and memory queue."""
        self.running = False

        # Cancel background tasks
        if self._file_watcher_task:
            self._file_watcher_task.cancel()
            try:
                await self._file_watcher_task
            except asyncio.CancelledError:
                pass

        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass

        # Stop memory queue
        await self.memory_queue.stop()

        logger.info("Stopped queued file system adapter")

    async def get_logs(self) -> AsyncGenerator[LogEntry, None]:  # type: ignore
        """Get logs from the memory queue."""
        if not self.running:
            raise SourceNotRunningError("File system adapter is not running")

        while self.running:
            try:
                # Get logs from memory queue
                log_entries = await self.memory_queue.dequeue()

                if not log_entries:
                    # No logs available, wait a bit
                    await asyncio.sleep(0.1)
                    continue

                for log_entry in log_entries:
                    yield log_entry

            except Exception as e:
                logger.error(f"Error getting logs from queue: {e}")
                self._error_count += 1
                self._last_error = str(e)
                await asyncio.sleep(1)

    async def health_check(self) -> SourceHealth:
        """Check the health of the file system adapter."""
        try:
            if not self.running:
                return SourceHealth(
                    is_healthy=False,
                    last_success=None,
                    error_count=self._error_count,
                    last_error="Adapter not running",
                    metrics={"status": "stopped"},
                )

            # Check if file path still exists
            if not os.path.exists(self.file_path):
                return SourceHealth(
                    is_healthy=False,
                    last_success=None,
                    error_count=self._error_count,
                    last_error=f"File path does not exist: {self.file_path}",
                    metrics={"status": "error"},
                )

            # Get queue stats
            queue_stats = self.memory_queue.get_stats()

            return SourceHealth(
                is_healthy=True,
                last_success=datetime.now(timezone.utc).isoformat(),
                error_count=self._error_count,
                last_error=self._last_error,
                metrics={
                    "file_path": self.file_path,
                    "file_pattern": self.file_pattern,
                    "queue_size": queue_stats.current_size,
                    "queue_dropped": queue_stats.dropped_count,
                    "processed_files": len(self._processed_files),
                    "last_check": self._last_check_time.isoformat(),
                },
            )

        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)
            return SourceHealth(
                is_healthy=False,
                last_success=None,
                error_count=self._error_count,
                last_error=str(e),
                metrics={"status": "error"},
            )

    def get_config(self) -> SourceConfig:  # type: ignore
        """Get the current configuration."""
        return self.config

    async def update_config(self, config: SourceConfig) -> None:
        """Update the configuration."""
        if isinstance(config, FileSystemConfig):
            self.config = config
            # Restart if running
            if self.running:
                await self.stop()
                await self.start()
        else:
            raise ValueError("Invalid config type for file system adapter")

    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle errors from the adapter."""
        logger.error(
            f"File system error in {context.get('operation', 'unknown')}: {error}"
        )
        self._error_count += 1
        self._last_error = str(error)

        # Return True if error should be retried
        if isinstance(error, (OSError, IOError)):
            return True  # Retry file system errors
        return False

    async def get_health_metrics(self) -> Dict[str, Any]:
        """Get detailed health metrics."""
        queue_stats = self.memory_queue.get_stats()

        return {
            "file_path": self.file_path,
            "file_pattern": self.file_pattern,
            "watch_mode": self.watch_mode,
            "encoding": self.encoding,
            "running": self.running,
            "error_count": self._error_count,
            "last_error": self._last_error,
            "last_check_time": self._last_check_time.isoformat(),
            "processed_files": len(self._processed_files),
            "queue_stats": {
                "current_size": queue_stats.current_size,
                "total_enqueued": queue_stats.total_enqueued,
                "total_dequeued": queue_stats.total_dequeued,
                "dropped_count": queue_stats.dropped_count,
                "memory_usage_mb": queue_stats.memory_usage_mb,
            },
        }

    async def _file_watcher_loop(self) -> None:
        """Background task to watch for file changes and enqueue logs."""
        while self.running:
            try:
                # Get files to process
                files_to_process = await self._get_files_to_process()

                for file_path in files_to_process:
                    if not self.running:
                        break

                    try:
                        # Process file and enqueue logs
                        await self._process_file(file_path)

                    except Exception as e:
                        logger.error(f"Error processing file {file_path}: {e}")
                        self._error_count += 1
                        self._last_error = str(e)
                        continue

                # Update last check time
                self._last_check_time = datetime.now(timezone.utc)

                # Wait before next check
                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in file watcher loop: {e}")
                await asyncio.sleep(5.0)

    async def _queue_processor_loop(self) -> None:
        """Background task to process logs from the queue."""
        while self.running:
            try:
                # This loop is mainly for monitoring and cleanup
                # The actual log processing happens in get_logs()

                # Check queue health
                if self.memory_queue.is_full():
                    logger.warning("Memory queue is full, logs may be dropped")

                await asyncio.sleep(10.0)  # Check every 10 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue processor loop: {e}")
                await asyncio.sleep(5.0)

    async def _get_files_to_process(self) -> List[str]:
        """Get list of files to process."""
        files = []

        try:
            if os.path.isfile(self.file_path):
                # Single file
                files.append(self.file_path)
            elif os.path.isdir(self.file_path):
                # Directory with pattern
                pattern = os.path.join(self.file_path, self.file_pattern)
                files = glob.glob(pattern)
            else:
                # Pattern-based search
                files = glob.glob(self.file_path)

            # Filter out already processed files (for non-watch mode)
            if not self.watch_mode:
                files = [f for f in files if f not in self._processed_files]

            return files

        except Exception as e:
            logger.error(f"Error getting files to process: {e}")
            return []

    async def _process_file(self, file_path: str) -> None:
        """Process a single file and enqueue logs."""
        try:
            # Get current position in file
            current_position = self._file_positions.get(file_path, 0)

            with open(file_path, "r", encoding=self.encoding) as f:
                # Seek to last known position
                f.seek(current_position)

                # Read new content
                new_content = f.read()
                current_position = f.tell()

                if not new_content:
                    return  # No new content

                # Parse log lines
                log_lines = new_content.strip().split("\n")

                for line_num, line in enumerate(log_lines):
                    if not line.strip():
                        continue

                    try:
                        # Parse log entry
                        log_entry = self._parse_log_line(line, file_path, line_num)

                        # Enqueue to memory queue
                        success = await self.memory_queue.enqueue(log_entry)

                        if not success:
                            logger.warning(
                                f"Failed to enqueue log entry from {file_path}:{line_num}"
                            )

                    except LogParsingError as e:
                        logger.warning(
                            f"Failed to parse log line {file_path}:{line_num}: {e}"
                        )
                        continue

                # Update file position
                self._file_positions[file_path] = current_position

                # Mark as processed if not in watch mode
                if not self.watch_mode:
                    self._processed_files.add(file_path)

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            raise

    def _parse_log_line(self, line: str, file_path: str, line_num: int) -> LogEntry:
        """Parse a single log line into a LogEntry."""
        try:
            # Simple log parsing - can be enhanced based on log format
            timestamp = datetime.now(timezone.utc)
            message = line.strip()
            severity = LogSeverity.INFO

            # Try to extract timestamp and severity from common log formats
            parts = line.split(" ", 3)
            if len(parts) >= 3:
                try:
                    # Try to parse timestamp (common formats)
                    timestamp_str = f"{parts[0]} {parts[1]}"
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                    message = parts[3] if len(parts) > 3 else message
                except ValueError:
                    pass

                # Try to extract severity
                if len(parts) >= 3:
                    severity_str = parts[2].upper()
                    if severity_str in ["ERROR", "ERR"]:
                        severity = LogSeverity.ERROR
                    elif severity_str in ["WARN", "WARNING"]:
                        severity = LogSeverity.WARN
                    elif severity_str in ["DEBUG", "DBG"]:
                        severity = LogSeverity.DEBUG
                    elif severity_str in ["CRITICAL", "CRIT", "FATAL"]:
                        severity = LogSeverity.CRITICAL
                    elif severity_str in ["INFO"]:
                        severity = LogSeverity.INFO

            # Generate unique ID
            log_id = f"fs-{os.path.basename(file_path)}-{line_num}-{hash(line) % 10000}"

            return LogEntry(
                id=log_id,
                timestamp=timestamp,
                message=message,
                source=f"file-system-{os.path.basename(file_path)}",
                severity=severity,
                metadata={
                    "file_path": file_path,
                    "line_number": line_num,
                    "file_size": (
                        os.path.getsize(file_path) if os.path.exists(file_path) else 0
                    ),
                },
            )

        except Exception as e:
            raise LogParsingError(f"Failed to parse log line: {e}") from e
