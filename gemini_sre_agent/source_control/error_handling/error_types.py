# gemini_sre_agent/source_control/error_handling/error_types.py

"""
Hierarchical error type definitions for source control operations.

This module provides organized error type categories using enum classes
to support classification patterns and maintain backward compatibility.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set


class ErrorSeverity(Enum):
    """Error severity levels for classification and handling."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """High-level error categories for classification."""

    NETWORK = "network"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    FILE_SYSTEM = "file_system"
    SECURITY = "security"
    API = "api"
    PROVIDER = "provider"
    LOCAL = "local"
    UNKNOWN = "unknown"


@dataclass
class ErrorTypeMetadata:
    """Metadata for error type classification."""

    severity: ErrorSeverity
    category: ErrorCategory
    is_retryable: bool
    retry_delay: float
    max_retries: int
    description: str
    keywords: List[str]
    patterns: List[str]


class NetworkErrors(Enum):
    """Network-related error types."""

    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    CONNECTION_RESET_ERROR = "connection_reset_error"
    DNS_ERROR = "dns_error"
    SSL_ERROR = "ssl_error"
    PROXY_ERROR = "proxy_error"
    FIREWALL_ERROR = "firewall_error"
    VPN_ERROR = "vpn_error"
    INTERNET_CONNECTION_ERROR = "internet_connection_error"


class AuthenticationErrors(Enum):
    """Authentication-related error types."""

    AUTHENTICATION_ERROR = "authentication_error"
    GITHUB_2FA_ERROR = "github_2fa_error"


class AuthorizationErrors(Enum):
    """Authorization-related error types."""

    AUTHORIZATION_ERROR = "authorization_error"
    PERMISSION_DENIED_ERROR = "permission_denied_error"
    LOCAL_PERMISSION_ERROR = "local_permission_error"


class ValidationErrors(Enum):
    """Validation-related error types."""

    VALIDATION_ERROR = "validation_error"
    INVALID_INPUT_ERROR = "invalid_input_error"
    NOT_FOUND_ERROR = "not_found_error"
    GITHUB_REPOSITORY_NOT_FOUND = "github_repository_not_found"
    GITHUB_BRANCH_NOT_FOUND = "github_branch_not_found"
    GITLAB_PROJECT_NOT_FOUND = "gitlab_project_not_found"
    GITLAB_BRANCH_NOT_FOUND = "gitlab_branch_not_found"
    LOCAL_REPOSITORY_NOT_FOUND = "local_repository_not_found"


class ConfigurationErrors(Enum):
    """Configuration-related error types."""

    CONFIGURATION_ERROR = "configuration_error"


class FileSystemErrors(Enum):
    """File system-related error types."""

    FILE_NOT_FOUND_ERROR = "file_not_found_error"
    FILE_ACCESS_ERROR = "file_access_error"
    FILE_LOCK_ERROR = "file_lock_error"
    DISK_SPACE_ERROR = "disk_space_error"
    FILE_CORRUPTION_ERROR = "file_corruption_error"
    LOCAL_FILE_ERROR = "local_file_error"


class SecurityErrors(Enum):
    """Security-related error types."""

    GITHUB_SSH_ERROR = "github_ssh_error"
    GITLAB_SSH_ERROR = "gitlab_ssh_error"


class ApiErrors(Enum):
    """API-related error types."""

    SERVER_ERROR = "server_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    TEMPORARY_ERROR = "temporary_error"
    GITHUB_API_ERROR = "github_api_error"
    GITHUB_RATE_LIMIT_ERROR = "github_rate_limit_error"
    GITLAB_API_ERROR = "gitlab_api_error"
    GITLAB_RATE_LIMIT_ERROR = "gitlab_rate_limit_error"
    GITHUB_MAINTENANCE_ERROR = "github_maintenance_error"
    GITLAB_MAINTENANCE_ERROR = "gitlab_maintenance_error"


class ProviderErrors(Enum):
    """Provider-specific error types."""

    # GitHub-specific errors
    GITHUB_MERGE_CONFLICT = "github_merge_conflict"
    GITHUB_PULL_REQUEST_ERROR = "github_pull_request_error"
    GITHUB_COMMIT_ERROR = "github_commit_error"
    GITHUB_FILE_ERROR = "github_file_error"
    GITHUB_WEBHOOK_ERROR = "github_webhook_error"

    # GitLab-specific errors
    GITLAB_MERGE_CONFLICT = "gitlab_merge_conflict"
    GITLAB_MERGE_REQUEST_ERROR = "gitlab_merge_request_error"
    GITLAB_COMMIT_ERROR = "gitlab_commit_error"
    GITLAB_FILE_ERROR = "gitlab_file_error"
    GITLAB_PIPELINE_ERROR = "gitlab_pipeline_error"


class LocalErrors(Enum):
    """Local Git operation error types."""

    LOCAL_GIT_ERROR = "local_git_error"
    LOCAL_GIT_COMMAND_ERROR = "local_git_command_error"
    LOCAL_GIT_MERGE_ERROR = "local_git_merge_error"
    LOCAL_GIT_PUSH_ERROR = "local_git_push_error"
    LOCAL_GIT_PULL_ERROR = "local_git_pull_error"
    LOCAL_GIT_CHECKOUT_ERROR = "local_git_checkout_error"
    LOCAL_GIT_BRANCH_ERROR = "local_git_branch_error"
    LOCAL_GIT_COMMIT_ERROR = "local_git_commit_error"
    LOCAL_GIT_STASH_ERROR = "local_git_stash_error"
    LOCAL_GIT_REBASE_ERROR = "local_git_rebase_error"


class UnknownErrors(Enum):
    """Unknown or unclassified error types."""

    UNKNOWN_ERROR = "unknown_error"


class ErrorTypeRegistry:
    """Registry for managing error type metadata and mappings."""

    def __init__(self):
        """Initialize the error type registry."""
        self._metadata: Dict[str, ErrorTypeMetadata] = {}
        self._category_mappings: Dict[ErrorCategory, Set[str]] = {}
        self._severity_mappings: Dict[ErrorSeverity, Set[str]] = {}
        self._retryable_errors: Set[str] = set()
        self._non_retryable_errors: Set[str] = set()
        
        self._initialize_metadata()

    def _initialize_metadata(self) -> None:
        """Initialize error type metadata."""
        # Network errors
        self._add_error_metadata(
            NetworkErrors.NETWORK_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.NETWORK,
            True,
            1.0,
            3,
            "General network connectivity error",
            ["network", "connection", "timeout"],
            [r"network.*error", r"connection.*failed", r"timeout"],
        )

        self._add_error_metadata(
            NetworkErrors.TIMEOUT_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.NETWORK,
            True,
            2.0,
            3,
            "Request timeout error",
            ["timeout", "timed out", "deadline"],
            [r"timeout", r"timed out", r"deadline exceeded"],
        )

        self._add_error_metadata(
            NetworkErrors.CONNECTION_RESET_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.NETWORK,
            True,
            1.5,
            3,
            "Connection was reset by peer",
            ["connection reset", "reset by peer"],
            [r"connection.*reset", r"reset by peer"],
        )

        self._add_error_metadata(
            NetworkErrors.DNS_ERROR,
            ErrorSeverity.HIGH,
            ErrorCategory.NETWORK,
            True,
            5.0,
            2,
            "DNS resolution error",
            ["dns", "name resolution", "hostname"],
            [r"dns.*error", r"name resolution", r"hostname.*not found"],
        )

        self._add_error_metadata(
            NetworkErrors.SSL_ERROR,
            ErrorSeverity.HIGH,
            ErrorCategory.NETWORK,
            True,
            3.0,
            2,
            "SSL/TLS connection error",
            ["ssl", "tls", "certificate"],
            [r"ssl.*error", r"tls.*error", r"certificate.*error"],
        )

        # Authentication errors
        self._add_error_metadata(
            AuthenticationErrors.AUTHENTICATION_ERROR,
            ErrorSeverity.HIGH,
            ErrorCategory.AUTHENTICATION,
            False,
            0.0,
            0,
            "Authentication failed",
            ["auth", "login", "credentials", "token"],
            [r"auth.*failed", r"invalid.*credentials", r"unauthorized"],
        )

        self._add_error_metadata(
            AuthenticationErrors.GITHUB_2FA_ERROR,
            ErrorSeverity.HIGH,
            ErrorCategory.AUTHENTICATION,
            False,
            0.0,
            0,
            "GitHub 2FA authentication required",
            ["2fa", "two factor", "otp", "totp"],
            [r"2fa.*required", r"two.*factor", r"otp.*required"],
        )

        # Authorization errors
        self._add_error_metadata(
            AuthorizationErrors.AUTHORIZATION_ERROR,
            ErrorSeverity.HIGH,
            ErrorCategory.AUTHORIZATION,
            False,
            0.0,
            0,
            "Authorization failed",
            ["forbidden", "access denied", "permission"],
            [r"forbidden", r"access.*denied", r"permission.*denied"],
        )

        self._add_error_metadata(
            AuthorizationErrors.PERMISSION_DENIED_ERROR,
            ErrorSeverity.HIGH,
            ErrorCategory.AUTHORIZATION,
            False,
            0.0,
            0,
            "Permission denied",
            ["permission", "denied", "access"],
            [r"permission.*denied", r"access.*denied"],
        )

        # Validation errors
        self._add_error_metadata(
            ValidationErrors.VALIDATION_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.VALIDATION,
            False,
            0.0,
            0,
            "Input validation error",
            ["validation", "invalid", "bad request"],
            [r"validation.*error", r"invalid.*input", r"bad.*request"],
        )

        self._add_error_metadata(
            ValidationErrors.INVALID_INPUT_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.VALIDATION,
            False,
            0.0,
            0,
            "Invalid input provided",
            ["invalid", "input", "malformed"],
            [r"invalid.*input", r"malformed.*request"],
        )

        self._add_error_metadata(
            ValidationErrors.NOT_FOUND_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.VALIDATION,
            False,
            0.0,
            0,
            "Resource not found",
            ["not found", "404", "missing"],
            [r"not.*found", r"404", r"missing.*resource"],
        )

        # Configuration errors
        self._add_error_metadata(
            ConfigurationErrors.CONFIGURATION_ERROR,
            ErrorSeverity.HIGH,
            ErrorCategory.CONFIGURATION,
            False,
            0.0,
            0,
            "Configuration error",
            ["config", "configuration", "setup"],
            [r"config.*error", r"configuration.*error", r"setup.*error"],
        )

        # File system errors
        self._add_error_metadata(
            FileSystemErrors.FILE_NOT_FOUND_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.FILE_SYSTEM,
            False,
            0.0,
            0,
            "File not found",
            ["file", "not found", "missing"],
            [r"file.*not.*found", r"no.*such.*file"],
        )

        self._add_error_metadata(
            FileSystemErrors.FILE_ACCESS_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.FILE_SYSTEM,
            False,
            0.0,
            0,
            "File access error",
            ["file", "access", "permission"],
            [r"file.*access", r"permission.*denied"],
        )

        self._add_error_metadata(
            FileSystemErrors.DISK_SPACE_ERROR,
            ErrorSeverity.HIGH,
            ErrorCategory.FILE_SYSTEM,
            False,
            0.0,
            0,
            "Insufficient disk space",
            ["disk", "space", "full"],
            [r"disk.*space", r"no.*space", r"device.*full"],
        )

        # Security errors
        self._add_error_metadata(
            SecurityErrors.GITHUB_SSH_ERROR,
            ErrorSeverity.HIGH,
            ErrorCategory.SECURITY,
            True,
            2.0,
            2,
            "GitHub SSH authentication error",
            ["ssh", "github", "key"],
            [r"ssh.*error", r"github.*ssh", r"key.*error"],
        )

        self._add_error_metadata(
            SecurityErrors.GITLAB_SSH_ERROR,
            ErrorSeverity.HIGH,
            ErrorCategory.SECURITY,
            True,
            2.0,
            2,
            "GitLab SSH authentication error",
            ["ssh", "gitlab", "key"],
            [r"ssh.*error", r"gitlab.*ssh", r"key.*error"],
        )

        # API errors
        self._add_error_metadata(
            ApiErrors.SERVER_ERROR,
            ErrorSeverity.HIGH,
            ErrorCategory.API,
            True,
            3.0,
            3,
            "Server error",
            ["server", "error", "500"],
            [r"server.*error", r"500", r"internal.*error"],
        )

        self._add_error_metadata(
            ApiErrors.RATE_LIMIT_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.API,
            True,
            60.0,
            1,
            "Rate limit exceeded",
            ["rate", "limit", "quota", "throttle"],
            [r"rate.*limit", r"quota.*exceeded", r"throttle"],
        )

        self._add_error_metadata(
            ApiErrors.TEMPORARY_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.API,
            True,
            2.0,
            3,
            "Temporary service error",
            ["temporary", "service", "unavailable"],
            [r"temporary", r"service.*unavailable", r"try.*again"],
        )

        # Provider errors
        self._add_error_metadata(
            ProviderErrors.GITHUB_MERGE_CONFLICT,
            ErrorSeverity.MEDIUM,
            ErrorCategory.PROVIDER,
            False,
            0.0,
            0,
            "GitHub merge conflict",
            ["merge", "conflict", "github"],
            [r"merge.*conflict", r"conflict.*github"],
        )

        self._add_error_metadata(
            ProviderErrors.GITLAB_MERGE_CONFLICT,
            ErrorSeverity.MEDIUM,
            ErrorCategory.PROVIDER,
            False,
            0.0,
            0,
            "GitLab merge conflict",
            ["merge", "conflict", "gitlab"],
            [r"merge.*conflict", r"conflict.*gitlab"],
        )

        # Local errors
        self._add_error_metadata(
            LocalErrors.LOCAL_GIT_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.LOCAL,
            False,
            0.0,
            0,
            "Local Git operation error",
            ["git", "local", "command"],
            [r"git.*error", r"local.*git"],
        )

        self._add_error_metadata(
            LocalErrors.LOCAL_GIT_COMMAND_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.LOCAL,
            False,
            0.0,
            0,
            "Local Git command error",
            ["git", "command", "failed"],
            [r"git.*command", r"command.*failed"],
        )

        # Unknown errors
        self._add_error_metadata(
            UnknownErrors.UNKNOWN_ERROR,
            ErrorSeverity.MEDIUM,
            ErrorCategory.UNKNOWN,
            False,
            0.0,
            0,
            "Unknown error type",
            ["unknown", "unexpected", "error"],
            [r"unknown", r"unexpected", r"error"],
        )

    def _add_error_metadata(
        self,
        error_enum: Enum,
        severity: ErrorSeverity,
        category: ErrorCategory,
        is_retryable: bool,
        retry_delay: float,
        max_retries: int,
        description: str,
        keywords: List[str],
        patterns: List[str],
    ) -> None:
        """Add error type metadata to the registry."""
        error_value = error_enum.value
        
        self._metadata[error_value] = ErrorTypeMetadata(
            severity=severity,
            category=category,
            is_retryable=is_retryable,
            retry_delay=retry_delay,
            max_retries=max_retries,
            description=description,
            keywords=keywords,
            patterns=patterns,
        )

        # Update category mappings
        if category not in self._category_mappings:
            self._category_mappings[category] = set()
        self._category_mappings[category].add(error_value)

        # Update severity mappings
        if severity not in self._severity_mappings:
            self._severity_mappings[severity] = set()
        self._severity_mappings[severity].add(error_value)

        # Update retryable mappings
        if is_retryable:
            self._retryable_errors.add(error_value)
        else:
            self._non_retryable_errors.add(error_value)

    def get_metadata(self, error_type: str) -> Optional[ErrorTypeMetadata]:
        """Get metadata for a specific error type."""
        return self._metadata.get(error_type)

    def get_errors_by_category(self, category: ErrorCategory) -> Set[str]:
        """Get all error types in a specific category."""
        return self._category_mappings.get(category, set())

    def get_errors_by_severity(self, severity: ErrorSeverity) -> Set[str]:
        """Get all error types with a specific severity."""
        return self._severity_mappings.get(severity, set())

    def get_retryable_errors(self) -> Set[str]:
        """Get all retryable error types."""
        return self._retryable_errors.copy()

    def get_non_retryable_errors(self) -> Set[str]:
        """Get all non-retryable error types."""
        return self._non_retryable_errors.copy()

    def get_all_error_types(self) -> Set[str]:
        """Get all registered error types."""
        return set(self._metadata.keys())

    def get_error_categories(self) -> List[ErrorCategory]:
        """Get all error categories."""
        return list(ErrorCategory)

    def get_error_severities(self) -> List[ErrorSeverity]:
        """Get all error severities."""
        return list(ErrorSeverity)


# Global registry instance
error_type_registry = ErrorTypeRegistry()


def get_error_metadata(error_type: str) -> Optional[ErrorTypeMetadata]:
    """Get error type metadata from the global registry."""
    return error_type_registry.get_metadata(error_type)


def get_errors_by_category(category: ErrorCategory) -> Set[str]:
    """Get error types by category from the global registry."""
    return error_type_registry.get_errors_by_category(category)


def get_errors_by_severity(severity: ErrorSeverity) -> Set[str]:
    """Get error types by severity from the global registry."""
    return error_type_registry.get_errors_by_severity(severity)


def is_retryable_error(error_type: str) -> bool:
    """Check if an error type is retryable."""
    metadata = get_error_metadata(error_type)
    return metadata.is_retryable if metadata else False


def get_retry_delay(error_type: str) -> float:
    """Get retry delay for an error type."""
    metadata = get_error_metadata(error_type)
    return metadata.retry_delay if metadata else 0.0


def get_max_retries(error_type: str) -> int:
    """Get maximum retries for an error type."""
    metadata = get_error_metadata(error_type)
    return metadata.max_retries if metadata else 0


def get_error_severity(error_type: str) -> Optional[ErrorSeverity]:
    """Get severity for an error type."""
    metadata = get_error_metadata(error_type)
    return metadata.severity if metadata else None


def get_error_category(error_type: str) -> Optional[ErrorCategory]:
    """Get category for an error type."""
    metadata = get_error_metadata(error_type)
    return metadata.category if metadata else None
