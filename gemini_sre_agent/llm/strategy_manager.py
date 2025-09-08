"""
Strategy Manager for Model Selection with Strategy Pattern.

This module implements the Strategy pattern for model selection, providing
different optimization strategies for various goals like cost, performance,
quality, and time-based selection.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from datetime import time as dt_time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .base import ModelType
from .common.enums import ProviderType
from .model_registry import ModelInfo
from .model_scorer import ModelScore, ModelScorer, ScoringContext, ScoringWeights

logger = logging.getLogger(__name__)


class OptimizationGoal(str, Enum):
    """Optimization goals for model selection strategies."""

    COST = "cost"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    TIME_BASED = "time_based"
    HYBRID = "hybrid"


@dataclass
class StrategyContext:
    """Context for strategy execution."""

    task_type: Optional[ModelType] = None
    max_cost: Optional[float] = None
    min_performance: Optional[float] = None
    min_quality: Optional[float] = None
    max_latency: Optional[float] = None
    business_hours_only: bool = False
    provider_preference: Optional[List[ProviderType]] = None
    custom_weights: Optional[ScoringWeights] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyResult:
    """Result of strategy execution."""

    selected_model: ModelInfo
    score: ModelScore
    strategy_used: str
    execution_time_ms: float
    fallback_models: List[ModelInfo] = field(default_factory=list)
    reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelSelectionStrategy(ABC):
    """Abstract base class for model selection strategies."""

    def __init__(self, name: str, model_scorer: Optional[ModelScorer] = None):
        """Initialize the strategy."""
        self.name = name
        self.model_scorer = model_scorer or ModelScorer()
        self._selection_history: List[Tuple[Optional[ModelInfo], float, bool]] = (
            []
        )  # (model, score, success)
        self._performance_metrics: Dict[str, float] = {
            "total_selections": 0.0,
            "successful_selections": 0.0,
            "average_score": 0.0,
            "average_latency": 0.0,
        }

    @abstractmethod
    def select_model(
        self, candidates: List[ModelInfo], context: StrategyContext
    ) -> StrategyResult:
        """Select the best model based on strategy criteria."""
        pass

    def update_performance(
        self, model: Optional[ModelInfo], score: float, success: bool, latency_ms: float
    ):
        """Update performance metrics based on selection outcome."""
        self._selection_history.append((model, score, success))

        # Update metrics
        self._performance_metrics["total_selections"] += 1
        if success:
            self._performance_metrics["successful_selections"] += 1

        # Update average score (exponential moving average)
        alpha = 0.1
        current_avg = self._performance_metrics["average_score"]
        self._performance_metrics["average_score"] = (
            alpha * score + (1 - alpha) * current_avg
        )

        # Update average latency
        current_latency = self._performance_metrics["average_latency"]
        self._performance_metrics["average_latency"] = (
            alpha * latency_ms + (1 - alpha) * current_latency
        )

    def get_performance_metrics(self) -> Dict[str, float]:
        """Get current performance metrics."""
        metrics = self._performance_metrics.copy()
        if metrics["total_selections"] > 0:
            metrics["success_rate"] = (
                metrics["successful_selections"] / metrics["total_selections"]
            )
        else:
            metrics["success_rate"] = 0.0
        return metrics

    def _filter_candidates(
        self, candidates: List[ModelInfo], context: StrategyContext
    ) -> List[ModelInfo]:
        """Filter candidates based on context constraints."""
        filtered = candidates.copy()

        # Filter by task type
        if context.task_type:
            filtered = [m for m in filtered if context.task_type in m.capabilities]

        # Filter by provider preference
        if context.provider_preference:
            filtered = [
                m for m in filtered if m.provider in context.provider_preference
            ]

        # Filter by cost constraint
        if context.max_cost is not None:
            filtered = [m for m in filtered if m.cost_per_1k_tokens <= context.max_cost]

        # Filter by performance constraint
        if context.min_performance is not None:
            filtered = [
                m for m in filtered if m.performance_score >= context.min_performance
            ]

        # Filter by quality constraint (using performance_score as proxy for quality)
        if context.min_quality is not None:
            filtered = [
                m for m in filtered if m.performance_score >= context.min_quality
            ]

        return filtered


class CostOptimizedStrategy(ModelSelectionStrategy):
    """Strategy that selects the cheapest suitable model."""

    def __init__(self, model_scorer: Optional[ModelScorer] = None):
        super().__init__("cost_optimized", model_scorer)

    def select_model(
        self, candidates: List[ModelInfo], context: StrategyContext
    ) -> StrategyResult:
        """Select the cheapest model that meets all constraints."""
        start_time = time.time()

        # Filter candidates based on constraints
        filtered_candidates = self._filter_candidates(candidates, context)

        if not filtered_candidates:
            raise ValueError("No models meet the specified constraints")

        # Select cheapest model
        selected_model = min(filtered_candidates, key=lambda m: m.cost_per_1k_tokens)

        # Score the selected model
        scoring_context = ScoringContext(
            task_type=context.task_type,
            provider_preference=(
                context.provider_preference[0] if context.provider_preference else None
            ),
        )
        score = self.model_scorer.score_model(selected_model, scoring_context)

        execution_time = (time.time() - start_time) * 1000

        # Build fallback chain (next cheapest models)
        fallback_models = sorted(
            [m for m in filtered_candidates if m != selected_model],
            key=lambda m: m.cost_per_1k_tokens,
        )[
            :3
        ]  # Top 3 fallback options

        reasoning = f"Selected {selected_model.name} as the cheapest model (${selected_model.cost_per_1k_tokens}/1k tokens) that meets all constraints"

        return StrategyResult(
            selected_model=selected_model,
            score=score,
            strategy_used=self.name,
            execution_time_ms=execution_time,
            fallback_models=fallback_models,
            reasoning=reasoning,
            metadata={
                "cost_per_1k_tokens": selected_model.cost_per_1k_tokens,
                "total_candidates": len(candidates),
                "filtered_candidates": len(filtered_candidates),
            },
        )


class PerformanceOptimizedStrategy(ModelSelectionStrategy):
    """Strategy that selects the fastest model meeting quality requirements."""

    def __init__(self, model_scorer: Optional[ModelScorer] = None):
        super().__init__("performance_optimized", model_scorer)

    def select_model(
        self, candidates: List[ModelInfo], context: StrategyContext
    ) -> StrategyResult:
        """Select the fastest model that meets quality requirements."""
        start_time = time.time()

        # Filter candidates based on constraints
        filtered_candidates = self._filter_candidates(candidates, context)

        if not filtered_candidates:
            raise ValueError("No models meet the specified constraints")

        # Use performance-focused scoring weights
        weights = ScoringWeights(
            cost=0.1,
            performance=0.6,
            reliability=0.2,
            speed=0.1,
            quality=0.0,
            availability=0.0,
        )

        # Score all candidates with performance focus
        scoring_context = ScoringContext(
            task_type=context.task_type,
            provider_preference=(
                context.provider_preference[0] if context.provider_preference else None
            ),
        )

        scored_models = []
        for model in filtered_candidates:
            score = self.model_scorer.score_model(model, scoring_context, weights)
            scored_models.append((model, score))

        # Select model with highest performance score
        selected_model, score = max(scored_models, key=lambda x: x[1].performance_score)

        execution_time = (time.time() - start_time) * 1000

        # Build fallback chain (next best performing models)
        fallback_models = sorted(
            [(m, s) for m, s in scored_models if m != selected_model],
            key=lambda x: x[1].performance_score,
            reverse=True,
        )[:3]
        fallback_models = [m for m, s in fallback_models]

        reasoning = f"Selected {selected_model.name} as the highest performing model (score: {score.performance_score:.3f}) that meets quality requirements"

        return StrategyResult(
            selected_model=selected_model,
            score=score,
            strategy_used=self.name,
            execution_time_ms=execution_time,
            fallback_models=fallback_models,
            reasoning=reasoning,
            metadata={
                "performance_score": score.performance_score,
                "total_candidates": len(candidates),
                "filtered_candidates": len(filtered_candidates),
            },
        )


class QualityOptimizedStrategy(ModelSelectionStrategy):
    """Strategy that selects the highest quality model within budget."""

    def __init__(self, model_scorer: Optional[ModelScorer] = None):
        super().__init__("quality_optimized", model_scorer)

    def select_model(
        self, candidates: List[ModelInfo], context: StrategyContext
    ) -> StrategyResult:
        """Select the highest quality model within budget constraints."""
        start_time = time.time()

        # Filter candidates based on constraints
        filtered_candidates = self._filter_candidates(candidates, context)

        if not filtered_candidates:
            raise ValueError("No models meet the specified constraints")

        # Use quality-focused scoring weights
        weights = ScoringWeights(
            cost=0.2,
            performance=0.2,
            reliability=0.3,
            speed=0.0,
            quality=0.3,
            availability=0.0,
        )

        # Score all candidates with quality focus
        scoring_context = ScoringContext(
            task_type=context.task_type,
            provider_preference=(
                context.provider_preference[0] if context.provider_preference else None
            ),
        )

        scored_models = []
        for model in filtered_candidates:
            score = self.model_scorer.score_model(model, scoring_context, weights)
            scored_models.append((model, score))

        # Select model with highest quality score (using performance_score as proxy)
        selected_model, score = max(
            scored_models,
            key=lambda x: x[1].dimension_scores.get(
                "quality", x[1].dimension_scores.get("performance", 0)
            ),
        )

        execution_time = (time.time() - start_time) * 1000

        # Build fallback chain (next best quality models)
        fallback_models = sorted(
            [(m, s) for m, s in scored_models if m != selected_model],
            key=lambda x: x[1].dimension_scores.get(
                "quality", x[1].dimension_scores.get("performance", 0)
            ),
            reverse=True,
        )[:3]
        fallback_models = [m for m, s in fallback_models]

        quality_score = score.dimension_scores.get(
            "quality", score.dimension_scores.get("performance", 0)
        )
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

    def __init__(self, model_scorer: Optional[ModelScorer] = None):
        super().__init__("time_based", model_scorer)
        self.business_hours_start = dt_time(9, 0)  # 9 AM
        self.business_hours_end = dt_time(17, 0)  # 5 PM

    def _is_business_hours(self) -> bool:
        """Check if current time is within business hours."""
        now = datetime.now().time()
        return self.business_hours_start <= now <= self.business_hours_end

    def select_model(
        self, candidates: List[ModelInfo], context: StrategyContext
    ) -> StrategyResult:
        """Select model based on time of day and business requirements."""
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
            task_type=context.task_type,
            provider_preference=(
                context.provider_preference[0] if context.provider_preference else None
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

    def __init__(self, model_scorer: Optional[ModelScorer] = None):
        super().__init__("hybrid", model_scorer)
        self._learning_weights = (
            ScoringWeights()
        )  # Will be updated based on performance

    def _update_learning_weights(self, success: bool, latency_ms: float):
        """Update weights based on performance feedback."""
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
        """Select model using hybrid approach with learning."""
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
                constraint_details.append(f"provider_preference={context.provider_preference}")
            
            constraint_str = ", ".join(constraint_details) if constraint_details else "no specific constraints"
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
            task_type=context.task_type,
            provider_preference=(
                context.provider_preference[0] if context.provider_preference else None
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


class StrategyManager:
    """Manager for model selection strategies using the Strategy pattern."""

    def __init__(self, model_scorer: Optional[ModelScorer] = None):
        """Initialize the strategy manager."""
        self.model_scorer = model_scorer or ModelScorer()
        self._strategies: Dict[OptimizationGoal, ModelSelectionStrategy] = {}
        self._strategy_usage_stats: Dict[str, int] = {}
        self._strategy_performance: Dict[str, Dict[str, float]] = {}

        # Initialize default strategies
        self._initialize_default_strategies()

        logger.info("StrategyManager initialized with default strategies")

    def _initialize_default_strategies(self):
        """Initialize default strategies."""
        self._strategies = {
            OptimizationGoal.COST: CostOptimizedStrategy(self.model_scorer),
            OptimizationGoal.PERFORMANCE: PerformanceOptimizedStrategy(
                self.model_scorer
            ),
            OptimizationGoal.QUALITY: QualityOptimizedStrategy(self.model_scorer),
            OptimizationGoal.TIME_BASED: TimeBasedStrategy(self.model_scorer),
            OptimizationGoal.HYBRID: HybridStrategy(self.model_scorer),
        }

        # Initialize usage stats
        for goal in OptimizationGoal:
            self._strategy_usage_stats[goal.value] = 0
            self._strategy_performance[goal.value] = {
                "total_selections": 0.0,
                "successful_selections": 0.0,
                "average_score": 0.0,
                "average_latency": 0.0,
            }

    def select_model(
        self,
        candidates: List[ModelInfo],
        goal: OptimizationGoal,
        context: StrategyContext,
    ) -> StrategyResult:
        """Select model using specified strategy."""
        if goal not in self._strategies:
            raise ValueError(f"Unknown optimization goal: {goal}")

        strategy = self._strategies[goal]

        # Execute strategy
        result = strategy.select_model(candidates, context)

        # Update usage statistics
        self._strategy_usage_stats[goal.value] += 1

        # Update performance metrics
        strategy_metrics = self._strategy_performance[goal.value]
        strategy_metrics["total_selections"] += 1
        strategy_metrics["average_latency"] = (
            strategy_metrics["average_latency"]
            * (strategy_metrics["total_selections"] - 1)
            + result.execution_time_ms
        ) / strategy_metrics["total_selections"]

        logger.debug(
            f"Selected model {result.selected_model.name} using {goal.value} strategy in {result.execution_time_ms:.2f}ms"
        )

        return result

    def add_strategy(self, goal: OptimizationGoal, strategy: ModelSelectionStrategy):
        """Add or replace a strategy."""
        self._strategies[goal] = strategy
        if goal.value not in self._strategy_usage_stats:
            self._strategy_usage_stats[goal.value] = 0
            self._strategy_performance[goal.value] = {
                "total_selections": 0.0,
                "successful_selections": 0.0,
                "average_score": 0.0,
                "average_latency": 0.0,
            }

        logger.info(f"Added strategy {strategy.name} for goal {goal.value}")

    def remove_strategy(self, goal: OptimizationGoal):
        """Remove a strategy."""
        if goal in self._strategies:
            del self._strategies[goal]
            logger.info(f"Removed strategy for goal {goal.value}")

    def get_available_strategies(self) -> List[OptimizationGoal]:
        """Get list of available strategies."""
        return list(self._strategies.keys())

    def get_strategy_performance(self, goal: OptimizationGoal) -> Dict[str, float]:
        """Get performance metrics for a specific strategy."""
        if goal not in self._strategies:
            raise ValueError(f"Unknown optimization goal: {goal}")

        strategy_metrics = self._strategy_performance[goal.value]
        strategy_performance = self._strategies[goal].get_performance_metrics()

        # Combine manager and strategy metrics
        combined_metrics = strategy_metrics.copy()
        combined_metrics.update(strategy_performance)

        return combined_metrics

    def get_all_performance_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get performance metrics for all strategies."""
        all_metrics = {}
        for goal in self._strategies.keys():
            all_metrics[goal.value] = self.get_strategy_performance(goal)
        return all_metrics

    def get_usage_statistics(self) -> Dict[str, int]:
        """Get usage statistics for all strategies."""
        return self._strategy_usage_stats.copy()

    def update_strategy_performance(
        self, goal: OptimizationGoal, success: bool, latency_ms: float
    ):
        """Update performance metrics for a strategy based on actual usage."""
        if goal not in self._strategies:
            return

        strategy = self._strategies[goal]
        strategy_metrics = self._strategy_performance[goal.value]

        # Update strategy's internal metrics
        # Note: We can't access the selected model from the strategy, so we pass None
        strategy.update_performance(None, 0.0, success, latency_ms)

        # Update manager metrics
        if success:
            strategy_metrics["successful_selections"] += 1

        logger.debug(
            f"Updated performance for {goal.value} strategy: success={success}, latency={latency_ms}ms"
        )

    def reset_statistics(self):
        """Reset all statistics."""
        for goal in OptimizationGoal:
            self._strategy_usage_stats[goal.value] = 0
            self._strategy_performance[goal.value] = {
                "total_selections": 0.0,
                "successful_selections": 0.0,
                "average_score": 0.0,
                "average_latency": 0.0,
            }

        # Reset individual strategy statistics
        for strategy in self._strategies.values():
            strategy._selection_history.clear()
            strategy._performance_metrics = {
                "total_selections": 0.0,
                "successful_selections": 0.0,
                "average_score": 0.0,
                "average_latency": 0.0,
            }

        logger.info("Reset all strategy statistics")
