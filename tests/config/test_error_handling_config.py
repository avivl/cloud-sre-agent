# tests/config/test_error_handling_config.py

"""
Tests for error handling configuration.

This module tests the error handling configuration system including
validation, loading, and provider-specific configurations.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from gemini_sre_agent.config.source_control_error_handling import (
    CircuitBreakerConfig,
    ErrorHandlingConfig,
    GracefulDegradationConfig,
    HealthCheckConfig,
    MetricsConfig,
    OperationCircuitBreakerConfig,
    RetryConfig,
)
from gemini_sre_agent.config.source_control_error_handling_loader import (
    ErrorHandlingConfigLoader,
)
from gemini_sre_agent.config.source_control_error_handling_validation import (
    ErrorHandlingConfigValidator,
)
from gemini_sre_agent.config.source_control_repositories import (
    GitHubRepositoryConfig,
    GitLabRepositoryConfig,
    LocalRepositoryConfig,
)


class TestErrorHandlingConfig:
    """Test error handling configuration classes."""

    def test_circuit_breaker_config_defaults(self):
        """Test circuit breaker configuration defaults."""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.success_threshold == 3
        assert config.timeout == 30.0

    def test_operation_circuit_breaker_config_defaults(self):
        """Test operation-specific circuit breaker configuration defaults."""
        config = OperationCircuitBreakerConfig()

        # Test file operations (more lenient)
        assert config.file_operations.failure_threshold == 10
        assert config.file_operations.recovery_timeout == 30.0
        assert config.file_operations.success_threshold == 2
        assert config.file_operations.timeout == 60.0

        # Test auth operations (very strict)
        assert config.auth_operations.failure_threshold == 10
        assert config.auth_operations.recovery_timeout == 300.0
        assert config.auth_operations.success_threshold == 5
        assert config.auth_operations.timeout == 15.0

    def test_retry_config_defaults(self):
        """Test retry configuration defaults."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_factor == 2.0
        assert config.jitter is True

    def test_graceful_degradation_config_defaults(self):
        """Test graceful degradation configuration defaults."""
        config = GracefulDegradationConfig()

        assert config.enabled is True
        assert "cached_response" in config.fallback_strategies
        assert "simplified_operation" in config.fallback_strategies
        assert "offline_mode" in config.fallback_strategies
        assert config.cache_ttl == 300.0
        assert config.simplified_operation_timeout == 10.0
        assert config.offline_mode_enabled is True

    def test_health_check_config_defaults(self):
        """Test health check configuration defaults."""
        config = HealthCheckConfig()

        assert config.enabled is True
        assert config.check_interval == 30.0
        assert config.timeout == 10.0
        assert config.failure_threshold == 3
        assert config.success_threshold == 2
        assert config.metrics_retention_hours == 24

    def test_metrics_config_defaults(self):
        """Test metrics configuration defaults."""
        config = MetricsConfig()

        assert config.enabled is True
        assert config.collection_interval == 60.0
        assert config.retention_hours == 168  # 7 days
        assert config.max_series == 1000
        assert config.max_points_per_series == 10000
        assert config.background_processing is True

    def test_error_handling_config_defaults(self):
        """Test error handling configuration defaults."""
        config = ErrorHandlingConfig()

        assert config.enabled is True
        assert isinstance(config.circuit_breaker, OperationCircuitBreakerConfig)
        assert isinstance(config.retry, RetryConfig)
        assert isinstance(config.graceful_degradation, GracefulDegradationConfig)
        assert isinstance(config.health_checks, HealthCheckConfig)
        assert isinstance(config.metrics, MetricsConfig)
        assert config.provider_overrides == {}

    def test_get_provider_config(self):
        """Test getting provider-specific configuration."""
        config = ErrorHandlingConfig()

        # Test default provider config
        provider_config = config.get_provider_config("github")
        assert provider_config["enabled"] is True
        assert "circuit_breaker" in provider_config
        assert "retry" in provider_config
        assert "graceful_degradation" in provider_config
        assert "health_checks" in provider_config
        assert "metrics" in provider_config

    def test_get_operation_circuit_breaker_config(self):
        """Test getting operation-specific circuit breaker configuration."""
        config = ErrorHandlingConfig()

        # Test file operations
        file_cb_config = config.get_operation_circuit_breaker_config("file_operations")
        assert file_cb_config.failure_threshold == 10

        # Test unknown operation (should return default)
        default_cb_config = config.get_operation_circuit_breaker_config(
            "unknown_operation"
        )
        assert default_cb_config.failure_threshold == 5

    def test_is_operation_enabled(self):
        """Test checking if operation is enabled."""
        config = ErrorHandlingConfig()

        # Test when error handling is enabled
        assert config.is_operation_enabled("file_operations") is True

        # Test when error handling is disabled
        config.enabled = False
        assert config.is_operation_enabled("file_operations") is False

        # Test with disabled operations
        config.enabled = True
        config.provider_overrides = {"disabled_operations": ["file_operations"]}
        assert config.is_operation_enabled("file_operations") is False


