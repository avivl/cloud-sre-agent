"""
Performance monitoring system for the log ingestion system.

Provides comprehensive performance monitoring including:
- Processing time tracking
- Throughput monitoring
- Resource utilization tracking
- Performance bottleneck identification
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import deque, defaultdict
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a component or operation."""
    name: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Processing metrics
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    
    # Timing metrics
    total_processing_time_ms: float = 0.0
    average_processing_time_ms: float = 0.0
    min_processing_time_ms: float = float('inf')
    max_processing_time_ms: float = 0.0
    
    # Throughput metrics
    operations_per_second: float = 0.0
    bytes_processed: int = 0
    bytes_per_second: float = 0.0
    
    # Resource metrics
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    # Error metrics
    error_rate: float = 0.0
    consecutive_failures: int = 0
    
    # Additional details
    details: Dict[str, Any] = field(default_factory=dict)


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system for the log ingestion system.
    
    Tracks performance metrics for:
    - Individual log adapters
    - Queue operations
    - Log processing pipeline
    - System resource utilization
    """
    
    def __init__(self, window_size: int = 1000, update_interval: timedelta = timedelta(seconds=10)):
        """
        Initialize the performance monitor.
        
        Args:
            window_size: Number of recent measurements to keep
            update_interval: How often to update aggregated metrics
        """
        self.window_size = window_size
        self.update_interval = update_interval
        
        # Performance data storage
        self._operation_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self._operation_counts: Dict[str, int] = defaultdict(int)
        self._success_counts: Dict[str, int] = defaultdict(int)
        self._failure_counts: Dict[str, int] = defaultdict(int)
        self._bytes_processed: Dict[str, int] = defaultdict(int)
        self._last_update: Dict[str, datetime] = defaultdict(lambda: datetime.now())
        
        # Aggregated metrics
        self._metrics: Dict[str, PerformanceMetrics] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Background update task
        self._update_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("PerformanceMonitor initialized")
    
    async def start(self) -> None:
        """Start the performance monitor."""
        if self._running:
            return
            
        self._running = True
        self._update_task = asyncio.create_task(self._update_metrics_periodically())
        logger.info("PerformanceMonitor started")
    
    async def stop(self) -> None:
        """Stop the performance monitor."""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        logger.info("PerformanceMonitor stopped")
    
    def record_operation(
        self,
        component: str,
        operation: str,
        duration_ms: float,
        success: bool = True,
        bytes_processed: int = 0,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record an operation's performance metrics.
        
        Args:
            component: Component name (e.g., 'file_system_adapter')
            operation: Operation name (e.g., 'process_logs')
            duration_ms: Operation duration in milliseconds
            success: Whether the operation was successful
            bytes_processed: Number of bytes processed
            details: Additional operation details
        """
        key = f"{component}:{operation}"
        now = datetime.now()
        
        with self._lock:
            # Record timing data
            self._operation_times[key].append((now, duration_ms))
            self._operation_counts[key] += 1
            self._last_update[key] = now
            
            if success:
                self._success_counts[key] += 1
            else:
                self._failure_counts[key] += 1
            
            self._bytes_processed[key] += bytes_processed
            
            # Update aggregated metrics immediately for real-time access
            self._update_component_metrics(key)
    
    def get_component_metrics(self, component: str) -> Dict[str, PerformanceMetrics]:
        """
        Get performance metrics for a specific component.
        
        Args:
            component: Component name
            
        Returns:
            Dictionary mapping operation names to PerformanceMetrics
        """
        with self._lock:
            return {
                key.split(':', 1)[1]: metrics
                for key, metrics in self._metrics.items()
                if key.startswith(f"{component}:")
            }
    
    def get_operation_metrics(self, component: str, operation: str) -> Optional[PerformanceMetrics]:
        """
        Get performance metrics for a specific operation.
        
        Args:
            component: Component name
            operation: Operation name
            
        Returns:
            PerformanceMetrics for the operation or None
        """
        key = f"{component}:{operation}"
        with self._lock:
            return self._metrics.get(key)
    
    def get_all_metrics(self) -> Dict[str, PerformanceMetrics]:
        """Get all performance metrics."""
        with self._lock:
            return dict(self._metrics)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive performance summary.
        
        Returns:
            Dictionary with performance summary
        """
        with self._lock:
            summary = {
                "timestamp": datetime.now().isoformat(),
                "components": {},
                "overall": {
                    "total_operations": sum(self._operation_counts.values()),
                    "total_successful": sum(self._success_counts.values()),
                    "total_failed": sum(self._failure_counts.values()),
                    "total_bytes_processed": sum(self._bytes_processed.values()),
                    "average_processing_time_ms": 0.0,
                    "overall_success_rate": 0.0
                }
            }
            
            # Calculate component-level summaries
            components = set(key.split(':', 1)[0] for key in self._metrics.keys())
            
            for component in components:
                component_metrics = self.get_component_metrics(component)
                
                total_ops = sum(m.total_operations for m in component_metrics.values())
                total_success = sum(m.successful_operations for m in component_metrics.values())
                total_time = sum(m.total_processing_time_ms for m in component_metrics.values())
                
                summary["components"][component] = {
                    "total_operations": total_ops,
                    "successful_operations": total_success,
                    "failed_operations": total_ops - total_success,
                    "success_rate": total_success / total_ops if total_ops > 0 else 0.0,
                    "average_processing_time_ms": total_time / total_ops if total_ops > 0 else 0.0,
                    "operations": {
                        op: {
                            "total_operations": m.total_operations,
                            "success_rate": m.error_rate,
                            "avg_processing_time_ms": m.average_processing_time_ms,
                            "throughput_ops_per_sec": m.operations_per_second,
                            "throughput_bytes_per_sec": m.bytes_per_second
                        }
                        for op, m in component_metrics.items()
                    }
                }
            
            # Calculate overall metrics
            total_ops = summary["overall"]["total_operations"]
            if total_ops > 0:
                summary["overall"]["overall_success_rate"] = summary["overall"]["total_successful"] / total_ops
                
                # Calculate weighted average processing time
                total_time = sum(
                    m.total_processing_time_ms for m in self._metrics.values()
                )
                summary["overall"]["average_processing_time_ms"] = total_time / total_ops
            
            return summary
    
    def get_bottlenecks(self, threshold_ms: float = 1000.0) -> List[Dict[str, Any]]:
        """
        Identify performance bottlenecks.
        
        Args:
            threshold_ms: Threshold for considering an operation slow
            
        Returns:
            List of bottleneck information
        """
        with self._lock:
            bottlenecks = []
            
            for key, metrics in self._metrics.items():
                if metrics.average_processing_time_ms > threshold_ms:
                    component, operation = key.split(':', 1)
                    
                    bottlenecks.append({
                        "component": component,
                        "operation": operation,
                        "average_time_ms": metrics.average_processing_time_ms,
                        "max_time_ms": metrics.max_processing_time_ms,
                        "total_operations": metrics.total_operations,
                        "error_rate": metrics.error_rate,
                        "severity": "high" if metrics.average_processing_time_ms > threshold_ms * 2 else "medium"
                    })
            
            # Sort by severity and average time
            bottlenecks.sort(key=lambda x: (x["severity"] == "high", x["average_time_ms"]), reverse=True)
            
            return bottlenecks
    
    def _update_component_metrics(self, key: str) -> None:
        """Update aggregated metrics for a component/operation."""
        if key not in self._operation_times:
            return
        
        times = self._operation_times[key]
        if not times:
            return
        
        # Calculate timing statistics
        durations = [duration for _, duration in times]
        total_time = sum(durations)
        avg_time = total_time / len(durations) if durations else 0.0
        min_time = min(durations) if durations else 0.0
        max_time = max(durations) if durations else 0.0
        
        # Calculate throughput
        now = datetime.now()
        last_update = self._last_update[key]
        time_diff = (now - last_update).total_seconds()
        
        ops_per_sec = len(times) / time_diff if time_diff > 0 else 0.0
        bytes_per_sec = self._bytes_processed[key] / time_diff if time_diff > 0 else 0.0
        
        # Calculate error rate
        total_ops = self._operation_counts[key]
        failed_ops = self._failure_counts[key]
        error_rate = failed_ops / total_ops if total_ops > 0 else 0.0
        
        # Create or update metrics
        self._metrics[key] = PerformanceMetrics(
            name=key,
            timestamp=now,
            total_operations=total_ops,
            successful_operations=self._success_counts[key],
            failed_operations=failed_ops,
            total_processing_time_ms=total_time,
            average_processing_time_ms=avg_time,
            min_processing_time_ms=min_time,
            max_processing_time_ms=max_time,
            operations_per_second=ops_per_sec,
            bytes_processed=self._bytes_processed[key],
            bytes_per_second=bytes_per_sec,
            error_rate=error_rate,
            consecutive_failures=0  # TODO: Track consecutive failures
        )
    
    async def _update_metrics_periodically(self) -> None:
        """Background task to update metrics periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.update_interval.total_seconds())
                
                with self._lock:
                    # Update all component metrics
                    for key in list(self._operation_times.keys()):
                        self._update_component_metrics(key)
                
                logger.debug("Updated performance metrics")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error updating performance metrics: {e}")


