# gemini_sre_agent/llm/deduplicator.py

"""
Request deduplication system for cost optimization.

This module provides request deduplication functionality to prevent duplicate
LLM calls and reduce costs while improving performance.
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .error_config import DeduplicationConfig


@dataclass
class CachedResponse:
    """Cached response for deduplication."""
    response: Any
    timestamp: float


class RequestDeduplicator:
    """Prevent duplicate requests to reduce costs and improve performance."""

    def __init__(self, config: DeduplicationConfig):
        self.config = config
        self.cache: Dict[str, CachedResponse] = {}
        self._lock = asyncio.Lock()

    async def get_cached_response(self, request: Dict[str, Any]) -> Optional[Any]:
        """Get cached response if available."""
        if not self.config.enabled:
            return None
            
        request_hash = self._generate_request_hash(request)
        async with self._lock:
            cached = self.cache.get(request_hash)
            if cached and time.time() - cached.timestamp < self.config.ttl:
                return cached.response
            return None

    async def cache_response(self, request: Dict[str, Any], response: Any) -> None:
        """Cache response for future requests."""
        if not self.config.enabled:
            return
            
        request_hash = self._generate_request_hash(request)
        async with self._lock:
            self.cache[request_hash] = CachedResponse(
                response=response,
                timestamp=time.time()
            )

    def _generate_request_hash(self, request: Dict[str, Any]) -> str:
        """Generate deterministic hash for request."""
        # Include relevant request parameters
        key_data = {
            "model": request.get("model"),
            "messages": request.get("messages"),
            "temperature": request.get("temperature"),
            "max_tokens": request.get("max_tokens"),
        }
        
        # Create deterministic string representation
        key_str = str(sorted(key_data.items()))
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    async def cleanup_expired_cache(self) -> None:
        """Remove expired cache entries."""
        current_time = time.time()
        async with self._lock:
            expired_keys = [
                key for key, cached in self.cache.items()
                if current_time - cached.timestamp >= self.config.ttl
            ]
            for key in expired_keys:
                del self.cache[key]

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            return {
                "cache_size": len(self.cache),
                "enabled": self.config.enabled,
                "ttl": self.config.ttl
            }

    async def clear_cache(self) -> None:
        """Clear all cached responses."""
        async with self._lock:
            self.cache.clear()

    async def get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate (simplified implementation)."""
        # This would need to track hits/misses in a real implementation
        async with self._lock:
            return 0.0  # Placeholder
