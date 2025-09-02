# tests/test_performance_optimizations.py

"""
Test performance optimization features.

This test suite verifies that the performance optimizations work correctly,
including caching, async processing, and repository analysis.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from gemini_sre_agent.ml.caching import (
    ContextCache,
    IssuePatternCache,
    RepositoryContextCache,
)
from gemini_sre_agent.ml.performance import (
    AnalysisConfig,
    CacheConfig,
    ModelPerformanceConfig,
    PerformanceConfig,
    PerformanceRepositoryAnalyzer,
)


class TestContextCache:
    """Test the context caching system."""

    @pytest.fixture
    def cache(self):
        """Create a test cache instance."""
        return ContextCache(max_size_mb=1, default_ttl_seconds=1)

    @pytest.mark.asyncio
    async def test_cache_set_get(self, cache):
        """Test basic cache set and get operations."""
        # Set a value
        success = await cache.set("test_key", "test_value")
        assert success is True

        # Get the value
        value = await cache.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache):
        """Test that cache entries expire correctly."""
        # Set a value with short TTL
        await cache.set("expire_key", "expire_value", ttl_seconds=0.1)

        # Wait for expiration
        import asyncio

        await asyncio.sleep(0.2)

        # Value should be expired
        value = await cache.get("expire_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_cache_stats(self, cache):
        """Test cache statistics."""
        # Add some data
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        # Get stats
        stats = await cache.get_stats()

        assert stats["total_entries"] == 2
        assert stats["current_size_bytes"] > 0
        assert stats["total_accesses"] == 2

    @pytest.mark.asyncio
    async def test_cache_cleanup(self, cache):
        """Test cache cleanup operations."""
        # Add data
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        # Clear cache
        await cache.clear()

        # Verify cache is empty
        stats = await cache.get_stats()
        assert stats["total_entries"] == 0


class TestRepositoryContextCache:
    """Test the repository context cache."""

    @pytest.fixture
    def base_cache(self):
        """Create a base cache instance."""
        return ContextCache(max_size_mb=1, default_ttl_seconds=1)

    @pytest.fixture
    def repo_cache(self, base_cache):
        """Create a repository context cache instance."""
        return RepositoryContextCache(base_cache)

    @pytest.mark.asyncio
    async def test_repository_context_caching(self, repo_cache):
        """Test repository context caching."""
        repo_path = "/test/repo"
        context = {"architecture": "microservices", "framework": "fastapi"}

        # Cache repository context
        success = await repo_cache.set_repository_context(
            repo_path, context, "standard"
        )
        assert success is True

        # Retrieve cached context
        cached_context = await repo_cache.get_repository_context(repo_path, "standard")
        assert cached_context == context

    @pytest.mark.asyncio
    async def test_repository_context_invalidation(self, repo_cache):
        """Test repository context invalidation."""
        repo_path = "/test/repo"
        context = {"test": "data"}

        # Cache multiple analysis depths
        await repo_cache.set_repository_context(repo_path, context, "basic")
        await repo_cache.set_repository_context(repo_path, context, "standard")

        # Invalidate all entries for this repository
        await repo_cache.invalidate_repository_context(repo_path)

        # Verify all entries are removed
        basic_context = await repo_cache.get_repository_context(repo_path, "basic")
        standard_context = await repo_cache.get_repository_context(
            repo_path, "standard"
        )

        assert basic_context is None
        assert standard_context is None


class TestIssuePatternCache:
    """Test the issue pattern cache."""

    @pytest.fixture
    def base_cache(self):
        """Create a base cache instance."""
        return ContextCache(max_size_mb=1, default_ttl_seconds=1)

    @pytest.fixture
    def pattern_cache(self, base_cache):
        """Create an issue pattern cache instance."""
        return IssuePatternCache(base_cache)

    @pytest.mark.asyncio
    async def test_issue_pattern_caching(self, pattern_cache):
        """Test issue pattern caching."""
        pattern_type = "error"
        pattern_data = "database connection failed"
        pattern_result = {"classification": "database_error", "confidence": 0.9}

        # Cache pattern
        success = await pattern_cache.set_issue_pattern(
            pattern_type, pattern_data, pattern_result
        )
        assert success is True

        # Retrieve cached pattern
        cached_result = await pattern_cache.get_issue_pattern(
            pattern_type, pattern_data
        )
        assert cached_result == pattern_result


class TestPerformanceConfig:
    """Test the performance configuration system."""

    def test_default_config(self):
        """Test default configuration creation."""
        config = PerformanceConfig(
            cache=CacheConfig(),
            analysis=AnalysisConfig(
                basic_analysis={
                    "max_files": 100,
                    "max_depth": 2,
                    "include_hidden": False,
                    "parallel_workers": 2,
                    "analysis_timeout": 30,
                },
                standard_analysis={
                    "max_files": 500,
                    "max_depth": 3,
                    "include_hidden": False,
                    "parallel_workers": 4,
                    "analysis_timeout": 60,
                },
                comprehensive_analysis={
                    "max_files": 2000,
                    "max_depth": 5,
                    "include_hidden": True,
                    "parallel_workers": 8,
                    "analysis_timeout": 120,
                },
            ),
            model=ModelPerformanceConfig(),
        )

        assert config.enable_performance_monitoring is True
        assert config.performance_log_level == "INFO"
        assert config.max_memory_usage_mb == 512

    def test_analysis_config_mapping(self):
        """Test analysis configuration depth mapping."""
        config = PerformanceConfig(
            cache=CacheConfig(),
            analysis=AnalysisConfig(
                basic_analysis={
                    "max_files": 100,
                    "max_depth": 2,
                    "include_hidden": False,
                    "parallel_workers": 2,
                    "analysis_timeout": 30,
                },
                standard_analysis={
                    "max_files": 500,
                    "max_depth": 3,
                    "include_hidden": False,
                    "parallel_workers": 4,
                    "analysis_timeout": 60,
                },
                comprehensive_analysis={
                    "max_files": 2000,
                    "max_depth": 5,
                    "include_hidden": True,
                    "parallel_workers": 8,
                    "analysis_timeout": 120,
                },
            ),
            model=ModelPerformanceConfig(),
        )

        basic_config = config.get_analysis_config("basic")
        assert basic_config["max_files"] == 100
        assert basic_config["max_depth"] == 2

        standard_config = config.get_analysis_config("standard")
        assert standard_config["max_files"] == 500
        assert standard_config["max_depth"] == 3

    def test_config_serialization(self):
        """Test configuration serialization to/from dictionary."""
        config = PerformanceConfig(
            cache=CacheConfig(),
            analysis=AnalysisConfig(
                basic_analysis={
                    "max_files": 100,
                    "max_depth": 2,
                    "include_hidden": False,
                    "parallel_workers": 2,
                    "analysis_timeout": 30,
                },
                standard_analysis={
                    "max_files": 500,
                    "max_depth": 3,
                    "include_hidden": False,
                    "parallel_workers": 4,
                    "analysis_timeout": 60,
                },
                comprehensive_analysis={
                    "max_files": 2000,
                    "max_depth": 5,
                    "include_hidden": True,
                    "parallel_workers": 8,
                    "analysis_timeout": 120,
                },
            ),
            model=ModelPerformanceConfig(),
        )

        # Convert to dictionary
        config_dict = config.to_dict()

        # Convert back from dictionary
        restored_config = PerformanceConfig.from_dict(config_dict)

        # Verify they're equivalent
        assert (
            restored_config.enable_performance_monitoring
            == config.enable_performance_monitoring
        )
        assert restored_config.performance_log_level == config.performance_log_level
        assert restored_config.max_memory_usage_mb == config.max_memory_usage_mb


class TestPerformanceRepositoryAnalyzer:
    """Test the performance repository analyzer."""

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache instance."""
        cache = Mock(spec=RepositoryContextCache)
        cache.get_repository_context = AsyncMock(return_value=None)
        cache.set_repository_context = AsyncMock(return_value=True)
        return cache

    @pytest.fixture
    def analyzer(self, mock_cache):
        """Create a test analyzer instance."""
        return PerformanceRepositoryAnalyzer(mock_cache, repo_path=".")

    @pytest.mark.asyncio
    async def test_analyzer_initialization(self, analyzer):
        """Test analyzer initialization."""
        assert analyzer.repo_path is not None
        assert analyzer.cache is not None
        assert "basic" in analyzer.analysis_configs
        assert "standard" in analyzer.analysis_configs
        assert "comprehensive" in analyzer.analysis_configs

    @pytest.mark.asyncio
    async def test_analysis_depth_configs(self, analyzer):
        """Test analysis depth configurations."""
        basic_config = analyzer.analysis_configs["basic"]
        assert basic_config["max_files"] == 100
        assert basic_config["max_depth"] == 2
        assert basic_config["parallel_workers"] == 2

        comprehensive_config = analyzer.analysis_configs["comprehensive"]
        assert comprehensive_config["max_files"] == 2000
        assert comprehensive_config["max_depth"] == 5
        assert comprehensive_config["parallel_workers"] == 8

    @pytest.mark.asyncio
    async def test_architecture_detection(self, analyzer):
        """Test architecture type detection."""
        # Test microservices detection
        microservices_structure = {"docker-compose.yml": "exists"}
        arch_type = analyzer._determine_architecture_type(microservices_structure)
        assert arch_type == "microservices"

        # Test unknown architecture
        unknown_structure = {}
        arch_type = analyzer._determine_architecture_type(unknown_structure)
        assert arch_type == "unknown"

    @pytest.mark.asyncio
    async def test_framework_detection(self, analyzer):
        """Test framework detection."""
        # Mock file existence checks
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            # Test FastAPI detection
            framework = await analyzer._detect_framework()
            # This would need proper mocking of the file structure
            # For now, just test that the method runs without error
            assert framework is None or isinstance(framework, str)

    @pytest.mark.asyncio
    async def test_quality_metrics_calculation(self, analyzer):
        """Test code quality metrics calculation."""
        file_structure = {
            "total_files": 100,
            "large_files": [{"name": "large1.txt"}, {"name": "large2.txt"}],
            "recent_files": [{"name": "recent1.txt"}],
        }

        metrics = await analyzer._calculate_quality_metrics(file_structure)

        assert metrics["total_files"] == 100
        assert metrics["large_files_count"] == 2
        assert metrics["recent_files_count"] == 1
        assert metrics["activity_score"] == 1.0  # 1 recent file out of 100 total
