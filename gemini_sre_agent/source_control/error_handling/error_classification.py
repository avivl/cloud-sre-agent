# gemini_sre_agent/source_control/error_handling/error_classification.py

"""
Error classification and analysis for source control operations.

This module provides comprehensive error classification logic to determine
retry behavior, circuit breaker actions, and error handling strategies.
"""

import asyncio
import logging
from typing import  Callable, List, Optional

from .core import ErrorClassification, ErrorType


class ErrorClassifier:
    """Classifies errors and determines retry behavior."""

    def __init__(self):
        self.logger = logging.getLogger("ErrorClassifier")

        # Error classification rules (ordered by specificity)
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
            self._classify_file_system_errors,
            self._classify_security_errors,
            self._classify_api_errors,
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

        # 2FA required
        elif any(term in error_str for term in ["2fa", "two-factor", "otp", "mfa"]):
            return ErrorClassification(
                error_type=ErrorType.GITHUB_2FA_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "github"},
            )

        # SSH errors
        elif any(term in error_str for term in ["ssh", "key", "fingerprint"]):
            return ErrorClassification(
                error_type=ErrorType.GITHUB_SSH_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "github"},
            )

        # Webhook errors
        elif any(term in error_str for term in ["webhook", "hook", "delivery"]):
            return ErrorClassification(
                error_type=ErrorType.GITHUB_WEBHOOK_ERROR,
                is_retryable=True,
                retry_delay=5.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "github"},
            )

        # Maintenance mode
        elif any(term in error_str for term in ["maintenance", "scheduled", "downtime"]):
            return ErrorClassification(
                error_type=ErrorType.GITHUB_MAINTENANCE_ERROR,
                is_retryable=True,
                retry_delay=30.0,
                max_retries=3,
                should_open_circuit=True,
                details={"error": str(error), "provider": "github"},
            )

        # Pull request errors
        elif any(term in error_str for term in ["pull request", "pr", "review"]):
            return ErrorClassification(
                error_type=ErrorType.GITHUB_PULL_REQUEST_ERROR,
                is_retryable=True,
                retry_delay=2.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "github"},
            )

        # Commit errors
        elif any(term in error_str for term in ["commit", "sha", "hash"]):
            return ErrorClassification(
                error_type=ErrorType.GITHUB_COMMIT_ERROR,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "github"},
            )

        # File errors
        elif any(term in error_str for term in ["file", "content", "blob"]):
            return ErrorClassification(
                error_type=ErrorType.GITHUB_FILE_ERROR,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=2,
                should_open_circuit=False,
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

        # SSH errors
        elif any(term in error_str for term in ["ssh", "key", "fingerprint"]):
            return ErrorClassification(
                error_type=ErrorType.GITLAB_SSH_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "gitlab"},
            )

        # Pipeline errors
        elif any(term in error_str for term in ["pipeline", "ci", "cd", "job"]):
            return ErrorClassification(
                error_type=ErrorType.GITLAB_PIPELINE_ERROR,
                is_retryable=True,
                retry_delay=5.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "gitlab"},
            )

        # Maintenance mode
        elif any(term in error_str for term in ["maintenance", "scheduled", "downtime"]):
            return ErrorClassification(
                error_type=ErrorType.GITLAB_MAINTENANCE_ERROR,
                is_retryable=True,
                retry_delay=30.0,
                max_retries=3,
                should_open_circuit=True,
                details={"error": str(error), "provider": "gitlab"},
            )

        # Merge request errors
        elif any(term in error_str for term in ["merge request", "mr", "review"]):
            return ErrorClassification(
                error_type=ErrorType.GITLAB_MERGE_REQUEST_ERROR,
                is_retryable=True,
                retry_delay=2.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "gitlab"},
            )

        # Commit errors
        elif any(term in error_str for term in ["commit", "sha", "hash"]):
            return ErrorClassification(
                error_type=ErrorType.GITLAB_COMMIT_ERROR,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "gitlab"},
            )

        # File errors
        elif any(term in error_str for term in ["file", "content", "blob"]):
            return ErrorClassification(
                error_type=ErrorType.GITLAB_FILE_ERROR,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=2,
                should_open_circuit=False,
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

        # Git command errors
        elif any(term in error_str for term in ["command", "git", "fatal"]):
            return ErrorClassification(
                error_type=ErrorType.LOCAL_GIT_COMMAND_ERROR,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )

        # Merge errors
        elif any(term in error_str for term in ["merge", "conflict", "unmerged"]):
            return ErrorClassification(
                error_type=ErrorType.LOCAL_GIT_MERGE_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )

        # Push errors
        elif any(term in error_str for term in ["push", "rejected", "non-fast-forward"]):
            return ErrorClassification(
                error_type=ErrorType.LOCAL_GIT_PUSH_ERROR,
                is_retryable=True,
                retry_delay=2.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )

        # Pull errors
        elif any(term in error_str for term in ["pull", "fetch", "remote"]):
            return ErrorClassification(
                error_type=ErrorType.LOCAL_GIT_PULL_ERROR,
                is_retryable=True,
                retry_delay=2.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )

        # Checkout errors
        elif any(term in error_str for term in ["checkout", "branch", "switch"]):
            return ErrorClassification(
                error_type=ErrorType.LOCAL_GIT_CHECKOUT_ERROR,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )

        # Branch errors
        elif any(term in error_str for term in ["branch", "ref", "reference"]):
            return ErrorClassification(
                error_type=ErrorType.LOCAL_GIT_BRANCH_ERROR,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )

        # Commit errors
        elif any(term in error_str for term in ["commit", "staged", "index"]):
            return ErrorClassification(
                error_type=ErrorType.LOCAL_GIT_COMMIT_ERROR,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )

        # Stash errors
        elif any(term in error_str for term in ["stash", "pop", "apply"]):
            return ErrorClassification(
                error_type=ErrorType.LOCAL_GIT_STASH_ERROR,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=2,
                should_open_circuit=False,
                details={"error": str(error), "provider": "local"},
            )

        # Rebase errors
        elif any(term in error_str for term in ["rebase", "interactive", "onto"]):
            return ErrorClassification(
                error_type=ErrorType.LOCAL_GIT_REBASE_ERROR,
                is_retryable=True,
                retry_delay=2.0,
                max_retries=2,
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

    def _classify_file_system_errors(
        self, error: Exception
    ) -> Optional[ErrorClassification]:
        """Classify file system errors."""
        error_str = str(error).lower()
        
        # File not found
        if any(term in error_str for term in ["file not found", "no such file", "enoent"]):
            return ErrorClassification(
                error_type=ErrorType.FILE_NOT_FOUND_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error)},
            )
        
        # Permission denied
        elif any(term in error_str for term in ["permission denied", "access denied", "eacces"]):
            return ErrorClassification(
                error_type=ErrorType.PERMISSION_DENIED_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error)},
            )
        
        # File locked
        elif any(term in error_str for term in ["file locked", "resource busy", "ebusy"]):
            return ErrorClassification(
                error_type=ErrorType.FILE_LOCK_ERROR,
                is_retryable=True,
                retry_delay=2.0,
                max_retries=3,
                should_open_circuit=False,
                details={"error": str(error)},
            )
        
        # Disk space
        elif any(term in error_str for term in ["no space", "disk full", "enospc"]):
            return ErrorClassification(
                error_type=ErrorType.DISK_SPACE_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=True,
                details={"error": str(error)},
            )
        
        # File corruption
        elif any(term in error_str for term in ["corrupt", "invalid", "bad file"]):
            return ErrorClassification(
                error_type=ErrorType.FILE_CORRUPTION_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error)},
            )
        
        return None

    def _classify_security_errors(
        self, error: Exception
    ) -> Optional[ErrorClassification]:
        """Classify security-related errors."""
        error_str = str(error).lower()
        
        # SSL/TLS errors
        if any(term in error_str for term in ["ssl", "tls", "certificate", "handshake"]):
            return ErrorClassification(
                error_type=ErrorType.SSL_ERROR,
                is_retryable=True,
                retry_delay=5.0,
                max_retries=2,
                should_open_circuit=True,
                details={"error": str(error)},
            )
        
        # Certificate errors
        elif any(term in error_str for term in ["certificate", "cert", "x509"]):
            return ErrorClassification(
                error_type=ErrorType.CERTIFICATE_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error)},
            )
        
        # Encryption errors
        elif any(term in error_str for term in ["encryption", "decrypt", "cipher"]):
            return ErrorClassification(
                error_type=ErrorType.ENCRYPTION_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error)},
            )
        
        return None

    def _classify_api_errors(
        self, error: Exception
    ) -> Optional[ErrorClassification]:
        """Classify API and service errors."""
        error_str = str(error).lower()
        
        # Service unavailable
        if any(term in error_str for term in ["service unavailable", "503", "unavailable"]):
            return ErrorClassification(
                error_type=ErrorType.API_SERVICE_UNAVAILABLE_ERROR,
                is_retryable=True,
                retry_delay=10.0,
                max_retries=5,
                should_open_circuit=True,
                details={"error": str(error)},
            )
        
        # Maintenance mode
        elif any(term in error_str for term in ["maintenance", "scheduled", "downtime"]):
            return ErrorClassification(
                error_type=ErrorType.API_MAINTENANCE_ERROR,
                is_retryable=True,
                retry_delay=30.0,
                max_retries=3,
                should_open_circuit=True,
                details={"error": str(error)},
            )
        
        # API version errors
        elif any(term in error_str for term in ["version", "deprecated", "api version"]):
            return ErrorClassification(
                error_type=ErrorType.API_VERSION_ERROR,
                is_retryable=False,
                retry_delay=0.0,
                max_retries=0,
                should_open_circuit=False,
                details={"error": str(error)},
            )
        
        # Quota exceeded
        elif any(term in error_str for term in ["quota", "limit exceeded", "usage limit"]):
            return ErrorClassification(
                error_type=ErrorType.API_QUOTA_EXCEEDED_ERROR,
                is_retryable=True,
                retry_delay=60.0,
                max_retries=2,
                should_open_circuit=True,
                details={"error": str(error)},
            )
        
        return None
