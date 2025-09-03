# gemini_sre_agent/ml/caching/issue_pattern_cache.py

"""
Specialized cache for issue patterns with domain-specific optimization.

This module provides intelligent caching for issue patterns, including
pattern recognition, classification, and historical analysis data.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .context_cache import CacheEntry, ContextCache


class IssuePatternCache(ContextCache):
    """
    Specialized cache for issue patterns with domain-specific optimizations.

    Features:
    - Pattern similarity matching
    - Domain-specific TTL strategies
    - Pattern clustering and grouping
    - Historical pattern analysis
    """

    def __init__(
        self,
        max_size_mb: int = 50,
        default_ttl_seconds: int = 7200,  # 2 hours for patterns
        cleanup_interval_seconds: int = 600,  # 10 minutes
        max_entries: int = 500,
    ):
        """Initialize the issue pattern cache."""
        super().__init__(
            max_size_mb=max_size_mb,
            default_ttl_seconds=default_ttl_seconds,
            cleanup_interval_seconds=cleanup_interval_seconds,
            max_entries=max_entries,
        )
        self.logger = logging.getLogger(__name__)

        # Pattern-specific metadata
        self.pattern_domains: Dict[str, str] = {}  # pattern_key -> domain
        self.domain_patterns: Dict[str, List[str]] = {}  # domain -> pattern_keys
        self.pattern_similarity: Dict[str, List[str]] = (
            {}
        )  # pattern_key -> similar_patterns

    async def get_issue_pattern(
        self, pattern_type: str, pattern_key: str, domain: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached issue pattern with domain-specific optimization.

        Args:
            pattern_type: Type of pattern (e.g., 'issue_context', 'error_pattern')
            pattern_key: Unique identifier for the pattern
            domain: Optional domain for domain-specific caching

        Returns:
            Cached pattern data or None if not found
        """
        cache_key = self._generate_pattern_key(pattern_type, pattern_key, domain)
        cached_entry = self.cache.get(cache_key)

        if cached_entry and not self._is_expired(cached_entry):
            # Update access metadata
            cached_entry.access_count += 1
            cached_entry.last_accessed = self._get_current_time()

            # Track domain for optimization
            if domain and pattern_key not in self.pattern_domains:
                self.pattern_domains[pattern_key] = domain
                if domain not in self.domain_patterns:
                    self.domain_patterns[domain] = []
                self.domain_patterns[domain].append(pattern_key)

            self.logger.debug(f"[PATTERN-CACHE] Hit for {pattern_type}:{pattern_key}")
            return cached_entry.value

        self.logger.debug(f"[PATTERN-CACHE] Miss for {pattern_type}:{pattern_key}")
        return None

    async def set_issue_pattern(
        self,
        pattern_type: str,
        pattern_key: str,
        pattern_data: Dict[str, Any],
        domain: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        similarity_keys: Optional[List[str]] = None,
    ) -> None:
        """
        Cache issue pattern with domain-specific metadata.

        Args:
            pattern_type: Type of pattern
            pattern_key: Unique identifier for the pattern
            pattern_data: Pattern data to cache
            domain: Domain for domain-specific optimization
            ttl_seconds: Custom TTL for this pattern
            similarity_keys: List of similar pattern keys
        """
        cache_key = self._generate_pattern_key(pattern_type, pattern_key, domain)

        # Calculate TTL based on domain and pattern type
        effective_ttl = self._calculate_pattern_ttl(pattern_type, domain, ttl_seconds)

        # Create cache entry
        entry = CacheEntry(
            key=cache_key,
            value=pattern_data,
            created_at=self._get_current_time(),
            expires_at=self._get_current_time() + effective_ttl,
            size_bytes=self._calculate_size(pattern_data),
        )

        # Store in cache
        self.cache[cache_key] = entry

        # Update domain tracking
        if domain:
            self.pattern_domains[pattern_key] = domain
            if domain not in self.domain_patterns:
                self.domain_patterns[domain] = []
            self.domain_patterns[domain].append(pattern_key)

        # Update similarity tracking
        if similarity_keys:
            self.pattern_similarity[pattern_key] = similarity_keys

        self.logger.debug(
            f"[PATTERN-CACHE] Stored {pattern_type}:{pattern_key} (TTL: {effective_ttl}s)"
        )

    async def get_similar_patterns(
        self, pattern_key: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get patterns similar to the given pattern.

        Args:
            pattern_key: Key of the pattern to find similar ones for
            limit: Maximum number of similar patterns to return

        Returns:
            List of similar pattern data
        """
        similar_keys = self.pattern_similarity.get(pattern_key, [])
        similar_patterns = []

        for similar_key in similar_keys[:limit]:
            # Find the pattern in cache by searching through all entries
            for entry in self.cache.values():
                if similar_key in entry.key and not self._is_expired(entry):
                    similar_patterns.append(entry.value)
                    break

        return similar_patterns

    async def get_domain_patterns(
        self, domain: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get all patterns for a specific domain.

        Args:
            domain: Domain to get patterns for
            limit: Maximum number of patterns to return

        Returns:
            List of pattern data for the domain
        """
        domain_keys = self.domain_patterns.get(domain, [])
        domain_patterns = []

        for pattern_key in domain_keys[:limit]:
            # Find the pattern in cache
            for entry in self.cache.values():
                if pattern_key in entry.key and not self._is_expired(entry):
                    domain_patterns.append(entry.value)
                    break

        return domain_patterns

    async def invalidate_domain_patterns(self, domain: str) -> int:
        """
        Invalidate all patterns for a specific domain.

        Args:
            domain: Domain whose patterns should be invalidated

        Returns:
            Number of patterns invalidated
        """
        domain_keys = self.domain_patterns.get(domain, [])
        invalidated_count = 0

        for pattern_key in domain_keys:
            # Find and remove patterns for this domain
            keys_to_remove = [key for key in self.cache.keys() if pattern_key in key]

            for key in keys_to_remove:
                del self.cache[key]
                invalidated_count += 1

        # Clean up domain tracking
        if domain in self.domain_patterns:
            del self.domain_patterns[domain]

        self.logger.info(
            f"[PATTERN-CACHE] Invalidated {invalidated_count} patterns for domain: {domain}"
        )
        return invalidated_count

    def _generate_pattern_key(
        self, pattern_type: str, pattern_key: str, domain: Optional[str] = None
    ) -> str:
        """Generate cache key for pattern."""
        if domain:
            return f"{pattern_type}:{domain}:{pattern_key}"
        return f"{pattern_type}:{pattern_key}"

    def _calculate_pattern_ttl(
        self,
        pattern_type: str,
        domain: Optional[str] = None,
        custom_ttl: Optional[int] = None,
    ) -> int:
        """Calculate TTL for pattern based on type and domain."""
        if custom_ttl:
            return custom_ttl

        # Domain-specific TTL strategies
        if domain == "security":
            return 1800  # 30 minutes for security patterns
        elif domain == "database":
            return 3600  # 1 hour for database patterns
        elif domain == "api":
            return 7200  # 2 hours for API patterns
        elif domain == "performance":
            return 5400  # 1.5 hours for performance patterns

        # Pattern type-specific TTL
        if pattern_type == "error_pattern":
            return 7200  # 2 hours for error patterns
        elif pattern_type == "fix_pattern":
            return 10800  # 3 hours for fix patterns
        elif pattern_type == "context_pattern":
            return 3600  # 1 hour for context patterns

        return self.default_ttl_seconds

    def _calculate_size(self, value: Any) -> int:
        """Calculate approximate size of data in bytes."""
        try:
            return len(json.dumps(value, default=str).encode("utf-8"))
        except (TypeError, ValueError):
            return 1024  # Default size if serialization fails

    def _get_current_time(self) -> float:
        """Get current time for consistency."""
        import time

        return time.time()

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if cache entry is expired."""
        return self._get_current_time() > entry.expires_at

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        total_size = sum(entry.size_bytes for entry in self.cache.values())
        domain_counts = {
            domain: len(keys) for domain, keys in self.domain_patterns.items()
        }

        return {
            "total_entries": len(self.cache),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "domain_counts": domain_counts,
            "max_entries": self.max_entries,
            "max_size_bytes": self.max_size_bytes,
            "max_size_mb": self.max_size_bytes / (1024 * 1024),
        }
