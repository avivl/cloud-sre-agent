"""Performance alerting and threshold management system."""

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
import time
from typing import Any

from ..logging import get_logger

logger = get_logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AlertThreshold:
    """Alert threshold configuration.
    
    Attributes:
        metric_name: Name of the metric to monitor
        threshold_value: Threshold value
        comparison_operator: Comparison operator ('gt', 'lt', 'eq', 'gte', 'lte')
        severity: Alert severity level
        duration: Duration in seconds before triggering alert
        cooldown: Cooldown period in seconds between alerts
    """

    metric_name: str
    threshold_value: int | float
    comparison_operator: str = "gt"  # gt, lt, eq, gte, lte
    severity: AlertSeverity = AlertSeverity.WARNING
    duration: float = 0.0  # Duration before triggering
    cooldown: float = 300.0  # 5 minutes cooldown


@dataclass
class AlertRule:
    """Alert rule definition.
    
    Attributes:
        name: Name of the alert rule
        description: Description of the alert rule
        thresholds: List of thresholds for this rule
        enabled: Whether the rule is enabled
        tags: Additional metadata tags
    """

    name: str
    description: str
    thresholds: list[AlertThreshold] = field(default_factory=list)
    enabled: bool = True
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """Alert instance.
    
    Attributes:
        rule_name: Name of the alert rule
        metric_name: Name of the metric that triggered the alert
        current_value: Current value of the metric
        threshold_value: Threshold value that was exceeded
        severity: Alert severity
        timestamp: When the alert was triggered
        message: Alert message
        tags: Additional metadata tags
    """

    rule_name: str
    metric_name: str
    current_value: int | float
    threshold_value: int | float
    severity: AlertSeverity
    timestamp: float = field(default_factory=time.time)
    message: str = ""
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class AlertConfig:
    """Configuration for performance alerts.
    
    Attributes:
        max_alerts: Maximum number of alerts to store
        alert_retention: How long to keep alerts in seconds
        enable_alert_deduplication: Whether to deduplicate similar alerts
        enable_alert_escalation: Whether to enable alert escalation
        escalation_delay: Delay before escalating alerts in seconds
        max_escalation_levels: Maximum number of escalation levels
    """

    max_alerts: int = 1000
    alert_retention: float = 86400.0  # 24 hours
    enable_alert_deduplication: bool = True
    enable_alert_escalation: bool = True
    escalation_delay: float = 300.0  # 5 minutes
    max_escalation_levels: int = 3


