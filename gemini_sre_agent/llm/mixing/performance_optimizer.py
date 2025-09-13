# gemini_sre_agent/llm/mixing/performance_optimizer.py

"""
Performance optimizer module for the model mixer system.

This module provides performance optimization capabilities including
caching, load balancing, resource management, and performance monitoring.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from typing import Any

from ..base import LLMResponse
from ..constants import MAX_CONCURRENT_REQUESTS

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """Strategies for performance optimization."""

    CACHING = "caching"
    LOAD_BALANCING = "load_balancing"
    RESOURCE_POOLING = "resource_pooling"
    BATCH_PROCESSING = "batch_processing"
    ADAPTIVE_TIMEOUTS = "adaptive_timeouts"
    CIRCUIT_BREAKER = "circuit_breaker"


@dataclass
class PerformanceMetrics:
    """Performance metrics for optimization."""

    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_response_time: float = 0.0
    average_response_time: float = 0.0
    min_response_time: float = float("inf")
    max_response_time: float = 0.0
    cache_hit_rate: float = 0.0
    error_rate: float = 0.0
    throughput: float = 0.0
    last_updated: float = field(default_factory=time.time)

    def update(
        self, response_time: float, success: bool, cache_hit: bool = False
    ) -> None:
        """
        Update metrics with new data.

        Args:
            response_time: Response time in seconds
            success: Whether the request was successful
            cache_hit: Whether this was a cache hit
        """
        self.request_count += 1
        self.total_response_time += response_time

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        # Update response time statistics
        self.average_response_time = self.total_response_time / self.request_count
        self.min_response_time = min(self.min_response_time, response_time)
        self.max_response_time = max(self.max_response_time, response_time)

        # Update rates
        self.error_rate = self.failure_count / self.request_count * 100
        self.cache_hit_rate = (
            self.cache_hit_rate * (self.request_count - 1) + (1 if cache_hit else 0)
        ) / self.request_count

        self.last_updated = time.time()


@dataclass
class CacheEntry:
    """Entry in the performance cache."""

    key: str
    response: LLMResponse
    created_at: float
    accessed_at: float
    access_count: int = 0
    ttl: float = 3600.0  # Time to live in seconds

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() - self.created_at > self.ttl

    def touch(self) -> None:
        """Update access information."""
        self.accessed_at = time.time()
        self.access_count += 1


class PerformanceCache:
    """Cache for performance optimization."""

    def __init__(self, max_size: int = 1000, default_ttl: float = 3600.0) -> None:
        """
        Initialize the performance cache.

        Args:
            max_size: Maximum number of cache entries
            default_ttl: Default time-to-live for cache entries
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: dict[str, CacheEntry] = {}
        self.access_order: list[str] = []

        logger.info(f"PerformanceCache initialized with max_size={max_size}")

    def get(self, key: str) -> LLMResponse | None:
        """
        Get cached response by key.

        Args:
            key: Cache key

        Returns:
            Cached response or None if not found/expired
        """
        if key not in self.cache:
            return None

        entry = self.cache[key]
        if entry.is_expired():
            del self.cache[key]
            if key in self.access_order:
                self.access_order.remove(key)
            return None

        entry.touch()
        return entry.response

    def put(self, key: str, response: LLMResponse, ttl: float | None = None) -> None:
        """
        Store response in cache.

        Args:
            key: Cache key
            response: Response to cache
            ttl: Optional time-to-live override
        """
        # Remove expired entries
        self._cleanup_expired()

        # Enforce max size
        if len(self.cache) >= self.max_size:
            self._evict_lru()

        entry = CacheEntry(
            key=key,
            response=response,
            created_at=time.time(),
            accessed_at=time.time(),
            ttl=ttl or self.default_ttl,
        )

        self.cache[key] = entry
        if key not in self.access_order:
            self.access_order.append(key)

    def _cleanup_expired(self) -> None:
        """Remove expired cache entries."""
        expired_keys = [key for key, entry in self.cache.items() if entry.is_expired()]

        for key in expired_keys:
            del self.cache[key]
            if key in self.access_order:
                self.access_order.remove(key)

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _evict_lru(self) -> None:
        """Evict least recently used cache entry."""
        if not self.access_order:
            return

        lru_key = self.access_order[0]
        del self.cache[lru_key]
        self.access_order.remove(lru_key)
        logger.info(f"Evicted LRU cache entry: {lru_key}")

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        self.access_order.clear()
        logger.info("Cleared all cache entries")

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        total_accesses = sum(entry.access_count for entry in self.cache.values())
        avg_accesses = total_accesses / len(self.cache) if self.cache else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "total_accesses": total_accesses,
            "average_accesses": avg_accesses,
            "hit_rate": 0.0,  # Would need to track hits/misses separately
        }


