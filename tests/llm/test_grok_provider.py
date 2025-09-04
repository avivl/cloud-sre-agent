# tests/llm/test_grok_provider.py

"""
Unit tests for Grok provider implementation.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import HttpUrl

from gemini_sre_agent.llm.base import LLMRequest, ModelType
from gemini_sre_agent.llm.config import LLMProviderConfig
from gemini_sre_agent.llm.providers.grok_provider import GrokProvider


@pytest.fixture
def mock_config():
    """Create a mock configuration for Grok provider."""
    return LLMProviderConfig(
        provider="grok",
        api_key="xai-test123456789",
        base_url=HttpUrl("https://api.x.ai/v1"),
        region=None,
        timeout=30,
        max_retries=3,
        rate_limit=None,
        provider_specific={
            "model": "grok-beta",
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 1.0,
        },
    )


@pytest.fixture
def provider(mock_config):
    """Create a Grok provider instance."""
    return GrokProvider(mock_config)


class TestGrokProvider:
    """Test cases for Grok provider."""

    def test_provider_initialization(self, provider, mock_config):
        """Test provider initialization."""
        assert provider.api_key == "xai-test123456789"
        assert str(provider.base_url) == "https://api.x.ai/v1"
        assert provider.model == "default"  # Base class sets to "default"
        assert provider.provider_name == "grok"

    def test_get_available_models(self, provider):
        """Test getting available models."""
        models = provider.get_available_models()

        assert ModelType.FAST in models
        assert ModelType.SMART in models
        assert ModelType.DEEP_THINKING in models
        assert ModelType.CODE in models
        assert ModelType.ANALYSIS in models

        assert models[ModelType.FAST] == "grok-beta"
        assert models[ModelType.SMART] == "grok-beta"
        assert models[ModelType.DEEP_THINKING] == "grok-beta"

    @pytest.mark.asyncio
    async def test_generate_success(self, provider):
        """Test successful text generation."""
        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_response.raise_for_status.return_value = None

        provider.client.post = AsyncMock(return_value=mock_response)

        request = LLMRequest(
            messages=[{"role": "user", "content": "Test prompt"}],
            model_type=ModelType.SMART,
        )

        response = await provider.generate(request)

        assert response.content == "Test response"
        assert response.model == "default"  # Base class sets to "default"
        assert response.provider == "grok"
        assert response.usage is not None
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 5

    @pytest.mark.asyncio
    async def test_generate_stream(self, provider):
        """Test streaming text generation."""

        # Create async iterator for lines
        async def mock_aiter_lines():
            lines = [
                'data: {"choices": [{"delta": {"content": "Hello"}}]}',
                'data: {"choices": [{"delta": {"content": " world"}}]}',
                "data: [DONE]",
            ]
            for line in lines:
                yield line

        # Mock streaming response
        mock_stream_response = MagicMock()
        mock_stream_response.raise_for_status.return_value = None
        mock_stream_response.aiter_lines.return_value = mock_aiter_lines()

        # Create a proper async context manager mock
        class MockAsyncContextManager:
            def __init__(self, response):
                self.response = response

            async def __aenter__(self):
                return self.response

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        # Mock the stream method to return the context manager directly
        provider.client.stream = MagicMock(
            return_value=MockAsyncContextManager(mock_stream_response)
        )

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
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        provider.client.get = AsyncMock(return_value=mock_response)

        result = await provider.health_check()

        assert result is True
        provider.client.get.assert_called_once_with("/models")

    @pytest.mark.asyncio
    async def test_health_check_failure(self, provider):
        """Test failed health check."""
        provider.client.get = AsyncMock(side_effect=Exception("API error"))

        result = await provider.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_embeddings(self, provider):
        """Test embeddings generation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        mock_response.raise_for_status.return_value = None

        provider.client.post = AsyncMock(return_value=mock_response)

        result = await provider.embeddings("Test text")

        assert result == [0.1, 0.2, 0.3]
        provider.client.post.assert_called_once_with(
            "/embeddings",
            json={"model": "grok-embedding", "input": "Test text"},
        )

    def test_token_count(self, provider):
        """Test token counting."""
        result = provider.token_count("Test text with multiple words")

        # Should use approximation: 5 words * 1.3 = 6.5 -> 6
        assert result == 6

    def test_cost_estimate(self, provider):
        """Test cost estimation."""
        cost = provider.cost_estimate(1000, 500)

        # Grok pricing: $0.10 per 1M tokens
        # Input: 1000 tokens * $0.10/1000 = $0.0001
        # Output: 500 tokens * $0.10/1000 = $0.00005
        # Total: $0.00015
        expected_cost = (1000 / 1000) * 0.0001 + (500 / 1000) * 0.0001
        assert cost == expected_cost

    def test_validate_config_valid(self, mock_config):
        """Test configuration validation with valid config."""
        # Should not raise any exception
        GrokProvider.validate_config(mock_config)

    def test_validate_config_invalid_key(self):
        """Test configuration validation with invalid API key."""
        config = LLMProviderConfig(
            provider="grok",
            api_key="invalid-key",
            base_url=HttpUrl("https://api.x.ai/v1"),
            region=None,
            timeout=30,
            max_retries=3,
            rate_limit=None,
        )

        # Grok doesn't have specific key format validation
        # Should not raise any exception
        GrokProvider.validate_config(config)

    def test_validate_config_missing_key(self):
        """Test configuration validation with missing API key."""

        # Create a mock config object that bypasses Pydantic validation
        class MockConfig:
            def __init__(self):
                self.api_key = None

        config = MockConfig()

        with pytest.raises(ValueError, match="Grok API key is required"):
            GrokProvider.validate_config(config)

    def test_convert_messages_to_grok_format(self, provider):
        """Test message format conversion."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "unknown", "content": "This should become user"},
        ]

        result = provider._convert_messages_to_grok_format(messages)

        expected = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "This should become user"},
        ]

        assert result == expected

    def test_extract_usage(self, provider):
        """Test usage extraction from response."""
        # Test with usage dict
        usage = {"prompt_tokens": 10, "completion_tokens": 5}

        result = provider._extract_usage(usage)

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
        assert provider.supports_tools() is False

    @pytest.mark.asyncio
    async def test_generate_error_handling(self, provider):
        """Test error handling in generate method."""
        provider.client.post = AsyncMock(side_effect=Exception("API error"))

        request = LLMRequest(
            messages=[{"role": "user", "content": "Test prompt"}],
            model_type=ModelType.SMART,
        )

        with pytest.raises(Exception, match="API error"):
            await provider.generate(request)

    @pytest.mark.asyncio
    async def test_embeddings_error_handling(self, provider):
        """Test error handling in embeddings method."""
        provider.client.post = AsyncMock(side_effect=Exception("Embeddings error"))

        with pytest.raises(Exception, match="Embeddings error"):
            await provider.embeddings("Test text")

    @pytest.mark.asyncio
    async def test_context_manager(self, provider):
        """Test async context manager functionality."""
        async with provider as ctx_provider:
            assert ctx_provider is provider
            # Test that client is properly closed
            assert hasattr(ctx_provider, "client")
