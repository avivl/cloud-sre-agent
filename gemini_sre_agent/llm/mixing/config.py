# gemini_sre_agent/llm/mixing/config.py

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class MixingStrategy(Enum):
    """Strategy for mixing multiple models."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CASCADE = "cascade"
    VOTING = "voting"


@dataclass
class ModelMixingConfig:
    """Configuration for model mixing operations."""

    # Concurrency and resource limits
    max_concurrent_requests: int = 5
    default_timeout_seconds: int = 30
    max_prompt_length: int = 50000
    max_model_configs: int = 10

    # Cost and performance settings
    enable_cost_filtering: bool = True
    cost_threshold: float = 1.0  # Maximum cost per request
    performance_weight: float = 0.4
    cost_weight: float = 0.3
    quality_weight: float = 0.3

    # Health and monitoring
    health_check_interval_seconds: int = 30
    enable_health_checks: bool = True
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0

    # Security settings
    enable_input_validation: bool = True
    enable_output_sanitization: bool = True
    max_context_size: int = 10000

    # Advanced features
    enable_adaptive_mixing: bool = False
    enable_result_caching: bool = False
    cache_ttl_seconds: int = 3600

    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.max_concurrent_requests <= 0:
            raise ValueError("max_concurrent_requests must be positive")

        if self.default_timeout_seconds <= 0:
            raise ValueError("default_timeout_seconds must be positive")

        if self.max_prompt_length <= 0:
            raise ValueError("max_prompt_length must be positive")

        if self.max_model_configs <= 0:
            raise ValueError("max_model_configs must be positive")

        if not 0 <= self.cost_threshold <= 100:
            raise ValueError("cost_threshold must be between 0 and 100")

        # Validate weights sum to approximately 1.0
        total_weight = self.performance_weight + self.cost_weight + self.quality_weight
        if not 0.95 <= total_weight <= 1.05:
            raise ValueError(
                f"Weights must sum to 1.0, got {total_weight:.3f}. "
                f"Current weights: performance={self.performance_weight}, "
                f"cost={self.cost_weight}, quality={self.quality_weight}"
            )

        if self.retry_attempts < 0:
            raise ValueError("retry_attempts must be non-negative")

        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be non-negative")

        if self.max_context_size <= 0:
            raise ValueError("max_context_size must be positive")

        if self.cache_ttl_seconds <= 0:
            raise ValueError("cache_ttl_seconds must be positive")


@dataclass
class MonitoringConfig:
    """Configuration for monitoring and observability."""

    # Metrics collection
    enable_metrics: bool = True
    metrics_retention_hours: int = 24
    max_latency_samples: int = 1000
    error_rate_threshold: float = 0.1

    # Health checks
    enable_health_checks: bool = True
    health_check_timeout: int = 10
    health_check_interval: int = 30

    # Logging
    enable_structured_logging: bool = True
    log_level: str = "INFO"
    log_format: str = "json"

    # Dashboard
    enable_dashboard: bool = True
    dashboard_port: int = 8080
    dashboard_host: str = "localhost"

    def validate(self) -> None:
        """Validate monitoring configuration."""
        if self.metrics_retention_hours <= 0:
            raise ValueError("metrics_retention_hours must be positive")

        if self.max_latency_samples <= 0:
            raise ValueError("max_latency_samples must be positive")

        if not 0 <= self.error_rate_threshold <= 1:
            raise ValueError("error_rate_threshold must be between 0 and 1")

        if self.health_check_timeout <= 0:
            raise ValueError("health_check_timeout must be positive")

        if self.health_check_interval <= 0:
            raise ValueError("health_check_interval must be positive")

        if self.dashboard_port <= 0 or self.dashboard_port > 65535:
            raise ValueError("dashboard_port must be between 1 and 65535")

        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(f"log_level must be one of {valid_log_levels}")

        valid_log_formats = ["json", "text", "structured"]
        if self.log_format.lower() not in valid_log_formats:
            raise ValueError(f"log_format must be one of {valid_log_formats}")


@dataclass
class SecurityConfig:
    """Configuration for security settings."""

    # Input validation
    enable_input_validation: bool = True
    max_prompt_length: int = 50000
    max_context_size: int = 10000
    allowed_prompt_patterns: Optional[list] = None
    blocked_prompt_patterns: Optional[list] = None

    # Authentication
    enable_authentication: bool = False
    api_key_required: bool = False
    rate_limit_per_minute: int = 100

    # Output sanitization
    enable_output_sanitization: bool = True
    sanitize_sensitive_data: bool = True

    def validate(self) -> None:
        """Validate security configuration."""
        if self.max_prompt_length <= 0:
            raise ValueError("max_prompt_length must be positive")

        if self.max_context_size <= 0:
            raise ValueError("max_context_size must be positive")

        if self.rate_limit_per_minute <= 0:
            raise ValueError("rate_limit_per_minute must be positive")

        if self.allowed_prompt_patterns is not None:
            if not isinstance(self.allowed_prompt_patterns, list):
                raise ValueError("allowed_prompt_patterns must be a list")

        if self.blocked_prompt_patterns is not None:
            if not isinstance(self.blocked_prompt_patterns, list):
                raise ValueError("blocked_prompt_patterns must be a list")


@dataclass
class IntegratedConfig:
    """Integrated configuration for all mixing and monitoring components."""

    mixing: ModelMixingConfig
    monitoring: MonitoringConfig
    security: SecurityConfig

    def __post_init__(self):
        """Validate all configurations after initialization."""
        self.mixing.validate()
        self.monitoring.validate()
        self.security.validate()

    @classmethod
    def create_default(cls) -> "IntegratedConfig":
        """Create a default configuration."""
        return cls(
            mixing=ModelMixingConfig(),
            monitoring=MonitoringConfig(),
            security=SecurityConfig(),
        )

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "IntegratedConfig":
        """Create configuration from dictionary."""
        mixing_config = ModelMixingConfig(**config_dict.get("mixing", {}))
        monitoring_config = MonitoringConfig(**config_dict.get("monitoring", {}))
        security_config = SecurityConfig(**config_dict.get("security", {}))

        return cls(
            mixing=mixing_config,
            monitoring=monitoring_config,
            security=security_config,
        )
