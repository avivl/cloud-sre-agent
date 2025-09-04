# gemini_sre_agent/llm/enhanced_service.py

"""
Enhanced LLM Service with Intelligent Model Selection.

This module provides an enhanced LLM service that integrates the semantic model
selection system with the existing provider interfaces, enabling intelligent
model selection based on task requirements, performance metrics, and fallback chains.
"""

import logging
import time
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

try:
    from mirascope import Prompt
except ImportError as e:
    raise ImportError(
        "Required dependency 'mirascope' not installed. Please install: pip install mirascope"
    ) from e

from pydantic import BaseModel

from .base import ModelType, ProviderType
from .config import LLMConfig
from .factory import get_provider_factory
from .model_registry import ModelInfo, ModelRegistry
from .model_scorer import ModelScorer, ScoringContext, ScoringWeights
from .model_selector import (
    ModelSelector,
    SelectionCriteria,
    SelectionResult,
    SelectionStrategy,
)
from .performance_cache import MetricType, PerformanceMonitor
from .prompt_manager import PromptManager

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class EnhancedLLMService(Generic[T]):
    """
    Enhanced LLM service with intelligent model selection.

    Integrates the semantic model selection system with provider interfaces,
    enabling intelligent model selection based on task requirements, performance
    metrics, and fallback chains.
    """

    def __init__(
        self,
        config: LLMConfig,
        model_registry: Optional[ModelRegistry] = None,
        performance_monitor: Optional[PerformanceMonitor] = None,
    ):
        """Initialize the enhanced LLM service."""
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize provider factory and create providers
        self.provider_factory = get_provider_factory()
        self.providers = self.provider_factory.create_providers_from_config(config)

        # Initialize prompt manager
        self.prompt_manager = PromptManager()

        # Initialize model selection components
        self.model_registry = model_registry or ModelRegistry()
        self.model_scorer = ModelScorer()
        self.model_selector = ModelSelector(self.model_registry, self.model_scorer)
        self.performance_monitor = performance_monitor or PerformanceMonitor()

        # Track selection statistics
        self._selection_stats: Dict[str, int] = {}
        self._last_selection_time: Dict[str, float] = {}

        self.logger.info(
            "EnhancedLLMService initialized with intelligent model selection"
        )

    async def generate_structured(
        self,
        prompt: Union[str, Prompt],
        response_model: Type[T],
        model: Optional[str] = None,
        model_type: Optional[ModelType] = None,
        provider: Optional[str] = None,
        selection_strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE,
        custom_weights: Optional[ScoringWeights] = None,
        max_cost: Optional[float] = None,
        min_performance: Optional[float] = None,
        min_reliability: Optional[float] = None,
        **kwargs: Any,
    ) -> T:
        """Generate a structured response with intelligent model selection."""
        start_time = time.time()

        try:
            # Select the best model based on criteria
            selected_model, selection_result = await self._select_model_for_task(
                model=model,
                model_type=model_type,
                provider=provider,
                selection_strategy=selection_strategy,
                custom_weights=custom_weights,
                max_cost=max_cost,
                min_performance=min_performance,
                min_reliability=min_reliability,
                required_capabilities=[],  # Could be enhanced to detect from response_model
            )

            # Get the provider for the selected model
            provider_name = selected_model.provider.value
            if provider_name not in self.providers:
                raise ValueError(
                    f"Provider '{provider_name}' not available for model '{selected_model.name}'"
                )

            provider_instance = self.providers[provider_name]

            self.logger.info(
                f"Generating structured response using model: {selected_model.name} via provider: {provider_name}"
            )

            # Generate the response
            result = await provider_instance.generate_structured(
                prompt=prompt,
                response_model=response_model,
                model=selected_model.name,
                **kwargs,
            )

            # Record performance metrics
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            self.performance_monitor.record_latency(
                model_name=selected_model.name,
                latency_ms=latency_ms,
                provider=selected_model.provider,
                context={
                    "task_type": "structured_generation",
                    "model_type": model_type.value if model_type else "unknown",
                    "selection_strategy": selection_strategy.value,
                    "response_model": response_model.__name__,
                },
            )

            self.performance_monitor.record_success(
                model_name=selected_model.name,
                success=True,
                provider=selected_model.provider,
                context={"task_type": "structured_generation"},
            )

            # Update selection statistics
            self._update_selection_stats(selected_model.name, selection_strategy)

            return result

        except Exception as e:
            # Record failure metrics if we have a selected model
            try:
                if "selected_model" in locals() and "selected_model" in locals():
                    selected_model = locals().get("selected_model")
                    if selected_model:
                        self.performance_monitor.record_success(
                            model_name=selected_model.name,
                            success=False,
                            provider=selected_model.provider,
                            context={
                                "task_type": "structured_generation",
                                "error": str(e),
                            },
                        )
            except Exception:
                pass  # Don't let metrics recording errors mask the original error

            self.logger.error(f"Error generating structured response: {str(e)}")
            raise

    async def generate_text(
        self,
        prompt: Union[str, Prompt],
        model: Optional[str] = None,
        model_type: Optional[ModelType] = None,
        provider: Optional[str] = None,
        selection_strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE,
        custom_weights: Optional[ScoringWeights] = None,
        max_cost: Optional[float] = None,
        min_performance: Optional[float] = None,
        min_reliability: Optional[float] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a plain text response with intelligent model selection."""
        start_time = time.time()

        try:
            # Select the best model based on criteria
            selected_model, selection_result = await self._select_model_for_task(
                model=model,
                model_type=model_type,
                provider=provider,
                selection_strategy=selection_strategy,
                custom_weights=custom_weights,
                max_cost=max_cost,
                min_performance=min_performance,
                min_reliability=min_reliability,
                required_capabilities=[],
            )

            # Get the provider for the selected model
            provider_name = selected_model.provider.value
            if provider_name not in self.providers:
                raise ValueError(
                    f"Provider '{provider_name}' not available for model '{selected_model.name}'"
                )

            provider_instance = self.providers[provider_name]

            self.logger.info(
                f"Generating text response using model: {selected_model.name} via provider: {provider_name}"
            )

            # Generate the response
            result = await provider_instance.generate_text(
                prompt=prompt, model=selected_model.name, **kwargs
            )

            # Record performance metrics
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            self.performance_monitor.record_latency(
                model_name=selected_model.name,
                latency_ms=latency_ms,
                provider=selected_model.provider,
                context={
                    "task_type": "text_generation",
                    "model_type": model_type.value if model_type else "unknown",
                    "selection_strategy": selection_strategy.value,
                },
            )

            self.performance_monitor.record_success(
                model_name=selected_model.name,
                success=True,
                provider=selected_model.provider,
                context={"task_type": "text_generation"},
            )

            # Update selection statistics
            self._update_selection_stats(selected_model.name, selection_strategy)

            return result

        except Exception as e:
            # Record failure metrics if we have a selected model
            try:
                if "selected_model" in locals():
                    selected_model = locals().get("selected_model")
                    if selected_model:
                        self.performance_monitor.record_success(
                            model_name=selected_model.name,
                            success=False,
                            provider=selected_model.provider,
                            context={"task_type": "text_generation", "error": str(e)},
                        )
            except Exception:
                pass  # Don't let metrics recording errors mask the original error

            self.logger.error(f"Error generating text response: {str(e)}")
            raise

    async def generate_with_fallback(
        self,
        prompt: Union[str, Prompt],
        response_model: Optional[Type[T]] = None,
        model_type: Optional[ModelType] = None,
        selection_strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE,
        max_attempts: int = 3,
        **kwargs: Any,
    ) -> Union[str, T]:
        """Generate response with automatic fallback chain execution."""
        last_error = None

        # Create selection criteria
        criteria = SelectionCriteria(
            semantic_type=model_type,
            strategy=selection_strategy,
            allow_fallback=True,
            max_models_to_consider=10,
        )

        # Get selection result with fallback chain
        selection_result = self.model_selector.select_model(criteria)

        # Try each model in the fallback chain
        for i, model_info in enumerate(selection_result.fallback_chain):
            if i >= max_attempts:
                break

            try:
                self.logger.info(
                    f"Attempting model: {model_info.name} (attempt {i+1}/{max_attempts})"
                )

                # Get the provider for this model
                provider_name = model_info.provider.value
                if provider_name not in self.providers:
                    self.logger.warning(
                        f"Provider '{provider_name}' not available for model '{model_info.name}'"
                    )
                    continue

                provider_instance = self.providers[provider_name]

                # Generate response based on type
                if response_model:
                    result = await provider_instance.generate_structured(
                        prompt=prompt,
                        response_model=response_model,
                        model=model_info.name,
                        **kwargs,
                    )
                else:
                    result = await provider_instance.generate_text(
                        prompt=prompt, model=model_info.name, **kwargs
                    )

                # Record success
                self.performance_monitor.record_success(
                    model_name=model_info.name,
                    success=True,
                    provider=model_info.provider,
                    context={"task_type": "fallback_generation", "attempt": i + 1},
                )

                self.logger.info(
                    f"Successfully generated response using model: {model_info.name}"
                )
                return result

            except Exception as e:
                last_error = e
                self.logger.warning(f"Model {model_info.name} failed: {str(e)}")

                # Record failure
                self.performance_monitor.record_success(
                    model_name=model_info.name,
                    success=False,
                    provider=model_info.provider,
                    context={
                        "task_type": "fallback_generation",
                        "attempt": i + 1,
                        "error": str(e),
                    },
                )

                continue

        # All models failed
        self.logger.error(
            f"All {max_attempts} models in fallback chain failed. Last error: {str(last_error)}"
        )
        raise last_error or Exception("All models in fallback chain failed")

    async def _select_model_for_task(
        self,
        model: Optional[str] = None,
        model_type: Optional[ModelType] = None,
        provider: Optional[str] = None,
        selection_strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE,
        custom_weights: Optional[ScoringWeights] = None,
        max_cost: Optional[float] = None,
        min_performance: Optional[float] = None,
        min_reliability: Optional[float] = None,
        required_capabilities: Optional[List] = None,
    ) -> tuple[ModelInfo, SelectionResult]:
        """Select the best model for a task based on criteria."""

        # If specific model is requested, try to find it in registry
        if model:
            model_info = self.model_registry.get_model(model)
            if model_info:
                # Create a simple selection result
                context = ScoringContext(
                    task_type=model_type,
                    required_capabilities=required_capabilities or [],
                    max_cost=max_cost,
                    min_performance=min_performance,
                    min_reliability=min_reliability,
                )
                score = self.model_scorer.score_model(model_info, context)

                selection_result = SelectionResult(
                    selected_model=model_info,
                    score=score,
                    fallback_chain=[model_info],
                    selection_reason=f"Explicitly requested model: {model}",
                    criteria=SelectionCriteria(
                        semantic_type=model_type,
                        strategy=selection_strategy,
                        custom_weights=custom_weights,
                        max_cost=max_cost,
                        min_performance=min_performance,
                        min_reliability=min_reliability,
                    ),
                )
                return model_info, selection_result

        # Create selection criteria
        criteria = SelectionCriteria(
            semantic_type=model_type,
            required_capabilities=required_capabilities or [],
            max_cost=max_cost,
            min_performance=min_performance,
            min_reliability=min_reliability,
            provider_preference=ProviderType(provider) if provider else None,
            strategy=selection_strategy,
            custom_weights=custom_weights,
            allow_fallback=True,
        )

        # Select model with fallback support
        selected_model, selection_result = (
            self.model_selector.select_model_with_fallback(criteria)
        )

        return selected_model, selection_result

    def _update_selection_stats(
        self, model_name: str, strategy: SelectionStrategy
    ) -> None:
        """Update selection statistics."""
        key = f"{model_name}:{strategy.value}"
        self._selection_stats[key] = self._selection_stats.get(key, 0) + 1
        self._last_selection_time[model_name] = time.time()

    async def health_check(self, provider: Optional[str] = None) -> bool:
        """Check if the specified provider is healthy and accessible."""
        try:
            if provider:
                if provider in self.providers:
                    return await self.providers[provider].health_check()
                return False

            # Check all providers
            health_status = {}
            for provider_name, provider_instance in self.providers.items():
                health_status[provider_name] = await provider_instance.health_check()

            return all(health_status.values())

        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False

    def get_available_models(
        self, provider: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """Get available models for the specified provider or all providers."""
        if provider:
            if provider in self.providers:
                return {provider: self.providers[provider].get_available_models()}
            return {}

        return {
            provider_name: provider_instance.get_available_models()
            for provider_name, provider_instance in self.providers.items()
        }

    def get_model_performance(self, model_name: str) -> Dict[str, Any]:
        """Get performance metrics for a specific model."""
        return self.performance_monitor.get_model_performance(model_name)

    def get_best_models(
        self, metric_type: MetricType, limit: int = 5
    ) -> List[tuple[str, float]]:
        """Get best performing models for a specific metric."""
        return self.performance_monitor.get_best_models(metric_type, limit)

    def get_selection_stats(self) -> Dict[str, Any]:
        """Get model selection statistics."""
        return {
            "selection_counts": self._selection_stats.copy(),
            "last_selection_times": self._last_selection_time.copy(),
            "performance_cache_stats": self.performance_monitor.get_cache_stats(),
        }

    def get_model_rankings(
        self,
        metric_types: List[MetricType],
        weights: Optional[Dict[MetricType, float]] = None,
    ) -> List[tuple[str, float]]:
        """Get model rankings based on multiple performance metrics."""
        return self.performance_monitor.get_model_rankings(metric_types, weights)


def create_enhanced_llm_service(
    config: LLMConfig,
    model_registry: Optional[ModelRegistry] = None,
    performance_monitor: Optional[PerformanceMonitor] = None,
) -> EnhancedLLMService:
    """Factory function to create and configure an EnhancedLLMService instance."""
    return EnhancedLLMService(config, model_registry, performance_monitor)
