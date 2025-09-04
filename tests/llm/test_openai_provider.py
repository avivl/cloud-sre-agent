# tests/llm/test_openai_provider.py

"""
Unit tests for OpenAI provider implementation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import HttpUrl

from gemini_sre_agent.llm.providers.openai_provider import OpenAIProvider
from gemini_sre_agent.llm.base import LLMRequest, ModelType
from gemini_sre_agent.llm.config import LLMProviderConfig


@pytest.fixture
def mock_config():
    """Create a mock configuration for OpenAI provider."""
    return LLMProviderConfig(
        provider="openai",
        api_key="sk-test123456789",
        base_url=HttpUrl("https://api.openai.com/v1"),
        region=None,
        timeout=30,
        max_retries=3,
        rate_limit=None,
        provider_specific={
            "model": "gpt-4o",
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 1.0,
            "organization_id": "org-123",
        },
    )


@pytest.fixture
def provider(mock_config):
    """Create an OpenAI provider instance."""
    return OpenAIProvider(mock_config)


class TestOpenAIProvider:
    """Test cases for OpenAI provider."""

    def test_provider_initialization(self, provider, mock_config):
        """Test provider initialization."""
        assert provider.api_key == "sk-test123456789"
        assert str(provider.base_url) == "https://api.openai.com/v1"
        assert provider.organization == "org-123"
        assert provider.model == "default"  # Base class sets to "default"
        assert provider.provider_name == "openai"

    def test_get_available_models(self, provider):
        """Test getting available models."""
        models = provider.get_available_models()
        
        assert ModelType.FAST in models
        assert ModelType.SMART in models
        assert ModelType.DEEP_THINKING in models
        assert ModelType.CODE in models
        assert ModelType.ANALYSIS in models
        
        assert models[ModelType.FAST] == "gpt-3.5-turbo"
        assert models[ModelType.SMART] == "gpt-4o-mini"
        assert models[ModelType.DEEP_THINKING] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_generate_success(self, provider):
        """Test successful text generation."""
        # Mock the OpenAI client response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        
        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        request = LLMRequest(
            messages=[{"role": "user", "content": "Test prompt"}],
            model_type=ModelType.SMART,
        )
        
        response = await provider.generate(request)
        
        assert response.content == "Test response"
        assert response.model == "default"  # Base class sets to "default"
        assert response.provider == "openai"
        assert response.usage is not None
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 5

    @pytest.mark.asyncio
    async def test_generate_stream(self, provider):
        """Test streaming text generation."""
        # Mock streaming response
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta.content = "Hello"
        
        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = " world"
        
        async def mock_stream():
            yield mock_chunk1
            yield mock_chunk2
        
        provider.client.chat.completions.create = AsyncMock(return_value=mock_stream())
        
        request = LLMRequest(
            messages=[{"role": "user", "content": "Test prompt"}],
            model_type=ModelType.SMART,
        )
        
        chunks = []
        async for chunk in provider.generate_stream(request):
            chunks.append(chunk)
        
        assert len(chunks) == 2
        assert chunks[0].content == "Hello"
        assert chunks[1].content == " world"

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        """Test successful health check."""
        provider.client.models.list = AsyncMock()
        
        result = await provider.health_check()
        
        assert result is True
        provider.client.models.list.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, provider):
        """Test failed health check."""
        provider.client.models.list = AsyncMock(side_effect=Exception("API error"))
        
        result = await provider.health_check()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_embeddings(self, provider):
        """Test embeddings generation."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        
        provider.client.embeddings.create = AsyncMock(return_value=mock_response)
        
        result = await provider.embeddings("Test text")
        
        assert result == [0.1, 0.2, 0.3]
        provider.client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input="Test text",
        )

    def test_token_count_with_tiktoken(self, provider):
        """Test token counting with tiktoken."""
        with patch("builtins.__import__") as mock_import:
            # Mock tiktoken module
            mock_tiktoken = MagicMock()
            mock_encoder = MagicMock()
            mock_encoder.encode.return_value = [1, 2, 3, 4, 5]
            mock_tiktoken.get_encoding.return_value = mock_encoder
            
            def import_side_effect(name, *args, **kwargs):
                if name == "tiktoken":
                    return mock_tiktoken
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            result = provider.token_count("Test text")
            
            assert result == 5
            mock_tiktoken.get_encoding.assert_called_once_with("cl100k_base")

    def test_token_count_fallback(self, provider):
        """Test token counting fallback when tiktoken is not available."""
        with patch("builtins.__import__") as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == "tiktoken":
                    raise ImportError("No module named 'tiktoken'")
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            result = provider.token_count("Test text with multiple words")
            
            # Should use approximation: 5 words * 1.3 = 6.5 -> 6
            assert result == 6

    def test_cost_estimate(self, provider):
        """Test cost estimation."""
        cost = provider.cost_estimate(1000, 500)
        
        # GPT-4o pricing: $2.50/1M input, $10.00/1M output
        # Input: 1000 tokens * $2.50/1000 = $0.0025
        # Output: 500 tokens * $10.00/1000 = $0.005
        # Total: $0.0075
        expected_cost = (1000 / 1000) * 0.0025 + (500 / 1000) * 0.01
        assert cost == expected_cost

    def test_validate_config_valid(self, mock_config):
        """Test configuration validation with valid config."""
        # Should not raise any exception
        OpenAIProvider.validate_config(mock_config)

    def test_validate_config_invalid_key(self):
        """Test configuration validation with invalid API key."""
        config = LLMProviderConfig(
            provider="openai",
            api_key="invalid-key",
            base_url=HttpUrl("https://api.openai.com/v1"),
            region=None,
            timeout=30,
            max_retries=3,
            rate_limit=None,
        )
        
        with pytest.raises(ValueError, match="OpenAI API key must start with 'sk-'"):
            OpenAIProvider.validate_config(config)

    def test_validate_config_missing_key(self):
        """Test configuration validation with missing API key."""
        # Create a mock config object that bypasses Pydantic validation
        class MockConfig:
            def __init__(self):
                self.api_key = None
        
        config = MockConfig()
        
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            OpenAIProvider.validate_config(config)

    def test_convert_messages_to_openai_format(self, provider):
        """Test message format conversion."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "unknown", "content": "This should become user"},
        ]
        
        result = provider._convert_messages_to_openai_format(messages)
        
        expected = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "This should become user"},
        ]
        
        assert result == expected

    def test_extract_usage(self, provider):
        """Test usage extraction from response."""
        # Test with usage object
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 5
        
        result = provider._extract_usage(mock_usage)
        
        assert result == {"input_tokens": 10, "output_tokens": 5}

    def test_extract_usage_none(self, provider):
        """Test usage extraction with None usage."""
        result = provider._extract_usage(None)
        
        assert result == {"input_tokens": 0, "output_tokens": 0}

    def test_supports_streaming(self, provider):
        """Test streaming support."""
        assert provider.supports_streaming() is True

    def test_supports_tools(self, provider):
        """Test tool calling support."""
        assert provider.supports_tools() is True

    @pytest.mark.asyncio
    async def test_generate_error_handling(self, provider):
        """Test error handling in generate method."""
        provider.client.chat.completions.create = AsyncMock(
            side_effect=Exception("API error")
        )
        
        request = LLMRequest(
            messages=[{"role": "user", "content": "Test prompt"}],
            model_type=ModelType.SMART,
        )
        
        with pytest.raises(Exception, match="API error"):
            await provider.generate(request)

    @pytest.mark.asyncio
    async def test_embeddings_error_handling(self, provider):
        """Test error handling in embeddings method."""
        provider.client.embeddings.create = AsyncMock(
            side_effect=Exception("Embeddings error")
        )
        
        with pytest.raises(Exception, match="Embeddings error"):
            await provider.embeddings("Test text")
