# gemini_sre_agent/llm/strategy_implementations.py

"""
Concrete strategy implementations for model selection.

This module contains the concrete implementations of the Strategy pattern
for model selection. Each strategy implements a different optimization
approach (cost, performance, quality, time-based, hybrid).

Classes:
    CostOptimizedStrategy: Strategy that prioritizes cost efficiency
    PerformanceOptimizedStrategy: Strategy that prioritizes performance
    QualityOptimizedStrategy: Strategy that prioritizes quality
    TimeBasedStrategy: Strategy that adapts based on time of day
    HybridStrategy: Strategy that balances multiple factors with learning

Author: Gemini SRE Agent
Created: 2024
"""

import time
from datetime import datetime
from datetime import time as dt_time
from typing import List, Optional

from .base import ModelType
from .common.enums import ProviderType
from .model_registry import ModelInfo
from .model_scorer import (
    ModelScore,
    ModelScorer,
    ScoringContext,
    ScoringDimension,
    ScoringWeights,
)
from .strategy_base import (
    ModelSelectionStrategy,
    StrategyContext,
    StrategyResult,
)


class CostOptimizedStrategy(ModelSelectionStrategy):
    """Strategy that prioritizes cost efficiency over other factors."""

    def __init__(self, model_scorer: Optional[ModelScorer] = None) -> None:
        """Initialize the cost-optimized strategy.

        Args:
            model_scorer: Optional model scorer instance
        """
        super().__init__("cost_optimized", model_scorer)

    def select_model(
        self, candidates: List[ModelInfo], context: StrategyContext
    ) -> StrategyResult:
        """Select the most cost-effective model from candidates.

        Args:
            candidates: List of available models
            context: Strategy execution context

        Returns:
            StrategyResult containing selected model and metadata

        Raises:
            ValueError: If no models meet the constraints
        """
        start_time = time.time()

        # Filter candidates based on constraints
        filtered_candidates = self._filter_candidates(candidates, context)

        if not filtered_candidates:
            raise ValueError("No models meet the specified constraints")

        # Sort by cost (ascending) and select the cheapest
        sorted_candidates = sorted(
            filtered_candidates, key=lambda x: x.cost_per_1k_tokens
        )
        selected_model = sorted_candidates[0]

        execution_time = (time.time() - start_time) * 1000

        # Build fallback chain (next cheapest models)
        fallback_models = sorted_candidates[1:4]

        # Calculate cost savings
        most_expensive = max(filtered_candidates, key=lambda x: x.cost_per_1k_tokens)
        cost_savings = (
            most_expensive.cost_per_1k_tokens - selected_model.cost_per_1k_tokens
        )

        reasoning = f"Selected {selected_model.name} as the most cost-effective option (${selected_model.cost_per_1k_tokens:.4f}/1k tokens)"

        return StrategyResult(
            selected_model=selected_model,
            score=self._create_cost_score(selected_model),
            strategy_used=self.name,
            execution_time_ms=execution_time,
            fallback_models=fallback_models,
            reasoning=reasoning,
            metadata={
                "cost_per_1k_tokens": selected_model.cost_per_1k_tokens,
                "cost_savings": cost_savings,
                "total_candidates": len(candidates),
                "filtered_candidates": len(filtered_candidates),
            },
        )

    def _create_cost_score(self, model: ModelInfo) -> "ModelScore":
        """Create a score focused on cost efficiency.

        Args:
            model: Model to score

        Returns:
            ModelScore with cost-focused scoring
        """
        # Invert cost to make lower costs score higher
        max_cost = 0.1  # Assume max cost for normalization
        cost_score = max(0, 1 - (model.cost_per_1k_tokens / max_cost))

        return ModelScore(
            model_name=model.name,
            overall_score=cost_score,
            dimension_scores={
                ScoringDimension.COST: cost_score,
                ScoringDimension.PERFORMANCE: model.performance_score
                * 0.1,  # Low weight
                ScoringDimension.RELIABILITY: model.reliability_score
                * 0.1,  # Low weight
                ScoringDimension.SPEED: 0.5,  # Default speed score
                ScoringDimension.QUALITY: 0.5,  # Default quality score
                ScoringDimension.AVAILABILITY: 0.5,  # Default availability score
            },
            weights=ScoringWeights(
                cost=1.0,
                performance=0.1,
                reliability=0.1,
                speed=0.1,
                quality=0.1,
                availability=0.1,
            ),
            context=ScoringContext(task_type=ModelType.FAST),
        )


