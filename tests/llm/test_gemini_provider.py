# tests/llm/test_gemini_provider.py

"""
Unit tests for the Gemini provider implementation.
"""

import pytest
from unittest.mock import MagicMock, patch

from gemini_sre_agent.llm.base import LLMRequest, ModelType
from gemini_sre_agent.llm.config import LLMProviderConfig
from gemini_sre_agent.llm.providers.gemini_provider import GeminiProvider


class TestGeminiProvider:
    """Test cases for GeminiProvider."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for testing."""
        return LLMProviderConfig(
            provider="gemini",
            api_key="AIzaSyDummyKeyForTesting123456789",
            base_url=None,
            region=None,
            timeout=30,
            max_retries=3,
            rate_limit=None,
            provider_specific={
                "temperature": 0.7,
                "max_tokens": 1000,
                "top_p": 0.95,
                "top_k": 40,
            }
        )

    @pytest.fixture
    def mock_gemini_response(self):
        """Create a mock Gemini API response."""
        mock_response = MagicMock()
        mock_response.text = "This is a test response from Gemini"
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        return mock_response

    @pytest.fixture
    def mock_streaming_response(self):
        """Create mock streaming responses."""
        chunks = [
            MagicMock(text="This "),
            MagicMock(text="is "),
            MagicMock(text="a "),
            MagicMock(text="streaming "),
            MagicMock(text="response"),
        ]
        for chunk in chunks:
            chunk.usage_metadata = MagicMock()
            chunk.usage_metadata.prompt_token_count = 10
            chunk.usage_metadata.candidates_token_count = 1
        return chunks

    @pytest.mark.asyncio
    async def test_provider_initialization(self, mock_config):
        """Test provider initialization."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model:
            
            mock_model_instance = MagicMock()
            mock_model.return_value = mock_model_instance
            
            provider = GeminiProvider(mock_config)
            
            assert provider.api_key == mock_config.api_key
            assert provider.model == "gemini-1.5-flash"  # Default model
            assert provider._model == mock_model_instance

    @pytest.mark.asyncio
    async def test_generate_response(self, mock_config, mock_gemini_response):
        """Test non-streaming response generation."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model:
            
            mock_model_instance = MagicMock()
            mock_model_instance.generate_content = MagicMock(
                return_value=mock_gemini_response
            )
            mock_model.return_value = mock_model_instance
            
            provider = GeminiProvider(mock_config)
            
            request = LLMRequest(
                messages=[{"role": "user", "content": "Hello, world!"}],
                model_type=ModelType.FAST
            )
            
            with patch('asyncio.to_thread') as mock_to_thread:
                mock_to_thread.return_value = mock_gemini_response
                
                response = await provider.generate(request)
                
                assert response.content == "This is a test response from Gemini"
                assert response.model == "gemini-1.5-flash"  # Default model
                assert response.provider == "gemini"
                assert response.usage is not None
                assert response.usage["input_tokens"] == 10
                assert response.usage["output_tokens"] == 5

    @pytest.mark.asyncio
    async def test_generate_streaming_response(self, mock_config, mock_streaming_response):
        """Test streaming response generation."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model:
            
            mock_model_instance = MagicMock()
            mock_model_instance.generate_content = MagicMock(
                return_value=mock_streaming_response
            )
            mock_model.return_value = mock_model_instance
            
            provider = GeminiProvider(mock_config)
            
            request = LLMRequest(
                messages=[{"role": "user", "content": "Hello, world!"}],
                model_type=ModelType.FAST
            )
            
            with patch('asyncio.to_thread') as mock_to_thread:
                mock_to_thread.return_value = mock_streaming_response
                
                responses = []
                async for response in provider.generate_stream(request):
                    responses.append(response)
                
                assert len(responses) == 5
                assert responses[0].content == "This "
                assert responses[1].content == "is "
                assert responses[2].content == "a "
                assert responses[3].content == "streaming "
                assert responses[4].content == "response"

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_config):
        """Test successful health check."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model:
            
            mock_model_instance = MagicMock()
            mock_model_instance.generate_content = MagicMock(
                return_value=MagicMock(text="Hello")
            )
            mock_model.return_value = mock_model_instance
            
            provider = GeminiProvider(mock_config)
            
            with patch('asyncio.to_thread') as mock_to_thread:
                mock_to_thread.return_value = MagicMock(text="Hello")
                
                result = await provider.health_check()
                assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_config):
        """Test failed health check."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model:
            
            mock_model_instance = MagicMock()
            mock_model_instance.generate_content = MagicMock(
                side_effect=Exception("API Error")
            )
            mock_model.return_value = mock_model_instance
            
            provider = GeminiProvider(mock_config)
            
            with patch('asyncio.to_thread') as mock_to_thread:
                mock_to_thread.side_effect = Exception("API Error")
                
                result = await provider.health_check()
                assert result is False

    def test_supports_streaming(self, mock_config):
        """Test streaming support."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            provider = GeminiProvider(mock_config)
            assert provider.supports_streaming() is True

    def test_supports_tools(self, mock_config):
        """Test tool calling support."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            provider = GeminiProvider(mock_config)
            assert provider.supports_tools() is True

    def test_get_available_models(self, mock_config):
        """Test getting available models."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            provider = GeminiProvider(mock_config)
            models = provider.get_available_models()
            
            assert models[ModelType.FAST] == "gemini-1.5-flash"
            assert models[ModelType.SMART] == "gemini-1.5-pro"
            assert models[ModelType.DEEP_THINKING] == "gemini-1.5-pro"
            assert models[ModelType.CODE] == "gemini-1.5-pro"
            assert models[ModelType.ANALYSIS] == "gemini-1.5-pro"

    @pytest.mark.asyncio
    async def test_embeddings(self, mock_config):
        """Test embeddings generation."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'), \
             patch('google.generativeai.embed_content') as mock_embed:
            
            mock_embed.return_value = {'embedding': [0.1, 0.2, 0.3] * 256}  # 768 dimensions
            
            provider = GeminiProvider(mock_config)
            
            with patch('asyncio.to_thread') as mock_to_thread:
                mock_to_thread.return_value = {'embedding': [0.1, 0.2, 0.3] * 256}
                
                embeddings = await provider.embeddings("Test text")
                
                assert len(embeddings) == 768
                assert embeddings[0] == 0.1

    def test_token_count(self, mock_config):
        """Test token counting."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model:
            
            mock_model_instance = MagicMock()
            mock_model_instance.count_tokens = MagicMock(
                return_value=MagicMock(total_tokens=10)
            )
            mock_model.return_value = mock_model_instance
            
            provider = GeminiProvider(mock_config)
            
            count = provider.token_count("Test text")
            assert count == 10

    def test_token_count_fallback(self, mock_config):
        """Test token counting fallback."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model:
            
            mock_model_instance = MagicMock()
            mock_model_instance.count_tokens = MagicMock(
                side_effect=Exception("API Error")
            )
            mock_model.return_value = mock_model_instance
            
            provider = GeminiProvider(mock_config)
            
            count = provider.token_count("Test text with multiple words")
            # Should fallback to approximation: 5 words * 1.3 = 6.5 -> 6
            assert count == 6

    def test_cost_estimate_flash_model(self, mock_config):
        """Test cost estimation for Flash model."""
        # Create a new config with flash model
        flash_config = LLMProviderConfig(
            provider="gemini",
            api_key="AIzaSyDummyKeyForTesting123456789",
            base_url=None,
            region=None,
            timeout=30,
            max_retries=3,
            rate_limit=None,
            provider_specific={"model": "gemini-1.5-flash"}
        )
        
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            provider = GeminiProvider(flash_config)
            provider.model = "gemini-1.5-flash"  # Set model directly for testing
            
            cost = provider.cost_estimate(1000, 500)
            # Flash pricing: input $0.075/1M, output $0.30/1M
            expected = (1000/1000) * 0.000075 + (500/1000) * 0.0003
            assert abs(cost - expected) < 0.000001

    def test_cost_estimate_pro_model(self, mock_config):
        """Test cost estimation for Pro model."""
        # Create a new config with pro model
        pro_config = LLMProviderConfig(
            provider="gemini",
            api_key="AIzaSyDummyKeyForTesting123456789",
            base_url=None,
            region=None,
            timeout=30,
            max_retries=3,
            rate_limit=None,
            provider_specific={"model": "gemini-1.5-pro"}
        )
        
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            provider = GeminiProvider(pro_config)
            provider.model = "gemini-1.5-pro"  # Set model directly for testing
            
            cost = provider.cost_estimate(1000, 500)
            # Pro pricing: input $1.25/1M, output $5.00/1M
            expected = (1000/1000) * 0.00125 + (500/1000) * 0.005
            assert abs(cost - expected) < 0.000001

    def test_convert_messages_to_prompt(self, mock_config):
        """Test message conversion to prompt."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            provider = GeminiProvider(mock_config)
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi there!"},
            ]
            
            prompt = provider._convert_messages_to_prompt(messages)
            
            expected = "System: You are a helpful assistant.\n\nUser: Hello!\n\nAssistant: Hi there!"
            assert prompt == expected

    def test_extract_usage(self, mock_config):
        """Test usage extraction from response."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            provider = GeminiProvider(mock_config)
            
            mock_response = MagicMock()
            mock_response.usage_metadata = MagicMock()
            mock_response.usage_metadata.prompt_token_count = 15
            mock_response.usage_metadata.candidates_token_count = 8
            
            usage = provider._extract_usage(mock_response)
            
            assert usage["input_tokens"] == 15
            assert usage["output_tokens"] == 8

    def test_extract_usage_no_metadata(self, mock_config):
        """Test usage extraction when metadata is missing."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            provider = GeminiProvider(mock_config)
            
            mock_response = MagicMock()
            mock_response.usage_metadata = None
            
            usage = provider._extract_usage(mock_response)
            
            assert usage["input_tokens"] == 0
            assert usage["output_tokens"] == 0

    def test_validate_config_valid(self, mock_config):
        """Test configuration validation with valid config."""
        GeminiProvider.validate_config(mock_config)

    def test_validate_config_missing_api_key(self):
        """Test configuration validation with missing API key."""
        mock_config = MagicMock()
        mock_config.api_key = None
        
        with pytest.raises(ValueError, match="Gemini API key is required"):
            GeminiProvider.validate_config(mock_config)

    def test_validate_config_invalid_api_key(self):
        """Test configuration validation with invalid API key."""
        mock_config = MagicMock()
        mock_config.api_key = "invalid-key"
        
        with pytest.raises(ValueError, match="Gemini API key must start with 'AIza'"):
            GeminiProvider.validate_config(mock_config)

    def test_validate_config_invalid_model(self):
        """Test configuration validation with invalid model."""
        mock_config = MagicMock()
        mock_config.api_key = "AIzaValidKey123456789"
        mock_config.model = "invalid-model"
        
        # Should not raise an error, just log a warning
        GeminiProvider.validate_config(mock_config)

    @pytest.mark.asyncio
    async def test_generate_error_handling(self, mock_config):
        """Test error handling in generate method."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model:
            
            mock_model_instance = MagicMock()
            mock_model_instance.generate_content = MagicMock(
                side_effect=Exception("API Error")
            )
            mock_model.return_value = mock_model_instance
            
            provider = GeminiProvider(mock_config)
            
            request = LLMRequest(
                messages=[{"role": "user", "content": "Hello!"}],
                model_type=ModelType.FAST
            )
            
            with patch('asyncio.to_thread') as mock_to_thread:
                mock_to_thread.side_effect = Exception("API Error")
                
                with pytest.raises(Exception, match="API Error"):
                    await provider.generate(request)

    @pytest.mark.asyncio
    async def test_embeddings_error_handling(self, mock_config):
        """Test error handling in embeddings method."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'), \
             patch('google.generativeai.embed_content') as mock_embed:
            
            mock_embed.side_effect = Exception("Embeddings API Error")
            
            provider = GeminiProvider(mock_config)
            
            with patch('asyncio.to_thread') as mock_to_thread:
                mock_to_thread.side_effect = Exception("Embeddings API Error")
                
                with pytest.raises(Exception, match="Embeddings API Error"):
                    await provider.embeddings("Test text")
