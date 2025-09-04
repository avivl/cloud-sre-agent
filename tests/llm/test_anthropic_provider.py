# tests/llm/test_anthropic_provider.py

"""
Unit tests for AnthropicProvider.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import HttpUrl

from gemini_sre_agent.llm.providers.anthropic_provider import AnthropicProvider
from gemini_sre_agent.llm.base import LLMRequest, LLMResponse, ModelType
from gemini_sre_agent.llm.config import LLMProviderConfig


@pytest.fixture
def mock_config():
    """Create a mock configuration for Anthropic provider."""
    return LLMProviderConfig(
        provider="anthropic",
        api_key="sk-ant-test-key",
        base_url=HttpUrl("https://api.anthropic.com/"),
        region=None,
        timeout=30,
        max_retries=3,
        rate_limit=100,
        provider_specific={
            "model": "claude-3-5-sonnet-20241022",
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 1000,
        }
    )


@pytest.fixture
def provider(mock_config):
    """Create an AnthropicProvider instance with mocked dependencies."""
    with patch('gemini_sre_agent.llm.providers.anthropic_provider.anthropic.AsyncAnthropic') as mock_client:
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        provider = AnthropicProvider(mock_config)
        provider.client = mock_client_instance
        return provider


class TestAnthropicProvider:
    """Test cases for AnthropicProvider."""

    def test_provider_initialization(self, mock_config):
        """Test provider initialization."""
        with patch('gemini_sre_agent.llm.providers.anthropic_provider.anthropic.AsyncAnthropic'):
            provider = AnthropicProvider(mock_config)
            assert provider.provider_type == "anthropic"
            assert provider.model == "claude-3-5-sonnet-20241022"
            assert provider.base_url == "https://api.anthropic.com/"

    def test_get_available_models(self, provider):
        """Test getting available models."""
        models = provider.get_available_models()
        
        assert ModelType.FAST in models
        assert ModelType.SMART in models
        assert ModelType.DEEP_THINKING in models
        
        assert models[ModelType.FAST] == "claude-3-5-haiku-20241022"
        assert models[ModelType.SMART] == "claude-3-5-sonnet-20241022"
        assert models[ModelType.DEEP_THINKING] == "claude-3-5-sonnet-20241022"

    @pytest.mark.asyncio
    async def test_generate_success(self, provider):
        """Test successful text generation."""
        # Mock the client response
        mock_content = MagicMock()
        mock_content.text = "Test response"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        
        provider.client.messages.create = AsyncMock(return_value=mock_response)
        
        request = LLMRequest(
            messages=[{"role": "user", "content": "Test prompt"}],
            model_type=ModelType.FAST
        )
        
        response = await provider.generate(request)
        
        assert isinstance(response, LLMResponse)
        assert response.content == "Test response"
        assert response.usage is not None
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 5

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        """Test successful health check."""
        mock_content = MagicMock()
        mock_content.text = "Hello"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        
        provider.client.messages.create = AsyncMock(return_value=mock_response)
        
        result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, provider):
        """Test health check failure."""
        provider.client.messages.create = MagicMock(side_effect=Exception("Connection failed"))
        
        result = await provider.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_embeddings(self, provider):
        """Test embeddings generation."""
        embeddings = await provider.embeddings("Test text")
        # Anthropic doesn't provide embeddings, so should return mock
        assert len(embeddings) == 1024
        assert all(x == 0.0 for x in embeddings)

    def test_token_count(self, provider):
        """Test token counting."""
        count = provider.token_count("Test text with multiple words")
        # Should use approximation
        assert count > 0

    def test_cost_estimate(self, provider):
        """Test cost estimation."""
        cost = provider.cost_estimate(100, 50)
        # Should calculate based on Anthropic pricing
        assert cost > 0

    def test_validate_config(self, provider):
        """Test configuration validation."""
        # Create a config with valid API key
        config_with_key = LLMProviderConfig(
            provider="anthropic",
            api_key="sk-ant-test-key",
            base_url=HttpUrl("https://api.anthropic.com/"),
            region=None,
            timeout=30,
            max_retries=3,
            rate_limit=100,
            provider_specific={"model": "claude-3-5-sonnet-20241022"}
        )
        result = AnthropicProvider.validate_config(config_with_key)
        assert result is None  # validate_config doesn't return anything on success

    def test_validate_config_invalid_key(self, provider):
        """Test configuration validation with invalid API key."""
        config_with_invalid_key = LLMProviderConfig(
            provider="anthropic",
            api_key="invalid-key",
            base_url=HttpUrl("https://api.anthropic.com/"),
            region=None,
            timeout=30,
            max_retries=3,
            rate_limit=100,
            provider_specific={"model": "claude-3-5-sonnet-20241022"}
        )
        
        with pytest.raises(ValueError, match="Anthropic API key must start with 'sk-ant-'"):
            AnthropicProvider.validate_config(config_with_invalid_key)

    def test_convert_messages_to_anthropic_format(self, provider):
        """Test message format conversion."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"}
        ]
        
        anthropic_messages = provider._convert_messages_to_anthropic_format(messages)
        
        assert len(anthropic_messages) == 3
        assert anthropic_messages[0]["role"] == "user"
        assert anthropic_messages[0]["content"] == "Hello"
        assert anthropic_messages[1]["role"] == "assistant"
        assert anthropic_messages[1]["content"] == "Hi there"

    def test_extract_usage(self, provider):
        """Test usage extraction from response."""
        mock_usage = MagicMock()
        mock_usage.input_tokens = 20
        mock_usage.output_tokens = 15
        
        mock_response = MagicMock()
        mock_response.usage = mock_usage
        
        usage = provider._extract_usage(mock_response)
        assert usage["input_tokens"] == 20
        assert usage["output_tokens"] == 15
