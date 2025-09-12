# gemini_sre_agent/llm/service_metrics.py

"""
Service Metrics Module

This module provides comprehensive metrics collection, analysis, and reporting
for service performance monitoring and optimization.
"""

import logging
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class MetricType(Enum):
    """Types of metrics that can be collected."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"


class MetricAggregation(Enum):
    """Aggregation methods for metrics."""

    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    PERCENTILE = "percentile"


@dataclass
class MetricPoint:
    """A single metric data point."""

    timestamp: datetime
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """A series of metric data points."""

    name: str
    metric_type: MetricType
    points: deque = field(default_factory=lambda: deque(maxlen=1000))
    aggregation_window: timedelta = field(default_factory=lambda: timedelta(minutes=5))

    def add_point(self, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a new data point to the series."""
        point = MetricPoint(timestamp=datetime.now(), value=value, tags=tags or {})
        self.points.append(point)

    def get_aggregated_value(
        self, aggregation: MetricAggregation, window: Optional[timedelta] = None
    ) -> Optional[float]:
        """Get aggregated value for the specified time window."""
        if not self.points:
            return None

        window = window or self.aggregation_window
        cutoff_time = datetime.now() - window

        # Filter points within the time window
        recent_points = [
            point for point in self.points if point.timestamp >= cutoff_time
        ]

        if not recent_points:
            return None

        values = [point.value for point in recent_points]

        if aggregation == MetricAggregation.SUM:
            return sum(values)
        elif aggregation == MetricAggregation.AVG:
            return statistics.mean(values)
        elif aggregation == MetricAggregation.MIN:
            return min(values)
        elif aggregation == MetricAggregation.MAX:
            return max(values)
        elif aggregation == MetricAggregation.COUNT:
            return len(values)
        elif aggregation == MetricAggregation.PERCENTILE:
            return statistics.median(values)
        else:
            return statistics.mean(values)


@dataclass
class ServicePerformanceMetrics:
    """Comprehensive performance metrics for a service."""

    service_id: str
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_response_time: float = 0.0
    min_response_time: float = float("inf")
    max_response_time: float = 0.0
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    error_rate: float = 0.0
    throughput: float = 0.0  # requests per second
    availability: float = 100.0
    last_request_time: Optional[datetime] = None
    first_request_time: Optional[datetime] = None
    health_score: float = 1.0

    def update_with_request(
        self, success: bool, response_time: float, timestamp: Optional[datetime] = None
    ) -> None:
        """Update metrics with a new request."""
        if timestamp is None:
            timestamp = datetime.now()

        self.request_count += 1
        if success:
            self.success_count += 1
        else:
            self.error_count += 1

        # Update response time metrics
        self.total_response_time += response_time
        self.min_response_time = min(self.min_response_time, response_time)
        self.max_response_time = max(self.max_response_time, response_time)

        if self.request_count == 1:
            self.avg_response_time = response_time
            self.first_request_time = timestamp
        else:
            self.avg_response_time = self.total_response_time / self.request_count

        self.last_request_time = timestamp

        # Calculate derived metrics
        self.error_rate = (
            self.error_count / self.request_count if self.request_count > 0 else 0.0
        )

        # Calculate throughput (requests per second over last minute)
        if self.first_request_time:
            time_span = (timestamp - self.first_request_time).total_seconds()
            if time_span > 0:
                self.throughput = self.request_count / time_span

        # Calculate availability
        self.availability = (
            (self.success_count / self.request_count * 100)
            if self.request_count > 0
            else 100.0
        )

        # Calculate health score (0-1, higher is better)
        error_penalty = self.error_rate * 0.5
        response_penalty = min(
            0.3, self.avg_response_time / 10000.0
        )  # Penalty for slow responses
        self.health_score = max(0.0, 1.0 - error_penalty - response_penalty)

    def get_percentile_response_time(self, percentile: float) -> float:
        """Calculate percentile response time (requires storing individual response times)."""
        # This is a simplified implementation
        # In a real system, you'd store individual response times
        if percentile == 95:
            return self.p95_response_time
        elif percentile == 99:
            return self.p99_response_time
        else:
            return self.avg_response_time


@dataclass
class ServiceAlert:
    """Alert configuration and state for a service."""

    service_id: str
    metric_name: str
    threshold: float
    operator: str  # '>', '<', '>=', '<=', '==', '!='
    duration: timedelta
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    is_active: bool = False
    triggered_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    def check_condition(self, value: float) -> bool:
        """Check if the alert condition is met."""
        if self.operator == ">":
            return value > self.threshold
        elif self.operator == "<":
            return value < self.threshold
        elif self.operator == ">=":
            return value >= self.threshold
        elif self.operator == "<=":
            return value <= self.threshold
        elif self.operator == "==":
            return value == self.threshold
        elif self.operator == "!=":
            return value != self.threshold
        else:
            return False


