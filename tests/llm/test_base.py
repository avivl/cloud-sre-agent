# tests/llm/test_base.py

"""
Tests for the base LLM provider interfaces and data models.
"""

import asyncio
from typing import List
from unittest.mock import Mock

import pytest

from gemini_sre_agent.llm.base import (
    CircuitBreaker,
    ErrorSeverity,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    ModelType,
    ProviderType,
)


class MockProvider(LLMProvider):
    """Mock provider for testing."""

    def __init__(self, config: str) -> None:
        super().__init__(config)
        self.mock_responses = []
        self.mock_stream_responses = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if self.mock_responses:
            return self.mock_responses.pop(0)
        return LLMResponse(
            content="Mock response", provider=self.provider_name, model="mock-model"
        )

    async def generate_stream(self, request: LLMRequest):
        for response in self.mock_stream_responses:
            yield response

    async def health_check(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        """
        Supports Streaming.

        Returns:
            bool: Description of return value.

        """
        return True

    def supports_tools(self) -> bool:
        """
        Supports Tools.

        Returns:
            bool: Description of return value.

        """
        return False

    def get_available_models(self) -> None:
        """
        Get Available Models.

        """
        return {ModelType.SMART: "mock-model"}

    async def embeddings(self, text: str) -> List[float]:
        return [0.1] * 768

    def token_count(self, text: str) -> int:
        """
        Token Count.

        Args:
            text: str: Description of text: str.

        Returns:
            int: Description of return value.

        """
        return len(text.split())

    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """
        Cost Estimate.

        Args:
            input_tokens: int: Description of input_tokens: int.
            output_tokens: int: Description of output_tokens: int.

        Returns:
            float: Description of return value.

        """
        return 0.001

    @classmethod
    def validate_config(cls: str, config: str) -> None:
        """
        Validate Config.

        Args:
            cls: Description of cls.
            config: Description of config.

        """
        pass


class TestLLMRequest:
    """Test LLMRequest data model."""

    def test_llm_request_creation(self) -> None:
        """Test basic LLMRequest creation."""
        request = LLMRequest(prompt="Test prompt", temperature=0.8, max_tokens=500)

        assert request.prompt == "Test prompt"
        assert request.temperature == 0.8
        assert request.max_tokens == 500
        assert request.stream is False
        assert request.model_type is None

    def test_llm_request_with_model_type(self) -> None:
        """Test LLMRequest with model type."""
        request = LLMRequest(prompt="Test prompt", model_type=ModelType.FAST)

        assert request.model_type == ModelType.FAST


class TestLLMResponse:
    """Test LLMResponse data model."""

    def test_llm_response_creation(self) -> None:
        """Test basic LLMResponse creation."""
        response = LLMResponse(
            content="Test response", provider="test-provider", model="test-model"
        )

        assert response.content == "Test response"
        assert response.provider == "test-provider"
        assert response.model == "test-model"
        assert response.usage is None


class TestLLMProviderError:
    """Test LLMProviderError exception."""

    def test_error_creation(self) -> None:
        """Test basic error creation."""
        error = LLMProviderError("Test error")

        assert str(error) == "Test error"
        assert error.severity == ErrorSeverity.TRANSIENT
        assert error.retry_after is None

    def test_error_with_severity(self) -> None:
        """Test error with custom severity."""
        error = LLMProviderError(
            "Critical error", severity=ErrorSeverity.CRITICAL, retry_after=60
        )

        assert error.severity == ErrorSeverity.CRITICAL
        assert error.retry_after == 60


class TestCircuitBreaker:
    """Test CircuitBreaker functionality."""

    def test_circuit_breaker_initial_state(self) -> None:
        """Test circuit breaker initial state."""
        cb = CircuitBreaker()

        assert cb.state == "closed"
        assert cb.failure_count == 0
        assert cb.is_available() is True

    def test_circuit_breaker_success(self) -> None:
        """Test circuit breaker success handling."""
        cb = CircuitBreaker()

        cb.call_succeeded()

        assert cb.state == "closed"
        assert cb.failure_count == 0
        assert cb.is_available() is True

    def test_circuit_breaker_failure(self) -> None:
        """Test circuit breaker failure handling."""
        cb = CircuitBreaker(failure_threshold=2)

        cb.call_failed()
        assert cb.state == "closed"
        assert cb.is_available() is True

        cb.call_failed()
        assert cb.state == "open"
        assert cb.is_available() is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)

        cb.call_failed()
        assert cb.state == "open"
        assert cb.is_available() is False

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Check if available (which should trigger state change to half-open)
        assert cb.is_available() is True
        assert cb.state == "half-open"


class TestLLMProvider:
    """Test LLMProvider abstract base class."""

    def test_provider_initialization(self) -> None:
        """Test provider initialization."""
        config = Mock()
        config.provider = ProviderType.GEMINI
        config.model = "test-model"
        config.max_retries = 3

        provider = MockProvider(config)

        assert provider.provider_type == ProviderType.GEMINI
        assert provider.model == "test-model"
        assert provider.provider_name == "gemini"
        assert isinstance(provider.circuit_breaker, CircuitBreaker)

    @pytest.mark.asyncio
    async def test_provider_generate(self):
        """Test provider generate method."""
        config = Mock()
        config.provider = ProviderType.GEMINI
        config.model = "test-model"
        config.max_retries = 3

        provider = MockProvider(config)
        request = LLMRequest(prompt="Test prompt")

        response = await provider.generate(request)

        assert isinstance(response, LLMResponse)
        assert response.content == "Mock response"
        assert response.provider == "gemini"

    @pytest.mark.asyncio
    async def test_provider_health_check(self):
        """Test provider health check."""
        config = Mock()
        config.provider = ProviderType.GEMINI
        config.model = "test-model"
        config.max_retries = 3

        provider = MockProvider(config)

        is_healthy = await provider.health_check()

        assert is_healthy is True

    def test_provider_capabilities(self) -> None:
        """Test provider capability methods."""
        config = Mock()
        config.provider = ProviderType.GEMINI
        config.model = "test-model"
        config.max_retries = 3

        provider = MockProvider(config)

        assert provider.supports_streaming() is True
        assert provider.supports_tools() is False

        models = provider.get_available_models()
        assert ModelType.SMART in models
        assert models[ModelType.SMART] == "mock-model"
