# gemini_sre_agent/source_control/providers/github/enhanced_github_provider.py

"""
Enhanced GitHub provider with comprehensive error handling integration.

This module provides an enhanced GitHub provider that integrates the new error handling
system including circuit breakers, retry mechanisms, error classification, graceful
degradation, health checks, and metrics collection.
"""

from typing import Any, Dict, List, Optional

from github import Github
from github.Repository import Repository

from ....config.source_control_repositories import GitHubRepositoryConfig
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
from .github_operations import GitHubOperations
from .github_pull_requests import GitHubPullRequests
from .github_utils import GitHubUtils


class EnhancedGitHubProvider(EnhancedBaseSourceControlProvider):
    """Enhanced GitHub provider with comprehensive error handling."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the enhanced GitHub provider."""
        super().__init__(config)

        # Convert config dict back to GitHubRepositoryConfig for type safety
        self.repo_config = GitHubRepositoryConfig(**config)
        self.credentials = (
            None  # Will be set later when credential management is integrated
        )
        self.client: Optional[Github] = None
        self.repo: Optional[Repository] = None

        # Initialize component modules
        self.operations: Optional[GitHubOperations] = None
        self.pull_requests: Optional[GitHubPullRequests] = None
        self.utils: Optional[GitHubUtils] = None

    async def initialize(self) -> None:
        """Initialize the GitHub provider with error handling."""
        try:
            # Initialize GitHub client
            await self._setup_client()

            # Initialize component modules
            if self.client and self.repo:
                self.operations = GitHubOperations(self.client, self.repo, self.logger)
                self.pull_requests = GitHubPullRequests(
                    self.client, self.repo, self.logger
                )
                self.utils = GitHubUtils(self.client, self.repo, self.logger)

            self.logger.info(
                f"Enhanced GitHub provider initialized for repository: {self.repo_config.name}"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize enhanced GitHub provider: {e}")
            raise

    async def _setup_client(self) -> None:
        """Set up the GitHub client with error handling."""
        try:
            # Extract credentials from config
            token = getattr(self.repo_config, "token", None)
            if not token:
                raise ValueError("GitHub token is required")

            # Initialize GitHub client
            self.client = Github(token)

            # Get repository
            repo_name = getattr(self.repo_config, "name", None)
            if repo_name:
                self.repo = self.client.get_repo(repo_name)
            else:
                raise ValueError("Repository name is required for GitHub provider")

        except Exception as e:
            self.logger.error(f"Failed to setup GitHub client: {e}")
            raise

    async def _teardown_client(self) -> None:
        """Tear down the GitHub client."""
        self.client = None
        self.repo = None

    async def _get_basic_health_status(self) -> ProviderHealth:
        """Get basic GitHub provider health status."""
        try:
            if not self.client or not self.repo:
                return ProviderHealth(
                    status="unhealthy",
                    message="GitHub client not initialized",
                    additional_info={},
                )

            # Test API connectivity
            user = self.client.get_user()
            repo_info = self.repo.raw_data

            return ProviderHealth(
                status="healthy",
                message="GitHub provider is operational",
                additional_info={
                    "user": user.login,
                    "repository": repo_info.get("full_name"),
                    "repository_id": repo_info.get("id"),
                    "default_branch": repo_info.get("default_branch"),
                    "private": repo_info.get("private"),
                },
            )
        except Exception as e:
            return ProviderHealth(
                status="unhealthy",
                message=f"GitHub health check failed: {e}",
                additional_info={"error": str(e)},
            )

    async def get_capabilities(self) -> ProviderCapabilities:
        """Get GitHub provider capabilities."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")
        # Return basic capabilities for GitHub
        return ProviderCapabilities(
            supports_pull_requests=True,
            supports_merge_requests=False,
            supports_direct_commits=True,
            supports_branch_operations=True,
            supports_file_history=True,
            supports_batch_operations=True,
            supports_patch_generation=True,
        )

    # File operations with error handling
    async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
        """Get file content with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "get_file_content", self.operations.get_file_content, path, ref
        )

    async def apply_remediation(
        self, path: str, content: str, message: str, branch: Optional[str] = None
    ) -> RemediationResult:
        """Apply remediation with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "apply_remediation",
            self.operations.apply_remediation,
            path,
            content,
            message,
            branch,
        )

    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if file exists with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "file_exists", self.operations.file_exists, path, ref
        )

    async def get_file_info(self, path: str, ref: Optional[str] = None) -> FileInfo:
        """Get file information with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "get_file_info", self.operations.get_file_info, path, ref
        )

    async def list_files(
        self, path: str = "", ref: Optional[str] = None
    ) -> List[FileInfo]:
        """List files with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "list_files", self.operations.list_files, path, ref
        )

    async def generate_patch(self, original: str, modified: str) -> str:
        """Generate patch with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "generate_patch", self.operations.generate_patch, original, modified
        )

    async def apply_patch(self, patch: str, file_path: str) -> bool:
        """Apply patch with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "apply_patch", self.operations.apply_patch, patch, file_path
        )

    async def commit_changes(
        self, file_path: str, content: str, message: str, branch: Optional[str] = None
    ) -> Optional[str]:
        """Commit changes with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "commit_changes",
            self.operations.commit_changes,
            file_path,
            content,
            message,
            branch,
        )

    # Branch operations with error handling
    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create branch with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "create_branch", self.operations.create_branch, name, base_ref
        )

    async def delete_branch(self, name: str) -> bool:
        """Delete branch with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "delete_branch", self.operations.delete_branch, name
        )

    async def list_branches(self) -> List[BranchInfo]:
        """List branches with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "list_branches", self.operations.list_branches
        )

    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get branch info with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "get_branch_info", self.operations.get_branch_info, name
        )

    async def get_current_branch(self) -> str:
        """Get current branch with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "get_current_branch", self.operations.get_current_branch
        )

    async def get_repository_info(self) -> RepositoryInfo:
        """Get repository info with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "get_repository_info", self.operations.get_repository_info
        )

    async def check_conflicts(
        self, path: str, content: str, branch: Optional[str] = None
    ) -> bool:
        """Check conflicts with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "check_conflicts", self.operations.check_conflicts, path, content, branch
        )

    async def resolve_conflicts(
        self, path: str, content: str, strategy: str = "manual"
    ) -> bool:
        """Resolve conflicts with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "resolve_conflicts",
            self.operations.resolve_conflicts,
            path,
            content,
            strategy,
        )

    # Git operations with error handling
    async def get_file_history(self, path: str, limit: int = 10) -> List[CommitInfo]:
        """Get file history with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "get_file_history", self.operations.get_file_history, path, limit
        )

    async def diff_between_commits(self, base_sha: str, head_sha: str) -> str:
        """Get diff between commits with error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "diff_between_commits",
            self.operations.diff_between_commits,
            base_sha,
            head_sha,
        )

    # Pull request operations with error handling
    async def create_pull_request(
        self,
        title: str,
        description: str,
        head_branch: str,
        base_branch: str,
        **kwargs: Any,
    ) -> RemediationResult:
        """Create pull request with error handling."""
        if not self.pull_requests:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "create_pull_request",
            self.pull_requests.create_pull_request,
            title,
            description,
            head_branch,
            base_branch,
            **kwargs,
        )

    # Merge request operations (not supported for GitHub)
    async def create_merge_request(
        self,
        title: str,
        description: str,
        head_branch: str,
        base_branch: str,
        **kwargs: Any,
    ) -> RemediationResult:
        """Create merge request (not supported for GitHub)."""
        return RemediationResult(
            success=False,
            message="Merge requests are not supported for GitHub provider",
            file_path="",
            operation_type="create_merge_request",
            commit_sha="",
            pull_request_url="",
            error_details="Merge requests are not supported for GitHub provider",
            additional_info={},
        )

    # Enhanced batch operations with error handling
    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Execute batch operations with comprehensive error handling."""
        if not self.operations:
            raise RuntimeError("Provider not initialized")

        return await self._execute_with_error_handling(
            "batch_operations", super().batch_operations, operations
        )

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await super().cleanup()
        await self._teardown_client()

        # Cleanup component modules
        self.operations = None
        self.pull_requests = None
        self.utils = None
