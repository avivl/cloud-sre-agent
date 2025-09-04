"""
Unit tests for the core LLM Provider Factory functionality.
"""

from unittest.mock import MagicMock, patch

import pytest

# Mock the dependencies before importing the factory
with patch.dict(
    "sys.modules",
    {"instructor": MagicMock(), "litellm": MagicMock(), "mirascope": MagicMock()},
):
    from gemini_sre_agent.llm.base import ModelType
    from gemini_sre_agent.llm.config import LLMProviderConfig, ModelConfig
    from gemini_sre_agent.llm.factory import LLMProviderFactory
    from gemini_sre_agent.llm.provider import LLMProvider


class MockProvider(LLMProvider):
    """Mock provider for testing."""

    def __init__(self, config):
        super().__init__(config)
        self._initialized = False

    async def initialize(self):
        self._initialized = True

    async def generate_text(self, prompt, model=None, **kwargs):
        return "Mock response"

    async def generate_structured(self, prompt, response_model, model=None, **kwargs):
        return response_model()

    def generate_stream(self, prompt, model=None, **kwargs):
        async def _stream():
            yield "Mock"

        return _stream()

    async def health_check(self):
        return True

    def get_available_models(self):
        return ["mock-model"]

    def estimate_cost(self, prompt, model=None):
        return 0.01

    def validate_config(self):
        return True


class TestLLMProviderFactory:
    """Test the LLMProviderFactory class."""

    @pytest.fixture
    def factory(self):
        """Create a factory instance."""
        return LLMProviderFactory()

    @pytest.fixture
    def mock_config(self):
        """Create a mock provider configuration."""
        return LLMProviderConfig(
            provider="test",
            api_key="test-key",
            models={
                "test-model": ModelConfig(
                    name="test-model",
                    model_type=ModelType.FAST,
                    cost_per_1k_tokens=0.001,
                )
            },
        )

    def test_factory_initialization(self, factory):
        """Test factory initialization."""
        assert factory._providers == {}
        assert "openai" in factory._provider_types
        assert "anthropic" in factory._provider_types
        assert "gemini" in factory._provider_types

    def test_register_provider_type(self, factory):
        """Test registering a new provider type."""
        factory.register_provider_type("custom", MockProvider)
        assert "custom" in factory._provider_types
        assert factory._provider_types["custom"] == MockProvider

    def test_create_provider_success(self, factory, mock_config):
        """Test successful provider creation."""
        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.validate_config.return_value = True
            mock_provider_class.return_value = mock_provider

            provider = factory.create_provider(mock_config)

            assert provider == mock_provider
            assert "test" in factory._providers
            mock_provider_class.assert_called_once_with(mock_config)
            mock_provider.validate_config.assert_called_once()

    def test_create_provider_force_recreate(self, factory, mock_config):
        """Test provider creation with force_recreate=True."""
        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider1 = MagicMock()
            mock_provider1.validate_config.return_value = True
            mock_provider2 = MagicMock()
            mock_provider2.validate_config.return_value = True
            mock_provider_class.side_effect = [mock_provider1, mock_provider2]

            # Create first provider
            provider1 = factory.create_provider(mock_config)
            assert provider1 == mock_provider1

            # Create second provider with force_recreate=True
            provider2 = factory.create_provider(mock_config, force_recreate=True)
            assert provider2 == mock_provider2
            assert mock_provider_class.call_count == 2

    def test_create_provider_unsupported_type(self, factory):
        """Test creating provider with unsupported type."""
        config = LLMProviderConfig(
            provider="unsupported",
            models={"test": ModelConfig(name="test", model_type=ModelType.FAST)},
        )

        with pytest.raises(ValueError, match="Unsupported provider type: unsupported"):
            factory.create_provider(config)

    def test_create_provider_invalid_config(self, factory, mock_config):
        """Test creating provider with invalid configuration."""
        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.validate_config.return_value = False
            mock_provider_class.return_value = mock_provider

            with pytest.raises(
                ValueError, match="Invalid configuration for provider: test"
            ):
                factory.create_provider(mock_config)

    def test_create_provider_creation_failure(self, factory, mock_config):
        """Test provider creation failure."""
        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider_class.side_effect = Exception("Creation failed")

            with pytest.raises(RuntimeError, match="Provider creation failed"):
                factory.create_provider(mock_config)

    def test_get_provider_existing(self, factory, mock_config):
        """Test getting an existing provider."""
        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.validate_config.return_value = True
            mock_provider_class.return_value = mock_provider

            factory.create_provider(mock_config)
            provider = factory.get_provider("test")

            assert provider == mock_provider

    def test_get_provider_nonexistent(self, factory):
        """Test getting a non-existent provider."""
        provider = factory.get_provider("nonexistent")
        assert provider is None

    def test_get_all_providers(self, factory, mock_config):
        """Test getting all providers."""
        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.validate_config.return_value = True
            mock_provider_class.return_value = mock_provider

            factory.create_provider(mock_config)
            providers = factory.get_all_providers()

            assert "test" in providers
            assert providers["test"] == mock_provider
            # Should return a copy, not the original
            assert providers is not factory._providers

    def test_remove_provider_existing(self, factory, mock_config):
        """Test removing an existing provider."""
        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.validate_config.return_value = True
            mock_provider_class.return_value = mock_provider

            factory.create_provider(mock_config)
            result = factory.remove_provider("test")

            assert result is True
            assert "test" not in factory._providers

    def test_remove_provider_nonexistent(self, factory):
        """Test removing a non-existent provider."""
        result = factory.remove_provider("nonexistent")
        assert result is False

    def test_clear_providers(self, factory, mock_config):
        """Test clearing all providers."""
        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.validate_config.return_value = True
            mock_provider_class.return_value = mock_provider

            factory.create_provider(mock_config)
            factory.clear_providers()

            assert factory._providers == {}

    def test_get_supported_providers(self, factory):
        """Test getting supported provider types."""
        providers = factory.get_supported_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert "gemini" in providers
