# gemini_sre_agent/source_control/monitoring.py

"""
Comprehensive monitoring and health check system for source control providers.

This module provides advanced monitoring capabilities including metrics collection,
health checks, performance monitoring, and alerting for source control operations.
"""

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .base import SourceControlProvider


class MetricType(Enum):
    """Types of metrics that can be collected."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class Metric:
    """A single metric measurement."""

    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    unit: Optional[str] = None


@dataclass
class HealthCheck:
    """A health check result."""

    name: str
    status: HealthStatus
    message: str
    timestamp: datetime
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """An alert condition."""

    name: str
    severity: str  # "critical", "warning", "info"
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """Collects and stores metrics from source control operations."""

    def __init__(self, max_metrics: int = 10000):
        self.metrics: deque = deque(maxlen=max_metrics)
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self.logger = logging.getLogger("MetricsCollector")

    def record_metric(self, metric: Metric) -> None:
        """Record a metric."""
        self.metrics.append(metric)

        if metric.metric_type == MetricType.COUNTER:
            self.counters[metric.name] += metric.value
        elif metric.metric_type == MetricType.GAUGE:
            self.gauges[metric.name] = metric.value
        elif metric.metric_type == MetricType.HISTOGRAM:
            self.histograms[metric.name].append(metric.value)
        elif metric.metric_type == MetricType.TIMER:
            self.timers[metric.name].append(metric.value)

    def get_counter(self, name: str) -> float:
        """Get current counter value."""
        return self.counters.get(name, 0.0)

    def get_gauge(self, name: str) -> float:
        """Get current gauge value."""
        return self.gauges.get(name, 0.0)

    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """Get histogram statistics."""
        values = self.histograms.get(name, [])
        if not values:
            return {"count": 0, "min": 0, "max": 0, "mean": 0, "p95": 0, "p99": 0}

        sorted_values = sorted(values)
        count = len(values)
        return {
            "count": count,
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / count,
            "p95": sorted_values[int(count * 0.95)] if count > 0 else 0,
            "p99": sorted_values[int(count * 0.99)] if count > 0 else 0,
        }

    def get_timer_stats(self, name: str) -> Dict[str, float]:
        """Get timer statistics."""
        return self.get_histogram_stats(name)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {
                name: self.get_histogram_stats(name) for name in self.histograms
            },
            "timers": {name: self.get_timer_stats(name) for name in self.timers},
            "total_metrics": len(self.metrics),
        }


class HealthChecker:
    """Performs comprehensive health checks on source control providers."""

    def __init__(self):
        self.health_checks: Dict[
            str, Callable[[SourceControlProvider], Awaitable[HealthCheck]]
        ] = {}
        self.logger = logging.getLogger("HealthChecker")

    def register_health_check(
        self,
        name: str,
        check_func: Callable[[SourceControlProvider], Awaitable[HealthCheck]],
    ):
        """Register a custom health check."""
        self.health_checks[name] = check_func

    async def run_health_checks(
        self, provider: SourceControlProvider
    ) -> List[HealthCheck]:
        """Run all registered health checks on a provider."""
        results = []

        # Basic connectivity check
        connectivity_check = await self._check_connectivity(provider)
        results.append(connectivity_check)

        # Credentials check
        credentials_check = await self._check_credentials(provider)
        results.append(credentials_check)

        # Performance check
        performance_check = await self._check_performance(provider)
        results.append(performance_check)

        # Custom checks
        for name, check_func in self.health_checks.items():
            try:
                check_result = await check_func(provider)
                results.append(check_result)
            except Exception as e:
                self.logger.error(f"Health check {name} failed: {e}")
                results.append(
                    HealthCheck(
                        name=name,
                        status=HealthStatus.UNKNOWN,
                        message=f"Check failed: {e}",
                        timestamp=datetime.now(),
                        duration_ms=0.0,
                    )
                )

        return results

    async def _check_connectivity(self, provider: SourceControlProvider) -> HealthCheck:
        """Check basic connectivity to the provider."""
        start_time = time.time()
        try:
            is_connected = await provider.test_connection()
            duration_ms = (time.time() - start_time) * 1000

            return HealthCheck(
                name="connectivity",
                status=HealthStatus.HEALTHY if is_connected else HealthStatus.UNHEALTHY,
                message=(
                    "Connection successful" if is_connected else "Connection failed"
                ),
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                details={"connected": is_connected},
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                name="connectivity",
                status=HealthStatus.UNHEALTHY,
                message=f"Connection error: {e}",
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                details={"error": str(e)},
            )

    async def _check_credentials(self, provider: SourceControlProvider) -> HealthCheck:
        """Check credential validity."""
        start_time = time.time()
        try:
            are_valid = await provider.validate_credentials()
            duration_ms = (time.time() - start_time) * 1000

            return HealthCheck(
                name="credentials",
                status=HealthStatus.HEALTHY if are_valid else HealthStatus.UNHEALTHY,
                message="Credentials valid" if are_valid else "Credentials invalid",
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                details={"valid": are_valid},
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                name="credentials",
                status=HealthStatus.UNHEALTHY,
                message=f"Credential check error: {e}",
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                details={"error": str(e)},
            )

    async def _check_performance(self, provider: SourceControlProvider) -> HealthCheck:
        """Check provider performance."""
        start_time = time.time()
        try:
            # Test a simple operation
            health_status = await provider.get_health_status()
            duration_ms = (time.time() - start_time) * 1000

            # Determine status based on response time
            if duration_ms < 1000:
                status = HealthStatus.HEALTHY
            elif duration_ms < 3000:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY

            return HealthCheck(
                name="performance",
                status=status,
                message=f"Response time: {duration_ms:.2f}ms",
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                details={
                    "response_time_ms": duration_ms,
                    "provider_healthy": health_status.status == "healthy",
                },
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                name="performance",
                status=HealthStatus.UNHEALTHY,
                message=f"Performance check error: {e}",
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                details={"error": str(e)},
            )


class AlertManager:
    """Manages alerts and notifications."""

    def __init__(self):
        self.alerts: List[Alert] = []
        self.alert_rules: Dict[str, Callable[[Dict[str, Any]], bool]] = {}
        self.notification_handlers: List[Callable[[Alert], None]] = []
        self.logger = logging.getLogger("AlertManager")

    def add_alert_rule(self, name: str, rule_func: Callable[[Dict[str, Any]], bool]):
        """Add an alert rule."""
        self.alert_rules[name] = rule_func

    def add_notification_handler(self, handler: Callable[[Alert], None]):
        """Add a notification handler."""
        self.notification_handlers.append(handler)

    def check_alerts(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Check for alert conditions based on metrics."""
        new_alerts = []

        for rule_name, rule_func in self.alert_rules.items():
            try:
                if rule_func(metrics):
                    alert = Alert(
                        name=rule_name,
                        severity="warning",
                        message=f"Alert condition met for {rule_name}",
                        timestamp=datetime.now(),
                        metadata=metrics,
                    )
                    new_alerts.append(alert)
                    self.alerts.append(alert)
            except Exception as e:
                self.logger.error(f"Alert rule {rule_name} failed: {e}")

        # Send notifications for new alerts
        for alert in new_alerts:
            for handler in self.notification_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    self.logger.error(f"Notification handler failed: {e}")

        return new_alerts

    def resolve_alert(self, alert_name: str, resolved_at: Optional[datetime] = None):
        """Mark an alert as resolved."""
        for alert in self.alerts:
            if alert.name == alert_name and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = resolved_at or datetime.now()
                break

    def get_active_alerts(self) -> List[Alert]:
        """Get all active (unresolved) alerts."""
        return [alert for alert in self.alerts if not alert.resolved]


