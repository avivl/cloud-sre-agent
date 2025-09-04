# tests/llm/test_providers.py

"""
Tests for provider-specific configuration handlers.
"""

from unittest.mock import MagicMock

import pytest

from gemini_sre_agent.llm.base import ErrorSeverity, LLMProviderError, ModelType
from gemini_sre_agent.llm.config import LLMProviderConfig, ModelConfig
from gemini_sre_agent.llm.providers import (
    AnthropicProviderHandler,
    BedrockProviderHandler,
    GrokProviderHandler,
    OllamaProviderHandler,
    OpenAIProviderHandler,
    ProviderCapabilities,
    ProviderHandlerFactory,
)


def create_test_config(provider: str, **kwargs) -> LLMProviderConfig:
    """Helper to create test configs with defaults."""
    defaults = {"timeout": 30, "max_retries": 3, "rate_limit": 100, "models": {}}
    defaults.update(kwargs)
    return LLMProviderConfig(provider=provider, **defaults)  # type: ignore


def create_test_model_config(name: str, model_type: ModelType, **kwargs) -> ModelConfig:
    """Helper to create test model configs with defaults."""
    defaults = {"cost_per_1k_tokens": 0.01, "max_tokens": 4000}
    defaults.update(kwargs)
    return ModelConfig(name=name, model_type=model_type, **defaults)


class TestProviderCapabilities:
    """Test ProviderCapabilities dataclass."""

    def test_provider_capabilities_creation(self):
        """Test creating ProviderCapabilities."""
        caps = ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_vision=False,
            supports_function_calling=True,
            max_context_length=128000,
            supported_model_types=[ModelType.FAST, ModelType.SMART],
            cost_per_1k_tokens={"gpt-4": 0.01},
        )

        assert caps.supports_streaming is True
        assert caps.supports_tools is True
        assert caps.supports_vision is False
        assert caps.max_context_length == 128000
        assert ModelType.FAST in caps.supported_model_types
        assert caps.cost_per_1k_tokens["gpt-4"] == 0.01


