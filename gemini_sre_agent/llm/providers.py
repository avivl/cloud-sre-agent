# gemini_sre_agent/llm/providers.py

"""
Provider-specific configuration handlers for multi-LLM provider support.

This module provides specialized configuration handlers for each supported
LLM provider with provider-specific validation, credential testing, and
capability detection.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .base import ErrorSeverity, LLMProviderError, ModelType
from .config import LLMProviderConfig, ModelConfig

logger = logging.getLogger(__name__)


@dataclass
class ProviderCapabilities:
    """Provider capability information."""

    supports_streaming: bool
    supports_tools: bool
    supports_vision: bool
    supports_function_calling: bool
    max_context_length: int
    supported_model_types: List[ModelType]
    cost_per_1k_tokens: Dict[str, float]  # Model name -> cost


class BaseProviderHandler(ABC):
    """Base class for provider-specific configuration handlers."""

    def __init__(self, config: LLMProviderConfig):
        self.config = config
        self.provider_name = config.provider

    @abstractmethod
    def validate_config(self) -> List[str]:
        """Validate provider-specific configuration."""
        pass

    @abstractmethod
    def validate_credentials(self) -> Tuple[bool, Optional[str]]:
        """Validate provider credentials. Returns (is_valid, error_message)."""
        pass

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Get provider capabilities based on configuration."""
        pass

    @abstractmethod
    def map_models(self) -> Dict[ModelType, str]:
        """Map semantic model types to provider-specific model names."""
        pass

    @abstractmethod
    def calculate_cost(
        self, model_name: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Calculate cost for a specific model and token usage."""
        pass

    def get_model_config(self, model_type: ModelType) -> Optional[ModelConfig]:
        """Get model configuration for a specific model type."""
        model_mapping = self.map_models()
        if model_type not in model_mapping:
            return None

        model_name = model_mapping[model_type]
        return self.config.models.get(model_name)


class OpenAIProviderHandler(BaseProviderHandler):
    """OpenAI provider configuration handler."""

    def validate_config(self) -> List[str]:
        """Validate OpenAI-specific configuration."""
        errors = []

        if not self.config.api_key:
            errors.append("OpenAI API key is required")

        if self.config.base_url and not str(self.config.base_url).startswith(
            ("http://", "https://")
        ):
            errors.append("OpenAI base_url must be a valid HTTP/HTTPS URL")

        # Validate models
        for model_name, model_config in self.config.models.items():
            if not model_name.startswith(("gpt-", "o1-", "dall-e-")):
                errors.append(f"Invalid OpenAI model name: {model_name}")

            if model_config.max_tokens > 128000:
                errors.append(
                    f"Model {model_name} max_tokens exceeds OpenAI limit (128,000)"
                )

        return errors

    def validate_credentials(self) -> Tuple[bool, Optional[str]]:
        """Validate OpenAI credentials."""
        if not self.config.api_key:
            return False, "OpenAI API key is required"

        # Basic format validation
        if not self.config.api_key.startswith("sk-"):
            return False, "OpenAI API key must start with 'sk-'"

        if len(self.config.api_key) < 20:
            return False, "OpenAI API key appears to be too short"

        return True, None

    def get_capabilities(self) -> ProviderCapabilities:
        """Get OpenAI capabilities."""
        return ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_vision=True,
            supports_function_calling=True,
            max_context_length=128000,
            supported_model_types=[
                ModelType.FAST,
                ModelType.SMART,
                ModelType.DEEP_THINKING,
                ModelType.CODE,
                ModelType.ANALYSIS,
            ],
            cost_per_1k_tokens={
                "gpt-4o": 0.005,
                "gpt-4o-mini": 0.00015,
                "gpt-4-turbo": 0.01,
                "gpt-3.5-turbo": 0.0005,
                "o1-preview": 0.015,
                "o1-mini": 0.003,
            },
        )

    def map_models(self) -> Dict[ModelType, str]:
        """Map semantic model types to OpenAI model names."""
        return {
            ModelType.FAST: "gpt-3.5-turbo",
            ModelType.SMART: "gpt-4o-mini",
            ModelType.DEEP_THINKING: "gpt-4o",
            ModelType.CODE: "gpt-4o",
            ModelType.ANALYSIS: "o1-preview",
        }

    def calculate_cost(
        self, model_name: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Calculate OpenAI cost."""
        capabilities = self.get_capabilities()
        cost_per_1k = capabilities.cost_per_1k_tokens.get(model_name, 0.0)

        input_cost = (input_tokens / 1000) * cost_per_1k
        output_cost = (
            (output_tokens / 1000) * cost_per_1k * 2
        )  # Output is typically 2x input cost

        return input_cost + output_cost


class AnthropicProviderHandler(BaseProviderHandler):
    """Anthropic provider configuration handler."""

    def validate_config(self) -> List[str]:
        """Validate Anthropic-specific configuration."""
        errors = []

        if not self.config.api_key:
            errors.append("Anthropic API key is required")

        if self.config.base_url and not str(self.config.base_url).startswith(
            ("http://", "https://")
        ):
            errors.append("Anthropic base_url must be a valid HTTP/HTTPS URL")

        # Validate models
        for model_name, model_config in self.config.models.items():
            if not model_name.startswith(("claude-", "sonnet-", "haiku-", "opus-")):
                errors.append(f"Invalid Anthropic model name: {model_name}")

            if model_config.max_tokens > 200000:
                errors.append(
                    f"Model {model_name} max_tokens exceeds Anthropic limit (200,000)"
                )

        return errors

    def validate_credentials(self) -> Tuple[bool, Optional[str]]:
        """Validate Anthropic credentials."""
        if not self.config.api_key:
            return False, "Anthropic API key is required"

        # Basic format validation
        if not self.config.api_key.startswith("sk-ant-"):
            return False, "Anthropic API key must start with 'sk-ant-'"

        if len(self.config.api_key) < 30:
            return False, "Anthropic API key appears to be too short"

        return True, None

    def get_capabilities(self) -> ProviderCapabilities:
        """Get Anthropic capabilities."""
        return ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_vision=True,
            supports_function_calling=True,
            max_context_length=200000,
            supported_model_types=[
                ModelType.FAST,
                ModelType.SMART,
                ModelType.DEEP_THINKING,
                ModelType.CODE,
                ModelType.ANALYSIS,
            ],
            cost_per_1k_tokens={
                "claude-3-5-sonnet-20241022": 0.003,
                "claude-3-5-haiku-20241022": 0.0008,
                "claude-3-opus-20240229": 0.015,
                "claude-3-sonnet-20240229": 0.003,
                "claude-3-haiku-20240307": 0.00025,
            },
        )

    def map_models(self) -> Dict[ModelType, str]:
        """Map semantic model types to Anthropic model names."""
        return {
            ModelType.FAST: "claude-3-haiku-20240307",
            ModelType.SMART: "claude-3-5-haiku-20241022",
            ModelType.DEEP_THINKING: "claude-3-5-sonnet-20241022",
            ModelType.CODE: "claude-3-5-sonnet-20241022",
            ModelType.ANALYSIS: "claude-3-opus-20240229",
        }

    def calculate_cost(
        self, model_name: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Calculate Anthropic cost."""
        capabilities = self.get_capabilities()
        cost_per_1k = capabilities.cost_per_1k_tokens.get(model_name, 0.0)

        input_cost = (input_tokens / 1000) * cost_per_1k
        output_cost = (
            (output_tokens / 1000) * cost_per_1k * 5
        )  # Output is typically 5x input cost for Anthropic

        return input_cost + output_cost


class OllamaProviderHandler(BaseProviderHandler):
    """Ollama provider configuration handler."""

    def validate_config(self) -> List[str]:
        """Validate Ollama-specific configuration."""
        errors = []

        # Ollama doesn't require API key
        if self.config.api_key:
            errors.append("Ollama does not use API keys")

        # Validate base URL
        if not self.config.base_url:
            # Note: We can't modify the config here due to Pydantic validation
            # This should be handled at the config level
            pass

        if self.config.base_url and not str(self.config.base_url).startswith(
            ("http://", "https://")
        ):
            errors.append("Ollama base_url must be a valid HTTP/HTTPS URL")

        # Validate models
        for model_name, model_config in self.config.models.items():
            if model_config.max_tokens > 32768:
                errors.append(
                    f"Model {model_name} max_tokens exceeds typical Ollama limit (32,768)"
                )

        return errors

    def validate_credentials(self) -> Tuple[bool, Optional[str]]:
        """Validate Ollama credentials."""
        # Ollama doesn't require credentials
        return True, None

    def get_capabilities(self) -> ProviderCapabilities:
        """Get Ollama capabilities."""
        return ProviderCapabilities(
            supports_streaming=True,
            supports_tools=False,  # Depends on model
            supports_vision=False,  # Depends on model
            supports_function_calling=False,  # Depends on model
            max_context_length=32768,
            supported_model_types=[
                ModelType.FAST,
                ModelType.SMART,
                ModelType.DEEP_THINKING,
                ModelType.CODE,
                ModelType.ANALYSIS,
            ],
            cost_per_1k_tokens={},  # Free to use
        )

    def map_models(self) -> Dict[ModelType, str]:
        """Map semantic model types to Ollama model names."""
        return {
            ModelType.FAST: "llama3.2:1b",
            ModelType.SMART: "llama3.2:3b",
            ModelType.DEEP_THINKING: "llama3.2:11b",
            ModelType.CODE: "codellama:7b",
            ModelType.ANALYSIS: "llama3.2:11b",
        }

    def calculate_cost(
        self, model_name: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Calculate Ollama cost (free)."""
        return 0.0


class GrokProviderHandler(BaseProviderHandler):
    """Grok (xAI) provider configuration handler."""

    def validate_config(self) -> List[str]:
        """Validate Grok-specific configuration."""
        errors = []

        if not self.config.api_key:
            errors.append("Grok API key is required")

        if self.config.base_url and not str(self.config.base_url).startswith(
            ("http://", "https://")
        ):
            errors.append("Grok base_url must be a valid HTTP/HTTPS URL")

        # Validate models
        for model_name, _model_config in self.config.models.items():
            if not model_name.startswith(("grok-", "grok-beta")):
                errors.append(f"Invalid Grok model name: {model_name}")

        return errors

    def validate_credentials(self) -> Tuple[bool, Optional[str]]:
        """Validate Grok credentials."""
        if not self.config.api_key:
            return False, "Grok API key is required"

        # Basic format validation
        if len(self.config.api_key) < 20:
            return False, "Grok API key appears to be too short"

        return True, None

    def get_capabilities(self) -> ProviderCapabilities:
        """Get Grok capabilities."""
        return ProviderCapabilities(
            supports_streaming=True,
            supports_tools=False,  # Not yet supported
            supports_vision=False,  # Not yet supported
            supports_function_calling=False,  # Not yet supported
            max_context_length=128000,
            supported_model_types=[
                ModelType.FAST,
                ModelType.SMART,
                ModelType.DEEP_THINKING,
            ],
            cost_per_1k_tokens={"grok-beta": 0.001, "grok-2": 0.001},
        )

    def map_models(self) -> Dict[ModelType, str]:
        """Map semantic model types to Grok model names."""
        return {
            ModelType.FAST: "grok-beta",
            ModelType.SMART: "grok-beta",
            ModelType.DEEP_THINKING: "grok-2",
        }

    def calculate_cost(
        self, model_name: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Calculate Grok cost."""
        capabilities = self.get_capabilities()
        cost_per_1k = capabilities.cost_per_1k_tokens.get(model_name, 0.0)

        input_cost = (input_tokens / 1000) * cost_per_1k
        output_cost = (output_tokens / 1000) * cost_per_1k * 2

        return input_cost + output_cost


class BedrockProviderHandler(BaseProviderHandler):
    """AWS Bedrock provider configuration handler."""

    def validate_config(self) -> List[str]:
        """Validate Bedrock-specific configuration."""
        errors = []

        if not self.config.region:
            errors.append("AWS region is required for Bedrock")

        if not self.config.api_key:  # AWS Access Key
            errors.append("AWS Access Key is required for Bedrock")

        # Validate models
        for model_name, _model_config in self.config.models.items():
            if not any(
                model_name.startswith(prefix)
                for prefix in ["claude-", "llama-", "titan-", "j2-", "command-"]
            ):
                errors.append(f"Invalid Bedrock model name: {model_name}")

        return errors

    def validate_credentials(self) -> Tuple[bool, Optional[str]]:
        """Validate Bedrock credentials."""
        if not self.config.api_key:
            return False, "AWS Access Key is required for Bedrock"

        if not self.config.region:
            return False, "AWS region is required for Bedrock"

        # Basic format validation for AWS Access Key
        if len(self.config.api_key) != 20:
            return False, "AWS Access Key must be 20 characters long"

        return True, None

    def get_capabilities(self) -> ProviderCapabilities:
        """Get Bedrock capabilities."""
        return ProviderCapabilities(
            supports_streaming=True,
            supports_tools=True,
            supports_vision=True,
            supports_function_calling=True,
            max_context_length=200000,
            supported_model_types=[
                ModelType.FAST,
                ModelType.SMART,
                ModelType.DEEP_THINKING,
                ModelType.CODE,
                ModelType.ANALYSIS,
            ],
            cost_per_1k_tokens={
                "claude-3-5-sonnet-20241022-v2:0": 0.003,
                "claude-3-5-haiku-20241022-v1:0": 0.0008,
                "claude-3-opus-20240229-v1:0": 0.015,
                "llama3.2-11b-instruct-v1:0": 0.00065,
                "llama3.2-3b-instruct-v1:0": 0.0002,
            },
        )

    def map_models(self) -> Dict[ModelType, str]:
        """Map semantic model types to Bedrock model names."""
        return {
            ModelType.FAST: "claude-3-5-haiku-20241022-v1:0",
            ModelType.SMART: "claude-3-5-sonnet-20241022-v2:0",
            ModelType.DEEP_THINKING: "claude-3-opus-20240229-v1:0",
            ModelType.CODE: "llama3.2-11b-instruct-v1:0",
            ModelType.ANALYSIS: "claude-3-opus-20240229-v1:0",
        }

    def calculate_cost(
        self, model_name: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Calculate Bedrock cost."""
        capabilities = self.get_capabilities()
        cost_per_1k = capabilities.cost_per_1k_tokens.get(model_name, 0.0)

        input_cost = (input_tokens / 1000) * cost_per_1k
        output_cost = (output_tokens / 1000) * cost_per_1k * 2

        return input_cost + output_cost


class ProviderHandlerFactory:
    """Factory for creating provider-specific handlers."""

    _handlers = {
        "openai": OpenAIProviderHandler,
        "anthropic": AnthropicProviderHandler,
        "ollama": OllamaProviderHandler,
        "grok": GrokProviderHandler,
        "bedrock": BedrockProviderHandler,
    }

    @classmethod
    def create_handler(cls, config: LLMProviderConfig) -> BaseProviderHandler:
        """Create a provider-specific handler."""
        handler_class = cls._handlers.get(config.provider)
        if not handler_class:
            raise LLMProviderError(
                f"Unsupported provider: {config.provider}",
                severity=ErrorSeverity.CRITICAL,
            )

        return handler_class(config)

    @classmethod
    def get_supported_providers(cls) -> List[str]:
        """Get list of supported providers."""
        return list(cls._handlers.keys())

    @classmethod
    def validate_provider_config(cls, config: LLMProviderConfig) -> List[str]:
        """Validate provider configuration using appropriate handler."""
        try:
            handler = cls.create_handler(config)
            return handler.validate_config()
        except LLMProviderError:
            return [f"Unsupported provider: {config.provider}"]

    @classmethod
    def validate_provider_credentials(
        cls, config: LLMProviderConfig
    ) -> Tuple[bool, Optional[str]]:
        """Validate provider credentials using appropriate handler."""
        try:
            handler = cls.create_handler(config)
            return handler.validate_credentials()
        except LLMProviderError:
            return False, f"Unsupported provider: {config.provider}"