class MetricsCollector:
    """Collects and stores metrics for services."""

    def __init__(self, max_series_length: int = 1000):
        self.metrics: Dict[str, ServicePerformanceMetrics] = {}
        self.metric_series: Dict[str, MetricSeries] = {}
        self.max_series_length = max_series_length
        self.logger = logging.getLogger(__name__)

    def record_request(
        self,
        service_id: str,
        success: bool,
        response_time: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record a service request."""
        if service_id not in self.metrics:
            self.metrics[service_id] = ServicePerformanceMetrics(service_id=service_id)

        self.metrics[service_id].update_with_request(success, response_time, timestamp)

        # Record in time series
        self._record_metric_point(
            f"{service_id}.response_time", response_time, {"success": str(success)}
        )

        self._record_metric_point(
            f"{service_id}.request_count", 1, {"success": str(success)}
        )

    def _record_metric_point(
        self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a metric point in the time series."""
        if metric_name not in self.metric_series:
            self.metric_series[metric_name] = MetricSeries(
                name=metric_name, metric_type=MetricType.GAUGE
            )

        self.metric_series[metric_name].add_point(value, tags)

    def get_service_metrics(
        self, service_id: str
    ) -> Optional[ServicePerformanceMetrics]:
        """Get metrics for a specific service."""
        return self.metrics.get(service_id)

    def get_all_metrics(self) -> Dict[str, ServicePerformanceMetrics]:
        """Get metrics for all services."""
        return self.metrics.copy()

    def get_metric_series(
        self,
        metric_name: str,
        aggregation: MetricAggregation = MetricAggregation.AVG,
        window: Optional[timedelta] = None,
    ) -> Optional[float]:
        """Get aggregated value for a metric series."""
        series = self.metric_series.get(metric_name)
        if not series:
            return None

        return series.get_aggregated_value(aggregation, window)


class AlertManager:
    """Manages alerts and notifications for service metrics."""

    def __init__(self):
        self.alerts: Dict[str, List[ServiceAlert]] = defaultdict(list)
        self.active_alerts: Dict[str, ServiceAlert] = {}
        self.logger = logging.getLogger(__name__)

    def add_alert(self, alert: ServiceAlert) -> None:
        """Add a new alert configuration."""
        self.alerts[alert.service_id].append(alert)
        self.logger.info(f"Added alert for {alert.service_id}: {alert.metric_name}")

    def check_alerts(
        self, service_id: str, metrics: ServicePerformanceMetrics
    ) -> List[ServiceAlert]:
        """Check all alerts for a service and return triggered alerts."""
        triggered_alerts = []
        service_alerts = self.alerts.get(service_id, [])

        for alert in service_alerts:
            if alert.is_active:
                continue

            # Get the metric value
            metric_value = self._get_metric_value(alert.metric_name, metrics)
            if metric_value is None:
                continue

            # Check if alert condition is met
            if alert.check_condition(metric_value):
                alert.is_active = True
                alert.triggered_at = datetime.now()
                triggered_alerts.append(alert)
                self.active_alerts[f"{service_id}:{alert.metric_name}"] = alert

                self.logger.warning(
                    f"Alert triggered for {service_id}: {alert.message} "
                    f"(value: {metric_value}, threshold: {alert.threshold})"
                )

        return triggered_alerts

    def resolve_alert(self, service_id: str, metric_name: str) -> bool:
        """Resolve an active alert."""
        alert_key = f"{service_id}:{metric_name}"
        if alert_key in self.active_alerts:
            alert = self.active_alerts[alert_key]
            alert.is_active = False
            alert.resolved_at = datetime.now()
            del self.active_alerts[alert_key]

            self.logger.info(f"Alert resolved for {service_id}: {metric_name}")
            return True

        return False

    def _get_metric_value(
        self, metric_name: str, metrics: ServicePerformanceMetrics
    ) -> Optional[float]:
        """Get the value of a specific metric."""
        if metric_name == "error_rate":
            return metrics.error_rate
        elif metric_name == "avg_response_time":
            return metrics.avg_response_time
        elif metric_name == "throughput":
            return metrics.throughput
        elif metric_name == "availability":
            return metrics.availability
        elif metric_name == "health_score":
            return metrics.health_score
        elif metric_name == "request_count":
            return float(metrics.request_count)
        else:
            return None

    def get_active_alerts(self) -> List[ServiceAlert]:
        """Get all currently active alerts."""
        return list(self.active_alerts.values())


class MetricsReporter:
    """Generates reports and dashboards from collected metrics."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.logger = logging.getLogger(__name__)

    def generate_service_report(self, service_id: str) -> Dict[str, Any]:
        """Generate a comprehensive report for a service."""
        metrics = self.metrics_collector.get_service_metrics(service_id)
        if not metrics:
            return {"error": f"No metrics found for service {service_id}"}

        return {
            "service_id": service_id,
            "summary": {
                "total_requests": metrics.request_count,
                "success_rate": f"{(1 - metrics.error_rate) * 100:.2f}%",
                "avg_response_time": f"{metrics.avg_response_time:.2f}ms",
                "throughput": f"{metrics.throughput:.2f} req/s",
                "availability": f"{metrics.availability:.2f}%",
                "health_score": f"{metrics.health_score:.2f}",
            },
            "performance": {
                "min_response_time": f"{metrics.min_response_time:.2f}ms",
                "max_response_time": f"{metrics.max_response_time:.2f}ms",
                "p95_response_time": f"{metrics.get_percentile_response_time(95):.2f}ms",
                "p99_response_time": f"{metrics.get_percentile_response_time(99):.2f}ms",
            },
            "timeline": {
                "first_request": (
                    metrics.first_request_time.isoformat()
                    if metrics.first_request_time
                    else None
                ),
                "last_request": (
                    metrics.last_request_time.isoformat()
                    if metrics.last_request_time
                    else None
                ),
            },
        }

    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate a summary report for all services."""
        all_metrics = self.metrics_collector.get_all_metrics()

        if not all_metrics:
            return {"message": "No metrics available"}

        total_requests = sum(m.request_count for m in all_metrics.values())
        total_success = sum(m.success_count for m in all_metrics.values())
        avg_health_score = statistics.mean(m.health_score for m in all_metrics.values())

        return {
            "overview": {
                "total_services": len(all_metrics),
                "total_requests": total_requests,
                "overall_success_rate": (
                    f"{(total_success / total_requests * 100):.2f}%"
                    if total_requests > 0
                    else "0%"
                ),
                "average_health_score": f"{avg_health_score:.2f}",
            },
            "services": {
                service_id: {
                    "health_score": f"{metrics.health_score:.2f}",
                    "request_count": metrics.request_count,
                    "error_rate": f"{metrics.error_rate * 100:.2f}%",
                    "avg_response_time": f"{metrics.avg_response_time:.2f}ms",
                }
                for service_id, metrics in all_metrics.items()
            },
        }

    def export_metrics(self, format: str = "json") -> Union[Dict[str, Any], str]:
        """Export metrics in the specified format."""
        all_metrics = self.metrics_collector.get_all_metrics()

        if format == "json":
            return {
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    service_id: {
                        "request_count": metrics.request_count,
                        "success_count": metrics.success_count,
                        "error_count": metrics.error_count,
                        "avg_response_time": metrics.avg_response_time,
                        "error_rate": metrics.error_rate,
                        "throughput": metrics.throughput,
                        "availability": metrics.availability,
                        "health_score": metrics.health_score,
                    }
                    for service_id, metrics in all_metrics.items()
                },
            }
        elif format == "csv":
            # Simple CSV export
            lines = [
                "service_id,request_count,success_count,error_count,avg_response_time,error_rate,throughput,availability,health_score"
            ]
            for service_id, metrics in all_metrics.items():
                lines.append(
                    f"{service_id},{metrics.request_count},{metrics.success_count},"
                    f"{metrics.error_count},{metrics.avg_response_time:.2f},"
                    f"{metrics.error_rate:.4f},{metrics.throughput:.2f},"
                    f"{metrics.availability:.2f},{metrics.health_score:.2f}"
                )
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported export format: {format}")