class LoadBalancer:
    """Load balancer for distributing requests across models."""

    def __init__(self) -> None:
        """Initialize the load balancer."""
        self.model_weights: dict[str, float] = {}
        self.model_performance: dict[str, PerformanceMetrics] = {}
        self.round_robin_index: dict[str, int] = {}

        logger.info("LoadBalancer initialized")

    def add_model(self, model_key: str, weight: float = 1.0) -> None:
        """
        Add a model to the load balancer.

        Args:
            model_key: Unique model identifier
            weight: Weight for load balancing
        """
        self.model_weights[model_key] = weight
        self.model_performance[model_key] = PerformanceMetrics()
        self.round_robin_index[model_key] = 0

        logger.info(f"Added model {model_key} with weight {weight}")

    def remove_model(self, model_key: str) -> None:
        """
        Remove a model from the load balancer.

        Args:
            model_key: Model identifier to remove
        """
        self.model_weights.pop(model_key, None)
        self.model_performance.pop(model_key, None)
        self.round_robin_index.pop(model_key, None)

        logger.info(f"Removed model {model_key}")

    def select_model(self, strategy: str = "weighted") -> str | None:
        """
        Select a model using the specified strategy.

        Args:
            strategy: Load balancing strategy

        Returns:
            Selected model key or None if no models available
        """
        if not self.model_weights:
            return None

        if strategy == "weighted":
            return self._weighted_selection()
        elif strategy == "round_robin":
            return self._round_robin_selection()
        elif strategy == "least_connections":
            return self._least_connections_selection()
        elif strategy == "performance_based":
            return self._performance_based_selection()
        else:
            return self._weighted_selection()

    def _weighted_selection(self) -> str | None:
        """Select model using weighted random selection."""
        import random

        total_weight = sum(self.model_weights.values())
        if total_weight == 0:
            return None

        random_value = random.uniform(0, total_weight)
        current_weight = 0

        for model_key, weight in self.model_weights.items():
            current_weight += weight
            if random_value <= current_weight:
                return model_key

        return None

    def _round_robin_selection(self) -> str | None:
        """Select model using round-robin selection."""
        if not self.model_weights:
            return None

        model_keys = list(self.model_weights.keys())
        if not model_keys:
            return None

        # Find the model with the lowest round-robin index
        selected_model = min(model_keys, key=lambda k: self.round_robin_index[k])
        self.round_robin_index[selected_model] += 1

        return selected_model

    def _least_connections_selection(self) -> str | None:
        """Select model with least active connections."""
        if not self.model_performance:
            return None

        # Select model with lowest request count
        return min(
            self.model_performance.keys(),
            key=lambda k: self.model_performance[k].request_count,
        )

    def _performance_based_selection(self) -> str | None:
        """Select model based on performance metrics."""
        if not self.model_performance:
            return None

        # Score models based on performance
        scored_models = []
        for model_key, metrics in self.model_performance.items():
            if metrics.request_count == 0:
                # New model, give it a chance
                score = 100.0
            else:
                # Score based on success rate and response time
                success_rate = metrics.success_count / metrics.request_count * 100
                response_time_score = max(0, 100 - metrics.average_response_time * 10)
                score = success_rate * 0.7 + response_time_score * 0.3

            scored_models.append((model_key, score))

        if not scored_models:
            return None

        # Return model with highest score
        return max(scored_models, key=lambda x: x[1])[0]

    def update_performance(
        self,
        model_key: str,
        response_time: float,
        success: bool,
        cache_hit: bool = False,
    ) -> None:
        """
        Update performance metrics for a model.

        Args:
            model_key: Model identifier
            response_time: Response time in seconds
            success: Whether the request was successful
            cache_hit: Whether this was a cache hit
        """
        if model_key in self.model_performance:
            self.model_performance[model_key].update(response_time, success, cache_hit)

    def get_model_performance(self, model_key: str) -> PerformanceMetrics | None:
        """
        Get performance metrics for a model.

        Args:
            model_key: Model identifier

        Returns:
            Performance metrics or None if not found
        """
        return self.model_performance.get(model_key)

    def get_all_performance(self) -> dict[str, PerformanceMetrics]:
        """
        Get performance metrics for all models.

        Returns:
            Dictionary containing performance metrics for all models
        """
        return self.model_performance.copy()


