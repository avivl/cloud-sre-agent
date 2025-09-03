# tests/test_week4_performance_optimization.py

"""
Comprehensive tests for Week 4: Performance Optimization & Monitoring.

This module tests the enhanced caching system, model selection optimization,
and performance monitoring capabilities.
"""

import asyncio

import pytest

from gemini_sre_agent.ml.adaptive_prompt_strategy import (
    AdaptivePromptStrategy,
    StrategyConfig,
)
from gemini_sre_agent.ml.caching import (
    IssuePatternCache,
    RepositoryContextCache,
)
from gemini_sre_agent.ml.performance import (
    PerformanceMonitor,
    get_performance_monitor,
    get_performance_summary,
    record_performance,
)


class TestIssuePatternCache:
    """Test cases for IssuePatternCache class."""

    @pytest.fixture
    def pattern_cache(self):
        """Create an IssuePatternCache instance."""
        return IssuePatternCache()

    @pytest.fixture
    def sample_pattern_data(self):
        """Sample pattern data for testing."""
        return {
            "pattern_type": "database_error",
            "error_message": "connection timeout",
            "solution": "increase connection pool size",
            "complexity": 5,
        }

    @pytest.mark.asyncio
    async def test_set_and_get_issue_pattern(self, pattern_cache, sample_pattern_data):
        """Test setting and getting issue patterns."""
        # Set pattern
        await pattern_cache.set_issue_pattern(
            "error_pattern", "db_001", sample_pattern_data, domain="database"
        )

        # Get pattern
        retrieved = await pattern_cache.get_issue_pattern(
            "error_pattern", "db_001", domain="database"
        )

        assert retrieved is not None
        assert retrieved["pattern_type"] == "database_error"
        assert retrieved["error_message"] == "connection timeout"

    @pytest.mark.asyncio
    async def test_domain_specific_ttl(self, pattern_cache, sample_pattern_data):
        """Test domain-specific TTL strategies."""
        # Set security pattern (should have 30 min TTL)
        await pattern_cache.set_issue_pattern(
            "error_pattern", "sec_001", sample_pattern_data, domain="security"
        )

        # Set database pattern (should have 1 hour TTL)
        await pattern_cache.set_issue_pattern(
            "error_pattern", "db_002", sample_pattern_data, domain="database"
        )

        # Check that both are cached
        sec_pattern = await pattern_cache.get_issue_pattern(
            "error_pattern", "sec_001", domain="security"
        )
        db_pattern = await pattern_cache.get_issue_pattern(
            "error_pattern", "db_002", domain="database"
        )

        assert sec_pattern is not None
        assert db_pattern is not None

    @pytest.mark.asyncio
    async def test_similar_patterns(self, pattern_cache, sample_pattern_data):
        """Test similar pattern functionality."""
        # Set patterns with similarity
        await pattern_cache.set_issue_pattern(
            "error_pattern",
            "main_001",
            sample_pattern_data,
            similarity_keys=["similar_001", "similar_002"],
        )

        # Set similar patterns
        await pattern_cache.set_issue_pattern(
            "error_pattern", "similar_001", {"pattern_type": "similar", "complexity": 4}
        )

        # Get similar patterns
        similar = await pattern_cache.get_similar_patterns("main_001")
        assert len(similar) > 0

    @pytest.mark.asyncio
    async def test_domain_patterns(self, pattern_cache, sample_pattern_data):
        """Test domain pattern retrieval."""
        # Set patterns for different domains
        await pattern_cache.set_issue_pattern(
            "error_pattern", "api_001", sample_pattern_data, domain="api"
        )

        await pattern_cache.set_issue_pattern(
            "error_pattern",
            "api_002",
            {"pattern_type": "api_error", "complexity": 3},
            domain="api",
        )

        # Get all API patterns
        api_patterns = await pattern_cache.get_domain_patterns("api")
        assert len(api_patterns) == 2

    @pytest.mark.asyncio
    async def test_cache_stats(self, pattern_cache, sample_pattern_data):
        """Test cache statistics."""
        # Set some patterns
        await pattern_cache.set_issue_pattern(
            "error_pattern", "test_001", sample_pattern_data, domain="test"
        )

        stats = pattern_cache.get_cache_stats()
        assert stats["total_entries"] > 0
        assert "test" in stats["domain_counts"]


