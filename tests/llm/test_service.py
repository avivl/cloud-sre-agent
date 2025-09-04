# tests/llm/test_service.py

"""
Tests for the LLM service integration.

This module tests the LLMService class that integrates LiteLLM, Instructor, and Mirascope.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

# Mock the dependencies before importing the service
with patch.dict(
    "sys.modules",
    {"instructor": MagicMock(), "litellm": MagicMock(), "mirascope": MagicMock()},
):
    from gemini_sre_agent.llm.base import ModelType
    from gemini_sre_agent.llm.config import LLMConfig, LLMProviderConfig, ModelConfig
    from gemini_sre_agent.llm.service import LLMService, create_llm_service


class TestResponseModel(BaseModel):
    """Test response model for structured output testing."""

    answer: str
    confidence: float


@pytest.fixture
def mock_llm_config():
    """Create a mock LLM configuration for testing."""
    provider_config = LLMProviderConfig(
        provider="openai",
        api_key="test-key",
        models={
            "gpt-3.5-turbo": ModelConfig(
                name="gpt-3.5-turbo",
                model_type=ModelType.SMART,
                cost_per_1k_tokens=0.002,
            )
        },
        model_type_mappings={ModelType.SMART: "gpt-3.5-turbo"},
    )

    return LLMConfig(
        providers={"openai": provider_config},
        default_provider="openai",
        default_model_type=ModelType.SMART,
    )


@pytest.fixture
def mock_llm_service(mock_llm_config):
    """Create a mock LLM service for testing."""
    with patch("gemini_sre_agent.llm.service.instructor") as mock_instructor, patch(
        "gemini_sre_agent.llm.service.litellm"
    ), patch("gemini_sre_agent.llm.service.PromptManager"):

        mock_client = MagicMock()
        mock_instructor.patch.return_value = mock_client

        service = LLMService(mock_llm_config)
        service.client = mock_client
        return service


class TestLLMService:
    """Test cases for the LLMService class."""

    def test_initialization(self, mock_llm_config):
        """Test LLMService initialization."""
        with patch("gemini_sre_agent.llm.service.instructor") as mock_instructor, patch(
            "gemini_sre_agent.llm.service.litellm"
        ) as mock_litellm, patch("gemini_sre_agent.llm.service.PromptManager"):

            mock_client = MagicMock()
            mock_instructor.patch.return_value = mock_client

            service = LLMService(mock_llm_config)

            assert service.config == mock_llm_config
            assert service.client == mock_client
            mock_instructor.patch.assert_called_once_with(mock_litellm)

    @pytest.mark.asyncio
    async def test_generate_structured(self, mock_llm_service):
        """Test structured response generation."""
        # Arrange
        mock_response = TestResponseModel(answer="test answer", confidence=0.95)
        mock_llm_service.client.chat.completions.create.return_value = mock_response

        # Act
        result = await mock_llm_service.generate_structured(
            prompt="Test prompt", response_model=TestResponseModel
        )

        # Assert
        assert result == mock_response
        mock_llm_service.client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_text(self, mock_llm_service):
        """Test text response generation."""
        with patch(
            "gemini_sre_agent.llm.service.litellm.acompletion"
        ) as mock_completion:
            # Arrange
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "test response"
            mock_completion.return_value = mock_response

            # Act
            result = await mock_llm_service.generate_text(prompt="Test prompt")

            # Assert
            assert result == "test response"
            mock_completion.assert_called_once()

    def test_resolve_model(self, mock_llm_service):
        """Test model resolution logic."""
        # Test with specific model
        model = mock_llm_service._resolve_model(model="gpt-4")
        assert model == "gpt-4"

        # Test with model type
        model = mock_llm_service._resolve_model(model_type=ModelType.SMART)
        assert model == "gpt-3.5-turbo"

        # Test with provider
        model = mock_llm_service._resolve_model(
            provider="openai", model_type=ModelType.SMART
        )
        assert model == "gpt-3.5-turbo"

    def test_resolve_model_error(self, mock_llm_service):
        """Test model resolution with invalid parameters."""
        with pytest.raises(ValueError):
            mock_llm_service._resolve_model(provider="nonexistent")

    def test_handle_error(self, mock_llm_service):
        """Test error handling."""
        # Test rate limit error
        mock_llm_service._handle_error(Exception("Rate limit exceeded"))
        # Should not raise an exception

        # Test authentication error
        mock_llm_service._handle_error(Exception("Authentication failed"))
        # Should not raise an exception

    @pytest.mark.asyncio
    async def test_health_check(self, mock_llm_service):
        """Test health check functionality."""
        with patch.object(mock_llm_service, "generate_text") as mock_generate:
            # Arrange
            mock_generate.return_value = "Hello"

            # Act
            result = await mock_llm_service.health_check()

            # Assert
            assert result is True
            mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_llm_service):
        """Test health check failure."""
        with patch.object(mock_llm_service, "generate_text") as mock_generate:
            # Arrange
            mock_generate.side_effect = Exception("API error")

            # Act
            result = await mock_llm_service.health_check()

            # Assert
            assert result is False

    def test_get_available_models(self, mock_llm_service):
        """Test getting available models."""
        # Test with specific provider
        models = mock_llm_service.get_available_models(provider="openai")
        assert "openai" in models
        assert "gpt-3.5-turbo" in models["openai"]

        # Test with all providers
        all_models = mock_llm_service.get_available_models()
        assert "openai" in all_models

    def test_get_available_models_nonexistent_provider(self, mock_llm_service):
        """Test getting models for nonexistent provider."""
        models = mock_llm_service.get_available_models(provider="nonexistent")
        assert models == {}


class TestFactoryFunction:
    """Test cases for the factory function."""

    def test_create_llm_service(self, mock_llm_config):
        """Test the create_llm_service factory function."""
        with patch("gemini_sre_agent.llm.service.instructor") as mock_instructor, patch(
            "gemini_sre_agent.llm.service.litellm"
        ), patch("gemini_sre_agent.llm.service.PromptManager"):

            mock_client = MagicMock()
            mock_instructor.patch.return_value = mock_client

            service = create_llm_service(mock_llm_config)

            assert isinstance(service, LLMService)
            assert service.config == mock_llm_config


class TestImportErrors:
    """Test cases for import error handling."""

    def test_missing_dependencies(self):
        """Test behavior when required dependencies are missing."""
        with patch.dict(
            "sys.modules", {"instructor": None, "litellm": None, "mirascope": None}
        ):
            with pytest.raises(
                ImportError, match="Required dependencies not installed"
            ):
                pass
