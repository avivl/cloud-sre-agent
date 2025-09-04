"""
Health checking and status monitoring system for the log ingestion system.

Provides comprehensive health monitoring including:
- Component health checks (adapters, queues, managers)
- System health aggregation
- Health status reporting
- Dependency health tracking
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ComponentHealth:
    """Health information for a component."""

    name: str
    status: HealthStatus
    last_check: datetime
    last_success: Optional[datetime] = None
    consecutive_failures: int = 0
    total_checks: int = 0
    success_rate: float = 0.0
    average_response_time_ms: float = 0.0
    error_message: Optional[str] = None


class HealthChecker:
    """
    Comprehensive health checking system for the log ingestion system.

    Monitors the health of all components including:
    - Log adapters (file system, GCP, AWS, Kubernetes)
    - Queue systems (memory, file-based)
    - Log manager and orchestration
    - System resources (memory, disk, network)
    """

    def __init__(self, check_interval: timedelta = timedelta(seconds=30)):
        """
        Initialize the health checker.

        Args:
            check_interval: How often to run health checks
        """
        self.check_interval = check_interval
        self._health_checks: Dict[str, Callable[[], Awaitable[HealthCheckResult]]] = {}
        self._component_health: Dict[str, ComponentHealth] = {}
        self._running = False
        self._check_task: Optional[asyncio.Task] = None

        logger.info("HealthChecker initialized")

    async def start(self) -> None:
        """Start the health checker."""
        if self._running:
            return

        self._running = True
        self._check_task = asyncio.create_task(self._run_health_checks())
        logger.info("HealthChecker started")

    async def stop(self) -> None:
        """Stop the health checker."""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        logger.info("HealthChecker stopped")

    def register_health_check(
        self, name: str, check_func: Callable[[], Awaitable[HealthCheckResult]]
    ) -> None:
        """
        Register a health check function.

        Args:
            name: Name of the health check
            check_func: Async function that returns HealthCheckResult
        """
        self._health_checks[name] = check_func
        self._component_health[name] = ComponentHealth(
            name=name, status=HealthStatus.UNKNOWN, last_check=datetime.now()
        )
        logger.info(f"Registered health check: {name}")

    def unregister_health_check(self, name: str) -> None:
        """Unregister a health check."""
        if name in self._health_checks:
            del self._health_checks[name]
        if name in self._component_health:
            del self._component_health[name]
        logger.info(f"Unregistered health check: {name}")

    async def run_health_check(self, name: str) -> Optional[HealthCheckResult]:
        """
        Run a specific health check.

        Args:
            name: Name of the health check to run

        Returns:
            HealthCheckResult or None if check not found
        """
        if name not in self._health_checks:
            return None

        check_func = self._health_checks[name]
        start_time = time.time()

        try:
            result = await check_func()
            duration_ms = (time.time() - start_time) * 1000
            result.duration_ms = duration_ms

            # Update component health
            await self._update_component_health(name, result)

            return result

        except Exception as e:
            logger.error(f"Health check {name} failed with exception: {e}")

            # Create failure result
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
            )

            await self._update_component_health(name, result)
            return result

    async def run_all_health_checks(self) -> Dict[str, HealthCheckResult]:
        """
        Run all registered health checks.

        Returns:
            Dictionary mapping check names to results
        """
        results = {}

        # Run checks concurrently
        tasks = {
            name: asyncio.create_task(self.run_health_check(name))
            for name in self._health_checks.keys()
        }

        for name, task in tasks.items():
            try:
                result = await task
                if result:
                    results[name] = result
            except Exception as e:
                logger.error(f"Failed to run health check {name}: {e}")
                results[name] = HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check execution failed: {str(e)}",
                )

        return results

    def get_component_health(self, name: str) -> Optional[ComponentHealth]:
        """Get health information for a specific component."""
        return self._component_health.get(name)

    def get_all_component_health(self) -> Dict[str, ComponentHealth]:
        """Get health information for all components."""
        return dict(self._component_health)

    def get_overall_health_status(self) -> HealthStatus:
        """
        Get the overall system health status.

        Returns:
            Overall health status based on component health
        """
        if not self._component_health:
            return HealthStatus.UNKNOWN

        statuses = [health.status for health in self._component_health.values()]

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN

    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive health summary.

        Returns:
            Dictionary with health summary information
        """
        overall_status = self.get_overall_health_status()

        summary = {
            "overall_status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "components": {
                name: {
                    "status": health.status.value,
                    "last_check": health.last_check.isoformat(),
                    "last_success": (
                        health.last_success.isoformat() if health.last_success else None
                    ),
                    "consecutive_failures": health.consecutive_failures,
                    "total_checks": health.total_checks,
                    "success_rate": health.success_rate,
                    "average_response_time_ms": health.average_response_time_ms,
                    "error_message": health.error_message,
                }
                for name, health in self._component_health.items()
            },
            "statistics": {
                "total_components": len(self._component_health),
                "healthy_components": sum(
                    1
                    for h in self._component_health.values()
                    if h.status == HealthStatus.HEALTHY
                ),
                "degraded_components": sum(
                    1
                    for h in self._component_health.values()
                    if h.status == HealthStatus.DEGRADED
                ),
                "unhealthy_components": sum(
                    1
                    for h in self._component_health.values()
                    if h.status == HealthStatus.UNHEALTHY
                ),
                "unknown_components": sum(
                    1
                    for h in self._component_health.values()
                    if h.status == HealthStatus.UNKNOWN
                ),
            },
        }

        return summary

    async def _run_health_checks(self) -> None:
        """Background task to run health checks periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval.total_seconds())
                await self.run_all_health_checks()
                logger.debug("Completed periodic health checks")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic health checks: {e}")

    async def _update_component_health(
        self, name: str, result: HealthCheckResult
    ) -> None:
        """Update component health based on check result."""
        if name not in self._component_health:
            return

        health = self._component_health[name]
        health.last_check = result.timestamp
        health.total_checks += 1

        if result.status == HealthStatus.HEALTHY:
            health.status = HealthStatus.HEALTHY
            health.last_success = result.timestamp
            health.consecutive_failures = 0
            health.error_message = None
        else:
            health.consecutive_failures += 1
            health.error_message = result.message

            # Determine status based on consecutive failures
            if health.consecutive_failures >= 3:
                health.status = HealthStatus.UNHEALTHY
            elif health.consecutive_failures >= 1:
                health.status = HealthStatus.DEGRADED

        # Update success rate
        if health.total_checks > 0:
            successful_checks = health.total_checks - health.consecutive_failures
            health.success_rate = successful_checks / health.total_checks

        # Update average response time
        if result.duration_ms > 0:
            if health.average_response_time_ms == 0:
                health.average_response_time_ms = result.duration_ms
            else:
                # Simple moving average
                health.average_response_time_ms = (
                    health.average_response_time_ms * 0.9 + result.duration_ms * 0.1
                )


# Global health checker instance
_global_health_checker: Optional[HealthChecker] = None


def get_global_health_checker() -> HealthChecker:
    """Get the global health checker instance."""
    global _global_health_checker
    if _global_health_checker is None:
        _global_health_checker = HealthChecker()
    return _global_health_checker


def set_global_health_checker(health_checker: HealthChecker) -> None:
    """Set the global health checker instance."""
    global _global_health_checker
    _global_health_checker = health_checker


# Convenience functions for common health checks
async def create_adapter_health_check(adapter) -> HealthCheckResult:
    """
    Create a health check for a log adapter.

    Args:
        adapter: Log adapter instance

    Returns:
        HealthCheckResult for the adapter
    """
    try:
        health = await adapter.get_health()

        if health.is_healthy:
            return HealthCheckResult(
                name=f"adapter_{adapter.name}",
                status=HealthStatus.HEALTHY,
                message="Adapter is healthy",
                details={
                    "last_success": (
                        health.last_success.isoformat() if health.last_success else None
                    ),
                    "error_count": health.error_count,
                    "metrics": health.metrics,
                },
            )
        else:
            return HealthCheckResult(
                name=f"adapter_{adapter.name}",
                status=HealthStatus.UNHEALTHY,
                message=f"Adapter is unhealthy: {health.last_error}",
                details={
                    "last_success": (
                        health.last_success.isoformat() if health.last_success else None
                    ),
                    "error_count": health.error_count,
                    "last_error": health.last_error,
                },
            )

    except Exception as e:
        return HealthCheckResult(
            name=f"adapter_{adapter.name}",
            status=HealthStatus.UNHEALTHY,
            message=f"Health check failed: {str(e)}",
        )


async def create_queue_health_check(queue) -> HealthCheckResult:
    """
    Create a health check for a queue.

    Args:
        queue: Queue instance

    Returns:
        HealthCheckResult for the queue
    """
    try:
        size = await queue.size()
        max_size = getattr(queue, "max_size", None)

        # Determine health based on queue size
        if max_size and size > max_size * 0.9:
            status = HealthStatus.DEGRADED
            message = f"Queue is nearly full: {size}/{max_size}"
        elif max_size and size > max_size:
            status = HealthStatus.UNHEALTHY
            message = f"Queue is full: {size}/{max_size}"
        else:
            status = HealthStatus.HEALTHY
            message = f"Queue is healthy: {size} items"

        return HealthCheckResult(
            name=f"queue_{queue.name}",
            status=status,
            message=message,
            details={
                "size": size,
                "max_size": max_size,
                "utilization": size / max_size if max_size else 0,
            },
        )

    except Exception as e:
        return HealthCheckResult(
            name=f"queue_{queue.name}",
            status=HealthStatus.UNHEALTHY,
            message=f"Queue health check failed: {str(e)}",
        )


async def create_system_health_check() -> HealthCheckResult:
    """
    Create a system-level health check.

    Returns:
        HealthCheckResult for system health
    """
    try:
        import psutil

        # Check memory usage
        memory = psutil.virtual_memory()
        memory_usage_percent = memory.percent

        # Check disk usage
        disk = psutil.disk_usage("/")
        disk_usage_percent = (disk.used / disk.total) * 100

        # Determine overall system health
        if memory_usage_percent > 90 or disk_usage_percent > 90:
            status = HealthStatus.UNHEALTHY
            message = f"System resources critically low: Memory {memory_usage_percent:.1f}%, Disk {disk_usage_percent:.1f}%"
        elif memory_usage_percent > 80 or disk_usage_percent > 80:
            status = HealthStatus.DEGRADED
            message = f"System resources high: Memory {memory_usage_percent:.1f}%, Disk {disk_usage_percent:.1f}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"System resources normal: Memory {memory_usage_percent:.1f}%, Disk {disk_usage_percent:.1f}%"

        return HealthCheckResult(
            name="system",
            status=status,
            message=message,
            details={
                "memory_usage_percent": memory_usage_percent,
                "disk_usage_percent": disk_usage_percent,
                "cpu_count": psutil.cpu_count(),
                "load_average": (
                    psutil.getloadavg() if hasattr(psutil, "getloadavg") else None
                ),
            },
        )

    except ImportError:
        return HealthCheckResult(
            name="system",
            status=HealthStatus.UNKNOWN,
            message="System health check unavailable (psutil not installed)",
        )
    except Exception as e:
        return HealthCheckResult(
            name="system",
            status=HealthStatus.UNHEALTHY,
            message=f"System health check failed: {str(e)}",
        )
