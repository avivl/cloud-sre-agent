"""Circuit breaker pattern implementation for resilience."""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service is back


class CircuitBreaker:
    """Circuit breaker implementation to prevent cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
        name: Optional[str] = None,
    ):
        """Initialize the circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time in seconds before attempting recovery
            expected_exception: Exception type to count as failures
            name: Name for logging and identification
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name or "CircuitBreaker"

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._success_count = 0

        # Statistics
        self._total_requests = 0
        self._total_failures = 0
        self._total_successes = 0
        self._circuit_opened_count = 0

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    @property
    def success_count(self) -> int:
        """Get current success count."""
        return self._success_count

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenException: If circuit is open
            Exception: Original exception from function
        """
        self._total_requests += 1

        # Check if circuit should be opened
        if (
            self._state == CircuitState.CLOSED
            and self._failure_count >= self.failure_threshold
        ):
            self._open_circuit()

        # Check if circuit should be half-opened for testing
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._half_open_circuit()
            else:
                raise CircuitBreakerOpenException(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Last failure: {self._last_failure_time}"
                )

        # Execute the function
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            self._on_success()
            return result

        except Exception as e:
            if isinstance(e, self.expected_exception):
                self._on_failure()
                raise e
            else:
                # Unexpected exception - don't count as failure
                logger.warning(
                    f"Unexpected exception in circuit breaker '{self.name}': {e}"
                )
                raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return True

        return time.time() - self._last_failure_time >= self.recovery_timeout

    def _open_circuit(self) -> None:
        """Open the circuit breaker."""
        self._state = CircuitState.OPEN
        self._last_failure_time = time.time()
        self._circuit_opened_count += 1

        logger.warning(
            f"Circuit breaker '{self.name}' opened after {self._failure_count} failures"
        )

    def _half_open_circuit(self) -> None:
        """Move circuit to half-open state for testing."""
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0

        logger.info(f"Circuit breaker '{self.name}' moved to HALF_OPEN state")

    def _close_circuit(self) -> None:
        """Close the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0

        logger.info(f"Circuit breaker '{self.name}' closed - service recovered")

    def _on_success(self) -> None:
        """Handle successful operation."""
        self._total_successes += 1

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            # If we have enough successes, close the circuit
            if self._success_count >= 3:  # Require 3 successes to close
                self._close_circuit()
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed operation."""
        self._total_failures += 1
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # If we fail in half-open state, go back to open
            self._open_circuit()

        logger.debug(
            f"Circuit breaker '{self.name}' failure count: {self._failure_count}/"
            f"{self.failure_threshold}"
        )

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

        logger.info(f"Circuit breaker '{self.name}' manually reset")

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        success_rate = (
            self._total_successes / self._total_requests * 100
            if self._total_requests > 0
            else 0
        )

        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_requests": self._total_requests,
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
            "success_rate": success_rate,
            "circuit_opened_count": self._circuit_opened_count,
            "last_failure_time": self._last_failure_time,
            "is_healthy": self._state == CircuitState.CLOSED,
        }


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class CircuitBreakerManager:
    """Manages multiple circuit breakers for different services."""

    def __init__(self):
        """Initialize the circuit breaker manager."""
        self._breakers: Dict[str, CircuitBreaker] = {}

    def get_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker.

        Args:
            name: Circuit breaker name
            failure_threshold: Number of failures before opening
            recovery_timeout: Time before attempting recovery
            expected_exception: Exception type to count as failures

        Returns:
            Circuit breaker instance
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                name=name,
            )

        return self._breakers[name]

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        return {name: breaker.get_stats() for name, breaker in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()

        logger.info("All circuit breakers reset")

    def reset_breaker(self, name: str) -> bool:
        """Reset a specific circuit breaker.

        Args:
            name: Circuit breaker name

        Returns:
            True if breaker was reset, False if not found
        """
        if name in self._breakers:
            self._breakers[name].reset()
            return True

        return False

    def clear_all(self) -> None:
        """Clear all circuit breakers from the manager."""
        self._breakers.clear()
        logger.info("All circuit breakers cleared from manager")
