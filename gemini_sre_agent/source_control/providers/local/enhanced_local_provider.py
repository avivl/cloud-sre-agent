# gemini_sre_agent/source_control/providers/local/enhanced_local_provider.py

"""
Enhanced Local provider with comprehensive error handling integration.

This module provides an enhanced Local provider that integrates the new error handling
system including circuit breakers, retry mechanisms, error classification, graceful
degradation, health checks, and metrics collection.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ....config.source_control_repositories import LocalRepositoryConfig
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
from .local_batch_operations import LocalBatchOperations
from .local_file_operations import LocalFileOperations
from .local_git_operations import LocalGitOperations


class EnhancedLocalProvider(EnhancedBaseSourceControlProvider):
    """Enhanced Local provider with comprehensive error handling."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the enhanced Local provider."""
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
            self.root_path,
            self.git_enabled,
            self.auto_init_git,
            self.logger,
        )
        self.batch_ops = LocalBatchOperations(
            self.root_path,
            self.default_encoding,
            self.backup_files,
            self.backup_directory,
            self.logger,
        )

    async def initialize(self) -> None:
        """Initialize the Local provider with error handling."""
        try:
            # Initialize Git operations if enabled
            if self.git_enabled:
                # Git operations are initialized in the constructor
                pass

            self.logger.info(
                f"Enhanced Local provider initialized for path: {self.root_path}"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize enhanced Local provider: {e}")
            raise

    async def _get_basic_health_status(self) -> ProviderHealth:
        """Get basic Local provider health status."""
        try:
            # Check if root path exists and is accessible
            if not self.root_path.exists():
                return ProviderHealth(
                    status="unhealthy",
                    message="Root path does not exist",
                    additional_info={"path": str(self.root_path)},
                )

            if not self.root_path.is_dir():
                return ProviderHealth(
                    status="unhealthy",
                    message="Root path is not a directory",
                    additional_info={"path": str(self.root_path)},
                )

            # Check if we can read/write to the directory
            test_file = self.root_path / ".health_check_test"
            try:
                test_file.write_text("health check")
                test_file.unlink()
            except Exception as e:
                return ProviderHealth(
                    status="unhealthy",
                    message=f"Cannot write to directory: {e}",
                    additional_info={"path": str(self.root_path), "error": str(e)},
                )

            # Check Git status if enabled
            git_status = "disabled"
            if self.git_enabled:
                try:
                    # Simple check if .git directory exists
                    git_dir = self.root_path / ".git"
                    git_status = "enabled" if git_dir.exists() else "not_initialized"
                except Exception:
                    git_status = "error"

            return ProviderHealth(
                status="healthy",
                message="Local provider is operational",
                additional_info={
                    "path": str(self.root_path),
                    "git_enabled": self.git_enabled,
                    "git_status": git_status,
                    "backup_enabled": self.backup_files,
                    "encoding": self.default_encoding,
                },
            )
        except Exception as e:
            return ProviderHealth(
                status="unhealthy",
                message=f"Local health check failed: {e}",
                additional_info={"error": str(e)},
            )

    async def get_capabilities(self) -> ProviderCapabilities:
        """Get Local provider capabilities."""
        return ProviderCapabilities(
            supports_pull_requests=False,
            supports_merge_requests=False,
            supports_direct_commits=self.git_enabled,
            supports_branch_operations=self.git_enabled,
            supports_file_history=self.git_enabled,
            supports_batch_operations=True,
            supports_patch_generation=True,
        )

    # File operations with error handling
    async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
        """Get file content with error handling."""
        if not self.file_ops:
            raise RuntimeError("File operations not initialized")
        return await self._execute_with_error_handling(
            "get_file_content", self.file_ops.get_file_content, path
        )

    async def apply_remediation(
        self, path: str, content: str, message: str, branch: Optional[str] = None
    ) -> RemediationResult:
        """Apply remediation with error handling."""
        if not self.file_ops:
            raise RuntimeError("File operations not initialized")
        return await self._execute_with_error_handling(
            "apply_remediation", self.file_ops.apply_remediation, path, content, message
        )

    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if file exists with error handling."""
        if not self.file_ops:
            raise RuntimeError("File operations not initialized")
        return await self._execute_with_error_handling(
            "file_exists", self.file_ops.file_exists, path
        )

    async def get_file_info(self, path: str, ref: Optional[str] = None) -> FileInfo:
        """Get file information with error handling."""
        if not self.file_ops:
            raise RuntimeError("File operations not initialized")
        return await self._execute_with_error_handling(
            "get_file_info", self.file_ops.get_file_info, path
        )

    async def list_files(
        self, path: str = "", ref: Optional[str] = None
    ) -> List[FileInfo]:
        """List files with error handling."""
        if not self.file_ops:
            raise RuntimeError("File operations not initialized")
        return await self._execute_with_error_handling(
            "list_files", self.file_ops.list_files, path
        )

    async def generate_patch(self, original: str, modified: str) -> str:
        """Generate patch with error handling."""
        if not self.file_ops:
            raise RuntimeError("File operations not initialized")
        return await self._execute_with_error_handling(
            "generate_patch", self.file_ops.generate_patch, original, modified
        )

    async def apply_patch(self, patch: str, file_path: str) -> bool:
        """Apply patch with error handling."""
        if not self.file_ops:
            raise RuntimeError("File operations not initialized")
        return await self._execute_with_error_handling(
            "apply_patch", self.file_ops.apply_patch, patch, file_path
        )

    async def commit_changes(
        self, file_path: str, content: str, message: str, branch: Optional[str] = None
    ) -> Optional[str]:
        """Commit changes with error handling."""
        if not self.git_enabled:
            # For non-Git local operations, just write the file
            if not self.file_ops:
                raise RuntimeError("File operations not initialized")
            return await self._execute_with_error_handling(
                "commit_changes",
                self.file_ops.commit_changes,
                file_path,
                content,
                message,
            )

        # For Git-enabled operations, use file operations but with Git context
        if not self.file_ops:
            raise RuntimeError("File operations not initialized")
        return await self._execute_with_error_handling(
            "commit_changes", self.file_ops.commit_changes, file_path, content, message
        )

    # Branch operations with error handling (only if Git is enabled)
    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create branch with error handling."""
        if not self.git_enabled:
            raise RuntimeError("Git operations are not enabled")
        if not self.git_ops:
            raise RuntimeError("Git operations not initialized")

        return await self._execute_with_error_handling(
            "create_branch", self.git_ops.create_branch, name, base_ref
        )

    async def delete_branch(self, name: str) -> bool:
        """Delete branch with error handling."""
        if not self.git_enabled:
            raise RuntimeError("Git operations are not enabled")
        if not self.git_ops:
            raise RuntimeError("Git operations not initialized")

        return await self._execute_with_error_handling(
            "delete_branch", self.git_ops.delete_branch, name
        )

    async def list_branches(self) -> List[BranchInfo]:
        """List branches with error handling."""
        if not self.git_enabled:
            return []
        if not self.git_ops:
            raise RuntimeError("Git operations not initialized")

        return await self._execute_with_error_handling(
            "list_branches", self.git_ops.list_branches
        )

    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get branch info with error handling."""
        if not self.git_enabled:
            return None
        if not self.git_ops:
            raise RuntimeError("Git operations not initialized")

        return await self._execute_with_error_handling(
            "get_branch_info", self.git_ops.get_branch_info, name
        )

    async def get_current_branch(self) -> str:
        """Get current branch with error handling."""
        if not self.git_enabled:
            return "main"  # Default branch name for non-Git operations
        if not self.git_ops:
            raise RuntimeError("Git operations not initialized")

        return await self._execute_with_error_handling(
            "get_current_branch", self.git_ops.get_current_branch
        )

    async def get_repository_info(self) -> RepositoryInfo:
        """Get repository info with error handling."""
        if not self.git_enabled:
            return RepositoryInfo(
                name=self.root_path.name,
                url=str(self.root_path),
                default_branch="main",
                is_private=True,
            )
        if not self.git_ops:
            raise RuntimeError("Git operations not initialized")

        return await self._execute_with_error_handling(
            "get_repository_info", self.git_ops.get_repository_info
        )

    async def check_conflicts(
        self, path: str, content: str, branch: Optional[str] = None
    ) -> bool:
        """Check conflicts with error handling."""
        if not self.git_enabled:
            return False  # No conflicts for non-Git operations
        if not self.git_ops:
            raise RuntimeError("Git operations not initialized")

        return await self._execute_with_error_handling(
            "check_conflicts", self.git_ops.check_conflicts, path, content, branch
        )

    async def resolve_conflicts(
        self, path: str, content: str, strategy: str = "manual"
    ) -> bool:
        """Resolve conflicts with error handling."""
        if not self.git_enabled:
            return True  # No conflicts to resolve for non-Git operations
        if not self.git_ops:
            raise RuntimeError("Git operations not initialized")

        return await self._execute_with_error_handling(
            "resolve_conflicts", self.git_ops.resolve_conflicts, path, content, strategy
        )

    # Git operations with error handling (only if Git is enabled)
    async def get_file_history(self, path: str, limit: int = 10) -> List[CommitInfo]:
        """Get file history with error handling."""
        if not self.git_enabled:
            return []  # No history for non-Git operations
        if not self.git_ops:
            raise RuntimeError("Git operations not initialized")

        return await self._execute_with_error_handling(
            "get_file_history", self.git_ops.get_file_history, path, limit
        )

    async def diff_between_commits(self, base_sha: str, head_sha: str) -> str:
        """Get diff between commits with error handling."""
        if not self.git_enabled:
            return ""  # No diff for non-Git operations
        if not self.git_ops:
            raise RuntimeError("Git operations not initialized")

        return await self._execute_with_error_handling(
            "diff_between_commits",
            self.git_ops.diff_between_commits,
            base_sha,
            head_sha,
        )

    # Pull request operations (not supported for Local)
    async def create_pull_request(
        self,
        title: str,
        description: str,
        head_branch: str,
        base_branch: str,
        **kwargs: Any,
    ) -> RemediationResult:
        """Create pull request (not supported for Local provider)."""
        return RemediationResult(
            success=False,
            message="Pull requests are not supported for Local provider",
            file_path="",
            operation_type="create_pull_request",
            commit_sha="",
            pull_request_url="",
            error_details="Pull requests are not supported for Local provider",
            additional_info={},
        )

    # Merge request operations (not supported for Local)
    async def create_merge_request(
        self,
        title: str,
        description: str,
        head_branch: str,
        base_branch: str,
        **kwargs: Any,
    ) -> RemediationResult:
        """Create merge request (not supported for Local provider)."""
        return RemediationResult(
            success=False,
            message="Merge requests are not supported for Local provider",
            file_path="",
            operation_type="create_merge_request",
            commit_sha="",
            pull_request_url="",
            error_details="Merge requests are not supported for Local provider",
            additional_info={},
        )

    # Enhanced batch operations with error handling
    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Execute batch operations with comprehensive error handling."""
        if not self.batch_ops:
            raise RuntimeError("Batch operations not initialized")
        return await self._execute_with_error_handling(
            "batch_operations", self.batch_ops.batch_operations, operations
        )

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await super().cleanup()

        # Cleanup sub-modules
        self.file_ops = None
        self.git_ops = None
        self.batch_ops = None
