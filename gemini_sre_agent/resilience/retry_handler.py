"""Retry handler with exponential backoff and jitter."""

import asyncio
import logging
import random
from typing import Any, Callable, Optional

from tenacity import (
    RetryError,
    Retrying,
    after_log,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .error_classifier import ErrorCategory, ErrorClassifier

logger = logging.getLogger(__name__)


class RetryHandler:
    """Handles retries with exponential backoff and jitter."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        jitter_range: float = 0.1,
        error_classifier: Optional[ErrorClassifier] = None,
    ):
        """Initialize the retry handler.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds
            jitter: Whether to add jitter to prevent thundering herd
            jitter_range: Jitter range as fraction of delay (0.0 to 1.0)
            error_classifier: Error classifier for determining retry behavior
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.jitter_range = jitter_range
        self.error_classifier = error_classifier or ErrorClassifier()

        # Statistics
        self._total_attempts = 0
        self._total_retries = 0
        self._total_failures = 0
        self._total_successes = 0

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        retryable_exceptions: Optional[tuple] = None,
        **kwargs,
    ) -> Any:
        """Execute a function with retry logic.

        Args:
            func: Function to execute
            *args: Function arguments
            retryable_exceptions: Tuple of exception types to retry on
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            RetryError: If all retry attempts failed
            Exception: Last exception if retries exhausted
        """
        self._total_attempts += 1

        if retryable_exceptions is None:
            retryable_exceptions = (Exception,)
        
        # Import here to avoid circular imports
        from .circuit_breaker import CircuitBreakerOpenException
        
        # Don't retry circuit breaker exceptions
        if CircuitBreakerOpenException in retryable_exceptions:
            retryable_exceptions = tuple(
                exc for exc in retryable_exceptions 
                if exc != CircuitBreakerOpenException
            )

        last_exception = None
        attempt = 0

        while attempt < self.max_attempts:
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                self._total_successes += 1
                if attempt > 0:
                    logger.info(f"Function succeeded after {attempt + 1} attempts")

                return result

            except retryable_exceptions as e:
                last_exception = e
                attempt += 1

                # Don't retry circuit breaker exceptions
                if isinstance(e, CircuitBreakerOpenException):
                    logger.debug(f"Circuit breaker exception not retryable: {e}")
                    self._total_failures += 1
                    raise e

                # Classify the error
                error_category = self._classify_error(e)

                # Check if error is retryable
                if not self.error_classifier.is_retryable(error_category):
                    logger.debug(f"Error not retryable: {error_category}")
                    self._total_failures += 1
                    raise e

                # Check if we've exhausted retries
                if attempt >= self.max_attempts:
                    logger.error(f"All {self.max_attempts} retry attempts failed")
                    self._total_failures += 1
                    raise e

                # Calculate delay with jitter
                delay = self._calculate_delay(error_category, attempt)

                logger.warning(
                    f"Attempt {attempt} failed with {error_category} error: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )

                self._total_retries += 1
                await asyncio.sleep(delay)

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception

    def _classify_error(self, error: Exception) -> ErrorCategory:
        """Classify an error for retry decision."""
        try:
            return self.error_classifier.classify_error(error)
        except Exception as e:
            logger.warning(f"Error classifying exception: {e}")
            return ErrorCategory.TRANSIENT

    def _calculate_delay(
        self,
        error_category: ErrorCategory,
        attempt: int,
    ) -> float:
        """Calculate delay with exponential backoff and jitter.

        Args:
            error_category: Category of the error
            attempt: Current attempt number (0-based)

        Returns:
            Delay in seconds
        """
        # Get base delay from error classifier
        base_delay = self.error_classifier.get_retry_delay(
            error_category,
            attempt,
            self.base_delay,
            self.max_delay,
        )

        # Add jitter if enabled
        if self.jitter:
            jitter_amount = base_delay * self.jitter_range
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay = max(0.1, base_delay + jitter)  # Minimum 0.1s delay
        else:
            delay = base_delay

        return min(delay, self.max_delay)

    def get_stats(self) -> dict:
        """Get retry handler statistics."""
        success_rate = (
            self._total_successes / self._total_attempts * 100
            if self._total_attempts > 0
            else 0
        )

        return {
            "total_attempts": self._total_attempts,
            "total_retries": self._total_retries,
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
            "success_rate": success_rate,
            "max_attempts": self.max_attempts,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "jitter_enabled": self.jitter,
        }


class TenacityRetryHandler:
    """Retry handler using the tenacity library for advanced retry patterns."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        retryable_exceptions: Optional[tuple] = None,
    ):
        """Initialize the tenacity retry handler.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            jitter: Whether to add jitter
            retryable_exceptions: Exception types to retry on
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or (Exception,)

        # Configure tenacity retry strategy
        self._setup_retry_strategy()

    def _setup_retry_strategy(self) -> None:
        """Setup the tenacity retry strategy."""
        # Base retry configuration
        retry_config = [
            stop_after_attempt(self.max_attempts),
            retry_if_exception_type(self.retryable_exceptions),
            before_sleep_log(logger, logging.WARNING),
            after_log(logger, logging.INFO),
        ]

        # Add exponential backoff with jitter
        if self.jitter:
            retry_config.append(
                wait_exponential(
                    multiplier=self.base_delay,
                    max=self.max_delay,
                    exp_base=2,
                )
            )
        else:
            retry_config.append(
                wait_exponential(
                    multiplier=self.base_delay,
                    max=self.max_delay,
                    exp_base=2,
                )
            )

        self.retry_strategy = Retrying(*retry_config)

    async def _async_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Custom async retry logic for async functions."""
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs)
            except self.retryable_exceptions as e:
                last_exception = e
                if attempt < self.max_attempts - 1:
                    delay = self.base_delay * (2**attempt)
                    if self.jitter:
                        delay += random.uniform(0, delay * 0.1)
                    delay = min(delay, self.max_delay)
                    await asyncio.sleep(delay)
                else:
                    raise e

        if last_exception:
            raise last_exception

    async def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with tenacity retry logic.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            RetryError: If all retry attempts failed
        """
        try:
            if asyncio.iscoroutinefunction(func):
                # For async functions, use our custom retry logic
                return await self._async_retry(func, *args, **kwargs)
            else:
                # For sync functions, use tenacity
                return self.retry_strategy.call(func, *args, **kwargs)  # type: ignore

        except RetryError as e:
            logger.error(f"All retry attempts failed: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in retry handler: {e}")
            raise e

    def get_stats(self) -> dict:
        """Get retry handler statistics."""
        return {
            "max_attempts": self.max_attempts,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "jitter_enabled": self.jitter,
            "retryable_exceptions": [exc.__name__ for exc in self.retryable_exceptions],
        }
