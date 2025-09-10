"""
Core metrics collection and storage.

This module provides the core metrics collection functionality.
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from .core import MetricSeries, MetricType
from .background_processing import BackgroundProcessor
from .operation_metrics import OperationMetrics


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
        
        # Initialize background processor and operation metrics
        self.background_processor = BackgroundProcessor(self)
        self.operation_metrics = OperationMetrics(self)

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

    # Delegate background processing to the background processor
    async def start_background_processing(self):
        """Start background metric processing and cleanup."""
        await self.background_processor.start_background_processing()

    async def stop_background_processing(self):
        """Stop background metric processing."""
        await self.background_processor.stop_background_processing()

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
        await self.background_processor.record_metric_async(
            name, value, metric_type, tags or {}, unit or "", metadata or {}
        )

    async def record_metrics_batch_async(self, metrics: List[Dict[str, Any]]) -> None:
        """Queue multiple metrics for batch background processing."""
        await self.background_processor.record_metrics_batch_async(metrics)

    async def cleanup_old_metrics(self):
        """Remove metrics older than retention period."""
        await self.background_processor.cleanup_old_metrics()

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
