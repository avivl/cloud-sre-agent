# gemini_sre_agent/source_control/error_handling.py

"""
Comprehensive error handling and resilience patterns for source control operations.

This module provides circuit breaker patterns, retry mechanisms, and error classification
for robust source control operations.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .models import ProviderHealth


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service is back


class ErrorType(Enum):
    """Classification of error types."""

    # Retryable errors
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    TEMPORARY_ERROR = "temporary_error"
    SERVER_ERROR = "server_error"

    # Non-retryable errors
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    NOT_FOUND_ERROR = "not_found_error"
    VALIDATION_ERROR = "validation_error"
    CONFIGURATION_ERROR = "configuration_error"

    # Provider-specific errors
    GITHUB_API_ERROR = "github_api_error"
    GITHUB_RATE_LIMIT_ERROR = "github_rate_limit_error"
    GITHUB_REPOSITORY_NOT_FOUND = "github_repository_not_found"
    GITHUB_BRANCH_NOT_FOUND = "github_branch_not_found"
    GITHUB_MERGE_CONFLICT = "github_merge_conflict"

    GITLAB_API_ERROR = "gitlab_api_error"
    GITLAB_RATE_LIMIT_ERROR = "gitlab_rate_limit_error"
    GITLAB_PROJECT_NOT_FOUND = "gitlab_project_not_found"
    GITLAB_BRANCH_NOT_FOUND = "gitlab_branch_not_found"
    GITLAB_MERGE_CONFLICT = "gitlab_merge_conflict"

    LOCAL_GIT_ERROR = "local_git_error"
    LOCAL_FILE_ERROR = "local_file_error"
    LOCAL_PERMISSION_ERROR = "local_permission_error"
    LOCAL_REPOSITORY_NOT_FOUND = "local_repository_not_found"

    # Unknown errors
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ErrorClassification:
    """Classification of an error."""

    error_type: ErrorType
    is_retryable: bool
    retry_delay: float
    max_retries: int
    should_open_circuit: bool
    details: Optional[Dict[str, Any]] = None


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    timeout: float = 30.0


@dataclass
class OperationCircuitBreakerConfig:
    """Configuration for operation-specific circuit breakers."""

    # File operations - more lenient
    file_operations: CircuitBreakerConfig = CircuitBreakerConfig(
        failure_threshold=10, recovery_timeout=30.0, success_threshold=2, timeout=60.0
    )

    # Branch operations - moderate
    branch_operations: CircuitBreakerConfig = CircuitBreakerConfig(
        failure_threshold=5, recovery_timeout=45.0, success_threshold=3, timeout=45.0
    )

    # Pull request operations - strict
    pull_request_operations: CircuitBreakerConfig = CircuitBreakerConfig(
        failure_threshold=3, recovery_timeout=90.0, success_threshold=5, timeout=30.0
    )

    # Batch operations - very lenient
    batch_operations: CircuitBreakerConfig = CircuitBreakerConfig(
        failure_threshold=15, recovery_timeout=20.0, success_threshold=2, timeout=120.0
    )

    # Authentication operations - very strict
    auth_operations: CircuitBreakerConfig = CircuitBreakerConfig(
        failure_threshold=2, recovery_timeout=300.0, success_threshold=10, timeout=15.0
    )

    # Default fallback
    default: CircuitBreakerConfig = CircuitBreakerConfig()


@dataclass
class RetryConfig:
    """Configuration for retry mechanism."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True


