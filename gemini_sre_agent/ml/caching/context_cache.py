# gemini_sre_agent/ml/caching/context_cache.py

"""
Context caching system for performance optimization.

This module provides intelligent caching for repository context, issue patterns,
and other frequently accessed data to improve response times.
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """Represents a cached entry with metadata."""
    
    key: str
    value: Any
    created_at: float
    expires_at: float
    access_count: int = 0
    last_accessed: float = 0.0
    size_bytes: int = 0


class ContextCache:
    """
    Intelligent context caching system for performance optimization.
    
    Features:
    - TTL-based expiration
    - LRU eviction for memory management
    - Size-based eviction
    - Async operations
    - Automatic cleanup
    """
    
    def __init__(
        self,
        max_size_mb: int = 100,
        default_ttl_seconds: int = 3600,
        cleanup_interval_seconds: int = 300,
        max_entries: int = 1000
    ):
        """
        Initialize the context cache.
        
        Args:
            max_size_mb: Maximum cache size in megabytes
            default_ttl_seconds: Default time-to-live for cache entries
            cleanup_interval_seconds: How often to run cleanup
            max_entries: Maximum number of cache entries
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl_seconds = default_ttl_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.max_entries = max_entries
        
        self.cache: Dict[str, CacheEntry] = {}
        self.logger = logging.getLogger(__name__)
        
        # Start cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)
                await self._cleanup_expired()
                await self._cleanup_lru()
                await self._cleanup_size()
            except Exception as e:
                self.logger.error(f"Cleanup loop error: {e}")
    
    async def _cleanup_expired(self):
        """Remove expired cache entries."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time > entry.expires_at
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired entries")
    
    async def _cleanup_lru(self):
        """Remove least recently used entries if we exceed max_entries."""
        if len(self.cache) <= self.max_entries:
            return
        
        # Sort by last accessed time and remove oldest
        entries_to_remove = len(self.cache) - self.max_entries
        sorted_entries = sorted(
            self.cache.items(),
            key=lambda x: x[1].last_accessed
        )
        
        for key, _ in sorted_entries[:entries_to_remove]:
            del self.cache[key]
        
        self.logger.debug(f"Cleaned up {entries_to_remove} LRU entries")
    
    async def _cleanup_size(self):
        """Remove entries if we exceed max size."""
        current_size = sum(entry.size_bytes for entry in self.cache.values())
        
        if current_size <= self.max_size_bytes:
            return
        
        # Sort by access count and remove least accessed
        sorted_entries = sorted(
            self.cache.items(),
            key=lambda x: x[1].access_count
        )
        
        bytes_to_remove = current_size - self.max_size_bytes
        bytes_removed = 0
        
        for key, entry in sorted_entries:
            if bytes_removed >= bytes_to_remove:
                break
            
            bytes_removed += entry.size_bytes
            del self.cache[key]
        
        self.logger.debug(f"Cleaned up {bytes_removed} bytes of least accessed entries")
    
    def _generate_key(self, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        # Create a deterministic string representation
        key_data = {
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def _calculate_size(self, value: Any) -> int:
        """Calculate approximate size of a value in bytes."""
        try:
            return len(json.dumps(value).encode())
        except (TypeError, ValueError):
            # Fallback for non-serializable objects
            return 1024  # Default size
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        entry = self.cache.get(key)
        
        if entry is None:
            return None
        
        current_time = time.time()
        
        # Check if expired
        if current_time > entry.expires_at:
            del self.cache[key]
            return None
        
        # Update access metadata
        entry.access_count += 1
        entry.last_accessed = current_time
        
        return entry.value
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            current_time = time.time()
            ttl = ttl_seconds or self.default_ttl_seconds
            
            # Calculate size
            size_bytes = self._calculate_size(value)
            
            # Check if we have space
            if size_bytes > self.max_size_bytes:
                self.logger.warning(f"Value too large for cache: {size_bytes} bytes")
                return False
            
            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=current_time,
                expires_at=current_time + ttl,
                access_count=1,
                last_accessed=current_time,
                size_bytes=size_bytes
            )
            
            self.cache[key] = entry
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set cache entry: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        try:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to delete cache entry: {e}")
            return False
    
    async def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.logger.info("Cache cleared")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        current_size = sum(entry.size_bytes for entry in self.cache.values())
        
        # Calculate hit rate (simplified)
        total_accesses = sum(entry.access_count for entry in self.cache.values())
        hit_rate = total_accesses / len(self.cache) if self.cache else 0
        
        return {
            "total_entries": len(self.cache),
            "current_size_bytes": current_size,
            "max_size_bytes": self.max_size_bytes,
            "size_usage_percent": (current_size / self.max_size_bytes) * 100,
            "total_accesses": total_accesses,
            "average_hit_rate": hit_rate,
            "oldest_entry_age": min(
                current_time - entry.created_at 
                for entry in self.cache.values()
            ) if self.cache else 0,
            "newest_entry_age": max(
                current_time - entry.created_at 
                for entry in self.cache.values()
            ) if self.cache else 0
        }
    
    async def close(self):
        """Clean up resources."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        await self.clear()


