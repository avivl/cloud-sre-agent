import logging
import time
from typing import Any, Dict, List, Optional, Set
from functools import lru_cache

from gemini_sre_agent.llm.capabilities.models import ModelCapabilities, ModelCapability
from gemini_sre_agent.llm.capabilities.config import get_capability_config
from gemini_sre_agent.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class CapabilityDiscovery:
    """
    Discovers and catalogs capabilities of LLM models across various providers.
    """

    def __init__(self, providers: Dict[str, LLMProvider], cache_ttl: int = 3600):
        """
        Initialize the CapabilityDiscovery.

        Args:
            providers: A dictionary of initialized LLMProvider instances.
            cache_ttl: Cache time-to-live in seconds (default: 1 hour).
        """
        self.providers = providers
        self.model_capabilities: Dict[str, ModelCapabilities] = {}
        self.cache_ttl = cache_ttl
        self._cache_timestamps: Dict[str, float] = {}
        self._discovery_lock: Set[str] = set()  # Prevent concurrent discovery of same model
        
        # Load capability configuration
        self.capability_config = get_capability_config()
        
        # Metrics tracking
        self._metrics = {
            "discovery_attempts": 0,
            "discovery_successes": 0,
            "discovery_failures": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "last_discovery_time": None,
            "average_discovery_time": 0.0
        }

    def _is_cache_valid(self, model_id: str) -> bool:
        """Check if cached capabilities for a model are still valid."""
        if model_id not in self._cache_timestamps:
            return False
        return time.time() - self._cache_timestamps[model_id] < self.cache_ttl

    def _update_cache_timestamp(self, model_id: str) -> None:
        """Update the cache timestamp for a model."""
        self._cache_timestamps[model_id] = time.time()

    def clear_cache(self) -> None:
        """Clear all cached capabilities and timestamps."""
        self.model_capabilities.clear()
        self._cache_timestamps.clear()
        logger.info("Capability discovery cache cleared")

    async def discover_capabilities(self, force_refresh: bool = False) -> Dict[str, ModelCapabilities]:
        """
        Discover capabilities for all configured models across all providers.

        Args:
            force_refresh: If True, bypass cache and force fresh discovery.

        Returns:
            A dictionary mapping model IDs to their discovered capabilities.
        """
        start_time = time.time()
        self._metrics["discovery_attempts"] += 1
        
        try:
            for provider_name, provider_instance in self.providers.items():
                logger.info(f"Discovering capabilities for provider: {provider_name}")

                # Get models available for this provider
                available_models = provider_instance.get_available_models()

                # Handle both dict and list return types
                model_items: List[tuple] = []
                if isinstance(available_models, dict):
                    model_items = list(available_models.items())
                elif isinstance(available_models, list):
                    # If it's a list, create tuples with model names
                    model_items = [("default", model_name) for model_name in available_models]  # type: ignore

                for model_type, model_name in model_items:
                    model_id = f"{provider_name}/{model_name}"

                    # Check cache first (unless force refresh)
                    if not force_refresh and self._is_cache_valid(model_id):
                        logger.debug(f"Using cached capabilities for {model_id}")
                        self._metrics["cache_hits"] += 1
                        continue
                    
                    self._metrics["cache_misses"] += 1

                    # Prevent concurrent discovery of the same model
                    if model_id in self._discovery_lock:
                        logger.debug(f"Discovery already in progress for {model_id}, skipping")
                        continue

                    self._discovery_lock.add(model_id)
                    try:
                        capabilities = []
                        
                        # Safely check provider capabilities
                        try:
                            # Check if the provider has these methods using getattr
                            supports_streaming_method = getattr(provider_instance, 'supports_streaming', None)
                            if supports_streaming_method:
                                supports_streaming = await self._safe_check_capability(supports_streaming_method)
                            else:
                                supports_streaming = False
                                
                            supports_tools_method = getattr(provider_instance, 'supports_tools', None)
                            if supports_tools_method:
                                supports_tools = await self._safe_check_capability(supports_tools_method)
                            else:
                                supports_tools = False
                        except Exception as e:
                            logger.warning(
                                f"Failed to check capabilities for {provider_name}: {e}"
                            )
                            supports_streaming = False
                            supports_tools = False

                        # Get model configuration safely
                        try:
                            model_config = provider_instance.config.models.get(model_name)
                            if not model_config:
                                logger.warning(
                                    f"No configuration found for model {model_name} in provider {provider_name}"
                                )
                                continue
                        except AttributeError:
                            logger.warning(
                                f"Provider {provider_name} does not have models configuration"
                            )
                            continue

                        # Get provider-specific capabilities from configuration
                        provider_name_lower = provider_name.lower()
                        provider_capabilities = self.capability_config.get_provider_capabilities(
                            provider_name_lower, model_name
                        )
                        
                        # Add configured capabilities
                        for cap_name in provider_capabilities:
                            cap_def = self.capability_config.get_capability(cap_name)
                            if cap_def:
                                # Create a copy with model-specific performance scores
                                capability = ModelCapability(
                                    name=cap_def.name,
                                    description=cap_def.description,
                                    parameters=cap_def.parameters,
                                    performance_score=getattr(model_config, "performance_score", cap_def.performance_score),
                                    cost_efficiency=getattr(model_config, "cost_per_1k_tokens", cap_def.cost_efficiency),
                                )
                                capabilities.append(capability)
                        
                        # Add dynamic capabilities based on provider features
                        if supports_streaming:
                            streaming_cap = self.capability_config.get_capability("streaming")
                            if streaming_cap:
                                capabilities.append(streaming_cap)
                        
                        if supports_tools:
                            tool_cap = self.capability_config.get_capability("tool_calling")
                            if tool_cap:
                                capabilities.append(tool_cap)

                        self.model_capabilities[model_id] = ModelCapabilities(
                            model_id=model_id, capabilities=capabilities
                        )
                        self._update_cache_timestamp(model_id)
                        logger.debug(f"Discovered and cached capabilities for {model_id}")
                    finally:
                        self._discovery_lock.discard(model_id)

            # Update metrics
            end_time = time.time()
            discovery_time = end_time - start_time
            self._metrics["last_discovery_time"] = end_time
            self._metrics["discovery_successes"] += 1
            
            # Update average discovery time
            if self._metrics["discovery_attempts"] == 1:
                self._metrics["average_discovery_time"] = discovery_time
            else:
                # Running average
                self._metrics["average_discovery_time"] = (
                    (self._metrics["average_discovery_time"] * (self._metrics["discovery_attempts"] - 1) + discovery_time)
                    / self._metrics["discovery_attempts"]
                )
            
            logger.info(
                f"Discovered capabilities for {len(self.model_capabilities)} models in {discovery_time:.2f}s."
            )
            return self.model_capabilities
            
        except Exception as e:
            self._metrics["discovery_failures"] += 1
            logger.error(f"Capability discovery failed: {e}")
            raise

    async def _safe_check_capability(self, capability_method) -> bool:
        """
        Safely check a provider capability method, handling both sync and async cases.

        Args:
            capability_method: The capability method to check

        Returns:
            Boolean indicating if the capability is supported
        """
        try:
            # Try calling as async first
            if hasattr(capability_method, '__call__'):
                result = capability_method()
                # If it returns a coroutine, await it
                if hasattr(result, '__await__'):
                    return await result
                # Otherwise it's synchronous
                return bool(result)
            return False
        except Exception as e:
            logger.debug(f"Capability check failed: {e}")
            return False

    def get_model_capabilities(self, model_id: str, auto_refresh: bool = True) -> Optional[ModelCapabilities]:
        """
        Retrieve capabilities for a specific model.

        Args:
            model_id: The unique identifier for the model (e.g., "gemini/gemini-pro").
            auto_refresh: If True, automatically refresh expired cache entries.

        Returns:
            ModelCapabilities object if found, None otherwise.
        """
        if auto_refresh and not self._is_cache_valid(model_id):
            logger.debug(f"Cache expired for {model_id}, triggering refresh")
            # Note: In a real implementation, you might want to trigger async refresh here
            # For now, we'll just return None to indicate cache miss
            return None
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

    def find_models_by_capabilities(self, capability_names: List[str], require_all: bool = False) -> List[str]:
        """
        Find models that support multiple capabilities.

        Args:
            capability_names: List of capability names to search for.
            require_all: If True, model must support all capabilities. If False, any capability.

        Returns:
            A list of model IDs that support the specified capabilities.
        """
        matching_models = []
        for model_id, model_caps in self.model_capabilities.items():
            model_capability_names = {cap.name for cap in model_caps.capabilities}
            
            if require_all:
                if all(cap_name in model_capability_names for cap_name in capability_names):
                    matching_models.append(model_id)
            else:
                if any(cap_name in model_capability_names for cap_name in capability_names):
                    matching_models.append(model_id)
        
        return matching_models

    def get_capability_summary(self) -> Dict[str, int]:
        """
        Get a summary of how many models support each capability.

        Returns:
            Dictionary mapping capability names to count of supporting models.
        """
        capability_counts = {}
        for model_caps in self.model_capabilities.values():
            for cap in model_caps.capabilities:
                capability_counts[cap.name] = capability_counts.get(cap.name, 0) + 1
        return capability_counts

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics for the capability discovery system.

        Returns:
            Dictionary containing various metrics about discovery performance.
        """
        return self._metrics.copy()

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the capability discovery system.

        Returns:
            Dictionary containing health information.
        """
        total_attempts = self._metrics["discovery_attempts"]
        success_rate = (
            self._metrics["discovery_successes"] / total_attempts 
            if total_attempts > 0 else 0.0
        )
        
        cache_hit_rate = (
            self._metrics["cache_hits"] / (self._metrics["cache_hits"] + self._metrics["cache_misses"])
            if (self._metrics["cache_hits"] + self._metrics["cache_misses"]) > 0 else 0.0
        )
        
        return {
            "status": "healthy" if success_rate > 0.8 else "degraded" if success_rate > 0.5 else "unhealthy",
            "success_rate": success_rate,
            "cache_hit_rate": cache_hit_rate,
            "total_models": len(self.model_capabilities),
            "last_discovery": self._metrics["last_discovery_time"],
            "average_discovery_time": self._metrics["average_discovery_time"]
        }

    def reset_metrics(self) -> None:
        """Reset all metrics to initial state."""
        self._metrics = {
            "discovery_attempts": 0,
            "discovery_successes": 0,
            "discovery_failures": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "last_discovery_time": None,
            "average_discovery_time": 0.0
        }
        logger.info("Capability discovery metrics reset")

    def validate_task_requirements(self, task_type: str, model_id: str) -> Dict[str, Any]:
        """
        Validate if a model meets the requirements for a specific task type.
        
        Args:
            task_type: Type of task to validate for.
            model_id: ID of the model to validate.
            
        Returns:
            Dictionary with validation results.
        """
        model_caps = self.get_model_capabilities(model_id)
        if not model_caps:
            return {
                "meets_requirements": False,
                "error": f"Model {model_id} not found in capabilities database"
            }
        
        available_capabilities = [cap.name for cap in model_caps.capabilities]
        return self.capability_config.validate_capability_requirements(task_type, available_capabilities)

    def find_models_for_task(self, task_type: str, min_coverage: float = 0.8) -> List[Dict[str, Any]]:
        """
        Find models that meet the requirements for a specific task type.
        
        Args:
            task_type: Type of task to find models for.
            min_coverage: Minimum coverage score required (0.0 to 1.0).
            
        Returns:
            List of dictionaries with model information and validation results.
        """
        suitable_models = []
        
        for model_id, model_caps in self.model_capabilities.items():
            validation_result = self.validate_task_requirements(task_type, model_id)
            
            if validation_result.get("meets_requirements", False):
                coverage_score = validation_result.get("coverage_score", 0.0)
                if coverage_score >= min_coverage:
                    suitable_models.append({
                        "model_id": model_id,
                        "capabilities": [cap.name for cap in model_caps.capabilities],
                        "validation_result": validation_result,
                        "coverage_score": coverage_score
                    })
        
        # Sort by coverage score (descending)
        suitable_models.sort(key=lambda x: x["coverage_score"], reverse=True)
        return suitable_models
