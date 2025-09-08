import logging
from typing import Dict, List, Optional

from gemini_sre_agent.llm.capabilities.models import ModelCapabilities

logger = logging.getLogger(__name__)


class CapabilityDatabase:
    """
    A database for storing and querying model capabilities.
    """

    def __init__(self):
        self._capabilities: Dict[str, ModelCapabilities] = {}

    def add_capabilities(self, model_capabilities: ModelCapabilities) -> None:
        """
        Add or update capabilities for a model.

        Args:
            model_capabilities: The ModelCapabilities object to add.
        """
        self._capabilities[model_capabilities.model_id] = model_capabilities
        logger.info(
            f"Added/updated capabilities for model: {model_capabilities.model_id}"
        )

    def get_capabilities(self, model_id: str) -> Optional[ModelCapabilities]:
        """
        Retrieve capabilities for a specific model.

        Args:
            model_id: The unique identifier for the model.

        Returns:
            ModelCapabilities object if found, None otherwise.
        """
        return self._capabilities.get(model_id)

    def query_capabilities(
        self, capability_name: Optional[str] = None
    ) -> List[ModelCapabilities]:
        """
        Query models based on their capabilities.

        Args:
            capability_name: Optional. The name of the capability to query for.

        Returns:
            A list of ModelCapabilities objects that match the query.
        """
        results = []
        for model_caps in self._capabilities.values():
            if capability_name:
                if any(cap.name == capability_name for cap in model_caps.capabilities):
                    results.append(model_caps)
            else:
                results.append(model_caps)
        return results

    def clear(self) -> None:
        """
        Clear all capabilities from the database.
        """
        self._capabilities.clear()
        logger.info("Capability database cleared.")

    def __len__(self) -> int:
        return len(self._capabilities)

    def __contains__(self, model_id: str) -> bool:
        return model_id in self._capabilities

    def get_all_model_ids(self) -> List[str]:
        """
        Get all model IDs in the database.

        Returns:
            A list of all model IDs.
        """
        return list(self._capabilities.keys())
