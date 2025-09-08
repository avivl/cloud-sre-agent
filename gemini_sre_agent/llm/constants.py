# gemini_sre_agent/llm/constants.py

"""
Constants for LLM operations and configurations.
"""

# Timeout constants
DEFAULT_TIMEOUT_SECONDS = 30
HEALTH_CHECK_TIMEOUT_SECONDS = 10
CACHE_TTL_SECONDS = 3600

# Resource limits
MAX_CONCURRENT_REQUESTS = 5
MAX_PROMPT_LENGTH = 50000
MAX_MODEL_CONFIGS = 10
MAX_CONTEXT_SIZE = 10000
MAX_LATENCY_SAMPLES = 1000

# Cost and performance thresholds
DEFAULT_COST_THRESHOLD = 1.0
ERROR_RATE_THRESHOLD = 0.1
COST_OPTIMIZATION_THRESHOLD = 0.8

# Retry configuration
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 60.0

# Monitoring and metrics
METRICS_RETENTION_HOURS = 24
HEALTH_CHECK_INTERVAL_SECONDS = 30
DASHBOARD_PORT = 8080
DASHBOARD_HOST = "localhost"

# Security settings
RATE_LIMIT_PER_MINUTE = 100
MAX_REQUEST_SIZE_BYTES = 1024 * 1024  # 1MB

# Model mixing weights
DEFAULT_PERFORMANCE_WEIGHT = 0.4
DEFAULT_COST_WEIGHT = 0.3
DEFAULT_QUALITY_WEIGHT = 0.3

# Logging
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "json"

# Provider-specific limits
OPENAI_MAX_TOKENS = 4096
ANTHROPIC_MAX_TOKENS = 4096
GOOGLE_MAX_TOKENS = 4096

# Task decomposition
MAX_SUBTASKS = 10
MIN_SUBTASK_LENGTH = 10
MAX_SUBTASK_LENGTH = 1000

# Result aggregation
MAX_AGGREGATION_ATTEMPTS = 3
AGGREGATION_TIMEOUT_SECONDS = 60

# Context sharing
MAX_CONTEXT_ENTRIES = 100
CONTEXT_TTL_SECONDS = 1800  # 30 minutes

# Error handling
MAX_ERROR_MESSAGE_LENGTH = 1000
ERROR_RETRY_BACKOFF_FACTOR = 2.0

# Performance monitoring
LATENCY_PERCENTILES = [50, 95, 99]
PERFORMANCE_WINDOW_SIZE = 100

# Cost tracking
COST_PRECISION_DECIMALS = 6
BUDGET_ALERT_THRESHOLD = 0.8  # Alert when 80% of budget is used

# Health check thresholds
HEALTHY_RESPONSE_TIME_MS = 5000
HEALTHY_SUCCESS_RATE = 0.95
HEALTHY_ERROR_RATE = 0.05

# Model selection
MIN_MODEL_CONFIDENCE = 0.7
MAX_MODEL_SELECTION_ATTEMPTS = 3

# Caching
CACHE_KEY_PREFIX = "llm_cache"
CACHE_VERSION = "1.0"

# API endpoints
HEALTH_ENDPOINT = "/health"
METRICS_ENDPOINT = "/metrics"
DASHBOARD_ENDPOINT = "/dashboard"
API_VERSION = "v1"

# File and data limits
MAX_CONFIG_FILE_SIZE = 1024 * 1024  # 1MB
MAX_LOG_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_BACKUP_FILES = 10

# Network settings
DEFAULT_CONNECTION_TIMEOUT = 30
DEFAULT_READ_TIMEOUT = 60
MAX_CONNECTIONS_PER_HOST = 10

# Validation patterns
VALID_PROVIDER_NAMES = ["openai", "anthropic", "google", "claude", "gemini"]
VALID_MODEL_TYPES = ["smart", "fast", "creative", "analytical"]
VALID_TASK_TYPES = [
    "text_generation",
    "code_generation",
    "data_processing",
    "creative_writing",
    "analysis",
    "translation",
    "summarization",
]

# Environment variables
ENV_PREFIX = "GEMINI_SRE_AGENT_"
CONFIG_FILE_ENV = f"{ENV_PREFIX}CONFIG_FILE"
LOG_LEVEL_ENV = f"{ENV_PREFIX}LOG_LEVEL"
DEBUG_ENV = f"{ENV_PREFIX}DEBUG"