class PerformanceOptimizedStrategy(ModelSelectionStrategy):
    """Strategy that prioritizes performance over other factors."""

    def __init__(self, model_scorer: Optional[ModelScorer] = None) -> None:
        """Initialize the performance-optimized strategy.

        Args:
            model_scorer: Optional model scorer instance
        """
        super().__init__("performance_optimized", model_scorer)

    def select_model(
        self, candidates: List[ModelInfo], context: StrategyContext
    ) -> StrategyResult:
        """Select the highest performing model from candidates.

        Args:
            candidates: List of available models
            context: Strategy execution context

        Returns:
            StrategyResult containing selected model and metadata

        Raises:
            ValueError: If no models meet the constraints
        """
        start_time = time.time()

        # Filter candidates based on constraints
        filtered_candidates = self._filter_candidates(candidates, context)

        if not filtered_candidates:
            raise ValueError("No models meet the specified constraints")

        # Sort by performance score (descending) and select the best
        sorted_candidates = sorted(
            filtered_candidates, key=lambda x: x.performance_score, reverse=True
        )
        selected_model = sorted_candidates[0]

        execution_time = (time.time() - start_time) * 1000

        # Build fallback chain (next best performing models)
        fallback_models = sorted_candidates[1:4]

        reasoning = f"Selected {selected_model.name} as the highest performing model (score: {selected_model.performance_score:.3f})"

        return StrategyResult(
            selected_model=selected_model,
            score=self._create_performance_score(selected_model),
            strategy_used=self.name,
            execution_time_ms=execution_time,
            fallback_models=fallback_models,
            reasoning=reasoning,
            metadata={
                "performance_score": selected_model.performance_score,
                "total_candidates": len(candidates),
                "filtered_candidates": len(filtered_candidates),
            },
        )

    def _create_performance_score(self, model: ModelInfo) -> "ModelScore":
        """Create a score focused on performance.

        Args:
            model: Model to score

        Returns:
            ModelScore with performance-focused scoring
        """
        return ModelScore(
            model_name=model.name,
            overall_score=model.performance_score,
            dimension_scores={
                ScoringDimension.COST: model.cost_per_1k_tokens * 0.1,  # Low weight
                ScoringDimension.PERFORMANCE: model.performance_score,
                ScoringDimension.RELIABILITY: model.reliability_score
                * 0.2,  # Some weight
                ScoringDimension.SPEED: 0.5,  # Default speed score
                ScoringDimension.QUALITY: 0.5,  # Default quality score
                ScoringDimension.AVAILABILITY: 0.5,  # Default availability score
            },
            weights=ScoringWeights(
                cost=0.1,
                performance=1.0,
                reliability=0.2,
                speed=0.2,
                quality=0.1,
                availability=0.1,
            ),
            context=ScoringContext(task_type=ModelType.SMART),
        )


class QualityOptimizedStrategy(ModelSelectionStrategy):
    """Strategy that prioritizes quality over other factors."""

    def __init__(self, model_scorer: Optional[ModelScorer] = None) -> None:
        """Initialize the quality-optimized strategy.

        Args:
            model_scorer: Optional model scorer instance
        """
        super().__init__("quality_optimized", model_scorer)

    def select_model(
        self, candidates: List[ModelInfo], context: StrategyContext
    ) -> StrategyResult:
        """Select the highest quality model from candidates.

        Args:
            candidates: List of available models
            context: Strategy execution context

        Returns:
            StrategyResult containing selected model and metadata

        Raises:
            ValueError: If no models meet the constraints
        """
        start_time = time.time()

        # Filter candidates based on constraints
        filtered_candidates = self._filter_candidates(candidates, context)

        if not filtered_candidates:
            raise ValueError("No models meet the specified constraints")

        # Use custom weights if provided, otherwise use quality-focused weights
        if context.custom_weights:
            weights = context.custom_weights
        else:
            weights = ScoringWeights(
                cost=0.1,
                performance=0.2,
                reliability=0.3,
                speed=0.1,
                quality=0.3,
                availability=0.0,
            )

        # Score all candidates
        scoring_context = ScoringContext(
            task_type=ModelType.SMART,  # Use default model type
            provider_preference=(
                ProviderType(context.provider_preference[0])
                if context.provider_preference
                else None
            ),
        )

        scored_models = []
        for model in filtered_candidates:
            score = self.model_scorer.score_model(model, scoring_context, weights)
            scored_models.append((model, score))

        # Select best model based on quality-focused scoring
        selected_model, score = max(scored_models, key=lambda x: x[1].overall_score)

        execution_time = (time.time() - start_time) * 1000

        # Build fallback chain
        fallback_models = sorted(
            [(m, s) for m, s in scored_models if m != selected_model],
            key=lambda x: x[1].overall_score,
            reverse=True,
        )[:3]
        fallback_models = [m for m, s in fallback_models]

        quality_score = score.quality_score if hasattr(score, "quality_score") else 0.0
        reasoning = f"Selected {selected_model.name} as the highest quality model (score: {quality_score:.3f}) within budget constraints"

        return StrategyResult(
            selected_model=selected_model,
            score=score,
            strategy_used=self.name,
            execution_time_ms=execution_time,
            fallback_models=fallback_models,
            reasoning=reasoning,
            metadata={
                "quality_score": quality_score,
                "cost_per_1k_tokens": selected_model.cost_per_1k_tokens,
                "total_candidates": len(candidates),
                "filtered_candidates": len(filtered_candidates),
            },
        )


