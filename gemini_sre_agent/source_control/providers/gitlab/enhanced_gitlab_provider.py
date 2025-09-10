# gemini_sre_agent/source_control/providers/gitlab/enhanced_gitlab_provider.py

"""
Enhanced GitLab provider with comprehensive error handling integration.

This module provides an enhanced GitLab provider that integrates the new error handling
system including circuit breakers, retry mechanisms, error classification, graceful
degradation, health checks, and metrics collection.
"""

from typing import Any, Dict, List, Optional

import gitlab

from ....config.source_control_repositories import GitLabRepositoryConfig
from ...enhanced_base_implementation import EnhancedBaseSourceControlProvider
from ...models import (
    BatchOperation,
    BranchInfo,
    CommitInfo,
    FileInfo,
    OperationResult,
    ProviderCapabilities,
    ProviderHealth,
    RemediationResult,
    RepositoryInfo,
)
from .gitlab_branch_operations import GitLabBranchOperations
from .gitlab_file_operations import GitLabFileOperations
from .gitlab_merge_request_operations import GitLabMergeRequestOperations
from .gitlab_models import GitLabCredentials


class EnhancedGitLabProvider(EnhancedBaseSourceControlProvider):
    """Enhanced GitLab provider with comprehensive error handling."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the enhanced GitLab provider."""
        super().__init__(config)

        self.repo_config = GitLabRepositoryConfig(**config)
        self.credentials: Optional[GitLabCredentials] = None
        self.gl: Optional[gitlab.Gitlab] = None
        self.project: Optional[Any] = None

        # Initialize sub-modules (will be set after initialization)
        self.file_ops: Optional[GitLabFileOperations] = None
        self.branch_ops: Optional[GitLabBranchOperations] = None
        self.mr_ops: Optional[GitLabMergeRequestOperations] = None

    async def initialize(self) -> None:
        """Initialize the GitLab provider with error handling."""
        try:
            # Initialize GitLab client
            await self._setup_client()

            # Initialize sub-modules
            if self.gl and self.project:
                self.file_ops = GitLabFileOperations(self.gl, self.project, self.logger)
                self.branch_ops = GitLabBranchOperations(
                    self.gl, self.project, self.logger
                )
                self.mr_ops = GitLabMergeRequestOperations(
                    self.gl, self.project, self.logger
                )

            self.logger.info(
                f"Enhanced GitLab provider initialized for project: {self.repo_config.name}"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize enhanced GitLab provider: {e}")
            raise

    async def _setup_client(self) -> None:
        """Set up the GitLab client with error handling."""
        try:
            # Extract credentials from config
            token = getattr(self.repo_config, "token", None)
            if not token:
                raise ValueError("GitLab token is required")

            self.credentials = GitLabCredentials(
                url=self.repo_config.url,
                token=token,
                api_version=getattr(self.repo_config, "api_version", "4"),
                timeout=getattr(self.repo_config, "timeout", 60),
                ssl_verify=getattr(self.repo_config, "ssl_verify", True),
            )

            # Initialize GitLab client
            self.gl = gitlab.Gitlab(
                self.credentials.url,
                private_token=self.credentials.token,
                api_version=self.credentials.api_version,
                timeout=self.credentials.timeout,
                ssl_verify=self.credentials.ssl_verify,
            )

            # Authenticate
            self.gl.auth()

            # Get project
            project_name = getattr(self.repo_config, "name", None)
            if project_name:
                self.project = self.gl.projects.get(project_name)
            else:
                raise ValueError("Project name is required for GitLab provider")

        except Exception as e:
            self.logger.error(f"Failed to setup GitLab client: {e}")
            raise

    async def _teardown_client(self) -> None:
        """Tear down the GitLab client."""
        self.gl = None
        self.project = None
        self.credentials = None

    async def _get_basic_health_status(self) -> ProviderHealth:
        """Get basic GitLab provider health status."""
        try:
            if not self.gl or not self.project:
                return ProviderHealth(
                    status="unhealthy",
                    message="GitLab client not initialized",
                    additional_info={},
                )

            # Test API connectivity
            self.gl.auth()
            project_info = self.project.attributes

            return ProviderHealth(
                status="healthy",
                message="GitLab provider is operational",
                additional_info={
                    "project_id": project_info.get("id"),
                    "project_name": project_info.get("name"),
                    "project_url": project_info.get("web_url"),
                    "default_branch": project_info.get("default_branch"),
                },
            )
        except Exception as e:
            return ProviderHealth(
                status="unhealthy",
                message=f"GitLab health check failed: {e}",
                additional_info={"error": str(e)},
            )

    async def get_capabilities(self) -> ProviderCapabilities:
        """Get GitLab provider capabilities."""
        if not self.mr_ops:
            raise RuntimeError("Provider not initialized")
        return await self.mr_ops.get_capabilities()

    # File operations with error handling
    async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
        """Get file content with error handling."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "get_file_content", self.file_ops.get_file_content, path, ref
        )

    async def apply_remediation(
        self, path: str, content: str, message: str, branch: Optional[str] = None
    ) -> RemediationResult:
        """Apply remediation with error handling."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "apply_remediation",
            self.file_ops.apply_remediation,
            path,
            content,
            message,
            branch,
        )

    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if file exists with error handling."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "file_exists", self.file_ops.file_exists, path, ref
        )

    async def get_file_info(self, path: str, ref: Optional[str] = None) -> FileInfo:
        """Get file information with error handling."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "get_file_info", self.file_ops.get_file_info, path, ref
        )

    async def list_files(
        self, path: str = "", ref: Optional[str] = None
    ) -> List[FileInfo]:
        """List files with error handling."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "list_files", self.file_ops.list_files, path, ref
        )

    async def generate_patch(self, original: str, modified: str) -> str:
        """Generate patch with error handling."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "generate_patch", self.file_ops.generate_patch, original, modified
        )

    async def apply_patch(self, patch: str, file_path: str) -> bool:
        """Apply patch with error handling."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "apply_patch", self.file_ops.apply_patch, patch, file_path
        )

    async def commit_changes(
        self, file_path: str, content: str, message: str, branch: Optional[str] = None
    ) -> Optional[str]:
        """Commit changes with error handling."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "commit_changes",
            self.file_ops.commit_changes,
            file_path,
            content,
            message,
            branch,
        )

    # Branch operations with error handling
    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create branch with error handling."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "create_branch", self.branch_ops.create_branch, name, base_ref
        )

    async def delete_branch(self, name: str) -> bool:
        """Delete branch with error handling."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "delete_branch", self.branch_ops.delete_branch, name
        )

    async def list_branches(self) -> List[BranchInfo]:
        """List branches with error handling."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "list_branches", self.branch_ops.list_branches
        )

    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get branch info with error handling."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "get_branch_info", self.branch_ops.get_branch_info, name
        )

    async def get_current_branch(self) -> str:
        """Get current branch with error handling."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "get_current_branch", self.branch_ops.get_current_branch
        )

    async def get_repository_info(self) -> RepositoryInfo:
        """Get repository info with error handling."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "get_repository_info", self.branch_ops.get_repository_info
        )

    async def check_conflicts(
        self, path: str, content: str, branch: Optional[str] = None
    ) -> bool:
        """Check conflicts with error handling."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "check_conflicts", self.branch_ops.check_conflicts, path, content, branch
        )

    async def resolve_conflicts(
        self, path: str, content: str, strategy: str = "manual"
    ) -> bool:
        """Resolve conflicts with error handling."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "resolve_conflicts",
            self.branch_ops.resolve_conflicts,
            path,
            content,
            strategy,
        )

    # Git operations with error handling
    async def get_file_history(self, path: str, limit: int = 10) -> List[CommitInfo]:
        """Get file history with error handling."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")

        history = await self._execute_with_error_handling(
            "get_file_history", self.file_ops.get_file_history, path, limit
        )
        # Convert dict to CommitInfo objects
        return [
            CommitInfo(
                sha=commit["sha"],
                message=commit["message"],
                author=commit["author"],
                author_email=commit["author_email"],
                committer=commit["committer"],
                committer_email=commit["committer_email"],
                date=commit["date"],
            )
            for commit in history
        ]

    async def diff_between_commits(self, base_sha: str, head_sha: str) -> str:
        """Get diff between commits with error handling."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "diff_between_commits",
            self.file_ops.diff_between_commits,
            base_sha,
            head_sha,
        )

    # Pull request operations (not supported for GitLab)
    async def create_pull_request(
        self,
        title: str,
        description: str,
        head_branch: str,
        base_branch: str,
        **kwargs: Any,
    ) -> RemediationResult:
        """Create pull request (not supported for GitLab)."""
        return RemediationResult(
            success=False,
            message="Pull requests are not supported for GitLab provider",
            file_path="",
            operation_type="create_pull_request",
            commit_sha="",
            pull_request_url="",
            error_details="Pull requests are not supported for GitLab provider",
            additional_info={},
        )

    # Merge request operations with error handling
    async def create_merge_request(
        self,
        title: str,
        description: str,
        head_branch: str,
        base_branch: str,
        **kwargs: Any,
    ) -> RemediationResult:
        """Create merge request with error handling."""
        if not self.mr_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "create_merge_request",
            self.mr_ops.create_merge_request,
            title,
            description,
            head_branch,
            base_branch,
            **kwargs,
        )

    # Enhanced batch operations with error handling
    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Execute batch operations with comprehensive error handling."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "batch_operations", super().batch_operations, operations
        )

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await super().cleanup()
        await self._teardown_client()

        # Cleanup sub-modules
        self.file_ops = None
        self.branch_ops = None
        self.mr_ops = None
