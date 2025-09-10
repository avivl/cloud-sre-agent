# gemini_sre_agent/config/source_control_error_handling.py

"""
Error handling configuration for source control providers.

This module provides configuration models for the comprehensive error handling
system including circuit breakers, retries, graceful degradation, and health checks.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from pydantic import Field, field_validator

from .base import BaseConfig


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    timeout: float = 30.0


@dataclass
class OperationCircuitBreakerConfig:
    """Configuration for operation-specific circuit breakers."""

    # File operations - more lenient
    file_operations: CircuitBreakerConfig = field(
        default_factory=lambda: CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=30.0,
            success_threshold=2,
            timeout=60.0,
        )
    )

    # Branch operations - moderate
    branch_operations: CircuitBreakerConfig = field(
        default_factory=lambda: CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=45.0,
            success_threshold=3,
            timeout=45.0,
        )
    )

    # Pull request operations - strict
    pull_request_operations: CircuitBreakerConfig = field(
        default_factory=lambda: CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=90.0,
            success_threshold=3,
            timeout=30.0,
        )
    )

    # Batch operations - very lenient
    batch_operations: CircuitBreakerConfig = field(
        default_factory=lambda: CircuitBreakerConfig(
            failure_threshold=15,
            recovery_timeout=20.0,
            success_threshold=2,
            timeout=120.0,
        )
    )

    # Authentication operations - very strict
    auth_operations: CircuitBreakerConfig = field(
        default_factory=lambda: CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=300.0,
            success_threshold=5,
            timeout=15.0,
        )
    )

    # Default fallback
    default: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)


@dataclass
class RetryConfig:
    """Configuration for retry mechanism."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True


@dataclass
class GracefulDegradationConfig:
    """Configuration for graceful degradation strategies."""

    enabled: bool = True
    fallback_strategies: List[str] = field(
        default_factory=lambda: [
            "cached_response",
            "simplified_operation",
            "offline_mode",
        ]
    )
    cache_ttl: float = 300.0  # 5 minutes
    simplified_operation_timeout: float = 10.0
    offline_mode_enabled: bool = True


@dataclass
class HealthCheckConfig:
    """Configuration for health check monitoring."""

    enabled: bool = True
    check_interval: float = 30.0  # seconds
    timeout: float = 10.0  # seconds
    failure_threshold: int = 3
    success_threshold: int = 2
    metrics_retention_hours: int = 24


@dataclass
class MetricsConfig:
    """Configuration for error handling metrics."""

    enabled: bool = True
    collection_interval: float = 60.0  # seconds
    retention_hours: int = 168  # 7 days
    max_series: int = 1000
    max_points_per_series: int = 10000
    background_processing: bool = True


class ErrorHandlingConfig(BaseConfig):
    """Configuration for comprehensive error handling system."""

    enabled: bool = Field(default=True, description="Enable error handling system")

    # Circuit breaker configuration
    circuit_breaker: OperationCircuitBreakerConfig = Field(
        default_factory=OperationCircuitBreakerConfig,
        description="Circuit breaker configuration for different operations",
    )

    # Retry configuration
    retry: RetryConfig = Field(
        default_factory=RetryConfig, description="Retry mechanism configuration"
    )

    # Graceful degradation configuration
    graceful_degradation: GracefulDegradationConfig = Field(
        default_factory=GracefulDegradationConfig,
        description="Graceful degradation strategies configuration",
    )

    # Health check configuration
    health_checks: HealthCheckConfig = Field(
        default_factory=HealthCheckConfig,
        description="Health check monitoring configuration",
    )

    # Metrics configuration
    metrics: MetricsConfig = Field(
        default_factory=MetricsConfig,
        description="Error handling metrics configuration",
    )

    # Provider-specific overrides
    provider_overrides: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Provider-specific error handling overrides"
    )

    @field_validator("provider_overrides")
    @classmethod
    def validate_provider_overrides(cls, v):
        """Validate provider-specific overrides."""
        if not isinstance(v, dict):
            raise ValueError("Provider overrides must be a dictionary")

        valid_providers = ["github", "gitlab", "local"]
        for provider, config in v.items():
            if provider not in valid_providers:
                raise ValueError(
                    f"Invalid provider '{provider}'. Must be one of: {valid_providers}"
                )
            if not isinstance(config, dict):
                raise ValueError(
                    f"Provider override for '{provider}' must be a dictionary"
                )

        return v

    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Get error handling configuration for a specific provider."""
        base_config = {
            "enabled": self.enabled,
            "circuit_breaker": self.circuit_breaker,
            "retry": self.retry,
            "graceful_degradation": self.graceful_degradation,
            "health_checks": self.health_checks,
            "metrics": self.metrics,
        }

        # Apply provider-specific overrides
        if provider_name in self.provider_overrides:
            overrides = self.provider_overrides[provider_name]
            base_config.update(overrides)

        return base_config

    def get_operation_circuit_breaker_config(
        self, operation_type: str
    ) -> CircuitBreakerConfig:
        """Get circuit breaker configuration for a specific operation type."""
        operation_configs = {
            "file_operations": self.circuit_breaker.file_operations,
            "branch_operations": self.circuit_breaker.branch_operations,
            "pull_request_operations": self.circuit_breaker.pull_request_operations,
            "batch_operations": self.circuit_breaker.batch_operations,
            "auth_operations": self.circuit_breaker.auth_operations,
        }

        return operation_configs.get(operation_type, self.circuit_breaker.default)

    def is_operation_enabled(self, operation_type: str) -> bool:
        """Check if error handling is enabled for a specific operation type."""
        if not self.enabled:
            return False

        # Check if specific operation types are disabled
        disabled_operations = self.provider_overrides.get("disabled_operations", [])
        return operation_type not in disabled_operations
