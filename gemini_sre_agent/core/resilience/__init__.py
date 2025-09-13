"""Resilience patterns and fault tolerance for the Gemini SRE Agent.

This module provides comprehensive resilience patterns including:
- Circuit breakers for preventing cascading failures
- Retry mechanisms with exponential backoff
- Timeout handling and management
- Bulkhead isolation for resource protection
- Rate limiting and throttling
- Health checks and monitoring
- Graceful degradation strategies

The main components are:
- CircuitBreaker: Implements the circuit breaker pattern
- RetryHandler: Provides retry logic with various strategies
- TimeoutManager: Handles operation timeouts
- BulkheadIsolator: Implements bulkhead pattern for resource isolation
- RateLimiter: Provides rate limiting capabilities
- HealthChecker: Monitors system health
- ResilienceManager: Orchestrates all resilience patterns

Example usage:
    from gemini_sre_agent.core.resilience import CircuitBreaker, RetryHandler

    # Create a circuit breaker
    breaker = CircuitBreaker(
        failure_threshold=5,
        recovery_timeout=60,
        expected_exception=ConnectionError
    )

    # Use with retry handler
    retry_handler = RetryHandler(
        max_attempts=3,
        backoff_strategy="exponential"
    )

    # Execute operation with resilience
    result = retry_handler.execute(
        breaker.call,
        operation_func,
        *args,
        **kwargs
    )
"""

from .bulkhead_isolator import (
    BulkheadConfig,
    BulkheadError,
    BulkheadIsolator,
    ResourceExhaustedError,
)
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitHalfOpenError,
    CircuitOpenError,
    CircuitState,
)
from .fault_tolerance import (
    FaultToleranceConfig,
    FaultToleranceManager,
    FaultToleranceStrategy,
    fault_tolerance,
    with_circuit_breaker,
    with_retry,
    with_timeout,
)
from .health_checker import (
    HealthCheck,
    HealthChecker,
    HealthCheckError,
    HealthStatus,
    UnhealthyError,
)
from .rate_limiter import RateLimitConfig, RateLimiter, RateLimitError, RateLimitExceededError
from .resilience_manager import (
    OperationFailedError,
    ResilienceConfig,
    ResilienceError,
    ResilienceManager,
)
from .retry_handler import (
    MaxRetriesExceededError,
    RetryConfig,
    RetryError,
    RetryHandler,
    RetryStrategy,
)
from .timeout_manager import OperationTimeoutError, TimeoutConfig, TimeoutError, TimeoutManager

__all__ = [
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitOpenError",
    "CircuitHalfOpenError",

    # Retry Handler
    "RetryHandler",
    "RetryConfig",
    "RetryStrategy",
    "RetryError",
    "MaxRetriesExceededError",

    # Timeout Manager
    "TimeoutManager",
    "TimeoutConfig",
    "TimeoutError",
    "OperationTimeoutError",

    # Bulkhead Isolator
    "BulkheadIsolator",
    "BulkheadConfig",
    "BulkheadError",
    "ResourceExhaustedError",

    # Rate Limiter
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitError",
    "RateLimitExceededError",

    # Health Checker
    "HealthChecker",
    "HealthStatus",
    "HealthCheck",
    "HealthCheckError",
    "UnhealthyError",

    # Resilience Manager
    "ResilienceManager",
    "ResilienceConfig",
    "ResilienceError",
    "OperationFailedError",

    # Fault Tolerance Manager
    "FaultToleranceManager",
    "FaultToleranceConfig",
    "FaultToleranceStrategy",
    "fault_tolerance",
    "with_retry",
    "with_circuit_breaker",
    "with_timeout",
]
