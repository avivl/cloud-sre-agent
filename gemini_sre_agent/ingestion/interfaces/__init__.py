# gemini_sre_agent/ingestion/interfaces/__init__.py

"""
Core interfaces for the log ingestion system.
"""

from .core import (
    LogEntry,
    LogIngestionInterface,
    LogSeverity,
    LogSourceType,
    SourceConfig,
    SourceHealth,
)
from .errors import (
    ConfigurationError,
    LogIngestionError,
    LogParsingError,
    SourceAlreadyRunningError,
    SourceConnectionError,
    SourceNotFoundError,
    SourceNotRunningError,
)
from .resilience import (
    BackpressureManager,
    HyxResilientClient,
    ResilienceConfig,
    create_resilience_config,
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
    # Resilience patterns
    "BackpressureManager",
    "HyxResilientClient",
    "create_resilience_config",
    "ResilienceConfig",
]
