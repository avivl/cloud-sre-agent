"""Exceptions for the logging system."""

from typing import Any, Dict, Optional


class LoggingError(Exception):
    """Base exception for logging errors."""

    def __init__(
        self,
        message: str,
        logger_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the logging error.

        Args:
            message: Error message
            logger_name: Name of the logger that caused the error
            context: Additional context information
        """
        self.message = message
        self.logger_name = logger_name
        self.context = context or {}
        super().__init__(message)


class ConfigurationError(LoggingError):
    """Raised when logging configuration is invalid."""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the configuration error.

        Args:
            message: Error message
            config_key: Configuration key that caused the error
            config_value: Configuration value that caused the error
            context: Additional context information
        """
        self.config_key = config_key
        self.config_value = config_value
        super().__init__(message, context=context)


class FlowTrackingError(LoggingError):
    """Raised when flow tracking operations fail."""

    def __init__(
        self,
        message: str,
        flow_id: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the flow tracking error.

        Args:
            message: Error message
            flow_id: Flow ID that caused the error
            operation: Operation that caused the error
            context: Additional context information
        """
        self.flow_id = flow_id
        self.operation = operation
        super().__init__(message, context=context)


class MetricsError(LoggingError):
    """Raised when metrics collection or reporting fails."""

    def __init__(
        self,
        message: str,
        metric_name: Optional[str] = None,
        metric_value: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the metrics error.

        Args:
            message: Error message
            metric_name: Name of the metric that caused the error
            metric_value: Value of the metric that caused the error
            context: Additional context information
        """
        self.metric_name = metric_name
        self.metric_value = metric_value
        super().__init__(message, context=context)


class HandlerError(LoggingError):
    """Raised when log handler operations fail."""

    def __init__(
        self,
        message: str,
        handler_name: Optional[str] = None,
        handler_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the handler error.

        Args:
            message: Error message
            handler_name: Name of the handler that caused the error
            handler_type: Type of the handler that caused the error
            context: Additional context information
        """
        self.handler_name = handler_name
        self.handler_type = handler_type
        super().__init__(message, context=context)


class FormatterError(LoggingError):
    """Raised when log formatter operations fail."""

    def __init__(
        self,
        message: str,
        formatter_name: Optional[str] = None,
        formatter_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the formatter error.

        Args:
            message: Error message
            formatter_name: Name of the formatter that caused the error
            formatter_type: Type of the formatter that caused the error
            context: Additional context information
        """
        self.formatter_name = formatter_name
        self.formatter_type = formatter_type
        super().__init__(message, context=context)


class FilterError(LoggingError):
    """Raised when log filter operations fail."""

    def __init__(
        self,
        message: str,
        filter_name: Optional[str] = None,
        filter_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the filter error.

        Args:
            message: Error message
            filter_name: Name of the filter that caused the error
            filter_type: Type of the filter that caused the error
            context: Additional context information
        """
        self.filter_name = filter_name
        self.filter_type = filter_type
        super().__init__(message, context=context)
