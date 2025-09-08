# gemini_sre_agent/llm/mixing/intelligent_cache.py

"""
Intelligent caching system for model mixing results.

This module provides smart caching capabilities for model mixing operations,
including content hashing, LRU eviction, and performance optimization.
"""

import hashlib
import logging
import time
from typing import Any, Callable, Dict

from .model_mixer import MixingStrategy, TaskType

logger = logging.getLogger(__name__)


class IntelligentCache:
    """Smart caching for model mixing results."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """Initialize intelligent cache.

        Args:
            max_size: Maximum number of cached items
            ttl_seconds: Time-to-live for cached items in seconds
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, float] = {}
        self.creation_times: Dict[str, float] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.hit_count = 0
        self.miss_count = 0

    def get_cache_key(
        self,
        prompt: str,
        task_type: TaskType,
        strategy: MixingStrategy,
        model_configs_hash: str = "",
    ) -> str:
        """Generate cache key with content hashing."""
        # Create a content hash for the prompt
        content_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        # Include task type, strategy, and model configs in the key
        key_components = [
            task_type.value,
            strategy.value,
            content_hash,
            model_configs_hash,
        ]

        return ":".join(key_components)

    async def get_or_compute(
        self, key: str, compute_func: Callable, *args, **kwargs
    ) -> Any:
        """Get from cache or compute and cache."""
        # Check if item exists and is not expired
        if key in self.cache:
            if self._is_expired(key):
                self._remove_item(key)
            else:
                self.access_times[key] = time.time()
                self.hit_count += 1
                logger.debug(f"Cache hit for key: {key[:50]}...")
                return self.cache[key]["data"]

        # Cache miss - compute the result
        self.miss_count += 1
        logger.debug(f"Cache miss for key: {key[:50]}...")

        try:
            result = await compute_func(*args, **kwargs)
            await self._cache_with_eviction(key, result)
            return result
        except Exception as e:
            logger.error(f"Error computing cached result: {e}")
            raise

    def _is_expired(self, key: str) -> bool:
        """Check if a cached item has expired."""
        if key not in self.creation_times:
            return True

        age = time.time() - self.creation_times[key]
        return age > self.ttl_seconds

    def _remove_item(self, key: str) -> None:
        """Remove an item from the cache."""
        if key in self.cache:
            del self.cache[key]
        if key in self.access_times:
            del self.access_times[key]
        if key in self.creation_times:
            del self.creation_times[key]

    async def _cache_with_eviction(self, key: str, data: Any) -> None:
        """Cache an item with LRU eviction if necessary."""
        # Remove expired items first
        self._cleanup_expired()

        # If cache is full, remove least recently used item
        if len(self.cache) >= self.max_size:
            self._evict_lru()

        # Add new item
        self.cache[key] = {"data": data, "size": self._estimate_size(data)}
        self.access_times[key] = time.time()
        self.creation_times[key] = time.time()

        logger.debug(f"Cached item with key: {key[:50]}...")

    def _cleanup_expired(self) -> None:
        """Remove all expired items from the cache."""
        expired_keys = [key for key in self.cache.keys() if self._is_expired(key)]

        for key in expired_keys:
            self._remove_item(key)

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired items")

    def _evict_lru(self) -> None:
        """Evict the least recently used item."""
        if not self.access_times:
            return

        lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        self._remove_item(lru_key)
        logger.debug(f"Evicted LRU item: {lru_key[:50]}...")

    def _estimate_size(self, data: Any) -> int:
        """Estimate the size of cached data in bytes."""
        try:
            if isinstance(data, str):
                return len(data.encode("utf-8"))
            elif isinstance(data, (list, dict)):
                return len(str(data).encode("utf-8"))
            else:
                return len(str(data).encode("utf-8"))
        except Exception:
            return 1024  # Default estimate

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total_requests if total_requests > 0 else 0

        return {
            "cache_size": len(self.cache),
            "max_size": self.max_size,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": hit_rate,
            "ttl_seconds": self.ttl_seconds,
            "total_requests": total_requests,
        }

    def clear(self) -> None:
        """Clear all cached items."""
        self.cache.clear()
        self.access_times.clear()
        self.creation_times.clear()
        self.hit_count = 0
        self.miss_count = 0
        logger.info("Cache cleared")

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all items matching a pattern."""
        import re

        pattern_re = re.compile(pattern)
        invalidated = 0

        keys_to_remove = [key for key in self.cache.keys() if pattern_re.search(key)]

        for key in keys_to_remove:
            self._remove_item(key)
            invalidated += 1

        logger.info(f"Invalidated {invalidated} items matching pattern: {pattern}")
        return invalidated

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get estimated memory usage of the cache."""
        total_size = sum(item.get("size", 0) for item in self.cache.values())

        return {
            "estimated_bytes": total_size,
            "estimated_mb": total_size / (1024 * 1024),
            "item_count": len(self.cache),
            "average_item_size": total_size / len(self.cache) if self.cache else 0,
        }
