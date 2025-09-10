# gemini_sre_agent/source_control/error_handling/metrics_integration.py

"""
Metrics integration for error handling and resilience patterns.

This module provides comprehensive metrics collection for monitoring
error handling, circuit breaker states, retry patterns, and overall
system health.
"""

import logging
from typing import Any, Dict, Optional

from ..metrics.core import MetricType
from ..metrics.collectors import MetricsCollector
from .core import ErrorType, CircuitState


class ErrorHandlingMetrics:
    """Metrics collector for error handling and resilience patterns."""

    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        """Initialize error handling metrics."""
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.logger = logging.getLogger("ErrorHandlingMetrics")

    async def record_error(
        self,
        error_type: ErrorType,
        operation_name: str,
        provider: str,
        is_retryable: bool,
        retry_count: int = 0,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an error occurrence."""
        try:
            tags = {
                "error_type": error_type.value,
                "operation": operation_name,
                "provider": provider,
                "is_retryable": str(is_retryable),
            }

            # Record error count
            await self.metrics_collector.record_metric(
                name="source_control_errors_total",
                value=1.0,
                metric_type=MetricType.COUNTER,
                tags=tags,
                unit="errors",
            )

            # Record retry count if applicable
            if retry_count > 0:
                await self.metrics_collector.record_metric(
                    name="source_control_retry_attempts",
                    value=float(retry_count),
                    metric_type=MetricType.COUNTER,
                    tags=tags,
                    unit="attempts",
                )

            # Record error details if provided
            if error_details:
                await self.metrics_collector.record_metric(
                    name="source_control_error_details",
                    value=1.0,
                    metric_type=MetricType.COUNTER,
                    tags={**tags, "details": str(error_details)},
                    unit="errors",
                )

        except Exception as e:
            self.logger.error(f"Failed to record error metrics: {e}")

    async def record_circuit_breaker_state_change(
        self,
        circuit_name: str,
        old_state: CircuitState,
        new_state: CircuitState,
        operation_type: str,
    ) -> None:
        """Record circuit breaker state changes."""
        try:
            tags = {
                "circuit_name": circuit_name,
                "operation_type": operation_type,
                "old_state": old_state.value,
                "new_state": new_state.value,
            }

            await self.metrics_collector.record_metric(
                name="source_control_circuit_breaker_state_changes",
                value=1.0,
                metric_type=MetricType.COUNTER,
                tags=tags,
                unit="changes",
            )

            # Record current state as a gauge
            state_value = 1.0 if new_state == CircuitState.OPEN else 0.0
            await self.metrics_collector.record_metric(
                name="source_control_circuit_breaker_open",
                value=state_value,
                metric_type=MetricType.GAUGE,
                tags={**tags, "state": new_state.value},
                unit="boolean",
            )

        except Exception as e:
            self.logger.error(f"Failed to record circuit breaker metrics: {e}")

    async def record_retry_attempt(
        self,
        operation_name: str,
        provider: str,
        attempt_number: int,
        delay_seconds: float,
        error_type: ErrorType,
    ) -> None:
        """Record a retry attempt."""
        try:
            tags = {
                "operation": operation_name,
                "provider": provider,
                "error_type": error_type.value,
                "attempt": str(attempt_number),
            }

            await self.metrics_collector.record_metric(
                name="source_control_retry_attempts",
                value=1.0,
                metric_type=MetricType.COUNTER,
                tags=tags,
                unit="attempts",
            )

            await self.metrics_collector.record_metric(
                name="source_control_retry_delay_seconds",
                value=delay_seconds,
                metric_type=MetricType.HISTOGRAM,
                tags=tags,
                unit="seconds",
            )

        except Exception as e:
            self.logger.error(f"Failed to record retry metrics: {e}")

    async def record_operation_success(
        self,
        operation_name: str,
        provider: str,
        duration_seconds: float,
        retry_count: int = 0,
    ) -> None:
        """Record a successful operation."""
        try:
            tags = {
                "operation": operation_name,
                "provider": provider,
                "status": "success",
            }

            await self.metrics_collector.record_metric(
                name="source_control_operations_total",
                value=1.0,
                metric_type=MetricType.COUNTER,
                tags=tags,
                unit="operations",
            )

            await self.metrics_collector.record_metric(
                name="source_control_operation_duration_seconds",
                value=duration_seconds,
                metric_type=MetricType.HISTOGRAM,
                tags=tags,
                unit="seconds",
            )

            if retry_count > 0:
                await self.metrics_collector.record_metric(
                    name="source_control_operations_with_retries",
                    value=1.0,
                    metric_type=MetricType.COUNTER,
                    tags={**tags, "retry_count": str(retry_count)},
                    unit="operations",
                )

        except Exception as e:
            self.logger.error(f"Failed to record success metrics: {e}")

    async def record_operation_failure(
        self,
        operation_name: str,
        provider: str,
        duration_seconds: float,
        error_type: ErrorType,
        retry_count: int = 0,
    ) -> None:
        """Record a failed operation."""
        try:
            tags = {
                "operation": operation_name,
                "provider": provider,
                "status": "failure",
                "error_type": error_type.value,
            }

            await self.metrics_collector.record_metric(
                name="source_control_operations_total",
                value=1.0,
                metric_type=MetricType.COUNTER,
                tags=tags,
                unit="operations",
            )

            await self.metrics_collector.record_metric(
                name="source_control_operation_duration_seconds",
                value=duration_seconds,
                metric_type=MetricType.HISTOGRAM,
                tags=tags,
                unit="seconds",
            )

            if retry_count > 0:
                await self.metrics_collector.record_metric(
                    name="source_control_operations_with_retries",
                    value=1.0,
                    metric_type=MetricType.COUNTER,
                    tags={**tags, "retry_count": str(retry_count)},
                    unit="operations",
                )

        except Exception as e:
            self.logger.error(f"Failed to record failure metrics: {e}")

    async def record_circuit_breaker_stats(
        self,
        circuit_name: str,
        operation_type: str,
        state: CircuitState,
        failure_count: int,
        success_count: int,
        total_requests: int,
        failure_rate: float,
    ) -> None:
        """Record circuit breaker statistics."""
        try:
            tags = {
                "circuit_name": circuit_name,
                "operation_type": operation_type,
                "state": state.value,
            }

            await self.metrics_collector.record_metric(
                name="source_control_circuit_breaker_failures",
                value=float(failure_count),
                metric_type=MetricType.GAUGE,
                tags=tags,
                unit="failures",
            )

            await self.metrics_collector.record_metric(
                name="source_control_circuit_breaker_successes",
                value=float(success_count),
                metric_type=MetricType.GAUGE,
                tags=tags,
                unit="successes",
            )

            await self.metrics_collector.record_metric(
                name="source_control_circuit_breaker_requests",
                value=float(total_requests),
                metric_type=MetricType.GAUGE,
                tags=tags,
                unit="requests",
            )

            await self.metrics_collector.record_metric(
                name="source_control_circuit_breaker_failure_rate",
                value=failure_rate,
                metric_type=MetricType.GAUGE,
                tags=tags,
                unit="ratio",
            )

        except Exception as e:
            self.logger.error(f"Failed to record circuit breaker stats: {e}")

    async def record_health_check(
        self,
        provider: str,
        is_healthy: bool,
        response_time_ms: float,
        error_message: Optional[str] = None,
    ) -> None:
        """Record health check results."""
        try:
            tags = {
                "provider": provider,
                "status": "healthy" if is_healthy else "unhealthy",
            }

            await self.metrics_collector.record_metric(
                name="source_control_health_checks",
                value=1.0,
                metric_type=MetricType.COUNTER,
                tags=tags,
                unit="checks",
            )

            await self.metrics_collector.record_metric(
                name="source_control_health_check_duration_ms",
                value=response_time_ms,
                metric_type=MetricType.HISTOGRAM,
                tags=tags,
                unit="milliseconds",
            )

            if error_message:
                await self.metrics_collector.record_metric(
                    name="source_control_health_check_errors",
                    value=1.0,
                    metric_type=MetricType.COUNTER,
                    tags={**tags, "error": error_message},
                    unit="errors",
                )

        except Exception as e:
            self.logger.error(f"Failed to record health check metrics: {e}")

    def get_error_rate_by_provider(self, provider: str, time_window_minutes: int = 5) -> float:
        """Get error rate for a specific provider over a time window."""
        try:
            # This would need to be implemented based on the metrics collector's query capabilities
            # For now, return 0.0 as a placeholder
            return 0.0
        except Exception as e:
            self.logger.error(f"Failed to get error rate for provider {provider}: {e}")
            return 0.0

    def get_circuit_breaker_health(self, circuit_name: str) -> Dict[str, Any]:
        """Get health information for a specific circuit breaker."""
        try:
            # This would need to be implemented based on the metrics collector's query capabilities
            # For now, return empty dict as a placeholder
            return {}
        except Exception as e:
            self.logger.error(f"Failed to get circuit breaker health for {circuit_name}: {e}")
            return {}

    def get_operation_metrics(
        self, operation_name: str, provider: str, time_window_minutes: int = 5
    ) -> Dict[str, Any]:
        """Get metrics for a specific operation."""
        try:
            # This would need to be implemented based on the metrics collector's query capabilities
            # For now, return empty dict as a placeholder
            return {}
        except Exception as e:
            self.logger.error(f"Failed to get operation metrics for {operation_name}: {e}")
            return {}