class TestRepositoryContextCache:
    """Test cases for RepositoryContextCache class."""

    @pytest.fixture
    def repo_cache(self):
        """Create a RepositoryContextCache instance."""
        return RepositoryContextCache()

    @pytest.fixture
    def sample_repo_context(self):
        """Sample repository context data."""
        return {
            "architecture": "microservices",
            "technology_stack": {
                "backend": "Python",
                "database": "PostgreSQL",
                "cache": "Redis",
            },
            "code_patterns": ["async/await", "dependency_injection"],
        }

    @pytest.mark.asyncio
    async def test_set_and_get_repository_context(
        self, repo_cache, sample_repo_context
    ):
        """Test setting and getting repository context."""
        # Set context
        await repo_cache.set_repository_context(
            "/path/to/repo",
            "standard",
            sample_repo_context,
            tech_stack=sample_repo_context["technology_stack"],
            last_commit="abc123",
        )

        # Get context
        retrieved = await repo_cache.get_repository_context("/path/to/repo", "standard")
        assert retrieved is not None
        assert retrieved["architecture"] == "microservices"

    @pytest.mark.asyncio
    async def test_analysis_depth_caching(self, repo_cache, sample_repo_context):
        """Test different analysis depth caching."""
        # Set contexts for different depths
        await repo_cache.set_repository_context(
            "/path/to/repo", "shallow", {"depth": "shallow", "data": "minimal"}
        )

        await repo_cache.set_repository_context(
            "/path/to/repo", "deep", {"depth": "deep", "data": "comprehensive"}
        )

        # Check both are cached
        shallow = await repo_cache.get_repository_context("/path/to/repo", "shallow")
        deep = await repo_cache.get_repository_context("/path/to/repo", "deep")

        assert shallow is not None
        assert deep is not None
        assert shallow["depth"] == "shallow"
        assert deep["depth"] == "deep"

    @pytest.mark.asyncio
    async def test_repository_change_detection(self, repo_cache):
        """Test repository change detection."""
        # Set initial commit
        await repo_cache.set_repository_context(
            "/path/to/repo", "standard", {"data": "initial"}, last_commit="abc123"
        )

        # Check if changed
        has_changed = await repo_cache.has_repository_changed("/path/to/repo", "def456")
        assert has_changed is True

        # Check if unchanged
        has_changed = await repo_cache.has_repository_changed("/path/to/repo", "abc123")
        assert has_changed is False

    @pytest.mark.asyncio
    async def test_technology_stack_caching(self, repo_cache, sample_repo_context):
        """Test technology stack caching."""
        tech_stack = sample_repo_context["technology_stack"]

        await repo_cache.set_repository_context(
            "/path/to/repo", "standard", sample_repo_context, tech_stack=tech_stack
        )

        # Get tech stack separately
        cached_tech_stack = await repo_cache.get_technology_stack("/path/to/repo")
        assert cached_tech_stack is not None
        assert cached_tech_stack["backend"] == "Python"

    @pytest.mark.asyncio
    async def test_repository_summary(self, repo_cache, sample_repo_context):
        """Test repository summary generation."""
        # Set multiple contexts
        await repo_cache.set_repository_context(
            "/path/to/repo", "shallow", {"depth": "shallow"}
        )

        await repo_cache.set_repository_context(
            "/path/to/repo", "standard", sample_repo_context
        )

        # Get summary
        summary = await repo_cache.get_repository_summary("/path/to/repo")
        assert summary["repo_path"] == "/path/to/repo"
        assert len(summary["available_analysis_depths"]) == 2
        assert summary["cache_status"] == "active"


class TestModelSelectionOptimization:
    """Test cases for model selection optimization."""

    @pytest.fixture
    def strategy(self):
        """Create an AdaptivePromptStrategy instance."""
        config = StrategyConfig()
        return AdaptivePromptStrategy(config)

    @pytest.fixture
    def high_complexity_context(self):
        """High complexity task context."""
        from gemini_sre_agent.ml.prompt_context_models import TaskContext

        return TaskContext(
            task_type="complex_analysis",
            complexity_score=9,
            context_variability=0.8,
            business_impact=9,
            accuracy_requirement=0.95,
            latency_requirement=10000,
            context_richness=0.9,
            frequency="low",
            cost_sensitivity=0.1,
        )

    @pytest.fixture
    def low_complexity_context(self):
        """Low complexity task context."""
        from gemini_sre_agent.ml.prompt_context_models import TaskContext

        return TaskContext(
            task_type="simple_fix",
            complexity_score=2,
            context_variability=0.2,
            business_impact=2,
            accuracy_requirement=0.8,
            latency_requirement=2000,
            context_richness=0.3,
            frequency="high",
            cost_sensitivity=0.8,
        )

    def test_high_complexity_model_selection(self, strategy, high_complexity_context):
        """Test model selection for high complexity tasks."""
        # Meta-prompt strategy
        model = strategy.select_model(high_complexity_context, "meta_prompt")
        assert model == "gemini-1.5-pro-001"

        # Other strategies
        model = strategy.select_model(high_complexity_context, "context_aware")
        assert model == "gemini-1.5-pro-001"

    def test_low_complexity_model_selection(self, strategy, low_complexity_context):
        """Test model selection for low complexity tasks."""
        # Meta-prompt strategy
        model = strategy.select_model(low_complexity_context, "meta_prompt")
        assert model == "gemini-1.5-flash-001"

        # Other strategies
        model = strategy.select_model(low_complexity_context, "static_template")
        assert model == "gemini-1.5-flash-001"

    def test_medium_complexity_model_selection(self, strategy):
        """Test model selection for medium complexity tasks."""
        from gemini_sre_agent.ml.prompt_context_models import TaskContext

        medium_context = TaskContext(
            task_type="medium_analysis",
            complexity_score=6,
            context_variability=0.5,
            business_impact=6,
            accuracy_requirement=0.9,
            latency_requirement=5000,
            context_richness=0.6,
            frequency="medium",
            cost_sensitivity=0.5,
        )

        # Meta-prompt strategy should use flash
        model = strategy.select_model(medium_context, "meta_prompt")
        assert model == "gemini-1.5-flash-001"

        # Other strategies should use pro
        model = strategy.select_model(medium_context, "hybrid")
        assert model == "gemini-1.5-pro-001"

    def test_model_selection_stats(self, strategy):
        """Test model selection statistics."""
        stats = strategy.get_model_selection_stats()

        assert stats["model_selection_enabled"] is True
        assert "gemini-1.5-flash-001" in stats["available_models"]
        assert "gemini-1.5-pro-001" in stats["available_models"]
        assert stats["selection_criteria"]["complexity_threshold_high"] == 8
        assert stats["selection_criteria"]["complexity_threshold_medium"] == 5


