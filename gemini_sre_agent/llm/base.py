# gemini_sre_agent/llm/base.py

"""
Core interfaces and data models for the multi-LLM provider system.

This module defines the abstract base classes, data models, and core
functionality that all LLM providers must implement.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from gemini_sre_agent.metrics import get_metrics_manager
from gemini_sre_agent.metrics.enums import ErrorCategory

logger = logging.getLogger(__name__)


class ProviderType(str, Enum):
    """Supported LLM provider types."""

    GEMINI = "gemini"
    OLLAMA = "ollama"
    CLAUDE = "claude"
    OPENAI = "openai"
    GROK = "grok"
    BEDROCK = "bedrock"


class ModelType(str, Enum):
    """Semantic model types for easy configuration."""

    FAST = "fast"  # Quick responses, lower cost
    SMART = "smart"  # Balanced performance and quality
    DEEP_THINKING = "deep"  # Highest quality, slower responses
    CODE = "code"  # Specialized for code generation
    ANALYSIS = "analysis"  # Specialized for analysis tasks


class ErrorSeverity(Enum):
    """Error severity levels for proper handling."""

    TRANSIENT = "transient"  # Retry-able errors
    RATE_LIMIT = "rate_limit"  # Back off and retry
    AUTH = "auth"  # Non-retryable
    CRITICAL = "critical"  # Provider down


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.TRANSIENT,
        retry_after: Optional[int] = None,
    ):
        super().__init__(message)
        self.severity = severity
        self.retry_after = retry_after


@dataclass
class LLMRequest:
    """Request model for LLM generation."""

    prompt: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    provider_specific: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None
    model_type: Optional[ModelType] = None  # Semantic model selection


@dataclass
class LLMResponse:
    """Response model for LLM generation."""

    content: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    provider: str = ""
    model: str = ""
    model_type: Optional[ModelType] = None
    request_id: Optional[str] = None
    latency_ms: Optional[float] = None
    cost_usd: Optional[float] = None


class CircuitBreaker:
    """Circuit breaker pattern for provider resilience."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def call_succeeded(self):
        """Record a successful call."""
        self.failure_count = 0
        self.state = "closed"

    def call_failed(self):
        """Record a failed call."""
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            try:
                self.last_failure_time = asyncio.get_event_loop().time()
            except RuntimeError:
                # No event loop running, use time.time() as fallback
                import time

                self.last_failure_time = time.time()

    def is_available(self) -> bool:
        """Check if the circuit breaker allows calls."""
        if self.state == "closed":
            return True
        if self.state == "open":
            if self.last_failure_time is not None:
                try:
                    current_time = asyncio.get_event_loop().time()
                except RuntimeError:
                    # No event loop running, use time.time() as fallback
                    import time

                    current_time = time.time()

                if current_time - self.last_failure_time >= self.recovery_timeout:
                    self.state = "half-open"
                    return True
        return self.state == "half-open"


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, config: Any):
        self.config = config
        self.provider_type = config.provider
        # For backward compatibility, set a default model if not specified
        self.model = getattr(config, "model", None) or "default"
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.max_retries, recovery_timeout=60
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate non-streaming response with metrics."""
        return await self._generate_with_metrics(request)

    async def _generate_with_metrics(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        metrics_manager = get_metrics_manager()
        try:
            response = await self._generate(request)
            latency_ms = (time.time() - start_time) * 1000

            input_tokens = (
                response.usage.get("input_tokens", 0) if response.usage else 0
            )
            output_tokens = (
                response.usage.get("output_tokens", 0) if response.usage else 0
            )
            cost = self.cost_estimate(input_tokens, output_tokens)

            await metrics_manager.record_provider_request(
                provider_id=self.provider_name,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                success=True,
            )
            response.latency_ms = latency_ms
            response.cost_usd = cost
            return response
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_category = self._categorize_error(e)
            await metrics_manager.record_provider_request(
                provider_id=self.provider_name,
                latency_ms=latency_ms,
                input_tokens=0,  # Or estimate from request
                output_tokens=0,
                cost=0,
                success=False,
                error_info={"error": str(e), "category": error_category.value},
            )
            raise

    @abstractmethod
    async def _generate(self, request: LLMRequest) -> LLMResponse:
        """Generate non-streaming response."""
        pass

    @abstractmethod
    async def generate_stream(self, request: LLMRequest):  # type: ignore
        """Generate streaming response."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is healthy and accessible."""
        pass

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Check if provider supports streaming."""
        pass

    @abstractmethod
    def supports_tools(self) -> bool:
        """Check if provider supports tool calling."""
        pass

    @abstractmethod
    def get_available_models(self) -> Dict[ModelType, str]:
        """Get available models mapped to semantic types."""
        pass

    @abstractmethod
    async def embeddings(self, text: str) -> List[float]:
        """Generate embeddings for the given text."""
        pass

    @abstractmethod
    def token_count(self, text: str) -> int:
        """Count tokens in the given text."""
        pass

    @abstractmethod
    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for the given token usage."""
        pass

    @classmethod
    @abstractmethod
    def validate_config(cls, config: Any) -> None:
        """Validate provider-specific configuration."""
        pass

    def _categorize_error(self, e: Exception) -> ErrorCategory:
        # Basic error categorization, can be expanded
        if isinstance(e, asyncio.TimeoutError):
            return ErrorCategory.TIMEOUT
        # Add more specific error checks here based on provider exceptions
        return ErrorCategory.UNKNOWN

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return self.provider_type
