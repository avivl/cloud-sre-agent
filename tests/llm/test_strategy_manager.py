"""Tests for StrategyManager and model selection strategies."""

import pytest
from datetime import time as dt_time
from unittest.mock import MagicMock, patch

from gemini_sre_agent.llm.base import ModelType, ProviderType
from gemini_sre_agent.llm.model_registry import ModelInfo, ModelCapability
from gemini_sre_agent.llm.model_scorer import ModelScore, ScoringWeights, ScoringContext, ScoringDimension
from gemini_sre_agent.llm.strategy_manager import (
    StrategyManager,
    OptimizationGoal,
    StrategyContext,
    StrategyResult,
    CostOptimizedStrategy,
    PerformanceOptimizedStrategy,
    QualityOptimizedStrategy,
    TimeBasedStrategy,
    HybridStrategy,
)


@pytest.fixture
def mock_model_info():
    """Create mock model info for testing."""
    return [
        ModelInfo(
            name="gpt-3.5-turbo",
            provider=ProviderType.OPENAI,
            semantic_type=ModelType.FAST,
            capabilities={ModelCapability.STREAMING, ModelCapability.TOOLS},
            cost_per_1k_tokens=0.002,
            max_tokens=4096,
            context_window=4096,
            performance_score=0.7,
            reliability_score=0.9,
        ),
        ModelInfo(
            name="gpt-4o",
            provider=ProviderType.OPENAI,
            semantic_type=ModelType.SMART,
            capabilities={ModelCapability.STREAMING, ModelCapability.TOOLS},
            cost_per_1k_tokens=0.005,
            max_tokens=4096,
            context_window=128000,
            performance_score=0.9,
            reliability_score=0.95,
        ),
        ModelInfo(
            name="claude-3-haiku",
            provider=ProviderType.CLAUDE,
            semantic_type=ModelType.FAST,
            capabilities={ModelCapability.STREAMING},
            cost_per_1k_tokens=0.00025,
            max_tokens=4096,
            context_window=200000,
            performance_score=0.8,
            reliability_score=0.9,
        ),
        ModelInfo(
            name="gemini-1.5-flash",
            provider=ProviderType.GEMINI,
            semantic_type=ModelType.FAST,
            capabilities={ModelCapability.STREAMING, ModelCapability.VISION},
            cost_per_1k_tokens=0.00075,
            max_tokens=8192,
            context_window=1000000,
            performance_score=0.8,
            reliability_score=0.8,
        ),
    ]


@pytest.fixture
def mock_model_scorer():
    """Create mock model scorer."""
    scorer = MagicMock()
    scorer.score_model.return_value = ModelScore(
        model_name="test-model",
        overall_score=0.8,
        dimension_scores={
            ScoringDimension.COST: 0.8,
            ScoringDimension.PERFORMANCE: 0.7,
            ScoringDimension.RELIABILITY: 0.9,
            ScoringDimension.SPEED: 0.6,
            ScoringDimension.QUALITY: 0.8,
            ScoringDimension.AVAILABILITY: 1.0,
        },
        weights=ScoringWeights(),
        context=ScoringContext(),
    )
    return scorer


@pytest.fixture
def strategy_manager(mock_model_scorer):
    """Create StrategyManager instance for testing."""
    return StrategyManager(mock_model_scorer)


@pytest.fixture
def strategy_context():
    """Create StrategyContext for testing."""
    return StrategyContext(
        task_type=ModelType.FAST,
        max_cost=0.01,
        min_performance=0.5,
        min_quality=0.6,
        provider_preference=[ProviderType.OPENAI, ProviderType.CLAUDE],
    )


