"""
Comprehensive unit tests for GeminiResponseCache.

Tests the intelligent caching system with similarity-based matching
and performance optimization features.
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_sre_agent.ml.gemini_api_client import GeminiResponse
from gemini_sre_agent.ml.gemini_response_cache import GeminiResponseCache
from gemini_sre_agent.ml.schemas import PatternContext


class TestGeminiResponseCacheInit:
    """Test GeminiResponseCache initialization."""

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        cache = GeminiResponseCache()

        assert cache.max_cache_size == 1000
        assert cache.ttl_seconds == 24 * 3600  # 24 hours
        assert cache.similarity_threshold == 0.85
        assert cache.cache == {}
        assert cache.access_times == {}

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        cache = GeminiResponseCache(
            max_cache_size=500, ttl_hours=12, similarity_threshold=0.7
        )

        assert cache.max_cache_size == 500
        assert cache.ttl_seconds == 12 * 3600  # 12 hours
        assert cache.similarity_threshold == 0.7


class TestGeminiResponseCacheHashing:
    """Test context hashing functionality."""

    @pytest.fixture
    def sample_context(self):
        """Create sample PatternContext for testing."""
        return PatternContext(
            primary_service="api-service",
            affected_services=["api-service", "db-service"],
            time_window_start=datetime(2024, 1, 1, 10, 0, 0),
            time_window_end=datetime(2024, 1, 1, 11, 0, 0),
            error_patterns={"rate": 0.05, "types": ["timeout", "connection"]},
            timing_analysis={"burst_detected": True, "pattern": "exponential"},
            service_topology={"dependencies": ["db", "cache"]},
            code_changes_context="Recent deployment",
            static_analysis_findings={"complexity": 7.5},
            recent_commits=["abc123", "def456"],
        )

    def test_compute_context_hash(self, sample_context):
        """Test context hash computation."""
        cache = GeminiResponseCache()
        hash1 = cache._compute_context_hash(sample_context)

        # Hash should be consistent
        hash2 = cache._compute_context_hash(sample_context)
        assert hash1 == hash2
        assert len(hash1) == 16  # SHA256 truncated to 16 chars

    def test_compute_context_hash_different_contexts(self):
        """Test that different contexts produce different hashes."""
        cache = GeminiResponseCache()

        context1 = PatternContext(
            primary_service="service-a", affected_services=["service-a"]
        )
        context2 = PatternContext(
            primary_service="service-b", affected_services=["service-b"]
        )

        hash1 = cache._compute_context_hash(context1)
        hash2 = cache._compute_context_hash(context2)
        assert hash1 != hash2

    def test_compute_context_hash_none_values(self):
        """Test hash computation with None values."""
        cache = GeminiResponseCache()
        context = PatternContext()  # All fields None/empty

        hash_result = cache._compute_context_hash(context)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 16


class TestGeminiResponseCacheSimilarity:
    """Test similarity computation functionality."""

    def test_compute_similarity_identical_contexts(self):
        """Test similarity computation with identical contexts."""
        cache = GeminiResponseCache()

        context = PatternContext(
            primary_service="api-service",
            affected_services=["api-service", "db-service"],
            error_patterns={"rate": 0.05},
        )

        similarity = cache._compute_similarity(context, context)
        assert similarity == 1.0

    def test_compute_similarity_different_contexts(self):
        """Test similarity computation with different contexts."""
        cache = GeminiResponseCache()

        context1 = PatternContext(
            primary_service="api-service",
            affected_services=["api-service", "db-service"],
            error_patterns={"rate": 0.05},
        )
        context2 = PatternContext(
            primary_service="web-service",
            affected_services=["web-service"],
            error_patterns={"rate": 0.1},
        )

        similarity = cache._compute_similarity(context1, context2)
        assert 0.0 <= similarity <= 1.0
        assert similarity < 1.0  # Should be different

    def test_compute_similarity_partial_overlap(self):
        """Test similarity computation with partial service overlap."""
        cache = GeminiResponseCache()

        context1 = PatternContext(
            primary_service="api-service",
            affected_services=["api-service", "db-service", "cache-service"],
        )
        context2 = PatternContext(
            primary_service="api-service",
            affected_services=["api-service", "queue-service"],
        )

        similarity = cache._compute_similarity(context1, context2)
        assert 0.0 < similarity < 1.0  # Partial similarity

    def test_compare_dict_fields_identical(self):
        """Test dictionary field comparison with identical dicts."""
        cache = GeminiResponseCache()

        dict1 = {"key1": "value1", "key2": 2}
        dict2 = {"key1": "value1", "key2": 2}

        similarity = cache._compare_dict_fields(dict1, dict2)
        assert similarity == 1.0

    def test_compare_dict_fields_different(self):
        """Test dictionary field comparison with different dicts."""
        cache = GeminiResponseCache()

        dict1 = {"key1": "value1", "key2": 2}
        dict2 = {"key3": "value3", "key4": 4}

        similarity = cache._compare_dict_fields(dict1, dict2)
        assert similarity == 0.0

    def test_compare_dict_fields_none_values(self):
        """Test dictionary field comparison with None values."""
        cache = GeminiResponseCache()

        assert cache._compare_dict_fields(None, None) == 1.0
        assert cache._compare_dict_fields({"key": "value"}, None) == 0.0
        assert cache._compare_dict_fields(None, {"key": "value"}) == 0.0


class TestGeminiResponseCacheCaching:
    """Test caching and retrieval functionality."""

    @pytest.fixture
    def cache(self):
        """Create cache instance for testing."""
        return GeminiResponseCache(max_cache_size=10, ttl_hours=1)

    @pytest.fixture
    def sample_context(self):
        """Create sample context for testing."""
        return PatternContext(
            primary_service="api-service",
            affected_services=["api-service", "db-service"],
            error_patterns={"rate": 0.05},
        )

    @pytest.fixture
    def sample_response(self):
        """Create sample response for testing."""
        return GeminiResponse(
            success=True,
            content="Test response",
            parsed_json={"pattern": "test"},
            model_used="gemini-1.5-pro",
            tokens_used=100,
            latency_ms=250.0,
        )

    @pytest.mark.asyncio
    async def test_cache_response_success(self, cache, sample_context, sample_response):
        """Test caching a successful response."""
        await cache.cache_response(sample_context, "gemini-1.5-pro", sample_response)

        assert len(cache.cache) == 1
        assert len(cache.access_times) == 1

    @pytest.mark.asyncio
    async def test_cache_response_failure_not_cached(self, cache, sample_context):
        """Test that failed responses are not cached."""
        failed_response = GeminiResponse(
            success=False, error_message="API error", content=""
        )

        await cache.cache_response(sample_context, "gemini-1.5-pro", failed_response)

        assert len(cache.cache) == 0

    @pytest.mark.asyncio
    async def test_get_cached_response_exact_match(
        self, cache, sample_context, sample_response
    ):
        """Test retrieving response with exact context match."""
        # Cache the response
        await cache.cache_response(sample_context, "gemini-1.5-pro", sample_response)

        # Retrieve it
        cached_response = await cache.get_cached_response(
            sample_context, "gemini-1.5-pro"
        )

        assert cached_response is not None
        assert cached_response.content == sample_response.content

    @pytest.mark.asyncio
    async def test_get_cached_response_no_match(self, cache, sample_response):
        """Test retrieving response with no matching context."""
        context1 = PatternContext(primary_service="service-a")
        context2 = PatternContext(primary_service="service-b")

        # Cache with context1
        await cache.cache_response(context1, "gemini-1.5-pro", sample_response)

        # Try to retrieve with context2
        cached_response = await cache.get_cached_response(context2, "gemini-1.5-pro")

        assert cached_response is None

    @pytest.mark.asyncio
    async def test_get_cached_response_different_model(
        self, cache, sample_context, sample_response
    ):
        """Test that different models don't match."""
        # Cache with one model
        await cache.cache_response(sample_context, "gemini-1.5-pro", sample_response)

        # Try to retrieve with different model
        cached_response = await cache.get_cached_response(
            sample_context, "gemini-1.5-flash"
        )

        assert cached_response is None

    @pytest.mark.asyncio
    async def test_get_cached_response_similarity_match(self, cache, sample_response):
        """Test retrieving response with similar context."""
        cache.similarity_threshold = 0.5  # Lower threshold for testing

        context1 = PatternContext(
            primary_service="api-service",
            affected_services=["api-service", "db-service"],
        )
        context2 = PatternContext(
            primary_service="api-service",
            affected_services=["api-service"],  # Partial overlap
        )

        # Cache with context1
        await cache.cache_response(context1, "gemini-1.5-pro", sample_response)

        # Try to retrieve with similar context2
        cached_response = await cache.get_cached_response(context2, "gemini-1.5-pro")

        # Should find similarity match
        assert cached_response is not None
        assert cached_response.content == sample_response.content


