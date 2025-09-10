# gemini_sre_agent/source_control/metrics.py

"""
Metrics collection and analysis for source control operations.

This module provides comprehensive metrics collection, analysis, and reporting
capabilities for monitoring source control provider performance and usage.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from .models import OperationResult, ProviderHealth, RemediationResult


class MetricType(Enum):
    """Types of metrics that can be collected."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"


@dataclass
class MetricPoint:
    """A single metric measurement point."""

    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    unit: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """A series of metric points over time."""

    name: str
    metric_type: MetricType
    points: deque = field(default_factory=lambda: deque(maxlen=1000))
    tags: Dict[str, str] = field(default_factory=dict)
    unit: Optional[str] = None

    def add_point(
        self,
        value: float,
        timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Add a point to the series."""
        point = MetricPoint(
            name=self.name,
            value=value,
            metric_type=self.metric_type,
            timestamp=timestamp,
            tags=self.tags.copy(),
            unit=self.unit,
            metadata=metadata or {},
        )
        self.points.append(point)

    def get_latest(self) -> Optional[MetricPoint]:
        """Get the latest point in the series."""
        return self.points[-1] if self.points else None

    def get_range(self, start_time: datetime, end_time: datetime) -> List[MetricPoint]:
        """Get points within a time range."""
        return [
            point for point in self.points if start_time <= point.timestamp <= end_time
        ]

    def get_statistics(self, window_minutes: int = 60) -> Dict[str, float]:
        """Get statistics for the series over a time window."""
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_points = [p for p in self.points if p.timestamp >= cutoff_time]

        if not recent_points:
            return {"count": 0, "min": 0, "max": 0, "mean": 0, "sum": 0}

        values = [p.value for p in recent_points]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "sum": sum(values),
            "std_dev": self._calculate_std_dev(values),
            "p50": self._percentile(values, 50),
            "p95": self._percentile(values, 95),
            "p99": self._percentile(values, 99),
        }

    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance**0.5

    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]


class MetricsCollector:
    """Collects and stores metrics from source control operations."""

    def __init__(
        self,
        max_series: int = 100,
        max_points_per_series: int = 100,
        retention_hours: int = 24,
        cleanup_interval_minutes: int = 60,
    ):
        self.series: Dict[str, MetricSeries] = {}
        self.max_series = max_series
        self.max_points_per_series = max_points_per_series
        self.retention_hours = retention_hours
        self.cleanup_interval_minutes = cleanup_interval_minutes
        self.logger = logging.getLogger("MetricsCollector")
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._metric_queue: Optional[asyncio.Queue] = None
        self._background_task: Optional[asyncio.Task] = None

    async def record_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType,
        tags: Optional[Dict[str, str]] = None,
        unit: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a metric point."""
        async with self._lock:
            # Create series key from name and tags
            series_key = self._create_series_key(name, tags or {})

            # Get or create series
            if series_key not in self.series:
                if len(self.series) >= self.max_series:
                    # Remove oldest series
                    oldest_key = min(
                        self.series.keys(),
                        key=lambda k: (
                            self.series[k].points[0].timestamp
                            if self.series[k].points
                            else datetime.min
                        ),
                    )
                    del self.series[oldest_key]

                self.series[series_key] = MetricSeries(
                    name=name, metric_type=metric_type, tags=tags or {}, unit=unit
                )

            # Add point to series
            self.series[series_key].add_point(value, datetime.now(), metadata)

    def _create_series_key(self, name: str, tags: Dict[str, str]) -> str:
        """Create a unique key for a metric series."""
        if not tags:
            return name

        sorted_tags = sorted(tags.items())
        tag_str = ",".join(f"{k}={v}" for k, v in sorted_tags)
        return f"{name}[{tag_str}]"

    async def get_metric_series(
        self, name: str, tags: Optional[Dict[str, str]] = None
    ) -> Optional[MetricSeries]:
        """Get a metric series by name and tags."""
        series_key = self._create_series_key(name, tags or {})
        return self.series.get(series_key)

    async def get_metric_value(
        self, name: str, tags: Optional[Dict[str, str]] = None
    ) -> Optional[float]:
        """Get the latest value for a metric."""
        series = await self.get_metric_series(name, tags)
        if series and series.points:
            return series.points[-1].value
        return None

    async def get_metric_statistics(
        self, name: str, tags: Optional[Dict[str, str]] = None, window_minutes: int = 60
    ) -> Dict[str, float]:
        """Get statistics for a metric over a time window."""
        series = await self.get_metric_series(name, tags)
        if series:
            return series.get_statistics(window_minutes)
        return {"count": 0, "min": 0, "max": 0, "mean": 0, "sum": 0}

    async def list_metrics(self) -> List[str]:
        """List all metric names."""
        return list(set(series.name for series in self.series.values()))

    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        summary = {
            "total_series": len(self.series),
            "metrics": {},
            "timestamp": datetime.now().isoformat(),
        }

        # Group series by name
        metrics_by_name = defaultdict(list)
        for series in self.series.values():
            metrics_by_name[series.name].append(series)

        # Calculate summary for each metric
        for name, series_list in metrics_by_name.items():
            all_points = []
            for series in series_list:
                all_points.extend(series.points)

            if all_points:
                values = [p.value for p in all_points]
                summary["metrics"][name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                    "sum": sum(values),
                    "series_count": len(series_list),
                    "latest_timestamp": max(
                        p.timestamp for p in all_points
                    ).isoformat(),
                }

        return summary

    async def start_background_processing(self):
        """Start background metric processing and cleanup."""
        if self._background_task is None:
            self._metric_queue = asyncio.Queue(maxsize=1000)
            self._background_task = asyncio.create_task(self._process_metrics())
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self.logger.info("Started background metric processing")

    async def stop_background_processing(self):
        """Stop background metric processing."""
        if self._background_task:
            self._background_task.cancel()
            self._background_task = None
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
        self.logger.info("Stopped background metric processing")

    async def record_metric_async(
        self,
        name: str,
        value: float,
        metric_type: MetricType,
        tags: Optional[Dict[str, str]] = None,
        unit: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Queue metric for background processing."""
        if self._metric_queue is None:
            # Fallback to synchronous processing
            await self.record_metric(name, value, metric_type, tags, unit, metadata)
            return

        metric_data = {
            "name": name,
            "value": value,
            "metric_type": metric_type,
            "tags": tags,
            "unit": unit,
            "metadata": metadata,
            "timestamp": datetime.now(),
        }

        try:
            self._metric_queue.put_nowait(metric_data)
        except asyncio.QueueFull:
            # Drop oldest metric or implement overflow strategy
            self.logger.warning(f"Metric queue full, dropping metric: {name}")
            # Try to remove oldest metric and add new one
            try:
                self._metric_queue.get_nowait()
                self._metric_queue.put_nowait(metric_data)
            except asyncio.QueueEmpty:
                pass

    async def record_metrics_batch_async(self, metrics: List[Dict[str, Any]]) -> None:
        """Queue multiple metrics for batch background processing."""
        if self._metric_queue is None:
            # Fallback to synchronous processing
            for metric_data in metrics:
                await self.record_metric(
                    metric_data["name"],
                    metric_data["value"],
                    metric_data["metric_type"],
                    metric_data.get("tags"),
                    metric_data.get("unit"),
                    metric_data.get("metadata"),
                )
            return

        # Add timestamps to all metrics
        for metric_data in metrics:
            metric_data["timestamp"] = datetime.now()

        # Try to add all metrics to the queue
        failed_metrics = []
        for metric_data in metrics:
            try:
                self._metric_queue.put_nowait(metric_data)
            except asyncio.QueueFull:
                failed_metrics.append(metric_data)

        if failed_metrics:
            self.logger.warning(
                f"Metric queue full, dropped {len(failed_metrics)} metrics"
            )
            # Try to make space and add some of the failed metrics
            try:
                # Remove some old metrics to make space
                for _ in range(min(len(failed_metrics), 10)):
                    self._metric_queue.get_nowait()

                # Add some of the failed metrics back
                for metric_data in failed_metrics[:10]:
                    try:
                        self._metric_queue.put_nowait(metric_data)
                    except asyncio.QueueFull:
                        break
            except asyncio.QueueEmpty:
                pass

    async def _process_metrics(self):
        """Background task to process queued metrics with batch processing."""
        batch_size = 10
        batch_timeout = 1.0  # seconds

        while True:
            try:
                # Collect metrics in batches for more efficient processing
                batch = []
                start_time = asyncio.get_event_loop().time()

                # Collect up to batch_size metrics or wait for timeout
                while len(batch) < batch_size:
                    try:
                        # Wait for next metric with timeout
                        remaining_time = batch_timeout - (
                            asyncio.get_event_loop().time() - start_time
                        )
                        if remaining_time <= 0:
                            break

                        if self._metric_queue is not None:
                            metric_data = await asyncio.wait_for(
                                self._metric_queue.get(), timeout=remaining_time
                            )
                        else:
                            break
                        batch.append(metric_data)
                    except asyncio.TimeoutError:
                        break

                # Process the batch
                if batch:
                    await self._process_metric_batch(batch)
                    # Mark all tasks as done
                    if self._metric_queue is not None:
                        for _ in batch:
                            self._metric_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error processing metric batch: {e}")
                # Mark any remaining tasks as done to prevent deadlock
                if self._metric_queue is not None:
                    try:
                        while not self._metric_queue.empty():
                            self._metric_queue.task_done()
                    except:
                        pass

    async def _process_metric_batch(self, batch: List[Dict[str, Any]]):
        """Process a batch of metrics efficiently."""
        # Group metrics by name for more efficient processing
        metrics_by_name = {}
        for metric_data in batch:
            name = metric_data["name"]
            if name not in metrics_by_name:
                metrics_by_name[name] = []
            metrics_by_name[name].append(metric_data)

        # Process each metric name group
        for name, metric_list in metrics_by_name.items():
            try:
                # Use the first metric as template for series info
                template = metric_list[0]
                series_key = self._create_series_key(name, template.get("tags") or {})

                async with self._lock:
                    if series_key not in self.series:
                        self.series[series_key] = MetricSeries(
                            name=name,
                            metric_type=template["metric_type"],
                            tags=template.get("tags"),
                            unit=template.get("unit"),
                        )

                    series = self.series[series_key]

                    # Add all points from the batch
                    for metric_data in metric_list:
                        point = MetricPoint(
                            name=name,
                            metric_type=template["metric_type"],
                            value=metric_data["value"],
                            timestamp=metric_data["timestamp"],
                            metadata=metric_data.get("metadata"),
                        )
                        series.points.append(point)

                        # Enforce max points per series
                        if len(series.points) > self.max_points_per_series:
                            series.points.popleft()

            except Exception as e:
                self.logger.error(f"Error processing metric batch for {name}: {e}")

    async def _process_metric_sync(self, metric_data: Dict[str, Any]):
        """Process a single metric synchronously."""
        await self.record_metric(
            metric_data["name"],
            metric_data["value"],
            metric_data["metric_type"],
            metric_data["tags"],
            metric_data["unit"],
            metric_data["metadata"],
        )

    async def _cleanup_loop(self):
        """Background task to clean up old metrics."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_minutes * 60)
                await self.cleanup_old_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error during metrics cleanup: {e}")

    async def cleanup_old_metrics(self):
        """Remove metrics older than retention period."""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)
        removed_series = 0
        removed_points = 0

        async with self._lock:
            # Clean up old points in each series
            for series_key, series in list(self.series.items()):
                original_count = len(series.points)
                # Remove old points
                series.points = deque(
                    [p for p in series.points if p.timestamp >= cutoff_time],
                    maxlen=self.max_points_per_series,
                )
                removed_points += original_count - len(series.points)

                # Remove empty series
                if not series.points:
                    del self.series[series_key]
                    removed_series += 1

        if removed_series > 0 or removed_points > 0:
            self.logger.info(
                f"Cleaned up {removed_series} series and {removed_points} points older than {self.retention_hours} hours"
            )

    async def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics for metrics collection."""
        total_points = sum(len(series.points) for series in self.series.values())
        total_series = len(self.series)

        # Estimate memory usage (rough calculation)
        estimated_memory_mb = (total_points * 200 + total_series * 1000) / (
            1024 * 1024
        )  # Rough estimate

        return {
            "total_series": total_series,
            "total_points": total_points,
            "estimated_memory_mb": round(estimated_memory_mb, 2),
            "max_series": self.max_series,
            "max_points_per_series": self.max_points_per_series,
            "retention_hours": self.retention_hours,
            "memory_usage_percentage": (
                round((total_series / self.max_series) * 100, 2)
                if self.max_series > 0
                else 0
            ),
        }


class OperationMetrics:
    """Metrics collector specifically for source control operations."""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.logger = logging.getLogger("OperationMetrics")

    async def record_operation_start(
        self,
        operation_name: str,
        provider_name: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> str:
        """Record the start of an operation and return an operation ID."""
        operation_id = f"{operation_name}_{int(time.time() * 1000)}"

        operation_tags = tags or {}
        operation_tags.update(
            {
                "provider": provider_name,
                "operation": operation_name,
                "operation_id": operation_id,
            }
        )

        await self.collector.record_metric(
            name="operation_start",
            value=1,
            metric_type=MetricType.COUNTER,
            tags=operation_tags,
            metadata={"start_time": datetime.now().isoformat()},
        )

        return operation_id

    async def record_operation_end(
        self,
        operation_id: str,
        operation_name: str,
        provider_name: str,
        success: bool,
        duration_ms: float,
        error: Optional[Exception] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record the end of an operation."""
        operation_tags = tags or {}
        operation_tags.update(
            {
                "provider": provider_name,
                "operation": operation_name,
                "operation_id": operation_id,
                "status": "success" if success else "failure",
            }
        )

        # Record operation completion
        await self.collector.record_metric(
            name="operation_complete",
            value=1,
            metric_type=MetricType.COUNTER,
            tags=operation_tags,
        )

        # Record operation duration
        await self.collector.record_metric(
            name="operation_duration",
            value=duration_ms,
            metric_type=MetricType.TIMER,
            tags=operation_tags,
            unit="ms",
        )

        # Record success/failure rate
        await self.collector.record_metric(
            name="operation_success_rate",
            value=1.0 if success else 0.0,
            metric_type=MetricType.GAUGE,
            tags=operation_tags,
        )

        # Record error if present
        if error:
            error_tags = operation_tags.copy()
            error_tags["error_type"] = type(error).__name__
            await self.collector.record_metric(
                name="operation_errors",
                value=1,
                metric_type=MetricType.COUNTER,
                tags=error_tags,
                metadata={"error_message": str(error)},
            )

    async def record_remediation_result(
        self,
        result: RemediationResult,
        provider_name: str,
        duration_ms: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record metrics for a remediation result."""
        operation_tags = tags or {}
        operation_tags.update(
            {
                "provider": provider_name,
                "operation": "remediation",
                "operation_type": result.operation_type,
                "status": "success" if result.success else "failure",
            }
        )

        # Record remediation completion
        await self.collector.record_metric(
            name="remediation_complete",
            value=1,
            metric_type=MetricType.COUNTER,
            tags=operation_tags,
        )

        # Record remediation duration
        await self.collector.record_metric(
            name="remediation_duration",
            value=duration_ms,
            metric_type=MetricType.TIMER,
            tags=operation_tags,
            unit="ms",
        )

        # Record file path if available
        if result.file_path:
            file_tags = operation_tags.copy()
            file_tags["file_path"] = result.file_path
            await self.collector.record_metric(
                name="remediation_file_operations",
                value=1,
                metric_type=MetricType.COUNTER,
                tags=file_tags,
            )

    async def record_batch_operation_result(
        self,
        result: OperationResult,
        provider_name: str,
        duration_ms: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record metrics for a batch operation result."""
        operation_tags = tags or {}
        operation_tags.update(
            {
                "provider": provider_name,
                "operation": "batch_operation",
                "status": "success" if result.success else "failure",
            }
        )

        # Record batch operation completion
        await self.collector.record_metric(
            name="batch_operation_complete",
            value=1,
            metric_type=MetricType.COUNTER,
            tags=operation_tags,
        )

        # Record batch operation duration
        await self.collector.record_metric(
            name="batch_operation_duration",
            value=duration_ms,
            metric_type=MetricType.TIMER,
            tags=operation_tags,
            unit="ms",
        )

    async def record_health_check(
        self,
        health: ProviderHealth,
        provider_name: str,
        duration_ms: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record metrics for a health check."""
        operation_tags = tags or {}
        operation_tags.update(
            {
                "provider": provider_name,
                "operation": "health_check",
                "status": health.status,
            }
        )

        # Record health check completion
        await self.collector.record_metric(
            name="health_check_complete",
            value=1,
            metric_type=MetricType.COUNTER,
            tags=operation_tags,
        )

        # Record health check duration
        await self.collector.record_metric(
            name="health_check_duration",
            value=duration_ms,
            metric_type=MetricType.TIMER,
            tags=operation_tags,
            unit="ms",
        )

        # Record health status
        await self.collector.record_metric(
            name="provider_health_status",
            value=1.0 if health.status == "healthy" else 0.0,
            metric_type=MetricType.GAUGE,
            tags=operation_tags,
        )

    async def get_operation_statistics(
        self,
        provider_name: str,
        operation_name: Optional[str] = None,
        window_minutes: int = 60,
    ) -> Dict[str, Any]:
        """Get statistics for operations."""
        stats = {}

        # Get operation completion stats
        completion_tags = {"provider": provider_name}
        if operation_name:
            completion_tags["operation"] = operation_name

        completion_stats = await self.collector.get_metric_statistics(
            "operation_complete", completion_tags, window_minutes
        )
        stats["total_operations"] = completion_stats["count"]

        # Get success rate
        success_tags = completion_tags.copy()
        success_tags["status"] = "success"
        success_stats = await self.collector.get_metric_statistics(
            "operation_complete", success_tags, window_minutes
        )

        if completion_stats["count"] > 0:
            stats["success_rate"] = success_stats["count"] / completion_stats["count"]
        else:
            stats["success_rate"] = 0.0

        # Get duration stats
        duration_stats = await self.collector.get_metric_statistics(
            "operation_duration", completion_tags, window_minutes
        )
        stats["avg_duration_ms"] = duration_stats["mean"]
        stats["p95_duration_ms"] = duration_stats["p95"]
        stats["p99_duration_ms"] = duration_stats["p99"]

        # Get error stats
        error_tags = completion_tags.copy()
        error_tags["status"] = "failure"
        error_stats = await self.collector.get_metric_statistics(
            "operation_complete", error_tags, window_minutes
        )
        stats["error_count"] = error_stats["count"]

        return stats


class MetricsAnalyzer:
    """Analyzes metrics to provide insights and recommendations."""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.logger = logging.getLogger("MetricsAnalyzer")

    async def analyze_performance_trends(
        self, provider_name: str, window_minutes: int = 60
    ) -> Dict[str, Any]:
        """Analyze performance trends for a provider."""
        analysis = {
            "provider": provider_name,
            "window_minutes": window_minutes,
            "timestamp": datetime.now().isoformat(),
            "trends": {},
        }

        # Analyze operation duration trends
        duration_stats = await self.collector.get_metric_statistics(
            "operation_duration", {"provider": provider_name}, window_minutes
        )

        if duration_stats["count"] > 0:
            analysis["trends"]["operation_duration"] = {
                "current_avg_ms": duration_stats["mean"],
                "p95_ms": duration_stats["p95"],
                "p99_ms": duration_stats["p99"],
                "total_operations": duration_stats["count"],
            }

        # Analyze success rate trends
        success_rate = await self.collector.get_metric_value(
            "operation_success_rate", {"provider": provider_name}
        )
        if success_rate is not None:
            analysis["trends"]["success_rate"] = {
                "current_rate": success_rate,
                "status": (
                    "healthy"
                    if success_rate > 0.95
                    else "degraded" if success_rate > 0.8 else "unhealthy"
                ),
            }

        return analysis

    async def detect_anomalies(
        self, provider_name: str, window_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in provider metrics."""
        anomalies = []

        # Check for high error rates
        error_stats = await self.collector.get_metric_statistics(
            "operation_errors", {"provider": provider_name}, window_minutes
        )
        total_ops = await self.collector.get_metric_statistics(
            "operation_complete", {"provider": provider_name}, window_minutes
        )

        if total_ops["count"] > 0 and error_stats["count"] / total_ops["count"] > 0.1:
            anomalies.append(
                {
                    "type": "high_error_rate",
                    "severity": "warning",
                    "message": f"High error rate: {error_stats['count']}/{total_ops['count']} operations failed",
                    "value": error_stats["count"] / total_ops["count"],
                    "threshold": 0.1,
                }
            )

        # Check for slow operations
        duration_stats = await self.collector.get_metric_statistics(
            "operation_duration", {"provider": provider_name}, window_minutes
        )

        if duration_stats["count"] > 0 and duration_stats["p95"] > 5000:
            anomalies.append(
                {
                    "type": "slow_operations",
                    "severity": "warning",
                    "message": f"Slow operations detected: P95 duration is {duration_stats['p95']:.0f}ms",
                    "value": duration_stats["p95"],
                    "threshold": 5000,
                }
            )

        return anomalies

    async def generate_recommendations(
        self, provider_name: str, window_minutes: int = 60
    ) -> List[str]:
        """Generate recommendations based on metrics analysis."""
        recommendations = []

        # Analyze performance
        trends = await self.analyze_performance_trends(provider_name, window_minutes)

        if "operation_duration" in trends["trends"]:
            avg_duration = trends["trends"]["operation_duration"]["current_avg_ms"]
            if avg_duration > 2000:
                recommendations.append(
                    f"Consider optimizing operations - average duration is {avg_duration:.0f}ms"
                )

        if "success_rate" in trends["trends"]:
            success_rate = trends["trends"]["success_rate"]["current_rate"]
            if success_rate < 0.9:
                recommendations.append(
                    f"Investigate error causes - success rate is {success_rate:.1%}"
                )

        # Check for anomalies
        anomalies = await self.detect_anomalies(provider_name, window_minutes)
        for anomaly in anomalies:
            if anomaly["type"] == "high_error_rate":
                recommendations.append(
                    "Review error logs and consider implementing retry logic"
                )
            elif anomaly["type"] == "slow_operations":
                recommendations.append(
                    "Consider implementing caching or optimizing slow operations"
                )

        return recommendations
