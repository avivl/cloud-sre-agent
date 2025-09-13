# gemini_sre_agent/core/logging/handlers.py
"""
Custom log handlers for structured logging.

This module provides specialized handlers for different logging scenarios.
"""

import logging
import logging.handlers
from pathlib import Path
import sys
from typing import Any

from .exceptions import HandlerError
from .formatters import JSONFormatter, StructuredFormatter


class StructuredFileHandler(logging.FileHandler):
    """File handler that writes structured logs."""

    def __init__(
        self,
        filename: str | Path,
        mode: str = "a",
        encoding: str | None = None,
        delay: bool = False,
        formatter_type: str = "json"
    ):
        """Initialize the structured file handler.
        
        Args:
            filename: Log file path.
            mode: File mode.
            encoding: File encoding.
            delay: Whether to delay file opening.
            formatter_type: Type of formatter to use.
        """
        super().__init__(filename, mode, encoding, delay)

        # Set appropriate formatter
        if formatter_type == "json":
            self.setFormatter(JSONFormatter())
        else:
            self.setFormatter(StructuredFormatter())


class RotatingStructuredFileHandler(logging.handlers.RotatingFileHandler):
    """Rotating file handler for structured logs."""

    def __init__(
        self,
        filename: str | Path,
        mode: str = "a",
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: str | None = None,
        delay: bool = False,
        formatter_type: str = "json"
    ):
        """Initialize the rotating structured file handler.
        
        Args:
            filename: Log file path.
            mode: File mode.
            maxBytes: Maximum file size before rotation.
            backupCount: Number of backup files to keep.
            encoding: File encoding.
            delay: Whether to delay file opening.
            formatter_type: Type of formatter to use.
        """
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)

        # Set appropriate formatter
        if formatter_type == "json":
            self.setFormatter(JSONFormatter())
        else:
            self.setFormatter(StructuredFormatter())


class TimedRotatingStructuredFileHandler(logging.handlers.TimedRotatingFileHandler):
    """Time-based rotating file handler for structured logs."""

    def __init__(
        self,
        filename: str | Path,
        when: str = "h",
        interval: int = 1,
        backupCount: int = 0,
        encoding: str | None = None,
        delay: bool = False,
        utc: bool = False,
        atTime: Any | None = None,
        formatter_type: str = "json"
    ):
        """Initialize the timed rotating structured file handler.
        
        Args:
            filename: Log file path.
            when: When to rotate (h, d, w, etc.).
            interval: Rotation interval.
            backupCount: Number of backup files to keep.
            encoding: File encoding.
            delay: Whether to delay file opening.
            utc: Whether to use UTC time.
            atTime: Time to rotate.
            formatter_type: Type of formatter to use.
        """
        super().__init__(filename, when, interval, backupCount, encoding, delay, utc, atTime)

        # Set appropriate formatter
        if formatter_type == "json":
            self.setFormatter(JSONFormatter())
        else:
            self.setFormatter(StructuredFormatter())


class ConsoleHandler(logging.StreamHandler):
    """Console handler with structured output."""

    def __init__(
        self,
        stream: Any | None = None,
        formatter_type: str = "structured",
        colorize: bool = True
    ):
        """Initialize the console handler.
        
        Args:
            stream: Output stream (defaults to stderr).
            formatter_type: Type of formatter to use.
            colorize: Whether to add color to output.
        """
        if stream is None:
            stream = sys.stderr

        super().__init__(stream)

        # Set appropriate formatter
        if formatter_type == "json":
            self.setFormatter(JSONFormatter())
        else:
            self.setFormatter(StructuredFormatter())


class MemoryHandler(logging.handlers.MemoryHandler):
    """Memory handler for buffering logs."""

    def __init__(
        self,
        capacity: int,
        flushLevel: int = logging.ERROR,
        target: logging.Handler | None = None,
        flushOnClose: bool = True,
        formatter_type: str = "json"
    ):
        """Initialize the memory handler.
        
        Args:
            capacity: Buffer capacity.
            flushLevel: Level at which to flush.
            target: Target handler for flushing.
            flushOnClose: Whether to flush on close.
            formatter_type: Type of formatter to use.
        """
        super().__init__(capacity, flushLevel, target, flushOnClose)

        # Set appropriate formatter
        if formatter_type == "json":
            self.setFormatter(JSONFormatter())
        else:
            self.setFormatter(StructuredFormatter())


class QueueHandler(logging.handlers.QueueHandler):
    """Queue handler for asynchronous logging."""

    def __init__(self, queue, formatter_type: str = "json"):
        """Initialize the queue handler.
        
        Args:
            queue: Queue to send logs to.
            formatter_type: Type of formatter to use.
        """
        super().__init__(queue)

        # Set appropriate formatter
        if formatter_type == "json":
            self.setFormatter(JSONFormatter())
        else:
            self.setFormatter(StructuredFormatter())