class TestErrorHandlingConfigValidator:
    """Test error handling configuration validation."""

    def test_validate_config_valid(self):
        """Test validation of valid configuration."""
        validator = ErrorHandlingConfigValidator()
        config = ErrorHandlingConfig()

        issues = validator.validate_config(config)
        assert len(issues) == 0

    def test_validate_circuit_breaker_config_invalid(self):
        """Test validation of invalid circuit breaker configuration."""
        validator = ErrorHandlingConfigValidator()
        config = ErrorHandlingConfig()

        # Make configuration invalid
        config.circuit_breaker.file_operations.failure_threshold = -1
        config.circuit_breaker.file_operations.success_threshold = (
            10  # > failure_threshold
        )

        issues = validator.validate_config(config)
        assert len(issues) > 0
        assert any("failure_threshold" in issue for issue in issues)
        assert any("success_threshold" in issue for issue in issues)

    def test_validate_retry_config_invalid(self):
        """Test validation of invalid retry configuration."""
        validator = ErrorHandlingConfigValidator()
        config = ErrorHandlingConfig()

        # Test max_retries validation
        config.retry.max_retries = -1
        issues = validator.validate_config(config)
        assert any("max_retries" in issue for issue in issues)

        # Test base_delay validation
        config.retry.max_retries = 3  # Reset to valid
        config.retry.base_delay = -1.0
        issues = validator.validate_config(config)
        assert any("base_delay" in issue for issue in issues)

        # Test max_delay validation
        config.retry.base_delay = 1.0  # Reset to valid
        config.retry.max_delay = 0.5  # < base_delay
        issues = validator.validate_config(config)
        assert any("max_delay" in issue for issue in issues)

    def test_validate_graceful_degradation_config_invalid(self):
        """Test validation of invalid graceful degradation configuration."""
        validator = ErrorHandlingConfigValidator()
        config = ErrorHandlingConfig()

        # Make configuration invalid
        config.graceful_degradation.fallback_strategies = ["invalid_strategy"]
        config.graceful_degradation.cache_ttl = -1.0

        issues = validator.validate_config(config)
        assert len(issues) > 0
        assert any("Invalid graceful degradation strategy" in issue for issue in issues)
        assert any("cache_ttl" in issue for issue in issues)

    def test_validate_health_check_config_invalid(self):
        """Test validation of invalid health check configuration."""
        validator = ErrorHandlingConfigValidator()
        config = ErrorHandlingConfig()

        # Make configuration invalid
        config.health_checks.check_interval = -1.0
        config.health_checks.success_threshold = 5  # > failure_threshold

        issues = validator.validate_config(config)
        assert len(issues) > 0
        assert any("check_interval" in issue for issue in issues)
        assert any("success_threshold" in issue for issue in issues)

    def test_validate_metrics_config_invalid(self):
        """Test validation of invalid metrics configuration."""
        validator = ErrorHandlingConfigValidator()
        config = ErrorHandlingConfig()

        # Make configuration invalid
        config.metrics.collection_interval = -1.0
        config.metrics.max_series = -1

        issues = validator.validate_config(config)
        assert len(issues) > 0
        assert any("collection_interval" in issue for issue in issues)
        assert any("max_series" in issue for issue in issues)

    def test_validate_provider_overrides_invalid(self):
        """Test validation of invalid provider overrides."""
        validator = ErrorHandlingConfigValidator()
        config = ErrorHandlingConfig()

        # Make configuration invalid
        config.provider_overrides = {
            "invalid_provider": {"enabled": True},
            "github": {"invalid_key": "value"},
        }

        issues = validator.validate_config(config)
        assert len(issues) > 0
        assert any("Invalid provider" in issue for issue in issues)
        assert any("Invalid override key" in issue for issue in issues)

    def test_get_configuration_recommendations(self):
        """Test getting configuration recommendations."""
        validator = ErrorHandlingConfigValidator()
        config = ErrorHandlingConfig()

        recommendations = validator.get_configuration_recommendations(config)
        assert isinstance(recommendations, list)