class TestGeminiResponseCacheTTL:
    """Test TTL (time-to-live) functionality."""

    @pytest.fixture
    def short_ttl_cache(self):
        """Create cache with short TTL for testing."""
        return GeminiResponseCache(ttl_hours=0.001)  # ~3.6 seconds

    @pytest.mark.asyncio
    async def test_expired_entry_removed(self, short_ttl_cache):
        """Test that expired entries are automatically removed."""
        context = PatternContext(primary_service="test-service")
        response = GeminiResponse(success=True, content="test")

        # Cache the response
        await short_ttl_cache.cache_response(context, "gemini-1.5-pro", response)
        assert len(short_ttl_cache.cache) == 1

        # Wait for expiration
        await asyncio.sleep(4)

        # Try to retrieve - should be expired and removed
        cached_response = await short_ttl_cache.get_cached_response(
            context, "gemini-1.5-pro"
        )

        assert cached_response is None
        assert len(short_ttl_cache.cache) == 0


class TestGeminiResponseCacheEviction:
    """Test LRU eviction functionality."""

    @pytest.mark.asyncio
    async def test_lru_eviction_on_full_cache(self):
        """Test that LRU entries are evicted when cache is full."""
        cache = GeminiResponseCache(max_cache_size=5)  # Small cache
        response = GeminiResponse(success=True, content="test")

        # Fill cache to capacity
        for i in range(5):
            context = PatternContext(primary_service=f"service-{i}")
            await cache.cache_response(context, "gemini-1.5-pro", response)

        assert len(cache.cache) == 5

        # Add one more - should trigger eviction
        overflow_context = PatternContext(primary_service="overflow-service")
        await cache.cache_response(overflow_context, "gemini-1.5-pro", response)

        # Should evict ~20% (1 entry) and add new one
        assert len(cache.cache) <= 5

    @pytest.mark.asyncio
    async def test_evict_lru_entries_manually(self):
        """Test manual LRU eviction."""
        cache = GeminiResponseCache(max_cache_size=10)
        response = GeminiResponse(success=True, content="test")

        # Add entries
        for i in range(6):
            context = PatternContext(primary_service=f"service-{i}")
            await cache.cache_response(context, "gemini-1.5-pro", response)

        initial_count = len(cache.cache)

        # Manually trigger eviction
        await cache._evict_lru_entries()

        # Should have removed ~20% of entries
        assert len(cache.cache) < initial_count


