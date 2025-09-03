# gemini_sre_agent/ingestion/interfaces/core.py

"""
Core interfaces and data structures for log ingestion.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, Optional


class LogSourceType(Enum):
    """Supported log source types."""

    GCP_PUBSUB = "gcp_pubsub"
    GCP_LOGGING = "gcp_logging"
    FILE_SYSTEM = "file_system"
    AWS_CLOUDWATCH = "aws_cloudwatch"
    KUBERNETES = "kubernetes"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"


class LogSeverity(Enum):
    """Standardized log severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """Standardized log entry format with improved type safety."""

    # Core fields
    id: str  # Unique identifier (insertId, message_id, etc.)
    timestamp: datetime  # Use datetime instead of string for better type safety
    message: str  # Log message content

    # Flexible metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Standard optional fields
    severity: Optional[LogSeverity] = None
    source: Optional[str] = None
    service: Optional[str] = None
    environment: Optional[str] = None

    # Structured data
    labels: Dict[str, str] = field(default_factory=dict)
    resource: Dict[str, Any] = field(default_factory=dict)
    json_payload: Dict[str, Any] = field(default_factory=dict)

    # Flow tracking
    flow_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    def get_field(self, key: str, default=None):
        """Safely get field from metadata or attributes."""
        return getattr(self, key, self.metadata.get(key, default))


@dataclass
class SourceHealth:
    """Health status for a log source."""

    is_healthy: bool
    last_success: Optional[str] = None
    error_count: int = 0
    last_error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceConfig:
    """Base configuration for log sources."""

    name: str
    source_type: LogSourceType
    enabled: bool = True
    priority: int = 0  # Higher number = higher priority
    max_retries: int = 3
    retry_delay: float = 1.0
    health_check_interval: int = 30


class LogIngestionInterface(ABC):
    """Abstract interface for log ingestion sources with enhanced error handling."""

    @abstractmethod
    async def start(self) -> None:
        """Start the log ingestion process."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the log ingestion process gracefully."""
        pass

    @abstractmethod
    async def health_check(self) -> SourceHealth:
        """Check the health status of the log source."""
        pass

    @abstractmethod
    async def get_logs(self) -> AsyncIterator[LogEntry]:
        """Get logs from the source as an async iterator."""
        pass

    @abstractmethod
    def get_config(self) -> SourceConfig:
        """Get the current configuration for this source."""
        pass

    @abstractmethod
    async def update_config(self, config: SourceConfig) -> None:
        """Update the configuration for this source."""
        pass

    @abstractmethod
    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle errors with context. Return True if recoverable."""
        pass

    @abstractmethod
    async def get_health_metrics(self) -> Dict[str, Any]:
        """Get detailed health and performance metrics."""
        pass
