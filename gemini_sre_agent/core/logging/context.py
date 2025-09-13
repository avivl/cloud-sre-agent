# gemini_sre_agent/core/logging/context.py
"""
Logging context management.

This module provides context management for structured logging,
including flow tracking and contextual information.
"""

import contextvars
from dataclasses import dataclass, field
from datetime import datetime
import threading
from typing import Any

# Context variables for thread-local storage
_logging_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "logging_context", default={}
)
_flow_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "flow_context", default=None
)


@dataclass
class LoggingContext:
    """Context for structured logging operations."""

    # Core context
    flow_id: str | None = None
    operation: str | None = None
    user_id: str | None = None
    request_id: str | None = None
    session_id: str | None = None

    # Additional context
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)

    # Timing
    start_time: datetime | None = None
    end_time: datetime | None = None

    # Performance
    duration: float | None = None
    memory_usage: int | None = None

    def __post_init__(self):
        """Initialize context after creation."""
        if self.start_time is None:
            self.start_time = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary.
        
        Returns:
            Dictionary representation of the context.
        """
        return {
            "flow_id": self.flow_id,
            "operation": self.operation,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "metadata": self.metadata,
            "tags": self.tags,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "memory_usage": self.memory_usage,
        }

    def update(self, **kwargs: Any) -> None:
        """Update context with new values.
        
        Args:
            **kwargs: Key-value pairs to update in the context.
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.metadata[key] = value

    def add_tag(self, key: str, value: str) -> None:
        """Add a tag to the context.
        
        Args:
            key: Tag key.
            value: Tag value.
        """
        self.tags[key] = value

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the context.
        
        Args:
            key: Metadata key.
            value: Metadata value.
        """
        self.metadata[key] = value

    def finish(self) -> None:
        """Mark the context as finished and calculate duration."""
        self.end_time = datetime.now()
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()


class ContextManager:
    """Manages logging context across the application."""

    def __init__(self):
        """Initialize the context manager."""
        self._local = threading.local()

    def get_context(self) -> LoggingContext:
        """Get the current logging context.
        
        Returns:
            Current logging context.
        """
        context_data = _logging_context.get({})
        return LoggingContext(**context_data)

    def set_context(self, context: LoggingContext) -> None:
        """Set the current logging context.
        
        Args:
            context: Logging context to set.
        """
        _logging_context.set(context.to_dict())

    def update_context(self, **kwargs: Any) -> None:
        """Update the current logging context.
        
        Args:
            **kwargs: Key-value pairs to update.
        """
        current = self.get_context()
        current.update(**kwargs)
        self.set_context(current)

    def clear_context(self) -> None:
        """Clear the current logging context."""
        _logging_context.set({})

    def set_flow_id(self, flow_id: str) -> None:
        """Set the current flow ID.
        
        Args:
            flow_id: Flow ID to set.
        """
        _flow_context.set(flow_id)
        self.update_context(flow_id=flow_id)

    def get_flow_id(self) -> str | None:
        """Get the current flow ID.
        
        Returns:
            Current flow ID or None.
        """
        return _flow_context.get()

    def clear_flow_id(self) -> None:
        """Clear the current flow ID."""
        _flow_context.set(None)
        self.update_context(flow_id=None)


# Global context manager instance
context_manager = ContextManager()


def get_logging_context() -> LoggingContext:
    """Get the current logging context.
    
    Returns:
        Current logging context.
    """
    return context_manager.get_context()


def set_logging_context(context: LoggingContext) -> None:
    """Set the current logging context.
    
    Args:
        context: Logging context to set.
    """
    context_manager.set_context(context)


def update_logging_context(**kwargs: Any) -> None:
    """Update the current logging context.
    
    Args:
        **kwargs: Key-value pairs to update.
    """
    context_manager.update_context(**kwargs)


def clear_logging_context() -> None:
    """Clear the current logging context."""
    context_manager.clear_context()


def set_flow_id(flow_id: str) -> None:
    """Set the current flow ID.
    
    Args:
        flow_id: Flow ID to set.
    """
    context_manager.set_flow_id(flow_id)


def get_flow_id() -> str | None:
    """Get the current flow ID.
    
    Returns:
        Current flow ID or None.
    """
    return context_manager.get_flow_id()


def clear_flow_id() -> None:
    """Clear the current flow ID."""
    context_manager.clear_flow_id()


class LoggingContextMixin:
    """Mixin class for adding logging context support to classes."""

    def __init__(self, *args, **kwargs):
        """Initialize the mixin."""
        super().__init__(*args, **kwargs)
        self._logging_context = LoggingContext()

    @property
    def logging_context(self) -> LoggingContext:
        """Get the logging context for this instance.
        
        Returns:
            Logging context for this instance.
        """
        return self._logging_context

    def update_logging_context(self, **kwargs: Any) -> None:
        """Update the logging context for this instance.
        
        Args:
            **kwargs: Key-value pairs to update.
        """
        self._logging_context.update(**kwargs)

    def add_logging_tag(self, key: str, value: str) -> None:
        """Add a tag to the logging context.
        
        Args:
            key: Tag key.
            value: Tag value.
        """
        self._logging_context.add_tag(key, value)

    def add_logging_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the logging context.
        
        Args:
            key: Metadata key.
            value: Metadata value.
        """
        self._logging_context.add_metadata(key, value)


def with_logging_context(**context_kwargs: Any):
    """Decorator to add logging context to a function.
    
    Args:
        **context_kwargs: Context parameters to set.
        
    Returns:
        Decorated function with logging context.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Create context
            context = LoggingContext(**context_kwargs)

            # Set context
            old_context = get_logging_context()
            set_logging_context(context)

            try:
                # Execute function
                result = func(*args, **kwargs)
                return result
            finally:
                # Restore context
                set_logging_context(old_context)

        return wrapper
    return decorator


def with_flow_tracking(flow_id: str | None = None, operation: str | None = None):
    """Decorator to add flow tracking to a function.
    
    Args:
        flow_id: Flow ID to use (generated if None).
        operation: Operation name.
        
    Returns:
        Decorated function with flow tracking.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate flow ID if not provided
            if flow_id is None:
                import uuid
                current_flow_id = str(uuid.uuid4())
            else:
                current_flow_id = flow_id

            # Set flow context
            set_flow_id(current_flow_id)
            update_logging_context(operation=operation or func.__name__)

            try:
                # Execute function
                result = func(*args, **kwargs)
                return result
            finally:
                # Clear flow context
                clear_flow_id()

        return wrapper
    return decorator
