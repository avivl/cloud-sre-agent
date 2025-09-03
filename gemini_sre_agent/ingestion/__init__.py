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
    # Main components
    "LogManager",
    "LogProcessor",
]
