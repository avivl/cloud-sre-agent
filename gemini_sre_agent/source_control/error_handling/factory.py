# gemini_sre_agent/source_control/error_handling/factory.py

"""
Error handling factory for easy integration with source control providers.

This module provides factory functions and utilities to easily integrate the
comprehensive error handling system into source control providers.
"""

import logging
from typing import Any, Dict, Optional

from .core import (
    CircuitBreakerConfig,
    OperationCircuitBreakerConfig,
    RetryConfig,
)
from .error_classification import ErrorClassifier
from .graceful_degradation import create_graceful_degradation_manager
from .health_checks import HealthCheckManager
from .metrics_integration import ErrorHandlingMetrics
from .resilient_operations import ResilientOperationManager
from .validation import ErrorHandlingConfigValidator


class ErrorHandlingFactory:
    """Factory for creating error handling components."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the factory with configuration."""
        self.config = config or {}
        self.validator = ErrorHandlingConfigValidator()
        self.logger = logging.getLogger("ErrorHandlingFactory")

    def create_error_handling_system(
        self, provider_name: str, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a complete error handling system for a provider.

        Args:
            provider_name: Name of the provider (e.g., 'github', 'gitlab', 'local')
            config: Optional configuration override

        Returns:
            Dictionary containing all error handling components
        """
        # Use provided config or fall back to factory config
        error_config = config or self.config.get("error_handling", {})

        # Validate and fix configuration
        fixed_config, warnings = self.validator.validate_and_fix_config(error_config)
        if warnings:
            self.logger.info(f"Configuration warnings for {provider_name}: {warnings}")

        # Create components
        components = {}

        # Error classifier
        components["error_classifier"] = ErrorClassifier()

        # Metrics collector and error handling metrics
        from ..metrics import MetricsCollector

        metrics_collector = MetricsCollector()
        components["metrics_collector"] = metrics_collector
        components["error_handling_metrics"] = ErrorHandlingMetrics(metrics_collector)

        # Circuit breaker configuration
        circuit_config = self._create_circuit_breaker_config(fixed_config)
        operation_circuit_config = self._create_operation_circuit_breaker_config(
            fixed_config
        )

        # Retry configuration
        retry_config = self._create_retry_config(fixed_config)

        # Resilient operation manager
        components["resilient_manager"] = ResilientOperationManager(
            circuit_breaker_config=circuit_config,
            operation_circuit_breaker_config=operation_circuit_config,
            retry_config=retry_config,
            metrics=components["error_handling_metrics"],
        )

        # Graceful degradation manager
        components["graceful_degradation_manager"] = (
            create_graceful_degradation_manager(
                components["resilient_manager"],
            )
        )

        # Health check manager
        components["health_check_manager"] = HealthCheckManager(
            components["resilient_manager"],
        )

        return components

    def _create_circuit_breaker_config(
        self, config: Dict[str, Any]
    ) -> CircuitBreakerConfig:
        """Create circuit breaker configuration."""
        circuit_config = config.get("circuit_breaker", {})
        return CircuitBreakerConfig(
            failure_threshold=circuit_config.get("failure_threshold", 5),
            recovery_timeout=circuit_config.get("recovery_timeout", 60.0),
            success_threshold=circuit_config.get("success_threshold", 3),
            timeout=circuit_config.get("timeout", 30.0),
        )

    def _create_operation_circuit_breaker_config(
        self, config: Dict[str, Any]
    ) -> OperationCircuitBreakerConfig:
        """Create operation-specific circuit breaker configuration."""
        return OperationCircuitBreakerConfig()

    def _create_retry_config(self, config: Dict[str, Any]) -> RetryConfig:
        """Create retry configuration."""
        retry_config = config.get("retry", {})
        return RetryConfig(
            max_retries=retry_config.get("max_retries", 3),
            base_delay=retry_config.get("base_delay", 1.0),
            max_delay=retry_config.get("max_delay", 60.0),
            backoff_factor=retry_config.get("backoff_factor", 2.0),
            jitter=retry_config.get("jitter", True),
        )

    def get_default_config(self) -> Dict[str, Any]:
        """Get default error handling configuration."""
        return self.validator.get_default_config()

    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate error handling configuration."""
        return self.validator.validate_error_handling_config(config)


def create_error_handling_factory(
    config: Optional[Dict[str, Any]] = None,
) -> ErrorHandlingFactory:
    """Create an error handling factory with the given configuration."""
    return ErrorHandlingFactory(config)


def create_provider_error_handling(
    provider_name: str, config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create error handling components for a specific provider.

    This is a convenience function that creates a factory and returns
    the error handling components for a provider.

    Args:
        provider_name: Name of the provider
        config: Optional configuration

    Returns:
        Dictionary containing error handling components
    """
    factory = ErrorHandlingFactory(config)
    return factory.create_error_handling_system(provider_name, config)


# Provider-specific configuration presets
PROVIDER_CONFIGS = {
    "github": {
        "error_handling": {
            "circuit_breaker": {
                "failure_threshold": 5,
                "recovery_timeout": 60.0,
                "success_threshold": 3,
                "timeout": 30.0,
            },
            "retry": {
                "max_retries": 3,
                "base_delay": 1.0,
                "max_delay": 60.0,
                "backoff_factor": 2.0,
                "jitter": True,
            },
            "graceful_degradation": {
                "enabled": True,
                "fallback_timeout": 30.0,
                "strategies": {
                    "reduced_timeout": True,
                    "simplified_operations": True,
                    "local_operations": False,
                    "read_only_mode": True,
                },
            },
            "health_checks": {
                "enabled": True,
                "check_interval": 300.0,
                "timeout": 10.0,
                "providers": ["github"],
            },
        }
    },
    "gitlab": {
        "error_handling": {
            "circuit_breaker": {
                "failure_threshold": 5,
                "recovery_timeout": 60.0,
                "success_threshold": 3,
                "timeout": 30.0,
            },
            "retry": {
                "max_retries": 3,
                "base_delay": 1.0,
                "max_delay": 60.0,
                "backoff_factor": 2.0,
                "jitter": True,
            },
            "graceful_degradation": {
                "enabled": True,
                "fallback_timeout": 30.0,
                "strategies": {
                    "reduced_timeout": True,
                    "simplified_operations": True,
                    "local_operations": False,
                    "read_only_mode": True,
                },
            },
            "health_checks": {
                "enabled": True,
                "check_interval": 300.0,
                "timeout": 10.0,
                "providers": ["gitlab"],
            },
        }
    },
    "local": {
        "error_handling": {
            "circuit_breaker": {
                "failure_threshold": 10,  # Higher threshold for local operations
                "recovery_timeout": 30.0,  # Shorter recovery time
                "success_threshold": 5,
                "timeout": 60.0,  # Longer timeout for file operations
            },
            "retry": {
                "max_retries": 2,  # Fewer retries for local operations
                "base_delay": 0.5,  # Shorter delays
                "max_delay": 10.0,
                "backoff_factor": 1.5,
                "jitter": False,  # No jitter needed for local operations
            },
            "graceful_degradation": {
                "enabled": True,
                "fallback_timeout": 60.0,
                "strategies": {
                    "reduced_timeout": False,  # Not needed for local
                    "simplified_operations": True,
                    "local_operations": True,  # Enable local fallback
                    "read_only_mode": True,
                },
            },
            "health_checks": {
                "enabled": True,
                "check_interval": 600.0,  # Less frequent checks for local
                "timeout": 30.0,
                "providers": ["local"],
            },
        }
    },
}


def get_provider_config(provider_name: str) -> Dict[str, Any]:
    """Get provider-specific error handling configuration."""
    return PROVIDER_CONFIGS.get(provider_name, PROVIDER_CONFIGS["github"])


def create_provider_error_handling_with_preset(
    provider_name: str, custom_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create error handling components using provider-specific presets.

    Args:
        provider_name: Name of the provider
        custom_config: Optional custom configuration to merge with preset

    Returns:
        Dictionary containing error handling components
    """
    preset_config = get_provider_config(provider_name)

    # Merge custom config if provided
    if custom_config:
        # Deep merge custom config into preset
        merged_config = preset_config.copy()
        if "error_handling" in custom_config:
            merged_config["error_handling"] = {
                **preset_config.get("error_handling", {}),
                **custom_config["error_handling"],
            }
    else:
        merged_config = preset_config

    return create_provider_error_handling(provider_name, merged_config)
