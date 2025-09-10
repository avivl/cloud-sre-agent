"""
Background metric processing and cleanup.

This module handles asynchronous metric processing, batching, and cleanup operations.
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .core import MetricSeries, MetricType, MetricPoint

if TYPE_CHECKING:
    from .collectors import MetricsCollector


class BackgroundProcessor:
    """Handles background processing of metrics."""

    def __init__(self, collector: "MetricsCollector"):
        self.collector = collector
        self.logger = logging.getLogger("BackgroundProcessor")
        self._cleanup_task: Optional[asyncio.Task] = None
        self._metric_queue: Optional[asyncio.Queue] = None
        self._background_task: Optional[asyncio.Task] = None

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
            await self.collector.record_metric(name, value, metric_type, tags, unit, metadata)
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
                await self.collector.record_metric(
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
                    except Exception:
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
                series_key = self.collector._create_series_key(name, template.get("tags") or {})

                async with self.collector._lock:
                    if series_key not in self.collector.series:
                        self.collector.series[series_key] = MetricSeries(
                            name=name,
                            metric_type=template["metric_type"],
                            tags=template.get("tags"),
                            unit=template.get("unit"),
                        )

                    series = self.collector.series[series_key]

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
                        if len(series.points) > self.collector.max_points_per_series:
                            series.points.popleft()

            except Exception as e:
                self.logger.error(f"Error processing metric batch for {name}: {e}")

    async def _cleanup_loop(self):
        """Background task to clean up old metrics."""
        while True:
            try:
                await asyncio.sleep(self.collector.cleanup_interval_minutes * 60)
                await self.cleanup_old_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error during metrics cleanup: {e}")

    async def cleanup_old_metrics(self):
        """Remove metrics older than retention period."""
        cutoff_time = datetime.now() - timedelta(hours=self.collector.retention_hours)
        removed_series = 0
        removed_points = 0

        async with self.collector._lock:
            # Clean up old points in each series
            for series_key, series in list(self.collector.series.items()):
                original_count = len(series.points)
                # Remove old points
                series.points = deque(
                    [p for p in series.points if p.timestamp >= cutoff_time],
                    maxlen=self.collector.max_points_per_series,
                )
                removed_points += original_count - len(series.points)

                # Remove empty series
                if not series.points:
                    del self.collector.series[series_key]
                    removed_series += 1

        if removed_series > 0 or removed_points > 0:
            self.logger.info(
                f"Cleaned up {removed_series} series and {removed_points} points older than {self.collector.retention_hours} hours"
            )