class CircuitBreaker:
    """Circuit breaker implementation for source control operations."""

    def __init__(self, config: CircuitBreakerConfig, name: str = "default"):
        self.config = config
        self.name = name
        self.logger = logging.getLogger(f"CircuitBreaker.{name}")

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

    def _record_success(self):
        """Record a successful operation."""
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

    def _record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self.logger.warning(
                    f"Circuit breaker {self.name} opened after {self.failure_count} failures"
                )
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0
            self.logger.warning(
                f"Circuit breaker {self.name} reopened after failure in half-open state"
            )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection."""
        self.total_requests += 1

        # Check if circuit should be reset
        if self._should_attempt_reset():
            self.state = CircuitState.HALF_OPEN
            self.success_count = 0
            self.logger.info(f"Circuit breaker {self.name} moved to half-open state")

        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is open")

        try:
            # Execute the function with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs), timeout=self.config.timeout
            )
            self._record_success()
            return result

        except asyncio.TimeoutError:
            self._record_failure()
            raise CircuitBreakerTimeoutError(
                f"Operation timed out after {self.config.timeout}s"
            )
        except Exception as e:
            self._record_failure()
            raise e from None

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


class ErrorClassifier:
    """Classifies errors and determines retry behavior."""

    def __init__(self):
        self.logger = logging.getLogger("ErrorClassifier")

        # Error classification rules
        self.classification_rules: List[
            Callable[[Exception], Optional[ErrorClassification]]
        ] = [
            self._classify_provider_errors,
            self._classify_network_errors,
            self._classify_timeout_errors,
            self._classify_rate_limit_errors,
            self._classify_http_errors,
            self._classify_authentication_errors,
            self._classify_validation_errors,
        ]

    def classify_error(self, error: Exception) -> ErrorClassification:
        """Classify an error and determine retry behavior."""
        for rule in self.classification_rules:
            classification = rule(error)
            if classification:
                return classification

        # Default classification for unknown errors
        return ErrorClassification(
            error_type=ErrorType.UNKNOWN_ERROR,
            is_retryable=False,
            retry_delay=0.0,
            max_retries=0,
            should_open_circuit=True,
            details={"error": str(error), "type": type(error).__name__},
        )

    def _classify_network_errors(
        self, error: Exception
    ) -> Optional[ErrorClassification]:
        """Classify network-related errors."""
        if isinstance(error, (ConnectionError, OSError)):
            return ErrorClassification(
                error_type=ErrorType.NETWORK_ERROR,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=5,
                should_open_circuit=True,
                details={"error": str(error)},
            )
        return None

    def _classify_timeout_errors(
        self, error: Exception
    ) -> Optional[ErrorClassification]:
        """Classify timeout errors."""
        if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            return ErrorClassification(
                error_type=ErrorType.TIMEOUT_ERROR,
                is_retryable=True,
                retry_delay=2.0,
                max_retries=3,
                should_open_circuit=True,
                details={"error": str(error)},
            )
        return None

    def _classify_rate_limit_errors(
        self, error: Exception
    ) -> Optional[ErrorClassification]:
        """Classify rate limit errors."""
        error_str = str(error).lower()
        if any(
            term in error_str for term in ["rate limit", "too many requests", "429"]
        ):
            return ErrorClassification(
                error_type=ErrorType.RATE_LIMIT_ERROR,
                is_retryable=True,
                retry_delay=5.0,
                max_retries=3,
                should_open_circuit=False,  # Don't open circuit for rate limits
                details={"error": str(error)},
            )
        return None

    def _classify_http_errors(self, error: Exception) -> Optional[ErrorClassification]:
        """Classify HTTP status code errors."""
        if hasattr(error, "status"):
            status = getattr(error, "status", None)
            if status is not None and 500 <= status < 600:
                return ErrorClassification(
                    error_type=ErrorType.SERVER_ERROR,
                    is_retryable=True,
                    retry_delay=2.0,
                    max_retries=3,
                    should_open_circuit=True,
                    details={"error": str(error), "status": status},
                )
            elif status == 404:
                return ErrorClassification(
                    error_type=ErrorType.NOT_FOUND_ERROR,
                    is_retryable=False,
                    retry_delay=0.0,
                    max_retries=0,
                    should_open_circuit=False,
                    details={"error": str(error), "status": status},
                )
            elif status in [401, 403]:
                return ErrorClassification(
                    error_type=(
                        ErrorType.AUTHENTICATION_ERROR
                        if status == 401
                        else ErrorType.AUTHORIZATION_ERROR
                    ),
                    is_retryable=False,
                    retry_delay=0.0,
                    max_retries=0,
                    should_open_circuit=False,
                    details={"error": str(error), "status": status},
                )
        return None

    def _classify_authentication_errors(
        self, error: Exception
    ) -> Optional[ErrorClassification]:
        """Classify authentication errors."""
        error_str = str(error).lower()
        if any(
            term in error_str
            for term in ["unauthorized", "authentication", "invalid token", "401"]
        ):
            return ErrorClassification(
                error_type=ErrorType.AUTHENTICATION_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error)},
            )
        return None

    def _classify_validation_errors(
        self, error: Exception
    ) -> Optional[ErrorClassification]:
        """Classify validation errors."""
        if isinstance(error, (ValueError, TypeError)):
            return ErrorClassification(
                error_type=ErrorType.VALIDATION_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error)},
            )
        return None

    def _classify_provider_errors(
        self, error: Exception
    ) -> Optional[ErrorClassification]:
        """Classify provider-specific errors."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        # GitHub-specific errors
        if "github" in error_str or "pygithub" in error_type:
            return self._classify_github_errors(error, error_str)

        # GitLab-specific errors
        elif "gitlab" in error_str or "gitlab" in error_type:
            return self._classify_gitlab_errors(error, error_str)

        # Local Git errors
        elif "git" in error_str or "gitpython" in error_type:
            return self._classify_local_git_errors(error, error_str)

        # Local file system errors
        elif any(
            term in error_str
            for term in ["permission denied", "file not found", "no such file"]
        ):
            return self._classify_local_file_errors(error, error_str)

        return None

    def _classify_github_errors(
        self, error: Exception, error_str: str
    ) -> Optional[ErrorClassification]:
        """Classify GitHub-specific errors."""
        # Rate limiting
        if any(
            term in error_str for term in ["rate limit", "403", "too many requests"]
        ):
            return ErrorClassification(
                error_type=ErrorType.GITHUB_RATE_LIMIT_ERROR,
                is_retryable=True,
                retry_delay=60.0,  # GitHub rate limit reset time
                max_retries=3,
                should_open_circuit=True,
                details={"error": str(error), "provider": "github"},
            )

        # Repository not found
        elif any(term in error_str for term in ["404", "not found", "repository"]):
            return ErrorClassification(
                error_type=ErrorType.GITHUB_REPOSITORY_NOT_FOUND,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "github"},
            )

        # Branch not found
        elif any(term in error_str for term in ["branch", "ref"]):
            return ErrorClassification(
                error_type=ErrorType.GITHUB_BRANCH_NOT_FOUND,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "github"},
            )

        # Merge conflicts
        elif any(term in error_str for term in ["merge conflict", "conflict", "merge"]):
            return ErrorClassification(
                error_type=ErrorType.GITHUB_MERGE_CONFLICT,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "github"},
            )

        # General GitHub API errors
        else:
            return ErrorClassification(
                error_type=ErrorType.GITHUB_API_ERROR,
                is_retryable=True,
                retry_delay=5.0,
                max_retries=3,
                should_open_circuit=True,
                details={"error": str(error), "provider": "github"},
            )

    def _classify_gitlab_errors(
        self, error: Exception, error_str: str
    ) -> Optional[ErrorClassification]:
        """Classify GitLab-specific errors."""
        # Rate limiting
        if any(
            term in error_str for term in ["rate limit", "429", "too many requests"]
        ):
            return ErrorClassification(
                error_type=ErrorType.GITLAB_RATE_LIMIT_ERROR,
                is_retryable=True,
                retry_delay=60.0,
                max_retries=3,
                should_open_circuit=True,
                details={"error": str(error), "provider": "gitlab"},
            )

        # Project not found
        elif any(term in error_str for term in ["404", "not found", "project"]):
            return ErrorClassification(
                error_type=ErrorType.GITLAB_PROJECT_NOT_FOUND,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "gitlab"},
            )

        # Branch not found
        elif any(term in error_str for term in ["branch", "ref"]):
            return ErrorClassification(
                error_type=ErrorType.GITLAB_BRANCH_NOT_FOUND,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "gitlab"},
            )

        # Merge conflicts
        elif any(term in error_str for term in ["merge conflict", "conflict", "merge"]):
            return ErrorClassification(
                error_type=ErrorType.GITLAB_MERGE_CONFLICT,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "gitlab"},
            )

        # General GitLab API errors
        else:
            return ErrorClassification(
                error_type=ErrorType.GITLAB_API_ERROR,
                is_retryable=True,
                retry_delay=5.0,
                max_retries=3,
                should_open_circuit=True,
                details={"error": str(error), "provider": "gitlab"},
            )

    def _classify_local_git_errors(
        self, error: Exception, error_str: str
    ) -> Optional[ErrorClassification]:
        """Classify local Git errors."""
        # Repository not found
        if any(
            term in error_str
            for term in ["not a git repository", "no such file", "repository"]
        ):
            return ErrorClassification(
                error_type=ErrorType.LOCAL_REPOSITORY_NOT_FOUND,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )

        # General Git errors
        else:
            return ErrorClassification(
                error_type=ErrorType.LOCAL_GIT_ERROR,
                is_retryable=True,
                retry_delay=2.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )

    def _classify_local_file_errors(
        self, error: Exception, error_str: str
    ) -> Optional[ErrorClassification]:
        """Classify local file system errors."""
        # Permission errors
        if any(term in error_str for term in ["permission denied", "access denied"]):
            return ErrorClassification(
                error_type=ErrorType.LOCAL_PERMISSION_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )

        # File not found
        elif any(term in error_str for term in ["file not found", "no such file"]):
            return ErrorClassification(
                error_type=ErrorType.LOCAL_FILE_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )

        # General file errors
        else:
            return ErrorClassification(
                error_type=ErrorType.LOCAL_FILE_ERROR,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=1,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )


