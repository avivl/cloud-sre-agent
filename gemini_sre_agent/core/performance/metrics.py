"""Core performance metrics collection system."""

import asyncio
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable
from contextlib import asynccontextmanager, contextmanager

from ..logging import get_logger

logger = get_logger(__name__)


class MetricType(Enum):
    """Types of performance metrics."""
    
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"


@dataclass
class MetricValue:
    """A single metric value with metadata.
    
    Attributes:
        name: Name of the metric
        value: Numeric value
        timestamp: When the metric was recorded
        tags: Additional metadata tags
        unit: Unit of measurement (e.g., 'ms', 'bytes', 'count')
    """
    
    name: str
    value: Union[int, float]
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


@dataclass
class MetricAggregation:
    """Aggregated metric statistics.
    
    Attributes:
        count: Number of samples
        sum: Sum of all values
        min: Minimum value
        max: Maximum value
        mean: Average value
        p50: 50th percentile
        p95: 95th percentile
        p99: 99th percentile
    """
    
    count: int = 0
    sum: float = 0.0
    min: float = float('inf')
    max: float = float('-inf')
    mean: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0


@dataclass
class PerformanceMetrics:
    """Performance metrics for a specific operation or component.
    
    Attributes:
        operation_name: Name of the operation
        total_requests: Total number of requests
        successful_requests: Number of successful requests
        failed_requests: Number of failed requests
        avg_response_time: Average response time in milliseconds
        min_response_time: Minimum response time in milliseconds
        max_response_time: Maximum response time in milliseconds
        p95_response_time: 95th percentile response time in milliseconds
        p99_response_time: 99th percentile response time in milliseconds
        throughput: Requests per second
        error_rate: Error rate as percentage
        memory_usage: Memory usage in bytes
        cpu_usage: CPU usage as percentage
        timestamp: When metrics were collected
    """
    
    operation_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    throughput: float = 0.0
    error_rate: float = 0.0
    memory_usage: int = 0
    cpu_usage: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class MetricsConfig:
    """Configuration for metrics collection.
    
    Attributes:
        max_metrics_per_operation: Maximum number of metrics to store per operation
        aggregation_window: Time window for metric aggregation in seconds
        retention_period: How long to keep metrics in seconds
        enable_memory_tracking: Whether to track memory usage
        enable_cpu_tracking: Whether to track CPU usage
        enable_async_tracking: Whether to track async operations
        sampling_rate: Rate of metric sampling (0.0 to 1.0)
    """
    
    max_metrics_per_operation: int = 10000
    aggregation_window: float = 60.0
    retention_period: float = 3600.0
    enable_memory_tracking: bool = True
    enable_cpu_tracking: bool = True
    enable_async_tracking: bool = True
    sampling_rate: float = 1.0


