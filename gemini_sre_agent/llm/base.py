# gemini_sre_agent/llm/base.py

"""
Core interfaces and data models for the multi-LLM provider system.

This module defines the abstract base classes, data models, and core
functionality that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from typing import Any

from gemini_sre_agent.metrics import get_metrics_manager
from gemini_sre_agent.metrics.enums import ErrorCategory

from .capabilities.models import ModelCapability
from .common.enums import ModelType

logger = logging.getLogger(__name__)


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
        retry_after: int | None = None,
    ):
        super().__init__(message)
        self.severity = severity
        self.retry_after = retry_after


@dataclass
class LLMRequest:
    """Request model for LLM generation."""

    prompt: str | None = None
    messages: list[dict[str, str]] | None = None
    temperature: float = 0.7
    max_tokens: int = 1000
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    provider_specific: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    model_type: ModelType | None = None  # Semantic model selection


@dataclass
class LLMResponse:
    """Response model for LLM generation."""

    content: str
    usage: dict[str, int] | None = None
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    provider: str = ""
    model: str = ""
    model_type: ModelType | None = None
    request_id: str | None = None
    latency_ms: float | None = None
    cost_usd: float | None = None


class CircuitBreaker:
    """Circuit breaker pattern for provider resilience."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def call_succeeded(self) -> None:
        """Record a successful call."""
        self.failure_count = 0
        self.state = "closed"

    def call_failed(self) -> None:
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

    def __init__(self, config: Any) -> None:
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

            try:
                await metrics_manager.record_provider_request(
                    provider_id=self.provider_name,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    success=True,
                )
            except Exception as metrics_e:
                logger.error(f"Error recording successful metrics: {metrics_e}")
            response.latency_ms = latency_ms
            response.cost_usd = cost
            self.circuit_breaker.call_succeeded()
            return response
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_category = self._categorize_error(e)
            try:
                await metrics_manager.record_provider_request(
                    provider_id=self.provider_name,
                    latency_ms=latency_ms,
                    input_tokens=0,  # Or estimate from request
                    output_tokens=0,
                    cost=0,
                    success=False,
                    error_info={"error": str(e), "category": error_category.value},
                )
            except Exception as metrics_e:
                logger.error(f"Error recording failed metrics: {metrics_e}")
            self.circuit_breaker.call_failed()
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
    def get_available_models(self) -> dict[ModelType, str]:
        """Get available models mapped to semantic types."""
        pass

    @abstractmethod
    async def embeddings(self, text: str) -> list[float]:
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

    @abstractmethod
    def get_custom_capabilities(self) -> list[ModelCapability]:
        """
        Get provider-specific custom capabilities.

        Returns:
            A list of ModelCapability objects.
        """
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
