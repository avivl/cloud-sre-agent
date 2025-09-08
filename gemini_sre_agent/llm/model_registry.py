# gemini_sre_agent/llm/model_registry.py

"""
Model Registry for semantic model naming and selection.

This module provides a configuration-driven system for mapping semantic model names
to specific provider models, enabling easy model selection across different providers.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import yaml

from .capabilities.database import CapabilityDatabase
from .capabilities.models import ModelCapability
from .common.enums import ModelType, ProviderType

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Information about a specific model."""

    name: str
    provider: ProviderType
    semantic_type: ModelType
    capabilities: List[ModelCapability] = field(default_factory=list)
    cost_per_1k_tokens: float = 0.0
    max_tokens: int = 4096
    context_window: int = 4096
    performance_score: float = 0.5  # 0.0 to 1.0
    reliability_score: float = 0.5  # 0.0 to 1.0
    fallback_models: List[str] = field(default_factory=list)
    provider_specific: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelRegistryConfig:
    """Configuration for the ModelRegistry."""

    config_file: Optional[Union[str, Path]] = None
    auto_reload: bool = False
    cache_ttl: int = 300  # 5 minutes
    default_weights: Dict[str, float] = field(
        default_factory=lambda: {"cost": 0.3, "performance": 0.4, "reliability": 0.3}
    )


