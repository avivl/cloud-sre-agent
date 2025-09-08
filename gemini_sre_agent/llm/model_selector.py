# gemini_sre_agent/llm/model_selector.py

"""
Model Selector with Fallback Chains for intelligent model selection.

This module provides a sophisticated model selection system that chooses appropriate
models based on task requirements and constraints, with support for fallback chains
and Python 3.10+ pattern matching for elegant selection logic.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .capabilities.discovery import CapabilityDiscovery
from .capabilities.models import ModelCapability
from .common.enums import ModelType, ProviderType
from .model_registry import ModelInfo, ModelRegistry
from .model_scorer import ModelScore, ModelScorer, ScoringContext, ScoringWeights

logger = logging.getLogger(__name__)


class SelectionStrategy(str, Enum):
    """Model selection strategies."""

    BEST_SCORE = "best_score"  # Select highest scoring model
    FASTEST = "fastest"  # Select fastest available model
    CHEAPEST = "cheapest"  # Select cheapest available model
    MOST_RELIABLE = "most_reliable"  # Select most reliable model
    BALANCED = "balanced"  # Balanced selection across multiple factors
    CUSTOM = "custom"  # Custom selection logic


@dataclass
class SelectionCriteria:
    """Criteria for model selection."""

    semantic_type: Optional[ModelType] = None
    required_capabilities: List[ModelCapability] = field(default_factory=list)
    max_cost: Optional[float] = None
    min_performance: Optional[float] = None
    min_reliability: Optional[float] = None
    max_latency_ms: Optional[float] = None
    provider_preference: Optional[ProviderType] = None
    strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE
    custom_weights: Optional[ScoringWeights] = None
    max_models_to_consider: int = 10
    allow_fallback: bool = True


@dataclass
class SelectionResult:
    """Result of model selection."""

    selected_model: ModelInfo
    score: ModelScore
    fallback_chain: List[ModelInfo]
    selection_reason: str
    criteria: SelectionCriteria
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelSelector:
    """
    Intelligent model selector with fallback chain support.

    Provides sophisticated model selection based on task requirements,
    constraints, and fallback strategies using pattern matching.
    """

    def __init__(
        self,
        model_registry: ModelRegistry,
        capability_discovery: CapabilityDiscovery,
        model_scorer: Optional[ModelScorer] = None,
    ):
        """Initialize the ModelSelector with registry, capability discovery, and scorer."""
        self.model_registry = model_registry
        self.capability_discovery = capability_discovery  # Add this line
        self.model_scorer = model_scorer or ModelScorer()
        self._selection_cache: Dict[str, SelectionResult] = {}
        self._cache_ttl = 300  # 5 minutes
        self._selection_stats: Dict[str, int] = {}

        logger.info(
            "ModelSelector initialized with registry, capability discovery, and scorer"
        )

    def select_model(
        self, criteria: SelectionCriteria, use_cache: bool = True
    ) -> SelectionResult:
        """Select the best model based on criteria with fallback support."""
        # Check cache first
        cache_key = None
        if use_cache:
            cache_key = self._get_cache_key(criteria)
            cached_result = self._get_cached_selection(cache_key)
            if cached_result:
                return cached_result

        # Get candidate models
        candidates = self._get_candidate_models(criteria)
        if not candidates:
            raise ValueError(f"No models found matching criteria: {criteria}")

        # Select primary model
        primary_model, primary_score = self._select_primary_model(candidates, criteria)

        # Build fallback chain
        fallback_chain = self._build_fallback_chain(primary_model, criteria)

        # Create selection result
        result = SelectionResult(
            selected_model=primary_model,
            score=primary_score,
            fallback_chain=fallback_chain,
            selection_reason=self._generate_selection_reason(
                primary_model, primary_score, criteria
            ),
            criteria=criteria,
            metadata={
                "candidates_considered": len(candidates),
                "fallback_chain_length": len(fallback_chain),
                "selection_strategy": criteria.strategy.value,
            },
        )

        # Cache result
        if use_cache and cache_key is not None:
            self._cache_selection(cache_key, result)

        # Update statistics
        self._update_selection_stats(criteria.strategy)

        logger.info(
            f"Selected model: {primary_model.name} using strategy: {criteria.strategy}"
        )
        return result

    def select_model_with_fallback(
        self, criteria: SelectionCriteria, max_attempts: int = 3
    ) -> Tuple[ModelInfo, SelectionResult]:
        """Select model and return the first available one from fallback chain."""
        result = self.select_model(criteria)

        # Try primary model first
        if self._is_model_available(result.selected_model):
            return result.selected_model, result

        # Try fallback models
        for i, fallback_model in enumerate(result.fallback_chain[1:], 1):
            if i >= max_attempts:
                break

            if self._is_model_available(fallback_model):
                logger.info(
                    f"Using fallback model: {fallback_model.name} (attempt {i+1})"
                )
                return fallback_model, result

        # If no fallback available, return primary (will be handled by caller)
        logger.warning(
            f"No available models in fallback chain for criteria: {criteria}"
        )
        return result.selected_model, result

    def _get_candidate_models(self, criteria: SelectionCriteria) -> List[ModelInfo]:
        """Get candidate models based on criteria."""
        # Start with all models from the registry
        all_models = self.model_registry.get_all_models()
        candidates = []

        for model_info in all_models:
            # Filter by semantic type
            if (
                criteria.semantic_type
                and model_info.semantic_type != criteria.semantic_type
            ):
                continue

            # Filter by required capabilities using CapabilityDiscovery
            if criteria.required_capabilities:
                model_id = f"{model_info.provider}/{model_info.name}"
                model_caps = self.capability_discovery.get_model_capabilities(model_id)
                if not model_caps:
                    continue  # Model has no registered capabilities

                # Check if model has all required capabilities
                has_all_required = True
                for req_cap in criteria.required_capabilities:
                    if not any(
                        mc.name == req_cap.name for mc in model_caps.capabilities
                    ):
                        has_all_required = False
                        break
                if not has_all_required:
                    continue

            # Apply other filters (max_cost, min_performance, min_reliability)
            if (
                criteria.max_cost is not None
                and model_info.cost_per_1k_tokens > criteria.max_cost
            ):
                continue
            if (
                criteria.min_performance is not None
                and model_info.performance_score < criteria.min_performance
            ):
                continue
            if (
                criteria.min_reliability is not None
                and model_info.reliability_score < criteria.min_reliability
            ):
                continue

            candidates.append(model_info)

        # Apply additional filters (provider preference, latency)
        filtered_candidates = [
            model for model in candidates if self._meets_criteria(model, criteria)
        ]

        # Limit candidates if specified
        if (
            criteria.max_models_to_consider
            and len(filtered_candidates) > criteria.max_models_to_consider
        ):
            # Sort by a simple heuristic and take top N
            filtered_candidates.sort(
                key=lambda m: (m.performance_score + m.reliability_score) / 2,
                reverse=True,
            )
            filtered_candidates = filtered_candidates[: criteria.max_models_to_consider]

        return filtered_candidates

    def _meets_criteria(self, model: ModelInfo, criteria: SelectionCriteria) -> bool:
        """Check if model meets all criteria."""
        # Check provider preference
        if (
            criteria.provider_preference
            and model.provider != criteria.provider_preference
        ):
            return False

        # Check latency constraint (simplified heuristic)
        if criteria.max_latency_ms:
            # Use max_tokens as proxy for latency
            estimated_latency = model.max_tokens * 0.1  # Rough estimate
            if estimated_latency > criteria.max_latency_ms:
                return False

        return True

    def _select_primary_model(
        self, candidates: List[ModelInfo], criteria: SelectionCriteria
    ) -> Tuple[ModelInfo, ModelScore]:
        """Select primary model using specified strategy."""
        # Create scoring context
        context = ScoringContext(
            task_type=criteria.semantic_type,
            required_capabilities=criteria.required_capabilities,
            max_cost=criteria.max_cost,
            min_performance=criteria.min_performance,
            min_reliability=criteria.min_reliability,
            provider_preference=criteria.provider_preference,
        )

        # Use pattern matching for strategy selection
        match criteria.strategy:
            case SelectionStrategy.BEST_SCORE:
                return self._select_by_best_score(
                    candidates, context, criteria.custom_weights
                )
            case SelectionStrategy.FASTEST:
                return self._select_by_fastest(candidates, context)
            case SelectionStrategy.CHEAPEST:
                return self._select_by_cheapest(candidates, context)
            case SelectionStrategy.MOST_RELIABLE:
                return self._select_by_most_reliable(candidates, context)
            case SelectionStrategy.BALANCED:
                return self._select_by_balanced(candidates, context)
            case SelectionStrategy.CUSTOM:
                return self._select_by_custom(
                    candidates, context, criteria.custom_weights
                )
            case _:
                # Default to best score
                return self._select_by_best_score(
                    candidates, context, criteria.custom_weights
                )

    def _select_by_best_score(
        self,
        candidates: List[ModelInfo],
        context: ScoringContext,
        custom_weights: Optional[ScoringWeights] = None,
    ) -> Tuple[ModelInfo, ModelScore]:
        """Select model with best overall score."""
        ranked_models = self.model_scorer.rank_models(
            candidates, context, custom_weights, top_k=1
        )
        if not ranked_models:
            raise ValueError("No models could be scored")

        model, score = ranked_models[0]
        return model, score

    def _select_by_fastest(
        self, candidates: List[ModelInfo], context: ScoringContext
    ) -> Tuple[ModelInfo, ModelScore]:
        """Select fastest model based on max_tokens heuristic."""
        # Sort by max_tokens (lower = faster)
        fastest_model = min(candidates, key=lambda m: m.max_tokens)
        score = self.model_scorer.score_model(fastest_model, context)
        return fastest_model, score

    def _select_by_cheapest(
        self, candidates: List[ModelInfo], context: ScoringContext
    ) -> Tuple[ModelInfo, ModelScore]:
        """Select cheapest model."""
        cheapest_model = min(candidates, key=lambda m: m.cost_per_1k_tokens)
        score = self.model_scorer.score_model(cheapest_model, context)
        return cheapest_model, score

    def _select_by_most_reliable(
        self, candidates: List[ModelInfo], context: ScoringContext
    ) -> Tuple[ModelInfo, ModelScore]:
        """Select most reliable model."""
        most_reliable_model = max(candidates, key=lambda m: m.reliability_score)
        score = self.model_scorer.score_model(most_reliable_model, context)
        return most_reliable_model, score

    def _select_by_balanced(
        self, candidates: List[ModelInfo], context: ScoringContext
    ) -> Tuple[ModelInfo, ModelScore]:
        """Select model with balanced scoring."""
        balanced_weights = ScoringWeights(
            cost=0.25, performance=0.35, reliability=0.35, speed=0.05
        )
        return self._select_by_best_score(candidates, context, balanced_weights)

    def _select_by_custom(
        self,
        candidates: List[ModelInfo],
        context: ScoringContext,
        custom_weights: Optional[ScoringWeights] = None,
    ) -> Tuple[ModelInfo, ModelScore]:
        """Select model using custom weights."""
        if not custom_weights:
            raise ValueError("Custom weights required for custom selection strategy")

        return self._select_by_best_score(candidates, context, custom_weights)

    def _build_fallback_chain(
        self, primary_model: ModelInfo, criteria: SelectionCriteria
    ) -> List[ModelInfo]:
        """Build fallback chain for the primary model."""
        if not criteria.allow_fallback:
            return [primary_model]

        # Start with primary model
        fallback_chain = [primary_model]

        # Add model's configured fallbacks
        for fallback_name in primary_model.fallback_models:
            fallback_model = self.model_registry.get_model(fallback_name)
            if fallback_model and self._meets_criteria(fallback_model, criteria):
                fallback_chain.append(fallback_model)

        # Add additional fallbacks based on strategy
        additional_fallbacks = self._get_additional_fallbacks(primary_model, criteria)
        for fallback_model in additional_fallbacks:
            if fallback_model not in fallback_chain and self._meets_criteria(
                fallback_model, criteria
            ):
                fallback_chain.append(fallback_model)

        return fallback_chain

    def _get_additional_fallbacks(
        self, primary_model: ModelInfo, criteria: SelectionCriteria
    ) -> List[ModelInfo]:
        """Get additional fallback models based on strategy."""
        # Get other models of the same semantic type
        same_type_models = self.model_registry.get_models_by_semantic_type(
            primary_model.semantic_type
        )

        # Filter out primary model and sort by score
        other_models = [m for m in same_type_models if m.name != primary_model.name]

        if not other_models:
            return []

        # Score and rank other models
        context = ScoringContext(
            task_type=criteria.semantic_type,
            required_capabilities=criteria.required_capabilities,
            provider_preference=criteria.provider_preference,
        )

        ranked_models = self.model_scorer.rank_models(other_models, context, top_k=3)
        return [model for model, _ in ranked_models]

    def _is_model_available(self, model: ModelInfo) -> bool:
        """Check if a model is currently available."""
        # This is a simplified check - in a real implementation,
        # you might check provider health, quota limits, etc.
        return True

    def _generate_selection_reason(
        self, model: ModelInfo, score: ModelScore, criteria: SelectionCriteria
    ) -> str:
        """Generate human-readable selection reason."""
        reasons = [f"Selected {model.name} using {criteria.strategy.value} strategy"]

        if criteria.semantic_type:
            reasons.append(f"for {criteria.semantic_type.value} task type")

        if criteria.required_capabilities:
            cap_names = [cap.name for cap in criteria.required_capabilities]
            reasons.append(f"with capabilities: {', '.join(cap_names)}")

        if criteria.max_cost:
            reasons.append(f"within cost limit: ${criteria.max_cost:.4f}/1k tokens")

        reasons.append(f"with overall score: {score.overall_score:.3f}")

        return " ".join(reasons)

    # Cache management
    def _get_cache_key(self, criteria: SelectionCriteria) -> str:
        """Generate cache key for selection criteria."""
        key_parts = [
            str(criteria.semantic_type),
            str(sorted([cap.name for cap in criteria.required_capabilities])),
            str(criteria.max_cost),
            str(criteria.min_performance),
            str(criteria.min_reliability),
            str(criteria.provider_preference),
            criteria.strategy.value,
            str(criteria.max_models_to_consider),
        ]
        return "|".join(key_parts)

    def _get_cached_selection(self, cache_key: str) -> Optional[SelectionResult]:
        """Get cached selection if still valid."""
        if cache_key in self._selection_cache:
            cached_result = self._selection_cache[cache_key]
            if time.time() - cached_result.timestamp < self._cache_ttl:
                return cached_result
            else:
                del self._selection_cache[cache_key]
        return None

    def _cache_selection(self, cache_key: str, result: SelectionResult) -> None:
        """Cache a selection result."""
        self._selection_cache[cache_key] = result

        # Clean up old cache entries
        current_time = time.time()
        expired_keys = [
            key
            for key, cached_result in self._selection_cache.items()
            if current_time - cached_result.timestamp > self._cache_ttl
        ]
        for key in expired_keys:
            del self._selection_cache[key]

    def _update_selection_stats(self, strategy: SelectionStrategy) -> None:
        """Update selection statistics."""
        strategy_key = strategy.value
        self._selection_stats[strategy_key] = (
            self._selection_stats.get(strategy_key, 0) + 1
        )

    def clear_cache(self) -> None:
        """Clear the selection cache."""
        self._selection_cache.clear()
        logger.info("Model selection cache cleared")

    def get_selection_stats(self) -> Dict[str, Any]:
        """Get selection statistics."""
        current_time = time.time()
        valid_entries = sum(
            1
            for result in self._selection_cache.values()
            if current_time - result.timestamp < self._cache_ttl
        )

        return {
            "cache_entries": len(self._selection_cache),
            "valid_cache_entries": valid_entries,
            "selection_counts": self._selection_stats.copy(),
            "cache_ttl": self._cache_ttl,
        }
