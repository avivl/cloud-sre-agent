# gemini_sre_agent/ingestion/adapters/file_system.py

"""
File system adapter for log ingestion.

This adapter implements the LogIngestionInterface for consuming logs
from local file system files and directories.
"""

import glob
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional, Set

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

logger = logging.getLogger(__name__)


class FileSystemAdapter(LogIngestionInterface):
    """Adapter for file system log consumption."""

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

        # State management
        self._is_running = False
        self._watched_files: Set[str] = set()
        self._file_positions: Dict[str, int] = {}
        self._last_check_time = None

        # Health tracking
        self._last_health_check = datetime.now()
        self._consecutive_failures = 0
        self._total_logs_processed = 0
        self._total_logs_failed = 0

    async def start(self) -> None:
        """Start the file system consumer."""
        if self._is_running:
            return

        try:
            # Validate file path
            if not self.config.file_path:
                raise SourceConnectionError("File path not specified")

            path = Path(self.config.file_path)
            if not path.exists():
                raise SourceConnectionError(
                    f"File path does not exist: {self.config.file_path}"
                )

            # Initialize file positions
            self._initialize_file_positions()

            self._is_running = True
            self._last_check_time = datetime.now()

        except Exception as e:
            raise SourceConnectionError(
                f"Failed to start file system adapter: {e}"
            ) from e

    async def stop(self) -> None:
        """Stop the file system consumer."""
        self._is_running = False
        self._watched_files.clear()
        self._file_positions.clear()

    async def get_logs(self) -> AsyncGenerator[LogEntry, None]:  # type: ignore
        """Get logs from file system."""
        if not self._is_running:
            raise SourceNotRunningError("File system adapter is not running")

        try:
            # Get list of files to process
            files = self._get_files_to_process()

            for file_path in files:
                try:
                    # Read new content from file
                    async for log_entry in self._read_file_content(file_path):
                        self._total_logs_processed += 1
                        yield log_entry

                except Exception as e:
                    self._total_logs_failed += 1
                    self._consecutive_failures += 1
                    raise LogParsingError(
                        f"Failed to read file {file_path}: {e}"
                    ) from e

            # Reset failure count on successful processing
            self._consecutive_failures = 0

        except Exception as e:
            self._consecutive_failures += 1
            raise SourceConnectionError(
                f"Failed to get logs from file system: {e}"
            ) from e

    async def get_logs_continuous(self) -> AsyncGenerator[LogEntry, None]:  # type: ignore
        """Get logs from file system continuously."""
        if not self._is_running:
            raise SourceNotRunningError("File system adapter is not running")

        try:
            # Get list of files to process
            files = self._get_files_to_process()

            while self._is_running:
                for file_path in files:
                    try:
                        # Read new content from file
                        async for log_entry in self._read_file_content(file_path):
                            self._total_logs_processed += 1
                            yield log_entry

                    except Exception as e:
                        self._total_logs_failed += 1
                        self._consecutive_failures += 1
                        logger.error(f"Failed to read file {file_path}: {e}")
                        continue

                # Reset failure count on successful processing
                self._consecutive_failures = 0
                
                # Wait a bit before checking again
                await asyncio.sleep(1)

        except Exception as e:
            self._consecutive_failures += 1
            raise SourceConnectionError(
                f"Failed to get logs from file system: {e}"
            ) from e

    def _initialize_file_positions(self) -> None:
        """Initialize file positions for tracking."""
        files = self._get_files_to_process()
        for file_path in files:
            if file_path not in self._file_positions:
                # Start from end of file for existing files
                try:
                    self._file_positions[file_path] = os.path.getsize(file_path)
                except OSError:
                    self._file_positions[file_path] = 0

    def _get_files_to_process(self) -> List[str]:
        """Get list of files to process based on path and pattern."""
        file_path = self.config.file_path
        file_pattern = self.config.file_pattern

        if not file_path:
            return []

        path = Path(file_path)
        files = []

        if path.is_file():
            # Single file
            files.append(str(path))
        elif path.is_dir():
            # Directory with pattern
            pattern = str(path / file_pattern)
            files.extend(glob.glob(pattern))
        else:
            # Pattern matching
            files.extend(glob.glob(file_path))

        return sorted(files)

    async def _read_file_content(self, file_path: str) -> AsyncIterator[LogEntry]:
        """Read new content from a file and yield log entries."""
        try:
            current_size = os.path.getsize(file_path)
            last_position = self._file_positions.get(file_path, 0)
            
            logger.debug(f"File {file_path}: current_size={current_size}, last_position={last_position}")

            # Only read if file has grown
            if current_size > last_position:
                logger.debug(f"File {file_path} has grown, reading new content")
                # Read new content with resilience
                async def _read_file():
                    with open(
                        file_path, "r", encoding=self.encoding, errors="replace"
                    ) as f:
                        f.seek(last_position)
                        content = f.read()
                        return content

                content = await self.resilient_client.execute(_read_file)
                logger.debug(f"Read {len(content)} characters from {file_path}")

                # Parse content into log entries
                log_entries = self._parse_file_content(content, file_path)
                logger.debug(f"Parsed {len(log_entries)} log entries from {file_path}")
                
                for log_entry in log_entries:
                    yield log_entry

                # Update file position
                self._file_positions[file_path] = current_size
            else:
                logger.debug(f"File {file_path} has not grown, skipping")

        except Exception as e:
            raise LogParsingError(f"Failed to read file content: {e}") from e

    def _parse_file_content(self, content: str, file_path: str) -> List[LogEntry]:
        """Parse file content into log entries."""
        log_entries = []

        if not content.strip():
            return log_entries

        # Try to parse as JSON logs first (structured logs)
        try:
            # Look for JSON objects in the content
            import json
            import re
            
            # Find JSON objects in the content
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            json_matches = re.findall(json_pattern, content)
            
            for i, json_str in enumerate(json_matches):
                try:
                    json_data = json.loads(json_str)
                    
                    # Extract fields from JSON
                    timestamp_str = json_data.get('timestamp', '')
                    level = json_data.get('level', 'INFO')
                    message = json_data.get('message', json_str)
                    
                    # Parse timestamp
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except:
                        timestamp = datetime.now()
                    
                    # Map level to LogSeverity
                    if level.upper() == 'ERROR':
                        severity = LogSeverity.ERROR
                    elif level.upper() == 'WARN':
                        severity = LogSeverity.WARN
                    elif level.upper() == 'DEBUG':
                        severity = LogSeverity.DEBUG
                    else:
                        severity = LogSeverity.INFO
                    
                    log_entry = LogEntry(
                        id=f"{file_path}:json:{i}:{timestamp.isoformat()}",
                        message=message,
                        timestamp=timestamp,
                        severity=severity,
                        source=self.config.name,
                        metadata={
                            "file_path": file_path,
                            "json_data": json_data,
                            "raw_content": json_str,
                        },
                    )
                    log_entries.append(log_entry)
                    
                except json.JSONDecodeError:
                    # Not valid JSON, skip
                    continue
                    
        except Exception:
            # Fall back to line-by-line parsing
            pass

        # If no JSON logs found, fall back to line-by-line parsing
        if not log_entries:
            # Split content into lines
            lines = content.strip().split("\n")

            for line_num, line in enumerate(lines, 1):
                if not line.strip():
                    continue

                try:
                    # Parse log line
                    log_entry = self._parse_log_line(line, file_path, line_num)
                    if log_entry:
                        log_entries.append(log_entry)

                except Exception:
                    # Skip malformed lines but continue processing
                    continue

        return log_entries

    def _parse_log_line(
        self, line: str, file_path: str, line_num: int
    ) -> Optional[LogEntry]:
        """Parse a single log line into a LogEntry."""
        try:
            # Basic log parsing - can be enhanced with more sophisticated parsing
            # For now, treat each line as a log entry

            # Try to extract timestamp and severity from common log formats
            timestamp = datetime.now()
            severity = LogSeverity.INFO
            message = line.strip()

            # Simple timestamp detection (can be enhanced)
            if " " in line and len(line.split(" ")) > 1:
                parts = line.split(" ", 2)
                if len(parts) >= 2:
                    # Try to parse first part as timestamp
                    try:
                        # Common timestamp formats
                        for fmt in [
                            "%Y-%m-%dT%H:%M:%S",
                            "%Y-%m-%d %H:%M:%S",
                            "%b %d %H:%M:%S",
                        ]:
                            try:
                                timestamp = datetime.strptime(parts[0], fmt)
                                message = parts[2] if len(parts) > 2 else parts[1]
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass

            # Simple severity detection
            line_upper = line.upper()
            if any(level in line_upper for level in ["ERROR", "ERR"]):
                severity = LogSeverity.ERROR
            elif any(level in line_upper for level in ["WARN", "WARNING"]):
                severity = LogSeverity.WARN
            elif any(level in line_upper for level in ["DEBUG", "DBG"]):
                severity = LogSeverity.DEBUG
            elif any(level in line_upper for level in ["INFO", "INF"]):
                severity = LogSeverity.INFO

            return LogEntry(
                id=f"{file_path}:{line_num}:{timestamp.isoformat()}",
                message=message,
                timestamp=timestamp,
                severity=severity,
                source=self.config.name,
                metadata={
                    "file_path": file_path,
                    "line_number": line_num,
                    "file_size": (
                        os.path.getsize(file_path) if os.path.exists(file_path) else 0
                    ),
                    "raw_line": line,
                },
            )

        except Exception as e:
            raise LogParsingError(f"Failed to parse log line: {e}") from e

    async def get_health(self) -> SourceHealth:
        """Get health status of the file system adapter."""
        current_time = datetime.now()

        # Calculate health metrics
        total_logs = self._total_logs_processed + self._total_logs_failed
        error_rate = self._total_logs_failed / max(total_logs, 1)

        # Check file accessibility
        files_accessible = 0
        total_files = 0

        try:
            files = self._get_files_to_process()
            total_files = len(files)

            for file_path in files:
                if os.path.exists(file_path) and os.access(file_path, os.R_OK):
                    files_accessible += 1
        except Exception:
            pass

        # Determine health status
        if not self._is_running:
            status = "unhealthy"
        elif self._consecutive_failures > 5:
            status = "unhealthy"
        elif error_rate > 0.1:  # 10% error rate
            status = "degraded"
        elif files_accessible < total_files:
            status = "degraded"
        else:
            status = "healthy"

        return SourceHealth(
            is_healthy=(status == "healthy"),
            last_success=current_time.isoformat() if status == "healthy" else None,
            error_count=self._consecutive_failures,
            last_error=None if status == "healthy" else f"Status: {status}",
            metrics={
                "status": status,
                "last_check": current_time,
                "consecutive_failures": self._consecutive_failures,
                "total_processed": self._total_logs_processed,
                "total_failed": self._total_logs_failed,
                "error_rate": error_rate,
                "file_path": self.config.file_path,
                "file_pattern": self.config.file_pattern,
                "is_running": self._is_running,
                "files_accessible": files_accessible,
                "total_files": total_files,
                "watched_files": len(self._watched_files),
                "resilience_stats": self.resilient_client.get_health_stats(),
            },
        )

    def get_config(self) -> SourceConfig:
        """Get adapter configuration."""
        return self.config  # type: ignore

    async def health_check(self) -> SourceHealth:
        """Check the health status of the file system source."""
        return await self.get_health()

    async def update_config(self, config: SourceConfig) -> None:
        """Update the configuration for this source."""
        if isinstance(config, FileSystemConfig):
            self.config = config
            self.file_path = config.file_path
            self.file_pattern = config.file_pattern
            self.watch_mode = config.watch_mode
            self.encoding = config.encoding
            self.buffer_size = config.buffer_size
            self.max_memory_mb = config.max_memory_mb
        else:
            raise ValueError("Config must be FileSystemConfig")

    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle errors with context. Return True if recoverable."""
        logger.error(f"File system adapter error: {error} in context: {context}")
        self._consecutive_failures += 1

        # Consider file system errors as potentially recoverable
        if isinstance(error, (OSError, IOError)):
            return True
        return False

    async def get_health_metrics(self) -> Dict[str, Any]:
        """Get detailed health and performance metrics."""
        return {
            "is_running": self._is_running,
            "consecutive_failures": self._consecutive_failures,
            "total_logs_processed": self._total_logs_processed,
            "total_logs_failed": self._total_logs_failed,
            "last_check_time": (
                self._last_check_time.isoformat() if self._last_check_time else None
            ),
            "watched_files_count": len(self._watched_files),
            "resilience_stats": self.resilient_client.get_health_stats(),
        }
