# gemini_sre_agent/ingestion/__init__.py

"""
Log Ingestion System

A pluggable architecture for ingesting logs from multiple sources with
unified processing, error handling, and monitoring capabilities.
"""

from .adapters import (
    AWSCloudWatchAdapter,
    FileSystemAdapter,
    GCPLoggingAdapter,
    GCPPubSubAdapter,
    KubernetesAdapter,
    QueuedFileSystemAdapter,
)
from .interfaces import (
    BackpressureManager,
    ConfigurationError,
    HyxResilientClient,
    LogEntry,
    LogIngestionError,
    LogIngestionInterface,
    LogParsingError,
    LogSeverity,
    LogSourceType,
    ResilienceConfig,
    SourceAlreadyRunningError,
    SourceConfig,
    SourceConnectionError,
    SourceHealth,
    SourceNotFoundError,
    SourceNotRunningError,
    create_resilience_config,
)
from .manager import LogManager
from .processor import LogProcessor
from .queues import (
    FileQueueConfig,
    FileSystemQueue,
    MemoryQueue,
    QueueConfig,
    QueueStats,
)

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