class TimeBasedStrategy(ModelSelectionStrategy):
    """Strategy that selects different models based on time of day."""

    def __init__(self, model_scorer: Optional[ModelScorer] = None) -> None:
        """Initialize the time-based strategy.

        Args:
            model_scorer: Optional model scorer instance
        """
        super().__init__("time_based", model_scorer)
        self.business_hours_start = dt_time(9, 0)  # 9 AM
        self.business_hours_end = dt_time(17, 0)  # 5 PM

    def _is_business_hours(self) -> bool:
        """Check if current time is within business hours.

        Returns:
            True if within business hours, False otherwise
        """
        now = datetime.now().time()
        return self.business_hours_start <= now <= self.business_hours_end

    def select_model(
        self, candidates: List[ModelInfo], context: StrategyContext
    ) -> StrategyResult:
        """Select model based on time of day and business requirements.

        Args:
            candidates: List of available models
            context: Strategy execution context

        Returns:
            StrategyResult containing selected model and metadata

        Raises:
            ValueError: If no models meet the constraints
        """
        start_time = time.time()

        # Filter candidates based on constraints
        filtered_candidates = self._filter_candidates(candidates, context)

        if not filtered_candidates:
            raise ValueError("No models meet the specified constraints")

        is_business_hours = self._is_business_hours()

        # Choose strategy based on time and context
        if is_business_hours or context.business_hours_only:
            # Business hours: prioritize quality and reliability
            weights = ScoringWeights(
                cost=0.2,
                performance=0.3,
                reliability=0.3,
                speed=0.1,
                quality=0.1,
                availability=0.0,
            )
            time_context = "business hours"
        else:
            # Off hours: prioritize cost and speed
            weights = ScoringWeights(
                cost=0.4,
                performance=0.2,
                reliability=0.2,
                speed=0.2,
                quality=0.0,
                availability=0.0,
            )
            time_context = "off hours"

        # Score all candidates
        scoring_context = ScoringContext(
            task_type=ModelType.SMART,  # Use default model type
            provider_preference=(
                ProviderType(context.provider_preference[0])
                if context.provider_preference
                else None
            ),
        )

        scored_models = []
        for model in filtered_candidates:
            score = self.model_scorer.score_model(model, scoring_context, weights)
            scored_models.append((model, score))

        # Select best model based on time-based scoring
        selected_model, score = max(scored_models, key=lambda x: x[1].overall_score)

        execution_time = (time.time() - start_time) * 1000

        # Build fallback chain
        fallback_models = sorted(
            [(m, s) for m, s in scored_models if m != selected_model],
            key=lambda x: x[1].overall_score,
            reverse=True,
        )[:3]
        fallback_models = [m for m, s in fallback_models]

        reasoning = f"Selected {selected_model.name} based on {time_context} strategy (overall score: {score.overall_score:.3f})"

        return StrategyResult(
            selected_model=selected_model,
            score=score,
            strategy_used=self.name,
            execution_time_ms=execution_time,
            fallback_models=fallback_models,
            reasoning=reasoning,
            metadata={
                "time_context": time_context,
                "is_business_hours": is_business_hours,
                "overall_score": score.overall_score,
                "total_candidates": len(candidates),
                "filtered_candidates": len(filtered_candidates),
            },
        )


