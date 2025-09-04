# tests/llm/test_model_selector.py

"""
Unit tests for the ModelSelector class.
"""

from unittest.mock import Mock

import pytest

from gemini_sre_agent.llm.base import ModelType, ProviderType
from gemini_sre_agent.llm.model_registry import (
    ModelCapability,
    ModelInfo,
    ModelRegistry,
)
from gemini_sre_agent.llm.model_scorer import (
    ModelScore,
    ModelScorer,
    ScoringContext,
    ScoringWeights,
)
from gemini_sre_agent.llm.model_selector import (
    ModelSelector,
    SelectionCriteria,
    SelectionResult,
    SelectionStrategy,
)


class TestModelSelector:
    """Test the ModelSelector class."""

    def create_test_model(self, name: str, **kwargs) -> ModelInfo:
        """Create a test model with default values."""
        defaults = {
            "provider": ProviderType.OPENAI,
            "semantic_type": ModelType.FAST,
            "capabilities": set(),
            "cost_per_1k_tokens": 0.001,
            "max_tokens": 4096,
            "context_window": 4096,
            "performance_score": 0.8,
            "reliability_score": 0.9,
            "fallback_models": [],
            "provider_specific": {},
        }
        defaults.update(kwargs)
        return ModelInfo(name=name, **defaults)

    def create_mock_registry(self) -> ModelRegistry:
        """Create a mock model registry."""
        registry = Mock(spec=ModelRegistry)
        registry.query_models = Mock()
        registry.get_model = Mock()
        registry.get_models_by_semantic_type = Mock(return_value=[])
        return registry

    def create_mock_scorer(self) -> ModelScorer:
        """Create a mock model scorer."""
        scorer = Mock(spec=ModelScorer)
        scorer.rank_models = Mock()
        scorer.score_model = Mock()
        return scorer

    def test_selector_initialization(self):
        """Test ModelSelector initialization."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        selector = ModelSelector(registry, scorer)

        assert selector.model_registry == registry
        assert selector.model_scorer == scorer
        assert len(selector._selection_cache) == 0
        assert len(selector._selection_stats) == 0

    def test_selector_initialization_with_default_scorer(self):
        """Test ModelSelector initialization with default scorer."""
        registry = self.create_mock_registry()

        selector = ModelSelector(registry)

        assert selector.model_registry == registry
        assert isinstance(selector.model_scorer, ModelScorer)

    def test_select_model_basic(self):
        """Test basic model selection."""
        # Setup mocks
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        model = self.create_test_model("test-model")
        score = ModelScore(
            model_name="test-model",
            overall_score=0.8,
            dimension_scores={},
            weights=ScoringWeights(),
            context=ScoringContext(),
        )

        registry.query_models.return_value = [model]
        scorer.score_model.return_value = score
        scorer.rank_models.return_value = [(model, score)]

        selector = ModelSelector(registry, scorer)
        criteria = SelectionCriteria(semantic_type=ModelType.FAST)

        result = selector.select_model(criteria)

        assert isinstance(result, SelectionResult)
        assert result.selected_model == model
        assert result.score == score
        assert result.criteria == criteria
        assert len(result.fallback_chain) >= 1
        assert result.fallback_chain[0] == model

    def test_select_model_with_criteria(self):
        """Test model selection with specific criteria."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        model = self.create_test_model(
            "test-model",
            capabilities={ModelCapability.STREAMING},
            cost_per_1k_tokens=0.005,
        )
        score = ModelScore(
            model_name="test-model",
            overall_score=0.8,
            dimension_scores={},
            weights=ScoringWeights(),
            context=ScoringContext(),
        )

        registry.query_models.return_value = [model]
        scorer.score_model.return_value = score
        scorer.rank_models.return_value = [(model, score)]

        selector = ModelSelector(registry, scorer)
        criteria = SelectionCriteria(
            semantic_type=ModelType.SMART,
            required_capabilities=[ModelCapability.STREAMING],
            max_cost=0.01,
            min_performance=0.7,
        )

        result = selector.select_model(criteria)

        assert result.criteria == criteria
        # Verify registry was called with correct parameters
        registry.query_models.assert_called_once()
        call_args = registry.query_models.call_args
        assert call_args[1]["semantic_type"] == ModelType.SMART
        assert call_args[1]["capabilities"] == [ModelCapability.STREAMING]
        assert call_args[1]["max_cost"] == 0.01
        assert call_args[1]["min_performance"] == 0.7

    def test_select_model_different_strategies(self):
        """Test model selection with different strategies."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        model1 = self.create_test_model(
            "fast-model", max_tokens=1000, cost_per_1k_tokens=0.001
        )
        model2 = self.create_test_model(
            "reliable-model", reliability_score=0.95, cost_per_1k_tokens=0.005
        )
        model3 = self.create_test_model("cheap-model", cost_per_1k_tokens=0.0005)

        score = ModelScore(
            model_name="test-model",
            overall_score=0.8,
            dimension_scores={},
            weights=ScoringWeights(),
            context=ScoringContext(),
        )

        registry.query_models.return_value = [model1, model2, model3]
        scorer.score_model.return_value = score
        scorer.rank_models.return_value = [(model1, score)]

        selector = ModelSelector(registry, scorer)

        # Test fastest strategy
        criteria = SelectionCriteria(strategy=SelectionStrategy.FASTEST)
        result = selector.select_model(criteria)
        assert (
            result.selected_model == model1
        )  # Should select model with lowest max_tokens

        # Test cheapest strategy
        criteria = SelectionCriteria(strategy=SelectionStrategy.CHEAPEST)
        result = selector.select_model(criteria)
        assert result.selected_model == model3  # Should select model with lowest cost

        # Test most reliable strategy
        criteria = SelectionCriteria(strategy=SelectionStrategy.MOST_RELIABLE)
        result = selector.select_model(criteria)
        assert (
            result.selected_model == model2
        )  # Should select model with highest reliability

    def test_select_model_with_fallback(self):
        """Test model selection with fallback support."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        primary_model = self.create_test_model(
            "primary-model", fallback_models=["fallback1", "fallback2"]
        )
        fallback1_model = self.create_test_model("fallback1")
        fallback2_model = self.create_test_model("fallback2")

        score = ModelScore(
            model_name="primary-model",
            overall_score=0.8,
            dimension_scores={},
            weights=ScoringWeights(),
            context=ScoringContext(),
        )

        registry.query_models.return_value = [primary_model]
        registry.get_model.side_effect = lambda name: {
            "fallback1": fallback1_model,
            "fallback2": fallback2_model,
        }.get(name)
        registry.get_models_by_semantic_type.return_value = [
            primary_model,
            fallback1_model,
            fallback2_model,
        ]

        scorer.score_model.return_value = score
        scorer.rank_models.return_value = [(primary_model, score)]

        selector = ModelSelector(registry, scorer)
        criteria = SelectionCriteria(allow_fallback=True)

        result = selector.select_model(criteria)

        assert result.selected_model == primary_model
        assert len(result.fallback_chain) >= 3  # Primary + configured fallbacks
        assert result.fallback_chain[0] == primary_model

    def test_select_model_without_fallback(self):
        """Test model selection without fallback support."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        model = self.create_test_model("test-model", fallback_models=["fallback1"])
        score = ModelScore(
            model_name="test-model",
            overall_score=0.8,
            dimension_scores={},
            weights=ScoringWeights(),
            context=ScoringContext(),
        )

        registry.query_models.return_value = [model]
        scorer.score_model.return_value = score
        scorer.rank_models.return_value = [(model, score)]

        selector = ModelSelector(registry, scorer)
        criteria = SelectionCriteria(allow_fallback=False)

        result = selector.select_model(criteria)

        assert result.selected_model == model
        assert len(result.fallback_chain) == 1  # Only primary model
        assert result.fallback_chain[0] == model

    def test_select_model_with_fallback_execution(self):
        """Test select_model_with_fallback method."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        primary_model = self.create_test_model("primary-model")
        fallback_model = self.create_test_model("fallback-model")

        score = ModelScore(
            model_name="primary-model",
            overall_score=0.8,
            dimension_scores={},
            weights=ScoringWeights(),
            context=ScoringContext(),
        )

        registry.query_models.return_value = [primary_model]
        registry.get_models_by_semantic_type.return_value = [
            primary_model,
            fallback_model,
        ]

        scorer.score_model.return_value = score
        scorer.rank_models.return_value = [
            (primary_model, score),
            (fallback_model, score),
        ]

        selector = ModelSelector(registry, scorer)
        criteria = SelectionCriteria(allow_fallback=True)

        # Mock _is_model_available to return False for primary, True for fallback
        selector._is_model_available = Mock(
            side_effect=lambda m: m.name != "primary-model"
        )

        selected_model, result = selector.select_model_with_fallback(criteria)

        assert selected_model == fallback_model
        assert (
            result.selected_model == primary_model
        )  # Result still shows primary as selected
        assert len(result.fallback_chain) >= 2

    def test_meets_criteria(self):
        """Test criteria matching logic."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()
        selector = ModelSelector(registry, scorer)

        model = self.create_test_model("test-model", max_tokens=4000)

        # Test provider preference
        criteria = SelectionCriteria(provider_preference=ProviderType.CLAUDE)
        assert not selector._meets_criteria(model, criteria)

        criteria = SelectionCriteria(provider_preference=ProviderType.OPENAI)
        assert selector._meets_criteria(model, criteria)

        # Test latency constraint
        criteria = SelectionCriteria(max_latency_ms=100)  # Very low latency requirement
        assert not selector._meets_criteria(model, criteria)

        criteria = SelectionCriteria(max_latency_ms=1000)  # Higher latency requirement
        assert selector._meets_criteria(model, criteria)

    def test_selection_caching(self):
        """Test selection result caching."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        model = self.create_test_model("test-model")
        score = ModelScore(
            model_name="test-model",
            overall_score=0.8,
            dimension_scores={},
            weights=ScoringWeights(),
            context=ScoringContext(),
        )

        registry.query_models.return_value = [model]
        scorer.score_model.return_value = score
        scorer.rank_models.return_value = [(model, score)]

        selector = ModelSelector(registry, scorer)
        criteria = SelectionCriteria(semantic_type=ModelType.FAST)

        # First call should not be cached
        result1 = selector.select_model(criteria)
        assert len(selector._selection_cache) == 1

        # Second call should use cache
        result2 = selector.select_model(criteria)
        assert (
            result1.timestamp == result2.timestamp
        )  # Same timestamp indicates cache hit

    def test_selection_caching_disabled(self):
        """Test selection with caching disabled."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        model = self.create_test_model("test-model")
        score = ModelScore(
            model_name="test-model",
            overall_score=0.8,
            dimension_scores={},
            weights=ScoringWeights(),
            context=ScoringContext(),
        )

        registry.query_models.return_value = [model]
        scorer.score_model.return_value = score
        scorer.rank_models.return_value = [(model, score)]

        selector = ModelSelector(registry, scorer)
        criteria = SelectionCriteria(semantic_type=ModelType.FAST)

        # First call
        result1 = selector.select_model(criteria, use_cache=False)
        assert len(selector._selection_cache) == 0

        # Second call should also not be cached
        result2 = selector.select_model(criteria, use_cache=False)
        assert len(selector._selection_cache) == 0
        # Results should be different instances
        assert result1 is not result2

    def test_selection_stats(self):
        """Test selection statistics tracking."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        model = self.create_test_model("test-model")
        score = ModelScore(
            model_name="test-model",
            overall_score=0.8,
            dimension_scores={},
            weights=ScoringWeights(),
            context=ScoringContext(),
        )

        registry.query_models.return_value = [model]
        scorer.score_model.return_value = score
        scorer.rank_models.return_value = [(model, score)]

        selector = ModelSelector(registry, scorer)

        # Make selections with different strategies
        criteria1 = SelectionCriteria(strategy=SelectionStrategy.BEST_SCORE)
        criteria2 = SelectionCriteria(strategy=SelectionStrategy.FASTEST)
        criteria3 = SelectionCriteria(strategy=SelectionStrategy.BEST_SCORE)

        selector.select_model(criteria1)
        selector.select_model(criteria2)
        selector.select_model(criteria3)

        stats = selector.get_selection_stats()
        # Note: stats are tracked per unique criteria, not per strategy
        # Since criteria1 and criteria3 are identical, they share the same cache key
        assert (
            stats["selection_counts"]["best_score"] == 1
        )  # criteria1 and criteria3 are identical
        assert stats["selection_counts"]["fastest"] == 1

    def test_clear_cache(self):
        """Test cache clearing."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        model = self.create_test_model("test-model")
        score = ModelScore(
            model_name="test-model",
            overall_score=0.8,
            dimension_scores={},
            weights=ScoringWeights(),
            context=ScoringContext(),
        )

        registry.query_models.return_value = [model]
        scorer.score_model.return_value = score
        scorer.rank_models.return_value = [(model, score)]

        selector = ModelSelector(registry, scorer)
        criteria = SelectionCriteria(semantic_type=ModelType.FAST)

        # Add some selections to cache
        selector.select_model(criteria)
        assert len(selector._selection_cache) > 0

        # Clear cache
        selector.clear_cache()
        assert len(selector._selection_cache) == 0

    def test_no_candidates_error(self):
        """Test error handling when no candidates are found."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        registry.query_models.return_value = []

        selector = ModelSelector(registry, scorer)
        criteria = SelectionCriteria(semantic_type=ModelType.FAST)

        with pytest.raises(ValueError, match="No models found matching criteria"):
            selector.select_model(criteria)

    def test_custom_strategy_without_weights(self):
        """Test custom strategy without custom weights."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        model = self.create_test_model("test-model")
        score = ModelScore(
            model_name="test-model",
            overall_score=0.8,
            dimension_scores={},
            weights=ScoringWeights(),
            context=ScoringContext(),
        )

        registry.query_models.return_value = [model]
        scorer.score_model.return_value = score
        scorer.rank_models.return_value = [(model, score)]

        selector = ModelSelector(registry, scorer)
        criteria = SelectionCriteria(strategy=SelectionStrategy.CUSTOM)

        with pytest.raises(ValueError, match="Custom weights required"):
            selector.select_model(criteria)

    def test_custom_strategy_with_weights(self):
        """Test custom strategy with custom weights."""
        registry = self.create_mock_registry()
        scorer = self.create_mock_scorer()

        model = self.create_test_model("test-model")
        score = ModelScore(
            model_name="test-model",
            overall_score=0.8,
            dimension_scores={},
            weights=ScoringWeights(),
            context=ScoringContext(),
        )

        registry.query_models.return_value = [model]
        scorer.score_model.return_value = score
        scorer.rank_models.return_value = [(model, score)]

        selector = ModelSelector(registry, scorer)
        custom_weights = ScoringWeights(cost=0.8, performance=0.2)
        criteria = SelectionCriteria(
            strategy=SelectionStrategy.CUSTOM, custom_weights=custom_weights
        )

        result = selector.select_model(criteria)

        assert result.selected_model == model
        # Verify scorer was called with custom weights
        scorer.rank_models.assert_called_once()
        call_args = scorer.rank_models.call_args
        assert (
            call_args[0][2] == custom_weights
        )  # Third argument should be custom_weights
