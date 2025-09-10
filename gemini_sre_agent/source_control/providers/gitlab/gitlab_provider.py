"""GitLab provider implementation for source control operations."""

import logging
from typing import Any, Dict, List, Optional

import gitlab

from ....config.source_control_repositories import GitLabRepositoryConfig
from ...base_implementation import BaseSourceControlProvider
from ...error_handling import (
    ErrorHandlingFactory,
)
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


class GitLabProvider(BaseSourceControlProvider):
    """GitLab provider implementation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the GitLab provider."""
        super().__init__(config)
        self.repo_config = GitLabRepositoryConfig(**config)
        self.credentials: Optional[GitLabCredentials] = None
        self.gl: Optional[gitlab.Gitlab] = None
        self.project: Optional[Any] = None
        self.logger = logging.getLogger(__name__)

        # Initialize sub-modules (will be set after initialization)
        self.file_ops: Optional[GitLabFileOperations] = None
        self.branch_ops: Optional[GitLabBranchOperations] = None
        self.mr_ops: Optional[GitLabMergeRequestOperations] = None

        # Initialize error handling system
        self.error_handling_factory = ErrorHandlingFactory()
        self.error_handling_components: Optional[Dict[str, Any]] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    async def initialize(self) -> None:
        """Initialize the GitLab provider."""
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

            # Initialize error handling system
            self._initialize_error_handling(
                "gitlab", self.repo_config.error_handling.model_dump()
            )

            # Initialize sub-modules with error handling components
            self.file_ops = GitLabFileOperations(
                self.gl, self.project, self.logger, self._error_handling_components
            )
            self.branch_ops = GitLabBranchOperations(
                self.gl, self.project, self.logger, self._error_handling_components
            )
            self.mr_ops = GitLabMergeRequestOperations(
                self.gl, self.project, self.logger, self._error_handling_components
            )

            self.logger.info(f"GitLab provider initialized for project: {project_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize GitLab provider: {e}")
            raise

    async def cleanup(self) -> None:
        """Cleanup the GitLab provider."""
        self.gl = None
        self.project = None
        self.credentials = None
        self.file_ops = None
        self.branch_ops = None
        self.mr_ops = None
        self._error_handling_components = None

    async def get_capabilities(self) -> ProviderCapabilities:
        """Get provider capabilities."""
        if not self.mr_ops:
            raise RuntimeError("Provider not initialized")
        return await self.mr_ops.get_capabilities()

    async def get_health_status(self) -> ProviderHealth:
        """Get provider health status."""
        try:
            if not self.gl or not self.project:
                return ProviderHealth(
                    status="unhealthy",
                    message="Provider not initialized",
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
                message=f"Health check failed: {e}",
                additional_info={"error": str(e)},
            )

    # File operations - delegate to file_ops
    async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
        """Get file content from GitLab repository."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")
        return await self._execute_with_error_handling(
            "get_file_content", self.file_ops.get_file_content, path, ref
        )

    async def apply_remediation(
        self,
        path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
    ) -> RemediationResult:
        """Apply remediation to a file."""
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
        """Check if a file exists in the repository."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")
        return await self.file_ops.file_exists(path, ref)

    async def get_file_info(self, path: str, ref: Optional[str] = None) -> FileInfo:
        """Get file information."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")
        return await self.file_ops.get_file_info(path, ref)

    async def list_files(
        self, path: str = "", ref: Optional[str] = None
    ) -> List[FileInfo]:
        """List files in a directory."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")
        return await self.file_ops.list_files(path, ref)

    async def generate_patch(self, original: str, modified: str) -> str:
        """Generate a patch between original and modified content."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")
        return await self.file_ops.generate_patch(original, modified)

    async def apply_patch(self, patch: str, file_path: str) -> bool:
        """Apply a patch to a file."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")
        return await self.file_ops.apply_patch(patch, file_path)

    async def commit_changes(
        self,
        file_path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
    ) -> Optional[str]:
        """Commit changes to a file."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")
        return await self.file_ops.commit_changes(file_path, content, message, branch)

    # Branch operations - delegate to branch_ops
    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create a new branch."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")
        return await self.branch_ops.create_branch(name, base_ref)

    async def delete_branch(self, name: str) -> bool:
        """Delete a branch."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")
        return await self.branch_ops.delete_branch(name)

    async def list_branches(self) -> List[BranchInfo]:
        """List all branches."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")
        return await self.branch_ops.list_branches()

    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get information about a specific branch."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")
        return await self.branch_ops.get_branch_info(name)

    async def get_current_branch(self) -> str:
        """Get the current branch name."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")
        return await self.branch_ops.get_current_branch()

    async def get_repository_info(self) -> RepositoryInfo:
        """Get repository information."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")
        return await self.branch_ops.get_repository_info()

    async def check_conflicts(
        self,
        path: str,
        content: str,
        branch: Optional[str] = None,
    ) -> bool:
        """Check for conflicts between branches."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")
        # Use the default branch if no branch is specified
        feature_branch = branch or "main"
        base_branch = "main"  # This should be configurable

        try:
            conflict_info = await self.branch_ops.check_conflicts(
                path, base_branch, feature_branch
            )
            return conflict_info.has_conflicts
        except Exception as e:
            self.logger.error(f"Failed to check conflicts: {e}")
            return False

    async def resolve_conflicts(
        self,
        path: str,
        content: str,
        strategy: str = "manual",
    ) -> bool:
        """Resolve conflicts in a file."""
        if not self.branch_ops:
            raise RuntimeError("Provider not initialized")
        return await self.branch_ops.resolve_conflicts(path, content, strategy)

    # Git operations - delegate to file_ops
    async def get_file_history(self, path: str, limit: int = 10) -> List[CommitInfo]:
        """Get file commit history."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")
        history = await self.file_ops.get_file_history(path, limit)
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
        """Get diff between two commits."""
        if not self.file_ops:
            raise RuntimeError("Provider not initialized")
        return await self.file_ops.diff_between_commits(base_sha, head_sha)

    # Merge request operations - delegate to mr_ops
    async def create_merge_request(
        self,
        title: str,
        description: str,
        head_branch: str,
        base_branch: str,
        **kwargs: Any,
    ) -> RemediationResult:
        """Create a merge request."""
        if not self.mr_ops:
            raise RuntimeError("Provider not initialized")
        return await self.mr_ops.create_merge_request(
            title, description, head_branch, base_branch, **kwargs
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
        """Create a pull request (not supported for GitLab)."""
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

    # Batch operations (simplified implementation)
    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Execute multiple operations in batch."""
        results = []
        for operation in operations:
            try:
                if operation.operation_type == "create_file":
                    success = await self.commit_changes(
                        operation.file_path,
                        operation.content or "",
                        f"Create {operation.file_path}",
                    )
                elif operation.operation_type == "update_file":
                    success = await self.commit_changes(
                        operation.file_path,
                        operation.content or "",
                        f"Update {operation.file_path}",
                    )
                elif operation.operation_type == "delete_file":
                    # GitLab doesn't have a direct delete file API
                    success = False
                else:
                    success = False

                results.append(
                    OperationResult(
                        operation_id=operation.operation_id,
                        success=bool(success),
                        message=f"Executed {operation.operation_type} for {operation.file_path}",
                        file_path=operation.file_path,
                        error_details=(
                            ""
                            if success
                            else f"Failed to execute {operation.operation_type}"
                        ),
                        additional_info={},
                    )
                )
            except Exception as e:
                results.append(
                    OperationResult(
                        operation_id=operation.operation_id,
                        success=False,
                        message=f"Failed to execute {operation.operation_type}: {e}",
                        file_path=operation.file_path,
                        error_details=str(e),
                        additional_info={},
                    )
                )
        return results
