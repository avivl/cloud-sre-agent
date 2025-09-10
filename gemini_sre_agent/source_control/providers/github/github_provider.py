# gemini_sre_agent/source_control/providers/github_provider_refactored.py

"""
GitHub provider implementation for source control operations.

This module provides a concrete implementation of the SourceControlProvider
interface specifically for GitHub repositories.
"""

import logging
from typing import Any, Dict, List, Optional

from github import Github
from github.Repository import Repository

from ....config.source_control_repositories import GitHubRepositoryConfig
from ...base_implementation import BaseSourceControlProvider
from ...error_handling import (
    ErrorHandlingFactory,
    create_provider_error_handling,
)
from ...models import (
    BatchOperation,
    BranchInfo,
    CommitInfo,
    ConflictInfo,
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


class GitHubProvider(BaseSourceControlProvider):
    """GitHub implementation of the SourceControlProvider interface."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the GitHub provider with configuration."""
        super().__init__(config)
        # Convert config dict back to GitHubRepositoryConfig for type safety
        self.repo_config = GitHubRepositoryConfig(**config)
        self.credentials = (
            None  # Will be set later when credential management is integrated
        )
        self.logger = logging.getLogger("GitHubProvider")
        self.client: Optional[Github] = None
        self.repo: Optional[Repository] = None

        # Initialize component modules
        self.operations: Optional[GitHubOperations] = None
        self.pull_requests: Optional[GitHubPullRequests] = None
        self.utils: Optional[GitHubUtils] = None

        # Initialize error handling system
        self.error_handling_factory = ErrorHandlingFactory()
        self.error_handling_components: Optional[Dict[str, Any]] = None

    async def _setup_client(self) -> None:
        """Set up GitHub client and repository."""
        try:
            # Initialize GitHub client
            if self.credentials and "token" in self.credentials:
                self.client = Github(self.credentials["token"])
            else:
                # Use environment variable or config
                token = getattr(self.repo_config, "token", None)
                if not token:
                    raise ValueError("GitHub token is required")
                self.client = Github(token)

            # Get repository
            url_parts = self.repo_config.url.split("/")
            owner = url_parts[0]
            repo_name = url_parts[1]
            self.repo = self.client.get_repo(f"{owner}/{repo_name}")

            # Initialize component modules
            if self.client and self.repo:
                self.operations = GitHubOperations(self.client, self.repo, self.logger)
                self.pull_requests = GitHubPullRequests(
                    self.client, self.repo, self.logger
                )
                self.utils = GitHubUtils(self.client, self.repo, self.logger)

            # Initialize error handling system
            self.error_handling_components = create_provider_error_handling(
                "github", self.repo_config.error_handling.model_dump()
            )

        except Exception as e:
            self.logger.error(f"Failed to setup GitHub client: {e}")
            raise

    async def _teardown_client(self) -> None:
        """Clean up GitHub client resources."""
        self.client = None
        self.repo = None
        self.operations = None
        self.pull_requests = None
        self.utils = None
        self.error_handling_components = None

    async def test_connection(self) -> bool:
        """Test connection to GitHub."""
        if not self.utils:
            return False
        return await self.utils.test_connection()

    async def _with_retry(self, operation_func, *args, **kwargs):
        """Execute an operation with retry logic."""
        if not self.utils:
            raise RuntimeError("GitHub utils not initialized")
        return await self.utils._with_retry(operation_func, *args, **kwargs)

    # Delegate operations to component modules
    async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
        """Get file content from GitHub repository."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.get_file_content(path, ref)

    async def apply_remediation(
        self,
        path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
    ) -> RemediationResult:
        """Apply a remediation to a file."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.apply_remediation(path, content, message, branch)

    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create a new branch."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.create_branch(name, base_ref)

    async def delete_branch(self, name: str) -> bool:
        """Delete a branch."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.delete_branch(name)

    async def list_branches(self) -> List[BranchInfo]:
        """List all branches in the repository."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.list_branches()

    async def get_repository_info(self) -> RepositoryInfo:
        """Get repository information."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.get_repository_info()

    async def check_conflicts(
        self, path: str, content: str, branch: Optional[str] = None
    ) -> bool:
        """Check for merge conflicts between branches."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")

        # Use the default branch if no branch is specified
        feature_branch = branch or "main"
        base_branch = "main"  # This should be configurable

        try:
            conflict_info = await self.operations.check_conflicts(
                path, base_branch, feature_branch
            )
            return conflict_info.has_conflicts
        except Exception:
            # If we can't check conflicts, assume there are conflicts to be safe
            return True

    async def resolve_conflicts(
        self, path: str, content: str, strategy: str = "manual"
    ) -> bool:
        """Resolve merge conflicts in a file."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.resolve_conflicts(path, content, strategy)

    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Execute multiple operations in batch."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.batch_operations(operations)

    async def get_capabilities(self) -> ProviderCapabilities:
        """Get provider capabilities."""
        if not self.pull_requests:
            raise RuntimeError("GitHub pull requests not initialized")
        return await self.pull_requests.get_capabilities()

    async def create_pull_request(
        self, title: str, description: str, head_branch: str, base_branch: str, **kwargs
    ) -> RemediationResult:
        """Create a pull request with error handling."""
        if not self.pull_requests:
            raise RuntimeError("GitHub pull requests not initialized")

        # Use error handling if available
        if self.error_handling_components:
            resilient_manager = self.error_handling_components.get("resilient_manager")
            if resilient_manager:
                try:
                    result = await resilient_manager.execute_with_resilience(
                        "pull_request_operations",
                        self.pull_requests.create_pull_request,
                        title,
                        description,
                        head_branch,
                        base_branch,
                        kwargs.get("draft", False),
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to create pull request with error handling: {e}"
                    )
                    return RemediationResult(
                        success=False,
                        message=f"Failed to create pull request: {e}",
                        file_path="",
                        operation_type="pull_request",
                        commit_sha=None,
                        pull_request_url=None,
                        error_details=str(e),
                        additional_info={},
                    )
            else:
                result = await self.pull_requests.create_pull_request(
                    title,
                    description,
                    head_branch,
                    base_branch,
                    kwargs.get("draft", False),
                )
        else:
            result = await self.pull_requests.create_pull_request(
                title, description, head_branch, base_branch, kwargs.get("draft", False)
            )

        if result:
            return RemediationResult(
                success=True,
                message=f"Created pull request: {result.get('title', '')}",
                file_path="",
                operation_type="pull_request",
                commit_sha=None,
                pull_request_url=result.get("url"),
                error_details=None,
                additional_info=result,
            )
        else:
            return RemediationResult(
                success=False,
                message="Failed to create pull request",
                file_path="",
                operation_type="pull_request",
                commit_sha=None,
                pull_request_url=None,
                error_details="Failed to create pull request",
                additional_info={},
            )

    async def create_merge_request(
        self, title: str, description: str, head_branch: str, base_branch: str, **kwargs
    ) -> RemediationResult:
        """Create a merge request (GitHub uses pull requests)."""
        if not self.pull_requests:
            raise RuntimeError("GitHub pull requests not initialized")
        result = await self.pull_requests.create_merge_request(
            title, description, head_branch, base_branch
        )
        if result:
            return RemediationResult(
                success=True,
                message=f"Created merge request: {result.get('title', '')}",
                file_path="",
                operation_type="merge_request",
                commit_sha=None,
                pull_request_url=result.get("url"),
                error_details=None,
                additional_info=result,
            )
        else:
            return RemediationResult(
                success=False,
                message="Failed to create merge request",
                file_path="",
                operation_type="merge_request",
                commit_sha=None,
                pull_request_url=None,
                error_details="Failed to create merge request",
                additional_info={},
            )

    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if a file exists in the repository."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.file_exists(path, ref)

    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get information about a specific branch."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.get_branch_info(name)

    async def get_file_info(self, path: str, ref: Optional[str] = None) -> FileInfo:
        """Get detailed information about a file with error handling."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")

        # Use error handling if available
        if self.error_handling_components:
            resilient_manager = self.error_handling_components.get("resilient_manager")
            if resilient_manager:
                try:
                    return await resilient_manager.execute_with_resilience(
                        "file_operations", self.operations.get_file_info, path, ref
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to get file info with error handling: {e}"
                    )
                    # Return empty file info on error
                    return FileInfo(
                        path=path,
                        size=0,
                        sha="",
                        is_binary=False,
                        last_modified=None,
                    )
            else:
                return await self.operations.get_file_info(path, ref)
        else:
            return await self.operations.get_file_info(path, ref)

    async def refresh_credentials(self) -> bool:
        """Refresh GitHub credentials."""
        if not self.utils:
            raise RuntimeError("GitHub utils not initialized")
        return await self.utils.refresh_credentials()

    async def validate_credentials(self) -> bool:
        """Validate GitHub credentials."""
        if not self.utils:
            raise RuntimeError("GitHub utils not initialized")
        return await self.utils.validate_credentials()

    async def handle_operation_failure(self, operation: str, error: Exception) -> bool:
        """Handle operation failures with appropriate retry logic."""
        if not self.utils:
            raise RuntimeError("GitHub utils not initialized")
        return await self.utils.handle_operation_failure(operation, error)

    async def __aenter__(self):
        """Async context manager entry."""
        await self._setup_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._teardown_client()

    async def get_health_status(self) -> ProviderHealth:
        """Get health status of the GitHub provider."""
        if not self.utils:
            return ProviderHealth(
                status="unhealthy",
                message="GitHub utils not initialized",
                additional_info={"error": "Utils not initialized"},
            )
        return await self.utils.get_health_status()

    async def list_files(
        self, path: str = "", recursive: bool = True, ref: Optional[str] = None
    ) -> List[FileInfo]:
        """List files in the repository."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.list_files(path, ref)

    async def generate_patch(
        self, file_path: str, old_content: str, new_content: str
    ) -> str:
        """Generate a patch between old and new content."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.generate_patch(old_content, new_content)

    async def apply_patch(self, patch_content: str, file_path: str) -> bool:
        """Apply a patch to the repository."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.apply_patch(patch_content, file_path)

    async def commit_changes(
        self,
        file_path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
    ) -> Optional[str]:
        """Commit changes to a file."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.commit_changes(file_path, content, message, branch)

    async def get_file_history(self, path: str, limit: int = 10) -> List[CommitInfo]:
        """Get commit history for a file."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.get_file_history(path, limit)

    async def diff_between_commits(self, from_commit: str, to_commit: str) -> str:
        """Get diff between two commits."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.diff_between_commits(from_commit, to_commit)

    async def get_current_branch(self) -> str:
        """Get the current branch name."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        return await self.operations.get_current_branch()

    async def get_status(self) -> Dict[str, Any]:
        """Get current status of the GitHub provider."""
        if not self.utils:
            return {"error": "GitHub utils not initialized"}
        return await self.utils.get_status()

    async def execute_git_command(self, command: str, **kwargs) -> Dict[str, Any]:
        """Execute a git command (placeholder for GitHub API operations)."""
        if not self.utils:
            return {"error": "GitHub utils not initialized"}
        return await self.utils.execute_git_command(command, **kwargs)

    async def get_conflict_info(self, path: str) -> Optional[ConflictInfo]:
        """Get conflict information for a file."""
        if not self.operations:
            raise RuntimeError("GitHub operations not initialized")
        # This method needs to be implemented in the operations
        # For now, return None to indicate no conflict info available
        return None
