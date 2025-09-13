# gemini_sre_agent/core/logging/structured.py
"""
Structured logging implementation.

This module provides structured logging capabilities with support for
JSON formatting, context management, and advanced features.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import logging
import sys
import threading
import time
import traceback
from typing import Any

from .metrics import record_log_metrics


class LogLevel(Enum):
    """Log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    def __str__(self) -> str:
        return self.value


@dataclass
class LogFormat:
    """Log format configuration."""

    timestamp: bool = True
    level: bool = True
    logger_name: bool = True
    message: bool = True
    context: bool = True
    exception: bool = True
    stack_trace: bool = False
    process_id: bool = False
    thread_id: bool = False
    module: bool = False
    function: bool = False
    line_number: bool = False

    def to_dict(self) -> dict[str, bool]:
        """Convert to dictionary.
        
        Returns:
            Dictionary representation.
        """
        return asdict(self)


@dataclass
class LogContext:
    """Logging context information."""

    request_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    service_name: str | None = None
    version: str | None = None
    environment: str | None = None
    custom_fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.
        
        Returns:
            Dictionary representation.
        """
        result = {}

        if self.request_id:
            result["request_id"] = self.request_id
        if self.user_id:
            result["user_id"] = self.user_id
        if self.session_id:
            result["session_id"] = self.session_id
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.trace_id:
            result["trace_id"] = self.trace_id
        if self.span_id:
            result["span_id"] = self.span_id
        if self.service_name:
            result["service_name"] = self.service_name
        if self.version:
            result["version"] = self.version
        if self.environment:
            result["environment"] = self.environment

        result.update(self.custom_fields)
        return result

    def merge(self, other: "LogContext") -> "LogContext":
        """Merge with another context.
        
        Args:
            other: Other context to merge with.
            
        Returns:
            New merged context.
        """
        merged = LogContext()

        # Merge fields, preferring non-None values
        for field_name in ["request_id", "user_id", "session_id", "correlation_id",
                          "trace_id", "span_id", "service_name", "version", "environment"]:
            value = getattr(self, field_name) or getattr(other, field_name)
            setattr(merged, field_name, value)

        # Merge custom fields
        merged.custom_fields = {**other.custom_fields, **self.custom_fields}

        return merged


class StructuredLogger:
    """Structured logger with advanced features."""

    def __init__(
        self,
        name: str,
        level: str | int | LogLevel = LogLevel.INFO,
        formatter: LogFormat | None = None,
        context: LogContext | None = None
    ):
        """Initialize the structured logger.
        
        Args:
            name: Logger name.
            level: Log level.
            formatter: Log format configuration.
            context: Default context.
        """
        self.name = name
        self.logger = logging.getLogger(name)

        # Set level
        if isinstance(level, LogLevel):
            level = level.value
        elif isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)

        self.logger.setLevel(level)

        # Set formatter
        self.formatter = formatter or LogFormat()

        # Set context
        self.context = context or LogContext()

        # Performance tracking
        self._start_times: dict[str, float] = {}

    def _format_message(
        self,
        level: str,
        message: str,
        context: LogContext | None = None,
        exception: Exception | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """Format a log message.
        
        Args:
            level: Log level.
            message: Log message.
            context: Additional context.
            exception: Exception to log.
            **kwargs: Additional fields.
            
        Returns:
            Formatted log entry.
        """
        # Merge contexts
        merged_context = self.context.merge(context) if context else self.context

        # Build log entry
        log_entry = {}

        if self.formatter.timestamp:
            log_entry["timestamp"] = time.time()

        if self.formatter.level:
            log_entry["level"] = level

        if self.formatter.logger_name:
            log_entry["logger"] = self.name

        if self.formatter.message:
            log_entry["message"] = message

        if self.formatter.context and merged_context.to_dict():
            log_entry["context"] = merged_context.to_dict()

        # Add exception information
        if exception and self.formatter.exception:
            log_entry["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception)
            }

            if self.formatter.stack_trace:
                log_entry["exception"]["traceback"] = traceback.format_exc()

        # Add process/thread information
        if self.formatter.process_id:
            log_entry["process_id"] = sys.getpid()

        if self.formatter.thread_id:
            log_entry["thread_id"] = threading.get_ident()

        # Add module information
        if self.formatter.module or self.formatter.function or self.formatter.line_number:
            frame = sys._getframe(2)  # Go up two frames to get caller
            if self.formatter.module:
                log_entry["module"] = frame.f_globals.get("__name__", "unknown")
            if self.formatter.function:
                log_entry["function"] = frame.f_code.co_name
            if self.formatter.line_number:
                log_entry["line_number"] = frame.f_lineno

        # Add additional fields
        log_entry.update(kwargs)

        return log_entry

    def _log(
        self,
        level: str,
        message: str,
        context: LogContext | None = None,
        exception: Exception | None = None,
        **kwargs
    ) -> None:
        """Log a message.
        
        Args:
            level: Log level.
            message: Log message.
            context: Additional context.
            exception: Exception to log.
            **kwargs: Additional fields.
        """
        start_time = time.time()

        try:
            # Format message
            log_entry = self._format_message(level, message, context, exception, **kwargs)

            # Convert to JSON
            json_message = json.dumps(log_entry, default=str, ensure_ascii=False)

            # Log using standard logger
            log_level = getattr(logging, level.upper(), logging.INFO)
            self.logger.log(log_level, json_message)

            # Record metrics
            processing_time = time.time() - start_time
            record_log_metrics(level, processing_time)

        except Exception as e:
            # Fallback to simple logging
            self.logger.error(f"Failed to log structured message: {e}")
            self.logger.log(
                getattr(logging, level.upper(), logging.INFO),
                f"[{level}] {message}"
            )

    def debug(
        self,
        message: str,
        context: LogContext | None = None,
        **kwargs
    ) -> None:
        """Log a debug message.
        
        Args:
            message: Log message.
            context: Additional context.
            **kwargs: Additional fields.
        """
        self._log("DEBUG", message, context, **kwargs)

    def info(
        self,
        message: str,
        context: LogContext | None = None,
        **kwargs
    ) -> None:
        """Log an info message.
        
        Args:
            message: Log message.
            context: Additional context.
            **kwargs: Additional fields.
        """
        self._log("INFO", message, context, **kwargs)

    def warning(
        self,
        message: str,
        context: LogContext | None = None,
        **kwargs
    ) -> None:
        """Log a warning message.
        
        Args:
            message: Log message.
            context: Additional context.
            **kwargs: Additional fields.
        """
        self._log("WARNING", message, context, **kwargs)

    def error(
        self,
        message: str,
        context: LogContext | None = None,
        exception: Exception | None = None,
        **kwargs
    ) -> None:
        """Log an error message.
        
        Args:
            message: Log message.
            context: Additional context.
            exception: Exception to log.
            **kwargs: Additional fields.
        """
        self._log("ERROR", message, context, exception, **kwargs)

    def critical(
        self,
        message: str,
        context: LogContext | None = None,
        exception: Exception | None = None,
        **kwargs
    ) -> None:
        """Log a critical message.
        
        Args:
            message: Log message.
            context: Additional context.
            exception: Exception to log.
            **kwargs: Additional fields.
        """
        self._log("CRITICAL", message, context, exception, **kwargs)

    def with_context(self, context: LogContext) -> "StructuredLogger":
        """Create a new logger with additional context.
        
        Args:
            context: Additional context.
            
        Returns:
            New logger with merged context.
        """
        merged_context = self.context.merge(context)
        return StructuredLogger(
            name=self.name,
            level=self.logger.level,
            formatter=self.formatter,
            context=merged_context
        )

    def start_timer(self, operation: str) -> None:
        """Start timing an operation.
        
        Args:
            operation: Operation name.
        """
        self._start_times[operation] = time.time()

    def end_timer(self, operation: str, message: str | None = None) -> None:
        """End timing an operation and log the duration.
        
        Args:
            operation: Operation name.
            message: Optional message to log with timing.
        """
        if operation not in self._start_times:
            self.warning(f"Timer '{operation}' was not started")
            return

        duration = time.time() - self._start_times[operation]
        del self._start_times[operation]

        log_message = message or f"Operation '{operation}' completed"
        self.info(log_message, **{f"{operation}_duration": duration})

    def measure_time(self, operation: str):
        """Context manager for measuring operation time.
        
        Args:
            operation: Operation name.
            
        Returns:
            Context manager.
        """
        return TimerContext(self, operation)

    def set_level(self, level: str | int | LogLevel) -> None:
        """Set the log level.
        
        Args:
            level: Log level.
        """
        if isinstance(level, LogLevel):
            level = level.value
        elif isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)

        self.logger.setLevel(level)

    def add_handler(self, handler: logging.Handler) -> None:
        """Add a handler to the logger.
        
        Args:
            handler: Handler to add.
        """
        self.logger.addHandler(handler)

    def remove_handler(self, handler: logging.Handler) -> None:
        """Remove a handler from the logger.
        
        Args:
            handler: Handler to remove.
        """
        self.logger.removeHandler(handler)

    def get_handlers(self) -> list[logging.Handler]:
        """Get all handlers.
        
        Returns:
            List of handlers.
        """
        return self.logger.handlers.copy()


class TimerContext:
    """Context manager for timing operations."""

    def __init__(self, logger: StructuredLogger, operation: str):
        """Initialize the timer context.
        
        Args:
            logger: Logger instance.
            operation: Operation name.
        """
        self.logger = logger
        self.operation = operation

    def __enter__(self):
        """Enter the context."""
        self.logger.start_timer(self.operation)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context."""
        if exc_type is None:
            self.logger.end_timer(self.operation)
        else:
            self.logger.end_timer(
                self.operation,
                f"Operation '{self.operation}' failed"
            )


def get_structured_logger(
    name: str,
    level: str | int | LogLevel = LogLevel.INFO,
    formatter: LogFormat | None = None,
    context: LogContext | None = None
) -> StructuredLogger:
    """Get a structured logger.
    
    Args:
        name: Logger name.
        level: Log level.
        formatter: Log format configuration.
        context: Default context.
        
    Returns:
        Structured logger instance.
    """
    return StructuredLogger(name, level, formatter, context)


def create_log_context(**kwargs) -> LogContext:
    """Create a log context.
    
    Args:
        **kwargs: Context fields.
        
    Returns:
        Log context instance.
    """
    return LogContext(**kwargs)


def create_log_format(**kwargs) -> LogFormat:
    """Create a log format.
    
    Args:
        **kwargs: Format fields.
        
    Returns:
        Log format instance.
    """
    return LogFormat(**kwargs)