# Global performance monitor instance
_global_performance_monitor: Optional[PerformanceMonitor] = None


def get_global_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _global_performance_monitor
    if _global_performance_monitor is None:
        _global_performance_monitor = PerformanceMonitor()
    return _global_performance_monitor


def set_global_performance_monitor(monitor: PerformanceMonitor) -> None:
    """Set the global performance monitor instance."""
    global _global_performance_monitor
    _global_performance_monitor = monitor


# Convenience functions for common performance tracking
def record_processing_time(component: str, operation: str, duration_ms: float, success: bool = True) -> None:
    """Record processing time for an operation."""
    get_global_performance_monitor().record_operation(
        component=component,
        operation=operation,
        duration_ms=duration_ms,
        success=success
    )


def record_bytes_processed(component: str, operation: str, bytes_count: int) -> None:
    """Record bytes processed by an operation."""
    get_global_performance_monitor().record_operation(
        component=component,
        operation=operation,
        duration_ms=0.0,
        success=True,
        bytes_processed=bytes_count
    )


def time_operation(component: str, operation: str):
    """
    Context manager for timing operations.
    
    Usage:
        with time_operation('file_system', 'process_logs'):
            # operation code here
            pass
    """
    return OperationTimer(component, operation)


class OperationTimer:
    """Context manager for timing operations."""
    
    def __init__(self, component: str, operation: str):
        self.component = component
        self.operation = operation
        self.start_time = None
        self.success = True
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration_ms = (time.time() - self.start_time) * 1000
            self.success = exc_type is None
            
            record_processing_time(
                component=self.component,
                operation=self.operation,
                duration_ms=duration_ms,
                success=self.success
            )
