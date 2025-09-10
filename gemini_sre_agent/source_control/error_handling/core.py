# gemini_sre_agent/source_control/error_handling/core.py

"""
Core error handling types and exceptions.

This module contains the fundamental types, enums, data classes, and exceptions
used throughout the error handling system.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


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
    CONNECTION_RESET_ERROR = "connection_reset_error"
    DNS_ERROR = "dns_error"
    SSL_ERROR = "ssl_error"

    # Non-retryable errors
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    NOT_FOUND_ERROR = "not_found_error"
    VALIDATION_ERROR = "validation_error"
    CONFIGURATION_ERROR = "configuration_error"
    INVALID_INPUT_ERROR = "invalid_input_error"
    PERMISSION_DENIED_ERROR = "permission_denied_error"

    # GitHub-specific errors
    GITHUB_API_ERROR = "github_api_error"
    GITHUB_RATE_LIMIT_ERROR = "github_rate_limit_error"
    GITHUB_REPOSITORY_NOT_FOUND = "github_repository_not_found"
    GITHUB_BRANCH_NOT_FOUND = "github_branch_not_found"
    GITHUB_MERGE_CONFLICT = "github_merge_conflict"
    GITHUB_PULL_REQUEST_ERROR = "github_pull_request_error"
    GITHUB_COMMIT_ERROR = "github_commit_error"
    GITHUB_FILE_ERROR = "github_file_error"
    GITHUB_WEBHOOK_ERROR = "github_webhook_error"
    GITHUB_SSH_ERROR = "github_ssh_error"
    GITHUB_2FA_ERROR = "github_2fa_error"
    GITHUB_MAINTENANCE_ERROR = "github_maintenance_error"

    # GitLab-specific errors
    GITLAB_API_ERROR = "gitlab_api_error"
    GITLAB_RATE_LIMIT_ERROR = "gitlab_rate_limit_error"
    GITLAB_PROJECT_NOT_FOUND = "gitlab_project_not_found"
    GITLAB_BRANCH_NOT_FOUND = "gitlab_branch_not_found"
    GITLAB_MERGE_CONFLICT = "gitlab_merge_conflict"
    GITLAB_MERGE_REQUEST_ERROR = "gitlab_merge_request_error"
    GITLAB_COMMIT_ERROR = "gitlab_commit_error"
    GITLAB_FILE_ERROR = "gitlab_file_error"
    GITLAB_PIPELINE_ERROR = "gitlab_pipeline_error"
    GITLAB_SSH_ERROR = "gitlab_ssh_error"
    GITLAB_MAINTENANCE_ERROR = "gitlab_maintenance_error"

    # Local Git errors
    LOCAL_GIT_ERROR = "local_git_error"
    LOCAL_FILE_ERROR = "local_file_error"
    LOCAL_PERMISSION_ERROR = "local_permission_error"
    LOCAL_REPOSITORY_NOT_FOUND = "local_repository_not_found"
    LOCAL_GIT_COMMAND_ERROR = "local_git_command_error"
    LOCAL_GIT_MERGE_ERROR = "local_git_merge_error"
    LOCAL_GIT_PUSH_ERROR = "local_git_push_error"
    LOCAL_GIT_PULL_ERROR = "local_git_pull_error"
    LOCAL_GIT_CHECKOUT_ERROR = "local_git_checkout_error"
    LOCAL_GIT_BRANCH_ERROR = "local_git_branch_error"
    LOCAL_GIT_COMMIT_ERROR = "local_git_commit_error"
    LOCAL_GIT_STASH_ERROR = "local_git_stash_error"
    LOCAL_GIT_REBASE_ERROR = "local_git_rebase_error"

    # File system errors
    FILE_NOT_FOUND_ERROR = "file_not_found_error"
    FILE_ACCESS_ERROR = "file_access_error"
    FILE_LOCK_ERROR = "file_lock_error"
    DISK_SPACE_ERROR = "disk_space_error"
    FILE_CORRUPTION_ERROR = "file_corruption_error"

    # Network and connectivity errors
    PROXY_ERROR = "proxy_error"
    FIREWALL_ERROR = "firewall_error"
    VPN_ERROR = "vpn_error"
    INTERNET_CONNECTION_ERROR = "internet_connection_error"

    # API and service errors
    API_VERSION_ERROR = "api_version_error"
    API_DEPRECATED_ERROR = "api_deprecated_error"
    API_QUOTA_EXCEEDED_ERROR = "api_quota_exceeded_error"
    API_SERVICE_UNAVAILABLE_ERROR = "api_service_unavailable_error"
    API_MAINTENANCE_ERROR = "api_maintenance_error"

    # Security and compliance errors
    SECURITY_SCAN_ERROR = "security_scan_error"
    COMPLIANCE_ERROR = "compliance_error"
    ENCRYPTION_ERROR = "encryption_error"
    CERTIFICATE_ERROR = "certificate_error"

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
