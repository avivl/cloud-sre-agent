# gemini_sre_agent/source_control/providers/github_models.py

"""
GitHub-specific data models for source control operations.

This module contains data models specific to GitHub operations that extend
the base source control models with GitHub-specific functionality.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class GitHubAuthType(str, Enum):
    """GitHub authentication types."""

    TOKEN = "token"
    APP = "app"


class PullRequestStatus(str, Enum):
    """GitHub pull request status."""

    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"
    DRAFT = "draft"


class MergeMethod(str, Enum):
    """GitHub merge methods."""

    MERGE = "merge"
    SQUASH = "squash"
    REBASE = "rebase"


@dataclass
class GitHubCredentials:
    """GitHub authentication credentials."""

    auth_type: GitHubAuthType
    token: Optional[str] = None
    app_id: Optional[str] = None
    private_key: Optional[str] = None
    api_url: Optional[str] = None

    def __post_init__(self):
        """Validate credentials based on auth type."""
        if self.auth_type == GitHubAuthType.TOKEN and not self.token:
            raise ValueError("Token is required when auth_type is 'token'")
        if self.auth_type == GitHubAuthType.APP and (
            not self.app_id or not self.private_key
        ):
            raise ValueError(
                "app_id and private_key are required when auth_type is 'app'"
            )


@dataclass
class PullRequestInfo:
    """GitHub pull request information."""

    id: int
    title: str
    url: str
    status: PullRequestStatus
    head_branch: str
    base_branch: str
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    mergeable: Optional[bool] = None
    mergeable_state: Optional[str] = None
    draft: bool = False
    labels: Optional[List[str]] = None
    reviewers: Optional[List[str]] = None
    assignees: Optional[List[str]] = None
    additional_info: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.labels is None:
            self.labels = []
        if self.reviewers is None:
            self.reviewers = []
        if self.assignees is None:
            self.assignees = []
        if self.additional_info is None:
            self.additional_info = {}


@dataclass
class GitHubBranchInfo:
    """GitHub-specific branch information."""

    name: str
    commit_id: str
    protected: bool
    protection_rules: Optional[Dict[str, Any]] = None
    last_commit: Optional[Dict[str, Any]] = None
    ahead_count: int = 0
    behind_count: int = 0


@dataclass
class GitHubFileInfo:
    """GitHub-specific file information."""

    path: str
    size: int
    sha: str
    content_type: str
    is_binary: bool
    download_url: Optional[str] = None
    html_url: Optional[str] = None
    git_url: Optional[str] = None
    last_modified: Optional[datetime] = None
    additional_info: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.additional_info is None:
            self.additional_info = {}


@dataclass
class GitHubRepositoryInfo:
    """GitHub-specific repository information."""

    name: str
    owner: str
    full_name: str
    default_branch: str
    url: str
    html_url: str
    clone_url: str
    ssh_url: str
    is_private: bool
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None
    language: Optional[str] = None
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    license: Optional[str] = None
    topics: Optional[List[str]] = None
    additional_info: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.topics is None:
            self.topics = []
        if self.additional_info is None:
            self.additional_info = {}


@dataclass
class GitHubCommitInfo:
    """GitHub-specific commit information."""

    sha: str
    message: str
    author: str
    author_email: str
    committer: str
    committer_email: str
    created_at: datetime
    url: str
    html_url: str
    parents: Optional[List[str]] = None
    stats: Optional[Dict[str, Any]] = None
    files: Optional[List[Dict[str, Any]]] = None
    additional_info: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.parents is None:
            self.parents = []
        if self.files is None:
            self.files = []
        if self.additional_info is None:
            self.additional_info = {}


@dataclass
class GitHubWebhookInfo:
    """GitHub webhook information."""

    id: int
    name: str
    events: List[str]
    active: bool
    config: Dict[str, Any]
    url: str
    created_at: datetime
    updated_at: datetime
    last_response: Optional[Dict[str, Any]] = None
    additional_info: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.additional_info is None:
            self.additional_info = {}


@dataclass
class GitHubIssueInfo:
    """GitHub issue information."""

    id: int
    title: str
    body: str
    state: str
    author: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    labels: Optional[List[str]] = None
    assignees: Optional[List[str]] = None
    milestone: Optional[str] = None
    comments: int = 0
    url: str = ""
    html_url: str = ""
    additional_info: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.labels is None:
            self.labels = []
        if self.assignees is None:
            self.assignees = []
        if self.additional_info is None:
            self.additional_info = {}