class HybridStrategy(ModelSelectionStrategy):
    """Strategy that balances multiple factors using machine learning insights."""

    def __init__(self, model_scorer: Optional[ModelScorer] = None) -> None:
        """Initialize the hybrid strategy.

        Args:
            model_scorer: Optional model scorer instance
        """
        super().__init__("hybrid", model_scorer)
        self._learning_weights = (
            ScoringWeights()
        )  # Will be updated based on performance

    def _update_learning_weights(self, success: bool, latency_ms: float):
        """Update weights based on performance feedback.

        Args:
            success: Whether the selection was successful
            latency_ms: Execution latency in milliseconds
        """
        # Simple learning algorithm - adjust weights based on success and latency
        if success and latency_ms < 1000:  # Fast and successful
            # Increase performance and speed weights
            self._learning_weights.performance = min(
                0.5, self._learning_weights.performance + 0.05
            )
            self._learning_weights.speed = min(0.3, self._learning_weights.speed + 0.02)
        elif not success:
            # Increase reliability weight
            self._learning_weights.reliability = min(
                0.5, self._learning_weights.reliability + 0.05
            )

        # Normalize weights
        self._learning_weights = self._learning_weights.normalize()

    def select_model(
        self, candidates: List[ModelInfo], context: StrategyContext
    ) -> StrategyResult:
        """Select model using hybrid approach with learning.

        Args:
            candidates: List of available models
            context: Strategy execution context

        Returns:
            StrategyResult containing selected model and metadata

        Raises:
            ValueError: If no models meet the constraints
        """
        start_time = time.time()

        # Filter candidates based on constraints
        filtered_candidates = self._filter_candidates(candidates, context)

        if not filtered_candidates:
            constraint_details = []
            if context.max_cost:
                constraint_details.append(f"max_cost={context.max_cost}")
            if context.min_performance:
                constraint_details.append(f"min_performance={context.min_performance}")
            if context.min_quality:
                constraint_details.append(f"min_quality={context.min_quality}")
            if context.provider_preference:
                constraint_details.append(
                    f"provider_preference={context.provider_preference}"
                )

            constraint_str = (
                ", ".join(constraint_details)
                if constraint_details
                else "no specific constraints"
            )
            raise ValueError(
                f"No models meet the specified constraints ({constraint_str}). "
                f"Available candidates: {[c.name for c in candidates]}. "
                f"Consider relaxing constraints or adding more model providers."
            )

        # Use learned weights or default balanced weights
        if context.custom_weights:
            weights = context.custom_weights
        else:
            weights = (
                self._learning_weights
                if self._performance_metrics["total_selections"] > 10
                else ScoringWeights(
                    cost=0.25,
                    performance=0.3,
                    reliability=0.25,
                    speed=0.1,
                    quality=0.1,
                    availability=0.0,
                )
            )

        # Score all candidates
        scoring_context = ScoringContext(
            task_type=ModelType.SMART,  # Use default model type
            provider_preference=(
                ProviderType(context.provider_preference[0])
                if context.provider_preference
                else None
            ),
        )

        scored_models = []
        for model in filtered_candidates:
            score = self.model_scorer.score_model(model, scoring_context, weights)
            scored_models.append((model, score))

        # Select best model based on hybrid scoring
        selected_model, score = max(scored_models, key=lambda x: x[1].overall_score)

        execution_time = (time.time() - start_time) * 1000

        # Build fallback chain
        fallback_models = sorted(
            [(m, s) for m, s in scored_models if m != selected_model],
            key=lambda x: x[1].overall_score,
            reverse=True,
        )[:3]
        fallback_models = [m for m, s in fallback_models]

        reasoning = f"Selected {selected_model.name} using hybrid strategy with learned weights (overall score: {score.overall_score:.3f})"

        return StrategyResult(
            selected_model=selected_model,
            score=score,
            strategy_used=self.name,
            execution_time_ms=execution_time,
            fallback_models=fallback_models,
            reasoning=reasoning,
            metadata={
                "weights_used": {
                    "cost": weights.cost,
                    "performance": weights.performance,
                    "reliability": weights.reliability,
                    "speed": weights.speed,
                    "quality": weights.quality,
                },
                "learning_enabled": self._performance_metrics["total_selections"] > 10,
                "overall_score": score.overall_score,
                "total_candidates": len(candidates),
                "filtered_candidates": len(filtered_candidates),
            },
        )
