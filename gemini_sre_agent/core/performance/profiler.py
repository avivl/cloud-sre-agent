"""Asyncio profiling and async operation monitoring."""

import asyncio
from collections import deque
from collections.abc import Awaitable
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
import threading
import time
from typing import Any

from ..logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProfilerConfig:
    """Configuration for performance profiling.
    
    Attributes:
        max_profiles: Maximum number of profiles to store
        enable_task_tracking: Whether to track asyncio tasks
        enable_coroutine_tracking: Whether to track coroutine execution
        enable_event_loop_tracking: Whether to track event loop metrics
        enable_memory_profiling: Whether to enable memory profiling
        sampling_rate: Rate of profiling sampling (0.0 to 1.0)
    """

    max_profiles: int = 1000
    enable_task_tracking: bool = True
    enable_coroutine_tracking: bool = True
    enable_event_loop_tracking: bool = True
    enable_memory_profiling: bool = True
    sampling_rate: float = 1.0


@dataclass
class OperationProfile:
    """Profile of a single operation.
    
    Attributes:
        operation_name: Name of the operation
        start_time: When the operation started
        end_time: When the operation ended
        duration: Total duration in seconds
        memory_before: Memory usage before operation
        memory_after: Memory usage after operation
        memory_delta: Change in memory usage
        task_count: Number of asyncio tasks created
        coroutine_count: Number of coroutines executed
        event_loop_utilization: Event loop utilization percentage
        tags: Additional metadata tags
    """

    operation_name: str
    start_time: float
    end_time: float
    duration: float
    memory_before: int = 0
    memory_after: int = 0
    memory_delta: int = 0
    task_count: int = 0
    coroutine_count: int = 0
    event_loop_utilization: float = 0.0
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class ProfilerResult:
    """Result of performance profiling.
    
    Attributes:
        total_operations: Total number of profiled operations
        avg_duration: Average operation duration
        min_duration: Minimum operation duration
        max_duration: Maximum operation duration
        total_memory_delta: Total memory change across operations
        avg_memory_delta: Average memory change per operation
        total_tasks: Total number of asyncio tasks created
        total_coroutines: Total number of coroutines executed
        avg_event_loop_utilization: Average event loop utilization
        profiles: List of individual operation profiles
    """

    total_operations: int = 0
    avg_duration: float = 0.0
    min_duration: float = 0.0
    max_duration: float = 0.0
    total_memory_delta: int = 0
    avg_memory_delta: float = 0.0
    total_tasks: int = 0
    total_coroutines: int = 0
    avg_event_loop_utilization: float = 0.0
    profiles: list[OperationProfile] = field(default_factory=list)


