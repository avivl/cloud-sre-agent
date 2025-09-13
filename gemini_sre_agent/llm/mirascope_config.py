# gemini_sre_agent/llm/mirascope_config.py

"""
Mirascope Integration Configuration Module

This module provides configuration management for Mirascope integration,
including provider settings, prompt templates, and integration parameters.
"""

from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ProviderType(Enum):
    """Supported Mirascope provider types."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    COHERE = "cohere"
    MISTRAL = "mistral"


class PromptType(Enum):
    """Types of prompts supported."""

    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    FUNCTION_CALLING = "function_calling"
    STRUCTURED_OUTPUT = "structured_output"


class Environment(Enum):
    """Deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class ProviderConfig:
    """Configuration for a specific provider."""

    provider_type: ProviderType
    api_key: str
    base_url: str | None = None
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 1000
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    custom_headers: dict[str, str] = field(default_factory=dict)
    additional_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "provider_type": self.provider_type.value,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts,
            "retry_delay": self.retry_delay,
            "custom_headers": self.custom_headers,
            "additional_params": self.additional_params,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderConfig":
        """Create from dictionary."""
        return cls(
            provider_type=ProviderType(data["provider_type"]),
            api_key=data["api_key"],
            base_url=data.get("base_url"),
            model=data.get("model", "gpt-3.5-turbo"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 1000),
            timeout=data.get("timeout", 30),
            retry_attempts=data.get("retry_attempts", 3),
            retry_delay=data.get("retry_delay", 1.0),
            custom_headers=data.get("custom_headers", {}),
            additional_params=data.get("additional_params", {}),
        )


@dataclass
class PromptTemplateConfig:
    """Configuration for prompt templates."""

    template_id: str
    name: str
    description: str | None = None
    prompt_type: PromptType = PromptType.CHAT
    template: str = ""
    variables: list[str] = field(default_factory=list)
    validation_rules: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate_variables(self, provided_vars: dict[str, Any]) -> bool:
        """Validate that all required variables are provided."""
        missing_vars = set(self.variables) - set(provided_vars.keys())
        return len(missing_vars) == 0

    def get_missing_variables(self, provided_vars: dict[str, Any]) -> list[str]:
        """Get list of missing required variables."""
        return list(set(self.variables) - set(provided_vars.keys()))


class MirascopeIntegrationConfig(BaseModel):
    """Main configuration for Mirascope integration."""

    # Storage configuration
    storage_path: str = "./mirascope_data"
    prompts_file: str = "prompts.json"
    analytics_file: str = "analytics.json"
    cache_file: str = "cache.json"

    # Provider configurations
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    default_provider: str | None = None

    # Prompt management
    enable_versioning: bool = True
    enable_analytics: bool = True
    enable_caching: bool = True
    cache_ttl: int = 3600  # seconds

    # A/B testing
    enable_ab_testing: bool = True
    ab_test_duration: int = 7  # days
    ab_test_traffic_split: float = 0.5

    # Performance monitoring
    enable_performance_monitoring: bool = True
    performance_threshold_ms: float = 5000.0
    error_rate_threshold: float = 0.05

    # Security
    enable_encryption: bool = False
    encryption_key: str | None = None

    # Logging
    log_level: str = "INFO"
    log_requests: bool = True
    log_responses: bool = False

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        validate_assignment = True