class TestOpenAIProviderHandler:
    """Test OpenAI provider handler."""

    def test_openai_handler_creation(self):
        """Test creating OpenAI handler."""
        config = create_test_config(
            provider="openai",
            api_key="sk-test123456789012345678901234567890",
            models={"gpt-4": create_test_model_config("gpt-4", ModelType.SMART)},
        )

        handler = OpenAIProviderHandler(config)
        assert handler.provider_name == "openai"
        assert handler.config == config

    def test_openai_validate_config_valid(self):
        """Test OpenAI config validation with valid config."""
        config = create_test_config(
            provider="openai",
            api_key="sk-test123456789012345678901234567890",
            models={"gpt-4": create_test_model_config("gpt-4", ModelType.SMART)},
        )

        handler = OpenAIProviderHandler(config)
        errors = handler.validate_config()
        assert len(errors) == 0

    def test_openai_validate_config_missing_api_key(self):
        """Test OpenAI config validation with missing API key."""
        # Create a valid config first, then modify it to test validation
        config = create_test_config(
            provider="openai",
            api_key="sk-test123456789012345678901234567890",
            models={},
        )

        # Manually set api_key to None to test validation logic
        config.api_key = None

        handler = OpenAIProviderHandler(config)
        errors = handler.validate_config()
        assert "OpenAI API key is required" in errors

    def test_openai_validate_config_invalid_model(self):
        """Test OpenAI config validation with invalid model name."""
        config = create_test_config(
            provider="openai",
            api_key="sk-test123456789012345678901234567890",
            models={
                "invalid-model": create_test_model_config(
                    "invalid-model", ModelType.SMART
                )
            },
        )

        handler = OpenAIProviderHandler(config)
        errors = handler.validate_config()
        assert "Invalid OpenAI model name: invalid-model" in errors

    def test_openai_validate_credentials_valid(self):
        """Test OpenAI credential validation with valid key."""
        config = create_test_config(
            provider="openai", api_key="sk-test123456789012345678901234567890"
        )

        handler = OpenAIProviderHandler(config)
        is_valid, error = handler.validate_credentials()
        assert is_valid is True
        assert error is None

    def test_openai_validate_credentials_invalid_format(self):
        """Test OpenAI credential validation with invalid format."""
        config = create_test_config(provider="openai", api_key="invalid-key")

        handler = OpenAIProviderHandler(config)
        is_valid, error = handler.validate_credentials()
        assert is_valid is False
        assert error is not None and "must start with 'sk-'" in error

    def test_openai_get_capabilities(self):
        """Test OpenAI capabilities."""
        config = create_test_config(provider="openai", api_key="sk-test")
        handler = OpenAIProviderHandler(config)

        caps = handler.get_capabilities()
        assert caps.supports_streaming is True
        assert caps.supports_tools is True
        assert caps.supports_vision is True
        assert caps.max_context_length == 128000
        assert ModelType.FAST in caps.supported_model_types

    def test_openai_map_models(self):
        """Test OpenAI model mapping."""
        config = create_test_config(provider="openai", api_key="sk-test")
        handler = OpenAIProviderHandler(config)

        mapping = handler.map_models()
        assert mapping[ModelType.FAST] == "gpt-3.5-turbo"
        assert mapping[ModelType.SMART] == "gpt-4o-mini"
        assert mapping[ModelType.DEEP_THINKING] == "gpt-4o"

    def test_openai_calculate_cost(self):
        """Test OpenAI cost calculation."""
        config = create_test_config(provider="openai", api_key="sk-test")
        handler = OpenAIProviderHandler(config)

        cost = handler.calculate_cost("gpt-4o", 1000, 500)
        assert cost > 0
        # gpt-4o: 0.005 per 1k input, 0.01 per 1k output (2x multiplier)
        # 1000 input tokens = 1 * 0.005 = 0.005
        # 500 output tokens = 0.5 * 0.01 = 0.005
        # Total = 0.01
        assert cost == pytest.approx(0.01, rel=1e-2)


class TestAnthropicProviderHandler:
    """Test Anthropic provider handler."""

    def test_anthropic_handler_creation(self):
        """Test creating Anthropic handler."""
        config = create_test_config(
            provider="anthropic",
            api_key="sk-ant-test123456789012345678901234567890",
            models={
                "claude-3-sonnet": create_test_model_config(
                    "claude-3-sonnet", ModelType.SMART
                )
            },
        )

        handler = AnthropicProviderHandler(config)
        assert handler.provider_name == "anthropic"

    def test_anthropic_validate_credentials_valid(self):
        """Test Anthropic credential validation with valid key."""
        config = create_test_config(
            provider="anthropic", api_key="sk-ant-test123456789012345678901234567890"
        )

        handler = AnthropicProviderHandler(config)
        is_valid, error = handler.validate_credentials()
        assert is_valid is True
        assert error is None

    def test_anthropic_validate_credentials_invalid_format(self):
        """Test Anthropic credential validation with invalid format."""
        config = create_test_config(provider="anthropic", api_key="invalid-key")

        handler = AnthropicProviderHandler(config)
        is_valid, error = handler.validate_credentials()
        assert is_valid is False
        assert error is not None and "must start with 'sk-ant-'" in error

    def test_anthropic_get_capabilities(self):
        """Test Anthropic capabilities."""
        config = create_test_config(provider="anthropic", api_key="sk-ant-test")
        handler = AnthropicProviderHandler(config)

        caps = handler.get_capabilities()
        assert caps.supports_streaming is True
        assert caps.supports_tools is True
        assert caps.max_context_length == 200000

    def test_anthropic_calculate_cost(self):
        """Test Anthropic cost calculation."""
        config = create_test_config(provider="anthropic", api_key="sk-ant-test")
        handler = AnthropicProviderHandler(config)

        cost = handler.calculate_cost("claude-3-5-sonnet-20241022", 1000, 500)
        assert cost > 0