class DynamicConstants:
    """Dynamic constants that can be overridden by environment variables."""

    def __init__(self):
        import os

        self.MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
        self.MAX_PROMPT_LENGTH = int(os.getenv("MAX_PROMPT_LENGTH", "50000"))
        self.DEFAULT_TIMEOUT_SECONDS = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "30"))
        self.HEALTH_CHECK_TIMEOUT_SECONDS = int(
            os.getenv("HEALTH_CHECK_TIMEOUT_SECONDS", "10")
        )
        self.CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
        self.MAX_MODEL_CONFIGS = int(os.getenv("MAX_MODEL_CONFIGS", "10"))
        self.MAX_CONTEXT_SIZE = int(os.getenv("MAX_CONTEXT_SIZE", "10000"))
        self.MAX_LATENCY_SAMPLES = int(os.getenv("MAX_LATENCY_SAMPLES", "1000"))
        self.DEFAULT_COST_THRESHOLD = float(os.getenv("DEFAULT_COST_THRESHOLD", "1.0"))
        self.ERROR_RATE_THRESHOLD = float(os.getenv("ERROR_RATE_THRESHOLD", "0.1"))
        self.DEFAULT_RETRY_ATTEMPTS = int(os.getenv("DEFAULT_RETRY_ATTEMPTS", "3"))
        self.DEFAULT_RETRY_DELAY_SECONDS = int(
            os.getenv("DEFAULT_RETRY_DELAY_SECONDS", "1")
        )
        self.METRICS_RETENTION_HOURS = int(os.getenv("METRICS_RETENTION_HOURS", "24"))
        self.HEALTH_CHECK_INTERVAL_SECONDS = int(
            os.getenv("HEALTH_CHECK_INTERVAL_SECONDS", "30")
        )

        # Validate configuration values
        self.validate()

    def validate(self):
        """Validate configuration values."""
        if self.MAX_CONCURRENT_REQUESTS <= 0:
            raise ValueError("MAX_CONCURRENT_REQUESTS must be positive")
        if self.MAX_PROMPT_LENGTH <= 0:
            raise ValueError("MAX_PROMPT_LENGTH must be positive")
        if self.DEFAULT_TIMEOUT_SECONDS <= 0:
            raise ValueError("DEFAULT_TIMEOUT_SECONDS must be positive")
        if self.HEALTH_CHECK_TIMEOUT_SECONDS <= 0:
            raise ValueError("HEALTH_CHECK_TIMEOUT_SECONDS must be positive")
        if self.CACHE_TTL_SECONDS <= 0:
            raise ValueError("CACHE_TTL_SECONDS must be positive")
        if self.MAX_MODEL_CONFIGS <= 0:
            raise ValueError("MAX_MODEL_CONFIGS must be positive")
        if self.MAX_CONTEXT_SIZE <= 0:
            raise ValueError("MAX_CONTEXT_SIZE must be positive")
        if self.MAX_LATENCY_SAMPLES <= 0:
            raise ValueError("MAX_LATENCY_SAMPLES must be positive")
        if self.DEFAULT_COST_THRESHOLD < 0:
            raise ValueError("DEFAULT_COST_THRESHOLD must be non-negative")
        if not 0 <= self.ERROR_RATE_THRESHOLD <= 1:
            raise ValueError("ERROR_RATE_THRESHOLD must be between 0 and 1")
        if self.DEFAULT_RETRY_ATTEMPTS < 0:
            raise ValueError("DEFAULT_RETRY_ATTEMPTS must be non-negative")
        if self.DEFAULT_RETRY_DELAY_SECONDS < 0:
            raise ValueError("DEFAULT_RETRY_DELAY_SECONDS must be non-negative")
        if self.METRICS_RETENTION_HOURS <= 0:
            raise ValueError("METRICS_RETENTION_HOURS must be positive")
        if self.HEALTH_CHECK_INTERVAL_SECONDS <= 0:
            raise ValueError("HEALTH_CHECK_INTERVAL_SECONDS must be positive")

    def get_config_summary(self) -> dict:
        """Get a summary of current configuration."""
        return {
            "max_concurrent_requests": self.MAX_CONCURRENT_REQUESTS,
            "max_prompt_length": self.MAX_PROMPT_LENGTH,
            "default_timeout_seconds": self.DEFAULT_TIMEOUT_SECONDS,
            "health_check_timeout_seconds": self.HEALTH_CHECK_TIMEOUT_SECONDS,
            "cache_ttl_seconds": self.CACHE_TTL_SECONDS,
            "max_model_configs": self.MAX_MODEL_CONFIGS,
            "max_context_size": self.MAX_CONTEXT_SIZE,
            "max_latency_samples": self.MAX_LATENCY_SAMPLES,
            "default_cost_threshold": self.DEFAULT_COST_THRESHOLD,
            "error_rate_threshold": self.ERROR_RATE_THRESHOLD,
            "default_retry_attempts": self.DEFAULT_RETRY_ATTEMPTS,
            "default_retry_delay_seconds": self.DEFAULT_RETRY_DELAY_SECONDS,
            "metrics_retention_hours": self.METRICS_RETENTION_HOURS,
            "health_check_interval_seconds": self.HEALTH_CHECK_INTERVAL_SECONDS,
        }


