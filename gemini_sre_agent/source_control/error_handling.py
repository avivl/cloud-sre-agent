# gemini_sre_agent/source_control/error_handling.py

"""
Backward-compatible module for error handling components.

This module ensures that existing imports continue to work after the refactoring
into a subpackage.
"""

from .error_handling import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerOpenError,
    CircuitBreakerTimeoutError,
    CircuitState,
    ErrorClassification,
    ErrorClassifier,
    ErrorType,
    OperationCircuitBreakerConfig,
    ResilientOperationManager,
    RetryConfig,
    RetryManager,
    resilient_manager,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerOpenError",
    "CircuitBreakerTimeoutError",
    "CircuitState",
    "ErrorClassification",
    "ErrorClassifier",
    "ErrorType",
    "OperationCircuitBreakerConfig",
    "ResilientOperationManager",
    "RetryConfig",
    "RetryManager",
    "resilient_manager",
]