# gemini_sre_agent/ingestion/interfaces/errors.py

"""
Error handling classes for log ingestion system.
"""


class LogIngestionError(Exception):
    """Base exception for ingestion errors."""

    pass


class SourceConnectionError(LogIngestionError):
    """Connection to source failed."""

    pass


class LogParsingError(LogIngestionError):
    """Failed to parse log entry."""

    pass


class ConfigurationError(LogIngestionError):
    """Configuration validation or loading error."""

    pass


class SourceNotFoundError(LogIngestionError):
    """Requested log source not found."""

    pass


class SourceAlreadyRunningError(LogIngestionError):
    """Attempt to start an already running source."""

    pass


class SourceNotRunningError(LogIngestionError):
    """Attempt to stop a source that is not running."""

    pass
