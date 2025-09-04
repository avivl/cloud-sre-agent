"""
Alerting and notification system for the log ingestion system.

Provides comprehensive alerting capabilities including:
- Alert management and routing
- Notification channels (email, webhook, etc.)
- Alert escalation and suppression
- Alert history and analytics
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class Alert:
    """Represents an alert."""

    id: str
    title: str
    message: str
    level: AlertLevel
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class AlertRule:
    """Defines when an alert should be triggered."""

    name: str
    condition: Callable[[Dict[str, Any]], bool]
    level: AlertLevel
    title: str
    message_template: str
    source: str
    enabled: bool = True
    cooldown_minutes: int = 5
    suppression_rules: List[str] = field(default_factory=list)
    notification_channels: List[str] = field(default_factory=list)


@dataclass
class NotificationChannel:
    """Represents a notification channel."""

    name: str
    channel_type: str
    config: Dict[str, Any]
    enabled: bool = True


class AlertManager:
    """
    Comprehensive alerting system for the log ingestion system.

    Manages alerts for:
    - System health issues
    - Performance degradation
    - Error rate spikes
    - Resource exhaustion
    - Component failures
    """

    def __init__(self):
        """Initialize the alert manager."""
        self._alerts: Dict[str, Alert] = {}
        self._alert_rules: Dict[str, AlertRule] = {}
        self._notification_channels: Dict[str, NotificationChannel] = {}
        self._alert_history: List[Alert] = []
        self._suppressed_alerts: Dict[str, datetime] = {}

        # Background tasks
        self._evaluation_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        # Default notification channels
        self._setup_default_channels()

        # Default alert rules
        self._setup_default_rules()

        logger.info("AlertManager initialized")

    async def start(self) -> None:
        """Start the alert manager."""
        if self._running:
            return

        self._running = True
        self._evaluation_task = asyncio.create_task(
            self._evaluate_alerts_periodically()
        )
        self._cleanup_task = asyncio.create_task(self._cleanup_old_alerts())
        logger.info("AlertManager started")

    async def stop(self) -> None:
        """Stop the alert manager."""
        self._running = False

        if self._evaluation_task:
            self._evaluation_task.cancel()
            try:
                await self._evaluation_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("AlertManager stopped")

    def add_alert_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self._alert_rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")

    def remove_alert_rule(self, name: str) -> None:
        """Remove an alert rule."""
        if name in self._alert_rules:
            del self._alert_rules[name]
            logger.info(f"Removed alert rule: {name}")

    def add_notification_channel(self, channel: NotificationChannel) -> None:
        """Add a notification channel."""
        self._notification_channels[channel.name] = channel
        logger.info(f"Added notification channel: {channel.name}")

    def remove_notification_channel(self, name: str) -> None:
        """Remove a notification channel."""
        if name in self._notification_channels:
            del self._notification_channels[name]
            logger.info(f"Removed notification channel: {name}")

    async def create_alert(
        self,
        title: str,
        message: str,
        level: AlertLevel,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Alert:
        """
        Create a new alert.

        Args:
            title: Alert title
            message: Alert message
            level: Alert level
            source: Source of the alert
            metadata: Additional metadata
            tags: Alert tags

        Returns:
            Created Alert object
        """
        alert_id = f"{source}_{int(datetime.now().timestamp())}"

        alert = Alert(
            id=alert_id,
            title=title,
            message=message,
            level=level,
            source=source,
            metadata=metadata or {},
            tags=tags or [],
        )

        self._alerts[alert_id] = alert
        self._alert_history.append(alert)

        # Send notifications
        await self._send_notifications(alert)

        logger.info(f"Created alert: {alert_id} - {title}")
        return alert

    async def resolve_alert(
        self, alert_id: str, resolved_by: str, resolution_notes: Optional[str] = None
    ) -> bool:
        """
        Resolve an alert.

        Args:
            alert_id: Alert ID to resolve
            resolved_by: Who resolved the alert
            resolution_notes: Optional resolution notes

        Returns:
            True if alert was resolved, False if not found
        """
        if alert_id not in self._alerts:
            return False

        alert = self._alerts[alert_id]
        alert.resolved = True
        alert.resolved_at = datetime.now()
        alert.resolved_by = resolved_by
        alert.resolution_notes = resolution_notes

        logger.info(f"Resolved alert: {alert_id} by {resolved_by}")
        return True

    def get_active_alerts(self) -> List[Alert]:
        """Get all active (unresolved) alerts."""
        return [alert for alert in self._alerts.values() if not alert.resolved]

    def get_alerts_by_level(self, level: AlertLevel) -> List[Alert]:
        """Get alerts by severity level."""
        return [alert for alert in self._alerts.values() if alert.level == level]

    def get_alerts_by_source(self, source: str) -> List[Alert]:
        """Get alerts by source."""
        return [alert for alert in self._alerts.values() if alert.source == source]

    def get_alert_history(
        self, limit: int = 100, since: Optional[datetime] = None
    ) -> List[Alert]:
        """
        Get alert history.

        Args:
            limit: Maximum number of alerts to return
            since: Only return alerts since this time

        Returns:
            List of historical alerts
        """
        alerts = self._alert_history

        if since:
            alerts = [alert for alert in alerts if alert.timestamp >= since]

        return alerts[-limit:] if limit > 0 else alerts

    def get_alert_summary(self) -> Dict[str, Any]:
        """
        Get alert summary statistics.

        Returns:
            Dictionary with alert statistics
        """
        active_alerts = self.get_active_alerts()

        summary = {
            "timestamp": datetime.now().isoformat(),
            "active_alerts": {
                "total": len(active_alerts),
                "by_level": {
                    level.value: len([a for a in active_alerts if a.level == level])
                    for level in AlertLevel
                },
                "by_source": {},
            },
            "total_alerts_created": len(self._alert_history),
            "resolved_alerts": len([a for a in self._alert_history if a.resolved]),
            "alert_rules": len(self._alert_rules),
            "notification_channels": len(self._notification_channels),
        }

        # Count alerts by source
        for alert in active_alerts:
            source = alert.source
            if source not in summary["active_alerts"]["by_source"]:
                summary["active_alerts"]["by_source"][source] = 0
            summary["active_alerts"]["by_source"][source] += 1

        return summary

    async def evaluate_alert_rules(self, data: Dict[str, Any]) -> None:
        """
        Evaluate all alert rules against provided data.

        Args:
            data: Data to evaluate against alert rules
        """
        for rule_name, rule in self._alert_rules.items():
            if not rule.enabled:
                continue

            # Check if rule is in cooldown
            if self._is_rule_in_cooldown(rule_name):
                continue

            # Check if alert is suppressed
            if self._is_alert_suppressed(rule.source):
                continue

            try:
                if rule.condition(data):
                    # Create alert
                    message = rule.message_template.format(**data)

                    await self.create_alert(
                        title=rule.title,
                        message=message,
                        level=rule.level,
                        source=rule.source,
                        metadata={"rule": rule_name, "evaluation_data": data},
                        tags=["rule_triggered", rule_name],
                    )

                    # Set cooldown
                    self._suppressed_alerts[f"rule_{rule_name}"] = (
                        datetime.now() + timedelta(minutes=rule.cooldown_minutes)
                    )

            except Exception as e:
                logger.error(f"Error evaluating alert rule {rule_name}: {e}")

    async def _send_notifications(self, alert: Alert) -> None:
        """Send notifications for an alert."""
        for channel_name, channel in self._notification_channels.items():
            if not channel.enabled:
                continue

            try:
                await self._send_notification(channel, alert)
            except Exception as e:
                logger.error(f"Failed to send notification via {channel_name}: {e}")

    async def _send_notification(
        self, channel: NotificationChannel, alert: Alert
    ) -> None:
        """Send notification via a specific channel."""
        if channel.channel_type == "console":
            await self._send_console_notification(alert)
        elif channel.channel_type == "webhook":
            await self._send_webhook_notification(channel, alert)
        elif channel.channel_type == "email":
            await self._send_email_notification(channel, alert)
        else:
            logger.warning(f"Unknown notification channel type: {channel.channel_type}")

    async def _send_console_notification(self, alert: Alert) -> None:
        """Send notification to console."""
        level_color = {
            AlertLevel.INFO: "\033[94m",  # Blue
            AlertLevel.WARNING: "\033[93m",  # Yellow
            AlertLevel.CRITICAL: "\033[91m",  # Red
            AlertLevel.EMERGENCY: "\033[95m",  # Magenta
        }
        reset_color = "\033[0m"

        color = level_color.get(alert.level, "")
        print(f"{color}[{alert.level.value.upper()}] {alert.title}{reset_color}")
        print(f"Source: {alert.source}")
        print(f"Time: {alert.timestamp.isoformat()}")
        print(f"Message: {alert.message}")
        if alert.metadata:
            print(f"Metadata: {json.dumps(alert.metadata, indent=2)}")
        print("-" * 50)

    async def _send_webhook_notification(
        self, channel: NotificationChannel, alert: Alert
    ) -> None:
        """Send notification via webhook."""
        try:
            import aiohttp
        except ImportError:
            logger.error("aiohttp not available for webhook notifications")
            return

        webhook_url = channel.config.get("url")
        if not webhook_url:
            logger.error("Webhook URL not configured")
            return

        payload = {
            "alert_id": alert.id,
            "title": alert.title,
            "message": alert.message,
            "level": alert.level.value,
            "source": alert.source,
            "timestamp": alert.timestamp.isoformat(),
            "metadata": alert.metadata,
            "tags": alert.tags,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status >= 400:
                    logger.error(f"Webhook notification failed: {response.status}")

    async def _send_email_notification(
        self, channel: NotificationChannel, alert: Alert
    ) -> None:
        """Send notification via email."""
        # TODO: Implement email notification
        logger.info(f"Email notification would be sent for alert: {alert.id}")

    def _is_rule_in_cooldown(self, rule_name: str) -> bool:
        """Check if a rule is in cooldown period."""
        cooldown_key = f"rule_{rule_name}"
        if cooldown_key in self._suppressed_alerts:
            return datetime.now() < self._suppressed_alerts[cooldown_key]
        return False

    def _is_alert_suppressed(self, source: str) -> bool:
        """Check if alerts from a source are suppressed."""
        if source in self._suppressed_alerts:
            return datetime.now() < self._suppressed_alerts[source]
        return False

    async def _evaluate_alerts_periodically(self) -> None:
        """Background task to evaluate alert rules periodically."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Evaluate every 30 seconds

                # Get current system data for evaluation
                # This would typically come from metrics, health checks, etc.
                system_data = await self._get_system_data()
                await self.evaluate_alert_rules(system_data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic alert evaluation: {e}")

    async def _cleanup_old_alerts(self) -> None:
        """Background task to clean up old alerts."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Cleanup every hour

                # Remove alerts older than 7 days
                cutoff = datetime.now() - timedelta(days=7)
                self._alert_history = [
                    alert for alert in self._alert_history if alert.timestamp >= cutoff
                ]

                # Remove old suppression entries
                self._suppressed_alerts = {
                    key: value
                    for key, value in self._suppressed_alerts.items()
                    if value >= datetime.now()
                }

                logger.debug("Cleaned up old alerts")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error cleaning up alerts: {e}")

    async def _get_system_data(self) -> Dict[str, Any]:
        """Get current system data for alert evaluation."""
        # This would typically gather data from:
        # - Metrics collector
        # - Health checker
        # - Performance monitor
        # - System resources

        return {
            "timestamp": datetime.now().isoformat(),
            "active_alerts_count": len(self.get_active_alerts()),
            "system_health": "unknown",  # Would come from health checker
            "memory_usage": 0.0,  # Would come from system monitoring
            "cpu_usage": 0.0,  # Would come from system monitoring
            "error_rate": 0.0,  # Would come from metrics
            "throughput": 0.0,  # Would come from performance monitor
        }

    def _setup_default_channels(self) -> None:
        """Setup default notification channels."""
        # Console channel (always available)
        console_channel = NotificationChannel(
            name="console", channel_type="console", config={}
        )
        self.add_notification_channel(console_channel)

    def _setup_default_rules(self) -> None:
        """Setup default alert rules."""
        # High error rate rule
        high_error_rate_rule = AlertRule(
            name="high_error_rate",
            condition=lambda data: data.get("error_rate", 0) > 0.1,  # 10% error rate
            level=AlertLevel.CRITICAL,
            title="High Error Rate Detected",
            message_template="Error rate is {error_rate:.2%}, exceeding threshold of 10%",
            source="system",
            cooldown_minutes=5,
        )
        self.add_alert_rule(high_error_rate_rule)

        # High memory usage rule
        high_memory_rule = AlertRule(
            name="high_memory_usage",
            condition=lambda data: data.get("memory_usage", 0)
            > 0.9,  # 90% memory usage
            level=AlertLevel.WARNING,
            title="High Memory Usage",
            message_template="Memory usage is {memory_usage:.1%}, approaching critical levels",
            source="system",
            cooldown_minutes=10,
        )
        self.add_alert_rule(high_memory_rule)

        # Too many active alerts rule
        too_many_alerts_rule = AlertRule(
            name="too_many_alerts",
            condition=lambda data: data.get("active_alerts_count", 0) > 10,
            level=AlertLevel.WARNING,
            title="Too Many Active Alerts",
            message_template="There are {active_alerts_count} active alerts, indicating potential system issues",
            source="alert_manager",
            cooldown_minutes=15,
        )
        self.add_alert_rule(too_many_alerts_rule)


# Global alert manager instance
_global_alert_manager: Optional[AlertManager] = None


def get_global_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    global _global_alert_manager
    if _global_alert_manager is None:
        _global_alert_manager = AlertManager()
    return _global_alert_manager


def set_global_alert_manager(alert_manager: AlertManager) -> None:
    """Set the global alert manager instance."""
    global _global_alert_manager
    _global_alert_manager = alert_manager


# Convenience functions for common alerts
async def create_health_alert(
    component: str, message: str, level: AlertLevel = AlertLevel.WARNING
) -> Alert:
    """Create a health-related alert."""
    return await get_global_alert_manager().create_alert(
        title=f"Health Issue: {component}",
        message=message,
        level=level,
        source=component,
        tags=["health", component],
    )


async def create_performance_alert(
    component: str, message: str, level: AlertLevel = AlertLevel.WARNING
) -> Alert:
    """Create a performance-related alert."""
    return await get_global_alert_manager().create_alert(
        title=f"Performance Issue: {component}",
        message=message,
        level=level,
        source=component,
        tags=["performance", component],
    )


async def create_error_alert(
    component: str, error: Exception, level: AlertLevel = AlertLevel.CRITICAL
) -> Alert:
    """Create an error-related alert."""
    return await get_global_alert_manager().create_alert(
        title=f"Error in {component}",
        message=f"Error: {str(error)}",
        level=level,
        source=component,
        metadata={"error_type": type(error).__name__, "error_details": str(error)},
        tags=["error", component],
    )