class TestStrategyManager:
    """Test StrategyManager functionality."""

    def test_initialization(self, strategy_manager):
        """Test StrategyManager initialization."""
        assert len(strategy_manager._strategies) == 5
        assert OptimizationGoal.COST in strategy_manager._strategies
        assert OptimizationGoal.PERFORMANCE in strategy_manager._strategies
        assert OptimizationGoal.QUALITY in strategy_manager._strategies
        assert OptimizationGoal.TIME_BASED in strategy_manager._strategies
        assert OptimizationGoal.HYBRID in strategy_manager._strategies

    def test_select_model_cost_optimized(self, strategy_manager, mock_model_info, strategy_context):
        """Test cost-optimized model selection."""
        result = strategy_manager.select_model(
            mock_model_info, OptimizationGoal.COST, strategy_context
        )
        
        assert isinstance(result, StrategyResult)
        assert result.strategy_used == "cost_optimized"
        assert result.selected_model.name == "claude-3-haiku"  # Cheapest model
        assert result.execution_time_ms < 10  # Should be fast
        assert len(result.fallback_models) <= 3
        assert "cheapest" in result.reasoning.lower()

    def test_select_model_performance_optimized(self, strategy_manager, mock_model_info, strategy_context):
        """Test performance-optimized model selection."""
        result = strategy_manager.select_model(
            mock_model_info, OptimizationGoal.PERFORMANCE, strategy_context
        )
        
        assert isinstance(result, StrategyResult)
        assert result.strategy_used == "performance_optimized"
        assert result.execution_time_ms < 10
        assert len(result.fallback_models) <= 3
        assert "performance" in result.reasoning.lower()

    def test_select_model_quality_optimized(self, strategy_manager, mock_model_info, strategy_context):
        """Test quality-optimized model selection."""
        result = strategy_manager.select_model(
            mock_model_info, OptimizationGoal.QUALITY, strategy_context
        )
        
        assert isinstance(result, StrategyResult)
        assert result.strategy_used == "quality_optimized"
        assert result.execution_time_ms < 10
        assert len(result.fallback_models) <= 3
        assert "quality" in result.reasoning.lower()

    @patch('gemini_sre_agent.llm.strategy_manager.datetime')
    def test_select_model_time_based_business_hours(self, mock_datetime, strategy_manager, mock_model_info, strategy_context):
        """Test time-based model selection during business hours."""
        # Mock business hours
        mock_datetime.now.return_value.time.return_value = dt_time(10, 0)  # 10 AM
        
        result = strategy_manager.select_model(
            mock_model_info, OptimizationGoal.TIME_BASED, strategy_context
        )
        
        assert isinstance(result, StrategyResult)
        assert result.strategy_used == "time_based"
        assert result.execution_time_ms < 10
        assert result.metadata["is_business_hours"] is True
        assert "business hours" in result.reasoning

    @patch('gemini_sre_agent.llm.strategy_manager.datetime')
    def test_select_model_time_based_off_hours(self, mock_datetime, strategy_manager, mock_model_info, strategy_context):
        """Test time-based model selection during off hours."""
        # Mock off hours
        mock_datetime.now.return_value.time.return_value = dt_time(20, 0)  # 8 PM
        
        result = strategy_manager.select_model(
            mock_model_info, OptimizationGoal.TIME_BASED, strategy_context
        )
        
        assert isinstance(result, StrategyResult)
        assert result.strategy_used == "time_based"
        assert result.execution_time_ms < 10
        assert result.metadata["is_business_hours"] is False
        assert "off hours" in result.reasoning

    def test_select_model_hybrid(self, strategy_manager, mock_model_info, strategy_context):
        """Test hybrid model selection."""
        result = strategy_manager.select_model(
            mock_model_info, OptimizationGoal.HYBRID, strategy_context
        )
        
        assert isinstance(result, StrategyResult)
        assert result.strategy_used == "hybrid"
        assert result.execution_time_ms < 10
        assert len(result.fallback_models) <= 3
        assert "hybrid" in result.reasoning.lower()

    def test_select_model_with_custom_weights(self, strategy_manager, mock_model_info):
        """Test model selection with custom weights."""
        context = StrategyContext(
            task_type=ModelType.FAST,
            custom_weights=ScoringWeights(
                cost=0.5,
                performance=0.3,
                reliability=0.2,
                speed=0.0,
                quality=0.0,
                availability=0.0,
            )
        )
        
        result = strategy_manager.select_model(
            mock_model_info, OptimizationGoal.HYBRID, context
        )
        
        assert isinstance(result, StrategyResult)
        assert result.metadata["weights_used"]["cost"] == 0.5

    def test_add_strategy(self, strategy_manager):
        """Test adding a custom strategy."""
        custom_strategy = MagicMock()
        custom_strategy.name = "custom_test"
        
        strategy_manager.add_strategy(OptimizationGoal.COST, custom_strategy)
        
        assert strategy_manager._strategies[OptimizationGoal.COST] == custom_strategy

    def test_remove_strategy(self, strategy_manager):
        """Test removing a strategy."""
        strategy_manager.remove_strategy(OptimizationGoal.COST)
        
        assert OptimizationGoal.COST not in strategy_manager._strategies

    def test_get_available_strategies(self, strategy_manager):
        """Test getting available strategies."""
        strategies = strategy_manager.get_available_strategies()
        
        assert len(strategies) == 5
        assert OptimizationGoal.COST in strategies
        assert OptimizationGoal.PERFORMANCE in strategies

    def test_get_strategy_performance(self, strategy_manager):
        """Test getting strategy performance metrics."""
        performance = strategy_manager.get_strategy_performance(OptimizationGoal.COST)
        
        assert "total_selections" in performance
        assert "successful_selections" in performance
        assert "average_score" in performance
        assert "average_latency" in performance

    def test_get_all_performance_metrics(self, strategy_manager):
        """Test getting all performance metrics."""
        all_metrics = strategy_manager.get_all_performance_metrics()
        
        assert len(all_metrics) == 5
        for goal in OptimizationGoal:
            assert goal.value in all_metrics

    def test_get_usage_statistics(self, strategy_manager):
        """Test getting usage statistics."""
        stats = strategy_manager.get_usage_statistics()
        
        assert len(stats) == 5
        for goal in OptimizationGoal:
            assert goal.value in stats
            assert stats[goal.value] == 0  # Initially zero

    def test_update_strategy_performance(self, strategy_manager):
        """Test updating strategy performance."""
        strategy_manager.update_strategy_performance(OptimizationGoal.COST, True, 100.0)
        
        # Should not raise an exception
        assert True

    def test_reset_statistics(self, strategy_manager):
        """Test resetting statistics."""
        # Use a strategy to generate some stats
        mock_models = [MagicMock()]
        context = StrategyContext()
        
        with patch.object(strategy_manager._strategies[OptimizationGoal.COST], 'select_model') as mock_select:
            mock_select.return_value = MagicMock()
            strategy_manager.select_model(mock_models, OptimizationGoal.COST, context)
        
        # Reset statistics
        strategy_manager.reset_statistics()
        
        # Verify reset
        stats = strategy_manager.get_usage_statistics()
        assert stats[OptimizationGoal.COST.value] == 0

    def test_unknown_optimization_goal(self, strategy_manager, mock_model_info, strategy_context):
        """Test handling of unknown optimization goal."""
        with pytest.raises(ValueError, match="Unknown optimization goal"):
            strategy_manager.select_model(mock_model_info, "unknown_goal", strategy_context)

    def test_no_candidates_meet_constraints(self, strategy_manager, strategy_context):
        """Test handling when no candidates meet constraints."""
        # Create models that don't meet constraints
        expensive_model = MagicMock()
        expensive_model.cost_per_1k_tokens = 0.1  # Too expensive
        expensive_model.performance_score = 0.3   # Too low performance
        expensive_model.quality_score = 0.3       # Too low quality
        expensive_model.capabilities = []
        expensive_model.provider = ProviderType.GEMINI
        
        with pytest.raises(ValueError, match="No models meet the specified constraints"):
            strategy_manager.select_model([expensive_model], OptimizationGoal.COST, strategy_context)


