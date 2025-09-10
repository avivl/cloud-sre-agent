"""
Configuration validation for error handling system.

This module provides comprehensive validation for error handling configuration
options to ensure they are valid and reasonable.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from .core import (
    CircuitBreakerConfig,
    CircuitState,
    ErrorType,
    OperationCircuitBreakerConfig,
    RetryConfig,
)


class ErrorHandlingConfigValidator:
    """Validates error handling configuration options."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the validator."""
        self.logger = logger or logging.getLogger(__name__)

    def validate_circuit_breaker_config(
        self, config: CircuitBreakerConfig
    ) -> Tuple[bool, List[str]]:
        """
        Validate circuit breaker configuration.

        Args:
            config: Circuit breaker configuration to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate failure threshold
        if not isinstance(config.failure_threshold, int):
            errors.append("failure_threshold must be an integer")
        elif config.failure_threshold < 1:
            errors.append("failure_threshold must be at least 1")
        elif config.failure_threshold > 1000:
            errors.append("failure_threshold should not exceed 1000")

        # Validate recovery timeout
        if not isinstance(config.recovery_timeout, (int, float)):
            errors.append("recovery_timeout must be a number")
        elif config.recovery_timeout <= 0:
            errors.append("recovery_timeout must be positive")
        elif config.recovery_timeout > 3600:  # 1 hour
            errors.append("recovery_timeout should not exceed 3600 seconds")

        # Validate success threshold
        if not isinstance(config.success_threshold, int):
            errors.append("success_threshold must be an integer")
        elif config.success_threshold < 1:
            errors.append("success_threshold must be at least 1")
        elif config.success_threshold > 100:
            errors.append("success_threshold should not exceed 100")

        # Validate timeout
        if not isinstance(config.timeout, (int, float)):
            errors.append("timeout must be a number")
        elif config.timeout <= 0:
            errors.append("timeout must be positive")
        elif config.timeout > 300:  # 5 minutes
            errors.append("timeout should not exceed 300 seconds")

        # Validate logical relationships
        if config.success_threshold >= config.failure_threshold:
            errors.append(
                "success_threshold should be less than failure_threshold for proper circuit breaker behavior"
            )

        return len(errors) == 0, errors

    def validate_operation_circuit_breaker_config(
        self, config: OperationCircuitBreakerConfig
    ) -> Tuple[bool, List[str]]:
        """
        Validate operation-specific circuit breaker configuration.

        Args:
            config: Operation circuit breaker configuration to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate each operation type
        operation_types = [
            "file_operations",
            "branch_operations",
            "pull_request_operations",
            "batch_operations",
            "auth_operations",
            "default",
        ]

        for operation_type in operation_types:
            if hasattr(config, operation_type):
                operation_config = getattr(config, operation_type)
                is_valid, operation_errors = self.validate_circuit_breaker_config(
                    operation_config
                )
                if not is_valid:
                    errors.extend(
                        [f"{operation_type}: {error}" for error in operation_errors]
                    )

        return len(errors) == 0, errors

    def validate_retry_config(self, config: RetryConfig) -> Tuple[bool, List[str]]:
        """
        Validate retry configuration.

        Args:
            config: Retry configuration to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate max retries
        if not isinstance(config.max_retries, int):
            errors.append("max_retries must be an integer")
        elif config.max_retries < 0:
            errors.append("max_retries must be non-negative")
        elif config.max_retries > 10:
            errors.append(
                "max_retries should not exceed 10 to prevent excessive delays"
            )

        # Validate base delay
        if not isinstance(config.base_delay, (int, float)):
            errors.append("base_delay must be a number")
        elif config.base_delay <= 0:
            errors.append("base_delay must be positive")
        elif config.base_delay > 60:
            errors.append("base_delay should not exceed 60 seconds")

        # Validate max delay
        if not isinstance(config.max_delay, (int, float)):
            errors.append("max_delay must be a number")
        elif config.max_delay <= 0:
            errors.append("max_delay must be positive")
        elif config.max_delay > 300:  # 5 minutes
            errors.append("max_delay should not exceed 300 seconds")

        # Validate backoff factor
        if not isinstance(config.backoff_factor, (int, float)):
            errors.append("backoff_factor must be a number")
        elif config.backoff_factor <= 1.0:
            errors.append("backoff_factor must be greater than 1.0")
        elif config.backoff_factor > 10.0:
            errors.append("backoff_factor should not exceed 10.0")

        # Validate jitter
        if not isinstance(config.jitter, bool):
            errors.append("jitter must be a boolean")

        # Validate logical relationships
        if config.base_delay >= config.max_delay:
            errors.append("base_delay should be less than max_delay")

        # Validate that max delay is reasonable given retry count and backoff
        if config.max_retries > 0:
            max_possible_delay = config.base_delay * (
                config.backoff_factor ** (config.max_retries - 1)
            )
            if max_possible_delay > config.max_delay * 2:
                errors.append(
                    f"max_delay ({config.max_delay}) may be too low for the given "
                    f"base_delay ({config.base_delay}) and backoff_factor ({config.backoff_factor}) "
                    f"with {config.max_retries} retries"
                )

        return len(errors) == 0, errors

    def validate_error_type(
        self, error_type: Union[str, ErrorType]
    ) -> Tuple[bool, List[str]]:
        """
        Validate error type.

        Args:
            error_type: Error type to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if isinstance(error_type, str):
            try:
                ErrorType(error_type)
            except ValueError:
                errors.append(f"Invalid error type: {error_type}")
        elif not isinstance(error_type, ErrorType):
            errors.append("error_type must be a string or ErrorType enum")

        return len(errors) == 0, errors

    def validate_circuit_state(
        self, state: Union[str, CircuitState]
    ) -> Tuple[bool, List[str]]:
        """
        Validate circuit state.

        Args:
            state: Circuit state to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if isinstance(state, str):
            try:
                CircuitState(state)
            except ValueError:
                errors.append(f"Invalid circuit state: {state}")
        elif not isinstance(state, CircuitState):
            errors.append("state must be a string or CircuitState enum")

        return len(errors) == 0, errors

    def validate_health_check_config(
        self, config: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate health check configuration.

        Args:
            config: Health check configuration dictionary

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate enabled flag
        if "enabled" in config:
            if not isinstance(config["enabled"], bool):
                errors.append("enabled must be a boolean")

        # Validate check interval
        if "check_interval" in config:
            interval = config["check_interval"]
            if not isinstance(interval, (int, float)):
                errors.append("check_interval must be a number")
            elif interval <= 0:
                errors.append("check_interval must be positive")
            elif interval < 10:
                errors.append("check_interval should be at least 10 seconds")
            elif interval > 3600:  # 1 hour
                errors.append("check_interval should not exceed 3600 seconds")

        # Validate timeout
        if "timeout" in config:
            timeout = config["timeout"]
            if not isinstance(timeout, (int, float)):
                errors.append("timeout must be a number")
            elif timeout <= 0:
                errors.append("timeout must be positive")
            elif timeout > 60:
                errors.append("timeout should not exceed 60 seconds")

        # Validate providers
        if "providers" in config:
            providers = config["providers"]
            if not isinstance(providers, list):
                errors.append("providers must be a list")
            else:
                valid_providers = ["github", "gitlab", "local"]
                for provider in providers:
                    if provider not in valid_providers:
                        errors.append(
                            f"Invalid provider: {provider}. Must be one of {valid_providers}"
                        )

        return len(errors) == 0, errors

    def validate_metrics_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate metrics configuration.

        Args:
            config: Metrics configuration dictionary

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate enabled flag
        if "enabled" in config:
            if not isinstance(config["enabled"], bool):
                errors.append("enabled must be a boolean")

        # Validate collection interval
        if "collection_interval" in config:
            interval = config["collection_interval"]
            if not isinstance(interval, (int, float)):
                errors.append("collection_interval must be a number")
            elif interval <= 0:
                errors.append("collection_interval must be positive")
            elif interval < 1:
                errors.append("collection_interval should be at least 1 second")
            elif interval > 300:  # 5 minutes
                errors.append("collection_interval should not exceed 300 seconds")

        # Validate retention period
        if "retention_period" in config:
            retention = config["retention_period"]
            if not isinstance(retention, (int, float)):
                errors.append("retention_period must be a number")
            elif retention <= 0:
                errors.append("retention_period must be positive")
            elif retention < 3600:  # 1 hour
                errors.append("retention_period should be at least 3600 seconds")
            elif retention > 86400 * 30:  # 30 days
                errors.append("retention_period should not exceed 30 days")

        return len(errors) == 0, errors

    def validate_graceful_degradation_config(
        self, config: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate graceful degradation configuration.

        Args:
            config: Graceful degradation configuration dictionary

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate enabled flag
        if "enabled" in config:
            if not isinstance(config["enabled"], bool):
                errors.append("enabled must be a boolean")

        # Validate fallback timeout
        if "fallback_timeout" in config:
            timeout = config["fallback_timeout"]
            if not isinstance(timeout, (int, float)):
                errors.append("fallback_timeout must be a number")
            elif timeout <= 0:
                errors.append("fallback_timeout must be positive")
            elif timeout > 300:  # 5 minutes
                errors.append("fallback_timeout should not exceed 300 seconds")

        # Validate strategies
        if "strategies" in config:
            strategies = config["strategies"]
            if not isinstance(strategies, dict):
                errors.append("strategies must be a dictionary")
            else:
                valid_strategies = [
                    "reduced_timeout",
                    "cached_data",
                    "simplified_operations",
                    "local_operations",
                    "read_only_mode",
                ]
                for strategy, enabled in strategies.items():
                    if strategy not in valid_strategies:
                        errors.append(
                            f"Invalid strategy: {strategy}. Must be one of {valid_strategies}"
                        )
                    elif not isinstance(enabled, bool):
                        errors.append(
                            f"Strategy {strategy} enabled flag must be a boolean"
                        )

        return len(errors) == 0, errors

    def validate_error_handling_config(
        self, config: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate complete error handling configuration.

        Args:
            config: Complete error handling configuration dictionary

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate circuit breaker config
        if "circuit_breaker" in config:
            circuit_config = config["circuit_breaker"]
            if isinstance(circuit_config, dict):
                # Validate each operation type in the circuit breaker config
                for op_type, op_config in circuit_config.items():
                    if isinstance(op_config, dict):
                        try:
                            # Create a CircuitBreakerConfig from the dict
                            cb_config = CircuitBreakerConfig(**op_config)
                            is_valid, circuit_errors = (
                                self.validate_circuit_breaker_config(cb_config)
                            )
                            if not is_valid:
                                errors.extend(
                                    [
                                        f"circuit_breaker.{op_type}: {error}"
                                        for error in circuit_errors
                                    ]
                                )
                        except Exception as e:
                            errors.append(
                                f"circuit_breaker.{op_type}: Invalid configuration format: {e}"
                            )
                    else:
                        errors.append(f"circuit_breaker.{op_type} must be a dictionary")
            else:
                errors.append("circuit_breaker must be a dictionary")

        # Validate retry config
        if "retry" in config:
            retry_config = config["retry"]
            if isinstance(retry_config, dict):
                try:
                    retry_obj = RetryConfig(**retry_config)
                    is_valid, retry_errors = self.validate_retry_config(retry_obj)
                    if not is_valid:
                        errors.extend([f"retry: {error}" for error in retry_errors])
                except Exception as e:
                    errors.append(f"retry: Invalid configuration format: {e}")
            else:
                errors.append("retry must be a dictionary")

        # Validate health checks config
        if "health_checks" in config:
            is_valid, health_errors = self.validate_health_check_config(
                config["health_checks"]
            )
            if not is_valid:
                errors.extend([f"health_checks: {error}" for error in health_errors])

        # Validate metrics config
        if "metrics" in config:
            is_valid, metrics_errors = self.validate_metrics_config(config["metrics"])
            if not is_valid:
                errors.extend([f"metrics: {error}" for error in metrics_errors])

        # Validate graceful degradation config
        if "graceful_degradation" in config:
            is_valid, degradation_errors = self.validate_graceful_degradation_config(
                config["graceful_degradation"]
            )
            if not is_valid:
                errors.extend(
                    [f"graceful_degradation: {error}" for error in degradation_errors]
                )

        return len(errors) == 0, errors

    def get_default_config(self) -> Dict[str, Any]:
        """
        Get default error handling configuration.

        Returns:
            Default configuration dictionary
        """
        return {
            "circuit_breaker": {
                "file_operations": {
                    "failure_threshold": 10,
                    "recovery_timeout": 30.0,
                    "success_threshold": 2,
                    "timeout": 60.0,
                },
                "branch_operations": {
                    "failure_threshold": 5,
                    "recovery_timeout": 45.0,
                    "success_threshold": 3,
                    "timeout": 45.0,
                },
                "pull_request_operations": {
                    "failure_threshold": 5,
                    "recovery_timeout": 90.0,
                    "success_threshold": 3,
                    "timeout": 30.0,
                },
                "batch_operations": {
                    "failure_threshold": 15,
                    "recovery_timeout": 20.0,
                    "success_threshold": 2,
                    "timeout": 120.0,
                },
                "auth_operations": {
                    "failure_threshold": 10,
                    "recovery_timeout": 300.0,
                    "success_threshold": 5,
                    "timeout": 15.0,
                },
            },
            "retry": {
                "max_retries": 3,
                "base_delay": 1.0,
                "max_delay": 60.0,
                "backoff_factor": 2.0,
                "jitter": True,
            },
            "health_checks": {
                "enabled": True,
                "check_interval": 300.0,
                "timeout": 10.0,
                "providers": ["github", "gitlab", "local"],
            },
            "metrics": {
                "enabled": True,
                "collection_interval": 60.0,
                "retention_period": 86400 * 7,  # 7 days
            },
            "graceful_degradation": {
                "enabled": True,
                "fallback_timeout": 30.0,
                "strategies": {
                    "reduced_timeout": True,
                    "cached_data": True,
                    "simplified_operations": True,
                    "local_operations": True,
                    "read_only_mode": True,
                },
            },
        }

    def validate_and_fix_config(
        self, config: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate configuration and fix common issues.

        Args:
            config: Configuration to validate and fix

        Returns:
            Tuple of (fixed_config, warnings)
        """
        warnings = []
        fixed_config = config.copy()

        # Get default config for fallbacks
        default_config = self.get_default_config()

        # Fix circuit breaker config
        if "circuit_breaker" in fixed_config:
            circuit_config = fixed_config["circuit_breaker"]
            if isinstance(circuit_config, dict):
                # Ensure all operation types are present
                for op_type, default_op_config in default_config[
                    "circuit_breaker"
                ].items():
                    if op_type not in circuit_config:
                        circuit_config[op_type] = default_op_config.copy()
                        warnings.append(
                            f"Added missing {op_type} circuit breaker config"
                        )
        else:
            # Add entire circuit breaker section if missing
            fixed_config["circuit_breaker"] = default_config["circuit_breaker"].copy()
            warnings.append("Added missing circuit_breaker section")

        # Fix retry config
        if "retry" in fixed_config:
            retry_config = fixed_config["retry"]
            if isinstance(retry_config, dict):
                # Ensure all retry fields are present
                for field, default_value in default_config["retry"].items():
                    if field not in retry_config:
                        retry_config[field] = default_value
                        warnings.append(f"Added missing retry config field: {field}")
        else:
            # Add entire retry section if missing
            fixed_config["retry"] = default_config["retry"].copy()
            warnings.append("Added missing retry section")

        # Fix health checks config
        if "health_checks" in fixed_config:
            health_config = fixed_config["health_checks"]
            if isinstance(health_config, dict):
                for field, default_value in default_config["health_checks"].items():
                    if field not in health_config:
                        health_config[field] = default_value
                        warnings.append(
                            f"Added missing health_checks config field: {field}"
                        )
        else:
            # Add entire health_checks section if missing
            fixed_config["health_checks"] = default_config["health_checks"].copy()
            warnings.append("Added missing health_checks section")

        # Fix metrics config
        if "metrics" in fixed_config:
            metrics_config = fixed_config["metrics"]
            if isinstance(metrics_config, dict):
                for field, default_value in default_config["metrics"].items():
                    if field not in metrics_config:
                        metrics_config[field] = default_value
                        warnings.append(f"Added missing metrics config field: {field}")
        else:
            # Add entire metrics section if missing
            fixed_config["metrics"] = default_config["metrics"].copy()
            warnings.append("Added missing metrics section")

        # Fix graceful degradation config
        if "graceful_degradation" in fixed_config:
            degradation_config = fixed_config["graceful_degradation"]
            if isinstance(degradation_config, dict):
                for field, default_value in default_config[
                    "graceful_degradation"
                ].items():
                    if field not in degradation_config:
                        degradation_config[field] = default_value
                        warnings.append(
                            f"Added missing graceful_degradation config field: {field}"
                        )
        else:
            # Add entire graceful_degradation section if missing
            fixed_config["graceful_degradation"] = default_config[
                "graceful_degradation"
            ].copy()
            warnings.append("Added missing graceful_degradation section")

        return fixed_config, warnings
