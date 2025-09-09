# gemini_sre_agent/source_control/__init__.py

"""
Source control package for the Gemini SRE Agent.

This package provides a unified interface for interacting with different
source control systems (GitHub, GitLab, local repositories) through a
common abstract base class and provider implementations.
"""

from .base import SourceControlProvider
from .base_implementation import BaseSourceControlProvider
from .configured_provider import ConfiguredSourceControlProvider
from .models import (
    BatchOperation,
    BranchInfo,
    CommitInfo,
    ConflictInfo,
    FileInfo,
    OperationResult,
    OperationStatus,
    ProviderCapabilities,
    ProviderHealth,
    RemediationResult,
    RepositoryInfo,
)
from .utils import (
    create_operation_id,
    execute_with_retry,
    health_check_providers,
    is_fatal_status,
    is_retryable_status,
    is_successful_status,
    sanitize_branch_name,
    sanitize_commit_message,
    timeout_operation,
    validate_operation_status,
    with_provider,
)

__all__ = [
    # Base classes
    "SourceControlProvider",
    "BaseSourceControlProvider",
    "ConfiguredSourceControlProvider",
    # Models
    "BatchOperation",
    "BranchInfo",
    "CommitInfo",
    "ConflictInfo",
    "FileInfo",
    "OperationResult",
    "OperationStatus",
    "ProviderCapabilities",
    "ProviderHealth",
    "RemediationResult",
    "RepositoryInfo",
    # Utilities
    "create_operation_id",
    "execute_with_retry",
    "health_check_providers",
    "is_fatal_status",
    "is_retryable_status",
    "is_successful_status",
    "sanitize_branch_name",
    "sanitize_commit_message",
    "timeout_operation",
    "validate_operation_status",
    "with_provider",
]
