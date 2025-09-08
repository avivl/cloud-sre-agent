from typing import Any, Dict

from .metrics_manager import MetricsManager


class DashboardDataGenerator:
    """
    Generates data for monitoring dashboards.
    """

    def __init__(self, metrics_manager: MetricsManager):
        """
        Initialize the DashboardDataGenerator.

        Args:
            metrics_manager: The MetricsManager instance.
        """
        self.metrics_manager = metrics_manager

    def generate_overview_data(self) -> Dict[str, Any]:
        """
        Generate high-level system overview data.

        Returns:
            A dictionary with overview data.
        """
        return {
            "total_requests": sum(
                m.request_count for m in self.metrics_manager.provider_metrics.values()
            ),
            "success_rate": self._calculate_global_success_rate(),
            "avg_latency": self._calculate_global_avg_latency(),
            "total_cost": self._calculate_total_cost(),
            "provider_health": {
                p: m.health_score
                for p, m in self.metrics_manager.provider_metrics.items()
            },
        }

    def _calculate_global_success_rate(self) -> float:
        total_requests = sum(
            m.request_count for m in self.metrics_manager.provider_metrics.values()
        )
        if total_requests == 0:
            return 1.0
        total_successes = sum(
            m.success_count for m in self.metrics_manager.provider_metrics.values()
        )
        return total_successes / total_requests

    def _calculate_global_avg_latency(self) -> float:
        all_latencies = [
            latency
            for m in self.metrics_manager.provider_metrics.values()
            for latency in m.latency_ms
        ]
        if not all_latencies:
            return 0.0
        return sum(all_latencies) / len(all_latencies)

    def _calculate_total_cost(self) -> float:
        return sum(
            cost
            for m in self.metrics_manager.provider_metrics.values()
            for cost in m.costs
        )

    def generate_provider_comparison(self) -> Dict[str, Any]:
        """
        Generate provider comparison data.

        Returns:
            A dictionary with provider comparison data.
        """
        # Placeholder for provider comparison logic
        return {}

    def generate_time_series(self, metric: str, time_range: str) -> Dict[str, Any]:
        """
        Generate time series data for a specified metric.

        Args:
            metric: The metric to generate time series data for.
            time_range: The time range for the data (e.g., "1h", "24h").

        Returns:
            A dictionary with time series data.
        """
        # Placeholder for time series generation logic
        return {}
