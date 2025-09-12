"""Performance monitoring system for the logging framework."""

import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from .exceptions import PerformanceMonitoringError


@dataclass
class PerformanceMetric:
    """A performance metric measurement."""

    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary.

        Returns:
            Dictionary representation of the metric
        """
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class PerformanceStats:
    """Performance statistics for a metric."""

    name: str
    count: int
    min_value: float
    max_value: float
    sum_value: float
    avg_value: float
    p50_value: float
    p95_value: float
    p99_value: float
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary.

        Returns:
            Dictionary representation of the stats
        """
        return {
            "name": self.name,
            "count": self.count,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "sum_value": self.sum_value,
            "avg_value": self.avg_value,
            "p50_value": self.p50_value,
            "p95_value": self.p95_value,
            "p99_value": self.p99_value,
            "tags": self.tags,
        }


class PerformanceMonitor:
    """Monitors and tracks performance metrics."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the performance monitor.

        Args:
            config: Optional configuration for performance monitoring
        """
        self._config = config or {}
        self._metrics: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self._config.get("max_metrics_per_name", 1000))
        )
        self._lock = threading.RLock()
        self._enabled = self._config.get("enabled", True)
        self._sampling_rate = self._config.get("sampling_rate", 1.0)
        self._aggregation_window = self._config.get(
            "aggregation_window", 60.0
        )  # seconds
        self._last_aggregation = time.time()

    def record_metric(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a performance metric.

        Args:
            name: Name of the metric
            value: Metric value
            tags: Optional tags for the metric
            metadata: Optional metadata for the metric

        Raises:
            PerformanceMonitoringError: If metric recording fails
        """
        if not self._enabled:
            return

        try:
            # Apply sampling rate
            if self._sampling_rate < 1.0 and hash(name) % 1000 >= int(
                self._sampling_rate * 1000
            ):
                return

            metric = PerformanceMetric(
                name=name,
                value=value,
                timestamp=time.time(),
                tags=tags or {},
                metadata=metadata or {},
            )

            with self._lock:
                self._metrics[name].append(metric)

        except Exception as e:
            raise PerformanceMonitoringError(
                f"Failed to record metric: {str(e)}",
                metric_name=name,
                metric_value=value,
            ) from e

    def record_timing(
        self,
        name: str,
        duration: float,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a timing metric.

        Args:
            name: Name of the timing metric
            duration: Duration in seconds
            tags: Optional tags for the metric
            metadata: Optional metadata for the metric
        """
        self.record_metric(name, duration, tags, metadata)

    def record_counter(
        self,
        name: str,
        count: float = 1.0,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a counter metric.

        Args:
            name: Name of the counter metric
            count: Count value (default 1.0)
            tags: Optional tags for the metric
            metadata: Optional metadata for the metric
        """
        self.record_metric(name, count, tags, metadata)

    def record_gauge(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a gauge metric.

        Args:
            name: Name of the gauge metric
            value: Gauge value
            tags: Optional tags for the metric
            metadata: Optional metadata for the metric
        """
        self.record_metric(name, value, tags, metadata)

    def get_metric_stats(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None,
        window_seconds: Optional[float] = None,
    ) -> Optional[PerformanceStats]:
        """Get performance statistics for a metric.

        Args:
            name: Name of the metric
            tags: Optional tags to filter by
            window_seconds: Optional time window in seconds

        Returns:
            Performance statistics or None if no data
        """
        try:
            with self._lock:
                if name not in self._metrics:
                    return None

                metrics = list(self._metrics[name])

                # Filter by tags if provided
                if tags:
                    metrics = [
                        m
                        for m in metrics
                        if all(m.tags.get(k) == v for k, v in tags.items())
                    ]

                # Filter by time window if provided
                if window_seconds:
                    cutoff_time = time.time() - window_seconds
                    metrics = [m for m in metrics if m.timestamp >= cutoff_time]

                if not metrics:
                    return None

                # Calculate statistics
                values = [m.value for m in metrics]
                values.sort()

                count = len(values)
                min_value = values[0]
                max_value = values[-1]
                sum_value = sum(values)
                avg_value = sum_value / count

                # Calculate percentiles
                p50_idx = int(count * 0.5)
                p95_idx = int(count * 0.95)
                p99_idx = int(count * 0.99)

                p50_value = values[p50_idx] if p50_idx < count else values[-1]
                p95_value = values[p95_idx] if p95_idx < count else values[-1]
                p99_value = values[p99_idx] if p99_idx < count else values[-1]

                return PerformanceStats(
                    name=name,
                    count=count,
                    min_value=min_value,
                    max_value=max_value,
                    sum_value=sum_value,
                    avg_value=avg_value,
                    p50_value=p50_value,
                    p95_value=p95_value,
                    p99_value=p99_value,
                    tags=tags or {},
                )

        except Exception as e:
            raise PerformanceMonitoringError(
                f"Failed to get metric stats: {str(e)}", metric_name=name
            ) from e

    def get_all_metric_names(self) -> List[str]:
        """Get all metric names.

        Returns:
            List of metric names
        """
        with self._lock:
            return list(self._metrics.keys())

    def get_metrics_by_name(
        self, name: str, limit: Optional[int] = None
    ) -> List[PerformanceMetric]:
        """Get metrics by name.

        Args:
            name: Name of the metric
            limit: Optional limit on number of metrics

        Returns:
            List of performance metrics
        """
        with self._lock:
            if name not in self._metrics:
                return []

            metrics = list(self._metrics[name])
            if limit:
                metrics = metrics[-limit:]

            return metrics.copy()

    def get_metrics_by_tags(
        self, tags: Dict[str, str], limit: Optional[int] = None
    ) -> List[PerformanceMetric]:
        """Get metrics by tags.

        Args:
            tags: Tags to filter by
            limit: Optional limit on number of metrics

        Returns:
            List of performance metrics matching the tags
        """
        matching_metrics = []

        with self._lock:
            for _metric_name, metrics in self._metrics.items():
                for metric in metrics:
                    if all(metric.tags.get(k) == v for k, v in tags.items()):
                        matching_metrics.append(metric)

                        if limit and len(matching_metrics) >= limit:
                            break

                if limit and len(matching_metrics) >= limit:
                    break

        return matching_metrics

    def get_aggregated_stats(
        self, window_seconds: Optional[float] = None
    ) -> Dict[str, PerformanceStats]:
        """Get aggregated statistics for all metrics.

        Args:
            window_seconds: Optional time window in seconds

        Returns:
            Dictionary of metric names to performance statistics
        """
        stats = {}

        for metric_name in self.get_all_metric_names():
            stat = self.get_metric_stats(metric_name, window_seconds=window_seconds)
            if stat:
                stats[metric_name] = stat

        return stats

    def clear_metrics(self, name: Optional[str] = None) -> None:
        """Clear metrics.

        Args:
            name: Optional specific metric name to clear
        """
        with self._lock:
            if name:
                if name in self._metrics:
                    self._metrics[name].clear()
            else:
                self._metrics.clear()

    def enable(self) -> None:
        """Enable performance monitoring."""
        self._enabled = True

    def disable(self) -> None:
        """Disable performance monitoring."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if performance monitoring is enabled.

        Returns:
            True if enabled, False otherwise
        """
        return self._enabled

    def set_sampling_rate(self, rate: float) -> None:
        """Set the sampling rate.

        Args:
            rate: Sampling rate between 0.0 and 1.0
        """
        if not 0.0 <= rate <= 1.0:
            raise ValueError("Sampling rate must be between 0.0 and 1.0")

        self._sampling_rate = rate

    def get_sampling_rate(self) -> float:
        """Get the current sampling rate.

        Returns:
            Current sampling rate
        """
        return self._sampling_rate

    @contextmanager
    def timing(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Context manager for timing operations.

        Args:
            name: Name of the timing metric
            tags: Optional tags for the metric
            metadata: Optional metadata for the metric

        Yields:
            None
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_timing(name, duration, tags, metadata)

    def export_metrics(
        self, format_type: str = "dict", window_seconds: Optional[float] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Export metrics in various formats.

        Args:
            format_type: Export format ("dict", "list", "stats")
            window_seconds: Optional time window in seconds

        Returns:
            Exported metrics data
        """
        if format_type == "stats":
            return {
                name: stats.to_dict()
                for name, stats in self.get_aggregated_stats(window_seconds).items()
            }
        elif format_type == "list":
            all_metrics = []
            for metric_name in self.get_all_metric_names():
                metrics = self.get_metrics_by_name(metric_name)
                if window_seconds:
                    cutoff_time = time.time() - window_seconds
                    metrics = [m for m in metrics if m.timestamp >= cutoff_time]
                all_metrics.extend([m.to_dict() for m in metrics])
            return all_metrics
        else:  # dict
            result = {}
            for metric_name in self.get_all_metric_names():
                metrics = self.get_metrics_by_name(metric_name)
                if window_seconds:
                    cutoff_time = time.time() - window_seconds
                    metrics = [m for m in metrics if m.timestamp >= cutoff_time]
                result[metric_name] = [m.to_dict() for m in metrics]
            return result


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance.

    Returns:
        Global performance monitor instance
    """
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def set_performance_monitor(monitor: PerformanceMonitor) -> None:
    """Set the global performance monitor instance.

    Args:
        monitor: Performance monitor instance to set
    """
    global _performance_monitor
    _performance_monitor = monitor
