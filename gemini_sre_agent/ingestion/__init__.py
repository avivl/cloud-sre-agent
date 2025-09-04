# gemini_sre_agent/ingestion/__init__.py

"""
Log Ingestion System

A pluggable architecture for ingesting logs from multiple sources with
unified processing, error handling, and monitoring capabilities.
"""

from .interfaces import (
    BackpressureManager,
    ConfigurationError,
    LogEntry,
    LogIngestionError,
    LogIngestionInterface,
    LogParsingError,
    LogSeverity,
    LogSourceType,
    SourceAlreadyRunningError,
    SourceConfig,
    SourceConnectionError,
    SourceHealth,
    SourceNotFoundError,
    SourceNotRunningError,
    HyxResilientClient,
    create_resilience_config,
    ResilienceConfig,
)
from .adapters import (
    FileSystemAdapter,
    QueuedFileSystemAdapter,
    GCPLoggingAdapter,
    GCPPubSubAdapter,
    AWSCloudWatchAdapter,
    KubernetesAdapter,
)
from .queues import (
    MemoryQueue,
    QueueConfig,
    QueueStats,
    FileSystemQueue,
    FileQueueConfig,
)
from .manager import LogManager
from .processor import LogProcessor

__all__ = [
    # Core interfaces
    "LogIngestionInterface",
    "LogEntry",
    "LogSeverity",
    "SourceHealth",
    "SourceConfig",
    "LogSourceType",
    # Error handling
    "LogIngestionError",
    "SourceConnectionError",
    "LogParsingError",
    "ConfigurationError",
    "SourceNotFoundError",
    "SourceAlreadyRunningError",
    "SourceNotRunningError",
    "BackpressureManager",
    # Resilience
    "HyxResilientClient",
    "create_resilience_config",
    "ResilienceConfig",
    # Adapters
    "FileSystemAdapter",
    "QueuedFileSystemAdapter",
    "GCPLoggingAdapter",
    "GCPPubSubAdapter",
    "AWSCloudWatchAdapter",
    "KubernetesAdapter",
    # Queues
    "MemoryQueue",
    "QueueConfig",
    "QueueStats",
    "FileSystemQueue",
    "FileQueueConfig",
    # Main components
    "LogManager",
    "LogProcessor",
]
