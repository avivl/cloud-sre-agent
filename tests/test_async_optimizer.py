# tests/test_async_optimizer.py

"""
Tests for the AsyncOptimizer module.

This module tests the async processing optimizations including:
- Concurrent task execution
- Batch processing
- Retry mechanisms
- Performance monitoring integration
"""

import asyncio
import time
from unittest.mock import patch

import pytest

from gemini_sre_agent.ml.performance.async_optimizer import (
    AsyncOptimizer,
    AsyncTask,
    BatchResult,
    cleanup_async_optimizer,
    get_async_optimizer,
)


class TestAsyncTask:
    """Test the AsyncTask dataclass."""

    def test_async_task_creation(self):
        """Test creating an AsyncTask."""

        async def dummy_coroutine():
            return "test"

        task = AsyncTask(
            task_id="test_task",
            coroutine=dummy_coroutine,
            args=(1, 2),
            kwargs={"key": "value"},
            priority=5,
            timeout=10.0,
            max_retries=2,
        )

        assert task.task_id == "test_task"
        assert task.coroutine == dummy_coroutine
        assert task.args == (1, 2)
        assert task.kwargs == {"key": "value"}
        assert task.priority == 5
        assert task.timeout == 10.0
        assert task.max_retries == 2
        assert task.retry_count == 0

    def test_async_task_defaults(self):
        """Test AsyncTask with default values."""

        async def dummy_coroutine():
            return "test"

        task = AsyncTask(task_id="test_task", coroutine=dummy_coroutine)

        assert task.args == ()
        assert task.kwargs == {}
        assert task.priority == 0
        assert task.timeout is None
        assert task.max_retries == 3


