# gemini_sre_agent/config/metrics.py

"""
Configuration metrics and alerting.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict


@dataclass
class ConfigMetrics:
    """Configuration performance and health metrics."""

    config_load_time_ms: float
    validation_time_ms: float
    cache_hit_rate: float
    last_reload_duration_ms: float
    config_file_size_bytes: int
    environment: str
    timestamp: datetime


class ConfigMetricsCollector:
    """Collect and report configuration metrics."""

    def __init__(self):
        self.metrics_history: list[ConfigMetrics] = []
        self.alert_thresholds = {
            "max_load_time_ms": 1000,
            "max_validation_time_ms": 500,
            "min_cache_hit_rate": 0.8,
            "max_reload_duration_ms": 2000,
        }

    def record_config_load(
        self,
        load_time_ms: float,
        validation_time_ms: float,
        cache_hit_rate: float,
        file_size_bytes: int,
        environment: str,
    ):
        """Record configuration load metrics."""
        metrics = ConfigMetrics(
            config_load_time_ms=load_time_ms,
            validation_time_ms=validation_time_ms,
            cache_hit_rate=cache_hit_rate,
            last_reload_duration_ms=0,  # Will be updated on reload
            config_file_size_bytes=file_size_bytes,
            environment=environment,
            timestamp=datetime.now(),
        )

        self.metrics_history.append(metrics)
        self._check_alert_thresholds(metrics)

    def record_config_reload(self, reload_duration_ms: float):
        """Record configuration reload duration."""
        if self.metrics_history:
            self.metrics_history[-1].last_reload_duration_ms = reload_duration_ms
            self._check_alert_thresholds(self.metrics_history[-1])

    def _check_alert_thresholds(self, metrics: ConfigMetrics):
        """Check metrics against alert thresholds."""
        alerts = []

        if metrics.config_load_time_ms > self.alert_thresholds["max_load_time_ms"]:
            alerts.append(
                f"Config load time exceeded threshold: {metrics.config_load_time_ms}ms"
            )

        if metrics.validation_time_ms > self.alert_thresholds["max_validation_time_ms"]:
            alerts.append(
                f"Config validation time exceeded threshold: {metrics.validation_time_ms}ms"
            )

        if metrics.cache_hit_rate < self.alert_thresholds["min_cache_hit_rate"]:
            alerts.append(
                f"Cache hit rate below threshold: {metrics.cache_hit_rate:.2%}"
            )

        if (
            metrics.last_reload_duration_ms
            > self.alert_thresholds["max_reload_duration_ms"]
        ):
            alerts.append(
                f"Config reload duration exceeded threshold: {metrics.last_reload_duration_ms}ms"
            )

        if alerts:
            self._send_alerts(alerts, metrics)

    def _send_alerts(self, alerts: list[str], metrics: ConfigMetrics):
        """Send configuration alerts."""
        alert_data = {
            "timestamp": metrics.timestamp.isoformat(),
            "environment": metrics.environment,
            "alerts": alerts,
            "metrics": {
                "load_time_ms": metrics.config_load_time_ms,
                "validation_time_ms": metrics.validation_time_ms,
                "cache_hit_rate": metrics.cache_hit_rate,
                "reload_duration_ms": metrics.last_reload_duration_ms,
            },
        }

        # Send to monitoring system
        logger = logging.getLogger("config.alerts")
        logger.warning("Configuration performance alerts", extra=alert_data)

    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get configuration performance summary."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]

        if not recent_metrics:
            return {"error": "No metrics available for specified time period"}

        return {
            "avg_load_time_ms": sum(m.config_load_time_ms for m in recent_metrics)
            / len(recent_metrics),
            "avg_validation_time_ms": sum(m.validation_time_ms for m in recent_metrics)
            / len(recent_metrics),
            "avg_cache_hit_rate": sum(m.cache_hit_rate for m in recent_metrics)
            / len(recent_metrics),
            "avg_reload_duration_ms": sum(
                m.last_reload_duration_ms for m in recent_metrics
            )
            / len(recent_metrics),
            "total_config_loads": len(recent_metrics),
            "max_load_time_ms": max(m.config_load_time_ms for m in recent_metrics),
            "min_cache_hit_rate": min(m.cache_hit_rate for m in recent_metrics),
            "time_period_hours": hours,
        }