class RetryManager:
    """Manages retry logic with exponential backoff and jitter."""

    def __init__(self, config: RetryConfig):
        self.config = config
        self.logger = logging.getLogger("RetryManager")
        self.error_classifier = ErrorClassifier()

    async def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with retry logic."""
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return await func(*args, **kwargs)
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
                    raise e from None

                # Calculate delay with jitter
                delay = self._calculate_delay(attempt, classification.retry_delay)

                self.logger.warning(
                    f"Retrying after {delay:.2f}s (attempt {attempt + 1}/{self.config.max_retries + 1}): {e}"
                )

                await asyncio.sleep(delay)

        # All retries exhausted
        if last_exception:
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


class ResilientOperationManager:
    """Manages resilient operations with circuit breaker and retry logic."""

    def __init__(
        self,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        operation_circuit_breaker_config: Optional[
            OperationCircuitBreakerConfig
        ] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.operation_circuit_breaker_config = (
            operation_circuit_breaker_config or OperationCircuitBreakerConfig()
        )
        self.retry_config = retry_config or RetryConfig()

        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_manager = RetryManager(self.retry_config)
        self.logger = logging.getLogger("ResilientOperationManager")

    def _determine_operation_type(self, operation_name: str) -> str:
        """Determine the operation type based on the operation name."""
        operation_name_lower = operation_name.lower()

        # File operations
        if any(
            keyword in operation_name_lower
            for keyword in [
                "file",
                "content",
                "read",
                "write",
                "create_file",
                "update_file",
                "delete_file",
                "get_file",
                "list_files",
            ]
        ):
            return "file_operations"

        # Branch operations
        elif any(
            keyword in operation_name_lower
            for keyword in [
                "branch",
                "create_branch",
                "delete_branch",
                "list_branches",
                "checkout",
                "merge",
                "conflict",
            ]
        ):
            return "branch_operations"

        # Pull request operations
        elif any(
            keyword in operation_name_lower
            for keyword in [
                "pull_request",
                "merge_request",
                "pr",
                "mr",
                "review",
                "approve",
            ]
        ):
            return "pull_request_operations"

        # Batch operations
        elif any(
            keyword in operation_name_lower
            for keyword in ["batch", "bulk", "multiple", "batch_operations"]
        ):
            return "batch_operations"

        # Authentication operations
        elif any(
            keyword in operation_name_lower
            for keyword in ["auth", "login", "credential", "token", "authenticate"]
        ):
            return "auth_operations"

        # Default fallback
        return "default"

    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Get or create a circuit breaker for the given name with operation-specific config."""
        if name not in self.circuit_breakers:
            operation_type = self._determine_operation_type(name)
            config = getattr(
                self.operation_circuit_breaker_config,
                operation_type,
                self.operation_circuit_breaker_config.default,
            )
            self.circuit_breakers[name] = CircuitBreaker(config, name)
            self.logger.debug(
                f"Created circuit breaker for {name} with {operation_type} config"
            )
        return self.circuit_breakers[name]

    async def execute_resilient_operation(
        self, operation_name: str, func: Callable, *args, **kwargs
    ) -> Any:
        """Execute an operation with full resilience (circuit breaker + retry)."""
        circuit_breaker = self.get_circuit_breaker(operation_name)

        try:
            # First try with circuit breaker
            return await circuit_breaker.call(func, *args, **kwargs)
        except (CircuitBreakerOpenError, CircuitBreakerTimeoutError):
            # Circuit breaker is open or timed out, don't retry
            raise
        except Exception:
            # Other errors, try with retry logic
            try:
                return await self.retry_manager.execute_with_retry(
                    func, *args, **kwargs
                )
            except Exception as retry_error:
                # If retry also fails, record the failure in circuit breaker
                circuit_breaker._record_failure()
                raise retry_error

    def get_operation_config(self, operation_name: str) -> CircuitBreakerConfig:
        """Get the circuit breaker configuration for a specific operation."""
        operation_type = self._determine_operation_type(operation_name)
        return getattr(
            self.operation_circuit_breaker_config,
            operation_type,
            self.operation_circuit_breaker_config.default,
        )

    def get_health_status(self) -> ProviderHealth:
        """Get overall health status of all circuit breakers."""
        circuit_stats = []
        overall_healthy = True
        operation_type_stats = {}

        for name, circuit in self.circuit_breakers.items():
            stats = circuit.get_stats()
            operation_type = self._determine_operation_type(name)
            stats["operation_type"] = operation_type
            circuit_stats.append(stats)

            # Track stats by operation type
            if operation_type not in operation_type_stats:
                operation_type_stats[operation_type] = {
                    "total": 0,
                    "healthy": 0,
                    "open_circuits": 0,
                }

            operation_type_stats[operation_type]["total"] += 1
            if circuit.state != CircuitState.OPEN and stats["failure_rate"] <= 0.5:
                operation_type_stats[operation_type]["healthy"] += 1
            else:
                if circuit.state == CircuitState.OPEN:
                    operation_type_stats[operation_type]["open_circuits"] += 1
                overall_healthy = False

        return ProviderHealth(
            status="healthy" if overall_healthy else "unhealthy",
            message=(
                "All circuits healthy"
                if overall_healthy
                else "Some circuits are unhealthy"
            ),
            additional_info={
                "circuit_breakers": circuit_stats,
                "total_circuits": len(self.circuit_breakers),
                "healthy_circuits": sum(
                    1 for stats in circuit_stats if stats["failure_rate"] <= 0.5
                ),
                "operation_type_stats": operation_type_stats,
                "operation_configs": {
                    op_type: {
                        "failure_threshold": getattr(
                            self.operation_circuit_breaker_config,
                            op_type,
                            self.operation_circuit_breaker_config.default,
                        ).failure_threshold,
                        "recovery_timeout": getattr(
                            self.operation_circuit_breaker_config,
                            op_type,
                            self.operation_circuit_breaker_config.default,
                        ).recovery_timeout,
                        "timeout": getattr(
                            self.operation_circuit_breaker_config,
                            op_type,
                            self.operation_circuit_breaker_config.default,
                        ).timeout,
                    }
                    for op_type in [
                        "file_operations",
                        "branch_operations",
                        "pull_request_operations",
                        "batch_operations",
                        "auth_operations",
                        "default",
                    ]
                },
            },
        )


# Custom exceptions
class CircuitBreakerError(Exception):
    """Base class for circuit breaker errors."""

    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Raised when circuit breaker is open."""

    pass


class CircuitBreakerTimeoutError(CircuitBreakerError):
    """Raised when circuit breaker operation times out."""

    pass


# Global instance for easy access with operation-specific configurations
resilient_manager = ResilientOperationManager(
    operation_circuit_breaker_config=OperationCircuitBreakerConfig()
)
