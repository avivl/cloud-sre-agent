"""
Adaptive rate limiting for Gemini API requests with urgency-based controls.

This module provides dynamic request rate management based on API responses,
error patterns, and request urgency levels for optimal resource utilization.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from .cost_tracker import CostTracker
from .rate_limiter_config import (
    CircuitState,
    RateLimiterConfig,
    RateLimiterMetrics,
    UrgencyLevel,
)


class AdaptiveRateLimiter:
    """
    Dynamically adjust request rates based on API responses and urgency.

    Implements circuit breaker pattern with exponential backoff and
    urgency-based request filtering for optimal API usage.
    """

    def __init__(self, config: Optional[RateLimiterConfig] = None):
        self.config = config or RateLimiterConfig()

        # Rate limit tracking
        self.rate_limit_hit = False
        self.last_rate_limit_time: Optional[datetime] = None
        self.rate_limit_reset_duration = timedelta(
            minutes=self.config.rate_limit_reset_minutes
        )

        # Error tracking and circuit breaker
        self.consecutive_errors = 0
        self.current_backoff_seconds = self.config.base_backoff_seconds
        self.circuit_state = CircuitState.CLOSED
        self.circuit_opened_at: Optional[datetime] = None
        self.last_recovery_attempt: Optional[datetime] = None

        # Success tracking for adaptive behavior
        self.successful_requests = 0
        self.total_requests = 0

        self.logger = logging.getLogger(__name__)
        self.logger.info(
            "[RATE_LIMITER] Initialized with max_errors=%d, circuit_duration=%ds",
            self.config.max_consecutive_errors,
            self.config.circuit_open_duration_seconds,
        )

    async def should_allow_request(
        self, urgency_level: UrgencyLevel, cost_tracker: CostTracker
    ) -> bool:
        """
        Determine if request should be allowed based on rate limits and urgency.

        Args:
            urgency_level: Request urgency level
            cost_tracker: Cost tracker instance for budget validation

        Returns:
            True if request should be allowed, False otherwise
        """
        self._update_circuit_state()

        # Check budget constraints first
        budget_exceeded = not await cost_tracker.check_budget(0.01)
        if budget_exceeded and RateLimiterMetrics.should_allow_critical_override(
            urgency_level, self.circuit_state, budget_exceeded
        ):
            self.logger.warning(
                "[RATE_LIMITER] Budget exceeded but allowing %s request",
                urgency_level.value,
            )
            return True
        elif budget_exceeded:
            self.logger.info(
                "[RATE_LIMITER] Rejecting %s request due to budget constraints",
                urgency_level.value,
            )
            return False

        # Circuit breaker logic with critical override
        if self.circuit_state == CircuitState.OPEN:
            if RateLimiterMetrics.should_allow_critical_override(
                urgency_level, self.circuit_state, False
            ):
                self.logger.warning(
                    "[RATE_LIMITER] Circuit OPEN but allowing CRITICAL request"
                )
                return True

            self.logger.info(
                "[RATE_LIMITER] Circuit OPEN - rejecting %s request",
                urgency_level.value,
            )
            return False

        # Rate limit recovery check using helper method
        if RateLimiterMetrics.should_skip_for_rate_limit(
            urgency_level, self._is_rate_limit_active()
        ):
            self.logger.info(
                "[RATE_LIMITER] Active rate limit - skipping %s request",
                urgency_level.value,
            )
            return False

        # Apply backoff if needed
        if self.consecutive_errors > 0:
            await self._apply_backoff()

        self.total_requests += 1
        return True

    def record_success(self) -> None:
        """Record successful API call and reset error counters."""
        self.consecutive_errors = 0
        self.current_backoff_seconds = self.config.base_backoff_seconds
        self.successful_requests += 1

        # Close circuit if it was half-open
        if self.circuit_state == CircuitState.HALF_OPEN:
            self.circuit_state = CircuitState.CLOSED
            self.circuit_opened_at = None
            self.logger.info("[RATE_LIMITER] Circuit closed after successful recovery")

        self.rate_limit_hit = False

        self.logger.debug(
            "[RATE_LIMITER] Success recorded - %d/%d success rate",
            self.successful_requests,
            self.total_requests,
        )

    def record_rate_limit_error(self) -> None:
        """Record rate limit hit with timing information."""
        self.rate_limit_hit = True
        self.last_rate_limit_time = datetime.now()
        self.consecutive_errors += 1

        self._update_backoff()
        self._check_circuit_breaker()

        self.logger.warning(
            "[RATE_LIMITER] Rate limit hit - backoff: %ds, errors: %d",
            self.current_backoff_seconds,
            self.consecutive_errors,
        )

    def record_api_error(self) -> None:
        """Record API error for circuit breaker evaluation."""
        self.consecutive_errors += 1

        self._update_backoff()
        self._check_circuit_breaker()

        self.logger.warning(
            "[RATE_LIMITER] API error recorded - errors: %d, backoff: %ds",
            self.consecutive_errors,
            self.current_backoff_seconds,
        )

    def get_status(self) -> dict:
        """Get current rate limiter status and metrics."""
        success_rate = RateLimiterMetrics.calculate_success_rate(
            self.successful_requests, self.total_requests
        )

        return {
            "circuit_state": self.circuit_state.value,
            "consecutive_errors": self.consecutive_errors,
            "current_backoff_seconds": self.current_backoff_seconds,
            "rate_limit_active": self._is_rate_limit_active(),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "success_rate_pct": round(success_rate, 2),
            "rate_limit_reset_in_seconds": self._get_rate_limit_reset_seconds(),
        }

    def _update_circuit_state(self) -> None:
        """Update circuit breaker state based on timing."""
        if self.circuit_state == CircuitState.OPEN and self.circuit_opened_at:
            time_since_open = datetime.now() - self.circuit_opened_at

            if (
                time_since_open.total_seconds()
                >= self.config.circuit_open_duration_seconds
            ):
                self.circuit_state = CircuitState.HALF_OPEN
                self.last_recovery_attempt = datetime.now()
                self.logger.info("[RATE_LIMITER] Circuit moved to HALF_OPEN state")

    def _check_circuit_breaker(self) -> None:
        """Check if circuit breaker should open based on error count."""
        if (
            self.consecutive_errors >= self.config.max_consecutive_errors
            and self.circuit_state == CircuitState.CLOSED
        ):
            self.circuit_state = CircuitState.OPEN
            self.circuit_opened_at = datetime.now()

            self.logger.error(
                "[RATE_LIMITER] Circuit breaker OPENED after %d consecutive errors",
                self.consecutive_errors,
            )

    def _update_backoff(self) -> None:
        """Update backoff duration using exponential backoff."""
        self.current_backoff_seconds = min(
            self.config.max_backoff_seconds, self.current_backoff_seconds * 2
        )

    async def _apply_backoff(self) -> None:
        """Apply current backoff delay."""
        if self.current_backoff_seconds > 0:
            self.logger.debug(
                "[RATE_LIMITER] Applying backoff: %ds", self.current_backoff_seconds
            )
            await asyncio.sleep(self.current_backoff_seconds)

    def _is_rate_limit_active(self) -> bool:
        """Check if rate limit is currently active."""
        if not self.rate_limit_hit or not self.last_rate_limit_time:
            return False

        time_since_rate_limit = datetime.now() - self.last_rate_limit_time
        return time_since_rate_limit < self.rate_limit_reset_duration

    def _get_rate_limit_reset_seconds(self) -> int:
        """Get seconds until rate limit resets."""
        if not self._is_rate_limit_active() or not self.last_rate_limit_time:
            return 0

        time_since_rate_limit = datetime.now() - self.last_rate_limit_time
        reset_in = self.rate_limit_reset_duration - time_since_rate_limit
        return max(0, int(reset_in.total_seconds()))
