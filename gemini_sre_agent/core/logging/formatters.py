# gemini_sre_agent/core/logging/formatters.py
"""
Log formatters for structured logging.

This module provides various formatters for different logging output formats.
"""

from datetime import datetime
import json
import logging
from typing import Any

from .context import get_logging_context
from .exceptions import FormatterError


class StructuredFormatter(logging.Formatter):
    """Structured formatter for consistent log output."""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        include_context: bool = True,
        include_metadata: bool = True
    ):
        """Initialize the structured formatter.
        
        Args:
            fmt: Log format string.
            datefmt: Date format string.
            include_context: Whether to include logging context.
            include_metadata: Whether to include metadata.
        """
        if fmt is None:
            fmt = "%(asctime)s [%(levelname)8s] %(name)s: %(message)s"

        super().__init__(fmt, datefmt)
        self.include_context = include_context
        self.include_metadata = include_metadata

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record.
        
        Args:
            record: Log record to format.
            
        Returns:
            Formatted log message.
        """
        try:
            # Get base formatted message
            message = super().format(record)

            if not self.include_context:
                return message

            # Get logging context
            context = get_logging_context()

            # Add context information
            context_parts = []

            if context.flow_id:
                context_parts.append(f"flow_id={context.flow_id}")

            if context.operation:
                context_parts.append(f"operation={context.operation}")

            if context.user_id:
                context_parts.append(f"user_id={context.user_id}")

            if context.request_id:
                context_parts.append(f"request_id={context.request_id}")

            if context.session_id:
                context_parts.append(f"session_id={context.session_id}")

            # Add tags
            if context.tags:
                for key, value in context.tags.items():
                    context_parts.append(f"{key}={value}")

            # Add metadata if requested
            if self.include_metadata and context.metadata:
                for key, value in context.metadata.items():
                    context_parts.append(f"{key}={value}")

            # Combine message and context
            if context_parts:
                context_str = " | ".join(context_parts)
                return f"{message} | {context_str}"

            return message

        except Exception as e:
            raise FormatterError(
                f"Failed to format log record: {e!s}",
                formatter_name="StructuredFormatter",
                formatter_type="structured"
            ) from e


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(
        self,
        include_context: bool = True,
        include_metadata: bool = True,
        include_exception: bool = True
    ):
        """Initialize the JSON formatter.
        
        Args:
            include_context: Whether to include logging context.
            include_metadata: Whether to include metadata.
            include_exception: Whether to include exception information.
        """
        super().__init__()
        self.include_context = include_context
        self.include_metadata = include_metadata
        self.include_exception = include_exception

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON.
        
        Args:
            record: Log record to format.
            
        Returns:
            JSON formatted log message.
        """
        try:
            # Base log data
            log_data = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
                "thread": record.thread,
                "process": record.process,
            }

            # Add exception information
            if self.include_exception and record.exc_info:
                log_data["exception"] = {
                    "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                    "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                    "traceback": self.formatException(record.exc_info) if record.exc_info else None
                }

            # Add context information
            if self.include_context:
                context = get_logging_context()
                context_data = context.to_dict()

                # Add context fields
                for key, value in context_data.items():
                    if value is not None:
                        log_data[key] = value

            # Add custom fields from record
            for key, value in record.__dict__.items():
                if key not in log_data and not key.startswith("_"):
                    log_data[key] = value

            return json.dumps(log_data, default=str, ensure_ascii=False)

        except Exception as e:
            raise FormatterError(
                f"Failed to format log record as JSON: {e!s}",
                formatter_name="JSONFormatter",
                formatter_type="json"
            ) from e


