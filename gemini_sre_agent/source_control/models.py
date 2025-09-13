# gemini_sre_agent/source_control/models.py

"""Data models for source control operations."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


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
    content: str | None = None
    encoding: str | None = None
    new_path: str | None = None  # For rename operations


@dataclass
class CommitOptions:
    """Options for committing changes."""

    commit: bool = True
    commit_message: str = ""
    author: str | None = None
    committer: str | None = None
    files_to_add: list[str] | None = None


@dataclass
class RepositoryInfo:
    """Information about a repository."""

    name: str
    url: str | None = None
    owner: str | None = None
    is_private: bool = False
    default_branch: str = "main"
    description: str | None = None
    additional_info: dict[str, Any] | None = None


@dataclass
class BranchInfo:
    """Information about a Git branch."""

    name: str
    sha: str
    is_protected: bool = False
    last_commit: datetime | None = None

    def __post_init__(self) -> None:
        if self.last_commit is None:
            self.last_commit = datetime.now()


@dataclass
class FileInfo:
    """Information about a file."""

    path: str
    size: int
    last_modified: datetime | None = None
    sha: str | None = None
    is_binary: bool = False
    encoding: str | None = None

    def __post_init__(self) -> None:
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
    parents: list[str] | None = None

    def __post_init__(self) -> None:
        if self.parents is None:
            self.parents = []


@dataclass
class IssueInfo:
    """Information about an issue or pull request."""

    number: int
    title: str
    body: str | None = None
    state: str = "open"
    author: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    labels: list[str] | None = None
    assignees: list[str] | None = None

    def __post_init__(self) -> None:
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
    commit_sha: str | None = None
    pull_request_url: str | None = None
    error_details: str | None = None
    additional_info: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.additional_info is None:
            self.additional_info = {}


@dataclass
class OperationResult:
    """Result of a batch operation."""

    operation_id: str
    success: bool
    message: str
    file_path: str | None = None
    error_details: str | None = None
    additional_info: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.additional_info is None:
            self.additional_info = {}


@dataclass
class BatchOperation:
    """Represents a batch operation."""

    operation_id: str
    operation_type: str
    file_path: str
    content: str | None = None
    additional_params: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.additional_params is None:
            self.additional_params = {}


@dataclass
class ConflictInfo:
    """Information about a conflict."""

    path: str
    conflict_type: str
    has_conflicts: bool = False
    conflict_files: list[str] | None = None
    conflict_details: dict[str, Any] | None = None
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.conflict_files is None:
            self.conflict_files = []
        if self.conflict_details is None:
            self.conflict_details = {}
        if self.details is None:
            self.details = {}


@dataclass
class ProviderHealth:
    """Health status of a provider."""

    status: str
    message: str
    is_healthy: bool = True
    last_check: datetime | None = None
    response_time_ms: float | None = None
    error_message: str | None = None
    warnings: list[str] | None = None
    additional_info: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.last_check is None:
            self.last_check = datetime.now()
        if self.warnings is None:
            self.warnings = []
        if self.additional_info is None:
            self.additional_info = {}


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
    max_file_size: int | None = None
    supported_patch_formats: list[PatchFormat] | None = None
    supported_encodings: list[str] | None = None

    def __post_init__(self) -> None:
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
    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
    INVALID_INPUT = "invalid_input"
