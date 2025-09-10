"""Local filesystem provider with Git integration and patch generation capabilities."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from gemini_sre_agent.config.source_control_repositories import LocalRepositoryConfig
from gemini_sre_agent.source_control.base_implementation import (
    BaseSourceControlProvider,
)
from gemini_sre_agent.source_control.models import (
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

from .local_batch_operations import LocalBatchOperations
from .local_file_operations import LocalFileOperations
from .local_git_operations import LocalGitOperations


class LocalProvider(BaseSourceControlProvider):
    """Provider for local filesystem operations with Git integration and patch generation capabilities."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the local provider with configuration."""
        super().__init__(config)
        # Convert config dict back to LocalRepositoryConfig for type safety
        self.repo_config = LocalRepositoryConfig(**config)
        self.root_path = Path(self.repo_config.path).expanduser().resolve()
        self.git_enabled = getattr(self.repo_config, "git_enabled", False)
        self.auto_init_git = getattr(self.repo_config, "auto_init_git", False)
        self.default_encoding = getattr(self.repo_config, "default_encoding", "utf-8")
        self.backup_files = getattr(self.repo_config, "backup_files", True)
        self.backup_directory = getattr(self.repo_config, "backup_directory", None)

        # Initialize sub-modules
        self.file_ops = LocalFileOperations(
            self.root_path,
            self.default_encoding,
            self.backup_files,
            self.backup_directory,
            self.logger,
        )
        self.git_ops = LocalGitOperations(
            self.root_path, self.git_enabled, self.auto_init_git, self.logger
        )
        self.batch_ops = LocalBatchOperations(
            self.root_path,
            self.default_encoding,
            self.backup_files,
            self.backup_directory,
            self.logger,
        )

    async def get_capabilities(self) -> ProviderCapabilities:
        """Get provider capabilities."""
        return ProviderCapabilities(
            supports_pull_requests=False,
            supports_merge_requests=False,
            supports_direct_commits=True,
            supports_patch_generation=True,
            supports_branch_operations=self.git_enabled,
            supports_file_history=self.git_enabled,
            supports_batch_operations=True,
        )

    async def get_health_status(self) -> ProviderHealth:
        """Get provider health status."""
        try:
            # Check if root path exists and is accessible
            if not self.root_path.exists():
                return ProviderHealth(
                    status="unhealthy",
                    message="Root path does not exist",
                    additional_info={"root_path": str(self.root_path)},
                )

            # Check Git status if enabled
            git_status = "disabled"
            if self.git_enabled and self.git_ops.repo:
                git_status = "enabled"
            elif self.git_enabled and not self.git_ops.repo:
                git_status = "error"

            return ProviderHealth(
                status="healthy",
                message="Local provider is operational",
                additional_info={
                    "root_path": str(self.root_path),
                    "git_enabled": self.git_enabled,
                    "git_status": git_status,
                    "backup_enabled": self.backup_files,
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
        """Get file content from local filesystem."""
        return self.file_ops.get_file_content(path)

    async def apply_remediation(
        self,
        path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
    ) -> RemediationResult:
        """Apply remediation to a file."""
        return self.file_ops.apply_remediation(path, content, message)

    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if a file exists."""
        return self.file_ops.file_exists(path)

    async def get_file_info(self, path: str, ref: Optional[str] = None) -> FileInfo:
        """Get file information."""
        return self.file_ops.get_file_info(path)

    async def list_files(
        self, path: str = "", ref: Optional[str] = None
    ) -> List[FileInfo]:
        """List files in a directory."""
        return self.file_ops.list_files(path)

    async def generate_patch(self, original: str, modified: str) -> str:
        """Generate a patch between original and modified content."""
        return self.file_ops.generate_patch(original, modified)

    async def apply_patch(self, patch: str, file_path: str) -> bool:
        """Apply a patch to a file."""
        return self.file_ops.apply_patch(patch, file_path)

    async def commit_changes(
        self,
        file_path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
    ) -> Optional[str]:
        """Commit changes to a file."""
        success = self.file_ops.commit_changes(file_path, content, message)
        return "local_commit" if success else None

    # Branch operations - delegate to git_ops
    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create a new branch."""
        return self.git_ops.create_branch(name, base_ref)

    async def delete_branch(self, name: str) -> bool:
        """Delete a branch."""
        return self.git_ops.delete_branch(name)

    async def list_branches(self) -> List[BranchInfo]:
        """List all branches."""
        return self.git_ops.list_branches()

    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get information about a specific branch."""
        return self.git_ops.get_branch_info(name)

    async def get_current_branch(self) -> str:
        """Get the current branch name."""
        return self.git_ops.get_current_branch()

    async def get_repository_info(self) -> RepositoryInfo:
        """Get repository information."""
        return self.git_ops.get_repository_info()

    async def check_conflicts(
        self,
        path: str,
        content: str,
        branch: Optional[str] = None,
    ) -> bool:
        """Check for conflicts between branches."""
        # Use the default branch if no branch is specified
        feature_branch = branch or "main"
        base_branch = "main"  # This should be configurable

        try:
            conflict_info = self.git_ops.check_conflicts(
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
        return self.git_ops.resolve_conflicts(path, content, strategy)

    # Git operations - delegate to git_ops
    async def get_file_history(self, path: str, limit: int = 10) -> List[CommitInfo]:
        """Get file commit history."""
        return self.git_ops.get_file_history(path, limit)

    async def diff_between_commits(self, base_sha: str, head_sha: str) -> str:
        """Get diff between two commits."""
        return self.git_ops.diff_between_commits(base_sha, head_sha)

    def execute_git_command(self, command: List[str]) -> str:
        """Execute a Git command and return output."""
        return self.git_ops.execute_git_command(command)

    # Batch operations - delegate to batch_ops
    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Execute multiple operations in batch."""
        return self.batch_ops.batch_operations(operations)

    # Pull request operations (not supported for local provider)
    async def create_pull_request(
        self,
        title: str,
        description: str,
        head_branch: str,
        base_branch: str,
        **kwargs: Any,
    ) -> RemediationResult:
        """Create a pull request (not supported for local provider)."""
        return RemediationResult(
            success=False,
            message="Pull requests are not supported for local provider",
            file_path="",
            operation_type="create_pull_request",
            commit_sha="",
            pull_request_url="",
            error_details="Pull requests are not supported for local provider",
            additional_info={},
        )

    async def create_merge_request(
        self,
        title: str,
        description: str,
        head_branch: str,
        base_branch: str,
        **kwargs: Any,
    ) -> RemediationResult:
        """Create a merge request (not supported for local provider)."""
        return RemediationResult(
            success=False,
            message="Merge requests are not supported for local provider",
            file_path="",
            operation_type="create_merge_request",
            commit_sha="",
            pull_request_url="",
            error_details="Merge requests are not supported for local provider",
            additional_info={},
        )