class AsyncProfiler:
    """Asyncio-specific profiler for async operations.
    
    Tracks asyncio tasks, coroutines, event loop utilization,
    and async-specific performance metrics.
    """

    def __init__(self, config: ProfilerConfig | None = None):
        """Initialize the async profiler.
        
        Args:
            config: Profiler configuration
        """
        self._config = config or ProfilerConfig()
        self._lock = threading.RLock()
        self._profiles: deque = deque(maxlen=self._config.max_profiles)
        self._active_operations: dict[str, dict[str, Any]] = {}
        self._task_counter: int = 0
        self._coroutine_counter: int = 0
        self._event_loop_metrics: dict[str, Any] = {}

    def _should_sample(self) -> bool:
        """Check if we should sample this operation based on sampling rate.
        
        Returns:
            True if we should sample, False otherwise
        """
        import random
        return random.random() < self._config.sampling_rate

    def _get_memory_usage(self) -> int:
        """Get current memory usage.
        
        Returns:
            Memory usage in bytes
        """
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            return 0
        except Exception:
            return 0

    def _get_event_loop_utilization(self) -> float:
        """Get current event loop utilization.
        
        Returns:
            Event loop utilization as percentage
        """
        try:
            loop = asyncio.get_running_loop()
            if hasattr(loop, "get_debug"):
                # This is a simplified implementation
                # In practice, you'd use more sophisticated event loop monitoring
                return 0.0
            return 0.0
        except Exception:
            return 0.0

    def _track_task_creation(self, task: asyncio.Task) -> None:
        """Track asyncio task creation.
        
        Args:
            task: The created task
        """
        if not self._config.enable_task_tracking:
            return

        with self._lock:
            self._task_counter += 1

    def _track_coroutine_execution(self, coro: Awaitable) -> None:
        """Track coroutine execution.
        
        Args:
            coro: The coroutine being executed
        """
        if not self._config.enable_coroutine_tracking:
            return

        with self._lock:
            self._coroutine_counter += 1

    @asynccontextmanager
    async def profile_async_operation(
        self,
        operation_name: str,
        tags: dict[str, str] | None = None
    ):
        """Profile an async operation.
        
        Args:
            operation_name: Name of the operation
            tags: Additional metadata tags
            
        Yields:
            Operation context
        """
        if not self._should_sample():
            yield
            return

        start_time = time.time()
        memory_before = self._get_memory_usage() if self._config.enable_memory_profiling else 0
        task_count_before = self._task_counter
        coroutine_count_before = self._coroutine_counter

        # Store operation context
        operation_id = f"{operation_name}_{start_time}"
        with self._lock:
            self._active_operations[operation_id] = {
                "name": operation_name,
                "start_time": start_time,
                "memory_before": memory_before,
                "task_count_before": task_count_before,
                "coroutine_count_before": coroutine_count_before,
                "tags": tags or {}
            }

        try:
            yield

        finally:
            end_time = time.time()
            duration = end_time - start_time
            memory_after = self._get_memory_usage() if self._config.enable_memory_profiling else 0
            memory_delta = memory_after - memory_before

            task_count_after = self._task_counter
            coroutine_count_after = self._coroutine_counter

            # Create operation profile
            profile = OperationProfile(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                memory_before=memory_before,
                memory_after=memory_after,
                memory_delta=memory_delta,
                task_count=task_count_after - task_count_before,
                coroutine_count=coroutine_count_after - coroutine_count_before,
                event_loop_utilization=self._get_event_loop_utilization(),
                tags=tags or {}
            )

            # Store profile
            with self._lock:
                self._profiles.append(profile)
                self._active_operations.pop(operation_id, None)

    def get_profiles(self, operation_name: str | None = None) -> list[OperationProfile]:
        """Get profiles for a specific operation or all operations.
        
        Args:
            operation_name: Operation name (optional)
            
        Returns:
            List of operation profiles
        """
        with self._lock:
            if operation_name:
                return [
                    profile for profile in self._profiles
                    if profile.operation_name == operation_name
                ]
            else:
                return list(self._profiles)

    def get_profiler_result(self, operation_name: str | None = None) -> ProfilerResult:
        """Get profiler result for a specific operation or all operations.
        
        Args:
            operation_name: Operation name (optional)
            
        Returns:
            Profiler result
        """
        profiles = self.get_profiles(operation_name)

        if not profiles:
            return ProfilerResult()

        durations = [profile.duration for profile in profiles]
        memory_deltas = [profile.memory_delta for profile in profiles]
        event_loop_utilizations = [profile.event_loop_utilization for profile in profiles]

        total_operations = len(profiles)
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        min_duration = min(durations) if durations else 0.0
        max_duration = max(durations) if durations else 0.0

        total_memory_delta = sum(memory_deltas)
        avg_memory_delta = total_memory_delta / len(memory_deltas) if memory_deltas else 0.0

        total_tasks = sum(profile.task_count for profile in profiles)
        total_coroutines = sum(profile.coroutine_count for profile in profiles)

        avg_event_loop_utilization = (
            sum(event_loop_utilizations) / len(event_loop_utilizations)
            if event_loop_utilizations else 0.0
        )

        return ProfilerResult(
            total_operations=total_operations,
            avg_duration=avg_duration,
            min_duration=min_duration,
            max_duration=max_duration,
            total_memory_delta=total_memory_delta,
            avg_memory_delta=avg_memory_delta,
            total_tasks=total_tasks,
            total_coroutines=total_coroutines,
            avg_event_loop_utilization=avg_event_loop_utilization,
            profiles=profiles
        )

    def reset_profiles(self) -> None:
        """Reset all profiles."""
        with self._lock:
            self._profiles.clear()
            self._active_operations.clear()
            self._task_counter = 0
            self._coroutine_counter = 0
            self._event_loop_metrics.clear()


