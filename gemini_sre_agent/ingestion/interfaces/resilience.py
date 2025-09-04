# gemini_sre_agent/ingestion/interfaces/resilience.py

"""
Resilience patterns for log ingestion system using working libraries.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, TypeVar

# Try to import resilience libraries
HYX_AVAILABLE = False  # Not using Hyx anymore

try:
    import circuitbreaker

    CIRCUITBREAKER_AVAILABLE = True
except ImportError:
    CIRCUITBREAKER_AVAILABLE = False
    circuitbreaker = None

try:
    import tenacity

    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    tenacity = None


# Define resilience classes at module level
class AsyncCircuitBreaker:
    """Circuit breaker implementation using the circuitbreaker library."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
        **kwargs
    ):
        if CIRCUITBREAKER_AVAILABLE and circuitbreaker:
            self.circuit_breaker = circuitbreaker.CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
            )
        else:
            self.circuit_breaker = None

    def __call__(self, func):
        if self.circuit_breaker:
            # For async functions, we need to handle them differently
            if asyncio.iscoroutinefunction(func):
                async def async_wrapper(*args, **kwargs):
                    return self.circuit_breaker(func)(*args, **kwargs)
                return async_wrapper
            else:
                return self.circuit_breaker(func)
        return func

    @property
    def state(self):
        if self.circuit_breaker:
            return self.circuit_breaker.state
        return "closed"

    @property
    def failure_count(self):
        if self.circuit_breaker:
            return self.circuit_breaker.failure_count
        return 0


class AsyncRetry:
    """Retry implementation using the tenacity library."""

    def __init__(
        self,
        attempts: int = 3,
        backoff=None,
        expected_exception: type = Exception,
        **kwargs
    ):
        if TENACITY_AVAILABLE and tenacity:
            self.retry = tenacity.retry(
                stop=tenacity.stop_after_attempt(attempts),
                wait=backoff or tenacity.wait_exponential(multiplier=1, min=4, max=10),
                retry=tenacity.retry_if_exception_type(expected_exception),
            )
        else:
            self.retry = None

    def __call__(self, func):
        if self.retry:
            return self.retry(func)
        return func


class AsyncTimeout:
    """Timeout implementation using asyncio."""

    def __init__(self, timeout: int):
        self.timeout = timeout

    async def __call__(self, func):
        if asyncio.iscoroutinefunction(func):
            return await asyncio.wait_for(func(), timeout=self.timeout)
        else:
            return func()


class AsyncBulkhead:
    """Simple bulkhead implementation."""

    def __init__(self, capacity: int = 10, queue_size: int = 5, **kwargs):
        self.capacity = capacity
        self.queue_size = queue_size
        self.active_count = 0
        self.semaphore = asyncio.Semaphore(capacity)

    async def __aenter__(self):
        await self.semaphore.acquire()
        self.active_count += 1
        return self

    async def __aexit__(self, *args):
        self.active_count -= 1
        self.semaphore.release()


class AsyncRateLimit:
    """Simple rate limiting implementation."""

    def __init__(self, rate: int = 10, burst: int = 20, **kwargs):
        self.rate = rate
        self.burst = burst
        self.tokens = self.burst
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        async with self.lock:
            now = time.time()
            time_passed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + time_passed * self.rate)
            self.last_update = now

            if self.tokens < 1:
                await asyncio.sleep(1.0 / self.rate)

            self.tokens -= 1
            return self

    async def __aexit__(self, *args):
        pass


T = TypeVar("T")


@dataclass
class ResilienceConfig:
    """Configuration for resilience patterns."""

    retry: Dict[str, Any]
    circuit_breaker: Dict[str, Any]
    timeout: int
    bulkhead: Dict[str, Any]
    rate_limit: Dict[str, Any]


