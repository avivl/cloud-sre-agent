# gemini_sre_agent/ml/performance/async_optimizer.py

"""
Async Processing Optimizer for enhanced code generation workflows.

This module provides optimizations for async processing including:
- Concurrent task execution
- Batch processing
- Resource pooling
- Async context management
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .performance_monitor import record_performance

T = TypeVar("T")


@dataclass
class AsyncTask:
    """Represents an async task with metadata."""

    task_id: str
    coroutine: Callable[..., Any]
    args: tuple = ()
    kwargs: Optional[Dict[str, Any]] = None
    priority: int = 0  # Higher number = higher priority
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}

    def __lt__(self, other):
        """Make AsyncTask comparable for priority queue."""
        if not isinstance(other, AsyncTask):
            return NotImplemented
        # Higher priority first (reverse order)
        return self.priority > other.priority


@dataclass
class BatchResult:
    """Result of batch processing."""

    successful: List[Any]
    failed: List[Dict[str, Any]]
    total_duration_ms: float
    success_rate: float


class AsyncOptimizer:
    """
    Optimizes async processing for code generation workflows.

    Features:
    - Concurrent task execution with priority queuing
    - Batch processing for similar operations
    - Resource pooling and connection management
    - Automatic retry with exponential backoff
    - Performance monitoring integration
    """

    def __init__(
        self,
        max_concurrent_tasks: int = 10,
        batch_size: int = 5,
        default_timeout: float = 30.0,
        enable_monitoring: bool = True,
    ):
        """Initialize the async optimizer."""
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.max_concurrent_tasks = max_concurrent_tasks
        self.batch_size = batch_size
        self.default_timeout = default_timeout
        self.enable_monitoring = enable_monitoring

        # Task management
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: Dict[str, Any] = {}
        self.failed_tasks: Dict[str, Exception] = {}

        # Semaphore for concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)

        # Performance tracking
        self.total_tasks_processed = 0
        self.total_batches_processed = 0

    async def execute_concurrent_tasks(
        self, tasks: List[AsyncTask], wait_for_all: bool = True
    ) -> Dict[str, Any]:
        """
        Execute multiple tasks concurrently with priority queuing.

        Args:
            tasks: List of async tasks to execute
            wait_for_all: Whether to wait for all tasks to complete

        Returns:
            Dictionary mapping task_id to result or exception
        """
        start_time = time.time()

        try:
            # Add tasks to queue
            for task in tasks:
                await self.task_queue.put((task.priority, task))

            # Start task processor
            processor_task = asyncio.create_task(self._process_task_queue())

            if wait_for_all:
                # Wait for all tasks to complete
                await processor_task

                # Collect results
                results = {}
                for task_id in [task.task_id for task in tasks]:
                    if task_id in self.completed_tasks:
                        results[task_id] = self.completed_tasks[task_id]
                    elif task_id in self.failed_tasks:
                        results[task_id] = self.failed_tasks[task_id]
                    else:
                        results[task_id] = None

                duration_ms = (time.time() - start_time) * 1000

                if self.enable_monitoring:
                    await record_performance(
                        "concurrent_task_execution",
                        duration_ms,
                        success=True,
                        metadata={
                            "task_count": len(tasks),
                            "successful_tasks": len(self.completed_tasks),
                            "failed_tasks": len(self.failed_tasks),
                        },
                    )

                return results
            else:
                # Return immediately, tasks will continue in background
                return {"status": "started", "task_count": len(tasks)}

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            if self.enable_monitoring:
                await record_performance(
                    "concurrent_task_execution",
                    duration_ms,
                    success=False,
                    error_message=str(e),
                )

            self.logger.error(f"Concurrent task execution failed: {e}")
            raise

    async def execute_batch(
        self, batch_tasks: List[AsyncTask], batch_id: Optional[str] = None
    ) -> BatchResult:
        """
        Execute a batch of similar tasks efficiently.

        Args:
            batch_tasks: List of tasks to execute as a batch
            batch_id: Optional identifier for the batch

        Returns:
            BatchResult with execution details
        """
        start_time = time.time()
        successful = []
        failed = []

        try:
            # Process tasks in smaller chunks to avoid overwhelming the system
            chunk_size = min(self.batch_size, len(batch_tasks))

            for i in range(0, len(batch_tasks), chunk_size):
                chunk = batch_tasks[i : i + chunk_size]

                # Execute chunk concurrently
                chunk_results = await self.execute_concurrent_tasks(
                    chunk, wait_for_all=True
                )

                # Categorize results
                for task_id, result in chunk_results.items():
                    if isinstance(result, Exception):
                        failed.append(
                            {
                                "task_id": task_id,
                                "error": str(result),
                                "error_type": type(result).__name__,
                            }
                        )
                    else:
                        successful.append(result)

            duration_ms = (time.time() - start_time) * 1000
            success_rate = len(successful) / len(batch_tasks) if batch_tasks else 0

            result = BatchResult(
                successful=successful,
                failed=failed,
                total_duration_ms=duration_ms,
                success_rate=success_rate,
            )

            self.total_batches_processed += 1

            if self.enable_monitoring:
                await record_performance(
                    "batch_processing",
                    duration_ms,
                    success=success_rate
                    > 0.8,  # Consider successful if >80% success rate
                    metadata={
                        "batch_id": batch_id,
                        "batch_size": len(batch_tasks),
                        "success_rate": success_rate,
                        "successful_count": len(successful),
                        "failed_count": len(failed),
                    },
                )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            if self.enable_monitoring:
                await record_performance(
                    "batch_processing", duration_ms, success=False, error_message=str(e)
                )

            self.logger.error(f"Batch processing failed: {e}")
            raise

    async def execute_with_retry(
        self, task: AsyncTask, max_retries: Optional[int] = None
    ) -> Any:
        """
        Execute a task with automatic retry on failure.

        Args:
            task: Task to execute
            max_retries: Maximum number of retries (overrides task setting)

        Returns:
            Task result

        Raises:
            Exception: If all retries fail
        """
        retries = max_retries or task.max_retries
        last_exception = None

        for attempt in range(retries + 1):
            try:
                # Execute task with timeout
                timeout = task.timeout or self.default_timeout

                kwargs = task.kwargs or {}
                result = await asyncio.wait_for(
                    task.coroutine(*task.args, **kwargs), timeout=timeout
                )

                if self.enable_monitoring:
                    await record_performance(
                        f"task_execution_{task.task_id}",
                        0,  # Duration will be calculated by the task itself
                        success=True,
                        metadata={
                            "attempt": attempt + 1,
                            "max_retries": retries,
                            "task_id": task.task_id,
                        },
                    )

                return result

            except asyncio.TimeoutError as e:
                last_exception = e
                self.logger.warning(
                    f"Task {task.task_id} timed out on attempt {attempt + 1}/{retries + 1}"
                )

            except Exception as e:
                last_exception = e
                self.logger.warning(
                    f"Task {task.task_id} failed on attempt {attempt + 1}/{retries + 1}: {e}"
                )

            # Wait before retry with exponential backoff
            if attempt < retries:
                wait_time = min(2**attempt, 30)  # Max 30 seconds
                await asyncio.sleep(wait_time)

        # All retries failed
        if self.enable_monitoring:
            await record_performance(
                f"task_execution_{task.task_id}",
                0,
                success=False,
                error_message=str(last_exception),
                metadata={
                    "attempts": retries + 1,
                    "max_retries": retries,
                    "task_id": task.task_id,
                },
            )

        if last_exception is not None:
            raise last_exception
        else:
            raise RuntimeError("Task failed with unknown error")

    async def _process_task_queue(self):
        """Process tasks from the priority queue."""
        while not self.task_queue.empty():
            try:
                # Get next task (priority queue returns lowest priority first)
                priority, task = await self.task_queue.get()

                # Acquire semaphore
                async with self.semaphore:
                    # Execute task with retry
                    try:
                        result = await self.execute_with_retry(task)
                        self.completed_tasks[task.task_id] = result
                        self.total_tasks_processed += 1

                    except Exception as e:
                        self.failed_tasks[task.task_id] = e
                        self.logger.error(f"Task {task.task_id} failed: {e}")

                # Mark task as done
                self.task_queue.task_done()

            except Exception as e:
                self.logger.error(f"Error processing task queue: {e}")
                break

    async def optimize_context_building(
        self, context_tasks: List[AsyncTask]
    ) -> Dict[str, Any]:
        """
        Optimize context building operations with specialized batching.

        Args:
            context_tasks: List of context building tasks

        Returns:
            Optimized context building results
        """
        start_time = time.time()

        try:
            # Group tasks by type for optimal batching
            grouped_tasks = self._group_tasks_by_type(context_tasks)

            results = {}

            # Process each group with appropriate optimization
            for task_type, tasks in grouped_tasks.items():
                if task_type == "repository_analysis":
                    # Repository analysis can be done in parallel
                    batch_result = await self.execute_batch(
                        tasks, f"repo_analysis_{int(time.time())}"
                    )
                    results[task_type] = batch_result.successful

                elif task_type == "issue_pattern_extraction":
                    # Issue patterns can be processed concurrently
                    concurrent_result = await self.execute_concurrent_tasks(tasks)
                    results[task_type] = [
                        r
                        for r in concurrent_result.values()
                        if not isinstance(r, Exception)
                    ]

                else:
                    # Default batch processing
                    batch_result = await self.execute_batch(
                        tasks, f"{task_type}_{int(time.time())}"
                    )
                    results[task_type] = batch_result.successful

            duration_ms = (time.time() - start_time) * 1000

            if self.enable_monitoring:
                await record_performance(
                    "optimized_context_building",
                    duration_ms,
                    success=True,
                    metadata={
                        "task_groups": len(grouped_tasks),
                        "total_tasks": len(context_tasks),
                        "results_count": sum(len(r) for r in results.values()),
                    },
                )

            return results

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            if self.enable_monitoring:
                await record_performance(
                    "optimized_context_building",
                    duration_ms,
                    success=False,
                    error_message=str(e),
                )

            self.logger.error(f"Optimized context building failed: {e}")
            raise

    def _group_tasks_by_type(
        self, tasks: List[AsyncTask]
    ) -> Dict[str, List[AsyncTask]]:
        """Group tasks by their type for optimal processing."""
        grouped = {}

        for task in tasks:
            # Extract task type from task_id or coroutine name
            task_type = self._extract_task_type(task)

            if task_type not in grouped:
                grouped[task_type] = []

            grouped[task_type].append(task)

        return grouped

    def _extract_task_type(self, task: AsyncTask) -> str:
        """Extract task type from task metadata."""
        # Try to get type from task_id
        if "_" in task.task_id:
            parts = task.task_id.split("_")
            if len(parts) >= 2:
                return parts[0]

        # Try to get type from coroutine name
        if hasattr(task.coroutine, "__name__"):
            coroutine_name = task.coroutine.__name__
            if "_" in coroutine_name:
                parts = coroutine_name.split("_")
                if len(parts) >= 2:
                    return parts[0]

        # Default type
        return "general"

    def get_optimizer_stats(self) -> Dict[str, Any]:
        """Get optimizer performance statistics."""
        return {
            "total_tasks_processed": self.total_tasks_processed,
            "total_batches_processed": self.total_batches_processed,
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "running_tasks": len(self.running_tasks),
            "queue_size": self.task_queue.qsize(),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "batch_size": self.batch_size,
            "default_timeout": self.default_timeout,
        }

    async def cleanup(self):
        """Clean up resources and cancel running tasks."""
        # Cancel all running tasks
        for _task_id, task in self.running_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Clear the task queue
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Clear collections
        self.running_tasks.clear()
        self.completed_tasks.clear()
        self.failed_tasks.clear()

        self.logger.info("Async optimizer cleanup completed")


# Global async optimizer instance
_async_optimizer: Optional[AsyncOptimizer] = None


def get_async_optimizer() -> AsyncOptimizer:
    """Get the global async optimizer instance."""
    global _async_optimizer
    if _async_optimizer is None:
        _async_optimizer = AsyncOptimizer()
    return _async_optimizer


async def cleanup_async_optimizer():
    """Clean up the global async optimizer."""
    global _async_optimizer
    if _async_optimizer is not None:
        await _async_optimizer.cleanup()
        _async_optimizer = None