class HTTPHandler(logging.Handler):
    """HTTP handler for sending logs to remote servers."""

    def __init__(
        self,
        host: str,
        url: str,
        method: str = "POST",
        secure: bool = False,
        credentials: tuple | None = None,
        context: Any | None = None,
        formatter_type: str = "json"
    ):
        """Initialize the HTTP handler.
        
        Args:
            host: Target host.
            url: Target URL.
            method: HTTP method.
            secure: Whether to use HTTPS.
            credentials: Authentication credentials.
            context: SSL context.
            formatter_type: Type of formatter to use.
        """
        super().__init__()

        self.host = host
        self.url = url
        self.method = method
        self.secure = secure
        self.credentials = credentials
        self.context = context

        # Set appropriate formatter
        if formatter_type == "json":
            self.setFormatter(JSONFormatter())
        else:
            self.setFormatter(StructuredFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record via HTTP.
        
        Args:
            record: Log record to emit.
        """
        try:
            # Format the record
            msg = self.format(record)

            # Send via HTTP (simplified implementation)
            # In a real implementation, you would use requests or httpx
            print(f"HTTP {self.method} {self.host}{self.url}")
            print(f"Body: {msg}")

        except Exception as e:
            raise HandlerError(
                f"Failed to emit log record via HTTP: {e!s}",
                handler_name="HTTPHandler",
                handler_type="http"
            ) from e


class DatabaseHandler(logging.Handler):
    """Database handler for storing logs in a database."""

    def __init__(
        self,
        connection_string: str,
        table_name: str = "logs",
        formatter_type: str = "json"
    ):
        """Initialize the database handler.
        
        Args:
            connection_string: Database connection string.
            table_name: Table name to store logs in.
            formatter_type: Type of formatter to use.
        """
        super().__init__()

        self.connection_string = connection_string
        self.table_name = table_name

        # Set appropriate formatter
        if formatter_type == "json":
            self.setFormatter(JSONFormatter())
        else:
            self.setFormatter(StructuredFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the database.
        
        Args:
            record: Log record to emit.
        """
        try:
            # Format the record
            msg = self.format(record)

            # Store in database (simplified implementation)
            # In a real implementation, you would use a database library
            print(f"Database insert into {self.table_name}: {msg}")

        except Exception as e:
            raise HandlerError(
                f"Failed to emit log record to database: {e!s}",
                handler_name="DatabaseHandler",
                handler_type="database"
            ) from e


class MultiHandler(logging.Handler):
    """Handler that forwards logs to multiple handlers."""

    def __init__(self, handlers: list[logging.Handler]):
        """Initialize the multi handler.
        
        Args:
            handlers: List of handlers to forward to.
        """
        super().__init__()
        self.handlers = handlers

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to all handlers.
        
        Args:
            record: Log record to emit.
        """
        for handler in self.handlers:
            try:
                handler.emit(record)
            except Exception as e:
                # Log the error but don't raise it to avoid breaking other handlers
                print(f"Error in handler {handler.__class__.__name__}: {e}")

    def close(self) -> None:
        """Close all handlers."""
        for handler in self.handlers:
            try:
                handler.close()
            except Exception as e:
                print(f"Error closing handler {handler.__class__.__name__}: {e}")

        super().close()


def create_file_handler(
    filename: str | Path,
    formatter_type: str = "json",
    max_bytes: int | None = None,
    backup_count: int | None = None
) -> logging.Handler:
    """Create a file handler with appropriate configuration.
    
    Args:
        filename: Log file path.
        formatter_type: Type of formatter to use.
        max_bytes: Maximum file size for rotation.
        backup_count: Number of backup files.
        
    Returns:
        Configured file handler.
    """
    try:
        if max_bytes and backup_count:
            return RotatingStructuredFileHandler(
                filename,
                maxBytes=max_bytes,
                backupCount=backup_count,
                formatter_type=formatter_type
            )
        else:
            return StructuredFileHandler(filename, formatter_type=formatter_type)
    except Exception as e:
        raise HandlerError(
            f"Failed to create file handler: {e!s}",
            handler_name="FileHandler",
            handler_type="file"
        ) from e


def create_console_handler(
    formatter_type: str = "structured",
    colorize: bool = True
) -> logging.Handler:
    """Create a console handler with appropriate configuration.
    
    Args:
        formatter_type: Type of formatter to use.
        colorize: Whether to add color to output.
        
    Returns:
        Configured console handler.
    """
    try:
        return ConsoleHandler(
            formatter_type=formatter_type,
            colorize=colorize
        )
    except Exception as e:
        raise HandlerError(
            f"Failed to create console handler: {e!s}",
            handler_name="ConsoleHandler",
            handler_type="console"
        ) from e


def create_memory_handler(
    capacity: int = 1000,
    flush_level: int = logging.ERROR,
    target: logging.Handler | None = None,
    formatter_type: str = "json"
) -> logging.Handler:
    """Create a memory handler with appropriate configuration.
    
    Args:
        capacity: Buffer capacity.
        flush_level: Level at which to flush.
        target: Target handler for flushing.
        formatter_type: Type of formatter to use.
        
    Returns:
        Configured memory handler.
    """
    try:
        return MemoryHandler(
            capacity=capacity,
            flushLevel=flush_level,
            target=target,
            formatter_type=formatter_type
        )
    except Exception as e:
        raise HandlerError(
            f"Failed to create memory handler: {e!s}",
            handler_name="MemoryHandler",
            handler_type="memory"
        ) from e
