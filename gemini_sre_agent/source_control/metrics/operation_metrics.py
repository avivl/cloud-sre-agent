"""
Operation-specific metrics collection.

This module provides specialized metrics collection for source control operations,
remediation results, and health checks.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

from .core import MetricType
from ..models import OperationResult, ProviderHealth, RemediationResult

if TYPE_CHECKING:
    from .collectors import MetricsCollector


class OperationMetrics:
    """Metrics collector specifically for source control operations."""

    def __init__(self, collector: "MetricsCollector"):
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
