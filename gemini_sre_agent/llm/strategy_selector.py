"""
Strategy selector and manager for model selection strategies.

This module provides the StrategyManager class that implements the Factory pattern
for strategy selection and the Observer pattern for strategy performance monitoring.
It manages multiple strategy instances and provides a unified interface for
model selection.

Classes:
    StrategyManager: Manager for model selection strategies using the Strategy pattern

Author: Gemini SRE Agent
Created: 2024
"""

from typing import Dict, List, Optional, Any
import logging

from .strategy_base import (
    ModelSelectionStrategy, 
    StrategyContext, 
    StrategyResult,
    OptimizationGoal
)
from .strategy_implementations import (
    CostOptimizedStrategy,
    PerformanceOptimizedStrategy,
    QualityOptimizedStrategy,
    TimeBasedStrategy,
    HybridStrategy
)
from .model_registry import ModelInfo
from .model_scorer import ModelScorer

logger = logging.getLogger(__name__)


class StrategyManager:
    """Manager for model selection strategies using the Strategy pattern."""

    def __init__(self, model_scorer: Optional[ModelScorer] = None):
        """Initialize the strategy manager.
        
        Args:
            model_scorer: Optional model scorer instance
        """
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
        """Select model using specified strategy.
        
        Args:
            candidates: List of available models
            goal: Optimization goal to use
            context: Strategy execution context
            
        Returns:
            StrategyResult containing selected model and metadata
            
        Raises:
            ValueError: If unknown optimization goal
        """
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
        """Add or replace a strategy.
        
        Args:
            goal: Optimization goal for the strategy
            strategy: Strategy implementation
        """
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
        """Remove a strategy.
        
        Args:
            goal: Optimization goal to remove strategy for
        """
        if goal in self._strategies:
            del self._strategies[goal]
            logger.info(f"Removed strategy for goal {goal.value}")

    def get_available_strategies(self) -> List[OptimizationGoal]:
        """Get list of available strategies.
        
        Returns:
            List of available optimization goals
        """
        return list(self._strategies.keys())

    def get_strategy_performance(self, goal: OptimizationGoal) -> Dict[str, float]:
        """Get performance metrics for a specific strategy.
        
        Args:
            goal: Optimization goal to get metrics for
            
        Returns:
            Dictionary containing performance metrics
            
        Raises:
            ValueError: If unknown optimization goal
        """
        if goal not in self._strategies:
            raise ValueError(f"Unknown optimization goal: {goal}")

        strategy_metrics = self._strategy_performance[goal.value]
        strategy_performance = self._strategies[goal].get_performance_metrics()

        # Combine manager and strategy metrics
        combined_metrics = strategy_metrics.copy()
        combined_metrics.update(strategy_performance)

        return combined_metrics

    def get_all_performance_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get performance metrics for all strategies.
        
        Returns:
            Dictionary mapping strategy names to their performance metrics
        """
        all_metrics = {}
        for goal in self._strategies.keys():
            all_metrics[goal.value] = self.get_strategy_performance(goal)
        return all_metrics

    def get_usage_statistics(self) -> Dict[str, int]:
        """Get usage statistics for all strategies.
        
        Returns:
            Dictionary mapping strategy names to usage counts
        """
        return self._strategy_usage_stats.copy()

    def update_strategy_performance(
        self, goal: OptimizationGoal, success: bool, latency_ms: float
    ):
        """Update performance metrics for a strategy based on actual usage.
        
        Args:
            goal: Optimization goal to update
            success: Whether the selection was successful
            latency_ms: Execution latency in milliseconds
        """
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

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the strategy manager.
        
        Returns:
            Dictionary containing health status and metrics
        """
        available_strategies = len(self._strategies)
        total_usage = sum(self._strategy_usage_stats.values())
        
        # Calculate overall success rate
        total_successful = sum(
            metrics["successful_selections"] 
            for metrics in self._strategy_performance.values()
        )
        overall_success_rate = (
            total_successful / max(1, total_usage) if total_usage > 0 else 0.0
        )
        
        return {
            "status": "healthy",
            "available_strategies": available_strategies,
            "total_selections": total_usage,
            "overall_success_rate": overall_success_rate,
            "strategy_details": {
                goal.value: {
                    "available": goal in self._strategies,
                    "usage_count": self._strategy_usage_stats.get(goal.value, 0),
                    "performance": self._strategy_performance.get(goal.value, {}),
                }
                for goal in OptimizationGoal
            }
        }

    def get_strategy_recommendations(
        self, context: StrategyContext
    ) -> List[OptimizationGoal]:
        """Get recommended strategies based on context.
        
        Args:
            context: Strategy execution context
            
        Returns:
            List of recommended optimization goals in order of preference
        """
        recommendations = []
        
        # Business hours recommendation
        if context.business_hours_only:
            recommendations.extend([
                OptimizationGoal.QUALITY,
                OptimizationGoal.PERFORMANCE,
                OptimizationGoal.HYBRID
            ])
        else:
            # Cost-sensitive recommendation
            if context.max_cost and context.max_cost < 0.01:
                recommendations.extend([
                    OptimizationGoal.COST,
                    OptimizationGoal.TIME_BASED,
                    OptimizationGoal.HYBRID
                ])
            # Performance-critical recommendation
            elif context.min_performance and context.min_performance > 0.8:
                recommendations.extend([
                    OptimizationGoal.PERFORMANCE,
                    OptimizationGoal.QUALITY,
                    OptimizationGoal.HYBRID
                ])
            # Quality-focused recommendation
            elif context.min_quality and context.min_quality > 0.8:
                recommendations.extend([
                    OptimizationGoal.QUALITY,
                    OptimizationGoal.PERFORMANCE,
                    OptimizationGoal.HYBRID
                ])
            # Default balanced recommendation
            else:
                recommendations.extend([
                    OptimizationGoal.HYBRID,
                    OptimizationGoal.TIME_BASED,
                    OptimizationGoal.PERFORMANCE,
                    OptimizationGoal.COST,
                    OptimizationGoal.QUALITY
                ])
        
        # Filter to only available strategies
        available = self.get_available_strategies()
        return [goal for goal in recommendations if goal in available]
