# gemini_sre_agent/config/source_control_remediation.py

"""
Remediation strategy configuration models for source control operations.
"""

from enum import Enum
from typing import List, Optional

from pydantic import Field, field_validator

from .base import BaseConfig


class RemediationStrategy(str, Enum):
    """Available remediation strategies."""

    PULL_REQUEST = "pull_request"
    MERGE_REQUEST = "merge_request"
    DIRECT_COMMIT = "direct_commit"
    PATCH = "patch"


class ConflictResolutionStrategy(str, Enum):
    """Available conflict resolution strategies."""

    MANUAL = "manual"
    AUTO_MERGE = "auto_merge"
    FAIL_FAST = "fail_fast"


class PatchFormat(str, Enum):
    """Available patch formats."""

    UNIFIED = "unified"
    CONTEXT = "context"
    GIT = "git"


class RemediationStrategyConfig(BaseConfig):
    """Configuration for remediation strategies."""

    strategy: RemediationStrategy = Field(
        default=RemediationStrategy.PULL_REQUEST,
        description="Remediation strategy to use",
    )

    # Auto-merge and review settings
    auto_merge: bool = Field(
        default=False, description="Whether to auto-merge after creation"
    )
    require_review: bool = Field(
        default=True, description="Whether to require human review"
    )

    # PR/MR metadata
    labels: List[str] = Field(
        default_factory=list, description="Labels to apply to PRs/MRs"
    )
    assignees: List[str] = Field(
        default_factory=list, description="Users to assign to PRs/MRs"
    )
    reviewers: List[str] = Field(
        default_factory=list, description="Users to request review from"
    )

    # Commit message settings
    commit_message_template: Optional[str] = Field(
        default=None,
        description="Template for commit messages (for direct_commit strategy)",
    )
    commit_author_name: Optional[str] = Field(
        default=None, description="Author name for commits"
    )
    commit_author_email: Optional[str] = Field(
        default=None, description="Author email for commits"
    )

    # Patch-specific settings
    output_path: Optional[str] = Field(
        default=None, description="Path for patch files (for patch strategy)"
    )
    format: PatchFormat = Field(default=PatchFormat.UNIFIED, description="Patch format")
    include_metadata: bool = Field(
        default=True, description="Include metadata in patches"
    )

    # Branch settings
    branch_prefix: str = Field(
        default="sre-fix", description="Prefix for created branches"
    )
    branch_suffix: Optional[str] = Field(
        default=None, description="Suffix for created branches"
    )

    # Conflict resolution
    conflict_resolution: ConflictResolutionStrategy = Field(
        default=ConflictResolutionStrategy.MANUAL,
        description="Conflict resolution strategy",
    )

    # Retry settings
    max_retries: int = Field(
        default=3, ge=0, description="Maximum number of retries for failed operations"
    )
    retry_delay_seconds: int = Field(
        default=5, ge=0, description="Delay between retries in seconds"
    )

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v):
        """Validate label format."""
        for label in v:
            if not label or not label.strip():
                raise ValueError("Labels cannot be empty")
            if len(label) > 50:
                raise ValueError("Labels cannot exceed 50 characters")
            if not label.replace("-", "").replace("_", "").isalnum():
                raise ValueError(
                    "Labels can only contain alphanumeric characters, hyphens, and underscores"
                )
        return v

    @field_validator("assignees", "reviewers")
    @classmethod
    def validate_users(cls, v):
        """Validate user format."""
        for user in v:
            if not user or not user.strip():
                raise ValueError("Users cannot be empty")
            if len(user) > 100:
                raise ValueError("Usernames cannot exceed 100 characters")
        return v

    @field_validator("commit_message_template")
    @classmethod
    def validate_commit_template(cls, v):
        """Validate commit message template."""
        if v is not None:
            if not v.strip():
                raise ValueError("Commit message template cannot be empty")
            if len(v) > 500:
                raise ValueError("Commit message template cannot exceed 500 characters")

            # Check for required placeholders
            required_placeholders = ["{issue_id}", "{description}"]
            for placeholder in required_placeholders:
                if placeholder not in v:
                    raise ValueError(
                        f"Commit message template must include {placeholder}"
                    )

        return v

    @field_validator("output_path")
    @classmethod
    def validate_output_path(cls, v):
        """Validate output path for patches."""
        if v is not None:
            if not v.strip():
                raise ValueError("Output path cannot be empty")
            if not v.startswith("/"):
                raise ValueError("Output path must be absolute")
        return v

    @field_validator("branch_prefix", "branch_suffix")
    @classmethod
    def validate_branch_components(cls, v):
        """Validate branch prefix and suffix."""
        if v is not None:
            if not v.strip():
                raise ValueError("Branch component cannot be empty")
            if len(v) > 20:
                raise ValueError("Branch component cannot exceed 20 characters")
            if not v.replace("-", "").replace("_", "").isalnum():
                raise ValueError(
                    "Branch components can only contain alphanumeric characters, hyphens, and underscores"
                )
        return v

    def get_branch_name(self, issue_id: str) -> str:
        """Generate branch name for the given issue ID."""
        components = [self.branch_prefix, issue_id]
        if self.branch_suffix:
            components.append(self.branch_suffix)

        return "-".join(components)

    def get_commit_message(self, issue_id: str, description: str) -> str:
        """Generate commit message using template."""
        if self.commit_message_template:
            return self.commit_message_template.format(
                issue_id=issue_id, description=description
            )

        return f"SRE Fix: {issue_id} - {description}"

    def is_patch_strategy(self) -> bool:
        """Check if this is a patch-based strategy."""
        return self.strategy == RemediationStrategy.PATCH

    def is_direct_commit_strategy(self) -> bool:
        """Check if this is a direct commit strategy."""
        return self.strategy == RemediationStrategy.DIRECT_COMMIT

    def requires_branch_creation(self) -> bool:
        """Check if this strategy requires branch creation."""
        return self.strategy in [
            RemediationStrategy.PULL_REQUEST,
            RemediationStrategy.MERGE_REQUEST,
        ]
