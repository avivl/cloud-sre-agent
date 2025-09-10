# gemini_sre_agent/source_control/error_handling/retry_manager.py

"""
Retry management with exponential backoff and jitter.

This module provides intelligent retry logic with configurable backoff strategies
and error-based retry decisions.
"""

import asyncio
import logging
from typing import Any, Callable, Optional

from .core import RetryConfig
from .error_classification import ErrorClassifier
from .metrics_integration import ErrorHandlingMetrics


class RetryManager:
    """Manages retry logic with exponential backoff and jitter."""

    def __init__(self, config: RetryConfig, metrics: Optional[ErrorHandlingMetrics] = None):
        self.config = config
        self.logger = logging.getLogger("RetryManager")
        self.error_classifier = ErrorClassifier()
        self.metrics = metrics

    async def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with retry logic."""
        last_exception = None
        start_time = asyncio.get_event_loop().time()

        for attempt in range(self.config.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                if self.metrics:
                    duration = asyncio.get_event_loop().time() - start_time
                    await self.metrics.record_operation_success(
                        operation_name=func.__name__,
                        provider="unknown",  # We don't have provider info in retry manager
                        duration_seconds=duration,
                        retry_count=attempt,
                    )
                return result
            except Exception as e:
                last_exception = e

                # Classify the error
                classification = self.error_classifier.classify_error(e)

                # Check if we should retry
                if (
                    not classification.is_retryable
                    or attempt >= classification.max_retries
                ):
                    self.logger.error(
                        f"Not retrying error: {e} (attempt {attempt + 1})"
                    )
                    if self.metrics:
                        duration = asyncio.get_event_loop().time() - start_time
                        await self.metrics.record_operation_failure(
                            operation_name=func.__name__,
                            provider="unknown",  # We don't have provider info in retry manager
                            duration_seconds=duration,
                            error_type=classification.error_type,
                            retry_count=attempt,
                        )
                    raise e from None

                # Calculate delay with jitter
                delay = self._calculate_delay(attempt, classification.retry_delay)

                self.logger.warning(
                    f"Retrying after {delay:.2f}s (attempt {attempt + 1}/{self.config.max_retries + 1}): {e}"
                )

                await asyncio.sleep(delay)

        # All retries exhausted
        if last_exception:
            if self.metrics:
                duration = asyncio.get_event_loop().time() - start_time
                # Get classification for the last exception
                classification = self.error_classifier.classify_error(last_exception)
                await self.metrics.record_operation_failure(
                    operation_name=func.__name__,
                    provider="unknown",  # We don't have provider info in retry manager
                    duration_seconds=duration,
                    error_type=classification.error_type,
                    retry_count=self.config.max_retries,
                )
            raise last_exception
        raise RuntimeError("Retry operation failed without exception")

    def _calculate_delay(self, attempt: int, base_delay: float) -> float:
        """Calculate delay with exponential backoff and jitter."""
        # Use the base delay from error classification or config
        delay = base_delay or self.config.base_delay

        # Apply exponential backoff
        delay *= self.config.backoff_factor**attempt

        # Cap at max delay
        delay = min(delay, self.config.max_delay)

        # Add jitter if enabled
        if self.config.jitter:
            import random

            jitter_factor = random.uniform(0.5, 1.5)
            delay *= jitter_factor

        return delay
