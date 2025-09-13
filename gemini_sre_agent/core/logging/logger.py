"""Main logger implementation for the logging framework."""

from contextlib import contextmanager
import logging
import time
from typing import Any

from .alerting import AlertRule, AlertSeverity, get_alert_manager
from .config import LoggingConfig
from .context import LoggingContext
from .filters import (
    ContextFilter,
    LevelFilter,
    RateLimitFilter,
    SamplingFilter,
)
from .filters import (
    ContextFilter as TagFilter,
)
from .filters import (
    MessageFilter as RegexFilter,
)
from .flow_tracker import get_flow_tracker
from .handlers import (
    ConsoleHandler,
    DatabaseHandler,
    HTTPHandler,
    QueueHandler,
)
from .handlers import (
    DatabaseHandler as SyslogHandler,
)
from .handlers import (
    RotatingStructuredFileHandler as RotatingFileHandler,
)
from .handlers import (
    StructuredFileHandler as FileHandler,
)
from .performance_monitor import get_performance_monitor


class Logger:
    """Main logger class that integrates all logging components."""

    def __init__(self, config: LoggingConfig | None = None):
        """Initialize the logger.

        Args:
            config: Optional logging configuration
        """
        self._config = config or LoggingConfig()
        self._logger = logging.getLogger(self._config.name)
        self._logger.setLevel(self._config.level)

        # Clear existing handlers
        self._logger.handlers.clear()

        # Initialize components
        self._context = LoggingContext(self._config.context)
        self._flow_tracker = get_flow_tracker()
        self._performance_monitor = get_performance_monitor()
        self._alert_manager = get_alert_manager()

        # Setup handlers
        self._setup_handlers()

        # Setup filters
        self._setup_filters()

        # Setup alerting
        self._setup_alerting()

    def _setup_handlers(self) -> None:
        """Setup log handlers based on configuration."""
        for handler_config in self._config.handlers:
            handler = self._create_handler(handler_config)
            if handler:
                self._logger.addHandler(handler)

    def _create_handler(self, config: dict[str, Any]) -> logging.Handler | None:
        """Create a handler from configuration.

        Args:
            config: Handler configuration

        Returns:
            Created handler or None if creation fails
        """
        try:
            handler_type = config.get("type")

            if handler_type == "console":
                return ConsoleHandler(config)
            elif handler_type == "file":
                return FileHandler(config)
            elif handler_type == "rotating_file":
                return RotatingFileHandler(config)
            elif handler_type == "syslog":
                return SyslogHandler(config)
            elif handler_type == "http":
                return HTTPHandler(config)
            elif handler_type == "database":
                return DatabaseHandler(config)
            elif handler_type == "queue":
                return QueueHandler(config)
            else:
                self._logger.warning(f"Unknown handler type: {handler_type}")
                return None

        except Exception as e:
            self._logger.error(f"Failed to create handler: {e}")
            return None

    def _setup_filters(self) -> None:
        """Setup log filters based on configuration."""
        for filter_config in self._config.filters:
            filter_obj = self._create_filter(filter_config)
            if filter_obj:
                self._logger.addFilter(filter_obj)

    def _create_filter(self, config: dict[str, Any]) -> logging.Filter | None:
        """Create a filter from configuration.

        Args:
            config: Filter configuration

        Returns:
            Created filter or None if creation fails
        """
        try:
            filter_type = config.get("type")

            if filter_type == "level":
                return LevelFilter(config)
            elif filter_type == "regex":
                return RegexFilter(config)
            elif filter_type == "tag":
                return TagFilter(config)
            elif filter_type == "context":
                return ContextFilter(config)
            elif filter_type == "sampling":
                return SamplingFilter(config)
            elif filter_type == "rate_limit":
                return RateLimitFilter(config)
            else:
                self._logger.warning(f"Unknown filter type: {filter_type}")
                return None

        except Exception as e:
            self._logger.error(f"Failed to create filter: {e}")
            return None

    def _setup_alerting(self) -> None:
        """Setup alerting rules."""
        for alert_config in self._config.alerting:
            rule = AlertRule(
                name=alert_config["name"],
                condition=eval(
                    alert_config["condition"]
                ),  # Note: Use safer method in production
                severity=AlertSeverity(alert_config["severity"]),
                message_template=alert_config["message_template"],
                cooldown_seconds=alert_config.get("cooldown_seconds", 300),
                enabled=alert_config.get("enabled", True),
                tags=alert_config.get("tags", {}),
                metadata=alert_config.get("metadata", {}),
            )
            self._alert_manager.add_rule(rule)

    def log(
        self,
        level: int,
        message: str,
        extra: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        flow_id: str | None = None,
    ) -> None:
        """Log a message at the specified level.

        Args:
            level: Log level
            message: Log message
            extra: Optional extra data
            tags: Optional tags
            flow_id: Optional flow ID
        """
        try:
            # Get current flow ID if not provided
            if flow_id is None:
                flow_id = self._flow_tracker.get_current_flow_id()

            # Prepare extra data
            log_extra = {
                "flow_id": flow_id,
                "tags": tags or [],
                "timestamp": time.time(),
                "context": self._context.get_context(),
            }

            if extra:
                log_extra.update(extra)

            # Record performance metric
            self._performance_monitor.record_counter(
                "log_messages", tags={"level": logging.getLevelName(level).lower()}
            )

            # Log the message
            self._logger.log(level, message, extra=log_extra)

            # Check for alerts
            self._check_alerts(level, message, log_extra)

        except Exception as e:
            # Fallback to basic logging
            self._logger.error(f"Failed to log message: {e}")
            self._logger.log(level, message)

    def debug(
        self,
        message: str,
        extra: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        flow_id: str | None = None,
    ) -> None:
        """Log a debug message.

        Args:
            message: Log message
            extra: Optional extra data
            tags: Optional tags
            flow_id: Optional flow ID
        """
        self.log(logging.DEBUG, message, extra, tags, flow_id)

    def info(
        self,
        message: str,
        extra: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        flow_id: str | None = None,
    ) -> None:
        """Log an info message.

        Args:
            message: Log message
            extra: Optional extra data
            tags: Optional tags
            flow_id: Optional flow ID
        """
        self.log(logging.INFO, message, extra, tags, flow_id)

    def warning(
        self,
        message: str,
        extra: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        flow_id: str | None = None,
    ) -> None:
        """Log a warning message.

        Args:
            message: Log message
            extra: Optional extra data
            tags: Optional tags
            flow_id: Optional flow ID
        """
        self.log(logging.WARNING, message, extra, tags, flow_id)

    def error(
        self,
        message: str,
        extra: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        flow_id: str | None = None,
    ) -> None:
        """Log an error message.

        Args:
            message: Log message
            extra: Optional extra data
            tags: Optional tags
            flow_id: Optional flow ID
        """
        self.log(logging.ERROR, message, extra, tags, flow_id)

    def critical(
        self,
        message: str,
        extra: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        flow_id: str | None = None,
    ) -> None:
        """Log a critical message.

        Args:
            message: Log message
            extra: Optional extra data
            tags: Optional tags
            flow_id: Optional flow ID
        """
        self.log(logging.CRITICAL, message, extra, tags, flow_id)

    def exception(
        self,
        message: str,
        exc_info: bool = True,
        extra: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        flow_id: str | None = None,
    ) -> None:
        """Log an exception.

        Args:
            message: Log message
            exc_info: Include exception info
            extra: Optional extra data
            tags: Optional tags
            flow_id: Optional flow ID
        """
        log_extra = extra or {}
        if exc_info:
            log_extra["exc_info"] = True

        self.log(logging.ERROR, message, log_extra, tags, flow_id)

    def _check_alerts(self, level: int, message: str, extra: dict[str, Any]) -> None:
        """Check for alert conditions.

        Args:
            level: Log level
            message: Log message
            extra: Extra log data
        """
        try:
            alert_data = {
                "level": level,
                "level_name": logging.getLevelName(level),
                "message": message,
                "extra": extra,
            }

            self._alert_manager.evaluate_rules(alert_data)
        except Exception:
            pass  # Ignore alert evaluation errors

    def add_context(self, key: str, value: Any) -> None:
        """Add context data.

        Args:
            key: Context key
            value: Context value
        """
        self._context.add_context(key, value)

    def remove_context(self, key: str) -> None:
        """Remove context data.

        Args:
            key: Context key to remove
        """
        self._context.remove_context(key)

    def clear_context(self) -> None:
        """Clear all context data."""
        self._context.clear_context()

    def get_context(self) -> dict[str, Any]:
        """Get current context data.

        Returns:
            Current context data
        """
        return self._context.get_context()

    def start_flow(
        self,
        operation: str,
        flow_id: str | None = None,
        parent_flow_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Start a new flow.

        Args:
            operation: Name of the operation
            flow_id: Optional custom flow ID
            parent_flow_id: Optional parent flow ID
            metadata: Optional metadata for the flow
            tags: Optional tags for the flow

        Returns:
            Flow ID
        """
        flow_context = self._flow_tracker.start_flow(
            operation=operation,
            flow_id=flow_id,
            parent_flow_id=parent_flow_id,
            metadata=metadata,
            tags=tags,
        )
        return flow_context.flow_id

    def end_flow(
        self,
        flow_id: str,
        status: str = "completed",
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End a flow.

        Args:
            flow_id: Flow ID to end
            status: Status of the flow completion
            error: Optional error message
            metadata: Optional additional metadata
        """
        self._flow_tracker.end_flow(flow_id, status, error, metadata)

    @contextmanager
    def flow(
        self,
        operation: str,
        flow_id: str | None = None,
        parent_flow_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ):
        """Context manager for flow tracking.

        Args:
            operation: Name of the operation
            flow_id: Optional custom flow ID
            parent_flow_id: Optional parent flow ID
            metadata: Optional metadata for the flow
            tags: Optional tags for the flow

        Yields:
            Flow ID
        """
        flow_id = self.start_flow(operation, flow_id, parent_flow_id, metadata, tags)
        try:
            yield flow_id
        except Exception as e:
            self.end_flow(flow_id, "error", str(e))
            raise
        else:
            self.end_flow(flow_id, "completed")

    def record_metric(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a performance metric.

        Args:
            name: Name of the metric
            value: Metric value
            tags: Optional tags for the metric
            metadata: Optional metadata for the metric
        """
        self._performance_monitor.record_metric(name, value, tags, metadata)

    @contextmanager
    def timing(
        self,
        name: str,
        tags: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Context manager for timing operations.

        Args:
            name: Name of the timing metric
            tags: Optional tags for the metric
            metadata: Optional metadata for the metric

        Yields:
            None
        """
        with self._performance_monitor.timing(name, tags, metadata):
            yield

    def get_performance_stats(
        self,
        name: str,
        tags: dict[str, str] | None = None,
        window_seconds: float | None = None,
    ) -> dict[str, Any] | None:
        """Get performance statistics for a metric.

        Args:
            name: Name of the metric
            tags: Optional tags to filter by
            window_seconds: Optional time window in seconds

        Returns:
            Performance statistics or None if no data
        """
        stats = self._performance_monitor.get_metric_stats(name, tags, window_seconds)
        return stats.to_dict() if stats else None

    def get_alerts(
        self,
        status: str | None = None,
        severity: str | None = None,
        rule_name: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get alerts with optional filtering.

        Args:
            status: Optional status filter
            severity: Optional severity filter
            rule_name: Optional rule name filter
            limit: Optional limit on number of alerts

        Returns:
            List of alert dictionaries
        """
        from .alerting import AlertSeverity, AlertStatus

        status_enum = AlertStatus(status) if status else None
        severity_enum = AlertSeverity(severity) if severity else None

        alerts = self._alert_manager.get_alerts(
            status=status_enum, severity=severity_enum, rule_name=rule_name, limit=limit
        )

        return [alert.to_dict() for alert in alerts]

    def get_alert_stats(self) -> dict[str, Any]:
        """Get alert statistics.

        Returns:
            Dictionary of alert statistics
        """
        return self._alert_manager.get_alert_stats()

    def get_flow_context(self, flow_id: str) -> dict[str, Any] | None:
        """Get flow context by ID.

        Args:
            flow_id: Flow ID to look up

        Returns:
            Flow context or None if not found
        """
        flow_context = self._flow_tracker.get_flow_context(flow_id)
        return flow_context.to_dict() if flow_context else None

    def get_active_flows(self) -> list[dict[str, Any]]:
        """Get all active flows.

        Returns:
            List of active flow contexts
        """
        flows = self._flow_tracker.get_active_flows()
        return [flow.to_dict() for flow in flows]

    def get_flow_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get flow history.

        Args:
            limit: Optional limit on number of flows to return

        Returns:
            List of flow contexts from history
        """
        flows = self._flow_tracker.get_flow_history(limit)
        return [flow.to_dict() for flow in flows]

    def get_flow_tree(self, root_flow_id: str) -> dict[str, Any]:
        """Get flow tree starting from a root flow.

        Args:
            root_flow_id: Root flow ID

        Returns:
            Dictionary representing the flow tree
        """
        return self._flow_tracker.get_flow_tree(root_flow_id)

    def export_metrics(
        self, format_type: str = "dict", window_seconds: float | None = None
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Export performance metrics.

        Args:
            format_type: Export format ("dict", "list", "stats")
            window_seconds: Optional time window in seconds

        Returns:
            Exported metrics data
        """
        return self._performance_monitor.export_metrics(format_type, window_seconds)

    def configure(self, config: LoggingConfig) -> None:
        """Reconfigure the logger.

        Args:
            config: New logging configuration
        """
        self._config = config
        self._logger.setLevel(config.level)

        # Clear existing handlers and filters
        self._logger.handlers.clear()

        # Re-setup components
        self._setup_handlers()
        self._setup_filters()
        self._setup_alerting()

    def shutdown(self) -> None:
        """Shutdown the logger and cleanup resources."""
        # Close all handlers
        for handler in self._logger.handlers:
            handler.close()

        # Clear handlers
        self._logger.handlers.clear()

        # Clear context
        self._context.clear_context()

        # Clear flow tracker
        self._flow_tracker.clear_active_flows()
        self._flow_tracker.clear_history()

        # Clear performance monitor
        self._performance_monitor.clear_metrics()

        # Clear alerts
        self._alert_manager.clear_all_alerts()


# Global logger instance
_logger: Logger | None = None


def get_logger(config: LoggingConfig | None = None) -> Logger:
    """Get the global logger instance.

    Args:
        config: Optional logging configuration

    Returns:
        Global logger instance
    """
    global _logger
    if _logger is None or config is not None:
        _logger = Logger(config)
    return _logger


def set_logger(logger: Logger) -> None:
    """Set the global logger instance.

    Args:
        logger: Logger instance to set
    """
    global _logger
    _logger = logger
