# gemini_sre_agent/ml/rate_limiter_config.py

"""
Rate limiter configuration and enums for adaptive rate limiting.

This module defines the configuration classes and enums used by the
adaptive rate limiter for managing API request rates and circuit breaker patterns.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CircuitState(Enum):
    """Circuit breaker states for rate limiting."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, blocking requests
    HALF_OPEN = "half_open"  # Testing if service is back


class UrgencyLevel(Enum):
    """Urgency levels for request prioritization."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RateLimiterConfig:
    """
    Configuration for adaptive rate limiting.

    This class defines all the parameters needed to configure
    the adaptive rate limiter behavior.
    """

    # Circuit breaker configuration
    max_consecutive_errors: int = 3
    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0
    circuit_open_duration_seconds: int = 30
    recovery_test_interval_seconds: int = 10

    # Rate limiting configuration
    rate_limit_reset_minutes: int = 1
    max_requests_per_minute: int = 60
    burst_limit: int = 10

    # Adaptive behavior configuration
    success_rate_threshold: float = 0.8
    min_requests_for_adaptation: int = 10
    adaptation_factor: float = 0.1

    # Cost tracking integration
    enable_cost_tracking: bool = True
    max_cost_per_request: Optional[float] = None
    daily_cost_limit: Optional[float] = None

    # Monitoring and alerting
    enable_monitoring: bool = True
    alert_on_circuit_open: bool = True
    alert_on_high_error_rate: bool = True

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "max_consecutive_errors": self.max_consecutive_errors,
            "base_backoff_seconds": self.base_backoff_seconds,
            "max_backoff_seconds": self.max_backoff_seconds,
            "circuit_open_duration_seconds": self.circuit_open_duration_seconds,
            "recovery_test_interval_seconds": self.recovery_test_interval_seconds,
            "rate_limit_reset_minutes": self.rate_limit_reset_minutes,
            "max_requests_per_minute": self.max_requests_per_minute,
            "burst_limit": self.burst_limit,
            "success_rate_threshold": self.success_rate_threshold,
            "min_requests_for_adaptation": self.min_requests_for_adaptation,
            "adaptation_factor": self.adaptation_factor,
            "enable_cost_tracking": self.enable_cost_tracking,
            "max_cost_per_request": self.max_cost_per_request,
            "daily_cost_limit": self.daily_cost_limit,
            "enable_monitoring": self.enable_monitoring,
            "alert_on_circuit_open": self.alert_on_circuit_open,
            "alert_on_high_error_rate": self.alert_on_high_error_rate,
        }

    @classmethod
    def from_dict(cls, config_dict: dict) -> "RateLimiterConfig":
        """Create configuration from dictionary."""
        return cls(**config_dict)

    def validate(self) -> bool:
        """Validate configuration parameters."""
        if self.max_consecutive_errors < 1:
            return False
        if self.base_backoff_seconds <= 0:
            return False
        if self.max_backoff_seconds < self.base_backoff_seconds:
            return False
        if self.circuit_open_duration_seconds <= 0:
            return False
        if self.rate_limit_reset_minutes <= 0:
            return False
        if self.max_requests_per_minute <= 0:
            return False
        if not 0 <= self.success_rate_threshold <= 1:
            return False
        if self.min_requests_for_adaptation < 1:
            return False
        if not 0 < self.adaptation_factor <= 1:
            return False
        return True
