# gemini_sre_agent/config/source_control_error_handling_validation.py

"""
Validation utilities for source control error handling configuration.

This module provides validation functions to ensure error handling configurations
are properly set up and have sensible values.
"""

import logging
from typing import Any, Dict, List, Optional

from .source_control_error_handling import ErrorHandlingConfig


class ErrorHandlingConfigValidator:
    """Validator for error handling configuration."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the validator."""
        self.logger = logger or logging.getLogger(__name__)

    def validate_config(self, config: ErrorHandlingConfig) -> List[str]:
        """Validate error handling configuration and return list of issues."""
        issues = []

        # Validate circuit breaker configuration
        issues.extend(self._validate_circuit_breaker_config(config))

        # Validate retry configuration
        issues.extend(self._validate_retry_config(config))

        # Validate graceful degradation configuration
        issues.extend(self._validate_graceful_degradation_config(config))

        # Validate health check configuration
        issues.extend(self._validate_health_check_config(config))

        # Validate metrics configuration
        issues.extend(self._validate_metrics_config(config))

        # Validate provider overrides
        issues.extend(self._validate_provider_overrides(config))

        return issues

    def _validate_circuit_breaker_config(
        self, config: ErrorHandlingConfig
    ) -> List[str]:
        """Validate circuit breaker configuration."""
        issues = []

        cb_config = config.circuit_breaker

        # Validate failure thresholds
        for operation, cb in [
            ("file_operations", cb_config.file_operations),
            ("branch_operations", cb_config.branch_operations),
            ("pull_request_operations", cb_config.pull_request_operations),
            ("batch_operations", cb_config.batch_operations),
            ("auth_operations", cb_config.auth_operations),
            ("default", cb_config.default),
        ]:
            if cb.failure_threshold <= 0:
                issues.append(
                    f"Circuit breaker failure_threshold for {operation} must be positive"
                )
            if cb.failure_threshold > 100:
                issues.append(
                    f"Circuit breaker failure_threshold for {operation} is too high (>100)"
                )

            if cb.success_threshold <= 0:
                issues.append(
                    f"Circuit breaker success_threshold for {operation} must be positive"
                )
            if cb.success_threshold > cb.failure_threshold:
                issues.append(
                    f"Circuit breaker success_threshold for {operation} should not exceed failure_threshold"
                )

            if cb.recovery_timeout <= 0:
                issues.append(
                    f"Circuit breaker recovery_timeout for {operation} must be positive"
                )
            if cb.recovery_timeout > 3600:  # 1 hour
                issues.append(
                    f"Circuit breaker recovery_timeout for {operation} is too high (>1 hour)"
                )

            if cb.timeout <= 0:
                issues.append(
                    f"Circuit breaker timeout for {operation} must be positive"
                )
            if cb.timeout > 300:  # 5 minutes
                issues.append(
                    f"Circuit breaker timeout for {operation} is too high (>5 minutes)"
                )

        return issues

    def _validate_retry_config(self, config: ErrorHandlingConfig) -> List[str]:
        """Validate retry configuration."""
        issues = []

        retry_config = config.retry

        if retry_config.max_retries < 0:
            issues.append("Retry max_retries must be non-negative")
        if retry_config.max_retries > 20:
            issues.append("Retry max_retries is too high (>20)")

        if retry_config.base_delay <= 0:
            issues.append("Retry base_delay must be positive")
        if retry_config.base_delay > 60:
            issues.append("Retry base_delay is too high (>60 seconds)")

        if retry_config.max_delay <= 0:
            issues.append("Retry max_delay must be positive")
        if (
            retry_config.base_delay > 0
            and retry_config.max_delay < retry_config.base_delay
        ):
            issues.append("Retry max_delay must be >= base_delay")

        if retry_config.backoff_factor <= 1.0:
            issues.append("Retry backoff_factor must be > 1.0")
        if retry_config.backoff_factor > 10.0:
            issues.append("Retry backoff_factor is too high (>10.0)")

        return issues

    def _validate_graceful_degradation_config(
        self, config: ErrorHandlingConfig
    ) -> List[str]:
        """Validate graceful degradation configuration."""
        issues = []

        gd_config = config.graceful_degradation

        valid_strategies = ["cached_response", "simplified_operation", "offline_mode"]
        for strategy in gd_config.fallback_strategies:
            if strategy not in valid_strategies:
                issues.append(f"Invalid graceful degradation strategy: {strategy}")

        if gd_config.cache_ttl <= 0:
            issues.append("Graceful degradation cache_ttl must be positive")
        if gd_config.cache_ttl > 86400:  # 24 hours
            issues.append("Graceful degradation cache_ttl is too high (>24 hours)")

        if gd_config.simplified_operation_timeout <= 0:
            issues.append(
                "Graceful degradation simplified_operation_timeout must be positive"
            )
        if gd_config.simplified_operation_timeout > 300:  # 5 minutes
            issues.append(
                "Graceful degradation simplified_operation_timeout is too high (>5 minutes)"
            )

        return issues

    def _validate_health_check_config(self, config: ErrorHandlingConfig) -> List[str]:
        """Validate health check configuration."""
        issues = []

        hc_config = config.health_checks

        if hc_config.check_interval <= 0:
            issues.append("Health check check_interval must be positive")
        if hc_config.check_interval > 3600:  # 1 hour
            issues.append("Health check check_interval is too high (>1 hour)")

        if hc_config.timeout <= 0:
            issues.append("Health check timeout must be positive")
        if hc_config.timeout > 60:  # 1 minute
            issues.append("Health check timeout is too high (>1 minute)")

        if hc_config.failure_threshold <= 0:
            issues.append("Health check failure_threshold must be positive")
        if hc_config.failure_threshold > 20:
            issues.append("Health check failure_threshold is too high (>20)")

        if hc_config.success_threshold <= 0:
            issues.append("Health check success_threshold must be positive")
        if hc_config.success_threshold > hc_config.failure_threshold:
            issues.append(
                "Health check success_threshold should not exceed failure_threshold"
            )

        return issues

    def _validate_metrics_config(self, config: ErrorHandlingConfig) -> List[str]:
        """Validate metrics configuration."""
        issues = []

        metrics_config = config.metrics

        if metrics_config.collection_interval <= 0:
            issues.append("Metrics collection_interval must be positive")
        if metrics_config.collection_interval > 3600:  # 1 hour
            issues.append("Metrics collection_interval is too high (>1 hour)")

        if metrics_config.retention_hours <= 0:
            issues.append("Metrics retention_hours must be positive")
        if metrics_config.retention_hours > 8760:  # 1 year
            issues.append("Metrics retention_hours is too high (>1 year)")

        if metrics_config.max_series <= 0:
            issues.append("Metrics max_series must be positive")
        if metrics_config.max_series > 100000:
            issues.append("Metrics max_series is too high (>100,000)")

        if metrics_config.max_points_per_series <= 0:
            issues.append("Metrics max_points_per_series must be positive")
        if metrics_config.max_points_per_series > 1000000:
            issues.append("Metrics max_points_per_series is too high (>1,000,000)")

        return issues

    def _validate_provider_overrides(self, config: ErrorHandlingConfig) -> List[str]:
        """Validate provider-specific overrides."""
        issues = []

        valid_providers = ["github", "gitlab", "local"]
        valid_override_keys = [
            "enabled",
            "circuit_breaker",
            "retry",
            "graceful_degradation",
            "health_checks",
            "metrics",
            "disabled_operations",
        ]

        for provider, overrides in config.provider_overrides.items():
            if provider not in valid_providers:
                issues.append(f"Invalid provider in overrides: {provider}")

            for key in overrides.keys():
                if key not in valid_override_keys:
                    issues.append(
                        f"Invalid override key '{key}' for provider '{provider}'"
                    )

            # Validate disabled_operations if present
            if "disabled_operations" in overrides:
                disabled_ops = overrides["disabled_operations"]
                if not isinstance(disabled_ops, list):
                    issues.append(f"disabled_operations for {provider} must be a list")
                else:
                    valid_operations = [
                        "file_operations",
                        "branch_operations",
                        "pull_request_operations",
                        "merge_request_operations",
                        "batch_operations",
                        "auth_operations",
                    ]
                    for op in disabled_ops:
                        if op not in valid_operations:
                            issues.append(
                                f"Invalid disabled operation '{op}' for provider '{provider}'"
                            )

        return issues

    def validate_provider_config(
        self, provider_name: str, config: Dict[str, Any]
    ) -> List[str]:
        """Validate a specific provider's error handling configuration."""
        issues = []

        # Check required fields
        required_fields = [
            "enabled",
            "circuit_breaker",
            "retry",
            "graceful_degradation",
            "health_checks",
            "metrics",
        ]
        for field in required_fields:
            if field not in config:
                issues.append(
                    f"Missing required field '{field}' in {provider_name} configuration"
                )

        # Validate enabled field
        if "enabled" in config and not isinstance(config["enabled"], bool):
            issues.append(
                f"enabled field in {provider_name} configuration must be boolean"
            )

        # Validate circuit breaker configuration
        if "circuit_breaker" in config:
            cb_config = config["circuit_breaker"]
            if not isinstance(cb_config, dict):
                issues.append(
                    f"circuit_breaker in {provider_name} configuration must be a dictionary"
                )
            else:
                # Check for required circuit breaker fields
                required_cb_fields = ["file_operations", "branch_operations", "default"]
                for field in required_cb_fields:
                    if field not in cb_config:
                        issues.append(
                            f"Missing circuit_breaker.{field} in {provider_name} configuration"
                        )

        return issues

    def get_configuration_recommendations(
        self, config: ErrorHandlingConfig
    ) -> List[str]:
        """Get recommendations for improving the configuration."""
        recommendations = []

        # Circuit breaker recommendations
        if config.circuit_breaker.file_operations.failure_threshold < 5:
            recommendations.append(
                "Consider increasing file_operations failure_threshold for better resilience"
            )

        if config.circuit_breaker.auth_operations.failure_threshold > 5:
            recommendations.append(
                "Consider decreasing auth_operations failure_threshold for faster failure detection"
            )

        # Retry recommendations
        if config.retry.max_retries > 10:
            recommendations.append(
                "Consider reducing max_retries to avoid excessive delays"
            )

        if config.retry.max_delay > 120:
            recommendations.append(
                "Consider reducing max_delay to avoid long wait times"
            )

        # Health check recommendations
        if config.health_checks.check_interval < 10:
            recommendations.append(
                "Consider increasing health check interval to reduce overhead"
            )

        if config.health_checks.timeout > 30:
            recommendations.append(
                "Consider reducing health check timeout for faster failure detection"
            )

        # Metrics recommendations
        if config.metrics.retention_hours < 24:
            recommendations.append(
                "Consider increasing metrics retention for better historical analysis"
            )

        if config.metrics.max_series > 10000:
            recommendations.append(
                "Consider reducing max_series to avoid memory issues"
            )

        return recommendations
