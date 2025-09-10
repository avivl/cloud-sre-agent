# gemini_sre_agent/source_control/error_handling/__init__.py

"""
Error handling and resilience patterns package.

This package provides comprehensive error handling, circuit breaker patterns,
retry mechanisms, and error classification for robust source control operations.
"""

from .circuit_breaker import CircuitBreaker
from .core import (
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerOpenError,
    CircuitBreakerTimeoutError,
    CircuitState,
    ErrorClassification,
    ErrorType,
    OperationCircuitBreakerConfig,
    RetryConfig,
)
from .error_classification import ErrorClassifier
from .graceful_degradation import GracefulDegradationManager, create_graceful_degradation_manager
from .health_checks import HealthCheckManager, create_health_check_endpoints
from .metrics_integration import ErrorHandlingMetrics
from .resilient_operations import ResilientOperationManager, resilient_manager
from .retry_manager import RetryManager

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerOpenError",
    "CircuitBreakerTimeoutError",
    "CircuitState",
    "ErrorClassification",
    "ErrorClassifier",
    "ErrorHandlingMetrics",
    "ErrorType",
    "GracefulDegradationManager",
    "HealthCheckManager",
    "OperationCircuitBreakerConfig",
    "ResilientOperationManager",
    "RetryConfig",
    "RetryManager",
    "create_graceful_degradation_manager",
    "create_health_check_endpoints",
    "resilient_manager",
]
