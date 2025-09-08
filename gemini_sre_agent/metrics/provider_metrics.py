from collections import defaultdict
from datetime import datetime
from typing import List, Optional

from .enums import ErrorCategory


class ProviderMetrics:
    """
    A class to store and manage metrics for a single LLM provider.
    """

    def __init__(self, provider_id: str):
        """
        Initialize the ProviderMetrics.

        Args:
            provider_id: The unique identifier for the provider.
        """
        self.provider_id = provider_id
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.latency_ms: List[float] = []
        self.token_counts = {"input": 0, "output": 0}
        self.costs: List[float] = []
        self.last_error_time: Optional[datetime] = None
        self.error_categories: defaultdict[ErrorCategory, int] = defaultdict(int)
        self.health_score = 1.0  # 0.0-1.0 scale

    def record_request(
        self,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        success: bool,
        error_category: Optional[ErrorCategory] = None,
    ) -> None:
        """
        Record metrics for a single request.

        Args:
            latency_ms: The latency of the request in milliseconds.
            input_tokens: The number of input tokens.
            output_tokens: The number of output tokens.
            cost: The cost of the request.
            success: Whether the request was successful.
            error_category: The category of the error, if any.
        """
        self.request_count += 1
        self.latency_ms.append(latency_ms)
        self.token_counts["input"] += input_tokens
        self.token_counts["output"] += output_tokens
        self.costs.append(cost)

        if success:
            self.success_count += 1
        else:
            self.error_count += 1
            self.last_error_time = datetime.now()
            if error_category:
                self.error_categories[error_category] += 1

        self.health_score = self.calculate_health_score()

    def calculate_health_score(self) -> float:
        """
        Calculate the health score based on error rate, latency, and availability.

        Returns:
            The health score, a float between 0.0 and 1.0.
        """
        # Base score starts at 1.0 (perfect health)
        score = 1.0

        # Factor 1: Error rate (weighted at 40%)
        if self.request_count > 0:
            error_rate = self.error_count / self.request_count
            error_factor = max(0, 1 - (error_rate * 2))  # 50% error rate -> 0 score
            score -= 0.4 * (1 - error_factor)

        # Factor 2: Latency (weighted at 30%)
        if self.latency_ms:
            avg_latency = sum(self.latency_ms) / len(self.latency_ms)
            latency_factor = 1 - (avg_latency / 5000)
            score -= 0.3 * (1 - latency_factor)

        # Factor 3: Availability (weighted at 30%)
        # Check if any errors in the last 5 minutes
        if self.last_error_time:
            if (datetime.now() - self.last_error_time).total_seconds() < 300:
                score -= 0.3

        return max(0, min(1, score))  # Ensure score is between 0 and 1
