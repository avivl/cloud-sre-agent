# tests/llm/test_base.py

"""
Tests for the base LLM provider interfaces and data models.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from gemini_sre_agent.llm.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ModelType,
    ProviderType,
    ErrorSeverity,
    LLMProviderError,
    CircuitBreaker,
)


class MockProvider(LLMProvider):
    """Mock provider for testing."""
    
    def __init__(self, config):
        super().__init__(config)
        self.mock_responses = []
        self.mock_stream_responses = []
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        if self.mock_responses:
            return self.mock_responses.pop(0)
        return LLMResponse(
            content="Mock response",
            provider=self.provider_name,
            model="mock-model"
        )
    
    async def generate_stream(self, request: LLMRequest):
        for response in self.mock_stream_responses:
            yield response
    
    async def health_check(self) -> bool:
        return True
    
    def supports_streaming(self) -> bool:
        return True
    
    def supports_tools(self) -> bool:
        return False
    
    def get_available_models(self):
        return {ModelType.SMART: "mock-model"}
    
    @classmethod
    def validate_config(cls, config):
        pass


class TestLLMRequest:
    """Test LLMRequest data model."""
    
    def test_llm_request_creation(self):
        """Test basic LLMRequest creation."""
        request = LLMRequest(
            prompt="Test prompt",
            temperature=0.8,
            max_tokens=500
        )
        
        assert request.prompt == "Test prompt"
        assert request.temperature == 0.8
        assert request.max_tokens == 500
        assert request.stream is False
        assert request.model_type is None
    
    def test_llm_request_with_model_type(self):
        """Test LLMRequest with model type."""
        request = LLMRequest(
            prompt="Test prompt",
            model_type=ModelType.FAST
        )
        
        assert request.model_type == ModelType.FAST


class TestLLMResponse:
    """Test LLMResponse data model."""
    
    def test_llm_response_creation(self):
        """Test basic LLMResponse creation."""
        response = LLMResponse(
            content="Test response",
            provider="test-provider",
            model="test-model"
        )
        
        assert response.content == "Test response"
        assert response.provider == "test-provider"
        assert response.model == "test-model"
        assert response.usage is None


class TestLLMProviderError:
    """Test LLMProviderError exception."""
    
    def test_error_creation(self):
        """Test basic error creation."""
        error = LLMProviderError("Test error")
        
        assert str(error) == "Test error"
        assert error.severity == ErrorSeverity.TRANSIENT
        assert error.retry_after is None
    
    def test_error_with_severity(self):
        """Test error with custom severity."""
        error = LLMProviderError(
            "Critical error",
            severity=ErrorSeverity.CRITICAL,
            retry_after=60
        )
        
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.retry_after == 60


class TestCircuitBreaker:
    """Test CircuitBreaker functionality."""
    
    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker initial state."""
        cb = CircuitBreaker()
        
        assert cb.state == "closed"
        assert cb.failure_count == 0
        assert cb.is_available() is True
    
    def test_circuit_breaker_success(self):
        """Test circuit breaker success handling."""
        cb = CircuitBreaker()
        
        cb.call_succeeded()
        
        assert cb.state == "closed"
        assert cb.failure_count == 0
        assert cb.is_available() is True
    
    def test_circuit_breaker_failure(self):
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
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        cb.call_failed()
        assert cb.state == "open"
        assert cb.is_available() is False
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Check if available (which should trigger state change to half-open)
        assert cb.is_available() is True
        assert cb.state == "half-open"


class TestLLMProvider:
    """Test LLMProvider abstract base class."""
    
    def test_provider_initialization(self):
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
    
    def test_provider_capabilities(self):
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