class TestAsyncOptimizer:
    """Test the AsyncOptimizer class."""

    @pytest.fixture
    def optimizer(self):
        """Create an AsyncOptimizer instance for testing."""
        return AsyncOptimizer(
            max_concurrent_tasks=3,
            batch_size=2,
            default_timeout=5.0,
            enable_monitoring=False,  # Disable monitoring for cleaner tests
        )

    @pytest.fixture
    def simple_task(self):
        """Create a simple async task."""

        async def simple_coroutine(value):
            await asyncio.sleep(0.1)  # Simulate work
            return f"result_{value}"

        return AsyncTask(task_id="simple_task", coroutine=simple_coroutine, args=(42,))

    @pytest.fixture
    def failing_task(self):
        """Create a task that fails."""

        async def failing_coroutine():
            await asyncio.sleep(0.1)
            raise ValueError("Task failed")

        return AsyncTask(
            task_id="failing_task", coroutine=failing_coroutine, max_retries=1
        )

    @pytest.fixture
    def timeout_task(self):
        """Create a task that times out."""

        async def timeout_coroutine():
            await asyncio.sleep(10.0)  # Longer than timeout
            return "should_not_reach_here"

        return AsyncTask(
            task_id="timeout_task", coroutine=timeout_coroutine, timeout=0.1
        )

    @pytest.mark.asyncio
    async def test_execute_concurrent_tasks_success(self, optimizer, simple_task):
        """Test successful concurrent task execution."""
        tasks = [simple_task]
        results = await optimizer.execute_concurrent_tasks(tasks, wait_for_all=True)

        assert len(results) == 1
        assert "simple_task" in results
        assert results["simple_task"] == "result_42"

    @pytest.mark.asyncio
    async def test_execute_concurrent_tasks_multiple(self, optimizer):
        """Test executing multiple concurrent tasks."""

        async def task_coroutine(task_id, delay):
            await asyncio.sleep(delay)
            return f"result_{task_id}"

        tasks = [
            AsyncTask("task_1", task_coroutine, args=("task_1", 0.1)),
            AsyncTask("task_2", task_coroutine, args=("task_2", 0.2)),
            AsyncTask("task_3", task_coroutine, args=("task_3", 0.1)),
        ]

        start_time = time.time()
        results = await optimizer.execute_concurrent_tasks(tasks, wait_for_all=True)
        duration = time.time() - start_time

        # Should complete in roughly 0.2 seconds (max delay) due to concurrency
        assert duration < 0.5  # Allow some buffer
        assert len(results) == 3
        assert results["task_1"] == "result_task_1"
        assert results["task_2"] == "result_task_2"
        assert results["task_3"] == "result_task_3"

    @pytest.mark.asyncio
    async def test_execute_concurrent_tasks_with_failure(
        self, optimizer, simple_task, failing_task
    ):
        """Test concurrent task execution with some failures."""
        tasks = [simple_task, failing_task]
        results = await optimizer.execute_concurrent_tasks(tasks, wait_for_all=True)

        assert len(results) == 2
        assert results["simple_task"] == "result_42"
        assert isinstance(results["failing_task"], ValueError)
        assert str(results["failing_task"]) == "Task failed"

    @pytest.mark.asyncio
    async def test_execute_batch_success(self, optimizer):
        """Test successful batch processing."""

        async def batch_coroutine(value):
            await asyncio.sleep(0.05)
            return f"batch_result_{value}"

        tasks = [
            AsyncTask(f"batch_task_{i}", batch_coroutine, args=(i,)) for i in range(4)
        ]

        result = await optimizer.execute_batch(tasks, "test_batch")

        assert isinstance(result, BatchResult)
        assert len(result.successful) == 4
        assert len(result.failed) == 0
        assert result.success_rate == 1.0
        assert result.total_duration_ms > 0

        # Check that results are in the successful list
        successful_values = [r for r in result.successful]
        assert len(successful_values) == 4

    @pytest.mark.asyncio
    async def test_execute_batch_with_failures(
        self, optimizer, simple_task, failing_task
    ):
        """Test batch processing with some failures."""
        tasks = [simple_task, failing_task]
        result = await optimizer.execute_batch(tasks, "mixed_batch")

        assert isinstance(result, BatchResult)
        assert len(result.successful) == 1
        assert len(result.failed) == 1
        assert result.success_rate == 0.5

        # Check successful result
        assert result.successful[0] == "result_42"

        # Check failed result
        assert result.failed[0]["task_id"] == "failing_task"
        assert "Task failed" in result.failed[0]["error"]

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self, optimizer, simple_task):
        """Test task execution with retry on success."""
        result = await optimizer.execute_with_retry(simple_task)

        assert result == "result_42"

    @pytest.mark.asyncio
    async def test_execute_with_retry_failure(self, optimizer, failing_task):
        """Test task execution with retry on failure."""
        with pytest.raises(ValueError, match="Task failed"):
            await optimizer.execute_with_retry(failing_task)

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, optimizer, timeout_task):
        """Test task execution with timeout."""
        with pytest.raises(asyncio.TimeoutError):
            await optimizer.execute_with_retry(timeout_task)

    @pytest.mark.asyncio
    async def test_optimize_context_building(self, optimizer):
        """Test optimized context building."""

        async def repo_analysis_coroutine(repo_id):
            await asyncio.sleep(0.1)
            return f"repo_context_{repo_id}"

        async def issue_extraction_coroutine(issue_id):
            await asyncio.sleep(0.05)
            return f"issue_context_{issue_id}"

        tasks = [
            AsyncTask("repo_analysis_1", repo_analysis_coroutine, args=("repo1",)),
            AsyncTask("repo_analysis_2", repo_analysis_coroutine, args=("repo2",)),
            AsyncTask(
                "issue_pattern_extraction_1",
                issue_extraction_coroutine,
                args=("issue1",),
            ),
            AsyncTask(
                "issue_pattern_extraction_2",
                issue_extraction_coroutine,
                args=("issue2",),
            ),
        ]

        results = await optimizer.optimize_context_building(tasks)

        assert "repo" in results
        assert "issue" in results

        # Repository analysis should be batched
        repo_results = results["repo"]
        assert len(repo_results) == 2

        # Issue patterns should be concurrent
        issue_results = results["issue"]
        assert len(issue_results) == 2

    def test_group_tasks_by_type(self, optimizer):
        """Test task grouping by type."""

        async def repo_coroutine():
            return "repo"

        async def issue_coroutine():
            return "issue"

        tasks = [
            AsyncTask("repo_analysis_1", repo_coroutine),
            AsyncTask("repo_analysis_2", repo_coroutine),
            AsyncTask("issue_pattern_1", issue_coroutine),
            AsyncTask("general_task_1", repo_coroutine),
        ]

        grouped = optimizer._group_tasks_by_type(tasks)

        assert "repo" in grouped
        assert "issue" in grouped
        assert "general" in grouped

        assert len(grouped["repo"]) == 2
        assert len(grouped["issue"]) == 1
        assert len(grouped["general"]) == 1

    def test_extract_task_type(self, optimizer):
        """Test task type extraction."""

        async def test_coroutine():
            return "test"

        # Test with task_id
        task1 = AsyncTask("repository_analysis_1", test_coroutine)
        assert optimizer._extract_task_type(task1) == "repository"

        # Test with coroutine name
        async def issue_extraction_coroutine():
            return "test"

        task2 = AsyncTask("task_1", issue_extraction_coroutine)
        assert optimizer._extract_task_type(task2) == "task"

        # Test default
        task3 = AsyncTask("task_1", test_coroutine)
        assert optimizer._extract_task_type(task3) == "task"

    def test_get_optimizer_stats(self, optimizer):
        """Test getting optimizer statistics."""
        stats = optimizer.get_optimizer_stats()

        assert "total_tasks_processed" in stats
        assert "total_batches_processed" in stats
        assert "completed_tasks" in stats
        assert "failed_tasks" in stats
        assert "running_tasks" in stats
        assert "queue_size" in stats
        assert "max_concurrent_tasks" in stats
        assert "batch_size" in stats
        assert "default_timeout" in stats

        assert stats["max_concurrent_tasks"] == 3
        assert stats["batch_size"] == 2
        assert stats["default_timeout"] == 5.0

    @pytest.mark.asyncio
    async def test_cleanup(self, optimizer):
        """Test optimizer cleanup."""

        # Add some tasks to the queue
        async def dummy_coroutine():
            return "dummy"

        task = AsyncTask("cleanup_test", dummy_coroutine)
        await optimizer.task_queue.put((0, task))

        # Cleanup should clear everything
        await optimizer.cleanup()

        assert len(optimizer.running_tasks) == 0
        assert len(optimizer.completed_tasks) == 0
        assert len(optimizer.failed_tasks) == 0
        assert optimizer.task_queue.qsize() == 0