class ConfigurationManager:
    """Manages Mirascope integration configuration."""

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize configuration manager."""
        self.config_path = (
            Path(config_path) if config_path else Path("./mirascope_config.json")
        )
        self.config: MirascopeIntegrationConfig | None = None
        self.logger = logging.getLogger(__name__)
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file or create default."""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                    self.config = MirascopeIntegrationConfig(**data)
                self.logger.info(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                self.logger.error(f"Error loading configuration: {e}")
                self.config = MirascopeIntegrationConfig()
        else:
            self.config = MirascopeIntegrationConfig()
            self.save_config()
            self.logger.info("Created default configuration")

    def save_config(self) -> None:
        """Save current configuration to file."""
        if self.config:
            try:
                with open(self.config_path, "w") as f:
                    json.dump(self.config.model_dump(), f, indent=2)
                self.logger.info(f"Saved configuration to {self.config_path}")
            except Exception as e:
                self.logger.error(f"Error saving configuration: {e}")

    def get_config(self) -> MirascopeIntegrationConfig:
        """Get current configuration."""
        if self.config is None:
            self.config = MirascopeIntegrationConfig()
        return self.config

    def update_config(self, **kwargs) -> None:
        """Update configuration with new values."""
        if self.config:
            for key, value in kwargs.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            self.save_config()

    def add_provider(self, name: str, provider_config: ProviderConfig) -> None:
        """Add a new provider configuration."""
        if self.config:
            self.config.providers[name] = provider_config
            if not self.config.default_provider:
                self.config.default_provider = name
            self.save_config()

    def remove_provider(self, name: str) -> bool:
        """Remove a provider configuration."""
        if self.config and name in self.config.providers:
            del self.config.providers[name]
            if self.config.default_provider == name:
                self.config.default_provider = (
                    list(self.config.providers.keys())[0]
                    if self.config.providers
                    else None
                )
            self.save_config()
            return True
        return False

    def get_provider_config(self, name: str) -> ProviderConfig | None:
        """Get provider configuration by name."""
        if self.config:
            return self.config.providers.get(name)
        return None

    def get_default_provider_config(self) -> ProviderConfig | None:
        """Get default provider configuration."""
        if self.config and self.config.default_provider:
            return self.get_provider_config(self.config.default_provider)
        return None

    def validate_config(self) -> list[str]:
        """Validate current configuration and return any errors."""
        errors = []

        if not self.config:
            errors.append("Configuration not loaded")
            return errors

        # Validate providers
        if not self.config.providers:
            errors.append("No providers configured")
        else:
            for name, provider in self.config.providers.items():
                if not provider.api_key:
                    errors.append(f"Provider '{name}' missing API key")
                if not provider.model:
                    errors.append(f"Provider '{name}' missing model")

        # Validate default provider
        if (
            self.config.default_provider
            and self.config.default_provider not in self.config.providers
        ):
            errors.append(
                f"Default provider '{self.config.default_provider}' not found in providers"
            )

        # Validate storage path
        try:
            Path(self.config.storage_path).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(
                f"Cannot create storage path '{self.config.storage_path}': {e}"
            )

        # Validate thresholds
        if self.config.performance_threshold_ms <= 0:
            errors.append("Performance threshold must be positive")

        if not 0 <= self.config.error_rate_threshold <= 1:
            errors.append("Error rate threshold must be between 0 and 1")

        if not 0 <= self.config.ab_test_traffic_split <= 1:
            errors.append("A/B test traffic split must be between 0 and 1")

        return errors

    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self.config = MirascopeIntegrationConfig()
        self.save_config()
        self.logger.info("Configuration reset to defaults")

    def export_config(self, file_path: str) -> bool:
        """Export configuration to a file."""
        try:
            if self.config:
                with open(file_path, "w") as f:
                    json.dump(self.config.model_dump(), f, indent=2)
                self.logger.info(f"Configuration exported to {file_path}")
                return True
        except Exception as e:
            self.logger.error(f"Error exporting configuration: {e}")
        return False

    def import_config(self, file_path: str) -> bool:
        """Import configuration from a file."""
        try:
            with open(file_path) as f:
                data = json.load(f)
                self.config = MirascopeIntegrationConfig(**data)
            self.save_config()
            self.logger.info(f"Configuration imported from {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error importing configuration: {e}")
        return False


# Global configuration manager instance
_config_manager: ConfigurationManager | None = None


def get_config_manager(config_path: str | None = None) -> ConfigurationManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager(config_path)
    return _config_manager


def get_config() -> MirascopeIntegrationConfig:
    """Get the current configuration."""
    return get_config_manager().get_config()
