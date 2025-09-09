"""GitLab-specific models and data structures."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GitLabMergeRequestInfo(BaseModel):
    """Information about a GitLab merge request."""

    iid: int
    title: str
    description: Optional[str] = None
    state: str = "opened"
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    labels: List[str] = Field(default_factory=list)
    assignees: List[str] = Field(default_factory=list)
    web_url: Optional[str] = None
    source_branch: str
    target_branch: str
    merge_status: str = "unchecked"
    has_conflicts: bool = False


class GitLabProjectInfo(BaseModel):
    """Information about a GitLab project."""

    id: int
    name: str
    path: str
    full_path: str
    description: Optional[str] = None
    web_url: str
    ssh_url_to_repo: str
    http_url_to_repo: str
    default_branch: str
    visibility: str = "private"
    created_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    permissions: Dict[str, Any] = Field(default_factory=dict)


class GitLabBranchInfo(BaseModel):
    """Information about a GitLab branch."""

    name: str
    commit: Dict[str, Any]
    protected: bool = False
    developers_can_push: bool = False
    developers_can_merge: bool = False
    can_push: bool = False
    default: bool = False
    web_url: Optional[str] = None


class GitLabCommitInfo(BaseModel):
    """Information about a GitLab commit."""

    id: str
    short_id: str
    title: str
    message: str
    author_name: str
    author_email: str
    authored_date: datetime
    committer_name: str
    committer_email: str
    committed_date: datetime
    created_at: datetime
    parent_ids: List[str] = Field(default_factory=list)
    web_url: str


class GitLabFileInfo(BaseModel):
    """Information about a GitLab file."""

    file_name: str
    file_path: str
    size: int
    encoding: str = "base64"
    content_sha256: str
    ref: str
    blob_id: str
    commit_id: str
    last_commit_id: str
    content: Optional[str] = None


class GitLabPipelineInfo(BaseModel):
    """Information about a GitLab CI/CD pipeline."""

    id: int
    status: str
    ref: str
    sha: str
    web_url: str
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration: Optional[int] = None
    coverage: Optional[float] = None


@dataclass
class GitLabCredentials:
    """GitLab authentication credentials."""

    token: str
    url: str = "https://gitlab.com"
    api_version: str = "v4"
    timeout: int = 30
    ssl_verify: bool = True
    per_page: int = 20
    pagination: str = "keyset"
    order_by: str = "id"
    sort: str = "asc"
