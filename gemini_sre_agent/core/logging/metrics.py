# gemini_sre_agent/core/logging/metrics.py
"""
Logging metrics and monitoring.

This module provides metrics collection and monitoring for logging operations.
"""

from collections import deque
from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class LoggingMetrics:
    """Metrics for logging operations."""

    # Counters
    total_logs: int = 0
    debug_logs: int = 0
    info_logs: int = 0
    warning_logs: int = 0
    error_logs: int = 0
    critical_logs: int = 0

    # Performance metrics
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    max_processing_time: float = 0.0
    min_processing_time: float = float("inf")

    # Error metrics
    formatting_errors: int = 0
    handler_errors: int = 0
    configuration_errors: int = 0

    # Memory metrics
    memory_usage: int = 0
    peak_memory_usage: int = 0

    # Handler metrics
    handler_calls: dict[str, int] = field(default_factory=dict)
    handler_errors: dict[str, int] = field(default_factory=dict)

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.total_logs = 0
        self.debug_logs = 0
        self.info_logs = 0
        self.warning_logs = 0
        self.error_logs = 0
        self.critical_logs = 0

        self.total_processing_time = 0.0
        self.average_processing_time = 0.0
        self.max_processing_time = 0.0
        self.min_processing_time = float("inf")

        self.formatting_errors = 0
        self.handler_errors = 0
        self.configuration_errors = 0

        self.memory_usage = 0
        self.peak_memory_usage = 0

        self.handler_calls.clear()
        self.handler_errors.clear()

    def update_processing_time(self, processing_time: float) -> None:
        """Update processing time metrics.
        
        Args:
            processing_time: Time taken to process a log entry.
        """
        self.total_processing_time += processing_time
        self.max_processing_time = max(self.max_processing_time, processing_time)
        self.min_processing_time = min(self.min_processing_time, processing_time)

        if self.total_logs > 0:
            self.average_processing_time = self.total_processing_time / self.total_logs

    def increment_log_count(self, level: str) -> None:
        """Increment log count for a specific level.
        
        Args:
            level: Log level.
        """
        self.total_logs += 1

        level_lower = level.lower()
        if level_lower == "debug":
            self.debug_logs += 1
        elif level_lower == "info":
            self.info_logs += 1
        elif level_lower == "warning":
            self.warning_logs += 1
        elif level_lower == "error":
            self.error_logs += 1
        elif level_lower == "critical":
            self.critical_logs += 1

    def increment_handler_calls(self, handler_name: str) -> None:
        """Increment handler call count.
        
        Args:
            handler_name: Name of the handler.
        """
        self.handler_calls[handler_name] = self.handler_calls.get(handler_name, 0) + 1

    def increment_handler_errors(self, handler_name: str) -> None:
        """Increment handler error count.
        
        Args:
            handler_name: Name of the handler.
        """
        self.handler_errors[handler_name] = self.handler_errors.get(handler_name, 0) + 1
        self.handler_errors += 1

    def update_memory_usage(self, memory_usage: int) -> None:
        """Update memory usage metrics.
        
        Args:
            memory_usage: Current memory usage in bytes.
        """
        self.memory_usage = memory_usage
        self.peak_memory_usage = max(self.peak_memory_usage, memory_usage)

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary.
        
        Returns:
            Dictionary representation of metrics.
        """
        return {
            "total_logs": self.total_logs,
            "debug_logs": self.debug_logs,
            "info_logs": self.info_logs,
            "warning_logs": self.warning_logs,
            "error_logs": self.error_logs,
            "critical_logs": self.critical_logs,
            "total_processing_time": self.total_processing_time,
            "average_processing_time": self.average_processing_time,
            "max_processing_time": self.max_processing_time,
            "min_processing_time": (
                self.min_processing_time 
                if self.min_processing_time != float("inf") 
                else 0.0
            ),
            "formatting_errors": self.formatting_errors,
            "handler_errors": self.handler_errors,
            "configuration_errors": self.configuration_errors,
            "memory_usage": self.memory_usage,
            "peak_memory_usage": self.peak_memory_usage,
            "handler_calls": dict(self.handler_calls),
            "handler_errors": dict(self.handler_errors)
        }


class MetricsCollector:
    """Collects and manages logging metrics."""

    def __init__(self, max_history: int = 1000):
        """Initialize the metrics collector.
        
        Args:
            max_history: Maximum number of historical metrics to keep.
        """
        self.max_history = max_history
        self.current_metrics = LoggingMetrics()
        self.historical_metrics: deque = deque(maxlen=max_history)
        self.start_time = time.time()
        self.last_reset_time = time.time()

    def record_log(self, level: str, processing_time: float) -> None:
        """Record a log entry.
        
        Args:
            level: Log level.
            processing_time: Time taken to process the log entry.
        """
        self.current_metrics.increment_log_count(level)
        self.current_metrics.update_processing_time(processing_time)

    def record_handler_call(self, handler_name: str) -> None:
        """Record a handler call.
        
        Args:
            handler_name: Name of the handler.
        """
        self.current_metrics.increment_handler_calls(handler_name)

    def record_handler_error(self, handler_name: str) -> None:
        """Record a handler error.
        
        Args:
            handler_name: Name of the handler.
        """
        self.current_metrics.increment_handler_errors(handler_name)

    def record_formatting_error(self) -> None:
        """Record a formatting error."""
        self.current_metrics.formatting_errors += 1

    def record_configuration_error(self) -> None:
        """Record a configuration error."""
        self.current_metrics.configuration_errors += 1

    def update_memory_usage(self, memory_usage: int) -> None:
        """Update memory usage.
        
        Args:
            memory_usage: Current memory usage in bytes.
        """
        self.current_metrics.update_memory_usage(memory_usage)

    def get_current_metrics(self) -> LoggingMetrics:
        """Get current metrics.
        
        Returns:
            Current metrics instance.
        """
        return self.current_metrics

    def get_historical_metrics(self) -> list[LoggingMetrics]:
        """Get historical metrics.
        
        Returns:
            List of historical metrics.
        """
        return list(self.historical_metrics)

    def snapshot_metrics(self) -> LoggingMetrics:
        """Take a snapshot of current metrics.
        
        Returns:
            Snapshot of current metrics.
        """
        snapshot = LoggingMetrics()
        snapshot.total_logs = self.current_metrics.total_logs
        snapshot.debug_logs = self.current_metrics.debug_logs
        snapshot.info_logs = self.current_metrics.info_logs
        snapshot.warning_logs = self.current_metrics.warning_logs
        snapshot.error_logs = self.current_metrics.error_logs
        snapshot.critical_logs = self.current_metrics.critical_logs
        snapshot.total_processing_time = self.current_metrics.total_processing_time
        snapshot.average_processing_time = self.current_metrics.average_processing_time
        snapshot.max_processing_time = self.current_metrics.max_processing_time
        snapshot.min_processing_time = self.current_metrics.min_processing_time
        snapshot.formatting_errors = self.current_metrics.formatting_errors
        snapshot.handler_errors = self.current_metrics.handler_errors
        snapshot.configuration_errors = self.current_metrics.configuration_errors
        snapshot.memory_usage = self.current_metrics.memory_usage
        snapshot.peak_memory_usage = self.current_metrics.peak_memory_usage
        snapshot.handler_calls = self.current_metrics.handler_calls.copy()
        snapshot.handler_errors = self.current_metrics.handler_errors.copy()

        return snapshot

    def archive_metrics(self) -> None:
        """Archive current metrics to history."""
        snapshot = self.snapshot_metrics()
        self.historical_metrics.append(snapshot)

    def reset_metrics(self) -> None:
        """Reset current metrics."""
        self.archive_metrics()
        self.current_metrics.reset()
        self.last_reset_time = time.time()

    def get_uptime(self) -> float:
        """Get system uptime in seconds.
        
        Returns:
            Uptime in seconds.
        """
        return time.time() - self.start_time

    def get_time_since_reset(self) -> float:
        """Get time since last reset in seconds.
        
        Returns:
            Time since last reset in seconds.
        """
        return time.time() - self.last_reset_time

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get a summary of all metrics.
        
        Returns:
            Dictionary containing metrics summary.
        """
        current = self.current_metrics.to_dict()
        historical = [m.to_dict() for m in self.historical_metrics]

        return {
            "current": current,
            "historical": historical,
            "uptime": self.get_uptime(),
            "time_since_reset": self.get_time_since_reset(),
            "total_archived_metrics": len(self.historical_metrics)
        }

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics.
        
        Returns:
            Dictionary containing performance statistics.
        """
        if not self.historical_metrics:
            return {
                "average_logs_per_second": 0.0,
                "average_processing_time": self.current_metrics.average_processing_time,
                "peak_processing_time": self.current_metrics.max_processing_time,
                "total_uptime": self.get_uptime()
            }

        # Calculate averages from historical data
        total_logs = sum(m.total_logs for m in self.historical_metrics)
        total_time = sum(m.total_processing_time for m in self.historical_metrics)
        total_entries = sum(1 for m in self.historical_metrics if m.total_logs > 0)

        avg_logs_per_second = total_logs / self.get_uptime() if self.get_uptime() > 0 else 0.0
        avg_processing_time = total_time / total_entries if total_entries > 0 else 0.0

        # Find peak processing time
        peak_processing_time = max(
            m.max_processing_time for m in self.historical_metrics
        ) if self.historical_metrics else 0.0

        return {
            "average_logs_per_second": avg_logs_per_second,
            "average_processing_time": avg_processing_time,
            "peak_processing_time": peak_processing_time,
            "total_uptime": self.get_uptime(),
            "total_logs_processed": total_logs
        }

    def get_error_rates(self) -> dict[str, float]:
        """Get error rates.
        
        Returns:
            Dictionary containing error rates.
        """
        if self.current_metrics.total_logs == 0:
            return {
                "formatting_error_rate": 0.0,
                "handler_error_rate": 0.0,
                "configuration_error_rate": 0.0,
                "overall_error_rate": 0.0
            }

        total_errors = (
            self.current_metrics.formatting_errors +
            self.current_metrics.handler_errors +
            self.current_metrics.configuration_errors
        )

        return {
            "formatting_error_rate": (
                self.current_metrics.formatting_errors / self.current_metrics.total_logs
            ),
            "handler_error_rate": (
                self.current_metrics.handler_errors / self.current_metrics.total_logs
            ),
            "configuration_error_rate": (
                self.current_metrics.configuration_errors / self.current_metrics.total_logs
            ),
            "overall_error_rate": total_errors / self.current_metrics.total_logs
        }


# Global metrics collector instance
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector.
    
    Returns:
        Global metrics collector instance.
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def record_log_metrics(level: str, processing_time: float) -> None:
    """Record log metrics.
    
    Args:
        level: Log level.
        processing_time: Processing time in seconds.
    """
    collector = get_metrics_collector()
    collector.record_log(level, processing_time)


def record_handler_metrics(handler_name: str, success: bool = True) -> None:
    """Record handler metrics.
    
    Args:
        handler_name: Name of the handler.
        success: Whether the handler call was successful.
    """
    collector = get_metrics_collector()
    collector.record_handler_call(handler_name)
    if not success:
        collector.record_handler_error(handler_name)


def record_error_metrics(error_type: str) -> None:
    """Record error metrics.
    
    Args:
        error_type: Type of error ('formatting', 'handler', 'configuration').
    """
    collector = get_metrics_collector()

    if error_type == "formatting":
        collector.record_formatting_error()
    elif error_type == "handler":
        collector.record_handler_error("unknown")
    elif error_type == "configuration":
        collector.record_configuration_error()


def get_current_metrics() -> LoggingMetrics:
    """Get current metrics.
    
    Returns:
        Current metrics instance.
    """
    collector = get_metrics_collector()
    return collector.get_current_metrics()


def get_metrics_summary() -> dict[str, Any]:
    """Get metrics summary.
    
    Returns:
        Dictionary containing metrics summary.
    """
    collector = get_metrics_collector()
    return collector.get_metrics_summary()


def reset_metrics() -> None:
    """Reset all metrics."""
    collector = get_metrics_collector()
    collector.reset_metrics()