class PerformanceOptimizer:
    """Main performance optimizer for the model mixer system."""

    def __init__(
        self,
        cache_size: int = 1000,
        cache_ttl: float = 3600.0,
        max_concurrent_requests: int = MAX_CONCURRENT_REQUESTS,
    ):
        """
        Initialize the performance optimizer.

        Args:
            cache_size: Maximum cache size
            cache_ttl: Default cache TTL in seconds
            max_concurrent_requests: Maximum concurrent requests
        """
        self.cache = PerformanceCache(cache_size, cache_ttl)
        self.load_balancer = LoadBalancer()
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.optimization_strategies: Set[OptimizationStrategy] = set()

        # Performance tracking
        self.global_metrics = PerformanceMetrics()
        self.optimization_enabled = True

        logger.info("PerformanceOptimizer initialized")

    def enable_optimization(self, strategy: OptimizationStrategy) -> None:
        """
        Enable a specific optimization strategy.

        Args:
            strategy: Optimization strategy to enable
        """
        self.optimization_strategies.add(strategy)
        logger.info(f"Enabled optimization strategy: {strategy.value}")

    def disable_optimization(self, strategy: OptimizationStrategy) -> None:
        """
        Disable a specific optimization strategy.

        Args:
            strategy: Optimization strategy to disable
        """
        self.optimization_strategies.discard(strategy)
        logger.info(f"Disabled optimization strategy: {strategy.value}")

    def is_optimization_enabled(self, strategy: OptimizationStrategy) -> bool:
        """
        Check if an optimization strategy is enabled.

        Args:
            strategy: Optimization strategy to check

        Returns:
            True if strategy is enabled
        """
        return strategy in self.optimization_strategies

    def generate_cache_key(
        self,
        prompt: str,
        model_config: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate a cache key for a request.

        Args:
            prompt: Input prompt
            model_config: Model configuration
            context: Optional context

        Returns:
            Cache key string
        """
        import hashlib

        # Create a hash of the request parameters
        key_data = {
            "prompt": prompt,
            "model_config": model_config,
            "context": context or {},
        }

        key_string = str(sorted(key_data.items()))
        return hashlib.md5(key_string.encode()).hexdigest()

    async def get_cached_response(
        self,
        prompt: str,
        model_config: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> LLMResponse | None:
        """
        Get cached response if available.

        Args:
            prompt: Input prompt
            model_config: Model configuration
            context: Optional context

        Returns:
            Cached response or None
        """
        if not self.is_optimization_enabled(OptimizationStrategy.CACHING):
            return None

        cache_key = self.generate_cache_key(prompt, model_config, context)
        response = self.cache.get(cache_key)

        if response:
            logger.info(f"Cache hit for key: {cache_key}")
            self.global_metrics.update(0.0, True, cache_hit=True)

        return response

    def cache_response(
        self,
        prompt: str,
        model_config: dict[str, Any],
        response: LLMResponse,
        context: dict[str, Any] | None = None,
        ttl: float | None = None,
    ) -> None:
        """
        Cache a response.

        Args:
            prompt: Input prompt
            model_config: Model configuration
            response: Response to cache
            context: Optional context
            ttl: Optional TTL override
        """
        if not self.is_optimization_enabled(OptimizationStrategy.CACHING):
            return

        cache_key = self.generate_cache_key(prompt, model_config, context)
        self.cache.put(cache_key, response, ttl)
        logger.info(f"Cached response for key: {cache_key}")

    def select_optimal_model(
        self,
        available_models: list[str],
        strategy: str = "performance_based",
    ) -> str | None:
        """
        Select the optimal model for a request.

        Args:
            available_models: List of available model keys
            strategy: Load balancing strategy

        Returns:
            Selected model key or None
        """
        if not self.is_optimization_enabled(OptimizationStrategy.LOAD_BALANCING):
            return available_models[0] if available_models else None

        # Filter available models
        filtered_models = [
            model
            for model in available_models
            if model in self.load_balancer.model_weights
        ]

        if not filtered_models:
            return available_models[0] if available_models else None

        return self.load_balancer.select_model(strategy)

    def update_model_performance(
        self,
        model_key: str,
        response_time: float,
        success: bool,
        cache_hit: bool = False,
    ) -> None:
        """
        Update performance metrics for a model.

        Args:
            model_key: Model identifier
            response_time: Response time in seconds
            success: Whether the request was successful
            cache_hit: Whether this was a cache hit
        """
        self.load_balancer.update_performance(
            model_key, response_time, success, cache_hit
        )
        self.global_metrics.update(response_time, success, cache_hit)

    def get_performance_summary(self) -> dict[str, Any]:
        """
        Get performance summary.

        Returns:
            Dictionary containing performance summary
        """
        return {
            "global_metrics": {
                "request_count": self.global_metrics.request_count,
                "success_count": self.global_metrics.success_count,
                "failure_count": self.global_metrics.failure_count,
                "average_response_time": self.global_metrics.average_response_time,
                "error_rate": self.global_metrics.error_rate,
                "cache_hit_rate": self.global_metrics.cache_hit_rate,
            },
            "cache_stats": self.cache.get_stats(),
            "model_performance": {
                model_key: {
                    "request_count": metrics.request_count,
                    "success_rate": metrics.success_count
                    / max(metrics.request_count, 1)
                    * 100,
                    "average_response_time": metrics.average_response_time,
                    "error_rate": metrics.error_rate,
                }
                for model_key, metrics in self.load_balancer.get_all_performance().items()
            },
            "enabled_strategies": [
                strategy.value for strategy in self.optimization_strategies
            ],
        }

    def reset_performance_metrics(self) -> None:
        """Reset all performance metrics."""
        self.global_metrics = PerformanceMetrics()
        self.load_balancer = LoadBalancer()
        self.cache.clear()
        logger.info("Reset all performance metrics")

    def get_semaphore(self) -> asyncio.Semaphore:
        """
        Get the semaphore for limiting concurrent requests.

        Returns:
            Semaphore instance
        """
        return self.semaphore