class ServiceMetricsManager:
    """Main manager for all service metrics operations."""

    def __init__(self):
        self.collector = MetricsCollector()
        self.alert_manager = AlertManager()
        self.reporter = MetricsReporter(self.collector)
        self.logger = logging.getLogger(__name__)

    def record_request(
        self,
        service_id: str,
        success: bool,
        response_time: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record a service request and check for alerts."""
        self.collector.record_request(service_id, success, response_time, timestamp)

        # Check for alerts
        metrics = self.collector.get_service_metrics(service_id)
        if metrics:
            triggered_alerts = self.alert_manager.check_alerts(service_id, metrics)
            if triggered_alerts:
                self.logger.warning(
                    f"Triggered {len(triggered_alerts)} alerts for {service_id}"
                )

    def add_alert(self, alert: ServiceAlert) -> None:
        """Add a new alert configuration."""
        self.alert_manager.add_alert(alert)

    def get_service_metrics(
        self, service_id: str
    ) -> Optional[ServicePerformanceMetrics]:
        """Get metrics for a specific service."""
        return self.collector.get_service_metrics(service_id)

    def get_all_metrics(self) -> Dict[str, ServicePerformanceMetrics]:
        """Get metrics for all services."""
        return self.collector.get_all_metrics()

    def generate_service_report(self, service_id: str) -> Dict[str, Any]:
        """Generate a report for a specific service."""
        return self.reporter.generate_service_report(service_id)

    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate a summary report for all services."""
        return self.reporter.generate_summary_report()

    def get_active_alerts(self) -> List[ServiceAlert]:
        """Get all currently active alerts."""
        return self.alert_manager.get_active_alerts()

    def export_metrics(self, format: str = "json") -> Union[Dict[str, Any], str]:
        """Export metrics in the specified format."""
        return self.reporter.export_metrics(format)
