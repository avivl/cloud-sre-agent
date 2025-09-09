# gemini_sre_agent/config/source_control_repositories.py

"""
Repository configuration models for different source control providers.
"""

import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import Field, field_validator

from .base import BaseConfig
from .source_control_credentials import CredentialConfig
from .source_control_remediation import RemediationStrategyConfig


class RepositoryConfig(BaseConfig):
    """Base configuration for all repository types."""

    type: str = Field(..., description="Repository type (github, gitlab, local, etc.)")
    name: str = Field(..., description="Unique name for this repository configuration")
    branch: str = Field(default="main", description="Default branch for operations")
    paths: List[str] = Field(
        default=["/"], description="Paths to consider within the repository"
    )
    credentials: Optional[CredentialConfig] = Field(
        None, description="Repository credentials"
    )
    remediation: RemediationStrategyConfig = Field(
        default_factory=lambda: RemediationStrategyConfig(),
        description="Remediation configuration",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate repository name format."""
        if not v or not v.strip():
            raise ValueError("Repository name cannot be empty")
        if len(v) > 100:
            raise ValueError("Repository name cannot exceed 100 characters")
        if not re.match(r"^[a-zA-Z0-9_.-]+$", v):
            raise ValueError(
                "Repository name can only contain alphanumeric characters, "
                "periods, hyphens, and underscores"
            )
        return v.strip()

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v):
        """Validate branch name format."""
        if not v or not v.strip():
            raise ValueError("Branch name cannot be empty")
        if len(v) > 255:
            raise ValueError("Branch name cannot exceed 255 characters")
        if not re.match(r"^[a-zA-Z0-9/._-]+$", v):
            raise ValueError(
                "Branch name can only contain alphanumeric characters, "
                "slashes, periods, hyphens, and underscores"
            )
        return v.strip()

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, v):
        """Validate that paths are properly formatted."""
        if not v:
            raise ValueError("At least one path must be specified")

        for path in v:
            if not path or not path.strip():
                raise ValueError("Paths cannot be empty")
            if not path.startswith("/"):
                raise ValueError(f"Path '{path}' must start with '/'")
            if len(path) > 500:
                raise ValueError(f"Path '{path}' cannot exceed 500 characters")

        return v

    def matches_path(self, file_path: str) -> bool:
        """Check if a file path matches any of the configured paths."""
        for path in self.paths:
            if file_path.startswith(path):
                return True
        return False


class GitHubRepositoryConfig(RepositoryConfig):
    """GitHub-specific repository configuration."""

    def __init__(self, **data):
        if "type" not in data:
            data["type"] = "github"
        super().__init__(**data)

    url: str = Field(..., description="GitHub repository URL (e.g., 'owner/repo')")
    api_base_url: str = Field(
        default="https://api.github.com", description="GitHub API base URL"
    )

    @field_validator("url")
    @classmethod
    def validate_github_url(cls, v):
        """Validate GitHub repository URL format."""
        if not v or not v.strip():
            raise ValueError("GitHub URL cannot be empty")

        v = v.strip()

        # Remove protocol if present
        if v.startswith(("https://github.com/", "http://github.com/")):
            v = v.split("/", 3)[-1]
        elif v.startswith("github.com/"):
            v = v[11:]

        # Validate format: owner/repo
        if "/" not in v or v.count("/") != 1:
            raise ValueError("GitHub URL must be in format 'owner/repo'")

        owner, repo = v.split("/")
        if not owner or not repo:
            raise ValueError("GitHub URL must have both owner and repository name")

        if not re.match(r"^[a-zA-Z0-9_.-]+$", owner):
            raise ValueError("GitHub owner name contains invalid characters")

        if not re.match(r"^[a-zA-Z0-9_.-]+$", repo):
            raise ValueError("GitHub repository name contains invalid characters")

        return v

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, v):
        """Validate GitHub API base URL."""
        if not v or not v.strip():
            raise ValueError("API base URL cannot be empty")

        v = v.strip()
        parsed = urlparse(v)

        if not parsed.scheme or not parsed.netloc:
            raise ValueError("API base URL must be a valid URL")

        if parsed.scheme not in ["http", "https"]:
            raise ValueError("API base URL must use http or https protocol")

        return v

    def get_full_url(self) -> str:
        """Get the full GitHub repository URL."""
        if self.url.startswith(("http://", "https://")):
            return self.url
        return f"https://github.com/{self.url}"

    def get_owner(self) -> str:
        """Get the repository owner."""
        return self.url.split("/")[0]

    def get_repo_name(self) -> str:
        """Get the repository name."""
        return self.url.split("/")[1]


class GitLabRepositoryConfig(RepositoryConfig):
    """GitLab-specific repository configuration."""

    def __init__(self, **data):
        if "type" not in data:
            data["type"] = "gitlab"
        super().__init__(**data)

    url: str = Field(..., description="GitLab repository URL")
    api_base_url: str = Field(
        default="https://gitlab.com/api/v4", description="GitLab API base URL"
    )
    project_id: Optional[str] = Field(
        None, description="GitLab project ID (if different from URL)"
    )

    @field_validator("url")
    @classmethod
    def validate_gitlab_url(cls, v):
        """Validate GitLab repository URL format."""
        if not v or not v.strip():
            raise ValueError("GitLab URL cannot be empty")

        v = v.strip()
        parsed = urlparse(v)

        if not parsed.scheme or not parsed.netloc:
            raise ValueError("GitLab URL must be a valid URL")

        if parsed.scheme not in ["http", "https"]:
            raise ValueError("GitLab URL must use http or https protocol")

        # Check if it looks like a GitLab URL
        if "gitlab.com" not in parsed.netloc and not parsed.netloc.endswith(
            ".gitlab.io"
        ):
            # Allow custom GitLab instances
            pass

        return v

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, v):
        """Validate GitLab API base URL."""
        if not v or not v.strip():
            raise ValueError("API base URL cannot be empty")

        v = v.strip()
        parsed = urlparse(v)

        if not parsed.scheme or not parsed.netloc:
            raise ValueError("API base URL must be a valid URL")

        if parsed.scheme not in ["http", "https"]:
            raise ValueError("API base URL must use http or https protocol")

        return v

    def get_project_id(self) -> Optional[str]:
        """Get the GitLab project ID."""
        return self.project_id


class LocalRepositoryConfig(RepositoryConfig):
    """Local filesystem repository configuration."""

    def __init__(self, **data):
        if "type" not in data:
            data["type"] = "local"
        super().__init__(**data)

    path: str = Field(..., description="Absolute path to the local repository")
    git_enabled: bool = Field(default=True, description="Whether to use Git operations")

    @field_validator("path")
    @classmethod
    def validate_local_path(cls, v):
        """Validate that local path is absolute and exists."""
        if not v or not v.strip():
            raise ValueError("Local repository path cannot be empty")

        v = v.strip()

        if not v.startswith("/"):
            raise ValueError("Local repository path must be absolute")

        path_obj = Path(v)
        if not path_obj.exists():
            raise ValueError(f"Local repository path does not exist: {v}")

        if not path_obj.is_dir():
            raise ValueError(f"Local repository path is not a directory: {v}")

        return v

    def get_path(self) -> Path:
        """Get the repository path as a Path object."""
        return Path(self.path)

    def is_git_repository(self) -> bool:
        """Check if the path is a Git repository."""
        if not self.git_enabled:
            return False

        git_dir = self.get_path() / ".git"
        return git_dir.exists() and git_dir.is_dir()
