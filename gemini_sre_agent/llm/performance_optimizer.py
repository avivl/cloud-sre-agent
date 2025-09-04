"""
Performance Optimization System for Multi-LLM Provider Support.

This module implements comprehensive performance optimizations to meet the
< 10ms overhead requirement, including caching, connection pooling, lazy loading,
and optimized algorithms.
"""

import asyncio
import functools
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, TypeVar

from pydantic import BaseModel

from .base import ModelType, ProviderType
from .config import LLMConfig
from .model_registry import ModelInfo, ModelRegistry
from .model_scorer import ModelScorer, ScoringContext, ScoringWeights
from .model_selector import SelectionCriteria, SelectionResult, SelectionStrategy

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class PerformanceCache:
    """High-performance caching system for frequently accessed data."""

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300.0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        async with self._lock:
            if key not in self._cache:
                return None

            value, timestamp = self._cache[key]
            if time.time() - timestamp > self.ttl_seconds:
                del self._cache[key]
                self._access_times.pop(key, None)
                return None

            self._access_times[key] = time.time()
            return value

    async def set(self, key: str, value: Any) -> None:
        """Set cached value with eviction if needed."""
        async with self._lock:
            # Evict oldest entries if cache is full
            if len(self._cache) >= self.max_size:
                await self._evict_oldest()

            self._cache[key] = (value, time.time())
            self._access_times[key] = time.time()

    async def _evict_oldest(self) -> None:
        """Evict the least recently accessed entry."""
        if not self._access_times:
            return

        oldest_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        self._cache.pop(oldest_key, None)
        self._access_times.pop(oldest_key, None)

    async def clear(self) -> None:
        """Clear all cached data."""
        async with self._lock:
            self._cache.clear()
            self._access_times.clear()


class ModelSelectionCache:
    """Optimized caching for model selection results."""

    def __init__(self):
        self._cache = PerformanceCache(max_size=500, ttl_seconds=60.0)
        self._selection_stats: Dict[str, int] = {}

    def _generate_cache_key(
        self,
        model_type: Optional[ModelType],
        provider: Optional[str],
        selection_strategy: SelectionStrategy,
        max_cost: Optional[float],
        min_performance: Optional[float],
        min_reliability: Optional[float],
    ) -> str:
        """Generate cache key for model selection."""
        key_parts = [
            f"type:{model_type.value if model_type else 'any'}",
            f"provider:{provider or 'any'}",
            f"strategy:{selection_strategy.value}",
            f"cost:{max_cost or 'any'}",
            f"perf:{min_performance or 'any'}",
            f"rel:{min_reliability or 'any'}",
        ]
        return "|".join(key_parts)

    async def get_cached_selection(
        self,
        model_type: Optional[ModelType],
        provider: Optional[str],
        selection_strategy: SelectionStrategy,
        max_cost: Optional[float],
        min_performance: Optional[float],
        min_reliability: Optional[float],
    ) -> Optional[Tuple[ModelInfo, SelectionResult]]:
        """Get cached model selection result."""
        cache_key = self._generate_cache_key(
            model_type,
            provider,
            selection_strategy,
            max_cost,
            min_performance,
            min_reliability,
        )

        result = await self._cache.get(cache_key)
        if result:
            self._selection_stats["cache_hits"] = (
                self._selection_stats.get("cache_hits", 0) + 1
            )
            logger.debug(f"Model selection cache hit for key: {cache_key}")
        else:
            self._selection_stats["cache_misses"] = (
                self._selection_stats.get("cache_misses", 0) + 1
            )

        return result

    async def cache_selection(
        self,
        model_type: Optional[ModelType],
        provider: Optional[str],
        selection_strategy: SelectionStrategy,
        max_cost: Optional[float],
        min_performance: Optional[float],
        min_reliability: Optional[float],
        result: Tuple[ModelInfo, SelectionResult],
    ) -> None:
        """Cache model selection result."""
        cache_key = self._generate_cache_key(
            model_type,
            provider,
            selection_strategy,
            max_cost,
            min_performance,
            min_reliability,
        )

        await self._cache.set(cache_key, result)
        logger.debug(f"Cached model selection for key: {cache_key}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self._selection_stats.get(
            "cache_hits", 0
        ) + self._selection_stats.get("cache_misses", 0)
        hit_rate = (
            (self._selection_stats.get("cache_hits", 0) / total_requests * 100)
            if total_requests > 0
            else 0
        )

        return {
            "cache_hits": self._selection_stats.get("cache_hits", 0),
            "cache_misses": self._selection_stats.get("cache_misses", 0),
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total_requests,
        }


