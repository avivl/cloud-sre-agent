# gemini_sre_agent/source_control/models.py

"""
Data models for source control operations and results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class OperationStatus(Enum):
    """Enum representing the status of an operation."""

    SUCCESS = auto()
    FAILURE = auto()
    PENDING = auto()
    CONFLICT = auto()
    UNAUTHORIZED = auto()
    NOT_FOUND = auto()
    RATE_LIMITED = auto()
    TIMEOUT = auto()
    INVALID_INPUT = auto()


@dataclass
class RepositoryInfo:
    """Information about a repository."""

    name: str
    owner: str
    default_branch: str
    url: str
    is_private: bool
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RemediationResult:
    """Result of a remediation operation."""

    success: bool
    status: OperationStatus
    commit_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FileInfo:
    """Information about a file in the repository."""

    path: str
    size: int
    last_modified: datetime
    sha: str
    content_type: str
    is_binary: bool
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchOperation:
    """Represents a single operation in a batch."""

    operation_type: str
    path: Optional[str] = None
    content: Optional[str] = None
    message: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationResult:
    """Result of a single operation."""

    operation_id: str
    status: OperationStatus
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConflictInfo:
    """Information about a merge conflict."""

    path: str
    conflict_type: str
    base_sha: str
    head_sha: str
    merge_sha: Optional[str] = None
    conflict_markers: List[str] = field(default_factory=list)
    resolution_strategy: Optional[str] = None


@dataclass
class BranchInfo:
    """Information about a branch."""

    name: str
    sha: str
    is_protected: bool
    last_commit: datetime
    ahead_count: int = 0
    behind_count: int = 0
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CommitInfo:
    """Information about a commit."""

    sha: str
    message: str
    author: str
    author_email: str
    committer: str
    committer_email: str
    timestamp: datetime
    parent_shas: List[str] = field(default_factory=list)
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderCapabilities:
    """Capabilities supported by a source control provider."""

    supports_branches: bool = True
    supports_merges: bool = True
    supports_pull_requests: bool = False
    supports_merge_requests: bool = False
    supports_direct_commits: bool = True
    supports_patch_files: bool = True
    supports_batch_operations: bool = False
    supports_conflict_resolution: bool = False
    supports_file_history: bool = True
    supports_webhooks: bool = False
    max_file_size: Optional[int] = None
    max_batch_size: Optional[int] = None
    additional_capabilities: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderHealth:
    """Health status of a source control provider."""

    is_healthy: bool
    last_check: datetime
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    additional_info: Dict[str, Any] = field(default_factory=dict)
