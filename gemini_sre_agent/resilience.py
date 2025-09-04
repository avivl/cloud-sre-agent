import asyncio
import logging
from asyncio import TimeoutError  # Added for asyncio.wait_for
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, TypeVar

# from hyx.timeout.api import timeout # Removed due to unclear API
from hyx.bulkhead import bulkhead  # type: ignore
from hyx.circuitbreaker import consecutive_breaker as circuitbreaker  # type: ignore
from hyx.circuitbreaker.exceptions import BreakerFailing  # type: ignore
from hyx.ratelimit.api import tokenbucket as ratelimiter  # type: ignore
from hyx.ratelimit.exceptions import RateLimitExceeded  # type: ignore
from hyx.retry import backoffs, retry  # type: ignore
from hyx.retry.exceptions import MaxAttemptsExceeded  # type: ignore

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ResilienceConfig:
    """
    Configuration model for various resilience patterns.
    """

    retry: Dict[str, Any]
    circuit_breaker: Dict[str, Any]
    timeout: float  # Re-added timeout
    bulkhead: Dict[str, Any]
    rate_limit: Dict[str, Any]  # Re-added rate_limit


class HyxResilientClient:
    """
    Comprehensive resilience client using Hyx.
    Provides circuit breaker, retry, timeout, bulkhead, and rate limiting.
    """

    def __init__(self, config: ResilienceConfig):
        """
        Initializes the HyxResilientClient with a given resilience configuration.

        Args:
            config (ResilienceConfig): The configuration for resilience patterns.
        """
        self.config = config
        logger.info("HyxResilientClient initialized with provided configuration.")

        # Initialize Hyx components
        self._circuitbreaker = circuitbreaker(
            failure_threshold=config.circuit_breaker["failure_threshold"],
            recovery_time_secs=config.circuit_breaker["recovery_timeout"],
            # expected_exception=config.circuit_breaker.get('expected_exception', Exception) # Removed
        )
        logger.debug(f"Circuit Breaker configured: {config.circuit_breaker}")

        self._retry = retry(
            attempts=config.retry["max_attempts"],
            backoff=backoffs.expo(
                min_delay_secs=config.retry.get("initial_delay", 1),
                max_delay_secs=config.retry.get("max_delay", 60),
            ),
            on=config.retry.get("expected_exception", Exception),
        )
        logger.debug(f"Retry configured: {config.retry}")

        self._bulkhead = bulkhead(
            max_concurrency=config.bulkhead["limit"],
            max_capacity=config.bulkhead[
                "limit"
            ],  # Changed from config.bulkhead['queue']
        )
        logger.debug(f"Bulkhead configured: {config.bulkhead}")

        self._ratelimiter = ratelimiter(
            max_executions=config.rate_limit["requests_per_second"], per_time_secs=1.0
        )
        logger.debug(f"Rate Limiter configured: {config.rate_limit}")

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

    async def execute(self, operation: Callable[[], Awaitable[T]]) -> T:
        """
        Executes an asynchronous operation with applied resilience patterns.

        Args:
            operation (Callable[[], Awaitable[T]]): The asynchronous function to execute.

        Returns:
            T: The result of the executed operation.

        Raises:
            Exception: Any exception raised by the operation after resilience patterns are applied.
        """
        self._stats["total_operations"] += 1
        logger.info("Executing resilient operation.")

        @self._ratelimiter
        @self._bulkhead
        @self._circuitbreaker
        @self._retry
        async def resilient_operation():
            return await operation()

        try:
            result = await asyncio.wait_for(
                resilient_operation(), timeout=self.config.timeout
            )  # Added asyncio.wait_for
            self._stats["successful_operations"] += 1
            logger.info("Resilient operation completed successfully.")
            return result
        except TimeoutError:  # Catch asyncio.TimeoutError
            self._stats["failed_operations"] += 1
            self._stats["timeouts"] += 1  # Increment timeouts stat
            logger.error(
                f"Resilient operation timed out after {self.config.timeout} seconds."
            )
            raise  # Re-raise the TimeoutError
        except Exception as e:
            self._stats["failed_operations"] += 1
            self._update_error_stats(e)
            logger.error(f"Resilient operation failed: {type(e).__name__} - {e}")
            raise  # Re-raise the exception after updating stats

    def _update_error_stats(self, error: Exception):
        """
        Updates internal statistics based on the type of error encountered.

        Args:
            error (Exception): The exception that occurred.
        """
        if isinstance(error, BreakerFailing):
            self._stats["circuit_breaker_opens"] += 1
            logger.warning("Circuit Breaker is in failing state.")
        elif isinstance(error, MaxAttemptsExceeded):
            self._stats["retries"] += 1
            logger.warning("Max retry attempts exceeded.")
        elif isinstance(error, RateLimitExceeded):
            self._stats["rate_limit_hits"] += 1
            logger.warning("Rate limit exceeded.")
        # Add other specific Hyx exceptions if needed
        else:
            # Fallback for other exceptions, or if the specific Hyx exception is not directly caught
            logger.error(
                f"Unhandled exception in resilient operation: {type(error).__name__} - {error}"
            )
            pass

    def get_health_stats(self) -> Dict[str, Any]:
        """
        Retrieves comprehensive health statistics for the resilient client.

        Returns:
            Dict[str, Any]: A dictionary containing various health metrics.
        """
        return {
            "circuit_breaker": {
                "state": self._circuitbreaker.state.name,
                "failure_count": 0,
            },
            "bulkhead": {
                "active_requests": 0,
                "queued_requests": 0,
                # 'capacity': self._bulkhead._manager.max_capacity # Removed
            },
            "rate_limiter": {
                # 'requests_per_second': self._ratelimiter._manager._token_bucket._max_executions # Removed
            },
            "statistics": self._stats.copy(),
        }


# Environment-specific configuration factory
def create_resilience_config(environment: str = "development") -> ResilienceConfig:
    """
    Creates an environment-appropriate resilience configuration.

    Args:
        environment (str): The desired environment ("production", "staging", or "development").

    Returns:
        ResilienceConfig: The generated resilience configuration.
    """

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
            timeout=30.0,  # Re-added timeout
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
            timeout=25.0,  # Re-added timeout
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
            timeout=15.0,  # Re-added timeout
            bulkhead={"limit": 5, "queue": 5},
            rate_limit={"requests_per_second": 15, "burst_limit": 25},
        ),
    }

    return configs.get(environment, configs["development"])
