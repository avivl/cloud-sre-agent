# gemini_sre_agent/config/ml_config.py

"""
Unified ML configuration consolidating all ML-related settings.
"""

from enum import Enum
from typing import Dict

from pydantic import Field, field_validator

from .base import BaseConfig


class ModelType(str, Enum):
    """Supported model types."""

    TRIAGE = "triage"
    ANALYSIS = "analysis"
    CLASSIFICATION = "classification"
    CODE_GENERATION = "code_generation"
    META_PROMPT = "meta_prompt"


class ModelConfig(BaseConfig):
    """Configuration for a specific model."""

    name: str = Field(..., description="Model name (e.g., gemini-1.5-pro-001)")
    type: ModelType = Field(..., description="Model type/usage")
    max_tokens: int = Field(default=8192, ge=1, le=1000000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    retry_attempts: int = Field(default=3, ge=0, le=10)

    # Cost tracking
    cost_per_1k_tokens: float = Field(default=0.0, ge=0.0)

    @field_validator("name")
    @classmethod
    def validate_model_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Model name cannot be empty")
        return v.strip()


class CodeGenerationConfig(BaseConfig):
    """Configuration for code generation."""

    enable_validation: bool = True
    enable_specialized_generators: bool = True
    max_iterations: int = Field(default=3, ge=1, le=10)
    quality_threshold: float = Field(default=8.0, ge=0.0, le=10.0)
    human_review_threshold: float = Field(default=7.0, ge=0.0, le=10.0)
    enable_learning: bool = True


class AdaptivePromptConfig(BaseConfig):
    """Configuration for adaptive prompt strategy."""

    enable_adaptive_strategy: bool = True
    cache_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    max_cache_size: int = Field(default=1000, ge=10, le=10000)
    enable_fallback: bool = True
    strategy_switch_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class CostTrackingConfig(BaseConfig):
    """Configuration for cost tracking."""

    daily_budget_usd: float = Field(default=10.0, ge=0.0)
    monthly_budget_usd: float = Field(default=100.0, ge=0.0)
    warn_threshold_percent: float = Field(default=80.0, ge=0.0, le=100.0)
    alert_threshold_percent: float = Field(default=95.0, ge=0.0, le=100.0)
    enable_daily_reset: bool = True
    enable_monthly_reset: bool = True
    currency: str = "USD"
    model_costs: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class RateLimitingConfig(BaseConfig):
    """Configuration for rate limiting."""

    max_requests_per_minute: int = Field(default=60, ge=1)
    max_requests_per_hour: int = Field(default=1000, ge=1)
    max_concurrent_requests: int = Field(default=10, ge=1)
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = Field(default=5, ge=1)
    circuit_breaker_timeout_seconds: int = Field(default=60, ge=1)


class MLPerformanceConfig(BaseConfig):
    """Configuration for ML performance settings."""

    enable_caching: bool = True
    cache_ttl_seconds: int = Field(default=3600, ge=60)
    max_cache_size_mb: int = Field(default=100, ge=1)
    enable_parallel_processing: bool = True
    max_workers: int = Field(default=4, ge=1, le=16)


class MLConfig(BaseConfig):
    """Unified ML configuration."""

    # Model configurations
    models: Dict[ModelType, ModelConfig] = Field(default_factory=dict)

    # Code generation
    code_generation: CodeGenerationConfig = Field(default_factory=CodeGenerationConfig)

    # Adaptive prompting
    adaptive_prompt: AdaptivePromptConfig = Field(default_factory=AdaptivePromptConfig)

    # Cost tracking
    cost_tracking: CostTrackingConfig = Field(default_factory=CostTrackingConfig)

    # Rate limiting
    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)

    # Performance
    performance: MLPerformanceConfig = Field(default_factory=MLPerformanceConfig)

    @field_validator("models")
    @classmethod
    def validate_required_models(cls, v):
        """Validate that required models are configured."""
        required_models = [
            ModelType.TRIAGE,
            ModelType.ANALYSIS,
            ModelType.CLASSIFICATION,
        ]
        for model_type in required_models:
            if model_type not in v:
                raise ValueError(f"Required model '{model_type.value}' not configured")
        return v
