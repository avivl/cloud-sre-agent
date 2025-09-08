import logging
from typing import Dict, List, Optional

from gemini_sre_agent.llm.capabilities.models import ModelCapabilities, ModelCapability
from gemini_sre_agent.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class CapabilityDiscovery:
    """
    Discovers and catalogs capabilities of LLM models across various providers.
    """

    def __init__(self, providers: Dict[str, LLMProvider]):
        """
        Initialize the CapabilityDiscovery.

        Args:
            providers: A dictionary of initialized LLMProvider instances.
        """
        self.providers = providers
        self.model_capabilities: Dict[str, ModelCapabilities] = {}

    async def discover_capabilities(self) -> Dict[str, ModelCapabilities]:
        """
        Discover capabilities for all configured models across all providers.

        Returns:
            A dictionary mapping model IDs to their discovered capabilities.
        """
        for provider_name, provider_instance in self.providers.items():
            logger.info(f"Discovering capabilities for provider: {provider_name}")

            # Get models available for this provider
            available_models = provider_instance.get_available_models()

            for model_type, model_name in available_models.items():
                model_id = f"{provider_name}/{model_name}"

                # Placeholder for actual capability detection logic
                # In a real scenario, this would involve querying the model
                # or using predefined capability definitions.
                capabilities = []
                # Example heuristic: if supports_streaming or supports_tools are documented, assume text_generation
                # This is a simplification; real capability detection is more complex.
                if (
                    provider_instance.supports_streaming()
                    or provider_instance.supports_tools()
                ):
                    capabilities.append(
                        ModelCapability(
                            name="text_generation",
                            description="Generates human-like text based on a given prompt.",
                            parameters={
                                "max_tokens": {"type": "integer"},
                                "temperature": {"type": "float"},
                            },
                            performance_score=provider_instance.config.models[
                                model_name
                            ].performance_score,
                            cost_efficiency=provider_instance.config.models[
                                model_name
                            ].cost_per_1k_tokens,  # Simplified
                        )
                    )

                # Add other capabilities based on model_type or other heuristics
                if model_type.value == "code":
                    capabilities.append(
                        ModelCapability(
                            name="code_generation",
                            description="Generates programming code in various languages.",
                            parameters={
                                "language": {"type": "string"},
                                "framework": {"type": "string"},
                            },
                            performance_score=provider_instance.config.models[
                                model_name
                            ].performance_score,
                            cost_efficiency=provider_instance.config.models[
                                model_name
                            ].cost_per_1k_tokens,
                        )
                    )

                self.model_capabilities[model_id] = ModelCapabilities(
                    model_id=model_id, capabilities=capabilities
                )

        logger.info(
            f"Discovered capabilities for {len(self.model_capabilities)} models."
        )
        return self.model_capabilities

    def get_model_capabilities(self, model_id: str) -> Optional[ModelCapabilities]:
        """
        Retrieve capabilities for a specific model.

        Args:
            model_id: The unique identifier for the model (e.g., "gemini/gemini-pro").

        Returns:
            ModelCapabilities object if found, None otherwise.
        """
        return self.model_capabilities.get(model_id)

    def find_models_by_capability(self, capability_name: str) -> List[str]:
        """
        Find models that support a specific capability.

        Args:
            capability_name: The name of the capability to search for.

        Returns:
            A list of model IDs that support the capability.
        """
        matching_models = []
        for model_id, model_caps in self.model_capabilities.items():
            for cap in model_caps.capabilities:
                if cap.name == capability_name:
                    matching_models.append(model_id)
                    break
        return matching_models