class TestCostOptimizedStrategy:
    """Test CostOptimizedStrategy functionality."""

    def test_initialization(self, mock_model_scorer):
        """Test CostOptimizedStrategy initialization."""
        strategy = CostOptimizedStrategy(mock_model_scorer)
        
        assert strategy.name == "cost_optimized"
        assert strategy.model_scorer == mock_model_scorer

    def test_select_model(self, mock_model_scorer, mock_model_info, strategy_context):
        """Test cost-optimized model selection."""
        strategy = CostOptimizedStrategy(mock_model_scorer)
        
        result = strategy.select_model(mock_model_info, strategy_context)
        
        assert isinstance(result, StrategyResult)
        assert result.strategy_used == "cost_optimized"
        assert result.selected_model.name == "claude-3-haiku"  # Cheapest
        assert result.execution_time_ms < 10
        assert "cheapest" in result.reasoning.lower()

    def test_performance_update(self, mock_model_scorer):
        """Test performance metrics update."""
        strategy = CostOptimizedStrategy(mock_model_scorer)
        
        # Update performance
        strategy.update_performance(MagicMock(), 0.8, True, 50.0)
        
        metrics = strategy.get_performance_metrics()
        assert metrics["total_selections"] == 1
        assert metrics["successful_selections"] == 1
        assert metrics["average_score"] == 0.8
        assert metrics["average_latency"] == 50.0