class FlowFormatter(logging.Formatter):
    """Formatter optimized for flow tracking."""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        include_flow_details: bool = True
    ):
        """Initialize the flow formatter.
        
        Args:
            fmt: Log format string.
            datefmt: Date format string.
            include_flow_details: Whether to include flow details.
        """
        if fmt is None:
            fmt = "%(asctime)s [%(levelname)8s] [%(flow_id)s] %(name)s: %(message)s"

        super().__init__(fmt, datefmt)
        self.include_flow_details = include_flow_details

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record for flow tracking.
        
        Args:
            record: Log record to format.
            
        Returns:
            Formatted log message.
        """
        try:
            # Get logging context
            context = get_logging_context()

            # Add flow information to record
            record.flow_id = context.flow_id or "unknown"
            record.operation = context.operation or "unknown"
            record.user_id = context.user_id or "unknown"
            record.request_id = context.request_id or "unknown"

            # Get base formatted message
            message = super().format(record)

            if not self.include_flow_details:
                return message

            # Add flow details
            flow_parts = []

            if context.operation:
                flow_parts.append(f"op={context.operation}")

            if context.user_id:
                flow_parts.append(f"user={context.user_id}")

            if context.request_id:
                flow_parts.append(f"req={context.request_id}")

            if context.duration is not None:
                flow_parts.append(f"dur={context.duration:.3f}s")

            if context.memory_usage is not None:
                flow_parts.append(f"mem={context.memory_usage}MB")

            # Add tags
            if context.tags:
                for key, value in context.tags.items():
                    flow_parts.append(f"{key}={value}")

            # Combine message and flow details
            if flow_parts:
                flow_str = " | ".join(flow_parts)
                return f"{message} | {flow_str}"

            return message

        except Exception as e:
            raise FormatterError(
                f"Failed to format log record for flow tracking: {e!s}",
                formatter_name="FlowFormatter",
                formatter_type="flow"
            ) from e


class TextFormatter(logging.Formatter):
    """Simple text formatter for human-readable logs."""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        colorize: bool = False
    ):
        """Initialize the text formatter.
        
        Args:
            fmt: Log format string.
            datefmt: Date format string.
            colorize: Whether to add color to the output.
        """
        if fmt is None:
            fmt = "%(asctime)s [%(levelname)8s] %(name)s: %(message)s"

        super().__init__(fmt, datefmt)
        self.colorize = colorize

        # Color codes for different log levels
        self.colors = {
            "DEBUG": "\033[36m",    # Cyan
            "INFO": "\033[32m",     # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",    # Red
            "CRITICAL": "\033[35m", # Magenta
            "RESET": "\033[0m"      # Reset
        }

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as text.
        
        Args:
            record: Log record to format.
            
        Returns:
            Text formatted log message.
        """
        try:
            # Get base formatted message
            message = super().format(record)

            if not self.colorize:
                return message

            # Add color based on log level
            level_color = self.colors.get(record.levelname, "")
            reset_color = self.colors["RESET"]

            if level_color:
                # Colorize the level name
                message = message.replace(
                    f"[{record.levelname:8s}]",
                    f"{level_color}[{record.levelname:8s}]{reset_color}"
                )

            return message

        except Exception as e:
            raise FormatterError(
                f"Failed to format log record as text: {e!s}",
                formatter_name="TextFormatter",
                formatter_type="text"
            ) from e


class CompactFormatter(logging.Formatter):
    """Compact formatter for high-volume logging."""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None
    ):
        """Initialize the compact formatter.
        
        Args:
            fmt: Log format string.
            datefmt: Date format string.
        """
        if fmt is None:
            fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"

        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record in compact format.
        
        Args:
            record: Log record to format.
            
        Returns:
            Compact formatted log message.
        """
        try:
            return super().format(record)
        except Exception as e:
            raise FormatterError(
                f"Failed to format log record in compact format: {e!s}",
                formatter_name="CompactFormatter",
                formatter_type="compact"
            ) from e


def get_formatter(formatter_type: str, **kwargs: Any) -> logging.Formatter:
    """Get a formatter by type.
    
    Args:
        formatter_type: Type of formatter to get.
        **kwargs: Additional arguments for the formatter.
        
    Returns:
        Configured formatter instance.
        
    Raises:
        FormatterError: If formatter type is not supported.
    """
    formatters = {
        "structured": StructuredFormatter,
        "json": JSONFormatter,
        "flow": FlowFormatter,
        "text": TextFormatter,
        "compact": CompactFormatter
    }

    if formatter_type not in formatters:
        raise FormatterError(
            f"Unsupported formatter type: {formatter_type}",
            formatter_type=formatter_type
        )

    try:
        return formatters[formatter_type](**kwargs)
    except Exception as e:
        raise FormatterError(
            f"Failed to create formatter: {e!s}",
            formatter_name=formatter_type,
            formatter_type=formatter_type
        ) from e
