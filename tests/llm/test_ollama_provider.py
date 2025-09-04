# tests/llm/test_ollama_provider.py

"""
Unit tests for OllamaProvider.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import HttpUrl

from gemini_sre_agent.llm.base import LLMRequest, LLMResponse, ModelType
from gemini_sre_agent.llm.config import LLMProviderConfig
from gemini_sre_agent.llm.providers.ollama_provider import OllamaProvider


@pytest.fixture
def mock_config():
    """Create a mock configuration for Ollama provider."""
    return LLMProviderConfig(
        provider="ollama",
        api_key="test-key",
        base_url=HttpUrl("http://localhost:11434/"),
        region=None,
        timeout=30,
        max_retries=3,
        rate_limit=100,
        provider_specific={
            "model": "llama3.1:8b",
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "max_tokens": 1000,
        },
    )


@pytest.fixture
def provider(mock_config):
    """Create an OllamaProvider instance with mocked dependencies."""
    with patch(
        "gemini_sre_agent.llm.providers.ollama_provider.ollama.Client"
    ) as mock_client:
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        provider = OllamaProvider(mock_config)
        provider.client = mock_client_instance
        return provider


class TestOllamaProvider:
    """Test cases for OllamaProvider."""

    def test_provider_initialization(self, mock_config):
        """Test provider initialization."""
        with patch("gemini_sre_agent.llm.providers.ollama_provider.ollama.Client"):
            provider = OllamaProvider(mock_config)
            assert provider.provider_type == "ollama"
            assert provider.model == "llama3.1:8b"
            assert provider.base_url == "http://localhost:11434/"

    def test_get_available_models(self, provider):
        """Test getting available models."""
        models = provider.get_available_models()

        assert ModelType.FAST in models
        assert ModelType.SMART in models
        assert ModelType.CODE in models
        assert ModelType.ANALYSIS in models

        assert models[ModelType.FAST] == "llama3.1:8b"
        assert models[ModelType.SMART] == "llama3.1:70b"
        assert models[ModelType.CODE] == "codellama:34b"
        assert models[ModelType.ANALYSIS] == "llama3.1:70b"

    @pytest.mark.asyncio
    async def test_generate_success(self, provider):
        """Test successful text generation."""
        # Mock the client response
        mock_response = {
            "message": {"content": "Test response"},
            "eval_count": 10,
            "prompt_eval_count": 5,
        }
        provider.client.chat = MagicMock(return_value=mock_response)

        request = LLMRequest(
            messages=[{"role": "user", "content": "Test prompt"}],
            model_type=ModelType.FAST,
        )

        response = await provider.generate(request)

        assert isinstance(response, LLMResponse)
        assert response.content == "Test response"
        assert response.usage is not None
        assert response.usage["input_tokens"] == 5
        assert response.usage["output_tokens"] == 10

    @pytest.mark.asyncio
    async def test_generate_stream(self, provider):
        """Test streaming text generation."""
        # Mock streaming response
        mock_chunks = [
            {"message": {"content": "Hello"}, "done": False},
            {"message": {"content": " world"}, "done": False},
            {
                "message": {"content": ""},
                "done": True,
                "eval_count": 10,
                "prompt_eval_count": 5,
            },
        ]

        def mock_chat(*args, **kwargs):
            # Return a regular generator
            for chunk in mock_chunks:
                yield chunk

        provider.client.chat = mock_chat

        request = LLMRequest(
            messages=[{"role": "user", "content": "Test prompt"}],
            model_type=ModelType.FAST,
        )

        responses = []
        async for response in provider.generate_stream(request):
            responses.append(response)

        assert len(responses) == 2  # Only chunks with content
        assert responses[0].content == "Hello"
        assert responses[1].content == " world"

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        """Test successful health check."""
        provider.client.list = MagicMock(return_value={"models": []})

        result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, provider):
        """Test health check failure."""
        provider.client.list = MagicMock(side_effect=Exception("Connection failed"))

        result = await provider.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_embeddings(self, provider):
        """Test embeddings generation."""
        mock_response = {"embedding": [0.1, 0.2, 0.3]}
        provider.client.embeddings = MagicMock(return_value=mock_response)

        embeddings = await provider.embeddings("Test text")
        assert embeddings == [0.1, 0.2, 0.3]

    def test_token_count(self, provider):
        """Test token counting."""
        mock_response = {
            "message": {"content": ""},
            "eval_count": 15,
            "prompt_eval_count": 8,
        }
        provider.client.chat = MagicMock(return_value=mock_response)

        count = provider.token_count("Test text")
        assert count == 8

    def test_token_count_fallback(self, provider):
        """Test token count fallback when eval_count is not available."""
        mock_response = {"message": {"content": ""}}
        provider.client.chat = MagicMock(return_value=mock_response)

        count = provider.token_count("Test text")
        # Should fall back to approximation
        assert count > 0

    def test_cost_estimate(self, provider):
        """Test cost estimation."""
        cost = provider.cost_estimate(100, 50)
        # Ollama is free, so cost should be 0
        assert cost == 0.0

    def test_validate_config(self, provider):
        """Test configuration validation."""
        # Create a config without API key for Ollama
        config_without_key = LLMProviderConfig(
            provider="ollama",
            api_key=None,  # Ollama doesn't use API keys
            base_url=HttpUrl("http://localhost:11434/"),
            region=None,
            timeout=30,
            max_retries=3,
            rate_limit=100,
            provider_specific={"model": "llama3.1:8b"},
        )
        result = OllamaProvider.validate_config(config_without_key)
        assert result is None  # validate_config doesn't return anything on success

    def test_convert_messages_to_ollama_format(self, provider):
        """Test message format conversion."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]

        ollama_messages = provider._convert_messages_to_ollama_format(messages)

        assert len(ollama_messages) == 3
        assert ollama_messages[0]["role"] == "user"
        assert ollama_messages[0]["content"] == "Hello"
        assert ollama_messages[1]["role"] == "assistant"
        assert ollama_messages[1]["content"] == "Hi there"

    def test_extract_usage_from_dict(self, provider):
        """Test usage extraction from dict response."""
        response = {"eval_count": 20, "prompt_eval_count": 10}

        usage = provider._extract_usage(response)
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 20

    def test_extract_usage_from_object(self, provider):
        """Test usage extraction from object response."""

        class MockResponse:
            def __init__(self):
                self.eval_count = 15
                self.prompt_eval_count = 8

        response = MockResponse()
        usage = provider._extract_usage(response)
        assert usage["input_tokens"] == 8
        assert usage["output_tokens"] == 15

    def test_extract_usage_no_data(self, provider):
        """Test usage extraction when no usage data is available."""
        response = {}
        usage = provider._extract_usage(response)
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 0
