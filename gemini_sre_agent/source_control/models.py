"""Data models for source control operations."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PatchFormat(str, Enum):
    """Supported patch formats."""

    UNIFIED = "unified"
    CONTEXT = "context"
    GIT = "git"


@dataclass
class FileOperation:
    """Represents a file operation to be performed."""

    operation_type: str  # "write", "delete", "rename"
    file_path: str
    content: Optional[str] = None
    encoding: Optional[str] = None
    new_path: Optional[str] = None  # For rename operations


@dataclass
class CommitOptions:
    """Options for committing changes."""

    commit: bool = True
    commit_message: str = ""
    author: Optional[str] = None
    committer: Optional[str] = None
    files_to_add: Optional[List[str]] = None


@dataclass
class RepositoryInfo:
    """Information about a repository."""

    name: str
    url: Optional[str] = None
    owner: Optional[str] = None
    is_private: bool = False
    default_branch: str = "main"
    description: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None


@dataclass
class BranchInfo:
    """Information about a Git branch."""

    name: str
    sha: str
    is_protected: bool = False
    last_commit: Optional[datetime] = None

    def __post_init__(self):
        if self.last_commit is None:
            self.last_commit = datetime.now()


@dataclass
class FileInfo:
    """Information about a file."""

    path: str
    size: int
    last_modified: Optional[datetime] = None
    sha: Optional[str] = None
    is_binary: bool = False
    encoding: Optional[str] = None

    def __post_init__(self):
        if self.last_modified is None:
            self.last_modified = datetime.now()


@dataclass
class CommitInfo:
    """Information about a Git commit."""

    sha: str
    message: str
    author: str
    author_email: str
    committer: str
    committer_email: str
    date: datetime
    parents: Optional[List[str]] = None

    def __post_init__(self):
        if self.parents is None:
            self.parents = []


@dataclass
class IssueInfo:
    """Information about an issue or pull request."""

    number: int
    title: str
    body: Optional[str] = None
    state: str = "open"
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    labels: Optional[List[str]] = None
    assignees: Optional[List[str]] = None

    def __post_init__(self):
        if self.labels is None:
            self.labels = []
        if self.assignees is None:
            self.assignees = []


@dataclass
class RemediationResult:
    """Result of a remediation operation."""

    success: bool
    message: str
    file_path: str
    operation_type: str
    commit_sha: Optional[str] = None
    pull_request_url: Optional[str] = None
    error_details: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}


@dataclass
class OperationResult:
    """Result of a batch operation."""

    operation_id: str
    success: bool
    message: str
    file_path: Optional[str] = None
    error_details: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}


@dataclass
class BatchOperation:
    """Represents a batch operation."""

    operation_id: str
    operation_type: str
    file_path: str
    content: Optional[str] = None
    additional_params: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.additional_params is None:
            self.additional_params = {}


@dataclass
class ConflictInfo:
    """Information about a conflict."""

    path: str
    conflict_type: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class ProviderHealth:
    """Health status of a provider."""

    status: str
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class ProviderCapabilities:
    """Capabilities of a source control provider."""

    supports_pull_requests: bool = False
    supports_merge_requests: bool = False
    supports_direct_commits: bool = True
    supports_patch_generation: bool = True
    supports_branch_operations: bool = True
    supports_file_history: bool = True
    supports_batch_operations: bool = True
    max_file_size: Optional[int] = None
    supported_patch_formats: Optional[List[PatchFormat]] = None
    supported_encodings: Optional[List[str]] = None

    def __post_init__(self):
        if self.supported_patch_formats is None:
            self.supported_patch_formats = [PatchFormat.UNIFIED]
        if self.supported_encodings is None:
            self.supported_encodings = ["utf-8"]


class OperationStatus(str, Enum):
    """Status of an operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
