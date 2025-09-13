"""Exceptions for the logging system."""

from typing import Any


class LoggingError(Exception):
    """Base exception for logging errors."""

    def __init__(
        self,
        message: str,
        logger_name: str | None = None,
        context: dict[str, Any] | None = None,
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
        config_key: str | None = None,
        config_value: Any | None = None,
        context: dict[str, Any] | None = None,
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
        flow_id: str | None = None,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
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
        metric_name: str | None = None,
        metric_value: Any | None = None,
        context: dict[str, Any] | None = None,
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
        handler_name: str | None = None,
        handler_type: str | None = None,
        context: dict[str, Any] | None = None,
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
        formatter_name: str | None = None,
        formatter_type: str | None = None,
        context: dict[str, Any] | None = None,
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
        filter_name: str | None = None,
        filter_type: str | None = None,
        context: dict[str, Any] | None = None,
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


class AlertingError(LoggingError):
    """Raised when alerting operations fail."""

    def __init__(
        self,
        message: str,
        alert_name: str | None = None,
        alert_type: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        """Initialize the alerting error.

        Args:
            message: Error message
            alert_name: Name of the alert that caused the error
            alert_type: Type of the alert that caused the error
            context: Additional context information
        """
        self.alert_name = alert_name
        self.alert_type = alert_type
        super().__init__(message, context=context)


class PerformanceMonitoringError(LoggingError):
    """Raised when performance monitoring operations fail."""

    def __init__(
        self,
        message: str,
        metric_name: str | None = None,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        """Initialize the performance monitoring error.

        Args:
            message: Error message
            metric_name: Name of the metric that caused the error
            operation: Operation that caused the error
            context: Additional context information
        """
        self.metric_name = metric_name
        self.operation = operation
        super().__init__(message, context=context)
