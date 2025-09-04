"""
Unit tests for advanced LLM Provider Factory functionality.
"""

from unittest.mock import MagicMock, patch

import pytest

# Mock the dependencies before importing the factory
with patch.dict(
    "sys.modules",
    {"instructor": MagicMock(), "litellm": MagicMock(), "mirascope": MagicMock()},
):
    from gemini_sre_agent.llm.base import ModelType
    from gemini_sre_agent.llm.config import LLMConfig, LLMProviderConfig, ModelConfig
    from gemini_sre_agent.llm.factory import (
        LLMProviderFactory,
        create_provider_factory,
        get_provider_factory,
    )
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


class TestFactoryAdvanced:
    """Test advanced factory functionality."""

    @pytest.fixture
    def factory(self):
        """Create a factory instance."""
        return LLMProviderFactory()

    def test_create_providers_from_config(self, factory):
        """Test creating providers from complete configuration."""
        config = LLMConfig(
            default_provider="test1",
            providers={
                "test1": LLMProviderConfig(
                    provider="test1",
                    models={
                        "model1": ModelConfig(name="model1", model_type=ModelType.FAST)
                    },
                ),
                "test2": LLMProviderConfig(
                    provider="test2",
                    models={
                        "model2": ModelConfig(name="model2", model_type=ModelType.SMART)
                    },
                ),
            },
        )

        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.validate_config.return_value = True
            mock_provider_class.return_value = mock_provider

            providers = factory.create_providers_from_config(config)

            assert len(providers) == 2
            assert "test1" in providers
            assert "test2" in providers

    @pytest.mark.asyncio
    async def test_initialize_all_providers(self, factory):
        """Test initializing all providers."""
        config = LLMProviderConfig(
            provider="test",
            models={
                "test-model": ModelConfig(name="test-model", model_type=ModelType.FAST)
            },
        )

        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.validate_config.return_value = True
            mock_provider_class.return_value = mock_provider

            factory.create_provider(config)
            results = await factory.initialize_all_providers()

            assert "test" in results
            assert results["test"] is True
            mock_provider.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_all_providers(self, factory):
        """Test health checking all providers."""
        config = LLMProviderConfig(
            provider="test",
            models={
                "test-model": ModelConfig(name="test-model", model_type=ModelType.FAST)
            },
        )

        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.validate_config.return_value = True
            mock_provider.health_check.return_value = True
            mock_provider_class.return_value = mock_provider

            factory.create_provider(config)
            results = await factory.health_check_all_providers()

            assert "test" in results
            assert results["test"] is True
            mock_provider.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_providers_with_failure(self, factory):
        """Test initializing providers when some fail."""
        config1 = LLMProviderConfig(
            provider="test1",
            models={"model1": ModelConfig(name="model1", model_type=ModelType.FAST)},
        )
        config2 = LLMProviderConfig(
            provider="test2",
            models={"model2": ModelConfig(name="model2", model_type=ModelType.SMART)},
        )

        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider1 = MagicMock()
            mock_provider1.validate_config.return_value = True
            mock_provider1.initialize.side_effect = Exception("Init failed")

            mock_provider2 = MagicMock()
            mock_provider2.validate_config.return_value = True
            mock_provider2.initialize.return_value = None

            mock_provider_class.side_effect = [mock_provider1, mock_provider2]

            factory.create_provider(config1)
            factory.create_provider(config2)
            results = await factory.initialize_all_providers()

            assert "test1" in results
            assert "test2" in results
            assert results["test1"] is False
            assert results["test2"] is True

    @pytest.mark.asyncio
    async def test_health_check_providers_with_failure(self, factory):
        """Test health checking providers when some fail."""
        config1 = LLMProviderConfig(
            provider="test1",
            models={"model1": ModelConfig(name="model1", model_type=ModelType.FAST)},
        )
        config2 = LLMProviderConfig(
            provider="test2",
            models={"model2": ModelConfig(name="model2", model_type=ModelType.SMART)},
        )

        with patch(
            "gemini_sre_agent.llm.factory.LiteLLMProvider"
        ) as mock_provider_class:
            mock_provider1 = MagicMock()
            mock_provider1.validate_config.return_value = True
            mock_provider1.health_check.side_effect = Exception("Health check failed")

            mock_provider2 = MagicMock()
            mock_provider2.validate_config.return_value = True
            mock_provider2.health_check.return_value = True

            mock_provider_class.side_effect = [mock_provider1, mock_provider2]

            factory.create_provider(config1)
            factory.create_provider(config2)
            results = await factory.health_check_all_providers()

            assert "test1" in results
            assert "test2" in results
            assert results["test1"] is False
            assert results["test2"] is True


class TestFactoryFunctions:
    """Test the factory utility functions."""

    def test_get_provider_factory_singleton(self):
        """Test that get_provider_factory returns a singleton."""
        factory1 = get_provider_factory()
        factory2 = get_provider_factory()
        assert factory1 is factory2

    def test_create_provider_factory_new_instance(self):
        """Test that create_provider_factory returns a new instance."""
        factory1 = create_provider_factory()
        factory2 = create_provider_factory()
        assert factory1 is not factory2
        assert isinstance(factory1, LLMProviderFactory)
        assert isinstance(factory2, LLMProviderFactory)
