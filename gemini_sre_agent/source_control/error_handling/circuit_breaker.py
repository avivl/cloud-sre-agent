# gemini_sre_agent/source_control/error_handling/circuit_breaker.py

"""
Circuit breaker implementation for source control operations.

This module provides the circuit breaker pattern implementation for handling
failures and preventing cascading failures in distributed systems.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from .core import (
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerTimeoutError,
    CircuitState,
    ErrorType,
)
from .metrics_integration import ErrorHandlingMetrics


class CircuitBreaker:
    """Circuit breaker implementation for source control operations."""

    def __init__(
        self,
        config: CircuitBreakerConfig,
        name: str = "default",
        metrics: Optional[ErrorHandlingMetrics] = None,
    ):
        self.config = config
        self.name = name
        self.logger = logging.getLogger(f"CircuitBreaker.{name}")
        self.metrics = metrics

        # Circuit state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None

        # Statistics
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        if self.state != CircuitState.OPEN:
            return False

        if self.last_failure_time is None:
            return True

        return (
            datetime.now() - self.last_failure_time
        ).total_seconds() >= self.config.recovery_timeout

    async def _record_success(self):
        """Record a successful operation."""
        old_state = self.state
        self.success_count += 1
        self.total_successes += 1
        self.last_success_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.logger.info(
                    f"Circuit breaker {self.name} closed after successful operations"
                )

                # Record state change in metrics
                if self.metrics:
                    await self.metrics.record_circuit_breaker_state_change(
                        self.name, old_state, self.state, "unknown"
                    )

    async def _record_failure(self):
        """Record a failed operation."""
        old_state = self.state
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self.logger.warning(
                    f"Circuit breaker {self.name} opened after {self.failure_count} failures"
                )

                # Record state change in metrics
                if self.metrics:
                    await self.metrics.record_circuit_breaker_state_change(
                        self.name, old_state, self.state, "unknown"
                    )
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0
            self.logger.warning(
                f"Circuit breaker {self.name} reopened after failure in half-open state"
            )

            # Record state change in metrics
            if self.metrics:
                await self.metrics.record_circuit_breaker_state_change(
                    self.name, old_state, self.state, "unknown"
                )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection."""
        start_time = time.time()
        self.total_requests += 1

        # Check if circuit should be reset
        if self._should_attempt_reset():
            old_state = self.state
            self.state = CircuitState.HALF_OPEN
            self.success_count = 0
            self.logger.info(f"Circuit breaker {self.name} moved to half-open state")

            # Record state change in metrics
            if self.metrics:
                await self.metrics.record_circuit_breaker_state_change(
                    self.name, old_state, self.state, "unknown"
                )

        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            if self.metrics:
                duration = time.time() - start_time
                await self.metrics.record_operation_failure(
                    "circuit_breaker_open",
                    "unknown",
                    duration,
                    ErrorType.TEMPORARY_ERROR,
                    0,
                )
            raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is open")

        try:
            # Execute the function with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs), timeout=self.config.timeout
            )
            await self._record_success()

            # Record success in metrics
            if self.metrics:
                duration = time.time() - start_time
                await self.metrics.record_operation_success(
                    "circuit_breaker_call", "unknown", duration, 0
                )

            return result

        except asyncio.TimeoutError as e:
            await self._record_failure()

            # Record timeout in metrics
            if self.metrics:
                duration = time.time() - start_time
                await self.metrics.record_operation_failure(
                    "circuit_breaker_timeout",
                    "unknown",
                    duration,
                    ErrorType.TIMEOUT_ERROR,
                    0,
                )

            raise CircuitBreakerTimeoutError(
                f"Operation timed out after {self.config.timeout}s"
            ) from e
        except Exception as e:
            await self._record_failure()

            # Record failure in metrics
            if self.metrics:
                duration = time.time() - start_time
                await self.metrics.record_operation_failure(
                    "circuit_breaker_failure",
                    "unknown",
                    duration,
                    ErrorType.UNKNOWN_ERROR,
                    0,
                )

            raise e from e

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
            "last_success_time": (
                self.last_success_time.isoformat() if self.last_success_time else None
            ),
            "failure_rate": self.total_failures / max(self.total_requests, 1),
        }
