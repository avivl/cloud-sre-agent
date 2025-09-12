"""
Strategy performance metrics and monitoring utilities.

This module provides comprehensive metrics collection and analysis for
strategy performance monitoring. It implements the Observer pattern for
tracking strategy usage and performance over time.

Classes:
    StrategyMetricsCollector: Collects and analyzes strategy performance metrics
    StrategyPerformanceAnalyzer: Analyzes strategy performance patterns
    StrategyRecommendationEngine: Provides strategy recommendations based on metrics

Author: Gemini SRE Agent
Created: 2024
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import statistics
import logging

from .strategy_base import OptimizationGoal, StrategyResult
from .model_registry import ModelInfo

logger = logging.getLogger(__name__)


@dataclass
class StrategyMetrics:
    """Comprehensive metrics for a strategy."""
    
    strategy_name: str
    total_selections: int = 0
    successful_selections: int = 0
    failed_selections: int = 0
    average_score: float = 0.0
    average_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    success_rate: float = 0.0
    cost_efficiency: float = 0.0
    performance_trend: str = "stable"  # "improving", "declining", "stable"
    last_used: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceSnapshot:
    """Snapshot of performance at a specific time."""
    
    timestamp: datetime
    strategy_name: str
    success_rate: float
    average_latency_ms: float
    total_selections: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class StrategyMetricsCollector:
    """Collects and analyzes strategy performance metrics."""

    def __init__(self):
        """Initialize the metrics collector."""
        self._metrics: Dict[str, StrategyMetrics] = {}
        self._performance_history: List[PerformanceSnapshot] = []
        self._selection_history: List[Dict[str, Any]] = []
        self._max_history_size = 1000

    def record_selection(
        self,
        strategy_name: str,
        result: StrategyResult,
        success: bool,
        execution_time_ms: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a strategy selection and its outcome.
        
        Args:
            strategy_name: Name of the strategy used
            result: Strategy result
            success: Whether the selection was successful
            execution_time_ms: Execution time in milliseconds
            metadata: Optional additional metadata
        """
        # Initialize metrics if not exists
        if strategy_name not in self._metrics:
            self._metrics[strategy_name] = StrategyMetrics(strategy_name=strategy_name)

        metrics = self._metrics[strategy_name]
        
        # Update basic metrics
        metrics.total_selections += 1
        if success:
            metrics.successful_selections += 1
        else:
            metrics.failed_selections += 1

        # Update latency metrics
        metrics.average_latency_ms = (
            (metrics.average_latency_ms * (metrics.total_selections - 1) + execution_time_ms)
            / metrics.total_selections
        )
        metrics.min_latency_ms = min(metrics.min_latency_ms, execution_time_ms)
        metrics.max_latency_ms = max(metrics.max_latency_ms, execution_time_ms)

        # Update score metrics
        if hasattr(result, 'score') and hasattr(result.score, 'overall_score'):
            metrics.average_score = (
                (metrics.average_score * (metrics.total_selections - 1) + result.score.overall_score)
                / metrics.total_selections
            )

        # Update success rate
        metrics.success_rate = metrics.successful_selections / metrics.total_selections

        # Update last used timestamp
        metrics.last_used = datetime.now()

        # Record in history
        self._record_in_history(strategy_name, result, success, execution_time_ms, metadata)

        # Create performance snapshot
        self._create_performance_snapshot(strategy_name)

        logger.debug(f"Recorded selection for {strategy_name}: success={success}, latency={execution_time_ms}ms")

    def _record_in_history(
        self,
        strategy_name: str,
        result: StrategyResult,
        success: bool,
        execution_time_ms: float,
        metadata: Optional[Dict[str, Any]]
    ):
        """Record selection in history."""
        history_entry = {
            "timestamp": datetime.now(),
            "strategy_name": strategy_name,
            "model_name": result.selected_model.name,
            "success": success,
            "execution_time_ms": execution_time_ms,
            "score": getattr(result.score, 'overall_score', 0.0),
            "metadata": metadata or {},
        }
        
        self._selection_history.append(history_entry)
        
        # Trim history if too large
        if len(self._selection_history) > self._max_history_size:
            self._selection_history = self._selection_history[-self._max_history_size:]

    def _create_performance_snapshot(self, strategy_name: str):
        """Create a performance snapshot for trend analysis."""
        if strategy_name not in self._metrics:
            return

        metrics = self._metrics[strategy_name]
        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(),
            strategy_name=strategy_name,
            success_rate=metrics.success_rate,
            average_latency_ms=metrics.average_latency_ms,
            total_selections=metrics.total_selections,
            metadata={
                "average_score": metrics.average_score,
                "min_latency_ms": metrics.min_latency_ms,
                "max_latency_ms": metrics.max_latency_ms,
            }
        )
        
        self._performance_history.append(snapshot)

    def get_strategy_metrics(self, strategy_name: str) -> Optional[StrategyMetrics]:
        """Get metrics for a specific strategy.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            StrategyMetrics if found, None otherwise
        """
        return self._metrics.get(strategy_name)

    def get_all_metrics(self) -> Dict[str, StrategyMetrics]:
        """Get metrics for all strategies.
        
        Returns:
            Dictionary mapping strategy names to their metrics
        """
        return self._metrics.copy()

    def get_performance_trend(
        self, 
        strategy_name: str, 
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get performance trend for a strategy over time.
        
        Args:
            strategy_name: Name of the strategy
            hours: Number of hours to look back
            
        Returns:
            Dictionary containing trend analysis
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_snapshots = [
            s for s in self._performance_history
            if s.strategy_name == strategy_name and s.timestamp >= cutoff_time
        ]

        if len(recent_snapshots) < 2:
            return {"trend": "insufficient_data", "details": {}}

        # Calculate trend for success rate
        success_rates = [s.success_rate for s in recent_snapshots]
        success_trend = self._calculate_trend(success_rates)

        # Calculate trend for latency
        latencies = [s.average_latency_ms for s in recent_snapshots]
        latency_trend = self._calculate_trend(latencies)

        return {
            "trend": "improving" if success_trend > 0 and latency_trend < 0 else "declining",
            "success_rate_trend": success_trend,
            "latency_trend": latency_trend,
            "data_points": len(recent_snapshots),
            "time_range_hours": hours,
        }

    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend slope for a series of values.
        
        Args:
            values: List of numeric values
            
        Returns:
            Trend slope (positive = increasing, negative = decreasing)
        """
        if len(values) < 2:
            return 0.0

        # Simple linear regression slope
        n = len(values)
        x_values = list(range(n))
        
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(values)
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        return numerator / denominator if denominator != 0 else 0.0

    def get_top_performing_strategies(
        self, 
        metric: str = "success_rate", 
        limit: int = 5
    ) -> List[Tuple[str, float]]:
        """Get top performing strategies by metric.
        
        Args:
            metric: Metric to rank by ("success_rate", "average_score", "cost_efficiency")
            limit: Maximum number of strategies to return
            
        Returns:
            List of (strategy_name, metric_value) tuples sorted by performance
        """
        if not self._metrics:
            return []

        strategy_scores = []
        for name, metrics in self._metrics.items():
            if metric == "success_rate":
                score = metrics.success_rate
            elif metric == "average_score":
                score = metrics.average_score
            elif metric == "cost_efficiency":
                score = self._calculate_cost_efficiency(metrics)
            else:
                continue

            strategy_scores.append((name, score))

        # Sort by score (descending) and return top N
        strategy_scores.sort(key=lambda x: x[1], reverse=True)
        return strategy_scores[:limit]

    def _calculate_cost_efficiency(self, metrics: StrategyMetrics) -> float:
        """Calculate cost efficiency score for a strategy.
        
        Args:
            metrics: Strategy metrics
            
        Returns:
            Cost efficiency score (higher is better)
        """
        # Simple cost efficiency: success rate / average latency
        if metrics.average_latency_ms == 0:
            return 0.0
        
        return metrics.success_rate / (metrics.average_latency_ms / 1000)  # Convert to seconds

    def get_usage_statistics(self) -> Dict[str, Any]:
        """Get overall usage statistics.
        
        Returns:
            Dictionary containing usage statistics
        """
        total_selections = sum(m.total_selections for m in self._metrics.values())
        total_successful = sum(m.successful_selections for m in self._metrics.values())
        
        return {
            "total_selections": total_selections,
            "total_successful": total_successful,
            "overall_success_rate": total_successful / max(1, total_selections),
            "active_strategies": len(self._metrics),
            "most_used_strategy": max(
                self._metrics.items(), 
                key=lambda x: x[1].total_selections
            )[0] if self._metrics else None,
        }

    def reset_metrics(self, strategy_name: Optional[str] = None):
        """Reset metrics for a strategy or all strategies.
        
        Args:
            strategy_name: Specific strategy to reset, or None for all
        """
        if strategy_name:
            if strategy_name in self._metrics:
                del self._metrics[strategy_name]
            # Remove from history
            self._selection_history = [
                h for h in self._selection_history 
                if h["strategy_name"] != strategy_name
            ]
            self._performance_history = [
                s for s in self._performance_history 
                if s.strategy_name != strategy_name
            ]
        else:
            self._metrics.clear()
            self._selection_history.clear()
            self._performance_history.clear()

        logger.info(f"Reset metrics for {strategy_name or 'all strategies'}")

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the metrics collector.
        
        Returns:
            Dictionary containing health status and metrics
        """
        total_selections = sum(m.total_selections for m in self._metrics.values())
        recent_selections = len([
            h for h in self._selection_history
            if h["timestamp"] >= datetime.now() - timedelta(hours=1)
        ])

        return {
            "status": "healthy",
            "total_strategies": len(self._metrics),
            "total_selections": total_selections,
            "recent_selections_1h": recent_selections,
            "history_size": len(self._selection_history),
            "performance_snapshots": len(self._performance_history),
        }


class StrategyPerformanceAnalyzer:
    """Analyzes strategy performance patterns and provides insights."""

    def __init__(self, metrics_collector: StrategyMetricsCollector):
        """Initialize the performance analyzer.
        
        Args:
            metrics_collector: Metrics collector instance
        """
        self.metrics_collector = metrics_collector

    def analyze_performance_patterns(self) -> Dict[str, Any]:
        """Analyze performance patterns across all strategies.
        
        Returns:
            Dictionary containing analysis results
        """
        all_metrics = self.metrics_collector.get_all_metrics()
        
        if not all_metrics:
            return {"status": "no_data", "analysis": {}}

        # Find best and worst performing strategies
        best_strategy = max(all_metrics.items(), key=lambda x: x[1].success_rate)
        worst_strategy = min(all_metrics.items(), key=lambda x: x[1].success_rate)

        # Calculate performance variance
        success_rates = [m.success_rate for m in all_metrics.values()]
        latency_means = [m.average_latency_ms for m in all_metrics.values()]

        return {
            "status": "analyzed",
            "total_strategies": len(all_metrics),
            "best_strategy": {
                "name": best_strategy[0],
                "success_rate": best_strategy[1].success_rate,
                "average_latency_ms": best_strategy[1].average_latency_ms,
            },
            "worst_strategy": {
                "name": worst_strategy[0],
                "success_rate": worst_strategy[1].success_rate,
                "average_latency_ms": worst_strategy[1].average_latency_ms,
            },
            "performance_variance": {
                "success_rate_std": statistics.stdev(success_rates) if len(success_rates) > 1 else 0.0,
                "latency_std": statistics.stdev(latency_means) if len(latency_means) > 1 else 0.0,
            },
            "recommendations": self._generate_recommendations(all_metrics),
        }

    def _generate_recommendations(self, metrics: Dict[str, StrategyMetrics]) -> List[str]:
        """Generate performance recommendations.
        
        Args:
            metrics: Strategy metrics dictionary
            
        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Check for underperforming strategies
        for name, metric in metrics.items():
            if metric.success_rate < 0.7 and metric.total_selections > 10:
                recommendations.append(f"Consider investigating {name} strategy - low success rate ({metric.success_rate:.2%})")

            if metric.average_latency_ms > 5000 and metric.total_selections > 10:
                recommendations.append(f"Consider optimizing {name} strategy - high latency ({metric.average_latency_ms:.0f}ms)")

        # Check for unused strategies
        unused_strategies = [name for name, metric in metrics.items() if metric.total_selections == 0]
        if unused_strategies:
            recommendations.append(f"Consider removing unused strategies: {', '.join(unused_strategies)}")

        return recommendations


class StrategyRecommendationEngine:
    """Provides strategy recommendations based on performance metrics."""

    def __init__(self, metrics_collector: StrategyMetricsCollector):
        """Initialize the recommendation engine.
        
        Args:
            metrics_collector: Metrics collector instance
        """
        self.metrics_collector = metrics_collector

    def recommend_strategy(
        self, 
        context: Dict[str, Any],
        available_strategies: List[str]
    ) -> List[Tuple[str, float]]:
        """Recommend strategies based on context and performance.
        
        Args:
            context: Context for strategy selection
            available_strategies: List of available strategy names
            
        Returns:
            List of (strategy_name, confidence_score) tuples sorted by recommendation strength
        """
        all_metrics = self.metrics_collector.get_all_metrics()
        
        # Filter to available strategies only
        available_metrics = {
            name: metrics for name, metrics in all_metrics.items()
            if name in available_strategies
        }

        if not available_metrics:
            return []

        recommendations = []
        
        for name, metrics in available_metrics.items():
            confidence = self._calculate_recommendation_confidence(metrics, context)
            recommendations.append((name, confidence))

        # Sort by confidence (descending)
        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations

    def _calculate_recommendation_confidence(
        self, 
        metrics: StrategyMetrics, 
        context: Dict[str, Any]
    ) -> float:
        """Calculate recommendation confidence for a strategy.
        
        Args:
            metrics: Strategy metrics
            context: Selection context
            
        Returns:
            Confidence score between 0 and 1
        """
        if metrics.total_selections == 0:
            return 0.5  # Default confidence for untested strategies

        # Base confidence on success rate
        confidence = metrics.success_rate

        # Adjust based on latency requirements
        if "max_latency_ms" in context:
            if metrics.average_latency_ms <= context["max_latency_ms"]:
                confidence *= 1.1  # Boost for meeting latency requirements
            else:
                confidence *= 0.5  # Penalty for exceeding latency requirements

        # Adjust based on usage frequency (prefer proven strategies)
        if metrics.total_selections > 50:
            confidence *= 1.1
        elif metrics.total_selections < 5:
            confidence *= 0.8

        # Adjust based on recent performance
        trend = self.metrics_collector.get_performance_trend(metrics.strategy_name, hours=24)
        if trend.get("trend") == "improving":
            confidence *= 1.05
        elif trend.get("trend") == "declining":
            confidence *= 0.95

        return min(1.0, max(0.0, confidence))
