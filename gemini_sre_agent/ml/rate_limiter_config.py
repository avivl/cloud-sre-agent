"""
Configuration and data models for adaptive rate limiting.

This module provides enums, constants, and configuration classes
for the AdaptiveRateLimiter component.
"""

from dataclasses import dataclass
from enum import Enum


class UrgencyLevel(Enum):
    """Request urgency levels for rate limiting decisions."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CircuitState(Enum):
    """Circuit breaker states for error handling."""

    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Rejecting requests
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


@dataclass
class RateLimiterConfig:
    """Configuration for adaptive rate limiter behavior."""

    max_consecutive_errors: int = 3
    base_backoff_seconds: int = 1
    max_backoff_seconds: int = 60
    circuit_open_duration_seconds: int = 300  # 5 minutes
    recovery_test_interval_seconds: int = 30
    rate_limit_reset_minutes: int = 1


class RateLimiterMetrics:
    """Helper class for rate limiter metrics calculations."""

    @staticmethod
    def calculate_success_rate(successful_requests: int, total_requests: int) -> float:
        """Calculate success rate percentage."""
        if total_requests == 0:
            return 0.0
        return (successful_requests / total_requests) * 100

    @staticmethod
    def should_allow_critical_override(
        urgency_level: UrgencyLevel, circuit_state: CircuitState, budget_exceeded: bool
    ) -> bool:
        """Determine if critical override should be applied."""
        if urgency_level != UrgencyLevel.CRITICAL:
            return False

        return budget_exceeded or circuit_state == CircuitState.OPEN

    @staticmethod
    def should_skip_for_rate_limit(
        urgency_level: UrgencyLevel, is_rate_limit_active: bool
    ) -> bool:
        """Determine if request should be skipped due to rate limiting."""
        if not is_rate_limit_active:
            return False

        return urgency_level in [UrgencyLevel.LOW, UrgencyLevel.MEDIUM]
