# tests/source_control/test_sub_operation_config.py

"""
Tests for sub-operation configuration system.

This module tests the SubOperationConfig and SubOperationConfigManager classes
to ensure proper configuration management for sub-operation modules.
"""

import pytest

from gemini_sre_agent.source_control.error_handling.core import CircuitBreakerConfig, RetryConfig
from gemini_sre_agent.source_control.providers.sub_operation_config import (
    SubOperationConfig,
    SubOperationConfigManager,
    create_sub_operation_config,
    get_sub_operation_config,
    register_sub_operation_config,
)


class TestSubOperationConfig:
    """Test the SubOperationConfig class."""

    def test_config_creation(self):
        """Test creating a basic configuration."""
        config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="local"
        )
        
        assert config.operation_name == "file_operations"
        assert config.provider_type == "local"
        assert config.error_handling_enabled is True
        assert config.default_timeout == 30.0
        assert config.file_operation_timeout == 60.0

    def test_config_with_custom_settings(self):
        """Test creating configuration with custom settings."""
        circuit_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=30.0,
            success_threshold=3,
            timeout=60.0
        )
        
        retry_config = RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=60.0,
            backoff_factor=2.0,
            jitter=True
        )
        
        config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="github",
            circuit_breaker_config=circuit_config,
            retry_config=retry_config,
            file_operation_timeout=45.0,
            file_operation_retries=5,
            log_level="DEBUG",
            enable_metrics=True
        )
        
        assert config.circuit_breaker_config == circuit_config
        assert config.retry_config == retry_config
        assert config.file_operation_timeout == 45.0
        assert config.file_operation_retries == 5
        assert config.log_level == "DEBUG"
        assert config.enable_metrics is True

    def test_get_operation_timeout(self):
        """Test getting operation-specific timeouts."""
        config = SubOperationConfig(
            operation_name="test",
            provider_type="local",
            file_operation_timeout=60.0,
            branch_operation_timeout=30.0,
            batch_operation_timeout=120.0,
            git_command_timeout=15.0
        )
        
        assert config.get_operation_timeout("file") == 60.0
        assert config.get_operation_timeout("branch") == 30.0
        assert config.get_operation_timeout("batch") == 120.0
        assert config.get_operation_timeout("git") == 15.0
        assert config.get_operation_timeout("unknown") == 30.0  # default

    def test_get_operation_retries(self):
        """Test getting operation-specific retry counts."""
        config = SubOperationConfig(
            operation_name="test",
            provider_type="local",
            file_operation_retries=3,
            branch_operation_retries=2,
            batch_operation_retries=1,
            git_command_retries=4
        )
        
        assert config.get_operation_retries("file") == 3
        assert config.get_operation_retries("branch") == 2
        assert config.get_operation_retries("batch") == 1
        assert config.get_operation_retries("git") == 4
        assert config.get_operation_retries("unknown") == 2  # default

    def test_to_dict(self):
        """Test converting configuration to dictionary."""
        config = SubOperationConfig(
            operation_name="test_ops",
            provider_type="github",
            file_operation_timeout=45.0,
            custom_settings={"test_key": "test_value"}
        )
        
        config_dict = config.to_dict()
        
        assert config_dict["operation_name"] == "test_ops"
        assert config_dict["provider_type"] == "github"
        assert config_dict["file_operation_timeout"] == 45.0
        assert config_dict["custom_settings"]["test_key"] == "test_value"

    def test_from_dict(self):
        """Test creating configuration from dictionary."""
        config_data = {
            "operation_name": "test_ops",
            "provider_type": "gitlab",
            "file_operation_timeout": 50.0,
            "file_operation_retries": 4,
            "log_level": "WARNING",
            "custom_settings": {"key": "value"}
        }
        
        config = SubOperationConfig.from_dict(config_data)
        
        assert config.operation_name == "test_ops"
        assert config.provider_type == "gitlab"
        assert config.file_operation_timeout == 50.0
        assert config.file_operation_retries == 4
        assert config.log_level == "WARNING"
        assert config.custom_settings["key"] == "value"

    def test_from_dict_with_circuit_breaker(self):
        """Test creating configuration from dictionary with circuit breaker config."""
        config_data = {
            "operation_name": "test_ops",
            "provider_type": "github",
            "circuit_breaker_config": {
                "failure_threshold": 5,
                "recovery_timeout": 30.0,
                "success_threshold": 3,
                "timeout": 60.0
            }
        }
        
        config = SubOperationConfig.from_dict(config_data)
        
        assert config.circuit_breaker_config is not None
        assert config.circuit_breaker_config.failure_threshold == 5
        assert config.circuit_breaker_config.recovery_timeout == 30.0