class OptimizedModelRegistry:
    """Performance-optimized model registry with caching and indexing."""

    def __init__(self, base_registry: ModelRegistry):
        self.base_registry = base_registry
        self._model_cache: Dict[str, ModelInfo] = {}
        self._type_index: Dict[ModelType, List[ModelInfo]] = {}
        self._provider_index: Dict[ProviderType, List[ModelInfo]] = {}
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self) -> None:
        """Lazy initialization of indexes and cache."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            # Load all models and build indexes
            all_models = self.base_registry.get_all_models()

            for model in all_models:
                # Cache by name
                self._model_cache[model.name] = model

                # Index by semantic type
                if model.semantic_type not in self._type_index:
                    self._type_index[model.semantic_type] = []
                self._type_index[model.semantic_type].append(model)

                # Index by provider
                if model.provider not in self._provider_index:
                    self._provider_index[model.provider] = []
                self._provider_index[model.provider].append(model)

            self._initialized = True
            logger.info(
                f"OptimizedModelRegistry initialized with {len(all_models)} models"
            )

    async def get_model(self, name: str) -> Optional[ModelInfo]:
        """Get model by name with caching."""
        await self._ensure_initialized()
        return self._model_cache.get(name)

    async def get_models_by_type(self, model_type: ModelType) -> List[ModelInfo]:
        """Get models by semantic type with indexing."""
        await self._ensure_initialized()
        return self._type_index.get(model_type, []).copy()

    async def get_models_by_provider(self, provider: ProviderType) -> List[ModelInfo]:
        """Get models by provider with indexing."""
        await self._ensure_initialized()
        return self._provider_index.get(provider, []).copy()

    async def get_all_models(self) -> List[ModelInfo]:
        """Get all models with caching."""
        await self._ensure_initialized()
        return list(self._model_cache.values())


class OptimizedModelScorer:
    """Performance-optimized model scorer with caching and precomputation."""

    def __init__(self, base_scorer: ModelScorer):
        self.base_scorer = base_scorer
        self._score_cache = PerformanceCache(max_size=1000, ttl_seconds=300.0)
        self._precomputed_scores: Dict[str, Dict[str, float]] = {}

    def _generate_score_key(
        self,
        model: ModelInfo,
        context: ScoringContext,
        weights: ScoringWeights,
    ) -> str:
        """Generate cache key for model scoring."""
        key_parts = [
            f"model:{model.name}",
            f"type:{context.task_type.value if context.task_type else 'any'}",
            f"cost:{context.max_cost or 'any'}",
            f"perf:{context.min_performance or 'any'}",
            f"rel:{context.min_reliability or 'any'}",
            f"weights:{hash(str(weights))}",
        ]
        return "|".join(key_parts)

    async def score_model(
        self,
        model: ModelInfo,
        context: ScoringContext,
        weights: Optional[ScoringWeights] = None,
    ) -> Any:
        """Score model with caching."""
        weights = weights or ScoringWeights()
        cache_key = self._generate_score_key(model, context, weights)

        # Try cache first
        cached_score = await self._score_cache.get(cache_key)
        if cached_score:
            return cached_score

        # Compute score
        score = self.base_scorer.score_model(model, context, weights)

        # Cache result
        await self._score_cache.set(cache_key, score)

        return score


class ConnectionPool:
    """Connection pool for provider API connections."""

    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self._pools: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    async def get_connection(self, provider_name: str) -> Any:
        """Get connection from pool or create new one."""
        async with self._lock:
            if provider_name not in self._pools:
                self._pools[provider_name] = asyncio.Queue(maxsize=self.max_connections)

            pool = self._pools[provider_name]

            try:
                # Try to get existing connection
                return pool.get_nowait()
            except asyncio.QueueEmpty:
                # Create new connection (placeholder - would be provider-specific)
                return await self._create_connection(provider_name)

    async def return_connection(self, provider_name: str, connection: Any) -> None:
        """Return connection to pool."""
        async with self._lock:
            if provider_name in self._pools:
                pool = self._pools[provider_name]
                try:
                    pool.put_nowait(connection)
                except asyncio.QueueFull:
                    # Pool is full, discard connection
                    pass

    async def _create_connection(self, provider_name: str) -> Any:
        """Create new connection for provider."""
        # Placeholder - would be implemented per provider
        return f"connection_{provider_name}_{time.time()}"


class PerformanceOptimizer:
    """Main performance optimization orchestrator."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.model_selection_cache = ModelSelectionCache()
        self.connection_pool = ConnectionPool()
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(
        self,
        model_registry: ModelRegistry,
        model_scorer: ModelScorer,
    ) -> None:
        """Initialize optimization components."""
        async with self._lock:
            if self._initialized:
                return

            self.optimized_registry = OptimizedModelRegistry(model_registry)
            self.optimized_scorer = OptimizedModelScorer(model_scorer)

            self._initialized = True
            logger.info("PerformanceOptimizer initialized")

    async def get_optimized_model_selection(
        self,
        model_type: Optional[ModelType],
        provider: Optional[str],
        selection_strategy: SelectionStrategy,
        max_cost: Optional[float],
        min_performance: Optional[float],
        min_reliability: Optional[float],
        model_selector: Any,  # ModelSelector instance
    ) -> Tuple[ModelInfo, SelectionResult]:
        """Get optimized model selection with caching."""
        if not self._initialized:
            raise RuntimeError("PerformanceOptimizer not initialized")

        # Try cache first
        cached_result = await self.model_selection_cache.get_cached_selection(
            model_type,
            provider,
            selection_strategy,
            max_cost,
            min_performance,
            min_reliability,
        )

        if cached_result:
            return cached_result

        # Perform selection with optimized components
        start_time = time.time()

        # Use optimized registry for faster lookups
        if model_type:
            candidates = await self.optimized_registry.get_models_by_type(model_type)
        elif provider:
            provider_type = ProviderType(provider)
            candidates = await self.optimized_registry.get_models_by_provider(
                provider_type
            )
        else:
            candidates = await self.optimized_registry.get_all_models()

        # Create selection criteria
        criteria = SelectionCriteria(
            semantic_type=model_type,
            strategy=selection_strategy,
            max_cost=max_cost,
            min_performance=min_performance,
            min_reliability=min_reliability,
        )

        # Use optimized selector (would need to be modified to use optimized scorer)
        selection_result = model_selector.select_model(candidates, criteria)

        execution_time = (time.time() - start_time) * 1000
        logger.debug(f"Model selection completed in {execution_time:.2f}ms")

        # Cache result
        result = (selection_result.selected_model, selection_result)
        await self.model_selection_cache.cache_selection(
            model_type,
            provider,
            selection_strategy,
            max_cost,
            min_performance,
            min_reliability,
            result,
        )

        return result

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        return {
            "model_selection_cache": self.model_selection_cache.get_cache_stats(),
            "optimized_registry_initialized": self._initialized,
        }


