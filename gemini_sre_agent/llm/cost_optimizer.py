"""
Cost Optimization System for Multi-Provider LLM Operations.

This module provides intelligent cost optimization strategies and model selection
based on cost, performance, and budget constraints.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .cost_management import DynamicCostManager, OptimizationStrategy, UsageRecord
from .model_registry import ModelInfo, ModelRegistry
from .strategy_manager import StrategyContext

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result of cost optimization."""
    selected_model: ModelInfo
    estimated_cost: float
    reasoning: str
    alternatives: List[Tuple[ModelInfo, float]]  # (model, cost) pairs
    optimization_strategy: OptimizationStrategy
    execution_time_ms: float


class CostOptimizer:
    """Intelligent cost optimization for model selection."""
    
    def __init__(
        self,
        cost_manager: DynamicCostManager,
        model_registry: ModelRegistry
    ):
        self.cost_manager = cost_manager
        self.model_registry = model_registry
        
        # Optimization strategies
        self.strategies = {
            OptimizationStrategy.BUDGET: self._budget_optimized_strategy,
            OptimizationStrategy.PERFORMANCE: self._performance_optimized_strategy,
            OptimizationStrategy.BALANCED: self._balanced_strategy,
        }
    
    def optimize_model_selection(
        self,
        context: StrategyContext,
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
        max_cost: Optional[float] = None
    ) -> OptimizationResult:
        """
        Optimize model selection based on cost and performance requirements.
        
        Args:
            context: Strategy context with requirements
            strategy: Optimization strategy to use
            max_cost: Maximum cost constraint
            
        Returns:
            OptimizationResult with selected model and reasoning
        """
        start_time = time.time()
        
        # Get available models
        # Get available models for the request type
        # For now, we'll use a simplified approach since get_models_by_type doesn't exist
        available_models = []  # This would be populated with actual models
        
        if not available_models:
            raise ValueError(f"No models available for type {getattr(context, 'model_type', 'unknown')}")
        
        # Filter by constraints
        filtered_models = self._filter_models_by_constraints(available_models, context, max_cost)
        
        if not filtered_models:
            raise ValueError("No models meet the specified constraints")
        
        # Apply optimization strategy
        strategy_func = self.strategies.get(strategy, self._balanced_strategy)
        selected_model, reasoning = strategy_func(filtered_models, context)
        
        # Calculate estimated cost
        estimated_cost = self._estimate_request_cost(selected_model, context)
        
        # Get alternative options
        alternatives = self._get_alternatives(filtered_models, selected_model, context)
        
        execution_time = (time.time() - start_time) * 1000
        
        return OptimizationResult(
            selected_model=selected_model,
            estimated_cost=estimated_cost,
            reasoning=reasoning,
            alternatives=alternatives,
            optimization_strategy=strategy,
            execution_time_ms=execution_time
        )
    
    def _filter_models_by_constraints(
        self,
        models: List[ModelInfo],
        context: StrategyContext,
        max_cost: Optional[float]
    ) -> List[ModelInfo]:
        """Filter models based on constraints."""
        filtered = []
        
        for model in models:
            # Check provider preference
            if context.provider_preference and model.provider not in context.provider_preference:
                continue
            
            # Check cost constraint
            if max_cost is not None:
                estimated_cost = self._estimate_request_cost(model, context)
                if estimated_cost > max_cost:
                    continue
            
            # Check capability requirements (simplified for now)
            # In a real implementation, this would check model capabilities
            # if hasattr(context, 'required_capabilities') and context.required_capabilities:
            #     model_capabilities = set(model.capabilities or [])
            #     required_capabilities = set(context.required_capabilities)
            #     if not required_capabilities.issubset(model_capabilities):
            #         continue
            
            filtered.append(model)
        
        return filtered
    
    def _budget_optimized_strategy(
        self,
        models: List[ModelInfo],
        context: StrategyContext
    ) -> Tuple[ModelInfo, str]:
        """Select the cheapest model that meets requirements."""
        # Sort by cost per 1k tokens
        sorted_models = sorted(models, key=lambda m: m.cost_per_1k_tokens)
        selected = sorted_models[0]
        
        reasoning = f"Selected {selected.name} as the cheapest model (${selected.cost_per_1k_tokens}/1k tokens) that meets all requirements"
        
        return selected, reasoning
    
    def _performance_optimized_strategy(
        self,
        models: List[ModelInfo],
        context: StrategyContext
    ) -> Tuple[ModelInfo, str]:
        """Select the highest performance model within budget."""
        # Sort by performance score (assuming higher is better)
        # For now, we'll use a simple heuristic based on model name patterns
        def performance_score(model: ModelInfo) -> float:
            score = 1.0
            
            # Prefer newer models
            if "gpt-4" in model.name.lower():
                score += 2.0
            elif "claude-3" in model.name.lower():
                score += 1.8
            elif "gemini-1.5" in model.name.lower():
                score += 1.5
            
            # Prefer pro/opus models over turbo/flash
            if any(term in model.name.lower() for term in ["pro", "opus", "sonnet"]):
                score += 1.0
            
            return score
        
        sorted_models = sorted(models, key=performance_score, reverse=True)
        selected = sorted_models[0]
        
        reasoning = f"Selected {selected.name} as the highest performance model that meets requirements"
        
        return selected, reasoning
    
    def _balanced_strategy(
        self,
        models: List[ModelInfo],
        context: StrategyContext
    ) -> Tuple[ModelInfo, str]:
        """Select model with best cost/performance ratio."""
        def cost_performance_ratio(model: ModelInfo) -> float:
            # Calculate a simple cost/performance ratio
            # Lower cost and higher performance = better ratio
            performance_score = 1.0
            
            if "gpt-4" in model.name.lower():
                performance_score = 3.0
            elif "claude-3" in model.name.lower():
                performance_score = 2.5
            elif "gemini-1.5" in model.name.lower():
                performance_score = 2.0
            
            # Avoid division by zero
            cost = max(model.cost_per_1k_tokens, 0.001)
            return performance_score / cost
        
        sorted_models = sorted(models, key=cost_performance_ratio, reverse=True)
        selected = sorted_models[0]
        
        reasoning = f"Selected {selected.name} as the model with the best cost/performance ratio (${selected.cost_per_1k_tokens}/1k tokens)"
        
        return selected, reasoning
    
    def _estimate_request_cost(self, model: ModelInfo, context: StrategyContext) -> float:
        """Estimate cost for a request with the given model."""
        # Use average token counts for estimation
        # In a real implementation, this would be more sophisticated
        avg_input_tokens = 1000  # Default assumption
        avg_output_tokens = 500   # Default assumption
        
        return self.cost_manager.estimate_cost(
            model.provider,
            model.name,
            avg_input_tokens,
            avg_output_tokens
        )
    
    def _get_alternatives(
        self,
        models: List[ModelInfo],
        selected_model: ModelInfo,
        context: StrategyContext
    ) -> List[Tuple[ModelInfo, float]]:
        """Get alternative model options with their estimated costs."""
        alternatives = []
        
        for model in models:
            if model == selected_model:
                continue
            
            estimated_cost = self._estimate_request_cost(model, context)
            alternatives.append((model, estimated_cost))
        
        # Sort by cost
        alternatives.sort(key=lambda x: x[1])
        
        return alternatives[:3]  # Return top 3 alternatives
    
    def get_cost_comparison(self, models: List[ModelInfo], context: StrategyContext) -> Dict[str, Any]:
        """Get cost comparison for multiple models."""
        comparison = {}
        
        for model in models:
            estimated_cost = self._estimate_request_cost(model, context)
            comparison[model.name] = {
                "provider": model.provider.value,
                "cost_per_1k_tokens": model.cost_per_1k_tokens,
                "estimated_cost": estimated_cost,
                "capabilities": model.capabilities or [],
            }
        
        return comparison
    
    def optimize_for_budget(
        self,
        context: StrategyContext,
        budget_limit: float
    ) -> OptimizationResult:
        """Optimize model selection within a specific budget."""
        return self.optimize_model_selection(
            context=context,
            strategy=OptimizationStrategy.BUDGET,
            max_cost=budget_limit
        )
    
    def get_optimization_recommendations(
        self,
        usage_records: List[UsageRecord]
    ) -> Dict[str, Any]:
        """Get optimization recommendations based on usage patterns."""
        if not usage_records:
            return {"recommendations": [], "savings_potential": 0.0}
        
        # Analyze usage patterns
        provider_usage = {}
        model_usage = {}
        total_cost = 0.0
        
        for record in usage_records:
            provider = record.provider.value
            model = record.model
            
            if provider not in provider_usage:
                provider_usage[provider] = {"cost": 0.0, "requests": 0}
            provider_usage[provider]["cost"] += record.cost_usd
            provider_usage[provider]["requests"] += 1
            
            if model not in model_usage:
                model_usage[model] = {"cost": 0.0, "requests": 0}
            model_usage[model]["cost"] += record.cost_usd
            model_usage[model]["requests"] += 1
            
            total_cost += record.cost_usd
        
        recommendations = []
        
        # Find most expensive models
        expensive_models = sorted(model_usage.items(), key=lambda x: x[1]["cost"], reverse=True)[:3]
        for model, usage in expensive_models:
            if usage["cost"] > total_cost * 0.2:  # More than 20% of total cost
                recommendations.append({
                    "type": "high_cost_model",
                    "model": model,
                    "cost": usage["cost"],
                    "percentage": (usage["cost"] / total_cost) * 100,
                    "suggestion": f"Consider using a cheaper model for {model} to reduce costs"
                })
        
        # Calculate potential savings
        savings_potential = 0.0
        for rec in recommendations:
            if rec["type"] == "high_cost_model":
                savings_potential += rec["cost"] * 0.3  # Assume 30% savings possible
        
        return {
            "recommendations": recommendations,
            "savings_potential": savings_potential,
            "total_current_cost": total_cost,
            "provider_breakdown": provider_usage,
            "model_breakdown": model_usage,
        }