class TestPerformanceOptimizedStrategy:
    """Test PerformanceOptimizedStrategy functionality."""

    def test_initialization(self, mock_model_scorer):
        """Test PerformanceOptimizedStrategy initialization."""
        strategy = PerformanceOptimizedStrategy(mock_model_scorer)
        
        assert strategy.name == "performance_optimized"
        assert strategy.model_scorer == mock_model_scorer

    def test_select_model(self, mock_model_scorer, mock_model_info, strategy_context):
        """Test performance-optimized model selection."""
        strategy = PerformanceOptimizedStrategy(mock_model_scorer)
        
        result = strategy.select_model(mock_model_info, strategy_context)
        
        assert isinstance(result, StrategyResult)
        assert result.strategy_used == "performance_optimized"
        assert result.execution_time_ms < 10
        assert "performance" in result.reasoning.lower()


class TestQualityOptimizedStrategy:
    """Test QualityOptimizedStrategy functionality."""

    def test_initialization(self, mock_model_scorer):
        """Test QualityOptimizedStrategy initialization."""
        strategy = QualityOptimizedStrategy(mock_model_scorer)
        
        assert strategy.name == "quality_optimized"
        assert strategy.model_scorer == mock_model_scorer

    def test_select_model(self, mock_model_scorer, mock_model_info, strategy_context):
        """Test quality-optimized model selection."""
        strategy = QualityOptimizedStrategy(mock_model_scorer)
        
        result = strategy.select_model(mock_model_info, strategy_context)
        
        assert isinstance(result, StrategyResult)
        assert result.strategy_used == "quality_optimized"
        assert result.execution_time_ms < 10
        assert "quality" in result.reasoning.lower()


class TestTimeBasedStrategy:
    """Test TimeBasedStrategy functionality."""

    def test_initialization(self, mock_model_scorer):
        """Test TimeBasedStrategy initialization."""
        strategy = TimeBasedStrategy(mock_model_scorer)
        
        assert strategy.name == "time_based"
        assert strategy.model_scorer == mock_model_scorer

    @patch('gemini_sre_agent.llm.strategy_manager.datetime')
    def test_is_business_hours(self, mock_datetime, mock_model_scorer):
        """Test business hours detection."""
        strategy = TimeBasedStrategy(mock_model_scorer)
        
        # Test business hours
        mock_datetime.now.return_value.time.return_value = dt_time(10, 0)
        assert strategy._is_business_hours() is True
        
        # Test off hours
        mock_datetime.now.return_value.time.return_value = dt_time(20, 0)
        assert strategy._is_business_hours() is False

    @patch('gemini_sre_agent.llm.strategy_manager.datetime')
    def test_select_model_business_hours(self, mock_datetime, mock_model_scorer, mock_model_info, strategy_context):
        """Test time-based selection during business hours."""
        strategy = TimeBasedStrategy(mock_model_scorer)
        mock_datetime.now.return_value.time.return_value = dt_time(10, 0)
        
        result = strategy.select_model(mock_model_info, strategy_context)
        
        assert isinstance(result, StrategyResult)
        assert result.strategy_used == "time_based"
        assert result.metadata["is_business_hours"] is True
        assert "business hours" in result.reasoning


class TestHybridStrategy:
    """Test HybridStrategy functionality."""

    def test_initialization(self, mock_model_scorer):
        """Test HybridStrategy initialization."""
        strategy = HybridStrategy(mock_model_scorer)
        
        assert strategy.name == "hybrid"
        assert strategy.model_scorer == mock_model_scorer

    def test_select_model(self, mock_model_scorer, mock_model_info, strategy_context):
        """Test hybrid model selection."""
        strategy = HybridStrategy(mock_model_scorer)
        
        result = strategy.select_model(mock_model_info, strategy_context)
        
        assert isinstance(result, StrategyResult)
        assert result.strategy_used == "hybrid"
        assert result.execution_time_ms < 10
        assert "hybrid" in result.reasoning.lower()

    def test_learning_weights_update(self, mock_model_scorer):
        """Test learning weights update."""
        strategy = HybridStrategy(mock_model_scorer)
        
        # Update weights based on successful fast execution
        strategy._update_learning_weights(True, 500.0)
        
        # Should increase performance and speed weights
        assert strategy._learning_weights.performance > 0.0
        assert strategy._learning_weights.speed > 0.0

    def test_select_model_with_custom_weights(self, mock_model_scorer, mock_model_info):
        """Test hybrid selection with custom weights."""
        strategy = HybridStrategy(mock_model_scorer)
        context = StrategyContext(
            custom_weights=ScoringWeights(
                cost=0.6,
                performance=0.2,
                reliability=0.2,
                speed=0.0,
                quality=0.0,
                availability=0.0,
            )
        )
        
        result = strategy.select_model(mock_model_info, context)
        
        assert isinstance(result, StrategyResult)
        assert result.metadata["weights_used"]["cost"] == 0.6


