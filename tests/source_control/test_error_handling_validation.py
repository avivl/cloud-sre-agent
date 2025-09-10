"""
Unit tests for error handling configuration validation.
"""

import pytest

from gemini_sre_agent.source_control.error_handling.core import (
    CircuitBreakerConfig,
    CircuitState,
    ErrorType,
    OperationCircuitBreakerConfig,
    RetryConfig,
)
from gemini_sre_agent.source_control.error_handling.validation import (
    ErrorHandlingConfigValidator,
)


class TestErrorHandlingConfigValidator:
    """Test cases for ErrorHandlingConfigValidator."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance for testing."""
        return ErrorHandlingConfigValidator()

    def test_validate_circuit_breaker_config_valid(self, validator):
        """Test validation of valid circuit breaker config."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
            success_threshold=3,
            timeout=30.0,
        )

        is_valid, errors = validator.validate_circuit_breaker_config(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_circuit_breaker_config_invalid_thresholds(self, validator):
        """Test validation of circuit breaker config with invalid thresholds."""
        config = CircuitBreakerConfig(
            failure_threshold=0,  # Invalid: too low
            recovery_timeout=-1.0,  # Invalid: negative
            success_threshold=10,  # Invalid: >= failure_threshold
            timeout=0,  # Invalid: zero
        )

        is_valid, errors = validator.validate_circuit_breaker_config(config)
        assert not is_valid
        assert len(errors) > 0
        assert any("failure_threshold must be at least 1" in error for error in errors)
        assert any("recovery_timeout must be positive" in error for error in errors)
        assert any(
            "success_threshold should be less than failure_threshold" in error
            for error in errors
        )
        assert any("timeout must be positive" in error for error in errors)

    def test_validate_circuit_breaker_config_extreme_values(self, validator):
        """Test validation of circuit breaker config with extreme values."""
        config = CircuitBreakerConfig(
            failure_threshold=2000,  # Too high
            recovery_timeout=7200.0,  # Too high
            success_threshold=200,  # Too high
            timeout=600.0,  # Too high
        )

        is_valid, errors = validator.validate_circuit_breaker_config(config)
        assert not is_valid
        assert any(
            "failure_threshold should not exceed 1000" in error for error in errors
        )
        assert any(
            "recovery_timeout should not exceed 3600 seconds" in error
            for error in errors
        )
        assert any(
            "success_threshold should not exceed 100" in error for error in errors
        )
        assert any("timeout should not exceed 300 seconds" in error for error in errors)

    def test_validate_operation_circuit_breaker_config_valid(self, validator):
        """Test validation of valid operation circuit breaker config."""
        config = OperationCircuitBreakerConfig()

        is_valid, errors = validator.validate_operation_circuit_breaker_config(config)
        if not is_valid:
            print(f"Validation errors: {errors}")
        assert is_valid
        assert len(errors) == 0

    def test_validate_operation_circuit_breaker_config_invalid_operations(
        self, validator
    ):
        """Test validation of operation circuit breaker config with invalid operations."""
        config = OperationCircuitBreakerConfig()
        config.file_operations.failure_threshold = 0  # Invalid

        is_valid, errors = validator.validate_operation_circuit_breaker_config(config)
        assert not is_valid
        assert any(
            "file_operations: failure_threshold must be at least 1" in error
            for error in errors
        )

    def test_validate_retry_config_valid(self, validator):
        """Test validation of valid retry config."""
        config = RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=60.0,
            backoff_factor=2.0,
            jitter=True,
        )

        is_valid, errors = validator.validate_retry_config(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_retry_config_invalid_values(self, validator):
        """Test validation of retry config with invalid values."""
        config = RetryConfig(
            max_retries=-1,  # Invalid: negative
            base_delay=0,  # Invalid: zero
            max_delay=-1.0,  # Invalid: negative
            backoff_factor=0.5,  # Invalid: <= 1.0
            jitter="yes",  # Invalid: not boolean
        )

        is_valid, errors = validator.validate_retry_config(config)
        assert not is_valid
        assert any("max_retries must be non-negative" in error for error in errors)
        assert any("base_delay must be positive" in error for error in errors)
        assert any("max_delay must be positive" in error for error in errors)
        assert any(
            "backoff_factor must be greater than 1.0" in error for error in errors
        )
        assert any("jitter must be a boolean" in error for error in errors)

    def test_validate_retry_config_logical_errors(self, validator):
        """Test validation of retry config with logical errors."""
        config = RetryConfig(
            max_retries=3,
            base_delay=10.0,  # Greater than max_delay
            max_delay=5.0,
            backoff_factor=2.0,
            jitter=True,
        )

        is_valid, errors = validator.validate_retry_config(config)
        assert not is_valid
        assert any(
            "base_delay should be less than max_delay" in error for error in errors
        )

    def test_validate_retry_config_max_delay_too_low(self, validator):
        """Test validation of retry config with max_delay too low for retry count."""
        config = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=10.0,  # Too low for 5 retries with backoff_factor 2.0
            backoff_factor=2.0,
            jitter=True,
        )

        is_valid, errors = validator.validate_retry_config(config)
        if not is_valid:
            print(f"Retry validation errors: {errors}")
        assert not is_valid
        assert any("max_delay" in error and "too low" in error for error in errors)

    def test_validate_error_type_valid_string(self, validator):
        """Test validation of valid error type as string."""
        is_valid, errors = validator.validate_error_type("network_error")
        assert is_valid
        assert len(errors) == 0

    def test_validate_error_type_valid_enum(self, validator):
        """Test validation of valid error type as enum."""
        is_valid, errors = validator.validate_error_type(ErrorType.NETWORK_ERROR)
        assert is_valid
        assert len(errors) == 0

    def test_validate_error_type_invalid(self, validator):
        """Test validation of invalid error type."""
        is_valid, errors = validator.validate_error_type("invalid_error")
        assert not is_valid
        assert any("Invalid error type: invalid_error" in error for error in errors)

    def test_validate_circuit_state_valid_string(self, validator):
        """Test validation of valid circuit state as string."""
        is_valid, errors = validator.validate_circuit_state("closed")
        assert is_valid
        assert len(errors) == 0

    def test_validate_circuit_state_valid_enum(self, validator):
        """Test validation of valid circuit state as enum."""
        is_valid, errors = validator.validate_circuit_state(CircuitState.CLOSED)
        assert is_valid
        assert len(errors) == 0

    def test_validate_circuit_state_invalid(self, validator):
        """Test validation of invalid circuit state."""
        is_valid, errors = validator.validate_circuit_state("invalid_state")
        assert not is_valid
        assert any("Invalid circuit state: invalid_state" in error for error in errors)

    def test_validate_health_check_config_valid(self, validator):
        """Test validation of valid health check config."""
        config = {
            "enabled": True,
            "check_interval": 300.0,
            "timeout": 10.0,
            "providers": ["github", "gitlab", "local"],
        }

        is_valid, errors = validator.validate_health_check_config(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_health_check_config_invalid(self, validator):
        """Test validation of invalid health check config."""
        config = {
            "enabled": "yes",  # Invalid: not boolean
            "check_interval": -1.0,  # Invalid: negative
            "timeout": 120.0,  # Invalid: too high
            "providers": ["invalid_provider"],  # Invalid: unknown provider
        }

        is_valid, errors = validator.validate_health_check_config(config)
        assert not is_valid
        assert any("enabled must be a boolean" in error for error in errors)
        assert any("check_interval must be positive" in error for error in errors)
        assert any("timeout should not exceed 60 seconds" in error for error in errors)
        assert any("Invalid provider: invalid_provider" in error for error in errors)

    def test_validate_metrics_config_valid(self, validator):
        """Test validation of valid metrics config."""
        config = {
            "enabled": True,
            "collection_interval": 60.0,
            "retention_period": 86400 * 7,  # 7 days
        }

        is_valid, errors = validator.validate_metrics_config(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_metrics_config_invalid(self, validator):
        """Test validation of invalid metrics config."""
        config = {
            "enabled": "true",  # Invalid: not boolean
            "collection_interval": 0.5,  # Invalid: too low
            "retention_period": 3600 * 25,  # Invalid: too high
        }

        is_valid, errors = validator.validate_metrics_config(config)
        if not is_valid:
            print(f"Metrics validation errors: {errors}")
        assert not is_valid
        assert any("enabled must be a boolean" in error for error in errors)
        assert any(
            "collection_interval should be at least 1 second" in error
            for error in errors
        )
        # Note: retention_period validation might not be triggered if the value is within limits
        # Let's check if the error exists or adjust the test value
        if not any(
            "retention_period should not exceed 30 days" in error for error in errors
        ):
            # Try with a higher value
            config["retention_period"] = 86400 * 31  # 31 days
            is_valid, errors = validator.validate_metrics_config(config)
            assert any(
                "retention_period should not exceed 30 days" in error
                for error in errors
            )

    def test_validate_graceful_degradation_config_valid(self, validator):
        """Test validation of valid graceful degradation config."""
        config = {
            "enabled": True,
            "fallback_timeout": 30.0,
            "strategies": {
                "reduced_timeout": True,
                "cached_data": True,
                "simplified_operations": False,
                "local_operations": True,
                "read_only_mode": False,
            },
        }

        is_valid, errors = validator.validate_graceful_degradation_config(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_graceful_degradation_config_invalid(self, validator):
        """Test validation of invalid graceful degradation config."""
        config = {
            "enabled": "yes",  # Invalid: not boolean
            "fallback_timeout": -1.0,  # Invalid: negative
            "strategies": {
                "invalid_strategy": True,  # Invalid: unknown strategy
                "reduced_timeout": "yes",  # Invalid: not boolean
            },
        }

        is_valid, errors = validator.validate_graceful_degradation_config(config)
        assert not is_valid
        assert any("enabled must be a boolean" in error for error in errors)
        assert any("fallback_timeout must be positive" in error for error in errors)
        assert any("Invalid strategy: invalid_strategy" in error for error in errors)
        assert any(
            "Strategy reduced_timeout enabled flag must be a boolean" in error
            for error in errors
        )

    def test_validate_error_handling_config_valid(self, validator):
        """Test validation of valid complete error handling config."""
        config = {
            "circuit_breaker": {
                "file_operations": {
                    "failure_threshold": 10,
                    "recovery_timeout": 30.0,
                    "success_threshold": 2,
                    "timeout": 60.0,
                }
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
            },
            "metrics": {"enabled": True, "collection_interval": 60.0},
            "graceful_degradation": {"enabled": True, "fallback_timeout": 30.0},
        }

        is_valid, errors = validator.validate_error_handling_config(config)
        if not is_valid:
            print(f"Error handling config validation errors: {errors}")
        assert is_valid
        assert len(errors) == 0

    def test_validate_error_handling_config_invalid(self, validator):
        """Test validation of invalid complete error handling config."""
        config = {
            "circuit_breaker": "invalid",  # Invalid: not dict
            "retry": "invalid",  # Invalid: not dict
            "health_checks": {"enabled": "yes"},  # Invalid: not boolean
        }

        is_valid, errors = validator.validate_error_handling_config(config)
        assert not is_valid
        assert any("circuit_breaker must be a dictionary" in error for error in errors)
        assert any("retry must be a dictionary" in error for error in errors)
        assert any(
            "health_checks: enabled must be a boolean" in error for error in errors
        )

    def test_get_default_config(self, validator):
        """Test getting default configuration."""
        config = validator.get_default_config()

        assert isinstance(config, dict)
        assert "circuit_breaker" in config
        assert "retry" in config
        assert "health_checks" in config
        assert "metrics" in config
        assert "graceful_degradation" in config

        # Validate the default config
        is_valid, errors = validator.validate_error_handling_config(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_and_fix_config_complete(self, validator):
        """Test validation and fixing of complete config."""
        config = {
            "circuit_breaker": {
                "file_operations": {
                    "failure_threshold": 10,
                    "recovery_timeout": 30.0,
                    # Missing success_threshold and timeout
                }
            },
            "retry": {
                "max_retries": 3
                # Missing other fields
            },
            # Missing other sections
        }

        fixed_config, warnings = validator.validate_and_fix_config(config)

        # Should have warnings about missing fields
        assert len(warnings) > 0
        assert any("Added missing" in warning for warning in warnings)

        # Fixed config should be valid
        is_valid, errors = validator.validate_error_handling_config(fixed_config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_and_fix_config_empty(self, validator):
        """Test validation and fixing of empty config."""
        config = {}

        fixed_config, warnings = validator.validate_and_fix_config(config)

        # Should have many warnings about missing sections
        assert len(warnings) > 0

        # Fixed config should be valid
        is_valid, errors = validator.validate_error_handling_config(fixed_config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_and_fix_config_partial(self, validator):
        """Test validation and fixing of partial config."""
        config = {
            "circuit_breaker": {
                "file_operations": {
                    "failure_threshold": 10,
                    "recovery_timeout": 30.0,
                    "success_threshold": 2,
                    "timeout": 60.0,
                }
                # Missing other operation types
            },
            "retry": {
                "max_retries": 3,
                "base_delay": 1.0,
                "max_delay": 60.0,
                "backoff_factor": 2.0,
                "jitter": True,
            },
            # Missing health_checks, metrics, graceful_degradation
        }

        fixed_config, warnings = validator.validate_and_fix_config(config)

        # Should have warnings about missing sections and operation types
        assert len(warnings) > 0
        assert any("Added missing" in warning for warning in warnings)

        # Fixed config should be valid
        is_valid, errors = validator.validate_error_handling_config(fixed_config)
        assert is_valid
        assert len(errors) == 0
