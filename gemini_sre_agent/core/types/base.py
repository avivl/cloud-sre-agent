# gemini_sre_agent/core/types/base.py

"""
Core type definitions for the Gemini SRE Agent system.

This module defines fundamental type aliases, generic types, and type
utilities used throughout the system.
"""

from typing import Any, Protocol, TypeAlias, TypeVar

# Generic type variables
T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
R = TypeVar("R")

# Common type aliases
JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonDict: TypeAlias = dict[str, JsonValue]
JsonList: TypeAlias = list[JsonValue]

# Configuration types
ConfigDict: TypeAlias = dict[str, Any]
ConfigValue: TypeAlias = str | int | float | bool | None | list[Any] | dict[str, Any]

# Logging types
LogLevel: TypeAlias = str  # 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
LogMessage: TypeAlias = str
LogContext: TypeAlias = dict[str, Any]

# Agent types
AgentId: TypeAlias = str
AgentName: TypeAlias = str
AgentStatus: TypeAlias = str  # 'idle', 'running', 'error', 'stopped'

# LLM types
ModelId: TypeAlias = str
ProviderId: TypeAlias = str
PromptId: TypeAlias = str
ResponseId: TypeAlias = str

# Processing types
ProcessingStatus: TypeAlias = str  # 'pending', 'processing', 'completed', 'failed'
Priority: TypeAlias = int  # 1-10 scale
Confidence: TypeAlias = float  # 0.0-1.0 scale

# Monitoring types
MetricName: TypeAlias = str
MetricValue: TypeAlias = int | float
MetricTags: TypeAlias = dict[str, str]
MetricTimestamp: TypeAlias = float

# Error types
ErrorCode: TypeAlias = str
ErrorMessage: TypeAlias = str
ErrorDetails: TypeAlias = dict[str, Any]

# Time types
Timestamp: TypeAlias = float
Duration: TypeAlias = float
Timeout: TypeAlias = float

# ID types
RequestId: TypeAlias = str
SessionId: TypeAlias = str
UserId: TypeAlias = str
TenantId: TypeAlias = str

# Content types
Content: TypeAlias = str
ContentType: TypeAlias = str
ContentEncoding: TypeAlias = str


# Protocol definitions for structural typing
class Serializable(Protocol):
    """Protocol for objects that can be serialized to JSON."""

    def to_dict(self) -> JsonDict:
        """Convert object to dictionary representation."""
        ...

    def to_json(self) -> str:
        """Convert object to JSON string."""
        ...


class Deserializable(Protocol):
    """Protocol for objects that can be deserialized from JSON."""

    @classmethod
    def from_dict(cls: type[T], data: JsonDict) -> T:
        """Create object from dictionary representation."""
        ...

    @classmethod
    def from_json(cls: type[T], json_str: str) -> T:
        """Create object from JSON string."""
        ...


class Identifiable(Protocol):
    """Protocol for objects that have a unique identifier."""

    @property
    def id(self) -> str:
        """Get the unique identifier."""
        ...


class Timestamped(Protocol):
    """Protocol for objects that have timestamps."""

    @property
    def created_at(self) -> Timestamp:
        """Get creation timestamp."""
        ...

    @property
    def updated_at(self) -> Timestamp:
        """Get last update timestamp."""
        ...


class Configurable(Protocol):
    """Protocol for objects that can be configured."""

    def configure(self, config: ConfigDict) -> None:
        """Configure the object with given configuration."""
        ...

    def get_config(self) -> ConfigDict:
        """Get current configuration."""
        ...


class Stateful(Protocol):
    """Protocol for objects that maintain state."""

    @property
    def state(self) -> str:
        """Get current state."""
        ...

    def set_state(self, state: str) -> None:
        """Set new state."""
        ...


class Loggable(Protocol):
    """Protocol for objects that can be logged."""

    def get_log_context(self) -> LogContext:
        """Get logging context information."""
        ...


class Validatable(Protocol):
    """Protocol for objects that can be validated."""

    def validate(self) -> bool:
        """Validate the object."""
        ...

    def get_validation_errors(self) -> list[str]:
        """Get validation errors if any."""
        ...


# Utility type functions
def is_json_value(value: Any) -> bool:
    """
    Check if a value is a valid JSON value.

    Args:
        value: Value to check

    Returns:
        True if value is a valid JSON value, False otherwise
    """
    if value is None:
        return True
    if isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and is_json_value(v) for k, v in value.items())
    return False


def ensure_json_value(value: Any) -> JsonValue:
    """
    Ensure a value is a valid JSON value, converting if necessary.

    Args:
        value: Value to ensure

    Returns:
        Valid JSON value

    Raises:
        ValueError: If value cannot be converted to JSON value
    """
    if is_json_value(value):
        return value

    # Try to convert common types
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return {k: ensure_json_value(v) for k, v in value.__dict__.items()}

    raise ValueError(f"Cannot convert {type(value)} to JSON value")


def create_type_safe_dict(data: dict[str, Any]) -> JsonDict:
    """
    Create a type-safe JSON dictionary from a regular dictionary.

    Args:
        data: Dictionary to convert

    Returns:
        Type-safe JSON dictionary

    Raises:
        ValueError: If any value cannot be converted to JSON value
    """
    result = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise ValueError(f"Dictionary key must be string, got {type(key)}")
        result[key] = ensure_json_value(value)
    return result
