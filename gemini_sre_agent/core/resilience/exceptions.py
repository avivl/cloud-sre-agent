"""Exceptions for the resilience framework."""

from typing import Any


class ResilienceError(Exception):
    """Base exception for resilience framework errors.
    
    Attributes:
        message: Error message
        context: Additional context information
        original_error: Original exception that caused this error
    """

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None
    ) -> None:
        """Initialize the resilience error.
        
        Args:
            message: Error message
            context: Additional context information
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.original_error = original_error


class CircuitBreakerError(ResilienceError):
    """Base exception for circuit breaker errors."""
    pass


class CircuitOpenError(CircuitBreakerError):
    """Exception raised when circuit breaker is open."""

    def __init__(
        self,
        circuit_name: str,
        failure_count: int,
        failure_threshold: int,
        context: dict[str, Any] | None = None
    ) -> None:
        """Initialize the circuit open error.
        
        Args:
            circuit_name: Name of the circuit breaker
            failure_count: Current failure count
            failure_threshold: Failure threshold
            context: Additional context information
        """
        message = (
            f"Circuit breaker '{circuit_name}' is open. "
            f"Failures: {failure_count}/{failure_threshold}"
        )
        super().__init__(message, context)
        self.circuit_name = circuit_name
        self.failure_count = failure_count
        self.failure_threshold = failure_threshold


class CircuitHalfOpenError(CircuitBreakerError):
    """Exception raised when circuit breaker is half-open."""

    def __init__(
        self,
        circuit_name: str,
        context: dict[str, Any] | None = None
    ) -> None:
        """Initialize the circuit half-open error.
        
        Args:
            circuit_name: Name of the circuit breaker
            context: Additional context information
        """
        message = f"Circuit breaker '{circuit_name}' is half-open"
        super().__init__(message, context)
        self.circuit_name = circuit_name


class RetryError(ResilienceError):
    """Base exception for retry errors."""
    pass


class MaxRetriesExceededError(RetryError):
    """Exception raised when maximum retries are exceeded."""

    def __init__(
        self,
        max_attempts: int,
        last_error: Exception | None = None,
        context: dict[str, Any] | None = None
    ) -> None:
        """Initialize the max retries exceeded error.
        
        Args:
            max_attempts: Maximum number of attempts
            last_error: Last error that occurred
            context: Additional context information
        """
        message = f"Maximum retries ({max_attempts}) exceeded"
        super().__init__(message, context, last_error)
        self.max_attempts = max_attempts
        self.last_error = last_error


class TimeoutError(ResilienceError):
    """Base exception for timeout errors."""
    pass


class OperationTimeoutError(TimeoutError):
    """Exception raised when an operation times out."""

    def __init__(
        self,
        operation_name: str,
        timeout_seconds: float,
        context: dict[str, Any] | None = None
    ) -> None:
        """Initialize the operation timeout error.
        
        Args:
            operation_name: Name of the operation that timed out
            timeout_seconds: Timeout duration in seconds
            context: Additional context information
        """
        message = f"Operation '{operation_name}' timed out after {timeout_seconds}s"
        super().__init__(message, context)
        self.operation_name = operation_name
        self.timeout_seconds = timeout_seconds


class BulkheadError(ResilienceError):
    """Base exception for bulkhead errors."""
    pass


class ResourceExhaustedError(BulkheadError):
    """Exception raised when bulkhead resources are exhausted."""

    def __init__(
        self,
        resource_name: str,
        max_concurrency: int,
        current_usage: int,
        context: dict[str, Any] | None = None
    ) -> None:
        """Initialize the resource exhausted error.
        
        Args:
            resource_name: Name of the resource
            max_concurrency: Maximum concurrency allowed
            current_usage: Current resource usage
            context: Additional context information
        """
        message = (
            f"Resource '{resource_name}' exhausted. "
            f"Usage: {current_usage}/{max_concurrency}"
        )
        super().__init__(message, context)
        self.resource_name = resource_name
        self.max_concurrency = max_concurrency
        self.current_usage = current_usage


class RateLimitError(ResilienceError):
    """Base exception for rate limit errors."""
    pass


class RateLimitExceededError(RateLimitError):
    """Exception raised when rate limit is exceeded."""

    def __init__(
        self,
        rate_limit_name: str,
        limit: int,
        window_seconds: int,
        current_count: int,
        context: dict[str, Any] | None = None
    ) -> None:
        """Initialize the rate limit exceeded error.
        
        Args:
            rate_limit_name: Name of the rate limit
            limit: Rate limit value
            window_seconds: Time window in seconds
            current_count: Current request count
            context: Additional context information
        """
        message = (
            f"Rate limit '{rate_limit_name}' exceeded. "
            f"Limit: {limit}/{window_seconds}s, Current: {current_count}"
        )
        super().__init__(message, context)
        self.rate_limit_name = rate_limit_name
        self.limit = limit
        self.window_seconds = window_seconds
        self.current_count = current_count


class HealthCheckError(ResilienceError):
    """Base exception for health check errors."""
    pass


class UnhealthyError(HealthCheckError):
    """Exception raised when a health check fails."""

    def __init__(
        self,
        check_name: str,
        reason: str,
        context: dict[str, Any] | None = None
    ) -> None:
        """Initialize the unhealthy error.
        
        Args:
            check_name: Name of the health check
            reason: Reason for failure
            context: Additional context information
        """
        message = f"Health check '{check_name}' failed: {reason}"
        super().__init__(message, context)
        self.check_name = check_name
        self.reason = reason


class OperationFailedError(ResilienceError):
    """Exception raised when an operation fails after all resilience patterns."""

    def __init__(
        self,
        operation_name: str,
        failure_reasons: list[str],
        context: dict[str, Any] | None = None
    ) -> None:
        """Initialize the operation failed error.
        
        Args:
            operation_name: Name of the operation
            failure_reasons: List of failure reasons
            context: Additional context information
        """
        message = f"Operation '{operation_name}' failed: {', '.join(failure_reasons)}"
        super().__init__(message, context)
        self.operation_name = operation_name
        self.failure_reasons = failure_reasons
