# gemini_sre_agent/source_control/providers/github/github_operations.py

"""
GitHub provider operations module.

This module orchestrates the core file and repository operations for the GitHub provider.
"""

import logging
from typing import Any, Dict, List, Optional

from github import Github
from github.Repository import Repository

from ...models import (
    BatchOperation,
    BranchInfo,
    CommitInfo,
    ConflictInfo,
    FileInfo,
    OperationResult,
    RemediationResult,
    RepositoryInfo,
)
from .github_batch_operations import GitHubBatchOperations
from .github_branch_operations import GitHubBranchOperations
from .github_file_operations import GitHubFileOperations


class GitHubOperations:
    """Orchestrates core file and repository operations for GitHub."""

    def __init__(
        self,
        client: Github,
        repo: Repository,
        logger: logging.Logger,
        error_handling_components: Optional[Dict[str, Any]] = None,
    ):
        """Initialize operations with GitHub client and repository."""
        self.client = client
        self.repo = repo
        self.logger = logger
        self.error_handling_components = error_handling_components

        # Initialize sub-modules with error handling components
        self.file_ops = GitHubFileOperations(
            client, repo, logger, error_handling_components
        )
        self.branch_ops = GitHubBranchOperations(
            client, repo, logger, error_handling_components
        )
        self.batch_ops = GitHubBatchOperations(
            client, repo, logger, error_handling_components
        )

    # File operations - delegate to file_ops
    async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
        """Get file content from GitHub repository."""
        return await self.file_ops.get_file_content(path, ref)

    async def apply_remediation(
        self,
        file_path: str,
        remediation: str,
        commit_message: str,
        branch: Optional[str] = None,
    ) -> RemediationResult:
        """Apply remediation to a file."""
        return await self.file_ops.apply_remediation(
            file_path, remediation, commit_message, branch
        )

    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if a file exists in the repository."""
        return await self.file_ops.file_exists(path, ref)

    async def get_file_info(self, path: str, ref: Optional[str] = None) -> FileInfo:
        """Get file information."""
        return await self.file_ops.get_file_info(path, ref)

    async def list_files(
        self, path: str = "", ref: Optional[str] = None
    ) -> List[FileInfo]:
        """List files in a directory."""
        return await self.file_ops.list_files(path, ref)

    async def generate_patch(self, original: str, modified: str) -> str:
        """Generate a patch between original and modified content."""
        return await self.file_ops.generate_patch(original, modified)

    async def apply_patch(self, patch: str, file_path: str) -> bool:
        """Apply a patch to a file."""
        return await self.file_ops.apply_patch(patch, file_path)

    async def commit_changes(
        self,
        file_path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
    ) -> Optional[str]:
        """Commit changes to a file."""
        return await self.file_ops.commit_changes(file_path, content, message, branch)

    async def get_file_history(self, path: str, limit: int = 10) -> List[CommitInfo]:
        """Get file commit history."""
        return await self.file_ops.get_file_history(path, limit)

    async def diff_between_commits(self, base_sha: str, head_sha: str) -> str:
        """Get diff between two commits."""
        return await self.file_ops.diff_between_commits(base_sha, head_sha)

    # Branch operations - delegate to branch_ops
    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create a new branch."""
        return await self.branch_ops.create_branch(name, base_ref)

    async def delete_branch(self, name: str) -> bool:
        """Delete a branch."""
        return await self.branch_ops.delete_branch(name)

    async def list_branches(self) -> List[BranchInfo]:
        """List all branches."""
        return await self.branch_ops.list_branches()

    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get information about a specific branch."""
        return await self.branch_ops.get_branch_info(name)

    async def get_current_branch(self) -> str:
        """Get the current branch name."""
        return await self.branch_ops.get_current_branch()

    async def get_repository_info(self) -> RepositoryInfo:
        """Get repository information."""
        return await self.branch_ops.get_repository_info()

    async def check_conflicts(
        self,
        file_path: str,
        base_branch: str,
        feature_branch: str,
    ) -> ConflictInfo:
        """Check for conflicts between branches."""
        return await self.branch_ops.check_conflicts(
            file_path, base_branch, feature_branch
        )

    async def resolve_conflicts(
        self,
        file_path: str,
        resolution: str,
        commit_message: str,
    ) -> bool:
        """Resolve conflicts in a file."""
        return await self.branch_ops.resolve_conflicts(
            file_path, resolution, commit_message
        )

    # Batch operations - delegate to batch_ops
    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Execute multiple operations in batch."""
        return await self.batch_ops.batch_operations(operations)