class ModelRegistry:
    """
    Registry for managing semantic model mappings and selection.

    Provides a configuration-driven approach to map semantic model names
    to specific provider models with support for fallback chains.
    """

    def __init__(self, config: Optional[ModelRegistryConfig] = None):
        """Initialize the ModelRegistry with configuration."""
        self.config = config or ModelRegistryConfig()
        self._models: Dict[str, ModelInfo] = {}
        self._semantic_mappings: Dict[ModelType, List[str]] = {}
        self._provider_models: Dict[ProviderType, List[str]] = {}
        self._capability_index: Dict[str, Set[str]] = {}  # Change key type to str
        self.capability_database = CapabilityDatabase()  # Add this line
        self._last_loaded: Optional[float] = None

        if self.config.config_file:
            self.load_from_config(self.config.config_file)

    def load_from_config(self, config_path: Union[str, Path]) -> None:
        """Load model mappings from a configuration file."""
        config_path = Path(config_path)

        if not config_path.exists():
            logger.warning(f"Model registry config file not found: {config_path}")
            return

        try:
            with open(config_path, "r") as f:
                if config_path.suffix.lower() in [".yaml", ".yml"]:
                    data = yaml.safe_load(f)
                else:
                    import json

                    data = json.load(f)

            self._load_models_from_data(data)
            self._build_indexes()
            # Add all models to the capability database
            for model_info in self._models.values():
                self.capability_database.add_capabilities(
                    ModelCapabilities(
                        model_id=f"{model_info.provider}/{model_info.name}",
                        capabilities=model_info.capabilities,
                    )
                )
            self._last_loaded = self._get_current_time()

            logger.info(f"Loaded {len(self._models)} models from {config_path}")

        except Exception as e:
            logger.error(
                f"Failed to load model registry config from {config_path}: {e}"
            )
            raise

    def _load_models_from_data(self, data: Dict[str, Any]) -> None:
        """Load models from parsed configuration data."""
        models_data = data.get("models", {})

        for model_name, model_data in models_data.items():
            try:
                model_info = self._create_model_info(model_name, model_data)
                self._models[model_name] = model_info
            except Exception as e:
                logger.error(f"Failed to load model {model_name}: {e}")
                continue

    def _create_model_info(self, name: str, data: Dict[str, Any]) -> ModelInfo:
        """Create a ModelInfo object from configuration data."""
        # Parse capabilities
        capabilities = []  # Change set() to []
        for cap_data in data.get("capabilities", []):  # Change cap_str to cap_data
            try:
                # Assuming cap_data is a dictionary matching ModelCapability structure
                capabilities.append(
                    ModelCapability(**cap_data)
                )  # Create ModelCapability object
            except Exception as e:  # Catch general exception for parsing errors
                logger.warning(f"Failed to parse capability {cap_data}: {e}")

        # Parse semantic type
        semantic_type = ModelType(data.get("semantic_type", "smart"))

        # Parse provider
        provider = ProviderType(data.get("provider", "openai"))

        return ModelInfo(
            name=name,
            provider=provider,
            semantic_type=semantic_type,
            capabilities=capabilities,
            cost_per_1k_tokens=data.get("cost_per_1k_tokens", 0.0),
            max_tokens=data.get("max_tokens", 4096),
            context_window=data.get("context_window", 4096),
            performance_score=data.get("performance_score", 0.5),
            reliability_score=data.get("reliability_score", 0.5),
            fallback_models=data.get("fallback_models", []),
            provider_specific=data.get("provider_specific", {}),
        )

    def _build_indexes(self) -> None:
        """Build internal indexes for efficient querying."""
        self._semantic_mappings.clear()
        self._provider_models.clear()
        self._capability_index.clear()

        for model_name, model_info in self._models.items():
            # Build semantic type index
            if model_info.semantic_type not in self._semantic_mappings:
                self._semantic_mappings[model_info.semantic_type] = []
            self._semantic_mappings[model_info.semantic_type].append(model_name)

            # Build provider index
            if model_info.provider not in self._provider_models:
                self._provider_models[model_info.provider] = []
            self._provider_models[model_info.provider].append(model_name)

            # Build capability index
            for capability in model_info.capabilities:
                if capability.name not in self._capability_index:
                    self._capability_index[capability.name] = set()
                self._capability_index[capability.name].add(model_name)

    def register_model(self, model_info: ModelInfo) -> None:
        """Register a new model in the registry."""
        self._models[model_info.name] = model_info
        self._build_indexes()
        self.capability_database.add_capabilities(
            ModelCapabilities(
                model_id=f"{model_info.provider}/{model_info.name}",
                capabilities=model_info.capabilities,
            )
        )
        logger.info(f"Registered model: {model_info.name}")

    def unregister_model(self, model_name: str) -> bool:
        """Remove a model from the registry."""
        if model_name in self._models:
            del self._models[model_name]
            self._build_indexes()
            logger.info(f"Unregistered model: {model_name}")
            return True
        return False

    def get_model(self, model_name: str) -> Optional[ModelInfo]:
        """Get model information by name."""
        return self._models.get(model_name)

    def get_models_by_semantic_type(self, semantic_type: ModelType) -> List[ModelInfo]:
        """Get all models of a specific semantic type."""
        model_names = self._semantic_mappings.get(semantic_type, [])
        return [self._models[name] for name in model_names if name in self._models]

    def get_models_by_provider(self, provider: ProviderType) -> List[ModelInfo]:
        """Get all models from a specific provider."""
        model_names = self._provider_models.get(provider, [])
        return [self._models[name] for name in model_names if name in self._models]

    def get_models_by_capability(
        self, capability: str
    ) -> List[ModelInfo]:  # Change type hint to str
        """Get all models with a specific capability."""
        model_caps_list = self.capability_database.query_capabilities(
            capability_name=capability
        )  # Use capability_database
        model_ids = [mc.model_id for mc in model_caps_list]
        return [
            self._models[name.split("/")[-1]]
            for name in model_ids
            if name.split("/")[-1] in self._models
        ]  # Extract model name from model_id

    def get_fallback_chain(self, model_name: str) -> List[ModelInfo]:
        """Get the fallback chain for a model."""
        model_info = self.get_model(model_name)
        if not model_info:
            return []

        fallback_chain = [model_info]
        for fallback_name in model_info.fallback_models:
            fallback_model = self.get_model(fallback_name)
            if fallback_model:
                fallback_chain.append(fallback_model)

        return fallback_chain

    def query_models(
        self,
        semantic_type: Optional[ModelType] = None,
        provider: Optional[ProviderType] = None,
        capabilities: Optional[List[str]] = None,  # Change type hint to List[str]
        max_cost: Optional[float] = None,
        min_performance: Optional[float] = None,
        min_reliability: Optional[float] = None,
    ) -> List[ModelInfo]:
        """Query models with multiple filter criteria."""
        candidates = list(self._models.values())

        # Filter by semantic type
        if semantic_type:
            candidates = [m for m in candidates if m.semantic_type == semantic_type]

        # Filter by provider
        if provider:
            candidates = [m for m in candidates if m.provider == provider]

        # Filter by capabilities using CapabilityDatabase
        if capabilities:
            # Get models that have at least one of the required capabilities
            models_with_any_cap = set()
            for cap_name in capabilities:
                for model_caps in self.capability_database.query_capabilities(
                    capability_name=cap_name
                ):
                    models_with_any_cap.add(model_caps.model_id)

            # Filter candidates to only include those that have all required capabilities
            filtered_by_caps = []
            for model in candidates:
                model_id = f"{model.provider}/{model.name}"
                if model_id in models_with_any_cap:
                    # Verify all required capabilities are present for this model
                    model_caps = self.capability_database.get_capabilities(model_id)
                    if model_caps:
                        current_cap_names = {c.name for c in model_caps.capabilities}
                        if all(
                            req_cap in current_cap_names for req_cap in capabilities
                        ):
                            filtered_by_caps.append(model)
            candidates = filtered_by_caps

        # Filter by cost
        if max_cost is not None:
            candidates = [m for m in candidates if m.cost_per_1k_tokens <= max_cost]

        # Filter by performance
        if min_performance is not None:
            candidates = [
                m for m in candidates if m.performance_score >= min_performance
            ]

        # Filter by reliability
        if min_reliability is not None:
            candidates = [
                m for m in candidates if m.reliability_score >= min_reliability
            ]

        return candidates

    def get_all_models(self) -> List[ModelInfo]:
        """Get all registered models."""
        return list(self._models.values())

    def get_model_count(self) -> int:
        """Get the total number of registered models."""
        return len(self._models)

    def is_model_registered(self, model_name: str) -> bool:
        """Check if a model is registered."""
        return model_name in self._models

    def _get_current_time(self) -> float:
        """Get current timestamp for cache management."""
        import time

        return time.time()

    def should_reload(self) -> bool:
        """Check if the registry should reload from config file."""
        if not self.config.auto_reload or not self.config.config_file:
            return False

        if self._last_loaded is None:
            return True

        return (self._get_current_time() - self._last_loaded) > self.config.cache_ttl