class RepositoryContextCache:
    """
    Specialized cache for repository context data.
    
    This cache is optimized for repository-specific data that changes
    infrequently and can be shared across multiple requests.
    """
    
    def __init__(self, base_cache: ContextCache):
        """
        Initialize repository context cache.
        
        Args:
            base_cache: Base context cache instance
        """
        self.base_cache = base_cache
        self.logger = logging.getLogger(__name__)
        self.repo_prefix = "repo_context:"
    
    def _get_repo_key(self, repo_path: str, analysis_depth: str = "standard") -> str:
        """Generate cache key for repository context."""
        return f"{self.repo_prefix}{repo_path}:{analysis_depth}"
    
    async def get_repository_context(
        self, 
        repo_path: str, 
        analysis_depth: str = "standard"
    ) -> Optional[Any]:
        """
        Get cached repository context.
        
        Args:
            repo_path: Path to repository
            analysis_depth: Depth of analysis (basic, standard, comprehensive)
            
        Returns:
            Cached repository context or None
        """
        key = self._get_repo_key(repo_path, analysis_depth)
        return await self.base_cache.get(key)
    
    async def set_repository_context(
        self, 
        repo_path: str, 
        context: Any, 
        analysis_depth: str = "standard",
        ttl_seconds: int = 7200  # 2 hours for repo context
    ) -> bool:
        """
        Cache repository context.
        
        Args:
            repo_path: Path to repository
            context: Repository context data
            analysis_depth: Depth of analysis
            ttl_seconds: Time-to-live in seconds
            
        Returns:
            True if successful
        """
        key = self._get_repo_key(repo_path, analysis_depth)
        return await self.base_cache.set(key, context, ttl_seconds)
    
    async def invalidate_repository_context(self, repo_path: str):
        """Invalidate all cached data for a repository."""
        keys_to_delete = [
            key for key in self.base_cache.cache.keys()
            if key.startswith(f"{self.repo_prefix}{repo_path}:")
        ]
        
        for key in keys_to_delete:
            await self.base_cache.delete(key)
        
        self.logger.info(f"Invalidated {len(keys_to_delete)} cache entries for {repo_path}")


class IssuePatternCache:
    """
    Specialized cache for issue patterns and classification data.
    
    This cache stores frequently used patterns and classification results
    to speed up issue analysis.
    """
    
    def __init__(self, base_cache: ContextCache):
        """
        Initialize issue pattern cache.
        
        Args:
            base_cache: Base context cache instance
        """
        self.base_cache = base_cache
        self.logger = logging.getLogger(__name__)
        self.pattern_prefix = "issue_pattern:"
    
    def _get_pattern_key(self, pattern_type: str, pattern_data: str) -> str:
        """Generate cache key for issue patterns."""
        return f"{self.pattern_prefix}{pattern_type}:{hashlib.md5(pattern_data.encode(), usedforsecurity=False).hexdigest()}"
    
    async def get_issue_pattern(
        self, 
        pattern_type: str, 
        pattern_data: str
    ) -> Optional[Any]:
        """
        Get cached issue pattern.
        
        Args:
            pattern_type: Type of pattern (error, fix, validation)
            pattern_data: Pattern data to match
            
        Returns:
            Cached pattern or None
        """
        key = self._get_pattern_key(pattern_type, pattern_data)
        return await self.base_cache.get(key)
    
    async def set_issue_pattern(
        self, 
        pattern_type: str, 
        pattern_data: str, 
        pattern_result: Any,
        ttl_seconds: int = 86400  # 24 hours for patterns
    ) -> bool:
        """
        Cache issue pattern.
        
        Args:
            pattern_type: Type of pattern
            pattern_data: Pattern data
            pattern_result: Pattern analysis result
            ttl_seconds: Time-to-live in seconds
            
        Returns:
            True if successful
        """
        key = self._get_pattern_key(pattern_type, pattern_data)
        return await self.base_cache.set(key, pattern_result, ttl_seconds)