class TestSubOperationConfigManager:
    """Test the SubOperationConfigManager class."""

    @pytest.fixture
    def config_manager(self):
        """Create a configuration manager for testing."""
        return SubOperationConfigManager()

    def test_register_config(self, config_manager):
        """Test registering a configuration."""
        config = SubOperationConfig(
            operation_name="file_ops",
            provider_type="local"
        )
        
        config_manager.register_config(config)
        
        retrieved_config = config_manager.get_config("local", "file_ops")
        assert retrieved_config == config

    def test_get_config(self, config_manager):
        """Test retrieving a configuration."""
        config = SubOperationConfig(
            operation_name="branch_ops",
            provider_type="github"
        )
        
        config_manager.register_config(config)
        
        retrieved_config = config_manager.get_config("github", "branch_ops")
        assert retrieved_config == config
        
        # Test non-existent config
        non_existent = config_manager.get_config("gitlab", "unknown")
        assert non_existent is None

    def test_create_default_config(self, config_manager):
        """Test creating default configuration."""
        config = config_manager.create_default_config("local", "file_operations")
        
        assert config.operation_name == "file_operations"
        assert config.provider_type == "local"
        assert config.file_operation_timeout == 60.0  # Local default
        assert config.file_operation_retries == 2  # Local default

    def test_create_default_config_with_custom_settings(self, config_manager):
        """Test creating default configuration with custom settings."""
        custom_settings = {
            "file_operation_timeout": 90.0,
            "log_level": "DEBUG",
            "custom_key": "custom_value"
        }
        
        config = config_manager.create_default_config(
            "github", "file_operations", custom_settings
        )
        
        assert config.file_operation_timeout == 90.0
        assert config.log_level == "DEBUG"
        assert config.custom_settings["custom_key"] == "custom_value"

    def test_list_configs(self, config_manager):
        """Test listing registered configurations."""
        config1 = SubOperationConfig("ops1", "local")
        config2 = SubOperationConfig("ops2", "github")
        
        config_manager.register_config(config1)
        config_manager.register_config(config2)
        
        configs = config_manager.list_configs()
        assert len(configs) == 2
        assert "local_ops1" in configs
        assert "github_ops2" in configs

    def test_clear_configs(self, config_manager):
        """Test clearing all configurations."""
        config = SubOperationConfig("test_ops", "local")
        config_manager.register_config(config)
        
        assert len(config_manager.list_configs()) == 1
        
        config_manager.clear_configs()
        assert len(config_manager.list_configs()) == 0

    def test_provider_defaults(self, config_manager):
        """Test provider-specific default settings."""
        # Test GitHub defaults
        github_config = config_manager.create_default_config("github", "test")
        assert github_config.file_operation_timeout == 30.0
        assert github_config.file_operation_retries == 3
        
        # Test GitLab defaults
        gitlab_config = config_manager.create_default_config("gitlab", "test")
        assert gitlab_config.file_operation_timeout == 45.0
        assert gitlab_config.file_operation_retries == 3
        
        # Test Local defaults
        local_config = config_manager.create_default_config("local", "test")
        assert local_config.file_operation_timeout == 60.0
        assert local_config.file_operation_retries == 2
        assert local_config.git_command_timeout == 30.0


class TestGlobalFunctions:
    """Test global configuration functions."""

    def test_create_sub_operation_config(self):
        """Test creating sub-operation configuration."""
        config = create_sub_operation_config("local", "file_operations")
        
        assert config.operation_name == "file_operations"
        assert config.provider_type == "local"

    def test_create_sub_operation_config_with_custom_settings(self):
        """Test creating sub-operation configuration with custom settings."""
        custom_settings = {
            "file_operation_timeout": 90.0,
            "log_level": "DEBUG"
        }
        
        config = create_sub_operation_config(
            "github", "file_operations", custom_settings
        )
        
        assert config.file_operation_timeout == 90.0
        assert config.log_level == "DEBUG"

    def test_register_and_get_sub_operation_config(self):
        """Test registering and getting sub-operation configuration."""
        config = SubOperationConfig("test_ops", "local")
        
        register_sub_operation_config(config)
        retrieved_config = get_sub_operation_config("local", "test_ops")
        
        assert retrieved_config == config

    def test_get_nonexistent_config(self):
        """Test getting non-existent configuration."""
        config = get_sub_operation_config("unknown", "nonexistent")
        assert config is None
