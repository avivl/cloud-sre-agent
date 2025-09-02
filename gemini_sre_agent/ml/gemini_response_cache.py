"""
Intelligent cache for Gemini responses with similarity-based matching.

This module provides caching capabilities for Gemini API responses to reduce
costs and improve performance by avoiding duplicate API calls for similar
pattern contexts.
"""

import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from .gemini_api_client import GeminiResponse
from .schemas import PatternContext


class GeminiResponseCache:
    """Intelligent cache for Gemini responses with similarity-based matching."""

    def __init__(
        self,
        max_cache_size: int = 1000,
        ttl_hours: int = 24,
        similarity_threshold: float = 0.85,
    ):
        self.max_cache_size = max_cache_size
        self.ttl_seconds = ttl_hours * 3600
        self.similarity_threshold = similarity_threshold

        # Cache storage {context_hash: CacheEntry}
        self.cache = {}
        self.access_times = {}  # For LRU eviction

        self.logger = logging.getLogger(__name__)

    def _compute_context_hash(self, context: PatternContext) -> str:
        """Compute hash for pattern context to use as cache key."""

        # Create normalized context for hashing using actual PatternContext fields
        cache_key_data = {
            "primary_service": context.primary_service,
            "affected_services": sorted(context.affected_services or []),
            "time_window_start": (
                context.time_window_start.isoformat()
                if context.time_window_start
                else None
            ),
            "time_window_end": (
                context.time_window_end.isoformat() if context.time_window_end else None
            ),
            "error_patterns": (
                json.dumps(context.error_patterns, sort_keys=True)
                if context.error_patterns
                else None
            ),
            "timing_analysis": (
                json.dumps(context.timing_analysis, sort_keys=True)
                if context.timing_analysis
                else None
            ),
            "service_topology": (
                json.dumps(context.service_topology, sort_keys=True)
                if context.service_topology
                else None
            ),
        }

        # Include code context if available
        if context.code_changes_context:
            cache_key_data["has_code_changes"] = True
        if context.static_analysis_findings:
            cache_key_data["has_static_analysis"] = True
        if context.recent_commits:
            cache_key_data["has_recent_commits"] = len(context.recent_commits)

        # Create hash
        context_json = json.dumps(cache_key_data, sort_keys=True)
        return hashlib.sha256(context_json.encode()).hexdigest()[:16]

    def _compute_similarity(
        self, context1: PatternContext, context2: PatternContext
    ) -> float:
        """Compute similarity score between two contexts."""

        similarities = []

        # Service similarity (Jaccard index) - 40% weight
        services1 = set(context1.affected_services or [])
        services2 = set(context2.affected_services or [])
        if services1 or services2:
            service_similarity = len(services1 & services2) / len(services1 | services2)
            similarities.append(service_similarity * 0.4)

        # Primary service match - 20% weight
        if context1.primary_service and context2.primary_service:
            if context1.primary_service == context2.primary_service:
                similarities.append(0.2)
        elif context1.primary_service == context2.primary_service:  # Both None
            similarities.append(0.1)

        # Error patterns similarity - 20% weight
        error_similarity = self._compare_dict_fields(
            context1.error_patterns, context2.error_patterns
        )
        similarities.append(error_similarity * 0.2)

        # Timing analysis similarity - 10% weight
        timing_similarity = self._compare_dict_fields(
            context1.timing_analysis, context2.timing_analysis
        )
        similarities.append(timing_similarity * 0.1)

        # Service topology similarity - 10% weight
        topology_similarity = self._compare_dict_fields(
            context1.service_topology, context2.service_topology
        )
        similarities.append(topology_similarity * 0.1)

        return sum(similarities)

    def _compare_dict_fields(
        self, dict1: Optional[Dict[str, Any]], dict2: Optional[Dict[str, Any]]
    ) -> float:
        """Compare two dictionary fields for similarity."""
        if dict1 is None and dict2 is None:
            return 1.0
        if dict1 is None or dict2 is None:
            return 0.0

        # Convert to JSON strings and compare
        json1 = json.dumps(dict1, sort_keys=True)
        json2 = json.dumps(dict2, sort_keys=True)

        if json1 == json2:
            return 1.0

        # Simple similarity based on common keys
        keys1 = set(dict1.keys())
        keys2 = set(dict2.keys())
        if keys1 or keys2:
            return len(keys1 & keys2) / len(keys1 | keys2)

        return 0.0

    async def get_cached_response(
        self, context: PatternContext, model_name: str
    ) -> Optional[GeminiResponse]:
        """Get cached response for similar context."""

        context_hash = self._compute_context_hash(context)
        cache_key = f"{model_name}:{context_hash}"

        # Check exact match first
        if cache_key in self.cache:
            entry = self.cache[cache_key]

            # Check TTL
            if (
                datetime.now() - entry["timestamp"]
            ).total_seconds() < self.ttl_seconds:
                self.access_times[cache_key] = datetime.now()
                self.logger.debug(f"[CACHE] Exact cache hit for {cache_key}")
                return entry["response"]
            else:
                # Expired, remove
                del self.cache[cache_key]
                del self.access_times[cache_key]

        # Look for similar contexts
        best_match = None
        best_similarity = 0.0

        for cached_key, entry in self.cache.items():
            if not cached_key.startswith(f"{model_name}:"):
                continue

            # Check TTL
            if (
                datetime.now() - entry["timestamp"]
            ).total_seconds() >= self.ttl_seconds:
                continue

            # Compute similarity
            similarity = self._compute_similarity(context, entry["context"])

            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                best_match = cached_key

        if best_match:
            entry = self.cache[best_match]
            self.access_times[best_match] = datetime.now()
            self.logger.debug(
                f"[CACHE] Similarity cache hit for {best_match} "
                f"(similarity: {best_similarity:.2f})"
            )
            return entry["response"]

        return None

    async def cache_response(
        self, context: PatternContext, model_name: str, response: GeminiResponse
    ) -> None:
        """Cache a Gemini response for future use."""

        if not response.success:
            return  # Don't cache failed responses

        context_hash = self._compute_context_hash(context)
        cache_key = f"{model_name}:{context_hash}"

        # Evict if cache is full
        if len(self.cache) >= self.max_cache_size:
            await self._evict_lru_entries()

        # Store in cache
        self.cache[cache_key] = {
            "response": response,
            "context": context,
            "timestamp": datetime.now(),
            "model_name": model_name,
        }
        self.access_times[cache_key] = datetime.now()

        self.logger.debug(f"[CACHE] Cached response for {cache_key}")

    async def _evict_lru_entries(self) -> None:
        """Evict least recently used entries to make room."""

        # Remove 20% of entries (LRU)
        entries_to_remove = max(1, int(self.max_cache_size * 0.2))

        # Sort by access time
        sorted_entries = sorted(self.access_times.items(), key=lambda x: x[1])

        for cache_key, _ in sorted_entries[:entries_to_remove]:
            if cache_key in self.cache:
                del self.cache[cache_key]
            if cache_key in self.access_times:
                del self.access_times[cache_key]

        self.logger.info(f"[CACHE] Evicted {entries_to_remove} LRU entries")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""

        # Count entries by model
        model_counts = defaultdict(int)
        expired_count = 0

        current_time = datetime.now()
        for cache_key, entry in self.cache.items():
            model_name = cache_key.split(":", 1)[0]
            model_counts[model_name] += 1

            if (
                current_time - entry["timestamp"]
            ).total_seconds() >= self.ttl_seconds:
                expired_count += 1

        return {
            "total_entries": len(self.cache),
            "max_cache_size": self.max_cache_size,
            "cache_utilization": len(self.cache) / self.max_cache_size,
            "expired_entries": expired_count,
            "model_distribution": dict(model_counts),
            "oldest_entry_age_hours": self._get_oldest_entry_age_hours(),
            "ttl_hours": self.ttl_seconds / 3600,
        }

    def _get_oldest_entry_age_hours(self) -> float:
        """Get age of oldest cache entry in hours."""
        if not self.cache:
            return 0.0

        oldest_timestamp = min(entry["timestamp"] for entry in self.cache.values())
        age_seconds = (datetime.now() - oldest_timestamp).total_seconds()
        return age_seconds / 3600