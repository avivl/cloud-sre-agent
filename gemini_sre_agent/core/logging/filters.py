# gemini_sre_agent/core/logging/filters.py
"""
Custom log filters for structured logging.

This module provides various filters for controlling log output
and adding contextual information.
"""

import logging
import re
from typing import Any

from .context import get_logging_context
from .exceptions import FilterError


class LevelFilter(logging.Filter):
    """Filter logs based on level thresholds."""

    def __init__(self, min_level: int, max_level: int = logging.CRITICAL):
        """Initialize the level filter.
        
        Args:
            min_level: Minimum log level to allow.
            max_level: Maximum log level to allow.
        """
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record based on level.
        
        Args:
            record: Log record to filter.
            
        Returns:
            True if record should be logged, False otherwise.
        """
        try:
            return self.min_level <= record.levelno <= self.max_level
        except Exception as e:
            raise FilterError(
                f"Failed to filter log record by level: {e!s}",
                filter_name="LevelFilter",
                filter_type="level"
            ) from e


class NameFilter(logging.Filter):
    """Filter logs based on logger names."""

    def __init__(self, name_patterns: str | list[str], exclude: bool = False):
        """Initialize the name filter.
        
        Args:
            name_patterns: Logger name patterns to match.
            exclude: Whether to exclude matching names.
        """
        super().__init__()
        if isinstance(name_patterns, str):
            name_patterns = [name_patterns]

        self.name_patterns = [re.compile(pattern) for pattern in name_patterns]
        self.exclude = exclude

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record based on logger name.
        
        Args:
            record: Log record to filter.
            
        Returns:
            True if record should be logged, False otherwise.
        """
        try:
            matches = any(pattern.search(record.name) for pattern in self.name_patterns)
            return not matches if self.exclude else matches
        except Exception as e:
            raise FilterError(
                f"Failed to filter log record by name: {e!s}",
                filter_name="NameFilter",
                filter_type="name"
            ) from e


class MessageFilter(logging.Filter):
    """Filter logs based on message content."""

    def __init__(self, message_patterns: str | list[str], exclude: bool = False):
        """Initialize the message filter.
        
        Args:
            message_patterns: Message patterns to match.
            exclude: Whether to exclude matching messages.
        """
        super().__init__()
        if isinstance(message_patterns, str):
            message_patterns = [message_patterns]

        self.message_patterns = [re.compile(pattern) for pattern in message_patterns]
        self.exclude = exclude

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record based on message content.
        
        Args:
            record: Log record to filter.
            
        Returns:
            True if record should be logged, False otherwise.
        """
        try:
            message = record.getMessage()
            matches = any(pattern.search(message) for pattern in self.message_patterns)
            return not matches if self.exclude else matches
        except Exception as e:
            raise FilterError(
                f"Failed to filter log record by message: {e!s}",
                filter_name="MessageFilter",
                filter_type="message"
            ) from e


class ContextFilter(logging.Filter):
    """Filter logs based on logging context."""

    def __init__(
        self,
        flow_id_pattern: str | None = None,
        operation_pattern: str | None = None,
        user_id_pattern: str | None = None,
        exclude: bool = False
    ):
        """Initialize the context filter.
        
        Args:
            flow_id_pattern: Flow ID pattern to match.
            operation_pattern: Operation pattern to match.
            user_id_pattern: User ID pattern to match.
            exclude: Whether to exclude matching context.
        """
        super().__init__()

        self.flow_id_pattern = re.compile(flow_id_pattern) if flow_id_pattern else None
        self.operation_pattern = re.compile(operation_pattern) if operation_pattern else None
        self.user_id_pattern = re.compile(user_id_pattern) if user_id_pattern else None
        self.exclude = exclude

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record based on context.
        
        Args:
            record: Log record to filter.
            
        Returns:
            True if record should be logged, False otherwise.
        """
        try:
            context = get_logging_context()

            matches = []

            if self.flow_id_pattern and context.flow_id:
                matches.append(self.flow_id_pattern.search(context.flow_id) is not None)

            if self.operation_pattern and context.operation:
                matches.append(self.operation_pattern.search(context.operation) is not None)

            if self.user_id_pattern and context.user_id:
                matches.append(self.user_id_pattern.search(context.user_id) is not None)

            # If no patterns specified, allow all
            if not matches:
                return True

            # All specified patterns must match
            result = all(matches)
            return not result if self.exclude else result

        except Exception as e:
            raise FilterError(
                f"Failed to filter log record by context: {e!s}",
                filter_name="ContextFilter",
                filter_type="context"
            ) from e


class SamplingFilter(logging.Filter):
    """Filter logs based on sampling rate."""

    def __init__(self, sample_rate: float = 1.0, seed: int | None = None):
        """Initialize the sampling filter.
        
        Args:
            sample_rate: Fraction of logs to allow (0.0 to 1.0).
            seed: Random seed for reproducible sampling.
        """
        super().__init__()

        if not 0.0 <= sample_rate <= 1.0:
            raise ValueError("Sample rate must be between 0.0 and 1.0")

        self.sample_rate = sample_rate

        if seed is not None:
            import random
            random.seed(seed)

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record based on sampling rate.
        
        Args:
            record: Log record to filter.
            
        Returns:
            True if record should be logged, False otherwise.
        """
        try:
            import random
            return random.random() < self.sample_rate
        except Exception as e:
            raise FilterError(
                f"Failed to filter log record by sampling: {e!s}",
                filter_name="SamplingFilter",
                filter_type="sampling"
            ) from e


class RateLimitFilter(logging.Filter):
    """Filter logs based on rate limiting."""

    def __init__(self, max_logs_per_second: float = 10.0):
        """Initialize the rate limit filter.
        
        Args:
            max_logs_per_second: Maximum logs per second to allow.
        """
        super().__init__()

        self.max_logs_per_second = max_logs_per_second
        self.log_times = []
        self.window_size = 1.0  # 1 second window

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record based on rate limiting.
        
        Args:
            record: Log record to filter.
            
        Returns:
            True if record should be logged, False otherwise.
        """
        try:
            import time

            current_time = time.time()

            # Remove old log times outside the window
            self.log_times = [
                log_time for log_time in self.log_times
                if current_time - log_time < self.window_size
            ]

            # Check if we're within the rate limit
            if len(self.log_times) < self.max_logs_per_second:
                self.log_times.append(current_time)
                return True

            return False

        except Exception as e:
            raise FilterError(
                f"Failed to filter log record by rate limiting: {e!s}",
                filter_name="RateLimitFilter",
                filter_type="rate_limit"
            ) from e