class HyxResilientClient:
    """
    Comprehensive resilience client for log ingestion operations.
    Provides circuit breaker, retry, timeout, bulkhead, and rate limiting.
    """

    def __init__(self, config: ResilienceConfig):
        if not HYX_AVAILABLE:
            import warnings

            warnings.warn(
                "Hyx library not available. Using fallback implementation. "
                "Install with: pip install hyx>=0.4.0",
                UserWarning,
                stacklevel=2,
            )
        self.config = config

        # Initialize resilience components
        self.circuit_breaker = AsyncCircuitBreaker(
            failure_threshold=config.circuit_breaker["failure_threshold"],
            recovery_timeout=config.circuit_breaker["recovery_timeout"],
            expected_exception=config.circuit_breaker.get(
                "expected_exception", Exception
            ),
        )

        self.retry_policy = AsyncRetry(
            attempts=config.retry["max_attempts"],
            backoff=self._create_backoff_strategy(config.retry),
            expected_exception=config.retry.get("expected_exception", Exception),
        )

        self.timeout = AsyncTimeout(config.timeout)

        self.bulkhead = AsyncBulkhead(
            capacity=config.bulkhead["limit"], queue_size=config.bulkhead["queue"]
        )

        self.rate_limiter = AsyncRateLimit(
            rate=config.rate_limit["requests_per_second"],
            burst=config.rate_limit["burst_limit"],
        )

        # Health monitoring
        self._stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "circuit_breaker_opens": 0,
            "rate_limit_hits": 0,
            "timeouts": 0,
            "retries": 0,
        }

    def _create_backoff_strategy(self, retry_config: Dict[str, Any]):
        """Create exponential backoff with jitter"""
        if TENACITY_AVAILABLE and tenacity:
            return tenacity.wait_exponential(
                multiplier=retry_config.get("initial_delay", 1),
                max=retry_config.get("max_delay", 60),
            )
        else:
            # Fallback implementation
            return lambda: retry_config.get("initial_delay", 1)

    async def execute(self, operation: Callable[[], Awaitable[T]]) -> T:
        """
        Execute operation with simplified resilience pipeline.
        For now, we'll use a basic implementation to avoid complex async decorator issues.
        """
        self._stats["total_operations"] += 1

        try:
            # Apply rate limiting and bulkhead
            async with self.rate_limiter:
                async with self.bulkhead:
                    # Simple timeout implementation
                    result = await asyncio.wait_for(operation(), timeout=self.timeout.timeout)

            self._stats["successful_operations"] += 1
            return result

        except Exception as e:
            self._stats["failed_operations"] += 1
            self._update_error_stats(e)
            raise

    def _update_error_stats(self, error: Exception):
        """Update statistics based on error type"""
        error_type = type(error).__name__

        if "CircuitBreaker" in error_type:
            self._stats["circuit_breaker_opens"] += 1
        elif "RateLimit" in error_type:
            self._stats["rate_limit_hits"] += 1
        elif "Timeout" in error_type:
            self._stats["timeouts"] += 1
        elif "Retry" in error_type:
            self._stats["retries"] += 1

    def get_health_stats(self) -> Dict[str, Any]:
        """Get comprehensive health statistics"""
        return {
            "circuit_breaker": {
                "status": self.circuit_breaker.state,
                "failure_count": self.circuit_breaker.failure_count,
                "last_failure_time": getattr(
                    self.circuit_breaker, "last_failure_time", None
                ),
            },
            "bulkhead": {
                "active_requests": self.bulkhead.active_count,
                "queued_requests": self.bulkhead.queue_size,
                "capacity": self.bulkhead.capacity,
            },
            "rate_limiter": {
                "tokens_available": self.rate_limiter.tokens,
                "requests_per_second": self.rate_limiter.rate,
            },
            "statistics": self._stats.copy(),
        }


def create_resilience_config(environment: str = "development") -> ResilienceConfig:
    """Create environment-appropriate resilience configuration"""

    configs = {
        "production": ResilienceConfig(
            retry={
                "max_attempts": 3,
                "initial_delay": 1,
                "max_delay": 10,
                "randomize": True,
                "expected_exception": (ConnectionError, TimeoutError),
            },
            circuit_breaker={
                "failure_threshold": 3,
                "recovery_timeout": 60,
                "expected_exception": (ConnectionError, TimeoutError),
            },
            timeout=30,
            bulkhead={"limit": 10, "queue": 5},
            rate_limit={"requests_per_second": 8, "burst_limit": 15},
        ),
        "staging": ResilienceConfig(
            retry={
                "max_attempts": 3,
                "initial_delay": 1,
                "max_delay": 8,
                "randomize": True,
            },
            circuit_breaker={"failure_threshold": 4, "recovery_timeout": 45},
            timeout=25,
            bulkhead={"limit": 8, "queue": 4},
            rate_limit={"requests_per_second": 10, "burst_limit": 20},
        ),
        "development": ResilienceConfig(
            retry={
                "max_attempts": 2,
                "initial_delay": 0.5,
                "max_delay": 5,
                "randomize": False,
            },
            circuit_breaker={"failure_threshold": 5, "recovery_timeout": 30},
            timeout=15,
            bulkhead={"limit": 5, "queue": 3},
            rate_limit={"requests_per_second": 15, "burst_limit": 25},
        ),
    }

    return configs.get(environment, configs["development"])


class BackpressureManager:
    """Manage backpressure across sources using memory buffering."""

    def __init__(self, max_queue_size: int = 10000):
        self.max_queue_size = max_queue_size
        self.current_queue_size = 0
        self.dropped_items = 0
        self.total_items = 0

    async def can_accept(self) -> bool:
        """Check if system can accept more logs."""
        return self.current_queue_size < self.max_queue_size

    async def increment_queue(self) -> bool:
        """Increment queue size. Returns True if successful, False if dropped."""
        if self.current_queue_size >= self.max_queue_size:
            self.dropped_items += 1
            self.total_items += 1
            return False

        self.current_queue_size += 1
        self.total_items += 1
        return True

    async def decrement_queue(self):
        """Decrement queue size."""
        if self.current_queue_size > 0:
            self.current_queue_size -= 1

    def get_stats(self) -> Dict[str, Any]:
        """Get backpressure statistics."""
        return {
            "current_queue_size": self.current_queue_size,
            "max_queue_size": self.max_queue_size,
            "dropped_items": self.dropped_items,
            "total_items": self.total_items,
            "drop_rate": self.dropped_items / max(self.total_items, 1),
            "utilization": self.current_queue_size / self.max_queue_size,
        }
