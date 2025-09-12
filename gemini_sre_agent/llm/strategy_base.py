"""
Strategy base classes and common types for model selection strategies.

This module provides the abstract base class and common types for implementing
the Strategy pattern in model selection. It defines the core interfaces and
data structures used by all strategy implementations.

Classes:
    ModelSelectionStrategy: Abstract base class for model selection strategies
    OptimizationGoal: Enum defining available optimization goals
    StrategyContext: Context data for strategy execution
    StrategyResult: Result data from strategy execution
    ScoringWeights: Configuration for model scoring weights
    ScoringContext: Context for model scoring operations

Author: Gemini SRE Agent
Created: 2024
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from enum import Enum
from typing import Dict, List, Optional, Any
import time

from .model_registry import ModelInfo
from .model_scorer import ModelScorer, ModelScore, ScoringWeights, ScoringContext


class OptimizationGoal(Enum):
    """Enumeration of available optimization goals for model selection."""
    
    COST = "cost"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    TIME_BASED = "time_based"
    HYBRID = "hybrid"


@dataclass
class StrategyContext:
    """Context data for strategy execution."""
    
    task_type: str
    max_cost: Optional[float] = None
    min_performance: Optional[float] = None
    min_quality: Optional[float] = None
    provider_preference: Optional[List[str]] = None
    business_hours_only: bool = False
    custom_weights: Optional['ScoringWeights'] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class StrategyResult:
    """Result data from strategy execution."""
    
    selected_model: ModelInfo
    score: 'ModelScore'
    strategy_used: str
    execution_time_ms: float
    fallback_models: List[ModelInfo]
    reasoning: str
    metadata: Dict[str, Any]


# Use the types from model_scorer module


class ModelSelectionStrategy(ABC):
    """Abstract base class for model selection strategies."""
    
    def __init__(self, name: str, model_scorer: Optional[ModelScorer] = None):
        """Initialize the strategy.
        
        Args:
            name: Human-readable name for the strategy
            model_scorer: Optional model scorer instance
        """
        self.name = name
        self.model_scorer = model_scorer or ModelScorer()
        self._selection_history: List[Dict[str, Any]] = []
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
        """Select the best model from candidates based on strategy.
        
        Args:
            candidates: List of available models
            context: Strategy execution context
            
        Returns:
            StrategyResult containing selected model and metadata
            
        Raises:
            ValueError: If no models meet the constraints
        """
        pass
    
    def _filter_candidates(
        self, candidates: List[ModelInfo], context: StrategyContext
    ) -> List[ModelInfo]:
        """Filter candidates based on context constraints.
        
        Args:
            candidates: List of available models
            context: Strategy execution context
            
        Returns:
            Filtered list of candidates meeting constraints
        """
        filtered = candidates.copy()
        
        # Filter by cost constraint
        if context.max_cost is not None:
            filtered = [m for m in filtered if m.cost_per_1k_tokens <= context.max_cost]
        
        # Filter by performance constraint
        if context.min_performance is not None:
            filtered = [m for m in filtered if m.performance_score >= context.min_performance]
        
        # Filter by quality constraint (using performance_score as proxy)
        if context.min_quality is not None:
            filtered = [m for m in filtered if m.performance_score >= context.min_quality]
        
        # Filter by provider preference
        if context.provider_preference:
            filtered = [m for m in filtered if m.provider in context.provider_preference]
        
        return filtered
    
    def update_performance(
        self, 
        selected_model: Optional[ModelInfo], 
        score: float, 
        success: bool, 
        latency_ms: float
    ):
        """Update performance metrics based on strategy usage.
        
        Args:
            selected_model: The model that was selected (if any)
            score: The score assigned to the selected model
            success: Whether the selection was successful
            latency_ms: Execution latency in milliseconds
        """
        self._performance_metrics["total_selections"] += 1
        
        if success:
            self._performance_metrics["successful_selections"] += 1
        
        # Update average score
        current_avg = self._performance_metrics["average_score"]
        total = self._performance_metrics["total_selections"]
        self._performance_metrics["average_score"] = (
            (current_avg * (total - 1) + score) / total
        )
        
        # Update average latency
        current_avg_latency = self._performance_metrics["average_latency"]
        self._performance_metrics["average_latency"] = (
            (current_avg_latency * (total - 1) + latency_ms) / total
        )
        
        # Record selection history
        self._selection_history.append({
            "timestamp": datetime.now().isoformat(),
            "model": selected_model.name if selected_model else None,
            "score": score,
            "success": success,
            "latency_ms": latency_ms,
        })
        
        # Keep only last 100 selections
        if len(self._selection_history) > 100:
            self._selection_history = self._selection_history[-100:]
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get current performance metrics.
        
        Returns:
            Dictionary containing performance metrics
        """
        return self._performance_metrics.copy()
    
    def get_selection_history(self) -> List[Dict[str, Any]]:
        """Get selection history.
        
        Returns:
            List of recent selections with metadata
        """
        return self._selection_history.copy()
    
    def reset_metrics(self):
        """Reset all performance metrics."""
        self._performance_metrics = {
            "total_selections": 0.0,
            "successful_selections": 0.0,
            "average_score": 0.0,
            "average_latency": 0.0,
        }
        self._selection_history.clear()
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the strategy.
        
        Returns:
            Dictionary containing health status and metrics
        """
        return {
            "status": "healthy",
            "strategy_name": self.name,
            "total_selections": self._performance_metrics["total_selections"],
            "success_rate": (
                self._performance_metrics["successful_selections"] / 
                max(1, self._performance_metrics["total_selections"])
            ),
            "average_score": self._performance_metrics["average_score"],
            "average_latency_ms": self._performance_metrics["average_latency"],
        }
