# gemini_sre_agent/ml/adaptive_rate_limiter.py

"""
Adaptive rate limiter with circuit breaker pattern.

This module implements an adaptive rate limiter that can adjust its behavior
based on success rates, error patterns, and cost constraints.
"""

import logging
import time
from typing import Any, Dict, Optional

from .rate_limiter_config import CircuitState, RateLimiterConfig, UrgencyLevel


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter with circuit breaker functionality.

    This class provides intelligent rate limiting that adapts to service
    conditions, implements circuit breaker patterns, and integrates with
    cost tracking systems.
    """

    def __init__(self, config: Optional[RateLimiterConfig] = None):
        """
        Initialize the adaptive rate limiter.

        Args:
            config: Rate limiter configuration. If None, uses default config.
        """
        self.config = config or RateLimiterConfig()
        self.logger = logging.getLogger(__name__)

        # Circuit breaker state
        self.consecutive_errors = 0
        self.current_backoff_seconds = self.config.base_backoff_seconds
        self.circuit_state = CircuitState.CLOSED
        self.circuit_opened_at: Optional[float] = None
        self.last_recovery_test: Optional[float] = None

        # Rate limiting state
        self.rate_limit_hit = False
        self.last_rate_limit_time: Optional[float] = None
        self.request_count = 0
        self.window_start_time = time.time()

        # Success tracking
        self.successful_requests = 0
        self.total_requests = 0
        self.error_count = 0

        # Cost tracking
        self.total_cost = 0.0
        self.daily_cost = 0.0
        self.last_cost_reset = time.time()

        # Adaptive parameters
        self.adaptive_delay = 0.0
        self.success_rate = 1.0

    async def can_make_request(
        self,
        urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
        estimated_cost: Optional[float] = None,
        cost_tracker: Optional[Any] = None,
    ) -> bool:
        """
        Check if a request can be made based on current conditions.

        Args:
            urgency: Urgency level of the request
            estimated_cost: Estimated cost of the request
            cost_tracker: Optional cost tracker instance

        Returns:
            True if request can be made, False otherwise
        """
        # Check circuit breaker state
        if not self._is_circuit_closed():
            self.logger.warning("Circuit breaker is open, blocking request")
            return False

        # Check rate limits
        if not self._check_rate_limits(urgency):
            self.logger.warning("Rate limit exceeded, blocking request")
            return False

        # Check cost constraints
        if self.config.enable_cost_tracking and estimated_cost:
            if not self._check_cost_constraints(estimated_cost, cost_tracker):
                self.logger.warning("Cost constraints exceeded, blocking request")
                return False

        return True

    async def record_request_success(self, actual_cost: Optional[float] = None):
        """
        Record a successful request.

        Args:
            actual_cost: Actual cost of the request
        """
        self.successful_requests += 1
        self.total_requests += 1
        self.consecutive_errors = 0

        # Update cost tracking
        if actual_cost:
            self.total_cost += actual_cost
            self.daily_cost += actual_cost

        # Update success rate
        self.success_rate = self.successful_requests / self.total_requests

        # Reset circuit if it was half-open
        if self.circuit_state == CircuitState.HALF_OPEN:
            self.circuit_state = CircuitState.CLOSED
            self.logger.info("Circuit breaker closed after successful request")

        # Adapt delay based on success rate
        self._adapt_delay()

    async def record_request_error(
        self, error_type: str = "unknown", actual_cost: Optional[float] = None
    ):
        """
        Record a failed request.

        Args:
            error_type: Type of error that occurred
            actual_cost: Actual cost of the request (if any)
        """
        self.error_count += 1
        self.total_requests += 1
        self.consecutive_errors += 1

        # Update cost tracking even for failed requests
        if actual_cost:
            self.total_cost += actual_cost
            self.daily_cost += actual_cost

        # Update success rate
        self.success_rate = self.successful_requests / self.total_requests

        # Check if circuit should be opened
        if self.consecutive_errors >= self.config.max_consecutive_errors:
            self._open_circuit()

        # Increase backoff delay
        self._increase_backoff()

        self.logger.warning(
            f"Request failed: {error_type}, consecutive errors: {self.consecutive_errors}"
        )

    async def record_rate_limit_hit(self):
        """Record that a rate limit was hit."""
        self.rate_limit_hit = True
        self.last_rate_limit_time = time.time()
        self.logger.warning("Rate limit hit, requests will be throttled")

    async def get_delay_seconds(
        self, urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    ) -> float:
        """
        Get the delay in seconds before the next request should be made.

        Args:
            urgency: Urgency level of the request

        Returns:
            Delay in seconds
        """
        # Base delay from backoff
        delay = self.current_backoff_seconds

        # Add adaptive delay
        delay += self.adaptive_delay

        # Adjust for urgency
        urgency_multiplier = {
            UrgencyLevel.LOW: 1.5,
            UrgencyLevel.MEDIUM: 1.0,
            UrgencyLevel.HIGH: 0.5,
            UrgencyLevel.CRITICAL: 0.1,
        }
        delay *= urgency_multiplier.get(urgency, 1.0)

        # Add rate limit delay if needed
        if self.rate_limit_hit:
            delay += self._get_rate_limit_delay()

        return max(0.0, delay)

    def get_stats(self) -> Dict[str, Any]:
        """Get current rate limiter statistics."""
        return {
            "circuit_state": self.circuit_state.value,
            "consecutive_errors": self.consecutive_errors,
            "current_backoff_seconds": self.current_backoff_seconds,
            "success_rate": self.success_rate,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "error_count": self.error_count,
            "rate_limit_hit": self.rate_limit_hit,
            "adaptive_delay": self.adaptive_delay,
            "total_cost": self.total_cost,
            "daily_cost": self.daily_cost,
        }

    def reset_stats(self):
        """Reset all statistics and state."""
        self.consecutive_errors = 0
        self.current_backoff_seconds = self.config.base_backoff_seconds
        self.circuit_state = CircuitState.CLOSED
        self.circuit_opened_at = None
        self.rate_limit_hit = False
        self.last_rate_limit_time = None
        self.successful_requests = 0
        self.total_requests = 0
        self.error_count = 0
        self.adaptive_delay = 0.0
        self.success_rate = 1.0
        self.total_cost = 0.0
        self.daily_cost = 0.0

    def _is_circuit_closed(self) -> bool:
        """Check if circuit breaker allows requests."""
        if self.circuit_state == CircuitState.CLOSED:
            return True

        if self.circuit_state == CircuitState.OPEN:
            # Check if enough time has passed to try recovery
            if (
                self.circuit_opened_at
                and time.time() - self.circuit_opened_at
                >= self.config.circuit_open_duration_seconds
            ):
                self.circuit_state = CircuitState.HALF_OPEN
                self.last_recovery_test = time.time()
                self.logger.info("Circuit breaker moved to half-open state")
                return True
            return False

        if self.circuit_state == CircuitState.HALF_OPEN:
            # Allow limited requests for testing
            if (
                self.last_recovery_test
                and time.time() - self.last_recovery_test
                >= self.config.recovery_test_interval_seconds
            ):
                return True
            return False

        return False

    def _check_rate_limits(self, urgency: UrgencyLevel) -> bool:
        """Check if rate limits allow the request."""
        current_time = time.time()

        # Reset window if needed
        if current_time - self.window_start_time >= 60:  # 1 minute window
            self.request_count = 0
            self.window_start_time = current_time

        # Check if we're within rate limits
        max_requests = self.config.max_requests_per_minute
        if urgency == UrgencyLevel.CRITICAL:
            max_requests = int(max_requests * 1.5)  # Allow more for critical requests

        return self.request_count < max_requests

    def _check_cost_constraints(
        self, estimated_cost: float, cost_tracker: Optional[Any]
    ) -> bool:
        """Check if cost constraints allow the request."""
        # Check per-request cost limit
        if (
            self.config.max_cost_per_request
            and estimated_cost > self.config.max_cost_per_request
        ):
            return False

        # Check daily cost limit
        if (
            self.config.daily_cost_limit
            and self.daily_cost + estimated_cost > self.config.daily_cost_limit
        ):
            return False

        # Check with external cost tracker if provided
        if cost_tracker and hasattr(cost_tracker, "check_budget"):
            # This would be an async call in real implementation
            return True  # Simplified for now

        return True

    def _open_circuit(self):
        """Open the circuit breaker."""
        self.circuit_state = CircuitState.OPEN
        self.circuit_opened_at = time.time()
        self.logger.error("Circuit breaker opened due to consecutive errors")

    def _increase_backoff(self):
        """Increase the backoff delay exponentially."""
        self.current_backoff_seconds = min(
            self.current_backoff_seconds * 2, self.config.max_backoff_seconds
        )

    def _adapt_delay(self):
        """Adapt delay based on success rate."""
        if self.total_requests < self.config.min_requests_for_adaptation:
            return

        if self.success_rate < self.config.success_rate_threshold:
            # Increase delay for poor success rate
            self.adaptive_delay += self.config.adaptation_factor
        else:
            # Decrease delay for good success rate
            self.adaptive_delay = max(
                0, self.adaptive_delay - self.config.adaptation_factor
            )

    def _get_rate_limit_delay(self) -> float:
        """Get delay due to rate limiting."""
        if not self.last_rate_limit_time:
            return 0.0

        # Calculate time until rate limit resets
        time_since_limit = time.time() - self.last_rate_limit_time
        reset_interval = self.config.rate_limit_reset_minutes * 60

        if time_since_limit >= reset_interval:
            self.rate_limit_hit = False
            return 0.0

        return reset_interval - time_since_limit
