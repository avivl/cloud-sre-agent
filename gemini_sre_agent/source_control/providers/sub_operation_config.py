# gemini_sre_agent/source_control/providers/sub_operation_config.py

"""
Sub-operation configuration module.

This module provides configuration support for sub-operation modules,
allowing them to have their own error handling and operational settings.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..error_handling.core import CircuitBreakerConfig, RetryConfig


@dataclass
class SubOperationConfig:
    """Configuration for sub-operation modules."""
    
    # Operation-specific settings
    operation_name: str
    provider_type: str  # 'github', 'gitlab', 'local'
    
    # Error handling configuration
    error_handling_enabled: bool = True
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    retry_config: Optional[RetryConfig] = None
    
    # Operation-specific timeouts
    default_timeout: float = 30.0
    file_operation_timeout: float = 60.0
    branch_operation_timeout: float = 45.0
    batch_operation_timeout: float = 120.0
    git_command_timeout: float = 30.0
    
    # Retry settings for specific operation types
    file_operation_retries: int = 3
    branch_operation_retries: int = 2
    batch_operation_retries: int = 1
    git_command_retries: int = 2
    
    # Logging configuration
    log_level: str = "INFO"
    log_operations: bool = True
    log_errors: bool = True
    log_performance: bool = False
    
    # Performance settings
    enable_metrics: bool = True
    enable_tracing: bool = False
    
    # Provider-specific settings
    provider_settings: Dict[str, Any] = field(default_factory=dict)
    
    # Custom operation settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    def get_operation_timeout(self, operation_type: str) -> float:
        """Get timeout for specific operation type."""
        timeout_map = {
            "file": self.file_operation_timeout,
            "branch": self.branch_operation_timeout,
            "batch": self.batch_operation_timeout,
            "git": self.git_command_timeout,
        }
        return timeout_map.get(operation_type, self.default_timeout)
    
    def get_operation_retries(self, operation_type: str) -> int:
        """Get retry count for specific operation type."""
        retry_map = {
            "file": self.file_operation_retries,
            "branch": self.branch_operation_retries,
            "batch": self.batch_operation_retries,
            "git": self.git_command_retries,
        }
        return retry_map.get(operation_type, 2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "operation_name": self.operation_name,
            "provider_type": self.provider_type,
            "error_handling_enabled": self.error_handling_enabled,
            "circuit_breaker_config": (
                self.circuit_breaker_config.__dict__ if self.circuit_breaker_config else None
            ),
            "retry_config": (
                self.retry_config.__dict__ if self.retry_config else None
            ),
            "default_timeout": self.default_timeout,
            "file_operation_timeout": self.file_operation_timeout,
            "branch_operation_timeout": self.branch_operation_timeout,
            "batch_operation_timeout": self.batch_operation_timeout,
            "git_command_timeout": self.git_command_timeout,
            "file_operation_retries": self.file_operation_retries,
            "branch_operation_retries": self.branch_operation_retries,
            "batch_operation_retries": self.batch_operation_retries,
            "git_command_retries": self.git_command_retries,
            "log_level": self.log_level,
            "log_operations": self.log_operations,
            "log_errors": self.log_errors,
            "log_performance": self.log_performance,
            "enable_metrics": self.enable_metrics,
            "enable_tracing": self.enable_tracing,
            "provider_settings": self.provider_settings,
            "custom_settings": self.custom_settings,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubOperationConfig":
        """Create configuration from dictionary."""
        # Extract circuit breaker config
        circuit_breaker_config = None
        if data.get("circuit_breaker_config"):
            circuit_breaker_config = CircuitBreakerConfig(**data["circuit_breaker_config"])
        
        # Extract retry config
        retry_config = None
        if data.get("retry_config"):
            retry_config = RetryConfig(**data["retry_config"])
        
        return cls(
            operation_name=data["operation_name"],
            provider_type=data["provider_type"],
            error_handling_enabled=data.get("error_handling_enabled", True),
            circuit_breaker_config=circuit_breaker_config,
            retry_config=retry_config,
            default_timeout=data.get("default_timeout", 30.0),
            file_operation_timeout=data.get("file_operation_timeout", 60.0),
            branch_operation_timeout=data.get("branch_operation_timeout", 45.0),
            batch_operation_timeout=data.get("batch_operation_timeout", 120.0),
            git_command_timeout=data.get("git_command_timeout", 30.0),
            file_operation_retries=data.get("file_operation_retries", 3),
            branch_operation_retries=data.get("branch_operation_retries", 2),
            batch_operation_retries=data.get("batch_operation_retries", 1),
            git_command_retries=data.get("git_command_retries", 2),
            log_level=data.get("log_level", "INFO"),
            log_operations=data.get("log_operations", True),
            log_errors=data.get("log_errors", True),
            log_performance=data.get("log_performance", False),
            enable_metrics=data.get("enable_metrics", True),
            enable_tracing=data.get("enable_tracing", False),
            provider_settings=data.get("provider_settings", {}),
            custom_settings=data.get("custom_settings", {}),
        )


class SubOperationConfigManager:
    """Manages configuration for sub-operation modules."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize configuration manager."""
        self.logger = logger or logging.getLogger("SubOperationConfigManager")
        self._configs: Dict[str, SubOperationConfig] = {}
    
    def register_config(self, config: SubOperationConfig) -> None:
        """Register a sub-operation configuration."""
        key = f"{config.provider_type}_{config.operation_name}"
        self._configs[key] = config
        self.logger.info(f"Registered configuration for {key}")
    
    def get_config(self, provider_type: str, operation_name: str) -> Optional[SubOperationConfig]:
        """Get configuration for a specific sub-operation."""
        key = f"{provider_type}_{operation_name}"
        return self._configs.get(key)
    
    def create_default_config(
        self, 
        provider_type: str, 
        operation_name: str,
        custom_settings: Optional[Dict[str, Any]] = None
    ) -> SubOperationConfig:
        """Create default configuration for a sub-operation."""
        # Get provider-specific defaults
        provider_defaults = self._get_provider_defaults(provider_type)
        
        # Create base configuration
        config = SubOperationConfig(
            operation_name=operation_name,
            provider_type=provider_type,
            **provider_defaults
        )
        
        # Apply custom settings if provided
        if custom_settings:
            for key, value in custom_settings.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                else:
                    config.custom_settings[key] = value
        
        return config
    
    def _get_provider_defaults(self, provider_type: str) -> Dict[str, Any]:
        """Get provider-specific default settings."""
        defaults = {
            "github": {
                "file_operation_timeout": 30.0,
                "branch_operation_timeout": 30.0,
                "batch_operation_timeout": 60.0,
                "file_operation_retries": 3,
                "branch_operation_retries": 2,
                "batch_operation_retries": 1,
            },
            "gitlab": {
                "file_operation_timeout": 45.0,
                "branch_operation_timeout": 45.0,
                "batch_operation_timeout": 90.0,
                "file_operation_retries": 3,
                "branch_operation_retries": 2,
                "batch_operation_retries": 1,
            },
            "local": {
                "file_operation_timeout": 60.0,
                "branch_operation_timeout": 30.0,
                "batch_operation_timeout": 120.0,
                "git_command_timeout": 30.0,
                "file_operation_retries": 2,
                "branch_operation_retries": 1,
                "batch_operation_retries": 1,
                "git_command_retries": 2,
            }
        }
        
        return defaults.get(provider_type, {})
    
    def list_configs(self) -> List[str]:
        """List all registered configuration keys."""
        return list(self._configs.keys())
    
    def clear_configs(self) -> None:
        """Clear all registered configurations."""
        self._configs.clear()
        self.logger.info("Cleared all sub-operation configurations")


# Global configuration manager instance
_config_manager = SubOperationConfigManager()


def get_sub_operation_config(provider_type: str, operation_name: str) -> Optional[SubOperationConfig]:
    """Get sub-operation configuration."""
    return _config_manager.get_config(provider_type, operation_name)


def register_sub_operation_config(config: SubOperationConfig) -> None:
    """Register sub-operation configuration."""
    _config_manager.register_config(config)


def create_sub_operation_config(
    provider_type: str, 
    operation_name: str,
    custom_settings: Optional[Dict[str, Any]] = None
) -> SubOperationConfig:
    """Create sub-operation configuration."""
    return _config_manager.create_default_config(provider_type, operation_name, custom_settings)