class TestStrategyContext:
    """Test StrategyContext functionality."""

    def test_initialization_defaults(self):
        """Test StrategyContext initialization with defaults."""
        context = StrategyContext()
        
        assert context.task_type is None
        assert context.max_cost is None
        assert context.min_performance is None
        assert context.min_quality is None
        assert context.max_latency is None
        assert context.business_hours_only is False
        assert context.provider_preference is None
        assert context.custom_weights is None
        assert context.metadata == {}

    def test_initialization_with_values(self):
        """Test StrategyContext initialization with values."""
        weights = ScoringWeights()
        context = StrategyContext(
            task_type=ModelType.FAST,
            max_cost=0.01,
            min_performance=0.8,
            min_quality=0.9,
            max_latency=1000.0,
            business_hours_only=True,
            provider_preference=[ProviderType.OPENAI],
            custom_weights=weights,
            metadata={"test": "value"},
        )
        
        assert context.task_type == ModelType.FAST
        assert context.max_cost == 0.01
        assert context.min_performance == 0.8
        assert context.min_quality == 0.9
        assert context.max_latency == 1000.0
        assert context.business_hours_only is True
        assert context.provider_preference == [ProviderType.OPENAI]
        assert context.custom_weights == weights
        assert context.metadata == {"test": "value"}


class TestStrategyResult:
    """Test StrategyResult functionality."""

    def test_initialization(self, mock_model_info):
        """Test StrategyResult initialization."""
        model = mock_model_info[0]
        score = ModelScore(
            model_name="test-model",
            overall_score=0.8,
            dimension_scores={
                ScoringDimension.COST: 0.8,
                ScoringDimension.PERFORMANCE: 0.7,
                ScoringDimension.RELIABILITY: 0.9,
                ScoringDimension.SPEED: 0.6,
                ScoringDimension.QUALITY: 0.8,
                ScoringDimension.AVAILABILITY: 1.0,
            },
            weights=ScoringWeights(),
            context=ScoringContext(),
        )
        
        result = StrategyResult(
            selected_model=model,
            score=score,
            strategy_used="test_strategy",
            execution_time_ms=50.0,
            fallback_models=[mock_model_info[1]],
            reasoning="Test reasoning",
            metadata={"test": "value"},
        )
        
        assert result.selected_model == model
        assert result.score == score
        assert result.strategy_used == "test_strategy"
        assert result.execution_time_ms == 50.0
        assert result.fallback_models == [mock_model_info[1]]
        assert result.reasoning == "Test reasoning"
        assert result.metadata == {"test": "value"}

    def test_initialization_defaults(self, mock_model_info):
        """Test StrategyResult initialization with defaults."""
        model = mock_model_info[0]
        score = ModelScore(
            model_name="test-model",
            overall_score=0.8,
            dimension_scores={
                ScoringDimension.COST: 0.8,
                ScoringDimension.PERFORMANCE: 0.7,
                ScoringDimension.RELIABILITY: 0.9,
                ScoringDimension.SPEED: 0.6,
                ScoringDimension.QUALITY: 0.8,
                ScoringDimension.AVAILABILITY: 1.0,
            },
            weights=ScoringWeights(),
            context=ScoringContext(),
        )
        
        result = StrategyResult(
            selected_model=model,
            score=score,
            strategy_used="test_strategy",
            execution_time_ms=50.0,
        )
        
        assert result.selected_model == model
        assert result.score == score
        assert result.strategy_used == "test_strategy"
        assert result.execution_time_ms == 50.0
        assert result.fallback_models == []
        assert result.reasoning == ""
        assert result.metadata == {}


class TestOptimizationGoal:
    """Test OptimizationGoal enum."""

    def test_enum_values(self):
        """Test OptimizationGoal enum values."""
        assert OptimizationGoal.COST == "cost"
        assert OptimizationGoal.PERFORMANCE == "performance"
        assert OptimizationGoal.QUALITY == "quality"
        assert OptimizationGoal.TIME_BASED == "time_based"
        assert OptimizationGoal.HYBRID == "hybrid"

    def test_enum_membership(self):
        """Test OptimizationGoal enum membership."""
        assert "cost" in [goal.value for goal in OptimizationGoal]
        assert "performance" in [goal.value for goal in OptimizationGoal]
        assert "quality" in [goal.value for goal in OptimizationGoal]
        assert "time_based" in [goal.value for goal in OptimizationGoal]
        assert "hybrid" in [goal.value for goal in OptimizationGoal]