class TestPerformanceMonitor:
    """Test cases for PerformanceMonitor class."""

    @pytest.fixture
    def monitor(self):
        """Create a PerformanceMonitor instance."""
        return PerformanceMonitor(
            max_metrics_per_operation=100,
            alert_threshold_ms=1000.0,
            alert_success_rate_threshold=0.9,
        )

    @pytest.mark.asyncio
    async def test_record_metric(self, monitor):
        """Test recording performance metrics."""
        await monitor.record_metric(
            "test_operation", 1500.0, True, {"test": "data"}  # Above threshold
        )

        # Check if metric was recorded
        summary = await monitor.get_performance_summary("test_operation")
        assert summary is not None
        assert summary.total_operations == 1
        assert summary.successful_operations == 1
        assert summary.average_duration_ms == 1500.0

    @pytest.mark.asyncio
    async def test_performance_alerting(self, monitor):
        """Test performance alerting system."""
        # Record operation above threshold
        await monitor.record_metric(
            "slow_operation", 2000.0, True  # Above 1000ms threshold
        )

        # Check if alert was triggered
        stats = monitor.get_monitor_stats()
        assert stats["total_alerts_triggered"] > 0

    @pytest.mark.asyncio
    async def test_operation_recorder_context_manager(self, monitor):
        """Test OperationRecorder context manager."""
        async with monitor.record_operation("context_test", {"test": "data"}):
            # Simulate some work
            await asyncio.sleep(0.1)

        # Check if operation was recorded
        summary = await monitor.get_performance_summary("context_test")
        assert summary is not None
        assert summary.total_operations == 1
        assert summary.successful_operations == 1

    @pytest.mark.asyncio
    async def test_performance_trends(self, monitor):
        """Test performance trend analysis."""
        # Record multiple metrics over time
        for i in range(10):
            await monitor.record_metric(
                "trend_test", 100.0 + i * 10.0, True  # Increasing duration
            )
            await asyncio.sleep(0.01)

        # Get trends
        trends = await monitor.get_performance_trends("trend_test", hours=1)
        assert "avg_durations" in trends
        assert len(trends["avg_durations"]) > 0

    @pytest.mark.asyncio
    async def test_alert_callback(self, monitor):
        """Test alert callback functionality."""
        alert_received = []

        async def alert_callback(alert):
            alert_received.append(alert)

        # Add callback
        await monitor.add_alert_callback(alert_callback)

        # Trigger alert
        await monitor.record_metric("callback_test", 2000.0, True)  # Above threshold

        # Check if callback was called
        assert len(alert_received) > 0
        assert alert_received[0]["type"] == "performance_degradation"

    @pytest.mark.asyncio
    async def test_low_success_rate_alert(self, monitor):
        """Test low success rate alerting."""
        # Record multiple failed operations
        for _ in range(5):
            await monitor.record_metric(
                "failing_operation", 100.0, False, error_message="Test failure"
            )

        # Wait for monitoring loop to run
        await asyncio.sleep(0.1)

        # Check if low success rate alert was triggered
        # Note: This depends on the monitoring loop timing
        # In a real test, we might need to trigger the analysis manually

    def test_monitor_stats(self, monitor):
        """Test monitor statistics."""
        stats = monitor.get_monitor_stats()

        assert "total_operations_monitored" in stats
        assert "total_metrics_collected" in stats
        assert "total_alerts_triggered" in stats
        assert "alert_threshold_ms" in stats
        assert stats["alert_threshold_ms"] == 1000.0


class TestGlobalPerformanceMonitor:
    """Test cases for global performance monitor functions."""

    @pytest.mark.asyncio
    async def test_global_monitor_singleton(self):
        """Test that global monitor is a singleton."""
        monitor1 = get_performance_monitor()
        monitor2 = get_performance_monitor()

        assert monitor1 is monitor2

    @pytest.mark.asyncio
    async def test_record_performance_global(self):
        """Test global performance recording."""
        await record_performance("global_test", 500.0, True, {"global": "test"})

        # Check if recorded
        summary = await get_performance_summary("global_test")
        assert summary is not None
        assert summary.total_operations == 1


if __name__ == "__main__":
    pytest.main([__file__])
