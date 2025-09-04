"""
Provider Capability Discovery System.

This module provides a system for discovering and cataloging provider capabilities,
enabling intelligent provider selection based on required features.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..base import LLMProvider

logger = logging.getLogger(__name__)


class ProviderCapability:
    """Represents a specific capability of a provider."""

    def __init__(self, name: str, description: str, required: bool = False):
        self.name = name
        self.description = description
        self.required = required
        self.supported = False
        self.details: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert capability to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "required": self.required,
            "supported": self.supported,
            "details": self.details,
        }


class ProviderCapabilityDiscovery:
    """
    System for discovering and cataloging provider capabilities.

    Automatically detects what features each provider supports and maintains
    a registry of capabilities for intelligent provider selection.
    """

    def __init__(self):
        self.capability_registry: Dict[str, Dict[str, ProviderCapability]] = {}
        self.capability_tests: Dict[str, Any] = {
            "streaming": self._test_streaming_capability,
            "tools": self._test_tools_capability,
            "embeddings": self._test_embeddings_capability,
            "vision": self._test_vision_capability,
            "function_calling": self._test_function_calling_capability,
            "json_mode": self._test_json_mode_capability,
            "parallel_requests": self._test_parallel_requests_capability,
            "custom_models": self._test_custom_models_capability,
        }

    async def discover_provider_capabilities(
        self, provider: LLMProvider
    ) -> Dict[str, ProviderCapability]:
        """
        Discover all capabilities of a provider.

        Args:
            provider: The provider to analyze

        Returns:
            Dictionary mapping capability names to ProviderCapability objects
        """
        provider_name = provider.provider_name
        capabilities = {}

        logger.info(f"Discovering capabilities for provider: {provider_name}")

        for capability_name, test_func in self.capability_tests.items():
            try:
                capability = ProviderCapability(
                    name=capability_name,
                    description=self._get_capability_description(capability_name),
                    required=False,
                )

                # Test the capability
                if asyncio.iscoroutinefunction(test_func):
                    capability.supported = await test_func(provider)
                else:
                    capability.supported = test_func(provider)
                capability.details = await self._get_capability_details(
                    provider, capability_name
                )

                capabilities[capability_name] = capability

                logger.debug(
                    f"Capability {capability_name}: {'supported' if capability.supported else 'not supported'}"
                )

            except Exception as e:
                logger.warning(
                    f"Failed to test capability {capability_name} for {provider_name}: {e}"
                )
                capability = ProviderCapability(
                    name=capability_name,
                    description=self._get_capability_description(capability_name),
                    required=False,
                )
                capability.supported = False
                capability.details = {"error": str(e)}
                capabilities[capability_name] = capability

        # Store in registry
        self.capability_registry[provider_name] = capabilities

        logger.info(f"Discovered {len(capabilities)} capabilities for {provider_name}")
        return capabilities

    async def _test_streaming_capability(self, provider: LLMProvider) -> bool:
        """Test if provider supports streaming."""
        try:
            return provider.supports_streaming()
        except Exception:
            return False

    async def _test_tools_capability(self, provider: LLMProvider) -> bool:
        """Test if provider supports tool calling."""
        try:
            return provider.supports_tools()
        except Exception:
            return False

    async def _test_embeddings_capability(self, provider: LLMProvider) -> bool:
        """Test if provider supports embeddings."""
        try:
            # Try to generate embeddings for a simple text
            await provider.embeddings("test")
            return True
        except NotImplementedError:
            return False
        except Exception:
            # If it's not NotImplementedError, the provider might support it
            return True

    async def _test_vision_capability(self, provider: LLMProvider) -> bool:
        """Test if provider supports vision/image processing."""
        try:
            # Check if the provider has vision-related methods or models
            models = provider.get_available_models()
            vision_models = [
                model
                for model in models.values()
                if "vision" in model.lower() or "image" in model.lower()
            ]
            return len(vision_models) > 0
        except Exception:
            return False

    async def _test_function_calling_capability(self, provider: LLMProvider) -> bool:
        """Test if provider supports function calling."""
        try:
            # This is similar to tools capability
            return provider.supports_tools()
        except Exception:
            return False

    async def _test_json_mode_capability(self, provider: LLMProvider) -> bool:
        """Test if provider supports JSON mode."""
        try:
            # Check if the provider supports structured output
            # This is a heuristic - we'll check if it has JSON-related configuration
            config = getattr(provider, "config", None)
            if config and hasattr(config, "provider_specific"):
                provider_specific = getattr(config, "provider_specific", {})
                return (
                    "json_mode" in provider_specific
                    or "structured_output" in provider_specific
                )
            return False
        except Exception:
            return False

    async def _test_parallel_requests_capability(self, provider: LLMProvider) -> bool:
        """Test if provider supports parallel requests."""
        try:
            # Test by making multiple concurrent requests
            tasks = []
            for _ in range(3):
                task = provider.health_check()
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            # If all requests succeeded, the provider likely supports parallel requests
            return all(not isinstance(result, Exception) for result in results)
        except Exception:
            return False

    async def _test_custom_models_capability(self, provider: LLMProvider) -> bool:
        """Test if provider supports custom models."""
        try:
            # Check if the provider has configuration for custom models
            config = getattr(provider, "config", None)
            if config and hasattr(config, "provider_specific"):
                provider_specific = getattr(config, "provider_specific", {})
                return (
                    "custom_models" in provider_specific
                    or "fine_tuned_models" in provider_specific
                )
            return False
        except Exception:
            return False

    def _get_capability_description(self, capability_name: str) -> str:
        """Get description for a capability."""
        descriptions = {
            "streaming": "Supports streaming responses for real-time output",
            "tools": "Supports tool calling and function execution",
            "embeddings": "Supports text embedding generation",
            "vision": "Supports image and vision processing",
            "function_calling": "Supports function calling capabilities",
            "json_mode": "Supports structured JSON output mode",
            "parallel_requests": "Supports multiple concurrent requests",
            "custom_models": "Supports custom or fine-tuned models",
        }
        return descriptions.get(capability_name, f"Capability: {capability_name}")

    async def _get_capability_details(
        self, provider: LLMProvider, capability_name: str
    ) -> Dict[str, Any]:
        """Get detailed information about a capability."""
        details = {}

        try:
            if capability_name == "streaming":
                details["implementation"] = (
                    "generate_stream"
                    if hasattr(provider, "generate_stream")
                    else "fallback"
                )

            elif capability_name == "tools":
                details["implementation"] = (
                    "supports_tools"
                    if hasattr(provider, "supports_tools")
                    else "unknown"
                )

            elif capability_name == "embeddings":
                details["implementation"] = (
                    "embeddings"
                    if hasattr(provider, "embeddings")
                    else "not_implemented"
                )

            elif capability_name == "vision":
                models = provider.get_available_models()
                vision_models = [
                    model
                    for model in models.values()
                    if "vision" in model.lower() or "image" in model.lower()
                ]
                details["vision_models"] = vision_models

            elif capability_name == "parallel_requests":
                details["test_method"] = "concurrent_health_checks"

            elif capability_name == "custom_models":
                config = getattr(provider, "config", None)
                if config and hasattr(config, "provider_specific"):
                    provider_specific = getattr(config, "provider_specific", {})
                    details["custom_model_config"] = provider_specific.get(
                        "custom_models", {}
                    )

        except Exception as e:
            details["error"] = str(e)

        return details

    def get_provider_capabilities(
        self, provider_name: str
    ) -> Optional[Dict[str, ProviderCapability]]:
        """Get capabilities for a specific provider."""
        return self.capability_registry.get(provider_name)

    def get_capability_summary(self) -> Dict[str, Any]:
        """Get a summary of all provider capabilities."""
        summary = {
            "total_providers": len(self.capability_registry),
            "capability_counts": {},
            "provider_capabilities": {},
        }

        # Count capabilities across all providers
        for provider_name, capabilities in self.capability_registry.items():
            provider_summary = {}
            for capability_name, capability in capabilities.items():
                if capability.supported:
                    summary["capability_counts"][capability_name] = (
                        summary["capability_counts"].get(capability_name, 0) + 1
                    )
                provider_summary[capability_name] = capability.supported

            summary["provider_capabilities"][provider_name] = provider_summary

        return summary

    def find_providers_with_capability(self, capability_name: str) -> List[str]:
        """Find all providers that support a specific capability."""
        providers = []

        for provider_name, capabilities in self.capability_registry.items():
            if (
                capability_name in capabilities
                and capabilities[capability_name].supported
            ):
                providers.append(provider_name)

        return providers

    def find_providers_matching_requirements(
        self, required_capabilities: List[str]
    ) -> List[str]:
        """Find providers that support all required capabilities."""
        matching_providers = []

        for provider_name, capabilities in self.capability_registry.items():
            supports_all = True

            for required_capability in required_capabilities:
                if (
                    required_capability not in capabilities
                    or not capabilities[required_capability].supported
                ):
                    supports_all = False
                    break

            if supports_all:
                matching_providers.append(provider_name)

        return matching_providers

    def get_capability_compatibility_matrix(self) -> Dict[str, Dict[str, bool]]:
        """Get a compatibility matrix of providers and capabilities."""
        matrix = {}

        for provider_name, capabilities in self.capability_registry.items():
            matrix[provider_name] = {}
            for capability_name, capability in capabilities.items():
                matrix[provider_name][capability_name] = capability.supported

        return matrix

    def validate_provider_for_use_case(
        self, provider_name: str, use_case: str
    ) -> Dict[str, Any]:
        """
        Validate if a provider is suitable for a specific use case.

        Args:
            provider_name: Name of the provider
            use_case: The use case (e.g., 'chat', 'embeddings', 'vision')

        Returns:
            Dictionary with validation results
        """
        if provider_name not in self.capability_registry:
            return {
                "valid": False,
                "error": "Provider not found in capability registry",
            }

        capabilities = self.capability_registry[provider_name]

        # Define use case requirements
        use_case_requirements = {
            "chat": ["streaming"],
            "embeddings": ["embeddings"],
            "vision": ["vision"],
            "tools": ["tools", "function_calling"],
            "json_output": ["json_mode"],
            "parallel_processing": ["parallel_requests"],
        }

        required_capabilities = use_case_requirements.get(use_case, [])

        validation_result = {
            "valid": True,
            "provider": provider_name,
            "use_case": use_case,
            "required_capabilities": required_capabilities,
            "supported_capabilities": [],
            "missing_capabilities": [],
            "score": 0,
        }

        for capability in required_capabilities:
            if capability in capabilities and capabilities[capability].supported:
                validation_result["supported_capabilities"].append(capability)
            else:
                validation_result["missing_capabilities"].append(capability)
                validation_result["valid"] = False

        # Calculate compatibility score
        if required_capabilities:
            validation_result["score"] = len(
                validation_result["supported_capabilities"]
            ) / len(required_capabilities)
        else:
            validation_result["score"] = 1.0

        return validation_result

    def discover_all_providers(
        self, providers: List[LLMProvider]
    ) -> Dict[str, Dict[str, ProviderCapability]]:
        """
        Discover capabilities for all providers.

        Args:
            providers: List of provider instances

        Returns:
            Dictionary mapping provider names to their capabilities
        """
        all_capabilities = {}

        for provider in providers:
            try:
                capabilities = self.discover_provider_capabilities(provider)
                all_capabilities[provider.provider_name] = capabilities
            except Exception as e:
                logger.error(
                    f"Failed to discover capabilities for {provider.provider_name}: {e}"
                )

        return all_capabilities

    def export_capability_report(self) -> Dict[str, Any]:
        """Export a comprehensive capability report."""
        return {
            "summary": self.get_capability_summary(),
            "compatibility_matrix": self.get_capability_compatibility_matrix(),
            "detailed_capabilities": {
                provider_name: {
                    capability_name: capability.to_dict()
                    for capability_name, capability in capabilities.items()
                }
                for provider_name, capabilities in self.capability_registry.items()
            },
        }


# Global capability discovery instance
_global_capability_discovery = ProviderCapabilityDiscovery()


def get_capability_discovery() -> ProviderCapabilityDiscovery:
    """Get the global capability discovery instance."""
    return _global_capability_discovery


async def discover_provider_capabilities(
    provider: LLMProvider,
) -> Dict[str, ProviderCapability]:
    """
    Convenience function to discover capabilities for a provider.

    Args:
        provider: The provider to analyze

    Returns:
        Dictionary mapping capability names to ProviderCapability objects
    """
    return await _global_capability_discovery.discover_provider_capabilities(provider)