class PerformanceAlerts:
    """Performance alerting and threshold management system.
    
    Monitors performance metrics against configurable thresholds
    and triggers alerts when thresholds are exceeded.
    """

    def __init__(self, config: AlertConfig | None = None):
        """Initialize the performance alerts system.
        
        Args:
            config: Alert configuration
        """
        self._config = config or AlertConfig()
        self._lock = threading.RLock()
        self._rules: dict[str, AlertRule] = {}
        self._alerts: deque = deque(maxlen=self._config.max_alerts)
        self._alert_history: dict[str, float] = {}  # Rule name -> last alert time
        self._escalation_levels: dict[str, int] = {}  # Rule name -> escalation level
        self._alert_handlers: list[Callable[[Alert], None]] = []
        self._cleanup_task: asyncio.Task | None = None
        self._start_cleanup_task()

    def _start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_old_alerts())

    async def _cleanup_old_alerts(self) -> None:
        """Clean up old alerts based on retention period."""
        while True:
            try:
                current_time = time.time()
                cutoff_time = current_time - self._config.alert_retention

                with self._lock:
                    # Remove old alerts
                    while self._alerts and self._alerts[0].timestamp < cutoff_time:
                        self._alerts.popleft()

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in alert cleanup task: {e}")
                await asyncio.sleep(60)

    def add_alert_rule(self, rule: AlertRule) -> None:
        """Add an alert rule.
        
        Args:
            rule: Alert rule to add
        """
        with self._lock:
            self._rules[rule.name] = rule
            self._escalation_levels[rule.name] = 0

    def remove_alert_rule(self, rule_name: str) -> None:
        """Remove an alert rule.
        
        Args:
            rule_name: Name of the rule to remove
        """
        with self._lock:
            self._rules.pop(rule_name, None)
            self._alert_history.pop(rule_name, None)
            self._escalation_levels.pop(rule_name, None)

    def add_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add an alert handler.
        
        Args:
            handler: Function to call when an alert is triggered
        """
        with self._lock:
            self._alert_handlers.append(handler)

    def remove_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Remove an alert handler.
        
        Args:
            handler: Handler to remove
        """
        with self._lock:
            if handler in self._alert_handlers:
                self._alert_handlers.remove(handler)

    def check_metric(
        self,
        metric_name: str,
        value: int | float,
        operation: str | None = None,
        tags: dict[str, str] | None = None
    ) -> list[Alert]:
        """Check a metric value against all applicable rules.
        
        Args:
            metric_name: Name of the metric
            value: Current value of the metric
            operation: Operation name (optional)
            tags: Additional metadata tags
            
        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        current_time = time.time()

        with self._lock:
            for rule_name, rule in self._rules.items():
                if not rule.enabled:
                    continue

                # Check if rule applies to this metric
                applicable_thresholds = [
                    threshold for threshold in rule.thresholds
                    if threshold.metric_name == metric_name
                ]

                if not applicable_thresholds:
                    continue

                # Check each threshold
                for threshold in applicable_thresholds:
                    if self._should_trigger_alert(rule_name, threshold, value, current_time):
                        alert = self._create_alert(
                            rule_name,
                            threshold,
                            value,
                            operation,
                            tags
                        )
                        triggered_alerts.append(alert)
                        self._alerts.append(alert)
                        self._alert_history[rule_name] = current_time

        # Notify handlers
        for alert in triggered_alerts:
            for handler in self._alert_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Error in alert handler: {e}")

        return triggered_alerts

    def _should_trigger_alert(
        self,
        rule_name: str,
        threshold: AlertThreshold,
        value: int | float,
        current_time: float
    ) -> bool:
        """Check if an alert should be triggered.
        
        Args:
            rule_name: Name of the alert rule
            threshold: Alert threshold
            value: Current metric value
            current_time: Current timestamp
            
        Returns:
            True if alert should be triggered
        """
        # Check if we're in cooldown period
        last_alert_time = self._alert_history.get(rule_name, 0)
        if current_time - last_alert_time < threshold.cooldown:
            return False

        # Check threshold condition
        if threshold.comparison_operator == "gt":
            condition_met = value > threshold.threshold_value
        elif threshold.comparison_operator == "lt":
            condition_met = value < threshold.threshold_value
        elif threshold.comparison_operator == "eq":
            condition_met = value == threshold.threshold_value
        elif threshold.comparison_operator == "gte":
            condition_met = value >= threshold.threshold_value
        elif threshold.comparison_operator == "lte":
            condition_met = value <= threshold.threshold_value
        else:
            condition_met = False

        return condition_met

    def _create_alert(
        self,
        rule_name: str,
        threshold: AlertThreshold,
        value: int | float,
        operation: str | None,
        tags: dict[str, str] | None
    ) -> Alert:
        """Create an alert instance.
        
        Args:
            rule_name: Name of the alert rule
            threshold: Alert threshold
            value: Current metric value
            operation: Operation name (optional)
            tags: Additional metadata tags
            
        Returns:
            Alert instance
        """
        message = (
            f"Alert: {threshold.metric_name} {threshold.comparison_operator} "
            f"{threshold.threshold_value} (current: {value})"
        )

        if operation:
            message += f" for operation: {operation}"

        return Alert(
            rule_name=rule_name,
            metric_name=threshold.metric_name,
            current_value=value,
            threshold_value=threshold.threshold_value,
            severity=threshold.severity,
            message=message,
            tags={**(tags or {}), "operation": operation or "unknown"}
        )

    def get_alerts(
        self,
        rule_name: str | None = None,
        severity: AlertSeverity | None = None,
        since: float | None = None
    ) -> list[Alert]:
        """Get alerts matching the specified criteria.
        
        Args:
            rule_name: Filter by rule name (optional)
            severity: Filter by severity (optional)
            since: Filter by timestamp (optional)
            
        Returns:
            List of matching alerts
        """
        with self._lock:
            alerts = list(self._alerts)

        if rule_name:
            alerts = [alert for alert in alerts if alert.rule_name == rule_name]

        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]

        if since:
            alerts = [alert for alert in alerts if alert.timestamp >= since]

        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)

    def get_alert_summary(self) -> dict[str, Any]:
        """Get a summary of alerts.
        
        Returns:
            Alert summary
        """
        with self._lock:
            total_alerts = len(self._alerts)
            alerts_by_severity = {}
            alerts_by_rule = {}

            for alert in self._alerts:
                # Count by severity
                severity = alert.severity.value
                alerts_by_severity[severity] = alerts_by_severity.get(severity, 0) + 1

                # Count by rule
                rule_name = alert.rule_name
                alerts_by_rule[rule_name] = alerts_by_rule.get(rule_name, 0) + 1

            return {
                "total_alerts": total_alerts,
                "alerts_by_severity": alerts_by_severity,
                "alerts_by_rule": alerts_by_rule,
                "active_rules": len(self._rules),
                "alert_handlers": len(self._alert_handlers),
                "config": {
                    "max_alerts": self._config.max_alerts,
                    "alert_retention": self._config.alert_retention,
                    "enable_alert_deduplication": self._config.enable_alert_deduplication,
                    "enable_alert_escalation": self._config.enable_alert_escalation
                }
            }

    def clear_alerts(self, rule_name: str | None = None) -> None:
        """Clear alerts.
        
        Args:
            rule_name: Clear alerts for specific rule (optional)
        """
        with self._lock:
            if rule_name:
                self._alerts = deque(
                    [alert for alert in self._alerts if alert.rule_name != rule_name],
                    maxlen=self._config.max_alerts
                )
            else:
                self._alerts.clear()

    def enable_rule(self, rule_name: str) -> None:
        """Enable an alert rule.
        
        Args:
            rule_name: Name of the rule to enable
        """
        with self._lock:
            if rule_name in self._rules:
                self._rules[rule_name].enabled = True

    def disable_rule(self, rule_name: str) -> None:
        """Disable an alert rule.
        
        Args:
            rule_name: Name of the rule to disable
        """
        with self._lock:
            if rule_name in self._rules:
                self._rules[rule_name].enabled = False

    def get_rules(self) -> dict[str, AlertRule]:
        """Get all alert rules.
        
        Returns:
            Dictionary of rule names to alert rules
        """
        with self._lock:
            return dict(self._rules)

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