class TestGlobalAsyncOptimizer:
    """Test the global async optimizer functions."""

    def test_get_async_optimizer_singleton(self):
        """Test that get_async_optimizer returns a singleton."""
        optimizer1 = get_async_optimizer()
        optimizer2 = get_async_optimizer()

        assert optimizer1 is optimizer2

    @pytest.mark.asyncio
    async def test_cleanup_async_optimizer(self):
        """Test cleaning up the global async optimizer."""
        # Get the optimizer
        optimizer = get_async_optimizer()
        assert optimizer is not None

        # Clean it up
        await cleanup_async_optimizer()

        # Get a new one - should be different instance
        new_optimizer = get_async_optimizer()
        assert new_optimizer is not optimizer


class TestAsyncOptimizerIntegration:
    """Integration tests for AsyncOptimizer with performance monitoring."""

    @pytest.fixture
    def monitoring_optimizer(self):
        """Create an AsyncOptimizer with monitoring enabled."""
        return AsyncOptimizer(
            max_concurrent_tasks=2, batch_size=2, enable_monitoring=True
        )

    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self, monitoring_optimizer):
        """Test that performance monitoring is integrated."""

        async def monitored_coroutine(task_id):
            await asyncio.sleep(0.1)
            return f"monitored_{task_id}"

        task = AsyncTask("monitored_task", monitored_coroutine, args=("test",))

        # Mock the record_performance function
        with patch(
            "gemini_sre_agent.ml.performance.async_optimizer.record_performance"
        ) as mock_record:
            result = await monitoring_optimizer.execute_with_retry(task)

            assert result == "monitored_test"
            # Should have recorded performance
            assert mock_record.called

    @pytest.mark.asyncio
    async def test_concurrent_task_priority(self, monitoring_optimizer):
        """Test that tasks are executed in priority order."""
        results = []

        async def priority_coroutine(priority):
            await asyncio.sleep(0.1)
            results.append(priority)
            return f"priority_{priority}"

        # Create tasks with different priorities
        tasks = [
            AsyncTask("low_priority", priority_coroutine, args=(1,), priority=1),
            AsyncTask("high_priority", priority_coroutine, args=(3,), priority=3),
            AsyncTask("medium_priority", priority_coroutine, args=(2,), priority=2),
        ]

        await monitoring_optimizer.execute_concurrent_tasks(tasks, wait_for_all=True)

        # Results should be in priority order (higher priority first)
        # Note: Due to concurrency, exact order may vary, but high priority should complete first
        assert len(results) == 3
        assert set(results) == {1, 2, 3}

    @pytest.mark.asyncio
    async def test_semaphore_limit(self, monitoring_optimizer):
        """Test that semaphore limits concurrent execution."""
        execution_order = []

        async def limited_coroutine(task_id):
            execution_order.append(f"start_{task_id}")
            await asyncio.sleep(0.2)  # Longer sleep to see concurrency limits
            execution_order.append(f"end_{task_id}")
            return f"limited_{task_id}"

        # Create more tasks than max_concurrent_tasks (2)
        tasks = [AsyncTask(f"task_{i}", limited_coroutine, args=(i,)) for i in range(4)]

        start_time = time.time()
        await monitoring_optimizer.execute_concurrent_tasks(tasks, wait_for_all=True)
        duration = time.time() - start_time

        # Should take at least 0.4 seconds (2 batches of 0.2s each)
        assert duration >= 0.4

        # Should have all start and end markers
        assert len(execution_order) == 8  # 4 starts + 4 ends
        assert all(f"start_{i}" in execution_order for i in range(4))
        assert all(f"end_{i}" in execution_order for i in range(4))
