# gemini_sre_agent/llm/config.py

"""
Configuration models for the multi-LLM provider system.

This module defines Pydantic models for configuration validation and
management of LLM providers, models, and system settings.
"""

import os
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from gemini_sre_agent.metrics.config import MetricsConfig

from .common.enums import ModelType


class ModelConfig(BaseModel):
    """Configuration for a specific model within a provider."""

    name: str = Field(..., min_length=1, description="Model name/identifier")
    model_type: ModelType
    cost_per_1k_tokens: float = Field(
        0.0, ge=0.0, description="Cost per 1000 tokens in USD"
    )
    max_tokens: int = Field(
        4000, gt=0, le=1000000, description="Maximum tokens for this model"
    )
    supports_streaming: bool = True
    supports_tools: bool = False
    capabilities: List[str] = Field(
        default_factory=list, description="List of model capabilities"
    )
    performance_score: float = Field(
        0.5, ge=0.0, le=1.0, description="Performance score (0-1)"
    )
    reliability_score: float = Field(
        0.5, ge=0.0, le=1.0, description="Reliability score (0-1)"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Model name cannot be empty")
        return v.strip()

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v):
        if v is None:
            return []
        return [cap.strip() for cap in v if cap.strip()]


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider."""

    provider: Literal[
        "gemini", "ollama", "claude", "openai", "grok", "bedrock", "anthropic"
    ]
    api_key: Optional[str] = Field(None, description="API key for the provider")
    base_url: Optional[HttpUrl] = Field(
        None, description="Base URL for the provider API"
    )
    region: Optional[str] = Field(None, description="AWS region for Bedrock provider")
    timeout: int = Field(30, gt=0, le=300, description="Request timeout in seconds")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum retry attempts")
    rate_limit: Optional[int] = Field(None, gt=0, description="Rate limit per minute")
    models: Dict[str, ModelConfig] = Field(
        default_factory=dict, description="Available models"
    )
    # ModelType to model name mappings - allows users to configure which models are used for each semantic type
    model_type_mappings: Dict[ModelType, str] = Field(
        default_factory=dict,
        description="Mapping of ModelType to specific model names for this provider",
    )
    provider_specific: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific settings"
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v, info):
        provider = info.data.get("provider")
        # Only Ollama doesn't require an API key
        if provider and provider != "ollama" and not v:
            # Try environment variable fallback
            env_key = f"{provider.upper()}_API_KEY"
            v = os.environ.get(env_key)
            if not v:
                raise ValueError(f"API key required for {provider}")
        return v

    @field_validator("region")
    @classmethod
    def validate_region(cls, v, info):
        provider = info.data.get("provider")
        if provider == "bedrock" and not v:
            raise ValueError("Region is required for Bedrock provider")
        return v

    @field_validator("models")
    @classmethod
    def validate_models(cls, v):
        if v is None:
            return {}
        # Ensure model names are valid
        for model_name in v.keys():
            if not model_name or not model_name.strip():
                raise ValueError("Model names cannot be empty")
        return v

    @field_validator("model_type_mappings")
    @classmethod
    def validate_model_type_mappings(cls, v):
        if v is None:
            return {}
        # Ensure all ModelType values are valid
        valid_model_types = {
            ModelType.FAST,
            ModelType.SMART,
            ModelType.DEEP_THINKING,
            ModelType.CODE,
            ModelType.ANALYSIS,
        }
        for model_type in v.keys():
            if model_type not in valid_model_types:
                raise ValueError(f"Invalid ModelType: {model_type}")
        return v

    @model_validator(mode="after")
    def validate_provider_config(self):
        """Post-init validation for provider configuration."""
        # Validate that model_type_mappings reference existing models
        if self.model_type_mappings:
            for model_type, model_name in self.model_type_mappings.items():
                if model_name not in self.models:
                    raise ValueError(
                        f"Model type mapping '{model_type}' references non-existent model '{model_name}'. "
                        f"Available models: {list(self.models.keys())}"
                    )

        # Validate that at least one model is configured
        if not self.models:
            raise ValueError("At least one model must be configured for the provider")

        # Validate that models have reasonable cost configurations
        for model_name, model_config in self.models.items():
            if model_config.cost_per_1k_tokens < 0:
                raise ValueError(
                    f"Model '{model_name}' has negative cost per 1k tokens"
                )
            if model_config.max_tokens <= 0:
                raise ValueError(f"Model '{model_name}' has invalid max_tokens value")

        return self


class AgentLLMConfig(BaseModel):
    """Configuration for agent-specific LLM usage."""

    # Primary model selection
    primary_provider: str = Field(
        ..., min_length=1, description="Primary provider name"
    )
    primary_model_type: ModelType = Field(
        ModelType.SMART, description="Primary model type"
    )

    # Fallback configuration
    fallback_provider: Optional[str] = Field(None, description="Fallback provider name")
    fallback_model_type: Optional[ModelType] = Field(
        None, description="Fallback model type"
    )

    # Task-specific model overrides
    model_overrides: Dict[str, Dict[str, str]] = Field(
        default_factory=dict, description="Task-specific model overrides"
    )
    # Example: {"code_generation": {"provider": "openai", "model_type": "code"}}

    # Provider-specific configuration
    provider_specific_config: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific configuration"
    )

    @field_validator("primary_provider")
    @classmethod
    def validate_primary_provider(cls, v):
        if not v or not v.strip():
            raise ValueError("Primary provider cannot be empty")
        return v.strip()

    @field_validator("fallback_provider")
    @classmethod
    def validate_fallback_provider(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Fallback provider cannot be empty")
        return v.strip() if v else None

    @field_validator("model_overrides")
    @classmethod
    def validate_model_overrides(cls, v):
        if v is None:
            return {}
        # Validate override structure
        for task_name, override in v.items():
            if not task_name or not task_name.strip():
                raise ValueError("Task names in model_overrides cannot be empty")
            if not isinstance(override, dict):
                raise ValueError(
                    f"Model override for '{task_name}' must be a dictionary"
                )
            required_keys = {"provider", "model_type"}
            if not all(key in override for key in required_keys):
                raise ValueError(
                    f"Model override for '{task_name}' must contain 'provider' and 'model_type'"
                )
        return v

    @model_validator(mode="after")
    def validate_agent_config(self):
        """Post-init validation for agent configuration."""
        # Validate that fallback provider is different from primary provider
        if self.fallback_provider and self.fallback_provider == self.primary_provider:
            raise ValueError(
                f"Fallback provider '{self.fallback_provider}' cannot be the same as primary provider"
            )

        # Validate model overrides have valid model types
        if self.model_overrides:
            valid_model_types = {
                ModelType.FAST,
                ModelType.SMART,
                ModelType.DEEP_THINKING,
                ModelType.CODE,
                ModelType.ANALYSIS,
            }
            for task_name, override in self.model_overrides.items():
                model_type_str = override.get("model_type")
                if model_type_str and model_type_str not in [
                    t.value for t in valid_model_types
                ]:
                    raise ValueError(
                        f"Invalid model type '{model_type_str}' in override for task '{task_name}'. "
                        f"Valid types: {[t.value for t in valid_model_types]}"
                    )

        return self


class CostConfig(BaseModel):
    """Cost management configuration."""

    budget_limits: Dict[str, float] = Field(
        default_factory=dict, description="Budget limits per provider in USD"
    )
    monthly_budget: Optional[float] = Field(
        None, gt=0, description="Monthly budget limit in USD"
    )
    cost_alerts: List[float] = Field(
        default_factory=list, description="Cost alert thresholds as percentages (0-100)"
    )

    @field_validator("budget_limits")
    @classmethod
    def validate_budget_limits(cls, v):
        if v is None:
            return {}
        for provider, limit in v.items():
            if not provider or not provider.strip():
                raise ValueError("Provider names in budget_limits cannot be empty")
            if limit < 0:
                raise ValueError(f"Budget limit for '{provider}' cannot be negative")
        return v

    @field_validator("cost_alerts")
    @classmethod
    def validate_cost_alerts(cls, v):
        if v is None:
            return []
        for alert in v:
            if not 0 <= alert <= 100:
                raise ValueError("Cost alerts must be between 0 and 100 (percentages)")
        return sorted(v)


class ResilienceConfig(BaseModel):
    """Resilience and reliability configuration."""

    circuit_breaker_enabled: bool = Field(
        True, description="Enable circuit breaker pattern"
    )
    circuit_breaker_threshold: int = Field(
        5, gt=0, le=100, description="Failure threshold for circuit breaker"
    )
    circuit_breaker_timeout: int = Field(
        60, gt=0, le=3600, description="Circuit breaker timeout in seconds"
    )
    retry_enabled: bool = Field(True, description="Enable retry mechanism")
    retry_attempts: int = Field(3, ge=0, le=10, description="Maximum retry attempts")
    retry_delay: float = Field(
        1.0, gt=0, le=60, description="Initial retry delay in seconds"
    )
    timeout: int = Field(30, gt=0, le=300, description="Request timeout in seconds")

    @field_validator("retry_delay")
    @classmethod
    def validate_retry_delay(cls, v):
        if v <= 0:
            raise ValueError("Retry delay must be positive")
        return v


class LLMConfig(BaseModel):
    """Main configuration for the LLM system."""

    providers: Dict[str, LLMProviderConfig] = Field(
        default_factory=dict, description="Available LLM providers"
    )
    agents: Dict[str, AgentLLMConfig] = Field(
        default_factory=dict, description="Agent-specific configurations"
    )
    default_provider: str = Field(
        "gemini", min_length=1, description="Default provider name"
    )
    default_model_type: ModelType = Field(
        ModelType.SMART, description="Default model type"
    )
    enable_fallback: bool = Field(True, description="Enable fallback mechanisms")
    enable_monitoring: bool = Field(True, description="Enable monitoring and metrics")
    cost_config: Optional[CostConfig] = Field(
        default=None,
        description="Cost management configuration",
    )
    resilience_config: Optional[ResilienceConfig] = Field(
        default=None,
        description="Resilience and reliability configuration",
    )
    metrics_config: Optional[MetricsConfig] = Field(
        default=None,
        description="Metrics system configuration",
    )

    @field_validator("default_provider")
    @classmethod
    def validate_default_provider(cls, v, info):
        if not v or not v.strip():
            raise ValueError("Default provider cannot be empty")
        v = v.strip()

        # Check if default provider exists in providers
        providers = info.data.get("providers", {})
        if providers and v not in providers:
            raise ValueError(
                f"Default provider '{v}' not found in providers configuration"
            )
        return v

    @field_validator("providers")
    @classmethod
    def validate_providers(cls, v):
        if v is None:
            return {}
        # Allow empty providers for testing/initialization
        # if not v:
        #     raise ValueError("At least one provider must be configured")

        # Ensure provider names match their provider field
        for provider_name, provider_config in v.items():
            if not provider_name or not provider_name.strip():
                raise ValueError("Provider names cannot be empty")
            if provider_config.provider != provider_name:
                raise ValueError(
                    f"Provider name '{provider_name}' must match provider field '{provider_config.provider}'"
                )
        return v

    @field_validator("agents")
    @classmethod
    def validate_agents(cls, v, info):
        if v is None:
            return {}

        providers = info.data.get("providers", {})
        for agent_name, agent_config in v.items():
            if not agent_name or not agent_name.strip():
                raise ValueError("Agent names cannot be empty")

            # Validate primary provider exists
            if agent_config.primary_provider not in providers:
                raise ValueError(
                    f"Primary provider '{agent_config.primary_provider}' for agent '{agent_name}' not found in providers"
                )

            # Validate fallback provider exists if specified
            if (
                agent_config.fallback_provider
                and agent_config.fallback_provider not in providers
            ):
                raise ValueError(
                    f"Fallback provider '{agent_config.fallback_provider}' for agent '{agent_name}' not found in providers"
                )
        return v

    @model_validator(mode="after")
    def set_default_configs(self):
        """Set default configurations if not provided."""
        if self.cost_config is None:
            self.cost_config = CostConfig(
                budget_limits={}, monthly_budget=None, cost_alerts=[]
            )
        if self.resilience_config is None:
            self.resilience_config = ResilienceConfig(
                circuit_breaker_enabled=True,
                circuit_breaker_threshold=5,
                circuit_breaker_timeout=60,
                retry_enabled=True,
                retry_attempts=3,
                retry_delay=1.0,
                timeout=30,
            )
        if self.metrics_config is None:
            self.metrics_config = MetricsConfig()
        return self
