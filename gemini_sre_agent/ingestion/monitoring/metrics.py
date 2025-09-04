"""
Metrics collection and reporting system for the log ingestion system.

Provides comprehensive metrics collection including:
- Counter metrics (logs processed, errors, etc.)
- Gauge metrics (queue sizes, memory usage, etc.)
- Histogram metrics (processing times, latencies, etc.)
- Rate metrics (throughput, error rates, etc.)
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics supported by the system."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    RATE = "rate"


@dataclass
class MetricValue:
    """Represents a metric value with metadata."""

    name: str
    value: Union[int, float]
    metric_type: MetricType
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)
    unit: Optional[str] = None


@dataclass
class HistogramBucket:
    """Represents a histogram bucket for latency/performance metrics."""

    upper_bound: float
    count: int = 0


class MetricsCollector:
    """
    Comprehensive metrics collection system for the log ingestion system.

    Collects and aggregates metrics from all components including:
    - Log processing metrics (throughput, errors, latency)
    - System metrics (memory, CPU, queue sizes)
    - Component-specific metrics (adapter health, resilience stats)
    """

    def __init__(self, retention_period: timedelta = timedelta(hours=24)):
        """
        Initialize the metrics collector.

        Args:
            retention_period: How long to retain metrics data
        """
        self.retention_period = retention_period
        self._metrics: Dict[str, List[MetricValue]] = defaultdict(list)
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._rates: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # Thread safety
        self._lock = threading.RLock()

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        logger.info("MetricsCollector initialized")

    async def start(self) -> None:
        """Start the metrics collector and background tasks."""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_old_metrics())
        logger.info("MetricsCollector started")

    async def stop(self) -> None:
        """Stop the metrics collector and cleanup tasks."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("MetricsCollector stopped")

    def increment_counter(
        self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Increment a counter metric.

        Args:
            name: Metric name
            value: Value to increment by
            labels: Optional labels for the metric
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._counters[key] += value

            metric = MetricValue(
                name=name,
                value=self._counters[key],
                metric_type=MetricType.COUNTER,
                labels=labels or {},
            )
            self._metrics[name].append(metric)

    def set_gauge(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Set a gauge metric value.

        Args:
            name: Metric name
            value: Current value
            labels: Optional labels for the metric
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value

            metric = MetricValue(
                name=name,
                value=value,
                metric_type=MetricType.GAUGE,
                labels=labels or {},
            )
            self._metrics[name].append(metric)

    def record_histogram(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a value in a histogram metric.

        Args:
            name: Metric name
            value: Value to record
            labels: Optional labels for the metric
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._histograms[key].append(value)

            metric = MetricValue(
                name=name,
                value=value,
                metric_type=MetricType.HISTOGRAM,
                labels=labels or {},
            )
            self._metrics[name].append(metric)

    def record_rate(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a value for rate calculation.

        Args:
            name: Metric name
            value: Value to record
            labels: Optional labels for the metric
        """
        with self._lock:
            key = self._make_key(name, labels)
            self._rates[key].append((time.time(), value))

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value."""
        with self._lock:
            key = self._make_key(name, labels)
            return self._counters.get(key, 0.0)

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current gauge value."""
        with self._lock:
            key = self._make_key(name, labels)
            return self._gauges.get(key, 0.0)

    def get_histogram_stats(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """
        Get histogram statistics (count, sum, min, max, avg, p50, p95, p99).

        Args:
            name: Metric name
            labels: Optional labels for the metric

        Returns:
            Dictionary with histogram statistics
        """
        with self._lock:
            key = self._make_key(name, labels)
            values = self._histograms.get(key, [])

            if not values:
                return {
                    "count": 0,
                    "sum": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "avg": 0.0,
                    "p50": 0.0,
                    "p95": 0.0,
                    "p99": 0.0,
                }

            sorted_values = sorted(values)
            count = len(values)
            total = sum(values)

            return {
                "count": count,
                "sum": total,
                "min": min(values),
                "max": max(values),
                "avg": total / count,
                "p50": sorted_values[int(count * 0.5)],
                "p95": sorted_values[int(count * 0.95)],
                "p99": sorted_values[int(count * 0.99)],
            }

    def get_rate(
        self,
        name: str,
        window_seconds: int = 60,
        labels: Optional[Dict[str, str]] = None,
    ) -> float:
        """
        Calculate rate over a time window.

        Args:
            name: Metric name
            window_seconds: Time window in seconds
            labels: Optional labels for the metric

        Returns:
            Rate (events per second)
        """
        with self._lock:
            key = self._make_key(name, labels)
            now = time.time()
            cutoff = now - window_seconds

            # Filter values within the time window
            recent_values = [(t, v) for t, v in self._rates[key] if t >= cutoff]

            if len(recent_values) < 2:
                return 0.0

            # Calculate rate
            time_span = recent_values[-1][0] - recent_values[0][0]
            if time_span <= 0:
                return 0.0

            total_value = sum(v for _, v in recent_values)
            return total_value / time_span

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive summary of all metrics.

        Returns:
            Dictionary with metrics summary
        """
        with self._lock:
            summary = {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    name: self.get_histogram_stats(name)
                    for name in self._histograms.keys()
                },
                "rates": {name: self.get_rate(name) for name in self._rates.keys()},
                "timestamp": datetime.now().isoformat(),
            }
            return summary

    def get_metrics_for_export(
        self, metric_names: Optional[List[str]] = None
    ) -> List[MetricValue]:
        """
        Get metrics in a format suitable for export to monitoring systems.

        Args:
            metric_names: Optional list of metric names to export

        Returns:
            List of MetricValue objects
        """
        with self._lock:
            if metric_names:
                return [
                    metric
                    for name, metrics in self._metrics.items()
                    if name in metric_names
                    for metric in metrics[-100:]  # Last 100 values per metric
                ]
            else:
                return [
                    metric
                    for metrics in self._metrics.values()
                    for metric in metrics[-100:]  # Last 100 values per metric
                ]

    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create a unique key for a metric with labels."""
        if not labels:
            return name

        label_parts = [f"{k}={v}" for k, v in sorted(labels.items())]
        return f"{name}{{{','.join(label_parts)}}}"

    async def _cleanup_old_metrics(self) -> None:
        """Background task to clean up old metrics."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                cutoff_time = datetime.now() - self.retention_period

                with self._lock:
                    for name in list(self._metrics.keys()):
                        # Keep only recent metrics
                        self._metrics[name] = [
                            metric
                            for metric in self._metrics[name]
                            if metric.timestamp >= cutoff_time
                        ]

                        # Remove empty metric lists
                        if not self._metrics[name]:
                            del self._metrics[name]

                logger.debug("Cleaned up old metrics")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics cleanup: {e}")


# Global metrics collector instance
_global_metrics: Optional[MetricsCollector] = None


def get_global_metrics() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsCollector()
    return _global_metrics


def set_global_metrics(metrics: MetricsCollector) -> None:
    """Set the global metrics collector instance."""
    global _global_metrics
    _global_metrics = metrics


# Convenience functions for common metrics
def record_log_processed(source: str, count: int = 1) -> None:
    """Record that logs were processed from a source."""
    get_global_metrics().increment_counter(
        "logs_processed_total", value=count, labels={"source": source}
    )


def record_log_error(source: str, error_type: str) -> None:
    """Record a log processing error."""
    get_global_metrics().increment_counter(
        "logs_errors_total", labels={"source": source, "error_type": error_type}
    )


def record_processing_time(source: str, duration_seconds: float) -> None:
    """Record log processing time."""
    get_global_metrics().record_histogram(
        "log_processing_duration_seconds",
        value=duration_seconds,
        labels={"source": source},
    )


def record_queue_size(queue_name: str, size: int) -> None:
    """Record current queue size."""
    get_global_metrics().set_gauge(
        "queue_size", value=size, labels={"queue": queue_name}
    )


def record_memory_usage(component: str, usage_mb: float) -> None:
    """Record memory usage for a component."""
    get_global_metrics().set_gauge(
        "memory_usage_mb", value=usage_mb, labels={"component": component}
    )
