# gemini_sre_agent/llm/model_scorer.py

"""
Model Scoring Algorithm for intelligent model selection.

This module provides a flexible scoring system that evaluates models on multiple
dimensions including cost, performance, quality, and reliability to enable
optimal model selection based on different criteria.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .model_registry import ModelInfo, ModelCapability
from .base import ModelType, ProviderType

logger = logging.getLogger(__name__)


class ScoringDimension(str, Enum):
    """Available scoring dimensions."""
    
    COST = "cost"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    SPEED = "speed"
    QUALITY = "quality"
    AVAILABILITY = "availability"


@dataclass
class ScoringWeights:
    """Weights for different scoring dimensions."""
    
    cost: float = 0.3
    performance: float = 0.4
    reliability: float = 0.3
    speed: float = 0.0
    quality: float = 0.0
    availability: float = 0.0
    
    def normalize(self) -> 'ScoringWeights':
        """Normalize weights to sum to 1.0."""
        total = sum([
            self.cost, self.performance, self.reliability,
            self.speed, self.quality, self.availability
        ])
        
        if total == 0:
            # Default equal weights if all are zero
            return ScoringWeights(
                cost=0.2, performance=0.3, reliability=0.3,
                speed=0.1, quality=0.1, availability=0.0
            )
        
        return ScoringWeights(
            cost=self.cost / total,
            performance=self.performance / total,
            reliability=self.reliability / total,
            speed=self.speed / total,
            quality=self.quality / total,
            availability=self.availability / total
        )


@dataclass
class ScoringContext:
    """Context for model scoring."""
    
    task_type: Optional[ModelType] = None
    required_capabilities: List[ModelCapability] = field(default_factory=list)
    max_cost: Optional[float] = None
    min_performance: Optional[float] = None
    min_reliability: Optional[float] = None
    max_latency_ms: Optional[float] = None
    provider_preference: Optional[ProviderType] = None
    custom_requirements: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelScore:
    """Comprehensive score for a model."""
    
    model_name: str
    overall_score: float
    dimension_scores: Dict[ScoringDimension, float]
    weights: ScoringWeights
    context: ScoringContext
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelScorer:
    """
    Flexible scoring system for model evaluation and selection.
    
    Provides configurable scoring algorithms that can be customized
    for different use cases and requirements.
    """
    
    def __init__(self, default_weights: Optional[ScoringWeights] = None):
        """Initialize the ModelScorer with default weights."""
        self.default_weights = default_weights or ScoringWeights()
        self._custom_scorers: Dict[ScoringDimension, Callable] = {}
        self._score_cache: Dict[str, ModelScore] = {}
        self._cache_ttl = 300  # 5 minutes
        
        # Register default scorers
        self._register_default_scorers()
    
    def _register_default_scorers(self) -> None:
        """Register default scoring functions for each dimension."""
        self._custom_scorers[ScoringDimension.COST] = self._score_cost
        self._custom_scorers[ScoringDimension.PERFORMANCE] = self._score_performance
        self._custom_scorers[ScoringDimension.RELIABILITY] = self._score_reliability
        self._custom_scorers[ScoringDimension.SPEED] = self._score_speed
        self._custom_scorers[ScoringDimension.QUALITY] = self._score_quality
        self._custom_scorers[ScoringDimension.AVAILABILITY] = self._score_availability
    
    def register_custom_scorer(
        self, 
        dimension: ScoringDimension, 
        scorer_func: Callable[[ModelInfo, ScoringContext], float]
    ) -> None:
        """Register a custom scoring function for a dimension."""
        self._custom_scorers[dimension] = scorer_func
        logger.info(f"Registered custom scorer for dimension: {dimension}")
    
    def score_model(
        self, 
        model_info: ModelInfo, 
        context: ScoringContext,
        weights: Optional[ScoringWeights] = None
    ) -> ModelScore:
        """Calculate comprehensive score for a model."""
        weights = weights or self.default_weights
        weights = weights.normalize()
        
        # Check cache first
        cache_key = self._get_cache_key(model_info.name, context, weights)
        cached_score = self._get_cached_score(cache_key)
        if cached_score:
            return cached_score
        
        # Calculate dimension scores
        dimension_scores = {}
        for dimension in ScoringDimension:
            if hasattr(weights, dimension.value) and getattr(weights, dimension.value) > 0:
                scorer = self._custom_scorers.get(dimension)
                if scorer:
                    try:
                        score = scorer(model_info, context)
                        dimension_scores[dimension] = max(0.0, min(1.0, score))  # Clamp to [0, 1]
                    except Exception as e:
                        logger.warning(f"Error scoring {dimension} for {model_info.name}: {e}")
                        dimension_scores[dimension] = 0.0
                else:
                    dimension_scores[dimension] = 0.0
        
        # Calculate weighted overall score
        overall_score = 0.0
        for dimension, score in dimension_scores.items():
            weight = getattr(weights, dimension.value, 0.0)
            overall_score += score * weight
        
        # Create score object
        model_score = ModelScore(
            model_name=model_info.name,
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            weights=weights,
            context=context,
            metadata={
                'model_provider': model_info.provider.value,
                'model_semantic_type': model_info.semantic_type.value,
                'model_capabilities': [cap.value for cap in model_info.capabilities]
            }
        )
        
        # Cache the score
        self._cache_score(cache_key, model_score)
        
        return model_score
    
    def score_models(
        self, 
        models: List[ModelInfo], 
        context: ScoringContext,
        weights: Optional[ScoringWeights] = None
    ) -> List[ModelScore]:
        """Score multiple models and return sorted list."""
        scores = []
        for model in models:
            try:
                score = self.score_model(model, context, weights)
                scores.append(score)
            except Exception as e:
                logger.error(f"Error scoring model {model.name}: {e}")
                continue
        
        # Sort by overall score (descending)
        scores.sort(key=lambda s: s.overall_score, reverse=True)
        return scores
    
    def rank_models(
        self, 
        models: List[ModelInfo], 
        context: ScoringContext,
        weights: Optional[ScoringWeights] = None,
        top_k: Optional[int] = None
    ) -> List[Tuple[ModelInfo, ModelScore]]:
        """Rank models by score and return top-k results."""
        scores = self.score_models(models, context, weights)
        
        # Create model-score pairs
        model_score_pairs = []
        for score in scores:
            model = next((m for m in models if m.name == score.model_name), None)
            if model:
                model_score_pairs.append((model, score))
        
        # Apply top-k filter
        if top_k is not None:
            model_score_pairs = model_score_pairs[:top_k]
        
        return model_score_pairs
    
    def compare_models(
        self, 
        model1: ModelInfo, 
        model2: ModelInfo, 
        context: ScoringContext,
        weights: Optional[ScoringWeights] = None
    ) -> Dict[str, Any]:
        """Compare two models and return detailed comparison."""
        score1 = self.score_model(model1, context, weights)
        score2 = self.score_model(model2, context, weights)
        
        comparison = {
            'model1': {
                'name': model1.name,
                'overall_score': score1.overall_score,
                'dimension_scores': score1.dimension_scores
            },
            'model2': {
                'name': model2.name,
                'overall_score': score2.overall_score,
                'dimension_scores': score2.dimension_scores
            },
            'winner': model1.name if score1.overall_score > score2.overall_score else model2.name,
            'score_difference': abs(score1.overall_score - score2.overall_score),
            'dimension_comparison': {}
        }
        
        # Compare each dimension
        for dimension in ScoringDimension:
            if dimension in score1.dimension_scores and dimension in score2.dimension_scores:
                score1_val = score1.dimension_scores[dimension]
                score2_val = score2.dimension_scores[dimension]
                comparison['dimension_comparison'][dimension.value] = {
                    'model1': score1_val,
                    'model2': score2_val,
                    'difference': score1_val - score2_val
                }
        
        return comparison
    
    # Default scoring functions
    def _score_cost(self, model_info: ModelInfo, context: ScoringContext) -> float:
        """Score model based on cost (lower is better)."""
        if model_info.cost_per_1k_tokens == 0:
            return 1.0  # Free models get max score
        
        # Normalize cost (assume max reasonable cost is $0.1 per 1k tokens)
        max_cost = 0.1
        normalized_cost = min(model_info.cost_per_1k_tokens / max_cost, 1.0)
        return 1.0 - normalized_cost  # Invert so lower cost = higher score
    
    def _score_performance(self, model_info: ModelInfo, context: ScoringContext) -> float:
        """Score model based on performance metrics."""
        return model_info.performance_score
    
    def _score_reliability(self, model_info: ModelInfo, context: ScoringContext) -> float:
        """Score model based on reliability metrics."""
        return model_info.reliability_score
    
    def _score_speed(self, model_info: ModelInfo, context: ScoringContext) -> float:
        """Score model based on speed/latency."""
        # Use max_tokens as a proxy for speed (higher max_tokens = potentially slower)
        # This is a simplified heuristic
        max_tokens = model_info.max_tokens
        if max_tokens <= 1000:
            return 1.0
        elif max_tokens <= 4000:
            return 0.8
        elif max_tokens <= 8000:
            return 0.6
        else:
            return 0.4
    
    def _score_quality(self, model_info: ModelInfo, context: ScoringContext) -> float:
        """Score model based on quality metrics."""
        # Combine performance and reliability for quality
        return (model_info.performance_score + model_info.reliability_score) / 2
    
    def _score_availability(self, model_info: ModelInfo, context: ScoringContext) -> float:
        """Score model based on availability (provider preference)."""
        if context.provider_preference and model_info.provider == context.provider_preference:
            return 1.0
        return 0.5  # Neutral score for non-preferred providers
    
    # Cache management
    def _get_cache_key(
        self, 
        model_name: str, 
        context: ScoringContext, 
        weights: ScoringWeights
    ) -> str:
        """Generate cache key for model score."""
        key_parts = [
            model_name,
            str(context.task_type),
            str(sorted(context.required_capabilities)),
            str(context.max_cost),
            str(context.min_performance),
            str(context.min_reliability),
            str(context.provider_preference),
            str(weights.cost),
            str(weights.performance),
            str(weights.reliability)
        ]
        return "|".join(key_parts)
    
    def _get_cached_score(self, cache_key: str) -> Optional[ModelScore]:
        """Get cached score if still valid."""
        if cache_key in self._score_cache:
            cached_score = self._score_cache[cache_key]
            if time.time() - cached_score.timestamp < self._cache_ttl:
                return cached_score
            else:
                del self._score_cache[cache_key]
        return None
    
    def _cache_score(self, cache_key: str, score: ModelScore) -> None:
        """Cache a model score."""
        self._score_cache[cache_key] = score
        
        # Clean up old cache entries
        current_time = time.time()
        expired_keys = [
            key for key, cached_score in self._score_cache.items()
            if current_time - cached_score.timestamp > self._cache_ttl
        ]
        for key in expired_keys:
            del self._score_cache[key]
    
    def clear_cache(self) -> None:
        """Clear the score cache."""
        self._score_cache.clear()
        logger.info("Model score cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        valid_entries = sum(
            1 for score in self._score_cache.values()
            if current_time - score.timestamp < self._cache_ttl
        )
        
        return {
            'total_entries': len(self._score_cache),
            'valid_entries': valid_entries,
            'expired_entries': len(self._score_cache) - valid_entries,
            'cache_ttl': self._cache_ttl
        }
