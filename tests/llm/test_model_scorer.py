# tests/llm/test_model_scorer.py

"""
Unit tests for the ModelScorer class.
"""

import time

from gemini_sre_agent.llm.model_scorer import (
    ModelScorer,
    ScoringWeights,
    ScoringContext,
    ScoringDimension,
    ModelScore
)
from gemini_sre_agent.llm.model_registry import ModelInfo, ModelCapability
from gemini_sre_agent.llm.base import ModelType, ProviderType


class TestModelScorer:
    """Test the ModelScorer class."""
    
    def create_test_model(self, name: str, **kwargs) -> ModelInfo:
        """Create a test model with default values."""
        defaults = {
            'provider': ProviderType.OPENAI,
            'semantic_type': ModelType.FAST,
            'capabilities': set(),
            'cost_per_1k_tokens': 0.001,
            'max_tokens': 4096,
            'context_window': 4096,
            'performance_score': 0.8,
            'reliability_score': 0.9,
            'fallback_models': [],
            'provider_specific': {}
        }
        defaults.update(kwargs)
        return ModelInfo(name=name, **defaults)
    
    def test_scorer_initialization(self):
        """Test ModelScorer initialization."""
        scorer = ModelScorer()
        assert scorer.default_weights is not None
        assert len(scorer._custom_scorers) > 0
        assert len(scorer._score_cache) == 0
    
    def test_scorer_with_custom_weights(self):
        """Test ModelScorer with custom default weights."""
        weights = ScoringWeights(cost=0.5, performance=0.3, reliability=0.2)
        scorer = ModelScorer(default_weights=weights)
        assert scorer.default_weights == weights
    
    def test_weights_normalization(self):
        """Test weight normalization."""
        weights = ScoringWeights(cost=0.3, performance=0.6, reliability=0.1)
        normalized = weights.normalize()
        
        total = normalized.cost + normalized.performance + normalized.reliability
        assert abs(total - 1.0) < 0.001
        assert normalized.cost == 0.3
        assert normalized.performance == 0.6
        assert normalized.reliability == 0.1
    
    def test_weights_normalization_zero_weights(self):
        """Test weight normalization with all zero weights."""
        weights = ScoringWeights(cost=0.0, performance=0.0, reliability=0.0)
        normalized = weights.normalize()
        
        total = sum([
            normalized.cost, normalized.performance, normalized.reliability,
            normalized.speed, normalized.quality, normalized.availability
        ])
        assert abs(total - 1.0) < 0.001
    
    def test_score_model_basic(self):
        """Test basic model scoring."""
        scorer = ModelScorer()
        model = self.create_test_model("test-model")
        context = ScoringContext()
        
        score = scorer.score_model(model, context)
        
        assert isinstance(score, ModelScore)
        assert score.model_name == "test-model"
        assert 0.0 <= score.overall_score <= 1.0
        assert len(score.dimension_scores) > 0
        assert score.context == context
    
    def test_score_model_with_weights(self):
        """Test model scoring with custom weights."""
        scorer = ModelScorer()
        model = self.create_test_model("test-model")
        context = ScoringContext()
        weights = ScoringWeights(cost=0.8, performance=0.2, reliability=0.0)
        
        score = scorer.score_model(model, context, weights)
        
        assert score.weights == weights.normalize()
        # Cost should have high influence due to weight
        assert ScoringDimension.COST in score.dimension_scores
    
    def test_score_model_with_context(self):
        """Test model scoring with context requirements."""
        scorer = ModelScorer()
        model = self.create_test_model(
            "test-model",
            capabilities={ModelCapability.STREAMING},
            cost_per_1k_tokens=0.005
        )
        context = ScoringContext(
            required_capabilities=[ModelCapability.STREAMING],
            max_cost=0.01,
            min_performance=0.7
        )
        
        score = scorer.score_model(model, context)
        
        assert score.context == context
        # Model should score well since it meets requirements
        assert score.overall_score > 0.0
    
    def test_score_models_multiple(self):
        """Test scoring multiple models."""
        scorer = ModelScorer()
        models = [
            self.create_test_model("model1", cost_per_1k_tokens=0.001),
            self.create_test_model("model2", cost_per_1k_tokens=0.005),
            self.create_test_model("model3", cost_per_1k_tokens=0.002)
        ]
        context = ScoringContext()
        
        scores = scorer.score_models(models, context)
        
        assert len(scores) == 3
        # Should be sorted by overall score (descending)
        for i in range(len(scores) - 1):
            assert scores[i].overall_score >= scores[i + 1].overall_score
    
    def test_rank_models(self):
        """Test model ranking functionality."""
        scorer = ModelScorer()
        models = [
            self.create_test_model("cheap-model", cost_per_1k_tokens=0.001),
            self.create_test_model("expensive-model", cost_per_1k_tokens=0.01),
            self.create_test_model("mid-model", cost_per_1k_tokens=0.005)
        ]
        context = ScoringContext()
        
        ranked = scorer.rank_models(models, context, top_k=2)
        
        assert len(ranked) == 2
        assert all(isinstance(pair, tuple) and len(pair) == 2 for pair in ranked)
        assert all(isinstance(pair[0], ModelInfo) and isinstance(pair[1], ModelScore) for pair in ranked)
    
    def test_compare_models(self):
        """Test model comparison functionality."""
        scorer = ModelScorer()
        model1 = self.create_test_model("model1", cost_per_1k_tokens=0.001, performance_score=0.8)
        model2 = self.create_test_model("model2", cost_per_1k_tokens=0.005, performance_score=0.9)
        context = ScoringContext()
        
        comparison = scorer.compare_models(model1, model2, context)
        
        assert 'model1' in comparison
        assert 'model2' in comparison
        assert 'winner' in comparison
        assert 'score_difference' in comparison
        assert 'dimension_comparison' in comparison
        
        assert comparison['model1']['name'] == "model1"
        assert comparison['model2']['name'] == "model2"
        assert comparison['winner'] in ["model1", "model2"]
    
    def test_custom_scorer_registration(self):
        """Test custom scorer registration."""
        scorer = ModelScorer()
        
        def custom_scorer(model_info: ModelInfo, context: ScoringContext) -> float:
            return 0.5
        
        scorer.register_custom_scorer(ScoringDimension.COST, custom_scorer)
        
        model = self.create_test_model("test-model")
        context = ScoringContext()
        weights = ScoringWeights(cost=1.0, performance=0.0, reliability=0.0)
        
        score = scorer.score_model(model, context, weights)
        
        # Should use custom scorer
        assert score.dimension_scores[ScoringDimension.COST] == 0.5
    
    def test_score_cost_dimension(self):
        """Test cost scoring dimension."""
        scorer = ModelScorer()
        context = ScoringContext()
        
        # Free model should get max score
        free_model = self.create_test_model("free-model", cost_per_1k_tokens=0.0)
        free_score = scorer._score_cost(free_model, context)
        assert free_score == 1.0
        
        # Expensive model should get lower score
        expensive_model = self.create_test_model("expensive-model", cost_per_1k_tokens=0.1)
        expensive_score = scorer._score_cost(expensive_model, context)
        assert expensive_score < free_score
    
    def test_score_performance_dimension(self):
        """Test performance scoring dimension."""
        scorer = ModelScorer()
        context = ScoringContext()
        
        model = self.create_test_model("test-model", performance_score=0.8)
        score = scorer._score_performance(model, context)
        assert score == 0.8
    
    def test_score_reliability_dimension(self):
        """Test reliability scoring dimension."""
        scorer = ModelScorer()
        context = ScoringContext()
        
        model = self.create_test_model("test-model", reliability_score=0.9)
        score = scorer._score_reliability(model, context)
        assert score == 0.9
    
    def test_score_speed_dimension(self):
        """Test speed scoring dimension."""
        scorer = ModelScorer()
        context = ScoringContext()
        
        # Low max_tokens should get higher speed score
        fast_model = self.create_test_model("fast-model", max_tokens=1000)
        fast_score = scorer._score_speed(fast_model, context)
        
        slow_model = self.create_test_model("slow-model", max_tokens=8000)
        slow_score = scorer._score_speed(slow_model, context)
        
        assert fast_score > slow_score
    
    def test_score_quality_dimension(self):
        """Test quality scoring dimension."""
        scorer = ModelScorer()
        context = ScoringContext()
        
        model = self.create_test_model(
            "test-model", 
            performance_score=0.8, 
            reliability_score=0.9
        )
        score = scorer._score_quality(model, context)
        expected = (0.8 + 0.9) / 2
        assert abs(score - expected) < 0.001
    
    def test_score_availability_dimension(self):
        """Test availability scoring dimension."""
        scorer = ModelScorer()
        
        # Preferred provider should get higher score
        context_preferred = ScoringContext(provider_preference=ProviderType.OPENAI)
        preferred_model = self.create_test_model("preferred-model", provider=ProviderType.OPENAI)
        preferred_score = scorer._score_availability(preferred_model, context_preferred)
        
        # Non-preferred provider should get lower score
        context_non_preferred = ScoringContext(provider_preference=ProviderType.CLAUDE)
        non_preferred_score = scorer._score_availability(preferred_model, context_non_preferred)
        
        assert preferred_score > non_preferred_score
        assert preferred_score == 1.0
        assert non_preferred_score == 0.5
    
    def test_score_caching(self):
        """Test score caching functionality."""
        scorer = ModelScorer()
        model = self.create_test_model("test-model")
        context = ScoringContext()
        
        # First call should not be cached
        score1 = scorer.score_model(model, context)
        assert len(scorer._score_cache) == 1
        
        # Second call should use cache
        score2 = scorer.score_model(model, context)
        assert score1.timestamp == score2.timestamp  # Same timestamp indicates cache hit
    
    def test_cache_management(self):
        """Test cache management and cleanup."""
        scorer = ModelScorer()
        scorer._cache_ttl = 1  # Very short TTL for testing (1 second)
        
        model = self.create_test_model("test-model")
        context = ScoringContext()
        
        # Score and cache
        scorer.score_model(model, context)
        assert len(scorer._score_cache) == 1
        
        # Wait for cache to expire
        time.sleep(1.1)
        
        # Next score should clear expired cache
        scorer.score_model(model, context)
        assert len(scorer._score_cache) == 1  # Should have cleared old and added new
    
    def test_clear_cache(self):
        """Test cache clearing."""
        scorer = ModelScorer()
        model = self.create_test_model("test-model")
        context = ScoringContext()
        
        # Add some scores to cache
        scorer.score_model(model, context)
        assert len(scorer._score_cache) > 0
        
        # Clear cache
        scorer.clear_cache()
        assert len(scorer._score_cache) == 0
    
    def test_get_cache_stats(self):
        """Test cache statistics."""
        scorer = ModelScorer()
        model = self.create_test_model("test-model")
        context = ScoringContext()
        
        # Add score to cache
        scorer.score_model(model, context)
        
        stats = scorer.get_cache_stats()
        assert 'total_entries' in stats
        assert 'valid_entries' in stats
        assert 'expired_entries' in stats
        assert 'cache_ttl' in stats
        assert stats['total_entries'] == 1
        assert stats['valid_entries'] == 1
        assert stats['expired_entries'] == 0
    
    def test_error_handling_in_scoring(self):
        """Test error handling during scoring."""
        scorer = ModelScorer()
        
        # Register a scorer that raises an exception
        def faulty_scorer(model_info: ModelInfo, context: ScoringContext) -> float:
            raise ValueError("Test error")
        
        scorer.register_custom_scorer(ScoringDimension.COST, faulty_scorer)
        
        model = self.create_test_model("test-model")
        context = ScoringContext()
        weights = ScoringWeights(cost=1.0, performance=0.0, reliability=0.0)
        
        # Should handle error gracefully
        score = scorer.score_model(model, context, weights)
        assert score.dimension_scores[ScoringDimension.COST] == 0.0  # Default to 0 on error
    
    def test_score_clamping(self):
        """Test that scores are clamped to [0, 1] range."""
        scorer = ModelScorer()
        
        # Register a scorer that returns out-of-range values
        def extreme_scorer(model_info: ModelInfo, context: ScoringContext) -> float:
            return 2.0  # Above 1.0
        
        scorer.register_custom_scorer(ScoringDimension.COST, extreme_scorer)
        
        model = self.create_test_model("test-model")
        context = ScoringContext()
        weights = ScoringWeights(cost=1.0, performance=0.0, reliability=0.0)
        
        score = scorer.score_model(model, context, weights)
        assert score.dimension_scores[ScoringDimension.COST] == 1.0  # Should be clamped to 1.0