class TestGeminiResponseCacheStats:
    """Test cache statistics functionality."""

    @pytest.fixture
    def cache_with_data(self):
        """Create cache with some test data."""
        cache = GeminiResponseCache(max_cache_size=100, ttl_hours=24)
        return cache

    @pytest.mark.asyncio
    async def test_get_cache_stats_empty_cache(self, cache_with_data):
        """Test cache stats with empty cache."""
        stats = cache_with_data.get_cache_stats()

        assert stats["total_entries"] == 0
        assert stats["max_cache_size"] == 100
        assert stats["cache_utilization"] == 0.0
        assert stats["expired_entries"] == 0
        assert stats["model_distribution"] == {}
        assert stats["oldest_entry_age_hours"] == 0.0
        assert stats["ttl_hours"] == 24

    @pytest.mark.asyncio
    async def test_get_cache_stats_with_entries(self, cache_with_data):
        """Test cache stats with cached entries."""
        response = GeminiResponse(success=True, content="test")

        # Add entries with different models
        context1 = PatternContext(primary_service="service-1")
        context2 = PatternContext(primary_service="service-2")

        await cache_with_data.cache_response(context1, "gemini-1.5-pro", response)
        await cache_with_data.cache_response(context2, "gemini-1.5-flash", response)

        stats = cache_with_data.get_cache_stats()

        assert stats["total_entries"] == 2
        assert stats["cache_utilization"] == 0.02  # 2/100
        assert stats["model_distribution"] == {
            "gemini-1.5-pro": 1,
            "gemini-1.5-flash": 1,
        }
        assert stats["oldest_entry_age_hours"] >= 0.0

    def test_get_oldest_entry_age_hours_empty_cache(self):
        """Test oldest entry age calculation with empty cache."""
        cache = GeminiResponseCache()
        age = cache._get_oldest_entry_age_hours()
        assert age == 0.0

    def test_get_oldest_entry_age_hours_with_entries(self):
        """Test oldest entry age calculation with entries."""
        cache = GeminiResponseCache()

        # Mock cache entries with different timestamps
        old_time = datetime.now() - timedelta(hours=2)
        new_time = datetime.now() - timedelta(hours=1)

        cache.cache = {
            "model1:hash1": {"timestamp": old_time},
            "model2:hash2": {"timestamp": new_time},
        }

        age = cache._get_oldest_entry_age_hours()
        assert age >= 2.0  # Should be around 2 hours


class TestGeminiResponseCacheEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_affected_services_handling(self):
        """Test handling of empty/None affected_services."""
        cache = GeminiResponseCache()

        context1 = PatternContext(affected_services=None)
        context2 = PatternContext(affected_services=[])

        hash1 = cache._compute_context_hash(context1)
        hash2 = cache._compute_context_hash(context2)

        # Both should produce valid hashes
        assert isinstance(hash1, str)
        assert isinstance(hash2, str)

    def test_json_serialization_edge_cases(self):
        """Test JSON serialization of complex context data."""
        cache = GeminiResponseCache()

        context = PatternContext(
            error_patterns={"nested": {"deep": {"value": 123}}},
            timing_analysis={"list": [1, 2, 3], "bool": True},
            service_topology={"unicode": "test 🚀 emoji"},
        )

        hash_result = cache._compute_context_hash(context)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 16