class MonitoringManager:
    """Main monitoring manager that coordinates all monitoring activities."""

    def __init__(
        self,
        enable_metrics: bool = True,
        enable_health_checks: bool = True,
        enable_alerts: bool = True,
    ):
        self.metrics_collector = MetricsCollector() if enable_metrics else None
        self.health_checker = HealthChecker() if enable_health_checks else None
        self.alert_manager = AlertManager() if enable_alerts else None
        self.logger = logging.getLogger("MonitoringManager")

        # Setup default alert rules
        if self.alert_manager:
            self._setup_default_alert_rules()

    def _setup_default_alert_rules(self):
        """Setup default alert rules."""
        if not self.alert_manager:
            return

        # High error rate alert
        self.alert_manager.add_alert_rule(
            "high_error_rate", lambda metrics: metrics.get("error_rate", 0) > 0.1
        )

        # High response time alert
        self.alert_manager.add_alert_rule(
            "high_response_time",
            lambda metrics: metrics.get("avg_response_time_ms", 0) > 5000,
        )

        # Low success rate alert
        self.alert_manager.add_alert_rule(
            "low_success_rate", lambda metrics: metrics.get("success_rate", 1) < 0.9
        )

    async def monitor_operation(
        self,
        operation_name: str,
        operation_func: Callable[[], Awaitable[Any]],
        provider_name: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Monitor a source control operation."""
        if not self.metrics_collector:
            return await operation_func()

        start_time = time.time()
        success = False
        error = None

        try:
            result = await operation_func()
            success = True
            return result
        except Exception as e:
            error = e
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000

            # Record metrics
            operation_tags = tags or {}
            operation_tags.update(
                {"provider": provider_name, "operation": operation_name}
            )

            # Record timer metric
            self.metrics_collector.record_metric(
                Metric(
                    name="operation_duration",
                    value=duration_ms,
                    metric_type=MetricType.TIMER,
                    timestamp=datetime.now(),
                    tags=operation_tags,
                    unit="ms",
                )
            )

            # Record success/failure counter
            status = "success" if success else "failure"
            self.metrics_collector.record_metric(
                Metric(
                    name="operation_count",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    timestamp=datetime.now(),
                    tags={**operation_tags, "status": status},
                )
            )

            if error:
                self.metrics_collector.record_metric(
                    Metric(
                        name="operation_errors",
                        value=1,
                        metric_type=MetricType.COUNTER,
                        timestamp=datetime.now(),
                        tags={**operation_tags, "error_type": type(error).__name__},
                    )
                )

    async def run_health_checks(
        self, providers: List[SourceControlProvider]
    ) -> Dict[str, List[HealthCheck]]:
        """Run health checks on multiple providers."""
        if not self.health_checker:
            return {}

        results = {}
        for provider in providers:
            provider_name = provider.__class__.__name__
            try:
                health_checks = await self.health_checker.run_health_checks(provider)
                results[provider_name] = health_checks
            except Exception as e:
                self.logger.error(f"Health check failed for {provider_name}: {e}")
                results[provider_name] = [
                    HealthCheck(
                        name="health_check_error",
                        status=HealthStatus.UNKNOWN,
                        message=f"Health check failed: {e}",
                        timestamp=datetime.now(),
                        duration_ms=0.0,
                    )
                ]

        return results

    async def check_alerts(self) -> List[Alert]:
        """Check for alert conditions."""
        if not self.alert_manager or not self.metrics_collector:
            return []

        metrics_summary = self.metrics_collector.get_metrics_summary()

        # Calculate derived metrics
        derived_metrics = self._calculate_derived_metrics(metrics_summary)

        # Check for alerts
        return self.alert_manager.check_alerts(derived_metrics)

    def _calculate_derived_metrics(
        self, metrics_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate derived metrics from raw metrics."""
        derived = {}

        # Calculate success rate
        total_operations = 0
        successful_operations = 0

        for counter_name, value in metrics_summary.get("counters", {}).items():
            if counter_name == "operation_count":
                total_operations += value
            elif (
                counter_name.startswith("operation_count") and "success" in counter_name
            ):
                successful_operations += value

        if total_operations > 0:
            derived["success_rate"] = successful_operations / total_operations
            derived["error_rate"] = 1 - derived["success_rate"]

        # Calculate average response time
        timer_stats = metrics_summary.get("timers", {})
        if "operation_duration" in timer_stats:
            derived["avg_response_time_ms"] = timer_stats["operation_duration"].get(
                "mean", 0
            )

        return derived

    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get a comprehensive monitoring summary."""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "metrics_enabled": self.metrics_collector is not None,
            "health_checks_enabled": self.health_checker is not None,
            "alerts_enabled": self.alert_manager is not None,
        }

        if self.metrics_collector:
            summary["metrics"] = self.metrics_collector.get_metrics_summary()

        if self.alert_manager:
            summary["active_alerts"] = len(self.alert_manager.get_active_alerts())
            summary["total_alerts"] = len(self.alert_manager.alerts)

        return summary

    def add_notification_handler(self, handler: Callable[[Alert], None]):
        """Add a notification handler for alerts."""
        if self.alert_manager:
            self.alert_manager.add_notification_handler(handler)

    def add_health_check(
        self,
        name: str,
        check_func: Callable[[SourceControlProvider], Awaitable[HealthCheck]],
    ):
        """Add a custom health check."""
        if self.health_checker:
            self.health_checker.register_health_check(name, check_func)