class MetricsCollector:
    """Core performance metrics collection system.
    
    Provides comprehensive metrics collection for HTTP requests,
    memory usage, CPU utilization, and I/O throughput with
    configurable aggregation and retention policies.
    """
    
    def __init__(self, config: Optional[MetricsConfig] = None):
        """Initialize the metrics collector.
        
        Args:
            config: Metrics collection configuration
        """
        self._config = config or MetricsConfig()
        self._lock = threading.RLock()
        self._metrics: Dict[str, deque] = {}
        self._aggregations: Dict[str, MetricAggregation] = {}
        self._operation_timers: Dict[str, float] = {}
        self._operation_counts: Dict[str, int] = {}
        self._operation_errors: Dict[str, int] = {}
        self._memory_samples: deque = deque(maxlen=self._config.max_metrics_per_operation)
        self._cpu_samples: deque = deque(maxlen=self._config.max_metrics_per_operation)
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_old_metrics())
    
    async def _cleanup_old_metrics(self) -> None:
        """Clean up old metrics based on retention period."""
        while True:
            try:
                current_time = time.time()
                cutoff_time = current_time - self._config.retention_period
                
                with self._lock:
                    for operation_name, metrics_deque in self._metrics.items():
                        # Remove old metrics
                        while metrics_deque and metrics_deque[0].timestamp < cutoff_time:
                            metrics_deque.popleft()
                
                # Clean up old memory and CPU samples
                while self._memory_samples and self._memory_samples[0].timestamp < cutoff_time:
                    self._memory_samples.popleft()
                
                while self._cpu_samples and self._cpu_samples[0].timestamp < cutoff_time:
                    self._cpu_samples.popleft()
                
                await asyncio.sleep(self._config.aggregation_window)
                
            except Exception as e:
                logger.error(f"Error in metrics cleanup task: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    def record_metric(
        self,
        name: str,
        value: Union[int, float],
        operation: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        unit: str = ""
    ) -> None:
        """Record a metric value.
        
        Args:
            name: Name of the metric
            value: Metric value
            operation: Operation name (optional)
            tags: Additional metadata tags
            unit: Unit of measurement
        """
        if not self._should_sample():
            return
        
        metric = MetricValue(
            name=name,
            value=value,
            tags=tags or {},
            unit=unit
        )
        
        with self._lock:
            # Store metric by operation or global
            key = operation or "global"
            if key not in self._metrics:
                self._metrics[key] = deque(maxlen=self._config.max_metrics_per_operation)
            
            self._metrics[key].append(metric)
            
            # Update aggregation
            self._update_aggregation(key, metric)
    
    def _should_sample(self) -> bool:
        """Check if we should sample this metric based on sampling rate.
        
        Returns:
            True if we should sample, False otherwise
        """
        import random
        return random.random() < self._config.sampling_rate
    
    def _update_aggregation(self, key: str, metric: MetricValue) -> None:
        """Update metric aggregation for a key.
        
        Args:
            key: Aggregation key
            metric: Metric value to aggregate
        """
        if key not in self._aggregations:
            self._aggregations[key] = MetricAggregation()
        
        agg = self._aggregations[key]
        agg.count += 1
        agg.sum += metric.value
        agg.min = min(agg.min, metric.value)
        agg.max = max(agg.max, metric.value)
        agg.mean = agg.sum / agg.count
        
        # Calculate percentiles (simplified implementation)
        if key in self._metrics:
            values = sorted([m.value for m in self._metrics[key]])
            if values:
                agg.p50 = values[int(len(values) * 0.5)]
                agg.p95 = values[int(len(values) * 0.95)]
                agg.p99 = values[int(len(values) * 0.99)]
    
    @contextmanager
    def track_operation(self, operation_name: str, tags: Optional[Dict[str, str]] = None):
        """Context manager for tracking operation performance.
        
        Args:
            operation_name: Name of the operation
            tags: Additional metadata tags
            
        Yields:
            Operation context
        """
        start_time = time.time()
        self._operation_timers[operation_name] = start_time
        
        try:
            yield
            # Record success
            duration = time.time() - start_time
            self.record_metric(
                "operation_duration",
                duration * 1000,  # Convert to milliseconds
                operation=operation_name,
                tags=tags,
                unit="ms"
            )
            self._increment_operation_count(operation_name, success=True)
            
        except Exception as e:
            # Record failure
            duration = time.time() - start_time
            self.record_metric(
                "operation_duration",
                duration * 1000,
                operation=operation_name,
                tags={**(tags or {}), "error": str(e)},
                unit="ms"
            )
            self._increment_operation_count(operation_name, success=False)
            raise
    
    @asynccontextmanager
    async def track_async_operation(
        self,
        operation_name: str,
        tags: Optional[Dict[str, str]] = None
    ):
        """Async context manager for tracking async operation performance.
        
        Args:
            operation_name: Name of the operation
            tags: Additional metadata tags
            
        Yields:
            Async operation context
        """
        start_time = time.time()
        self._operation_timers[operation_name] = start_time
        
        try:
            yield
            # Record success
            duration = time.time() - start_time
            self.record_metric(
                "async_operation_duration",
                duration * 1000,  # Convert to milliseconds
                operation=operation_name,
                tags=tags,
                unit="ms"
            )
            self._increment_operation_count(operation_name, success=True)
            
        except Exception as e:
            # Record failure
            duration = time.time() - start_time
            self.record_metric(
                "async_operation_duration",
                duration * 1000,
                operation=operation_name,
                tags={**(tags or {}), "error": str(e)},
                unit="ms"
            )
            self._increment_operation_count(operation_name, success=False)
            raise
    
    def _increment_operation_count(self, operation_name: str, success: bool = True) -> None:
        """Increment operation count.
        
        Args:
            operation_name: Name of the operation
            success: Whether the operation was successful
        """
        with self._lock:
            if operation_name not in self._operation_counts:
                self._operation_counts[operation_name] = 0
                self._operation_errors[operation_name] = 0
            
            self._operation_counts[operation_name] += 1
            if not success:
                self._operation_errors[operation_name] += 1
    
    def record_memory_usage(self, operation: Optional[str] = None) -> None:
        """Record current memory usage.
        
        Args:
            operation: Operation name (optional)
        """
        if not self._config.enable_memory_tracking:
            return
        
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_usage = memory_info.rss  # Resident Set Size
            
            self.record_metric(
                "memory_usage",
                memory_usage,
                operation=operation,
                unit="bytes"
            )
            
            # Store in memory samples
            self._memory_samples.append(MetricValue(
                name="memory_usage",
                value=memory_usage,
                unit="bytes"
            ))
            
        except ImportError:
            logger.warning("psutil not available for memory tracking")
        except Exception as e:
            logger.error(f"Error recording memory usage: {e}")
    
    def record_cpu_usage(self, operation: Optional[str] = None) -> None:
        """Record current CPU usage.
        
        Args:
            operation: Operation name (optional)
        """
        if not self._config.enable_cpu_tracking:
            return
        
        try:
            import psutil
            cpu_percent = psutil.cpu_percent()
            
            self.record_metric(
                "cpu_usage",
                cpu_percent,
                operation=operation,
                unit="percent"
            )
            
            # Store in CPU samples
            self._cpu_samples.append(MetricValue(
                name="cpu_usage",
                value=cpu_percent,
                unit="percent"
            ))
            
        except ImportError:
            logger.warning("psutil not available for CPU tracking")
        except Exception as e:
            logger.error(f"Error recording CPU usage: {e}")
    
    def get_metrics(self, operation: Optional[str] = None) -> List[MetricValue]:
        """Get metrics for a specific operation or all operations.
        
        Args:
            operation: Operation name (optional)
            
        Returns:
            List of metric values
        """
        with self._lock:
            if operation:
                return list(self._metrics.get(operation, []))
            else:
                all_metrics = []
                for metrics_deque in self._metrics.values():
                    all_metrics.extend(metrics_deque)
                return all_metrics
    
    def get_aggregation(self, operation: Optional[str] = None) -> Dict[str, MetricAggregation]:
        """Get metric aggregations.
        
        Args:
            operation: Operation name (optional)
            
        Returns:
            Dictionary of metric aggregations
        """
        with self._lock:
            if operation:
                return {operation: self._aggregations.get(operation, MetricAggregation())}
            else:
                return dict(self._aggregations)
    
    def get_performance_metrics(self, operation_name: str) -> PerformanceMetrics:
        """Get comprehensive performance metrics for an operation.
        
        Args:
            operation_name: Name of the operation
            
        Returns:
            Performance metrics
        """
        with self._lock:
            total_requests = self._operation_counts.get(operation_name, 0)
            failed_requests = self._operation_errors.get(operation_name, 0)
            successful_requests = total_requests - failed_requests
            
            # Get response time metrics
            response_times = [
                m.value for m in self._metrics.get(operation_name, [])
                if m.name in ["operation_duration", "async_operation_duration"]
            ]
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                min_response_time = min(response_times)
                max_response_time = max(response_times)
                
                # Calculate percentiles
                sorted_times = sorted(response_times)
                p95_response_time = sorted_times[int(len(sorted_times) * 0.95)]
                p99_response_time = sorted_times[int(len(sorted_times) * 0.99)]
            else:
                avg_response_time = min_response_time = max_response_time = 0.0
                p95_response_time = p99_response_time = 0.0
            
            # Calculate throughput and error rate
            time_window = self._config.aggregation_window
            throughput = total_requests / time_window if time_window > 0 else 0.0
            error_rate = (failed_requests / total_requests * 100) if total_requests > 0 else 0.0
            
            # Get memory and CPU usage
            memory_usage = self._memory_samples[-1].value if self._memory_samples else 0
            cpu_usage = self._cpu_samples[-1].value if self._cpu_samples else 0.0
            
            return PerformanceMetrics(
                operation_name=operation_name,
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                avg_response_time=avg_response_time,
                min_response_time=min_response_time,
                max_response_time=max_response_time,
                p95_response_time=p95_response_time,
                p99_response_time=p99_response_time,
                throughput=throughput,
                error_rate=error_rate,
                memory_usage=int(memory_usage),
                cpu_usage=cpu_usage
            )
    
    def get_all_performance_metrics(self) -> Dict[str, PerformanceMetrics]:
        """Get performance metrics for all operations.
        
        Returns:
            Dictionary of operation names to performance metrics
        """
        with self._lock:
            operations = set(self._operation_counts.keys())
            return {
                operation: self.get_performance_metrics(operation)
                for operation in operations
            }
    
    def reset_metrics(self, operation: Optional[str] = None) -> None:
        """Reset metrics for a specific operation or all operations.
        
        Args:
            operation: Operation name (optional)
        """
        with self._lock:
            if operation:
                self._metrics.pop(operation, None)
                self._aggregations.pop(operation, None)
                self._operation_counts.pop(operation, None)
                self._operation_errors.pop(operation, None)
            else:
                self._metrics.clear()
                self._aggregations.clear()
                self._operation_counts.clear()
                self._operation_errors.clear()
                self._memory_samples.clear()
                self._cpu_samples.clear()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics.
        
        Returns:
            Metrics summary
        """
        with self._lock:
            return {
                "total_operations": len(self._operation_counts),
                "total_metrics": sum(len(metrics) for metrics in self._metrics.values()),
                "memory_samples": len(self._memory_samples),
                "cpu_samples": len(self._cpu_samples),
                "operations": list(self._operation_counts.keys()),
                "config": {
                    "max_metrics_per_operation": self._config.max_metrics_per_operation,
                    "aggregation_window": self._config.aggregation_window,
                    "retention_period": self._config.retention_period,
                    "sampling_rate": self._config.sampling_rate
                }
            }
    
    def __enter__(self):
        """Context manager entry.
        
        Returns:
            Self
        """
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit.
        
        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
