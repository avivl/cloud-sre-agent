# gemini_sre_agent/llm/error_config.py

"""
Configuration classes and core types for error handling system.

This module provides Pydantic configuration models and core data types
for the error handling, circuit breaker, and deduplication components.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from pydantic import BaseModel


class ErrorCategory(Enum):
    """Categorization of different error types for appropriate handling."""
    TRANSIENT = auto()           # Retry with same provider
    PROVIDER_FAILURE = auto()    # Try fallback provider
    PERMANENT = auto()           # Don't retry
    RATE_LIMITED = auto()        # Backoff and retry
    QUOTA_EXCEEDED = auto()      # Switch to different provider
    AUTHENTICATION = auto()      # Check credentials
    TIMEOUT = auto()             # Retry with longer timeout
    NETWORK = auto()             # Retry with exponential backoff


@dataclass
class RequestContext:
    """Context information for error handling."""
    provider_id: str
    request_id: str
    model: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    reset_timeout: float = 60.0  # seconds
    half_open_max_calls: int = 3


class DeduplicationConfig(BaseModel):
    """Configuration for request deduplication."""
    ttl: float = 300.0  # seconds
    enabled: bool = True


class ErrorHandlerConfig(BaseModel):
    """Configuration for error handler."""
    circuit_breaker_config: CircuitBreakerConfig = CircuitBreakerConfig()
    deduplication_config: DeduplicationConfig = DeduplicationConfig()
    max_retries: int = 3
    retry_delay_base: float = 1.0  # seconds
    retry_delay_max: float = 30.0  # seconds
