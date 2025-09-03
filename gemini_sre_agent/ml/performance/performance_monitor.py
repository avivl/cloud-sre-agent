# gemini_sre_agent/ml/performance/performance_monitor.py

"""
Performance monitoring system for ML module operations.

This module provides comprehensive performance tracking, metrics collection,
and performance analysis for all ML operations including code generation,
validation, and caching.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PerformanceMetric:
    """Represents a single performance metric."""

    operation: str
    duration_ms: float
    timestamp: float
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class PerformanceSummary:
    """Summary of performance metrics for an operation."""

    operation: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    average_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    success_rate: float
    last_24h_operations: int
    last_24h_success_rate: float


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system.

    Features:
    - Real-time metric collection
    - Performance trend analysis
    - Alerting for performance degradation
    - Integration with caching and validation systems
    """

    def __init__(
        self,
        max_metrics_per_operation: int = 1000,
        alert_threshold_ms: float = 5000.0,
        alert_success_rate_threshold: float = 0.8,
    ):
        """Initialize the performance monitor."""
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.max_metrics_per_operation = max_metrics_per_operation
        self.alert_threshold_ms = alert_threshold_ms
        self.alert_success_rate_threshold = alert_success_rate_threshold

        # Metric storage
        self.metrics: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_metrics_per_operation)
        )
        self.operation_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Performance alerts
        self.alerts: List[Dict[str, Any]] = []
        self.alert_callbacks: List[Any] = []

        # Start monitoring tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._start_monitoring()

    def _start_monitoring(self):
        """Start background monitoring tasks."""
        if self._monitoring_task is None or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._analyze_performance()
                await self._check_alerts()
                await self._cleanup_old_metrics()
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")

    async def record_metric(
        self,
        operation: str,
        duration_ms: float,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ):
        """
        Record a performance metric.

        Args:
            operation: Name of the operation
            duration_ms: Duration in milliseconds
            success: Whether the operation succeeded
            metadata: Additional metadata about the operation
            error_message: Error message if operation failed
        """
        metric = PerformanceMetric(
            operation=operation,
            duration_ms=duration_ms,
            timestamp=time.time(),
            success=success,
            metadata=metadata or {},
            error_message=error_message,
        )

        self.metrics[operation].append(metric)

        # Update operation statistics
        await self._update_operation_stats(operation)

        # Check for immediate alerts
        if duration_ms > self.alert_threshold_ms:
            await self._trigger_alert(
                "performance_degradation",
                f"Operation {operation} took {duration_ms:.2f}ms (threshold: {self.alert_threshold_ms}ms)",
                {
                    "operation": operation,
                    "duration_ms": duration_ms,
                    "threshold_ms": self.alert_threshold_ms,
                },
            )

    async def record_operation(
        self, operation: str, metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager for recording operation performance.

        Usage:
            async with monitor.record_operation("code_generation", {"model": "gemini-pro"}):
                # ... operation code ...
        """
        return OperationRecorder(self, operation, metadata)

    async def get_performance_summary(
        self, operation: str
    ) -> Optional[PerformanceSummary]:
        """
        Get performance summary for a specific operation.

        Args:
            operation: Name of the operation

        Returns:
            Performance summary or None if no metrics available
        """
        if operation not in self.metrics or not self.metrics[operation]:
            return None

        metrics = list(self.metrics[operation])
        if not metrics:
            return None

        # Calculate statistics
        durations = [m.duration_ms for m in metrics]
        successful = [m for m in metrics if m.success]
        failed = [m for m in metrics if not m.success]

        # Calculate percentiles
        sorted_durations = sorted(durations)
        p95_index = int(len(sorted_durations) * 0.95)
        p99_index = int(len(sorted_durations) * 0.99)

        # Last 24 hours
        cutoff_time = time.time() - 86400  # 24 hours
        last_24h = [m for m in metrics if m.timestamp > cutoff_time]
        last_24h_successful = [m for m in last_24h if m.success]

        return PerformanceSummary(
            operation=operation,
            total_operations=len(metrics),
            successful_operations=len(successful),
            failed_operations=len(failed),
            average_duration_ms=sum(durations) / len(durations),
            min_duration_ms=min(durations),
            max_duration_ms=max(durations),
            p95_duration_ms=(
                sorted_durations[p95_index] if p95_index < len(sorted_durations) else 0
            ),
            p99_duration_ms=(
                sorted_durations[p99_index] if p99_index < len(sorted_durations) else 0
            ),
            success_rate=len(successful) / len(metrics) if metrics else 0,
            last_24h_operations=len(last_24h),
            last_24h_success_rate=(
                len(last_24h_successful) / len(last_24h) if last_24h else 0
            ),
        )

    async def get_all_performance_summaries(self) -> Dict[str, PerformanceSummary]:
        """Get performance summaries for all operations."""
        summaries = {}
        for operation in self.metrics.keys():
            summary = await self.get_performance_summary(operation)
            if summary:
                summaries[operation] = summary
        return summaries

    async def get_performance_trends(
        self, operation: str, hours: int = 24
    ) -> Dict[str, List[float]]:
        """
        Get performance trends over time.

        Args:
            operation: Name of the operation
            hours: Number of hours to analyze

        Returns:
            Dictionary with trend data
        """
        if operation not in self.metrics:
            return {}

        cutoff_time = time.time() - (hours * 3600)
        recent_metrics = [
            m for m in self.metrics[operation] if m.timestamp > cutoff_time
        ]

        if not recent_metrics:
            return {}

        # Group by hour
        hourly_data = defaultdict(list)
        for metric in recent_metrics:
            hour = int(metric.timestamp // 3600) * 3600
            hourly_data[hour].append(metric.duration_ms)

        # Calculate hourly averages
        hours_list = sorted(hourly_data.keys())
        avg_durations = [
            sum(hourly_data[hour]) / len(hourly_data[hour]) for hour in hours_list
        ]
        success_rates = [
            sum(
                1
                for m in recent_metrics
                if m.timestamp >= hour and m.timestamp < hour + 3600 and m.success
            )
            / sum(
                1
                for m in recent_metrics
                if m.timestamp >= hour and m.timestamp < hour + 3600
            )
            for hour in hours_list
        ]

        return {
            "timestamps": hours_list,
            "avg_durations": avg_durations,
            "success_rates": success_rates,
            "operation_count": [len(hourly_data[hour]) for hour in hours_list],
        }

    async def add_alert_callback(self, callback: Any):
        """Add a callback function for performance alerts."""
        self.alert_callbacks.append(callback)

    async def _trigger_alert(self, alert_type: str, message: str, data: Dict[str, Any]):
        """Trigger a performance alert."""
        alert = {
            "type": alert_type,
            "message": message,
            "timestamp": time.time(),
            "data": data,
        }

        self.alerts.append(alert)
        self.logger.warning(f"[PERFORMANCE-ALERT] {message}")

        # Call alert callbacks
        for callback in self.alert_callbacks:
            try:
                if callable(callback):
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert)
                    else:
                        callback(alert)
            except Exception as e:
                self.logger.error(f"Alert callback error: {e}")

    async def _update_operation_stats(self, operation: str):
        """Update statistics for an operation."""
        if operation not in self.metrics:
            return

        metrics = list(self.metrics[operation])
        if not metrics:
            return

        # Calculate basic stats
        durations = [m.duration_ms for m in metrics]
        successful = [m for m in metrics if m.success]

        self.operation_stats[operation] = {
            "total_count": len(metrics),
            "success_count": len(successful),
            "failure_count": len(metrics) - len(successful),
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "last_updated": time.time(),
        }

    async def _analyze_performance(self):
        """Analyze overall performance and detect issues."""
        for operation, metrics in self.metrics.items():
            if not metrics:
                continue

            # Check success rate
            recent_metrics = list(metrics)[-100:]  # Last 100 metrics
            success_rate = sum(1 for m in recent_metrics if m.success) / len(
                recent_metrics
            )

            if success_rate < self.alert_success_rate_threshold:
                await self._trigger_alert(
                    "low_success_rate",
                    f"Operation {operation} has low success rate: {success_rate:.2%}",
                    {
                        "operation": operation,
                        "success_rate": success_rate,
                        "threshold": self.alert_success_rate_threshold,
                    },
                )

    async def _check_alerts(self):
        """Check for ongoing performance issues."""
        # This could include more sophisticated alert checking
        # For now, just log current status
        pass

    async def _cleanup_old_metrics(self):
        """Clean up old metrics to prevent memory issues."""
        # Metrics are automatically limited by deque maxlen
        pass

    def get_monitor_stats(self) -> Dict[str, Any]:
        """Get overall monitoring statistics."""
        total_metrics = sum(len(metrics) for metrics in self.metrics.values())

        return {
            "total_operations_monitored": len(self.metrics),
            "total_metrics_collected": total_metrics,
            "total_alerts_triggered": len(self.alerts),
            "alert_callbacks_registered": len(self.alert_callbacks),
            "max_metrics_per_operation": self.max_metrics_per_operation,
            "alert_threshold_ms": self.alert_threshold_ms,
            "alert_success_rate_threshold": self.alert_success_rate_threshold,
        }


class OperationRecorder:
    """Context manager for recording operation performance."""

    def __init__(
        self,
        monitor: PerformanceMonitor,
        operation: str,
        metadata: Optional[Dict[str, Any]],
    ):
        self.monitor = monitor
        self.operation = operation
        self.metadata = metadata or {}
        self.start_time = None

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is None:
            return

        duration_ms = (time.time() - self.start_time) * 1000
        success = exc_type is None
        error_message = str(exc_val) if exc_val else None

        await self.monitor.record_metric(
            operation=self.operation,
            duration_ms=duration_ms,
            success=success,
            metadata=self.metadata,
            error_message=error_message,
        )


# Global performance monitor instance
_global_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


async def record_performance(
    operation: str,
    duration_ms: float,
    success: bool,
    metadata: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
):
    """Record performance metric using global monitor."""
    monitor = get_performance_monitor()
    await monitor.record_metric(
        operation, duration_ms, success, metadata, error_message
    )


async def get_performance_summary(operation: str) -> Optional[PerformanceSummary]:
    """Get performance summary using global monitor."""
    monitor = get_performance_monitor()
    return await monitor.get_performance_summary(operation)