# Provider-specific configurations
PROVIDER_CONFIGS = {
    "openai": {
        "gpt-4": {"max_tokens": 8192, "context_window": 128000},
        "gpt-4-turbo": {"max_tokens": 4096, "context_window": 128000},
        "gpt-3.5-turbo": {"max_tokens": 4096, "context_window": 16385},
        "gpt-3.5-turbo-16k": {"max_tokens": 16384, "context_window": 16385},
    },
    "anthropic": {
        "claude-3-opus": {"max_tokens": 4096, "context_window": 200000},
        "claude-3-sonnet": {"max_tokens": 4096, "context_window": 200000},
        "claude-3-haiku": {"max_tokens": 4096, "context_window": 200000},
        "claude-2": {"max_tokens": 4096, "context_window": 100000},
    },
    "google": {
        "gemini-1.5-pro": {"max_tokens": 8192, "context_window": 2000000},
        "gemini-1.5-flash": {"max_tokens": 8192, "context_window": 1000000},
        "gemini-pro": {"max_tokens": 2048, "context_window": 30720},
    },
    "cohere": {
        "command": {"max_tokens": 4096, "context_window": 4096},
        "command-light": {"max_tokens": 4096, "context_window": 4096},
        "command-nightly": {"max_tokens": 4096, "context_window": 4096},
    },
    "mistral": {
        "mistral-large": {"max_tokens": 32768, "context_window": 32768},
        "mistral-medium": {"max_tokens": 32768, "context_window": 32768},
        "mistral-small": {"max_tokens": 32768, "context_window": 32768},
    },
    "meta": {
        "llama-2-70b": {"max_tokens": 4096, "context_window": 4096},
        "llama-2-13b": {"max_tokens": 4096, "context_window": 4096},
        "llama-2-7b": {"max_tokens": 4096, "context_window": 4096},
    },
}


def get_provider_config(provider: str, model: str) -> dict:
    """Get provider-specific configuration for a model."""
    return PROVIDER_CONFIGS.get(provider, {}).get(
        model, {"max_tokens": 4096, "context_window": 4096}
    )


def get_max_tokens(provider: str, model: str) -> int:
    """Get maximum tokens for a specific provider/model combination."""
    config = get_provider_config(provider, model)
    return config.get("max_tokens", 4096)


def get_context_window(provider: str, model: str) -> int:
    """Get context window size for a specific provider/model combination."""
    config = get_provider_config(provider, model)
    return config.get("context_window", 4096)


def validate_provider_model(provider: str, model: str) -> bool:
    """Validate if a provider/model combination is supported."""
    return provider in PROVIDER_CONFIGS and model in PROVIDER_CONFIGS[provider]


def get_supported_models(provider: str) -> list:
    """Get list of supported models for a provider."""
    return list(PROVIDER_CONFIGS.get(provider, {}).keys())


def get_supported_providers() -> list:
    """Get list of supported providers."""
    return list(PROVIDER_CONFIGS.keys())


# Global instance
DYNAMIC_CONFIG = DynamicConstants()
