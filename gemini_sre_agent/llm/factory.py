# gemini_sre_agent/llm/factory.py

"""
Factory pattern implementation for LLM provider instantiation.

This module provides the LLMProviderFactory class that handles the creation
and management of LLM providers based on configuration.
"""

import logging
from typing import Any, Dict, List, Optional, Type

from .base import ErrorSeverity, LLMProvider, LLMProviderError
from .concrete_providers import (
    AnthropicProvider,
    BedrockProvider,
    GrokProvider,
    OllamaProvider,
    OpenAIProvider,
)
from .providers import GeminiProvider

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    """Factory for creating and managing LLM providers."""

    _providers: Dict[str, Type[LLMProvider]] = {
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
        "grok": GrokProvider,
        "bedrock": BedrockProvider,
    }
    _instances: Dict[str, LLMProvider] = {}

    @classmethod
    def create_provider(cls, provider_name: str, config: Any) -> LLMProvider:
        """
        Create a new provider instance.

        Args:
            provider_name: Name of the provider configuration
            config: Provider configuration

        Returns:
            LLMProvider instance

        Raises:
            LLMProviderError: If provider type is not supported
        """
        provider_type = config.provider

        if provider_type not in cls._providers:
            raise LLMProviderError(
                f"Unsupported provider type: {provider_type}",
                severity=ErrorSeverity.CRITICAL,
            )

        try:
            provider_class = cls._providers[provider_type]
            provider_class.validate_config(config)

            # Create instance key for caching
            instance_key = f"{provider_name}:{provider_type}"

            # Return cached instance if available
            if instance_key in cls._instances:
                logger.debug(f"Returning cached provider instance: {instance_key}")
                return cls._instances[instance_key]

            # Create new instance
            provider = provider_class(config)
            cls._instances[instance_key] = provider

            logger.info(f"Created new provider instance: {instance_key}")
            return provider

        except Exception as e:
            logger.error(f"Failed to create provider {provider_type}: {e}")
            raise LLMProviderError(
                f"Failed to create provider {provider_type}: {e}",
                severity=ErrorSeverity.CRITICAL,
            ) from e

    @classmethod
    def get_provider(cls, provider_name: str) -> Optional[LLMProvider]:
        """
        Get an existing provider instance by name.

        Args:
            provider_name: Name of the provider

        Returns:
            LLMProvider instance or None if not found
        """
        return cls._instances.get(provider_name)

    @classmethod
    def list_providers(cls) -> List[str]:
        """
        List all registered provider types.

        Returns:
            List of provider type names
        """
        return list(cls._providers.keys())

    @classmethod
    def list_instances(cls) -> List[str]:
        """
        List all provider instances.

        Returns:
            List of provider instance names
        """
        return list(cls._instances.keys())

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[LLMProvider]):
        """
        Register a new provider type.

        Args:
            name: Provider type name
            provider_class: Provider class implementation
        """
        if not issubclass(provider_class, LLMProvider):
            raise ValueError("Provider class must inherit from LLMProvider")

        cls._providers[name] = provider_class
        logger.info(f"Registered provider type: {name}")

    @classmethod
    def unregister_provider(cls, name: str):
        """
        Unregister a provider type.

        Args:
            name: Provider type name
        """
        if name in cls._providers:
            del cls._providers[name]
            logger.info(f"Unregistered provider type: {name}")

    @classmethod
    def clear_instances(cls):
        """Clear all provider instances."""
        cls._instances.clear()
        logger.info("Cleared all provider instances")

    @classmethod
    def health_check_all(cls) -> Dict[str, bool]:
        """
        Perform health check on all provider instances.

        Returns:
            Dictionary mapping provider names to health status
        """
        health_status = {}

        for name, provider in cls._instances.items():
            try:
                # Note: This would need to be async in real implementation
                # For now, we'll just check if the provider exists
                health_status[name] = provider is not None
            except Exception as e:
                logger.warning(f"Health check failed for {name}: {e}")
                health_status[name] = False

        return health_status

    @classmethod
    def create_providers_from_config(cls, config: Any) -> Dict[str, LLMProvider]:
        """
        Create providers from a configuration object.
        
        Args:
            config: Configuration object with providers
            
        Returns:
            Dictionary mapping provider names to provider instances
        """
        providers = {}
        
        for provider_name, provider_config in config.providers.items():
            try:
                provider = cls.create_provider(provider_name, provider_config)
                providers[provider_name] = provider
            except Exception as e:
                logger.error(f"Failed to create provider {provider_name}: {e}")
                # Continue with other providers
                continue
        
        return providers


def get_provider_factory() -> LLMProviderFactory:
    """Get a singleton instance of the provider factory."""
    return LLMProviderFactory