class TestOllamaProviderHandler:
    """Test Ollama provider handler."""

    def test_ollama_handler_creation(self):
        """Test creating Ollama handler."""
        config = create_test_config(
            provider="ollama",
            base_url="http://localhost:11434",
            models={
                "llama3.2:3b": create_test_model_config("llama3.2:3b", ModelType.SMART)
            },
        )

        handler = OllamaProviderHandler(config)
        assert handler.provider_name == "ollama"

    def test_ollama_validate_config_with_api_key(self):
        """Test Ollama config validation with API key (should error)."""
        config = create_test_config(provider="ollama", api_key="should-not-have-key")

        handler = OllamaProviderHandler(config)
        errors = handler.validate_config()
        assert "Ollama does not use API keys" in errors

    def test_ollama_validate_credentials(self):
        """Test Ollama credential validation (always valid)."""
        config = create_test_config(provider="ollama")
        handler = OllamaProviderHandler(config)

        is_valid, error = handler.validate_credentials()
        assert is_valid is True
        assert error is None

    def test_ollama_get_capabilities(self):
        """Test Ollama capabilities."""
        config = create_test_config(provider="ollama")
        handler = OllamaProviderHandler(config)

        caps = handler.get_capabilities()
        assert caps.supports_streaming is True
        assert caps.supports_tools is False  # Depends on model
        assert caps.max_context_length == 32768

    def test_ollama_calculate_cost(self):
        """Test Ollama cost calculation (free)."""
        config = create_test_config(provider="ollama")
        handler = OllamaProviderHandler(config)

        cost = handler.calculate_cost("llama3.2:3b", 1000, 500)
        assert cost == 0.0


class TestGrokProviderHandler:
    """Test Grok provider handler."""

    def test_grok_handler_creation(self):
        """Test creating Grok handler."""
        config = create_test_config(
            provider="grok",
            api_key="test123456789012345678901234567890",
            models={
                "grok-beta": create_test_model_config("grok-beta", ModelType.SMART)
            },
        )

        handler = GrokProviderHandler(config)
        assert handler.provider_name == "grok"

    def test_grok_validate_config_missing_api_key(self):
        """Test Grok config validation with missing API key."""
        # Create a valid config first, then modify it to test validation
        config = create_test_config(
            provider="grok", api_key="test123456789012345678901234567890"
        )

        # Manually set api_key to None to test validation logic
        config.api_key = None

        handler = GrokProviderHandler(config)
        errors = handler.validate_config()
        assert "Grok API key is required" in errors

    def test_grok_get_capabilities(self):
        """Test Grok capabilities."""
        config = create_test_config(provider="grok", api_key="test")
        handler = GrokProviderHandler(config)

        caps = handler.get_capabilities()
        assert caps.supports_streaming is True
        assert caps.supports_tools is False  # Not yet supported
        assert caps.max_context_length == 128000


class TestBedrockProviderHandler:
    """Test Bedrock provider handler."""

    def test_bedrock_handler_creation(self):
        """Test creating Bedrock handler."""
        config = create_test_config(
            provider="bedrock",
            api_key="AKIAIOSFODNN7EXAMPLE",
            region="us-east-1",
            models={
                "claude-3-sonnet": create_test_model_config(
                    "claude-3-sonnet", ModelType.SMART
                )
            },
        )

        handler = BedrockProviderHandler(config)
        assert handler.provider_name == "bedrock"

    def test_bedrock_validate_config_missing_region(self):
        """Test Bedrock config validation with missing region."""
        config = create_test_config(provider="bedrock", api_key="AKIAIOSFODNN7EXAMPLE")

        handler = BedrockProviderHandler(config)
        errors = handler.validate_config()
        assert "AWS region is required for Bedrock" in errors

    def test_bedrock_validate_credentials_valid(self):
        """Test Bedrock credential validation with valid credentials."""
        config = create_test_config(
            provider="bedrock", api_key="AKIAIOSFODNN7EXAMPLE", region="us-east-1"
        )

        handler = BedrockProviderHandler(config)
        is_valid, error = handler.validate_credentials()
        assert is_valid is True
        assert error is None

    def test_bedrock_validate_credentials_invalid_key_length(self):
        """Test Bedrock credential validation with invalid key length."""
        config = create_test_config(
            provider="bedrock", api_key="short", region="us-east-1"
        )

        handler = BedrockProviderHandler(config)
        is_valid, error = handler.validate_credentials()
        assert is_valid is False
        assert error is not None and "must be 20 characters long" in error