class PerformanceProfiler:
    """Main performance profiler that combines sync and async profiling.
    
    Provides a unified interface for profiling both synchronous
    and asynchronous operations with comprehensive metrics collection.
    """

    def __init__(self, config: ProfilerConfig | None = None):
        """Initialize the performance profiler.
        
        Args:
            config: Profiler configuration
        """
        self._config = config or ProfilerConfig()
        self._async_profiler = AsyncProfiler(config)
        self._lock = threading.RLock()
        self._sync_profiles: deque = deque(maxlen=self._config.max_profiles)

    @contextmanager
    def profile_operation(
        self,
        operation_name: str,
        tags: dict[str, str] | None = None
    ):
        """Profile a synchronous operation.
        
        Args:
            operation_name: Name of the operation
            tags: Additional metadata tags
            
        Yields:
            Operation context
        """
        if not self._async_profiler._should_sample():
            yield
            return

        start_time = time.time()
        memory_before = (
            self._async_profiler._get_memory_usage() 
            if self._config.enable_memory_profiling else 0
        )

        try:
            yield

        finally:
            end_time = time.time()
            duration = end_time - start_time
            memory_after = (
                self._async_profiler._get_memory_usage() 
                if self._config.enable_memory_profiling else 0
            )
            memory_delta = memory_after - memory_before

            # Create sync operation profile
            profile = OperationProfile(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                memory_before=memory_before,
                memory_after=memory_after,
                memory_delta=memory_delta,
                tags=tags or {}
            )

            # Store profile
            with self._lock:
                self._sync_profiles.append(profile)

    @asynccontextmanager
    async def profile_async_operation(
        self,
        operation_name: str,
        tags: dict[str, str] | None = None
    ):
        """Profile an async operation.
        
        Args:
            operation_name: Name of the operation
            tags: Additional metadata tags
            
        Yields:
            Async operation context
        """
        async with self._async_profiler.profile_async_operation(operation_name, tags):
            yield

    def get_all_profiles(self, operation_name: str | None = None) -> list[OperationProfile]:
        """Get all profiles (sync and async) for a specific operation or all operations.
        
        Args:
            operation_name: Operation name (optional)
            
        Returns:
            List of operation profiles
        """
        with self._lock:
            sync_profiles = list(self._sync_profiles)
            async_profiles = self._async_profiler.get_profiles(operation_name)

            all_profiles = sync_profiles + async_profiles

            if operation_name:
                return [
                    profile for profile in all_profiles
                    if profile.operation_name == operation_name
                ]
            else:
                return all_profiles

    def get_profiler_result(self, operation_name: str | None = None) -> ProfilerResult:
        """Get profiler result for a specific operation or all operations.
        
        Args:
            operation_name: Operation name (optional)
            
        Returns:
            Profiler result
        """
        profiles = self.get_all_profiles(operation_name)

        if not profiles:
            return ProfilerResult()

        durations = [profile.duration for profile in profiles]
        memory_deltas = [profile.memory_delta for profile in profiles]
        event_loop_utilizations = [profile.event_loop_utilization for profile in profiles]

        total_operations = len(profiles)
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        min_duration = min(durations) if durations else 0.0
        max_duration = max(durations) if durations else 0.0

        total_memory_delta = sum(memory_deltas)
        avg_memory_delta = total_memory_delta / len(memory_deltas) if memory_deltas else 0.0

        total_tasks = sum(profile.task_count for profile in profiles)
        total_coroutines = sum(profile.coroutine_count for profile in profiles)

        avg_event_loop_utilization = (
            sum(event_loop_utilizations) / len(event_loop_utilizations)
            if event_loop_utilizations else 0.0
        )

        return ProfilerResult(
            total_operations=total_operations,
            avg_duration=avg_duration,
            min_duration=min_duration,
            max_duration=max_duration,
            total_memory_delta=total_memory_delta,
            avg_memory_delta=avg_memory_delta,
            total_tasks=total_tasks,
            total_coroutines=total_coroutines,
            avg_event_loop_utilization=avg_event_loop_utilization,
            profiles=profiles
        )

    def reset_profiles(self) -> None:
        """Reset all profiles."""
        with self._lock:
            self._sync_profiles.clear()
            self._async_profiler.reset_profiles()

    def get_profiler_summary(self) -> dict[str, Any]:
        """Get a summary of profiler state.
        
        Returns:
            Profiler summary
        """
        with self._lock:
            return {
                "total_sync_profiles": len(self._sync_profiles),
                "total_async_profiles": len(self._async_profiler._profiles),
                "active_operations": len(self._async_profiler._active_operations),
                "task_counter": self._async_profiler._task_counter,
                "coroutine_counter": self._async_profiler._coroutine_counter,
                "config": {
                    "max_profiles": self._config.max_profiles,
                    "enable_task_tracking": self._config.enable_task_tracking,
                    "enable_coroutine_tracking": self._config.enable_coroutine_tracking,
                    "enable_event_loop_tracking": self._config.enable_event_loop_tracking,
                    "enable_memory_profiling": self._config.enable_memory_profiling,
                    "sampling_rate": self._config.sampling_rate
                }
            }
