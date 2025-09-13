# gemini_sre_agent/source_control/providers/gitlab/gitlab_models.py

"""GitLab-specific models and data structures."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GitLabMergeRequestInfo(BaseModel):
    """Information about a GitLab merge request."""

    iid: int
    title: str
    description: str | None = None
    state: str = "opened"
    author: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    web_url: str | None = None
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
    description: str | None = None
    web_url: str
    ssh_url_to_repo: str
    http_url_to_repo: str
    default_branch: str
    visibility: str = "private"
    created_at: datetime | None = None
    last_activity_at: datetime | None = None
    permissions: dict[str, Any] = Field(default_factory=dict)


class GitLabBranchInfo(BaseModel):
    """Information about a GitLab branch."""

    name: str
    commit: dict[str, Any]
    protected: bool = False
    developers_can_push: bool = False
    developers_can_merge: bool = False
    can_push: bool = False
    default: bool = False
    web_url: str | None = None


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
    parent_ids: list[str] = Field(default_factory=list)
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
    content: str | None = None


class GitLabPipelineInfo(BaseModel):
    """Information about a GitLab CI/CD pipeline."""

    id: int
    status: str
    ref: str
    sha: str
    web_url: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration: int | None = None
    coverage: float | None = None


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
