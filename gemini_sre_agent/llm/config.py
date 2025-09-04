# gemini_sre_agent/llm/config.py

"""
Configuration models for the multi-LLM provider system.

This module defines Pydantic models for configuration validation and
management of LLM providers, models, and system settings.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Literal, Optional, List
import os
from .base import ModelType


class ModelConfig(BaseModel):
    """Configuration for a specific model within a provider."""
    name: str
    model_type: ModelType
    cost_per_1k_tokens: float = 0.0
    max_tokens: int = 4000
    supports_streaming: bool = True
    supports_tools: bool = False
    capabilities: List[str] = Field(default_factory=list)


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider."""
    provider: Literal["gemini", "ollama", "claude", "openai", "grok", "bedrock", "anthropic"]
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    region: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    rate_limit: Optional[int] = None
    models: Dict[str, ModelConfig] = Field(default_factory=dict)
    provider_specific: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v, info):
        provider = info.data.get('provider')
        # Only Ollama doesn't require an API key
        if provider and provider != 'ollama' and not v:
            # Try environment variable fallback
            env_key = f"{provider.upper()}_API_KEY"
            v = os.environ.get(env_key)
            if not v:
                raise ValueError(f"API key required for {provider}")
        return v


class AgentLLMConfig(BaseModel):
    """Configuration for agent-specific LLM usage."""
    # Primary model selection
    primary_provider: str
    primary_model_type: ModelType = ModelType.SMART
    
    # Fallback configuration
    fallback_provider: Optional[str] = None
    fallback_model_type: Optional[ModelType] = None
    
    # Task-specific model overrides
    model_overrides: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    # Example: {"code_generation": {"provider": "openai", "model_type": "code"}}
    
    # Provider-specific configuration
    provider_specific_config: Dict[str, Any] = Field(default_factory=dict)


class CostConfig(BaseModel):
    """Cost management configuration."""
    budget_limits: Dict[str, float] = Field(default_factory=dict)  # Per provider
    monthly_budget: Optional[float] = None
    cost_alerts: List[float] = Field(default_factory=list)  # Alert thresholds


class ResilienceConfig(BaseModel):
    """Resilience and reliability configuration."""
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60
    retry_enabled: bool = True
    retry_attempts: int = 3
    retry_delay: float = 1.0
    timeout: int = 30


class LLMConfig(BaseModel):
    """Main configuration for the LLM system."""
    providers: Dict[str, LLMProviderConfig]
    agents: Dict[str, AgentLLMConfig]
    default_provider: str = "gemini"
    default_model_type: ModelType = ModelType.SMART
    enable_fallback: bool = True
    enable_monitoring: bool = True
    cost_config: CostConfig = Field(default_factory=CostConfig)
    resilience_config: ResilienceConfig = Field(default_factory=ResilienceConfig)
