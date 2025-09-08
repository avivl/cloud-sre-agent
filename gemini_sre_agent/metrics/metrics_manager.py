from typing import Any, Dict, List, Optional, Tuple

from gemini_sre_agent.llm.config_manager import ConfigManager

from .enums import ErrorCategory
from .provider_metrics import ProviderMetrics


class MetricsManager:
    """
    Central manager for collecting and managing metrics for all LLM providers.
    """

    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the MetricsManager.

        Args:
            config_manager: The configuration manager instance.
        """
        self.config_manager = config_manager
        self.provider_metrics: Dict[str, ProviderMetrics] = {}
        self.global_metrics: Dict[str, Any] = {}
        self.alert_thresholds: Dict[str, Any] = {}
        self.history: Dict[str, Any] = {}
        self._setup_metrics_storage()

    def _setup_metrics_storage(self) -> None:
        """
        Set up metrics storage and load alert thresholds from config.
        """
        config = self.config_manager.get_config()
        if config.metrics_config:
            self.alert_thresholds = config.metrics_config.alert_thresholds
        else:
            self.alert_thresholds = {}

    async def record_provider_request(
        self,
        provider_id: str,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        success: bool,
        error_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record metrics for a provider request.

        Args:
            provider_id: The unique identifier for the provider.
            latency_ms: The latency of the request in milliseconds.
            input_tokens: The number of input tokens.
            output_tokens: The number of output tokens.
            cost: The cost of the request.
            success: Whether the request was successful.
            error_info: A dictionary with error information, if any.
        """
        if provider_id not in self.provider_metrics:
            self.provider_metrics[provider_id] = ProviderMetrics(provider_id)

        error_category = None
        if error_info and "category" in error_info:
            try:
                error_category = ErrorCategory(error_info["category"])
            except ValueError:
                error_category = ErrorCategory.UNKNOWN

        self.provider_metrics[provider_id].record_request(
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            success=success,
            error_category=error_category,
        )

    def get_provider_health(self, provider_id: str) -> float:
        """
        Get the current health score for a provider.

        Args:
            provider_id: The unique identifier for the provider.

        Returns:
            The health score, a float between 0.0 and 1.0.
        """
        if provider_id in self.provider_metrics:
            return self.provider_metrics[provider_id].health_score
        return 1.0  # Default to healthy if no metrics yet

    def get_dashboard_data(self, time_range: str = "1h") -> Dict[str, Any]:
        from .dashboard import DashboardDataGenerator

        """
        Generate data for a monitoring dashboard.

        Args:
            time_range: The time range for the data (e.g., "1h", "24h").

        Returns:
            A dictionary with dashboard data.
        """
        generator = DashboardDataGenerator(self)
        return generator.generate_overview_data()

    def check_alerts(self) -> List[Any]:
        """
        Check for threshold violations and generate alerts.

        Returns:
            A list of alerts.
        """
        # Placeholder for alert checking logic
        return []

    def rank_providers(self, metric: str = "health") -> List[Tuple[str, float]]:
        """
        Rank providers by a specified metric.

        Args:
            metric: The metric to rank by (e.g., "health", "latency", "cost").

        Returns:
            A list of tuples with provider ID and the metric value, sorted.
        """
        ranked_providers: List[Tuple[str, float]] = []
        if metric == "health":
            ranked_providers = [
                (pid, m.health_score) for pid, m in self.provider_metrics.items()
            ]
            ranked_providers.sort(key=lambda item: item[1], reverse=True)
        # Add other metrics for ranking as needed
        return ranked_providers
