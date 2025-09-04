"""
Unit tests for the LiteLLM Provider implementation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel

# Mock the dependencies before importing the provider
with patch.dict('sys.modules', {
    'instructor': MagicMock(),
    'litellm': MagicMock(),
    'mirascope': MagicMock()
}):
    from gemini_sre_agent.llm.litellm_provider import LiteLLMProvider
    from gemini_sre_agent.llm.config import LLMProviderConfig, ModelConfig
    from gemini_sre_agent.llm.base import ModelType


class TestResponse(BaseModel):
    """Test response model for structured output testing."""
    message: str
    confidence: float


class TestLiteLLMProvider:
    """Test the LiteLLMProvider implementation."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock provider configuration."""
        return LLMProviderConfig(
            provider="openai",
            api_key="test-key",
            models={
                "gpt-3.5-turbo": ModelConfig(
                    name="gpt-3.5-turbo",
                    model_type=ModelType.FAST,
                    cost_per_1k_tokens=0.002
                )
            }
        )
    
    @pytest.fixture
    def provider(self, mock_config):
        """Create a LiteLLMProvider instance."""
        with patch('gemini_sre_agent.llm.litellm_provider.litellm') as mock_litellm:
            return LiteLLMProvider(mock_config)
    
    def test_provider_initialization(self, provider, mock_config):
        """Test provider initialization."""
        assert provider.config == mock_config
        assert not provider.is_initialized
        assert provider.provider_name == "openai"
    
    def test_configure_litellm(self, provider):
        """Test LiteLLM configuration."""
        with patch('gemini_sre_agent.llm.litellm_provider.litellm') as mock_litellm:
            provider._configure_litellm()
            assert mock_litellm.api_key == "test-key"
            assert mock_litellm.verbose is True
            assert mock_litellm.drop_params is True
    
    @pytest.mark.asyncio
    async def test_initialize(self, provider):
        """Test provider initialization."""
        with patch.object(provider, 'health_check', return_value=True) as mock_health:
            await provider.initialize()
            assert provider.is_initialized
            mock_health.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_text(self, provider):
        """Test text generation."""
        with patch('gemini_sre_agent.llm.litellm_provider.litellm.acompletion') as mock_completion:
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Generated text"
            mock_completion.return_value = mock_response
            
            result = await provider.generate_text("Test prompt")
            assert result == "Generated text"
            mock_completion.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_structured(self, provider):
        """Test structured output generation."""
        with patch('gemini_sre_agent.llm.litellm_provider.instructor.from_litellm') as mock_instructor:
            mock_client = MagicMock()
            mock_instructor.return_value = mock_client
            mock_response = TestResponse(message="Test", confidence=0.95)
            mock_client.chat.completions.create.return_value = mock_response
            
            result = await provider.generate_structured("Test prompt", TestResponse)
            assert isinstance(result, TestResponse)
            assert result.message == "Test"
            assert result.confidence == 0.95
    
    @pytest.mark.asyncio
    async def test_generate_stream(self, provider):
        """Test streaming text generation."""
        with patch('gemini_sre_agent.llm.litellm_provider.litellm.acompletion') as mock_completion:
            # Mock streaming response
            mock_chunk1 = MagicMock()
            mock_chunk1.choices[0].delta.content = "Hello"
            mock_chunk2 = MagicMock()
            mock_chunk2.choices[0].delta.content = " World"
            
            async def mock_stream():
                yield mock_chunk1
                yield mock_chunk2
            
            mock_completion.return_value = mock_stream()
            
            stream = provider.generate_stream("Test prompt")
            result = ""
            async for chunk in stream:
                result += chunk
            
            assert result == "Hello World"
    
    @pytest.mark.asyncio
    async def test_health_check(self, provider):
        """Test health check functionality."""
        with patch.object(provider, 'generate_text', return_value="OK") as mock_generate:
            result = await provider.health_check()
            assert result is True
            mock_generate.assert_called_once_with(prompt="Hello", max_tokens=10)
    
    def test_get_available_models(self, provider):
        """Test getting available models."""
        models = provider.get_available_models()
        assert "gpt-3.5-turbo" in models
    
    def test_estimate_cost(self, provider):
        """Test cost estimation."""
        cost = provider.estimate_cost("Hello world", "gpt-3.5-turbo")
        assert cost > 0
    
    def test_validate_config_valid(self, provider):
        """Test configuration validation with valid config."""
        assert provider.validate_config() is True
    
    def test_validate_config_invalid(self):
        """Test configuration validation with invalid config."""
        invalid_config = LLMProviderConfig(
            provider="openai",
            # Missing API key
            models={"gpt-3.5-turbo": ModelConfig(name="gpt-3.5-turbo", model_type=ModelType.FAST)}
        )
        provider = LiteLLMProvider(invalid_config)
        assert provider.validate_config() is False
    
    def test_validate_config_no_models(self):
        """Test configuration validation with no models."""
        config = LLMProviderConfig(
            provider="openai",
            api_key="test-key",
            models={}
        )
        provider = LiteLLMProvider(config)
        assert provider.validate_config() is False