class TestProviderHandlerFactory:
    """Test ProviderHandlerFactory."""

    def test_create_handler_openai(self):
        """Test creating OpenAI handler via factory."""
        config = create_test_config(
            provider="openai", api_key="sk-test123456789012345678901234567890"
        )

        handler = ProviderHandlerFactory.create_handler(config)
        assert isinstance(handler, OpenAIProviderHandler)

    def test_create_handler_anthropic(self):
        """Test creating Anthropic handler via factory."""
        config = create_test_config(
            provider="anthropic", api_key="sk-ant-test123456789012345678901234567890"
        )

        handler = ProviderHandlerFactory.create_handler(config)
        assert isinstance(handler, AnthropicProviderHandler)

    def test_create_handler_unsupported(self):
        """Test creating handler for unsupported provider."""
        # Create a mock config object to bypass Pydantic validation
        config = MagicMock()
        config.provider = "unsupported"

        with pytest.raises(LLMProviderError) as exc_info:
            ProviderHandlerFactory.create_handler(config)

        assert exc_info.value.severity == ErrorSeverity.CRITICAL
        assert "Unsupported provider: unsupported" in str(exc_info.value)

    def test_get_supported_providers(self):
        """Test getting supported providers list."""
        providers = ProviderHandlerFactory.get_supported_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert "ollama" in providers
        assert "grok" in providers
        assert "bedrock" in providers

    def test_validate_provider_config_openai(self):
        """Test validating OpenAI config via factory."""
        config = create_test_config(
            provider="openai", api_key="sk-test123456789012345678901234567890"
        )

        errors = ProviderHandlerFactory.validate_provider_config(config)
        assert len(errors) == 0

    def test_validate_provider_config_unsupported(self):
        """Test validating unsupported provider config via factory."""
        # Create a mock config object to bypass Pydantic validation
        config = MagicMock()
        config.provider = "unsupported"

        errors = ProviderHandlerFactory.validate_provider_config(config)
        assert len(errors) == 1
        assert "Unsupported provider: unsupported" in errors[0]

    def test_validate_provider_credentials_openai(self):
        """Test validating OpenAI credentials via factory."""
        config = create_test_config(
            provider="openai", api_key="sk-test123456789012345678901234567890"
        )

        is_valid, error = ProviderHandlerFactory.validate_provider_credentials(config)
        assert is_valid is True
        assert error is None

    def test_validate_provider_credentials_unsupported(self):
        """Test validating unsupported provider credentials via factory."""
        # Create a mock config object to bypass Pydantic validation
        config = MagicMock()
        config.provider = "unsupported"

        is_valid, error = ProviderHandlerFactory.validate_provider_credentials(config)
        assert is_valid is False
        assert error is not None and "Unsupported provider: unsupported" in error


class TestBaseProviderHandler:
    """Test BaseProviderHandler abstract class."""

    def test_get_model_config(self):
        """Test getting model configuration."""
        config = create_test_config(
            provider="openai",
            api_key="sk-test",
            models={
                "gpt-4o-mini": create_test_model_config("gpt-4o-mini", ModelType.SMART)
            },
        )

        handler = OpenAIProviderHandler(config)

        # Test getting existing model config
        model_config = handler.get_model_config(ModelType.SMART)
        assert model_config is not None
        assert model_config.name == "gpt-4o-mini"

        # Test getting non-existing model config
        model_config = handler.get_model_config(ModelType.CODE)
        assert model_config is None