class TestErrorHandlingConfigLoader:
    """Test error handling configuration loader."""

    def test_load_default(self):
        """Test loading default configuration."""
        loader = ErrorHandlingConfigLoader()
        config = loader.load_default()

        assert isinstance(config, ErrorHandlingConfig)
        assert config.enabled is True

    def test_load_from_dict(self):
        """Test loading configuration from dictionary."""
        loader = ErrorHandlingConfigLoader()
        config_data = {
            "enabled": False,
            "retry": {
                "max_retries": 5,
                "base_delay": 2.0,
            },
        }

        config = loader.load_from_dict(config_data)
        assert config.enabled is False
        assert config.retry.max_retries == 5
        assert config.retry.base_delay == 2.0

    def test_load_from_env(self):
        """Test loading configuration from environment variables."""
        loader = ErrorHandlingConfigLoader()

        with patch.dict(
            "os.environ",
            {
                "ERROR_HANDLING_ENABLED": "false",
                "ERROR_HANDLING_RETRY_MAX_RETRIES": "10",
                "ERROR_HANDLING_RETRY_BASE_DELAY": "5.0",
            },
        ):
            config = loader.load_from_env()

            assert config.enabled is False
            assert config.retry.max_retries == 10
            assert config.retry.base_delay == 5.0

    def test_load_from_file_yaml(self):
        """Test loading configuration from YAML file."""
        loader = ErrorHandlingConfigLoader()

        config_data = {
            "enabled": True,
            "retry": {
                "max_retries": 3,
                "base_delay": 1.0,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml

            yaml.dump(config_data, f)
            temp_file = f.name

        try:
            config = loader.load_from_file(temp_file)
            assert config.enabled is True
            assert config.retry.max_retries == 3
        finally:
            Path(temp_file).unlink()

    def test_load_with_validation(self):
        """Test loading configuration with validation."""
        loader = ErrorHandlingConfigLoader()

        # Valid configuration
        config_data = {"enabled": True}
        config = loader.load_with_validation(config_data)
        assert config.enabled is True

        # Invalid configuration
        config_data = {
            "enabled": True,
            "retry": {"max_retries": -1},  # Invalid
        }
        config = loader.load_with_validation(config_data)
        assert config.enabled is True  # Should still load but log warnings

    def test_save_to_file_yaml(self):
        """Test saving configuration to YAML file."""
        loader = ErrorHandlingConfigLoader()
        config = ErrorHandlingConfig()

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_config.yaml"
            loader.save_to_file(config, file_path)

            assert file_path.exists()

            # Verify we can load it back
            loaded_config = loader.load_from_file(file_path)
            assert loaded_config.enabled == config.enabled

    def test_get_configuration_summary(self):
        """Test getting configuration summary."""
        loader = ErrorHandlingConfigLoader()
        config = ErrorHandlingConfig()

        summary = loader.get_configuration_summary(config)

        assert "enabled" in summary
        assert "circuit_breaker_operations" in summary
        assert "retry_max_retries" in summary
        assert "graceful_degradation_enabled" in summary
        assert "health_checks_enabled" in summary
        assert "metrics_enabled" in summary
        assert "provider_overrides" in summary


class TestRepositoryConfigErrorHandling:
    """Test repository configuration with error handling."""

    def test_github_repository_error_handling_config(self):
        """Test GitHub repository error handling configuration."""
        repo_config = GitHubRepositoryConfig(
            name="test-repo",
            url="owner/repo",
            error_handling=ErrorHandlingConfig(),
        )

        error_config = repo_config.get_github_error_handling_config()

        assert error_config["enabled"] is True
        assert "circuit_breaker" in error_config
        assert "retry" in error_config
        assert "graceful_degradation" in error_config

        # Check GitHub-specific overrides
        assert (
            error_config["circuit_breaker"]["file_operations"]["failure_threshold"] == 8
        )
        assert error_config["retry"]["max_retries"] == 5
        assert error_config["graceful_degradation"]["cache_ttl"] == 600.0

    def test_gitlab_repository_error_handling_config(self):
        """Test GitLab repository error handling configuration."""
        repo_config = GitLabRepositoryConfig(
            name="test-repo",
            url="https://gitlab.com/group/project",
            error_handling=ErrorHandlingConfig(),
        )

        error_config = repo_config.get_gitlab_error_handling_config()

        assert error_config["enabled"] is True
        assert "circuit_breaker" in error_config
        assert "retry" in error_config
        assert "graceful_degradation" in error_config

        # Check GitLab-specific overrides
        assert (
            error_config["circuit_breaker"]["file_operations"]["failure_threshold"] == 6
        )
        assert error_config["retry"]["max_retries"] == 4
        assert error_config["graceful_degradation"]["cache_ttl"] == 480.0

    def test_local_repository_error_handling_config(self):
        """Test Local repository error handling configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_config = LocalRepositoryConfig(
                name="test-repo",
                path=temp_dir,
                error_handling=ErrorHandlingConfig(),
            )

            error_config = repo_config.get_local_error_handling_config()

            assert error_config["enabled"] is True
            assert "circuit_breaker" in error_config
            assert "retry" in error_config
            assert "graceful_degradation" in error_config

            # Check Local-specific overrides
            assert (
                error_config["circuit_breaker"]["file_operations"]["failure_threshold"]
                == 20
            )
            assert error_config["retry"]["max_retries"] == 2
            assert error_config["graceful_degradation"]["cache_ttl"] == 1800.0