# Performance decorators and utilities
def cached_model_selection(ttl_seconds: float = 60.0):
    """Decorator for caching model selection results."""

    def decorator(func):
        cache = PerformanceCache(max_size=100, ttl_seconds=ttl_seconds)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from arguments
            cache_key = (
                f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            )

            # Try cache
            cached_result = await cache.get(cache_key)
            if cached_result:
                return cached_result

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            await cache.set(cache_key, result)

            return result

        return wrapper

    return decorator


@functools.lru_cache(maxsize=128)
def get_model_type_enum(model_type_str: str) -> ModelType:
    """Cached model type enum lookup."""
    return ModelType(model_type_str)


@functools.lru_cache(maxsize=128)
def get_provider_type_enum(provider_str: str) -> ProviderType:
    """Cached provider type enum lookup."""
    return ProviderType(provider_str)


class LazyLoader:
    """Lazy loading utility for expensive operations."""

    def __init__(self, loader_func, *args, **kwargs):
        self.loader_func = loader_func
        self.args = args
        self.kwargs = kwargs
        self._value = None
        self._loaded = False
        self._lock = asyncio.Lock()

    async def get(self) -> Any:
        """Get value, loading if necessary."""
        if self._loaded:
            return self._value

        async with self._lock:
            if self._loaded:
                return self._value

            self._value = await self.loader_func(*self.args, **self.kwargs)
            self._loaded = True
            return self._value


class BatchProcessor:
    """Batch processing utility for multiple operations."""

    def __init__(self, batch_size: int = 10, max_wait_ms: float = 5.0):
        self.batch_size = batch_size
        self.max_wait_ms = max_wait_ms
        self._pending_operations: List[Tuple[Any, asyncio.Future, tuple, dict]] = []
        self._lock = asyncio.Lock()
        self._processing = False

    async def add_operation(self, operation_func, *args, **kwargs) -> Any:
        """Add operation to batch."""
        future = asyncio.Future()

        async with self._lock:
            self._pending_operations.append((operation_func, future, args, kwargs))

            # Trigger processing if batch is full
            if len(self._pending_operations) >= self.batch_size:
                asyncio.create_task(self._process_batch())

        return await future

    async def _process_batch(self) -> None:
        """Process pending operations in batch."""
        async with self._lock:
            if self._processing:
                return

            self._processing = True
            operations = self._pending_operations.copy()
            self._pending_operations.clear()

        try:
            # Process operations concurrently
            tasks = []
            for operation_func, future, args, kwargs in operations:
                task = asyncio.create_task(
                    self._execute_operation(operation_func, future, args, kwargs)
                )
                tasks.append(task)

            await asyncio.gather(*tasks)

        finally:
            async with self._lock:
                self._processing = False

                # Process any new operations that arrived during processing
                if self._pending_operations:
                    asyncio.create_task(self._process_batch())

    async def _execute_operation(self, operation_func, future, args, kwargs) -> None:
        """Execute individual operation."""
        try:
            result = await operation_func(*args, **kwargs)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
