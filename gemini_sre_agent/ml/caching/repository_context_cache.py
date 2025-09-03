# gemini_sre_agent/ml/caching/repository_context_cache.py

"""
Specialized cache for repository context with analysis depth optimization.

This module provides intelligent caching for repository analysis results,
including different analysis depths and technology stack information.
"""

import logging
from typing import Any, Dict, List, Optional

from .context_cache import CacheEntry, ContextCache


class RepositoryContextCache(ContextCache):
    """
    Specialized cache for repository context with analysis depth optimization.

    Features:
    - Analysis depth-specific caching
    - Technology stack tracking
    - Repository change detection
    - Intelligent invalidation
    """

    def __init__(
        self,
        max_size_mb: int = 100,
        default_ttl_seconds: int = 3600,  # 1 hour for repo context
        cleanup_interval_seconds: int = 300,  # 5 minutes
        max_entries: int = 100,
    ):
        """Initialize the repository context cache."""
        super().__init__(
            max_size_mb=max_size_mb,
            default_ttl_seconds=default_ttl_seconds,
            cleanup_interval_seconds=cleanup_interval_seconds,
            max_entries=max_entries,
        )
        self.logger = logging.getLogger(__name__)

        # Repository-specific metadata
        self.repo_analysis_depths: Dict[str, List[str]] = (
            {}
        )  # repo_path -> analysis_depths
        self.tech_stack_cache: Dict[str, Dict[str, Any]] = {}  # repo_path -> tech_stack
        self.last_commit_cache: Dict[str, str] = {}  # repo_path -> last_commit_hash

    async def get_repository_context(
        self, repo_path: str, analysis_depth: str = "standard"
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached repository context for specific analysis depth.

        Args:
            repo_path: Path to the repository
            analysis_depth: Depth of analysis ('shallow', 'standard', 'deep')

        Returns:
            Cached repository context or None if not found
        """
        cache_key = self._generate_repo_key(repo_path, analysis_depth)
        cached_entry = self.cache.get(cache_key)

        if cached_entry and not self._is_expired(cached_entry):
            # Update access metadata
            cached_entry.access_count += 1
            cached_entry.last_accessed = self._get_current_time()

            # Track analysis depths for this repo
            if repo_path not in self.repo_analysis_depths:
                self.repo_analysis_depths[repo_path] = []
            if analysis_depth not in self.repo_analysis_depths[repo_path]:
                self.repo_analysis_depths[repo_path].append(analysis_depth)

            self.logger.debug(f"[REPO-CACHE] Hit for {repo_path}:{analysis_depth}")
            return cached_entry.value

        self.logger.debug(f"[REPO-CACHE] Miss for {repo_path}:{analysis_depth}")
        return None

    async def set_repository_context(
        self,
        repo_path: str,
        analysis_depth: str,
        context_data: Dict[str, Any],
        tech_stack: Optional[Dict[str, Any]] = None,
        last_commit: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """
        Cache repository context with metadata.

        Args:
            repo_path: Path to the repository
            analysis_depth: Depth of analysis
            context_data: Repository context data
            tech_stack: Technology stack information
            last_commit: Last commit hash for change detection
            ttl_seconds: Custom TTL for this context
        """
        cache_key = self._generate_repo_key(repo_path, analysis_depth)

        # Calculate TTL based on analysis depth
        effective_ttl = self._calculate_repo_ttl(analysis_depth, ttl_seconds)

        # Create cache entry
        entry = CacheEntry(
            key=cache_key,
            value=context_data,
            created_at=self._get_current_time(),
            expires_at=self._get_current_time() + effective_ttl,
            size_bytes=self._calculate_size(context_data),
        )

        # Store in cache
        self.cache[cache_key] = entry

        # Update analysis depth tracking
        if repo_path not in self.repo_analysis_depths:
            self.repo_analysis_depths[repo_path] = []
        if analysis_depth not in self.repo_analysis_depths[repo_path]:
            self.repo_analysis_depths[repo_path].append(analysis_depth)

        # Cache technology stack separately for quick access
        if tech_stack:
            self.tech_stack_cache[repo_path] = tech_stack

        # Cache last commit for change detection
        if last_commit:
            self.last_commit_cache[repo_path] = last_commit

        self.logger.debug(
            f"[REPO-CACHE] Stored {repo_path}:{analysis_depth} (TTL: {effective_ttl}s)"
        )

    async def get_technology_stack(self, repo_path: str) -> Optional[Dict[str, Any]]:
        """
        Get cached technology stack for repository.

        Args:
            repo_path: Path to the repository

        Returns:
            Technology stack information or None if not found
        """
        return self.tech_stack_cache.get(repo_path)

    async def get_last_commit(self, repo_path: str) -> Optional[str]:
        """
        Get cached last commit hash for repository.

        Args:
            repo_path: Path to the repository

        Returns:
            Last commit hash or None if not found
        """
        return self.last_commit_cache.get(repo_path)

    async def has_repository_changed(self, repo_path: str, current_commit: str) -> bool:
        """
        Check if repository has changed since last analysis.

        Args:
            repo_path: Path to the repository
            current_commit: Current commit hash

        Returns:
            True if repository has changed, False otherwise
        """
        cached_commit = self.last_commit_cache.get(repo_path)
        if not cached_commit:
            return True  # No cached commit, assume changed

        return cached_commit != current_commit

    async def invalidate_repository_context(
        self, repo_path: str, analysis_depth: Optional[str] = None
    ) -> int:
        """
        Invalidate repository context cache.

        Args:
            repo_path: Path to the repository
            analysis_depth: Specific analysis depth to invalidate, or None for all

        Returns:
            Number of cache entries invalidated
        """
        invalidated_count = 0

        if analysis_depth:
            # Invalidate specific analysis depth
            cache_key = self._generate_repo_key(repo_path, analysis_depth)
            if cache_key in self.cache:
                del self.cache[cache_key]
                invalidated_count += 1

                # Remove from tracking
                if repo_path in self.repo_analysis_depths:
                    if analysis_depth in self.repo_analysis_depths[repo_path]:
                        self.repo_analysis_depths[repo_path].remove(analysis_depth)
        else:
            # Invalidate all analysis depths for this repo
            if repo_path in self.repo_analysis_depths:
                for depth in self.repo_analysis_depths[repo_path]:
                    cache_key = self._generate_repo_key(repo_path, depth)
                    if cache_key in self.cache:
                        del self.cache[cache_key]
                        invalidated_count += 1

                # Clean up tracking
                del self.repo_analysis_depths[repo_path]

        # Clean up related caches
        if repo_path in self.tech_stack_cache:
            del self.tech_stack_cache[repo_path]
        if repo_path in self.last_commit_cache:
            del self.last_commit_cache[repo_path]

        self.logger.info(
            f"[REPO-CACHE] Invalidated {invalidated_count} entries for {repo_path}"
        )
        return invalidated_count

    async def get_available_analysis_depths(self, repo_path: str) -> List[str]:
        """
        Get list of available analysis depths for repository.

        Args:
            repo_path: Path to the repository

        Returns:
            List of available analysis depths
        """
        return self.repo_analysis_depths.get(repo_path, [])

    async def get_repository_summary(self, repo_path: str) -> Dict[str, Any]:
        """
        Get summary of cached repository information.

        Args:
            repo_path: Path to the repository

        Returns:
            Summary of cached repository data
        """
        available_depths = self.repo_analysis_depths.get(repo_path, [])
        tech_stack = self.tech_stack_cache.get(repo_path, {})
        last_commit = self.last_commit_cache.get(repo_path, "unknown")

        # Count cached entries for this repo
        cached_entries = 0
        total_size = 0
        for depth in available_depths:
            cache_key = self._generate_repo_key(repo_path, depth)
            entry = self.cache.get(cache_key)
            if entry and not self._is_expired(entry):
                cached_entries += 1
                total_size += entry.size_bytes

        return {
            "repo_path": repo_path,
            "available_analysis_depths": available_depths,
            "cached_entries": cached_entries,
            "total_cached_size_bytes": total_size,
            "total_cached_size_mb": total_size / (1024 * 1024),
            "technology_stack": tech_stack,
            "last_commit": last_commit,
            "cache_status": "active" if cached_entries > 0 else "empty",
        }

    def _generate_repo_key(self, repo_path: str, analysis_depth: str) -> str:
        """Generate cache key for repository context."""
        return f"repo_context:{repo_path}:{analysis_depth}"

    def _calculate_repo_ttl(
        self, analysis_depth: str, custom_ttl: Optional[int] = None
    ) -> int:
        """Calculate TTL for repository context based on analysis depth."""
        if custom_ttl:
            return custom_ttl

        # Analysis depth-specific TTL strategies
        if analysis_depth == "shallow":
            return 1800  # 30 minutes for shallow analysis
        elif analysis_depth == "standard":
            return 3600  # 1 hour for standard analysis
        elif analysis_depth == "deep":
            return 7200  # 2 hours for deep analysis
        elif analysis_depth == "comprehensive":
            return 10800  # 3 hours for comprehensive analysis

        return self.default_ttl_seconds

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
        repo_counts = {
            repo: len(depths) for repo, depths in self.repo_analysis_depths.items()
        }

        return {
            "total_entries": len(self.cache),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "repository_count": len(self.repo_analysis_depths),
            "repository_analysis_depths": repo_counts,
            "technology_stack_cache_size": len(self.tech_stack_cache),
            "last_commit_cache_size": len(self.last_commit_cache),
            "max_entries": self.max_entries,
            "max_size_bytes": self.max_size_bytes,
            "max_size_mb": self.max_size_bytes / (1024 * 1024),
        }
