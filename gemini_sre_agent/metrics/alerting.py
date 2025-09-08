import asyncio
from typing import Any, Dict, List

from .metrics_manager import MetricsManager
from .models import Alert


class AlertManager:
    """
    Manages alerts based on metrics and thresholds.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the AlertManager.

        Args:
            config: A dictionary with alert configuration.
        """
        self.thresholds = config.get("alert_thresholds", {})
        self.notification_channels = config.get("notification_channels", [])
        self.alert_history: List[Alert] = []

    def check_metrics(self, metrics_manager: MetricsManager) -> List[Alert]:
        """
        Check metrics for threshold violations and generate alerts.

        Args:
            metrics_manager: The MetricsManager instance.

        Returns:
            A list of generated alerts.
        """
        alerts = []
        for provider_id, metrics in metrics_manager.provider_metrics.items():
            health_threshold = self.thresholds.get("health_score", 0.7)
            if metrics.health_score < health_threshold:
                alerts.append(
                    Alert(
                        severity="high",
                        provider_id=provider_id,
                        message=f"Provider health score critical: {metrics.health_score:.2f}",
                        metric="health_score",
                        value=metrics.health_score,
                        threshold=health_threshold,
                    )
                )

        # Add checks for other metrics (latency, error rate, cost) here
        # ...

        self.alert_history.extend(alerts)
        return alerts

    async def send_alerts(self, alerts: List[Alert]) -> None:
        """
        Send alerts to configured notification channels.

        Args:
            alerts: A list of alerts to send.
        """
        # Placeholder for sending alerts to notification channels (e.g., Slack, PagerDuty)
        for alert in alerts:
            print(f"Sending alert: {alert.message}")
        await asyncio.sleep(0)  # To make it awaitable