class DuplicateFilter(logging.Filter):
    """Filter duplicate log messages."""

    def __init__(self, window_size: int = 100, max_duplicates: int = 5):
        """Initialize the duplicate filter.
        
        Args:
            window_size: Number of recent messages to check for duplicates.
            max_duplicates: Maximum number of duplicate messages to allow.
        """
        super().__init__()

        self.window_size = window_size
        self.max_duplicates = max_duplicates
        self.message_counts = {}
        self.message_times = []

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter duplicate log messages.
        
        Args:
            record: Log record to filter.
            
        Returns:
            True if record should be logged, False otherwise.
        """
        try:
            import time

            current_time = time.time()
            message = record.getMessage()

            # Clean up old messages
            cutoff_time = current_time - 60.0  # 1 minute window
            self.message_times = [
                msg_time for msg_time in self.message_times
                if msg_time > cutoff_time
            ]

            # Count occurrences of this message
            if message not in self.message_counts:
                self.message_counts[message] = 0

            self.message_counts[message] += 1
            self.message_times.append((current_time, message))

            # Check if we've exceeded the duplicate limit
            if self.message_counts[message] > self.max_duplicates:
                return False

            return True

        except Exception as e:
            raise FilterError(
                f"Failed to filter duplicate log messages: {e!s}",
                filter_name="DuplicateFilter",
                filter_type="duplicate"
            ) from e


class SensitiveDataFilter(logging.Filter):
    """Filter sensitive data from log messages."""

    def __init__(self, sensitive_patterns: str | list[str]):
        """Initialize the sensitive data filter.
        
        Args:
            sensitive_patterns: Patterns to identify sensitive data.
        """
        super().__init__()

        if isinstance(sensitive_patterns, str):
            sensitive_patterns = [sensitive_patterns]

        self.sensitive_patterns = [re.compile(pattern) for pattern in sensitive_patterns]
        self.replacement = "[REDACTED]"

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter sensitive data from log messages.
        
        Args:
            record: Log record to filter.
            
        Returns:
            True if record should be logged, False otherwise.
        """
        try:
            message = record.getMessage()

            # Check for sensitive patterns
            for pattern in self.sensitive_patterns:
                if pattern.search(message):
                    # Replace sensitive data
                    record.msg = pattern.sub(self.replacement, message)
                    record.args = ()  # Clear args to avoid re-formatting

            return True

        except Exception as e:
            raise FilterError(
                f"Failed to filter sensitive data: {e!s}",
                filter_name="SensitiveDataFilter",
                filter_type="sensitive_data"
            ) from e


class CompositeFilter(logging.Filter):
    """Composite filter that combines multiple filters."""

    def __init__(self, filters: list[logging.Filter], mode: str = "and"):
        """Initialize the composite filter.
        
        Args:
            filters: List of filters to combine.
            mode: Combination mode ('and', 'or', 'not').
        """
        super().__init__()

        self.filters = filters
        self.mode = mode.lower()

        if self.mode not in ["and", "or", "not"]:
            raise ValueError("Mode must be 'and', 'or', or 'not'")

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record using composite logic.
        
        Args:
            record: Log record to filter.
            
        Returns:
            True if record should be logged, False otherwise.
        """
        try:
            if not self.filters:
                return True

            results = [f.filter(record) for f in self.filters]

            if self.mode == "and":
                return all(results)
            elif self.mode == "or":
                return any(results)
            elif self.mode == "not":
                return not any(results)

            return True

        except Exception as e:
            raise FilterError(
                f"Failed to filter log record with composite filter: {e!s}",
                filter_name="CompositeFilter",
                filter_type="composite"
            ) from e


def create_filter(filter_type: str, **kwargs: Any) -> logging.Filter:
    """Create a filter by type.
    
    Args:
        filter_type: Type of filter to create.
        **kwargs: Additional arguments for the filter.
        
    Returns:
        Configured filter instance.
        
    Raises:
        FilterError: If filter type is not supported.
    """
    filters = {
        "level": LevelFilter,
        "name": NameFilter,
        "message": MessageFilter,
        "context": ContextFilter,
        "sampling": SamplingFilter,
        "rate_limit": RateLimitFilter,
        "duplicate": DuplicateFilter,
        "sensitive_data": SensitiveDataFilter,
        "composite": CompositeFilter
    }

    if filter_type not in filters:
        raise FilterError(
            f"Unsupported filter type: {filter_type}",
            filter_type=filter_type
        )

    try:
        return filters[filter_type](**kwargs)
    except Exception as e:
        raise FilterError(
            f"Failed to create filter: {e!s}",
            filter_name=filter_type,
            filter_type=filter_type
        ) from e
