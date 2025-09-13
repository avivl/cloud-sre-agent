"""Alerting system for the logging framework."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
import time
from typing import Any

from .exceptions import AlertingError


class AlertSeverity(Enum):
    """Alert severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class AlertRule:
    """Alert rule definition."""

    name: str
    condition: Callable[[dict[str, Any]], bool]
    severity: AlertSeverity
    message_template: str
    cooldown_seconds: int = 300  # 5 minutes default
    enabled: bool = True
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def evaluate(self, data: dict[str, Any]) -> bool:
        """Evaluate the alert rule.

        Args:
            data: Data to evaluate against the rule

        Returns:
            True if alert should be triggered
        """
        if not self.enabled:
            return False

        try:
            return self.condition(data)
        except Exception:
            return False


@dataclass
class Alert:
    """An alert instance."""

    id: str
    rule_name: str
    severity: AlertSeverity
    message: str
    timestamp: float
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_by: str | None = None
    acknowledged_at: float | None = None
    resolved_at: float | None = None
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary.

        Returns:
            Dictionary representation of the alert
        """
        return {
            "id": self.id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at,
            "resolved_at": self.resolved_at,
            "tags": self.tags,
            "metadata": self.metadata,
        }


class AlertManager:
    """Manages alerts and alert rules."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the alert manager.

        Args:
            config: Optional configuration for alerting
        """
        self._config = config or {}
        self._rules: dict[str, AlertRule] = {}
        self._alerts: dict[str, Alert] = {}
        self._last_triggered: dict[str, float] = {}
        self._lock = Lock()
        self._enabled = self._config.get("enabled", True)
        self._max_alerts = self._config.get("max_alerts", 1000)
        self._alert_handlers: list[Callable[[Alert], None]] = []

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule.

        Args:
            rule: Alert rule to add

        Raises:
            AlertingError: If rule addition fails
        """
        try:
            with self._lock:
                self._rules[rule.name] = rule
        except Exception as e:
            raise AlertingError(
                f"Failed to add alert rule: {e!s}", rule_name=rule.name
            ) from e

    def remove_rule(self, rule_name: str) -> None:
        """Remove an alert rule.

        Args:
            rule_name: Name of the rule to remove
        """
        with self._lock:
            self._rules.pop(rule_name, None)

    def get_rule(self, rule_name: str) -> AlertRule | None:
        """Get an alert rule by name.

        Args:
            rule_name: Name of the rule

        Returns:
            Alert rule or None if not found
        """
        return self._rules.get(rule_name)

    def get_all_rules(self) -> list[AlertRule]:
        """Get all alert rules.

        Returns:
            List of all alert rules
        """
        return list(self._rules.values())

    def evaluate_rules(self, data: dict[str, Any]) -> list[Alert]:
        """Evaluate all rules against data.

        Args:
            data: Data to evaluate against rules

        Returns:
            List of triggered alerts
        """
        if not self._enabled:
            return []

        triggered_alerts = []
        current_time = time.time()

        with self._lock:
            for rule_name, rule in self._rules.items():
                try:
                    # Check cooldown
                    if rule_name in self._last_triggered:
                        if (
                            current_time - self._last_triggered[rule_name]
                            < rule.cooldown_seconds
                        ):
                            continue

                    # Evaluate rule
                    if rule.evaluate(data):
                        # Create alert
                        alert = Alert(
                            id=f"{rule_name}-{int(current_time)}",
                            rule_name=rule_name,
                            severity=rule.severity,
                            message=self._format_message(rule.message_template, data),
                            timestamp=current_time,
                            tags=rule.tags.copy(),
                            metadata=rule.metadata.copy(),
                        )

                        # Add to alerts
                        self._alerts[alert.id] = alert

                        # Update last triggered time
                        self._last_triggered[rule_name] = current_time

                        # Trim alerts if needed
                        if len(self._alerts) > self._max_alerts:
                            # Remove oldest alerts
                            sorted_alerts = sorted(
                                self._alerts.items(), key=lambda x: x[1].timestamp
                            )
                            for alert_id, _ in sorted_alerts[
                                : len(self._alerts) - self._max_alerts
                            ]:
                                del self._alerts[alert_id]

                        triggered_alerts.append(alert)

                        # Notify handlers
                        for handler in self._alert_handlers:
                            try:
                                handler(alert)
                            except Exception:
                                pass  # Ignore handler errors

                except Exception:
                    # Log error but continue with other rules
                    continue

        return triggered_alerts

    def get_alert(self, alert_id: str) -> Alert | None:
        """Get an alert by ID.

        Args:
            alert_id: Alert ID

        Returns:
            Alert or None if not found
        """
        return self._alerts.get(alert_id)

    def get_alerts(
        self,
        status: AlertStatus | None = None,
        severity: AlertSeverity | None = None,
        rule_name: str | None = None,
        limit: int | None = None,
    ) -> list[Alert]:
        """Get alerts with optional filtering.

        Args:
            status: Optional status filter
            severity: Optional severity filter
            rule_name: Optional rule name filter
            limit: Optional limit on number of alerts

        Returns:
            List of filtered alerts
        """
        alerts = list(self._alerts.values())

        # Apply filters
        if status:
            alerts = [a for a in alerts if a.status == status]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if rule_name:
            alerts = [a for a in alerts if a.rule_name == rule_name]

        # Sort by timestamp (newest first)
        alerts.sort(key=lambda x: x.timestamp, reverse=True)

        # Apply limit
        if limit:
            alerts = alerts[:limit]

        return alerts

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert.

        Args:
            alert_id: Alert ID
            acknowledged_by: User who acknowledged the alert

        Returns:
            True if alert was acknowledged, False if not found
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if not alert:
                return False

            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = time.time()

            return True

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert.

        Args:
            alert_id: Alert ID

        Returns:
            True if alert was resolved, False if not found
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if not alert:
                return False

            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = time.time()

            return True

    def suppress_alert(self, alert_id: str) -> bool:
        """Suppress an alert.

        Args:
            alert_id: Alert ID

        Returns:
            True if alert was suppressed, False if not found
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if not alert:
                return False

            alert.status = AlertStatus.SUPPRESSED

            return True

    def clear_resolved_alerts(self) -> int:
        """Clear resolved alerts.

        Returns:
            Number of alerts cleared
        """
        with self._lock:
            resolved_ids = [
                alert_id
                for alert_id, alert in self._alerts.items()
                if alert.status == AlertStatus.RESOLVED
            ]

            for alert_id in resolved_ids:
                del self._alerts[alert_id]

            return len(resolved_ids)

    def clear_all_alerts(self) -> int:
        """Clear all alerts.

        Returns:
            Number of alerts cleared
        """
        with self._lock:
            count = len(self._alerts)
            self._alerts.clear()
            return count

    def add_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add an alert handler.

        Args:
            handler: Function to call when alerts are triggered
        """
        self._alert_handlers.append(handler)

    def remove_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Remove an alert handler.

        Args:
            handler: Handler to remove
        """
        try:
            self._alert_handlers.remove(handler)
        except ValueError:
            pass  # Handler not found

    def enable(self) -> None:
        """Enable alerting."""
        self._enabled = True

    def disable(self) -> None:
        """Disable alerting."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if alerting is enabled.

        Returns:
            True if enabled, False otherwise
        """
        return self._enabled

    def get_alert_stats(self) -> dict[str, Any]:
        """Get alert statistics.

        Returns:
            Dictionary of alert statistics
        """
        with self._lock:
            total_alerts = len(self._alerts)
            active_alerts = len(
                [a for a in self._alerts.values() if a.status == AlertStatus.ACTIVE]
            )
            acknowledged_alerts = len(
                [
                    a
                    for a in self._alerts.values()
                    if a.status == AlertStatus.ACKNOWLEDGED
                ]
            )
            resolved_alerts = len(
                [a for a in self._alerts.values() if a.status == AlertStatus.RESOLVED]
            )
            suppressed_alerts = len(
                [a for a in self._alerts.values() if a.status == AlertStatus.SUPPRESSED]
            )

            severity_counts = {}
            for alert in self._alerts.values():
                severity = alert.severity.value
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

            return {
                "total_alerts": total_alerts,
                "active_alerts": active_alerts,
                "acknowledged_alerts": acknowledged_alerts,
                "resolved_alerts": resolved_alerts,
                "suppressed_alerts": suppressed_alerts,
                "severity_counts": severity_counts,
                "total_rules": len(self._rules),
                "enabled_rules": len([r for r in self._rules.values() if r.enabled]),
            }

    def _format_message(self, template: str, data: dict[str, Any]) -> str:
        """Format alert message template with data.

        Args:
            template: Message template
            data: Data to format with

        Returns:
            Formatted message
        """
        try:
            return template.format(**data)
        except (KeyError, ValueError):
            return template  # Return original template if formatting fails


# Global alert manager instance
_alert_manager: AlertManager | None = None


def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance.

    Returns:
        Global alert manager instance
    """
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def set_alert_manager(manager: AlertManager) -> None:
    """Set the global alert manager instance.

    Args:
        manager: Alert manager instance to set
    """
    global _alert_manager
    _alert_manager = manager
