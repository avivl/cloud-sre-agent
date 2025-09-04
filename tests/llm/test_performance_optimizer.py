"""
Unit tests for the Performance Optimization System.

Tests the performance optimization components including caching, connection pooling,
lazy loading, and batch processing to ensure they meet the < 10ms overhead requirement.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_sre_agent.llm.base import ModelType, ProviderType
from gemini_sre_agent.llm.config import LLMConfig, LLMProviderConfig
from gemini_sre_agent.llm.model_registry import ModelInfo
from gemini_sre_agent.llm.model_scorer import ModelScorer, ScoringContext, ScoringWeights
from gemini_sre_agent.llm.model_selector import SelectionResult, SelectionStrategy
from gemini_sre_agent.llm.performance_optimizer import (
    BatchProcessor,
    ConnectionPool,
    LazyLoader,
    ModelSelectionCache,
    OptimizedModelRegistry,
    OptimizedModelScorer,
    PerformanceCache,
    PerformanceOptimizer,
    cached_model_selection,
    get_model_type_enum,
    get_provider_type_enum,
)


class TestPerformanceCache:
    """Test the PerformanceCache class."""

    @pytest.fixture
    def cache(self):
        """Create a PerformanceCache instance."""
        return PerformanceCache(max_size=3, ttl_seconds=0.1)

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache):
        """Test basic cache set and get operations."""
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache):
        """Test cache expiration."""
        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"
        
        # Wait for expiration
        await asyncio.sleep(0.2)
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_cache_eviction(self, cache):
        """Test cache eviction when max size is reached."""
        # Fill cache to max size
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        # Add one more to trigger eviction
        await cache.set("key4", "value4")
        
        # key1 should be evicted (least recently accessed)
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_cache_clear(self, cache):
        """Test cache clear operation."""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        
        await cache.clear()
        
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None


class TestModelSelectionCache:
    """Test the ModelSelectionCache class."""

    @pytest.fixture
    def selection_cache(self):
        """Create a ModelSelectionCache instance."""
        return ModelSelectionCache()

    @pytest.fixture
    def mock_model_info(self):
        """Create a mock ModelInfo."""
        return ModelInfo(
            name="test-model",
            provider=ProviderType.GEMINI,
            semantic_type=ModelType.SMART,
            capabilities=["streaming"],
            cost_per_1k_tokens=0.001,
            max_tokens=4096,
            context_window=8192,
            performance_score=0.8,
            reliability_score=0.9,
            fallback_models=["fallback-model"],
        )

    @pytest.fixture
    def mock_selection_result(self, mock_model_info):
        """Create a mock SelectionResult."""
        return SelectionResult(
            selected_model=mock_model_info,
            score=0.85,
            fallback_chain=[mock_model_info],
            selection_reason="Test selection",
            metadata={},
        )

    @pytest.mark.asyncio
    async def test_cache_selection(self, selection_cache, mock_model_info, mock_selection_result):
        """Test caching and retrieving model selection results."""
        # Cache a selection result
        await selection_cache.cache_selection(
            model_type=ModelType.SMART,
            provider=None,
            selection_strategy=SelectionStrategy.BEST_SCORE,
            max_cost=None,
            min_performance=None,
            min_reliability=None,
            result=(mock_model_info, mock_selection_result),
        )
        
        # Retrieve the cached result
        cached_result = await selection_cache.get_cached_selection(
            model_type=ModelType.SMART,
            provider=None,
            selection_strategy=SelectionStrategy.BEST_SCORE,
            max_cost=None,
            min_performance=None,
            min_reliability=None,
        )
        
        assert cached_result is not None
        model_info, selection_result = cached_result
        assert model_info.name == "test-model"
        assert selection_result.score == 0.85

    @pytest.mark.asyncio
    async def test_cache_stats(self, selection_cache, mock_model_info, mock_selection_result):
        """Test cache statistics tracking."""
        # Perform some cache operations
        await selection_cache.cache_selection(
            model_type=ModelType.SMART,
            provider=None,
            selection_strategy=SelectionStrategy.BEST_SCORE,
            max_cost=None,
            min_performance=None,
            min_reliability=None,
            result=(mock_model_info, mock_selection_result),
        )
        
        # Hit the cache
        await selection_cache.get_cached_selection(
            model_type=ModelType.SMART,
            provider=None,
            selection_strategy=SelectionStrategy.BEST_SCORE,
            max_cost=None,
            min_performance=None,
            min_reliability=None,
        )
        
        # Miss the cache
        await selection_cache.get_cached_selection(
            model_type=ModelType.FAST,
            provider=None,
            selection_strategy=SelectionStrategy.BEST_SCORE,
            max_cost=None,
            min_performance=None,
            min_reliability=None,
        )
        
        stats = selection_cache.get_cache_stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1
        assert stats["hit_rate_percent"] == 50.0
        assert stats["total_requests"] == 2


class TestOptimizedModelRegistry:
    """Test the OptimizedModelRegistry class."""

    @pytest.fixture
    def mock_base_registry(self):
        """Create a mock base registry."""
        registry = MagicMock()
        model1 = ModelInfo(
            name="model1",
            provider=ProviderType.GEMINI,
            semantic_type=ModelType.SMART,
            capabilities=["streaming"],
            cost_per_1k_tokens=0.001,
            max_tokens=4096,
            context_window=8192,
            performance_score=0.8,
            reliability_score=0.9,
            fallback_models=[],
        )
        model2 = ModelInfo(
            name="model2",
            provider=ProviderType.OPENAI,
            semantic_type=ModelType.FAST,
            capabilities=["streaming"],
            cost_per_1k_tokens=0.002,
            max_tokens=2048,
            context_window=4096,
            performance_score=0.7,
            reliability_score=0.8,
            fallback_models=[],
        )
        registry.get_all_models.return_value = [model1, model2]
        return registry

    @pytest.fixture
    def optimized_registry(self, mock_base_registry):
        """Create an OptimizedModelRegistry instance."""
        return OptimizedModelRegistry(mock_base_registry)

    @pytest.mark.asyncio
    async def test_get_model(self, optimized_registry):
        """Test getting a model by name."""
        model = await optimized_registry.get_model("model1")
        assert model is not None
        assert model.name == "model1"
        assert model.provider == ProviderType.GEMINI

    @pytest.mark.asyncio
    async def test_get_models_by_type(self, optimized_registry):
        """Test getting models by semantic type."""
        smart_models = await optimized_registry.get_models_by_type(ModelType.SMART)
        assert len(smart_models) == 1
        assert smart_models[0].name == "model1"
        
        fast_models = await optimized_registry.get_models_by_type(ModelType.FAST)
        assert len(fast_models) == 1
        assert fast_models[0].name == "model2"

    @pytest.mark.asyncio
    async def test_get_models_by_provider(self, optimized_registry):
        """Test getting models by provider."""
        gemini_models = await optimized_registry.get_models_by_provider(ProviderType.GEMINI)
        assert len(gemini_models) == 1
        assert gemini_models[0].name == "model1"
        
        openai_models = await optimized_registry.get_models_by_provider(ProviderType.OPENAI)
        assert len(openai_models) == 1
        assert openai_models[0].name == "model2"

    @pytest.mark.asyncio
    async def test_get_all_models(self, optimized_registry):
        """Test getting all models."""
        all_models = await optimized_registry.get_all_models()
        assert len(all_models) == 2
        model_names = [model.name for model in all_models]
        assert "model1" in model_names
        assert "model2" in model_names


class TestOptimizedModelScorer:
    """Test the OptimizedModelScorer class."""

    @pytest.fixture
    def mock_base_scorer(self):
        """Create a mock base scorer."""
        scorer = MagicMock()
        mock_score = MagicMock()
        mock_score.performance_score = 0.8
        mock_score.cost_score = 0.7
        scorer.score_model.return_value = mock_score
        return scorer

    @pytest.fixture
    def optimized_scorer(self, mock_base_scorer):
        """Create an OptimizedModelScorer instance."""
        return OptimizedModelScorer(mock_base_scorer)

    @pytest.fixture
    def mock_model_info(self):
        """Create a mock ModelInfo."""
        return ModelInfo(
            name="test-model",
            provider=ProviderType.GEMINI,
            semantic_type=ModelType.SMART,
            capabilities=["streaming"],
            cost_per_1k_tokens=0.001,
            max_tokens=4096,
            context_window=8192,
            performance_score=0.8,
            reliability_score=0.9,
            fallback_models=[],
        )

    @pytest.fixture
    def mock_scoring_context(self):
        """Create a mock ScoringContext."""
        return ScoringContext(
            task_type=ModelType.SMART,
            required_capabilities=[],
            max_cost=None,
            min_performance=None,
            min_reliability=None,
        )

    @pytest.mark.asyncio
    async def test_score_model_caching(self, optimized_scorer, mock_model_info, mock_scoring_context):
        """Test that model scoring results are cached."""
        weights = ScoringWeights()
        
        # First call should hit the base scorer
        result1 = await optimized_scorer.score_model(mock_model_info, mock_scoring_context, weights)
        assert result1.performance_score == 0.8
        
        # Second call should use cache
        result2 = await optimized_scorer.score_model(mock_model_info, mock_scoring_context, weights)
        assert result2.performance_score == 0.8
        
        # Base scorer should only be called once
        optimized_scorer.base_scorer.score_model.assert_called_once()


class TestConnectionPool:
    """Test the ConnectionPool class."""

    @pytest.fixture
    def connection_pool(self):
        """Create a ConnectionPool instance."""
        return ConnectionPool(max_connections=2)

    @pytest.mark.asyncio
    async def test_get_connection(self, connection_pool):
        """Test getting a connection from the pool."""
        connection = await connection_pool.get_connection("test_provider")
        assert connection is not None
        assert "test_provider" in connection

    @pytest.mark.asyncio
    async def test_return_connection(self, connection_pool):
        """Test returning a connection to the pool."""
        connection = await connection_pool.get_connection("test_provider")
        await connection_pool.return_connection("test_provider", connection)
        
        # Should be able to get the same connection back
        returned_connection = await connection_pool.get_connection("test_provider")
        assert returned_connection == connection


class TestLazyLoader:
    """Test the LazyLoader class."""

    @pytest.mark.asyncio
    async def test_lazy_loading(self):
        """Test that lazy loading works correctly."""
        call_count = 0
        
        async def loader_func():
            nonlocal call_count
            call_count += 1
            return f"loaded_value_{call_count}"
        
        lazy_loader = LazyLoader(loader_func)
        
        # First call should trigger loading
        result1 = await lazy_loader.get()
        assert result1 == "loaded_value_1"
        assert call_count == 1
        
        # Second call should use cached value
        result2 = await lazy_loader.get()
        assert result2 == "loaded_value_1"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_concurrent_lazy_loading(self):
        """Test that concurrent calls to lazy loader work correctly."""
        call_count = 0
        
        async def loader_func():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate slow loading
            return f"loaded_value_{call_count}"
        
        lazy_loader = LazyLoader(loader_func)
        
        # Multiple concurrent calls should only trigger loading once
        results = await asyncio.gather(
            lazy_loader.get(),
            lazy_loader.get(),
            lazy_loader.get(),
        )
        
        assert all(result == "loaded_value_1" for result in results)
        assert call_count == 1


class TestBatchProcessor:
    """Test the BatchProcessor class."""

    @pytest.fixture
    def batch_processor(self):
        """Create a BatchProcessor instance."""
        return BatchProcessor(batch_size=3, max_wait_ms=10.0)

    @pytest.mark.asyncio
    async def test_batch_processing(self, batch_processor):
        """Test batch processing of operations."""
        results = []
        
        async def operation_func(value):
            await asyncio.sleep(0.01)  # Simulate work
            return value * 2
        
        # Add operations to batch
        tasks = []
        for i in range(5):
            task = batch_processor.add_operation(operation_func, i)
            tasks.append(task)
        
        # Wait for all operations to complete
        batch_results = await asyncio.gather(*tasks)
        
        assert len(batch_results) == 5
        assert batch_results == [0, 2, 4, 6, 8]

    @pytest.mark.asyncio
    async def test_batch_processing_with_errors(self, batch_processor):
        """Test batch processing with some operations failing."""
        async def operation_func(value):
            if value == 2:
                raise ValueError("Test error")
            return value * 2
        
        # Add operations to batch
        tasks = []
        for i in range(5):
            task = batch_processor.add_operation(operation_func, i)
            tasks.append(task)
        
        # Wait for all operations to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        assert len(results) == 5
        assert results[0] == 0
        assert results[1] == 2
        assert isinstance(results[2], ValueError)
        assert results[3] == 6
        assert results[4] == 8


class TestPerformanceOptimizer:
    """Test the PerformanceOptimizer class."""

    @pytest.fixture
    def mock_llm_config(self):
        """Create a mock LLMConfig."""
        return LLMConfig(
            default_provider=ProviderType.GEMINI,
            default_model_type=ModelType.SMART,
            enable_fallback=True,
            enable_monitoring=True,
            providers={
                ProviderType.GEMINI: LLMProviderConfig(
                    provider=ProviderType.GEMINI,
                    api_key="test_key",
                    base_url="https://api.gemini.com",
                    timeout=30,
                    max_retries=3,
                    rate_limit=100,
                ),
            },
        )

    @pytest.fixture
    def mock_model_registry(self):
        """Create a mock model registry."""
        registry = MagicMock()
        model = ModelInfo(
            name="test-model",
            provider=ProviderType.GEMINI,
            semantic_type=ModelType.SMART,
            capabilities=["streaming"],
            cost_per_1k_tokens=0.001,
            max_tokens=4096,
            context_window=8192,
            performance_score=0.8,
            reliability_score=0.9,
            fallback_models=[],
        )
        registry.get_all_models.return_value = [model]
        return registry

    @pytest.fixture
    def mock_model_scorer(self):
        """Create a mock model scorer."""
        return MagicMock()

    @pytest.fixture
    def performance_optimizer(self, mock_llm_config):
        """Create a PerformanceOptimizer instance."""
        return PerformanceOptimizer(mock_llm_config)

    @pytest.mark.asyncio
    async def test_initialization(self, performance_optimizer, mock_model_registry, mock_model_scorer):
        """Test optimizer initialization."""
        await performance_optimizer.initialize(mock_model_registry, mock_model_scorer)
        
        assert performance_optimizer._initialized
        assert performance_optimizer.optimized_registry is not None
        assert performance_optimizer.optimized_scorer is not None

    @pytest.mark.asyncio
    async def test_get_optimized_model_selection(self, performance_optimizer, mock_model_registry, mock_model_scorer):
        """Test optimized model selection."""
        # Initialize the optimizer
        await performance_optimizer.initialize(mock_model_registry, mock_model_scorer)
        
        # Mock model selector
        mock_selector = MagicMock()
        mock_result = SelectionResult(
            selected_model=mock_model_registry.get_all_models()[0],
            score=0.85,
            fallback_chain=[],
            selection_reason="Test selection",
            metadata={},
        )
        mock_selector.select_model.return_value = mock_result
        
        # Test model selection
        model_info, selection_result = await performance_optimizer.get_optimized_model_selection(
            model_type=ModelType.SMART,
            provider=None,
            selection_strategy=SelectionStrategy.BEST_SCORE,
            max_cost=None,
            min_performance=None,
            min_reliability=None,
            model_selector=mock_selector,
        )
        
        assert model_info.name == "test-model"
        assert selection_result.score == 0.85

    def test_get_performance_stats(self, performance_optimizer):
        """Test getting performance statistics."""
        stats = performance_optimizer.get_performance_stats()
        
        assert "model_selection_cache" in stats
        assert "optimized_registry_initialized" in stats


class TestCachedDecorators:
    """Test the cached decorators."""

    @pytest.mark.asyncio
    async def test_cached_model_selection_decorator(self):
        """Test the cached_model_selection decorator."""
        call_count = 0
        
        @cached_model_selection(ttl_seconds=0.1)
        async def expensive_operation(value):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return value * 2
        
        # First call should execute the function
        result1 = await expensive_operation(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call should use cache
        result2 = await expensive_operation(5)
        assert result2 == 10
        assert call_count == 1
        
        # Different arguments should execute again
        result3 = await expensive_operation(6)
        assert result3 == 12
        assert call_count == 2

    def test_get_model_type_enum_caching(self):
        """Test that model type enum lookup is cached."""
        # First call
        result1 = get_model_type_enum("smart")
        assert result1 == ModelType.SMART
        
        # Second call should use cache
        result2 = get_model_type_enum("smart")
        assert result2 == ModelType.SMART
        
        # Cache should be working (same object)
        assert result1 is result2

    def test_get_provider_type_enum_caching(self):
        """Test that provider type enum lookup is cached."""
        # First call
        result1 = get_provider_type_enum("gemini")
        assert result1 == ProviderType.GEMINI
        
        # Second call should use cache
        result2 = get_provider_type_enum("gemini")
        assert result2 == ProviderType.GEMINI
        
        # Cache should be working (same object)
        assert result1 is result2


class TestPerformanceBenchmarks:
    """Test performance benchmarks to ensure < 10ms overhead."""

    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """Test that cache operations are fast."""
        cache = PerformanceCache(max_size=100, ttl_seconds=60.0)
        
        # Test cache set performance
        start_time = time.time()
        for i in range(100):
            await cache.set(f"key_{i}", f"value_{i}")
        set_time = (time.time() - start_time) * 1000
        
        # Test cache get performance
        start_time = time.time()
        for i in range(100):
            await cache.get(f"key_{i}")
        get_time = (time.time() - start_time) * 1000
        
        # Both operations should be very fast
        assert set_time < 10.0, f"Cache set took {set_time:.2f}ms, expected < 10ms"
        assert get_time < 10.0, f"Cache get took {get_time:.2f}ms, expected < 10ms"

    @pytest.mark.asyncio
    async def test_model_selection_cache_performance(self):
        """Test that model selection caching is fast."""
        cache = ModelSelectionCache()
        
        mock_model = ModelInfo(
            name="test-model",
            provider=ProviderType.GEMINI,
            semantic_type=ModelType.SMART,
            capabilities=["streaming"],
            cost_per_1k_tokens=0.001,
            max_tokens=4096,
            context_window=8192,
            performance_score=0.8,
            reliability_score=0.9,
            fallback_models=[],
        )
        
        mock_result = SelectionResult(
            selected_model=mock_model,
            score=0.85,
            fallback_chain=[],
            selection_reason="Test",
            metadata={},
        )
        
        # Test cache set performance
        start_time = time.time()
        await cache.cache_selection(
            model_type=ModelType.SMART,
            provider=None,
            selection_strategy=SelectionStrategy.BEST_SCORE,
            max_cost=None,
            min_performance=None,
            min_reliability=None,
            result=(mock_model, mock_result),
        )
        set_time = (time.time() - start_time) * 1000
        
        # Test cache get performance
        start_time = time.time()
        await cache.get_cached_selection(
            model_type=ModelType.SMART,
            provider=None,
            selection_strategy=SelectionStrategy.BEST_SCORE,
            max_cost=None,
            min_performance=None,
            min_reliability=None,
        )
        get_time = (time.time() - start_time) * 1000
        
        # Both operations should be very fast
        assert set_time < 10.0, f"Cache set took {set_time:.2f}ms, expected < 10ms"
        assert get_time < 10.0, f"Cache get took {get_time:.2f}ms, expected < 10ms"

    @pytest.mark.asyncio
    async def test_lazy_loader_performance(self):
        """Test that lazy loading is fast."""
        async def loader_func():
            return "loaded_value"
        
        lazy_loader = LazyLoader(loader_func)
        
        # Test first load performance
        start_time = time.time()
        result = await lazy_loader.get()
        first_load_time = (time.time() - start_time) * 1000
        
        # Test cached load performance
        start_time = time.time()
        result = await lazy_loader.get()
        cached_load_time = (time.time() - start_time) * 1000
        
        assert result == "loaded_value"
        assert first_load_time < 10.0, f"First load took {first_load_time:.2f}ms, expected < 10ms"
        assert cached_load_time < 1.0, f"Cached load took {cached_load_time:.2f}ms, expected < 1ms"
