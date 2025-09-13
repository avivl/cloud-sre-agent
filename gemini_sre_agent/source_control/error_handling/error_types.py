# gemini_sre_agent/source_control/error_handling/error_types.py

"""
Hierarchical error type definitions for comprehensive error classification.

This module provides a structured hierarchy of error types organized by category,
enabling more sophisticated error classification and handling strategies.
"""

from dataclasses import dataclass
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels for classification and handling."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """High-level error categories for organizational purposes."""

    NETWORK = "network"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    PROVIDER = "provider"
    FILE_SYSTEM = "file_system"
    SECURITY = "security"
    API = "api"
    UNKNOWN = "unknown"


@dataclass
class ErrorTypeMetadata:
    """Metadata associated with an error type."""

    category: ErrorCategory
    severity: ErrorSeverity
    is_retryable: bool
    retry_delay: float
    max_retries: int
    should_open_circuit: bool
    description: str
    keywords: list[str]
    patterns: list[str]


class NetworkErrors(Enum):
    """Network-related error types."""

    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    CONNECTION_RESET_ERROR = "connection_reset_error"
    DNS_ERROR = "dns_error"
    PROXY_ERROR = "proxy_error"
    FIREWALL_ERROR = "firewall_error"
    VPN_ERROR = "vpn_error"
    INTERNET_CONNECTION_ERROR = "internet_connection_error"


class AuthenticationErrors(Enum):
    """Authentication-related error types."""

    AUTHENTICATION_ERROR = "authentication_error"
    INVALID_TOKEN_ERROR = "invalid_token_error"
    TOKEN_EXPIRED_ERROR = "token_expired_error"
    CREDENTIALS_INVALID_ERROR = "credentials_invalid_error"
    TWO_FACTOR_AUTH_ERROR = "two_factor_auth_error"


class AuthorizationErrors(Enum):
    """Authorization-related error types."""

    AUTHORIZATION_ERROR = "authorization_error"
    PERMISSION_DENIED_ERROR = "permission_denied_error"
    INSUFFICIENT_PRIVILEGES_ERROR = "insufficient_privileges_error"
    ACCESS_FORBIDDEN_ERROR = "access_forbidden_error"


class ValidationErrors(Enum):
    """Validation-related error types."""

    VALIDATION_ERROR = "validation_error"
    INVALID_INPUT_ERROR = "invalid_input_error"
    CONFIGURATION_ERROR = "configuration_error"
    SCHEMA_VALIDATION_ERROR = "schema_validation_error"
    PARAMETER_MISSING_ERROR = "parameter_missing_error"


class GitHubErrors(Enum):
    """GitHub-specific error types."""

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


class GitLabErrors(Enum):
    """GitLab-specific error types."""

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


class LocalGitErrors(Enum):
    """Local Git operation error types."""

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


class FileSystemErrors(Enum):
    """File system-related error types."""

    FILE_NOT_FOUND_ERROR = "file_not_found_error"
    FILE_ACCESS_ERROR = "file_access_error"
    FILE_LOCK_ERROR = "file_lock_error"
    DISK_SPACE_ERROR = "disk_space_error"
    FILE_CORRUPTION_ERROR = "file_corruption_error"
    PERMISSION_DENIED_ERROR = "permission_denied_error"


class SecurityErrors(Enum):
    """Security-related error types."""

    SSL_ERROR = "ssl_error"
    CERTIFICATE_ERROR = "certificate_error"
    ENCRYPTION_ERROR = "encryption_error"
    SECURITY_SCAN_ERROR = "security_scan_error"
    COMPLIANCE_ERROR = "compliance_error"


class APIErrors(Enum):
    """API and service-related error types."""

    API_VERSION_ERROR = "api_version_error"
    API_DEPRECATED_ERROR = "api_deprecated_error"
    API_QUOTA_EXCEEDED_ERROR = "api_quota_exceeded_error"
    API_SERVICE_UNAVAILABLE_ERROR = "api_service_unavailable_error"
    API_MAINTENANCE_ERROR = "api_maintenance_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    SERVER_ERROR = "server_error"
    NOT_FOUND_ERROR = "not_found_error"


class UnknownErrors(Enum):
    """Unknown or unclassified error types."""

    UNKNOWN_ERROR = "unknown_error"
    TEMPORARY_ERROR = "temporary_error"


class ErrorTypeRegistry:
    """Registry for managing error type metadata and classification."""

    def __init__(self) -> None:
        self._metadata: dict[str, ErrorTypeMetadata] = {}
        self._category_mappings: dict[ErrorCategory, set[str]] = {
            category: set() for category in ErrorCategory
        }
        self._initialize_metadata()

    def _initialize_metadata(self) -> None:
        """Initialize error type metadata for all error types."""

        # Network errors
        network_errors = [
            (
                NetworkErrors.NETWORK_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                5,
                True,
                "General network connectivity issue",
                ["network", "connection"],
                ["connection.*error", "network.*unavailable"],
            ),
            (
                NetworkErrors.TIMEOUT_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                2.0,
                3,
                True,
                "Operation timed out",
                ["timeout", "timed out"],
                ["timeout", "timed.*out"],
            ),
            (
                NetworkErrors.CONNECTION_RESET_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                5,
                True,
                "Connection was reset by peer",
                ["connection reset", "reset"],
                ["connection.*reset", "reset.*by.*peer"],
            ),
            (
                NetworkErrors.DNS_ERROR,
                ErrorSeverity.HIGH,
                True,
                5.0,
                3,
                True,
                "DNS resolution failed",
                ["dns", "resolution"],
                ["dns.*error", "name.*resolution"],
            ),
            (
                NetworkErrors.PROXY_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                2.0,
                3,
                True,
                "Proxy server error",
                ["proxy", "gateway"],
                ["proxy.*error", "gateway.*error"],
            ),
            (
                NetworkErrors.FIREWALL_ERROR,
                ErrorSeverity.HIGH,
                True,
                10.0,
                2,
                True,
                "Firewall blocking connection",
                ["firewall", "blocked"],
                ["firewall", "blocked.*connection"],
            ),
            (
                NetworkErrors.VPN_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                5.0,
                3,
                True,
                "VPN connection issue",
                ["vpn", "tunnel"],
                ["vpn.*error", "tunnel.*error"],
            ),
            (
                NetworkErrors.INTERNET_CONNECTION_ERROR,
                ErrorSeverity.HIGH,
                True,
                5.0,
                3,
                True,
                "No internet connection",
                ["internet", "offline"],
                ["no.*internet", "offline"],
            ),
        ]

        for (
            error_type,
            severity,
            retryable,
            delay,
            max_retries,
            circuit,
            desc,
            keywords,
            patterns,
        ) in network_errors:
            self._register_error_type(
                error_type.value,
                ErrorCategory.NETWORK,
                severity,
                retryable,
                delay,
                max_retries,
                circuit,
                desc,
                keywords,
                patterns,
            )

        # Authentication errors
        auth_errors = [
            (
                AuthenticationErrors.AUTHENTICATION_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Authentication failed",
                ["auth", "login", "unauthorized"],
                ["unauthorized", "authentication.*failed"],
            ),
            (
                AuthenticationErrors.INVALID_TOKEN_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Invalid authentication token",
                ["token", "invalid"],
                ["invalid.*token", "token.*invalid"],
            ),
            (
                AuthenticationErrors.TOKEN_EXPIRED_ERROR,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "Authentication token expired",
                ["expired", "token"],
                ["token.*expired", "expired.*token"],
            ),
            (
                AuthenticationErrors.CREDENTIALS_INVALID_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Invalid credentials provided",
                ["credentials", "invalid"],
                ["invalid.*credentials", "credentials.*invalid"],
            ),
            (
                AuthenticationErrors.TWO_FACTOR_AUTH_ERROR,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "Two-factor authentication required",
                ["2fa", "two-factor", "otp"],
                ["2fa", "two.*factor", "otp"],
            ),
        ]

        for (
            error_type,
            severity,
            retryable,
            delay,
            max_retries,
            circuit,
            desc,
            keywords,
            patterns,
        ) in auth_errors:
            self._register_error_type(
                error_type.value,
                ErrorCategory.AUTHENTICATION,
                severity,
                retryable,
                delay,
                max_retries,
                circuit,
                desc,
                keywords,
                patterns,
            )

        # Authorization errors
        authz_errors = [
            (
                AuthorizationErrors.AUTHORIZATION_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Authorization failed",
                ["authorization", "forbidden"],
                ["authorization.*failed", "forbidden"],
            ),
            (
                AuthorizationErrors.PERMISSION_DENIED_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Permission denied",
                ["permission", "denied"],
                ["permission.*denied", "access.*denied"],
            ),
            (
                AuthorizationErrors.INSUFFICIENT_PRIVILEGES_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Insufficient privileges",
                ["privileges", "insufficient"],
                ["insufficient.*privileges", "privileges.*insufficient"],
            ),
            (
                AuthorizationErrors.ACCESS_FORBIDDEN_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Access forbidden",
                ["forbidden", "access"],
                ["access.*forbidden", "forbidden.*access"],
            ),
        ]

        for (
            error_type,
            severity,
            retryable,
            delay,
            max_retries,
            circuit,
            desc,
            keywords,
            patterns,
        ) in authz_errors:
            self._register_error_type(
                error_type.value,
                ErrorCategory.AUTHORIZATION,
                severity,
                retryable,
                delay,
                max_retries,
                circuit,
                desc,
                keywords,
                patterns,
            )

        # Validation errors
        validation_errors = [
            (
                ValidationErrors.VALIDATION_ERROR,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "Validation failed",
                ["validation", "invalid"],
                ["validation.*failed", "invalid.*input"],
            ),
            (
                ValidationErrors.INVALID_INPUT_ERROR,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "Invalid input provided",
                ["input", "invalid"],
                ["invalid.*input", "input.*invalid"],
            ),
            (
                ValidationErrors.CONFIGURATION_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Configuration error",
                ["config", "configuration"],
                ["configuration.*error", "config.*error"],
            ),
            (
                ValidationErrors.SCHEMA_VALIDATION_ERROR,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "Schema validation failed",
                ["schema", "validation"],
                ["schema.*validation", "validation.*schema"],
            ),
            (
                ValidationErrors.PARAMETER_MISSING_ERROR,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "Required parameter missing",
                ["parameter", "missing"],
                ["parameter.*missing", "missing.*parameter"],
            ),
        ]

        for (
            error_type,
            severity,
            retryable,
            delay,
            max_retries,
            circuit,
            desc,
            keywords,
            patterns,
        ) in validation_errors:
            self._register_error_type(
                error_type.value,
                ErrorCategory.VALIDATION,
                severity,
                retryable,
                delay,
                max_retries,
                circuit,
                desc,
                keywords,
                patterns,
            )

        # GitHub errors
        github_errors = [
            (
                GitHubErrors.GITHUB_API_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                5.0,
                3,
                True,
                "GitHub API error",
                ["github", "api"],
                ["github.*api", "api.*github"],
            ),
            (
                GitHubErrors.GITHUB_RATE_LIMIT_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                60.0,
                3,
                True,
                "GitHub rate limit exceeded",
                ["github", "rate", "limit"],
                ["rate.*limit", "too.*many.*requests"],
            ),
            (
                GitHubErrors.GITHUB_REPOSITORY_NOT_FOUND,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "GitHub repository not found",
                ["github", "repository", "not found"],
                ["repository.*not.*found", "404"],
            ),
            (
                GitHubErrors.GITHUB_BRANCH_NOT_FOUND,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "GitHub branch not found",
                ["github", "branch", "not found"],
                ["branch.*not.*found", "ref.*not.*found"],
            ),
            (
                GitHubErrors.GITHUB_MERGE_CONFLICT,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "GitHub merge conflict",
                ["github", "merge", "conflict"],
                ["merge.*conflict", "conflict.*merge"],
            ),
            (
                GitHubErrors.GITHUB_PULL_REQUEST_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                2.0,
                2,
                False,
                "GitHub pull request error",
                ["github", "pull", "request"],
                ["pull.*request", "pr.*error"],
            ),
            (
                GitHubErrors.GITHUB_COMMIT_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                2,
                False,
                "GitHub commit error",
                ["github", "commit"],
                ["commit.*error", "sha.*error"],
            ),
            (
                GitHubErrors.GITHUB_FILE_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                2,
                False,
                "GitHub file error",
                ["github", "file"],
                ["file.*error", "content.*error"],
            ),
            (
                GitHubErrors.GITHUB_WEBHOOK_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                5.0,
                2,
                False,
                "GitHub webhook error",
                ["github", "webhook"],
                ["webhook.*error", "hook.*error"],
            ),
            (
                GitHubErrors.GITHUB_SSH_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "GitHub SSH error",
                ["github", "ssh"],
                ["ssh.*error", "key.*error"],
            ),
            (
                GitHubErrors.GITHUB_2FA_ERROR,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "GitHub 2FA required",
                ["github", "2fa"],
                ["2fa", "two.*factor"],
            ),
            (
                GitHubErrors.GITHUB_MAINTENANCE_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                30.0,
                3,
                True,
                "GitHub maintenance mode",
                ["github", "maintenance"],
                ["maintenance", "scheduled.*downtime"],
            ),
        ]

        for (
            error_type,
            severity,
            retryable,
            delay,
            max_retries,
            circuit,
            desc,
            keywords,
            patterns,
        ) in github_errors:
            self._register_error_type(
                error_type.value,
                ErrorCategory.PROVIDER,
                severity,
                retryable,
                delay,
                max_retries,
                circuit,
                desc,
                keywords,
                patterns,
            )

        # GitLab errors
        gitlab_errors = [
            (
                GitLabErrors.GITLAB_API_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                5.0,
                3,
                True,
                "GitLab API error",
                ["gitlab", "api"],
                ["gitlab.*api", "api.*gitlab"],
            ),
            (
                GitLabErrors.GITLAB_RATE_LIMIT_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                60.0,
                3,
                True,
                "GitLab rate limit exceeded",
                ["gitlab", "rate", "limit"],
                ["rate.*limit", "too.*many.*requests"],
            ),
            (
                GitLabErrors.GITLAB_PROJECT_NOT_FOUND,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "GitLab project not found",
                ["gitlab", "project", "not found"],
                ["project.*not.*found", "404"],
            ),
            (
                GitLabErrors.GITLAB_BRANCH_NOT_FOUND,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "GitLab branch not found",
                ["gitlab", "branch", "not found"],
                ["branch.*not.*found", "ref.*not.*found"],
            ),
            (
                GitLabErrors.GITLAB_MERGE_CONFLICT,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "GitLab merge conflict",
                ["gitlab", "merge", "conflict"],
                ["merge.*conflict", "conflict.*merge"],
            ),
            (
                GitLabErrors.GITLAB_MERGE_REQUEST_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                2.0,
                2,
                False,
                "GitLab merge request error",
                ["gitlab", "merge", "request"],
                ["merge.*request", "mr.*error"],
            ),
            (
                GitLabErrors.GITLAB_COMMIT_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                2,
                False,
                "GitLab commit error",
                ["gitlab", "commit"],
                ["commit.*error", "sha.*error"],
            ),
            (
                GitLabErrors.GITLAB_FILE_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                2,
                False,
                "GitLab file error",
                ["gitlab", "file"],
                ["file.*error", "content.*error"],
            ),
            (
                GitLabErrors.GITLAB_PIPELINE_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                5.0,
                2,
                False,
                "GitLab pipeline error",
                ["gitlab", "pipeline"],
                ["pipeline.*error", "ci.*error"],
            ),
            (
                GitLabErrors.GITLAB_SSH_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "GitLab SSH error",
                ["gitlab", "ssh"],
                ["ssh.*error", "key.*error"],
            ),
            (
                GitLabErrors.GITLAB_MAINTENANCE_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                30.0,
                3,
                True,
                "GitLab maintenance mode",
                ["gitlab", "maintenance"],
                ["maintenance", "scheduled.*downtime"],
            ),
        ]

        for (
            error_type,
            severity,
            retryable,
            delay,
            max_retries,
            circuit,
            desc,
            keywords,
            patterns,
        ) in gitlab_errors:
            self._register_error_type(
                error_type.value,
                ErrorCategory.PROVIDER,
                severity,
                retryable,
                delay,
                max_retries,
                circuit,
                desc,
                keywords,
                patterns,
            )

        # Local Git errors
        local_git_errors = [
            (
                LocalGitErrors.LOCAL_GIT_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                2.0,
                2,
                False,
                "Local Git error",
                ["git", "local"],
                ["git.*error", "local.*git"],
            ),
            (
                LocalGitErrors.LOCAL_FILE_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                1,
                False,
                "Local file error",
                ["file", "local"],
                ["file.*error", "local.*file"],
            ),
            (
                LocalGitErrors.LOCAL_PERMISSION_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Local permission error",
                ["permission", "local"],
                ["permission.*denied", "access.*denied"],
            ),
            (
                LocalGitErrors.LOCAL_REPOSITORY_NOT_FOUND,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Local repository not found",
                ["repository", "not found"],
                ["not.*a.*git.*repository", "repository.*not.*found"],
            ),
            (
                LocalGitErrors.LOCAL_GIT_COMMAND_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                2,
                False,
                "Local Git command error",
                ["git", "command"],
                ["command.*error", "git.*command"],
            ),
            (
                LocalGitErrors.LOCAL_GIT_MERGE_ERROR,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "Local Git merge error",
                ["git", "merge"],
                ["merge.*error", "conflict"],
            ),
            (
                LocalGitErrors.LOCAL_GIT_PUSH_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                2.0,
                2,
                False,
                "Local Git push error",
                ["git", "push"],
                ["push.*error", "rejected"],
            ),
            (
                LocalGitErrors.LOCAL_GIT_PULL_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                2.0,
                2,
                False,
                "Local Git pull error",
                ["git", "pull"],
                ["pull.*error", "fetch.*error"],
            ),
            (
                LocalGitErrors.LOCAL_GIT_CHECKOUT_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                2,
                False,
                "Local Git checkout error",
                ["git", "checkout"],
                ["checkout.*error", "branch.*error"],
            ),
            (
                LocalGitErrors.LOCAL_GIT_BRANCH_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                2,
                False,
                "Local Git branch error",
                ["git", "branch"],
                ["branch.*error", "ref.*error"],
            ),
            (
                LocalGitErrors.LOCAL_GIT_COMMIT_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                2,
                False,
                "Local Git commit error",
                ["git", "commit"],
                ["commit.*error", "staged.*error"],
            ),
            (
                LocalGitErrors.LOCAL_GIT_STASH_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                2,
                False,
                "Local Git stash error",
                ["git", "stash"],
                ["stash.*error", "pop.*error"],
            ),
            (
                LocalGitErrors.LOCAL_GIT_REBASE_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                2.0,
                2,
                False,
                "Local Git rebase error",
                ["git", "rebase"],
                ["rebase.*error", "interactive.*error"],
            ),
        ]

        for (
            error_type,
            severity,
            retryable,
            delay,
            max_retries,
            circuit,
            desc,
            keywords,
            patterns,
        ) in local_git_errors:
            self._register_error_type(
                error_type.value,
                ErrorCategory.PROVIDER,
                severity,
                retryable,
                delay,
                max_retries,
                circuit,
                desc,
                keywords,
                patterns,
            )

        # File system errors
        filesystem_errors = [
            (
                FileSystemErrors.FILE_NOT_FOUND_ERROR,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "File not found",
                ["file", "not found"],
                ["file.*not.*found", "no.*such.*file"],
            ),
            (
                FileSystemErrors.FILE_ACCESS_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                1.0,
                1,
                False,
                "File access error",
                ["file", "access"],
                ["file.*access", "access.*file"],
            ),
            (
                FileSystemErrors.FILE_LOCK_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                2.0,
                3,
                False,
                "File locked",
                ["file", "locked"],
                ["file.*locked", "resource.*busy"],
            ),
            (
                FileSystemErrors.DISK_SPACE_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                True,
                "Disk space error",
                ["disk", "space"],
                ["no.*space", "disk.*full"],
            ),
            (
                FileSystemErrors.FILE_CORRUPTION_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "File corruption error",
                ["file", "corrupt"],
                ["corrupt", "invalid.*file"],
            ),
            (
                FileSystemErrors.PERMISSION_DENIED_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Permission denied",
                ["permission", "denied"],
                ["permission.*denied", "access.*denied"],
            ),
        ]

        for (
            error_type,
            severity,
            retryable,
            delay,
            max_retries,
            circuit,
            desc,
            keywords,
            patterns,
        ) in filesystem_errors:
            self._register_error_type(
                error_type.value,
                ErrorCategory.FILE_SYSTEM,
                severity,
                retryable,
                delay,
                max_retries,
                circuit,
                desc,
                keywords,
                patterns,
            )

        # Security errors
        security_errors = [
            (
                SecurityErrors.SSL_ERROR,
                ErrorSeverity.HIGH,
                True,
                5.0,
                2,
                True,
                "SSL/TLS error",
                ["ssl", "tls"],
                ["ssl.*error", "tls.*error"],
            ),
            (
                SecurityErrors.CERTIFICATE_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Certificate error",
                ["certificate", "cert"],
                ["certificate.*error", "cert.*error"],
            ),
            (
                SecurityErrors.ENCRYPTION_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Encryption error",
                ["encryption", "decrypt"],
                ["encryption.*error", "decrypt.*error"],
            ),
            (
                SecurityErrors.SECURITY_SCAN_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                10.0,
                2,
                False,
                "Security scan error",
                ["security", "scan"],
                ["security.*scan", "scan.*error"],
            ),
            (
                SecurityErrors.COMPLIANCE_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "Compliance error",
                ["compliance", "policy"],
                ["compliance.*error", "policy.*error"],
            ),
        ]

        for (
            error_type,
            severity,
            retryable,
            delay,
            max_retries,
            circuit,
            desc,
            keywords,
            patterns,
        ) in security_errors:
            self._register_error_type(
                error_type.value,
                ErrorCategory.SECURITY,
                severity,
                retryable,
                delay,
                max_retries,
                circuit,
                desc,
                keywords,
                patterns,
            )

        # API errors
        api_errors = [
            (
                APIErrors.API_VERSION_ERROR,
                ErrorSeverity.HIGH,
                False,
                0.0,
                0,
                False,
                "API version error",
                ["api", "version"],
                ["version.*error", "deprecated"],
            ),
            (
                APIErrors.API_DEPRECATED_ERROR,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "API deprecated",
                ["api", "deprecated"],
                ["deprecated", "api.*deprecated"],
            ),
            (
                APIErrors.API_QUOTA_EXCEEDED_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                60.0,
                2,
                True,
                "API quota exceeded",
                ["quota", "limit"],
                ["quota.*exceeded", "limit.*exceeded"],
            ),
            (
                APIErrors.API_SERVICE_UNAVAILABLE_ERROR,
                ErrorSeverity.HIGH,
                True,
                10.0,
                5,
                True,
                "API service unavailable",
                ["service", "unavailable"],
                ["service.*unavailable", "503"],
            ),
            (
                APIErrors.API_MAINTENANCE_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                30.0,
                3,
                True,
                "API maintenance mode",
                ["maintenance", "downtime"],
                ["maintenance", "scheduled.*downtime"],
            ),
            (
                APIErrors.RATE_LIMIT_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                5.0,
                3,
                False,
                "Rate limit exceeded",
                ["rate", "limit"],
                ["rate.*limit", "too.*many.*requests"],
            ),
            (
                APIErrors.SERVER_ERROR,
                ErrorSeverity.HIGH,
                True,
                2.0,
                3,
                True,
                "Server error",
                ["server", "error"],
                ["server.*error", "5[0-9][0-9]"],
            ),
            (
                APIErrors.NOT_FOUND_ERROR,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                False,
                "Resource not found",
                ["not found", "404"],
                ["not.*found", "404"],
            ),
        ]

        for (
            error_type,
            severity,
            retryable,
            delay,
            max_retries,
            circuit,
            desc,
            keywords,
            patterns,
        ) in api_errors:
            self._register_error_type(
                error_type.value,
                ErrorCategory.API,
                severity,
                retryable,
                delay,
                max_retries,
                circuit,
                desc,
                keywords,
                patterns,
            )

        # Unknown errors
        unknown_errors = [
            (
                UnknownErrors.UNKNOWN_ERROR,
                ErrorSeverity.MEDIUM,
                False,
                0.0,
                0,
                True,
                "Unknown error",
                ["unknown", "error"],
                [".*"],
            ),
            (
                UnknownErrors.TEMPORARY_ERROR,
                ErrorSeverity.MEDIUM,
                True,
                2.0,
                3,
                True,
                "Temporary error",
                ["temporary", "error"],
                ["temporary.*error", "temp.*error"],
            ),
        ]

        for (
            error_type,
            severity,
            retryable,
            delay,
            max_retries,
            circuit,
            desc,
            keywords,
            patterns,
        ) in unknown_errors:
            self._register_error_type(
                error_type.value,
                ErrorCategory.UNKNOWN,
                severity,
                retryable,
                delay,
                max_retries,
                circuit,
                desc,
                keywords,
                patterns,
            )

    def _register_error_type(
        self,
        error_type: str,
        category: ErrorCategory,
        severity: ErrorSeverity,
        is_retryable: bool,
        retry_delay: float,
        max_retries: int,
        should_open_circuit: bool,
        description: str,
        keywords: list[str],
        patterns: list[str],
    ) -> None:
        """Register an error type with its metadata."""
        metadata = ErrorTypeMetadata(
            category=category,
            severity=severity,
            is_retryable=is_retryable,
            retry_delay=retry_delay,
            max_retries=max_retries,
            should_open_circuit=should_open_circuit,
            description=description,
            keywords=keywords,
            patterns=patterns,
        )

        self._metadata[error_type] = metadata
        self._category_mappings[category].add(error_type)

    def get_metadata(self, error_type: str) -> ErrorTypeMetadata | None:
        """Get metadata for a specific error type."""
        return self._metadata.get(error_type)

    def get_errors_by_category(self, category: ErrorCategory) -> set[str]:
        """Get all error types in a specific category."""
        return self._category_mappings.get(category, set())

    def get_retryable_errors(self) -> set[str]:
        """Get all retryable error types."""
        return {
            error_type
            for error_type, metadata in self._metadata.items()
            if metadata.is_retryable
        }

    def get_circuit_breaker_errors(self) -> set[str]:
        """Get all error types that should open circuit breaker."""
        return {
            error_type
            for error_type, metadata in self._metadata.items()
            if metadata.should_open_circuit
        }

    def get_errors_by_severity(self, severity: ErrorSeverity) -> set[str]:
        """Get all error types with a specific severity level."""
        return {
            error_type
            for error_type, metadata in self._metadata.items()
            if metadata.severity == severity
        }

    def search_errors_by_keyword(self, keyword: str) -> set[str]:
        """Search for error types containing a specific keyword."""
        keyword_lower = keyword.lower()
        return {
            error_type
            for error_type, metadata in self._metadata.items()
            if keyword_lower in metadata.description.lower()
            or any(keyword_lower in kw.lower() for kw in metadata.keywords)
        }

    def get_all_error_types(self) -> set[str]:
        """Get all registered error types."""
        return set(self._metadata.keys())

    def get_error_categories(self) -> list[ErrorCategory]:
        """Get all error categories."""
        return list(ErrorCategory)


# Global registry instance
error_type_registry = ErrorTypeRegistry()


def get_error_type_metadata(error_type: str) -> ErrorTypeMetadata | None:
    """Convenience function to get error type metadata."""
    return error_type_registry.get_metadata(error_type)


def get_errors_by_category(category: ErrorCategory) -> set[str]:
    """Convenience function to get errors by category."""
    return error_type_registry.get_errors_by_category(category)


def get_retryable_errors() -> set[str]:
    """Convenience function to get retryable errors."""
    return error_type_registry.get_retryable_errors()


def get_circuit_breaker_errors() -> set[str]:
    """Convenience function to get circuit breaker errors."""
    return error_type_registry.get_circuit_breaker_errors()
