# gemini_sre_agent/source_control/providers/github_provider.py

"""
GitHub provider implementation for source control operations.

This module provides a concrete implementation of the SourceControlProvider
interface specifically for GitHub repositories.
"""

import asyncio
import base64
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from github import Github, GithubException
from github.Repository import Repository

from ...config.source_control_repositories import GitHubRepositoryConfig
from ..base_implementation import BaseSourceControlProvider
from ..models import (
    BatchOperation,
    BranchInfo,
    FileInfo,
    OperationResult,
    OperationStatus,
    ProviderCapabilities,
    RemediationResult,
    RepositoryInfo,
)


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
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = config.get("api_base_url", "https://api.github.com")
        self.retry_count = 3
        self.retry_delay = 2  # seconds

    async def _setup_client(self) -> None:
        """Set up GitHub client and repository connection."""
        # Initialize aiohttp session for async operations
        self.session = aiohttp.ClientSession()

        # Get credentials
        if not self.credentials:
            raise ValueError("GitHub credentials are required")

        token = self.credentials.get_token()
        if not token:
            raise ValueError("GitHub token is required")

        # Initialize PyGithub client
        self.client = Github(base_url=self.base_url, login_or_token=token)

        # Get repository reference
        self.repo = self.client.get_repo(
            f"{self.repo_config.get_owner_and_repo_name()[0]}/{self.repo_config.get_owner_and_repo_name()[1]}"
        )

    async def _teardown_client(self) -> None:
        """Clean up resources."""
        if self.client:
            self.client.close()
        if self.session:
            await self.session.close()

    async def test_connection(self) -> bool:
        """Test if the connection to GitHub is working."""
        try:
            if self.repo is None:
                raise RuntimeError("Repository not initialized")
            # Simple API call to verify connection
            self.repo.get_branches()[0]
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    async def _with_retry(self, operation_func, *args, **kwargs):
        """Execute an operation with automatic retry for rate limiting."""
        for attempt in range(self.retry_count):
            try:
                return await operation_func(*args, **kwargs)
            except GithubException as e:
                if e.status == 403 and "rate limit exceeded" in str(e).lower():
                    if attempt < self.retry_count - 1:
                        wait_time = self.retry_delay * (2**attempt)
                        self.logger.warning(
                            f"Rate limit exceeded. Waiting {wait_time}s before retry."
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        raise
                else:
                    raise

    async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
        """Get file content from the repository."""

        async def _get_file():
            if self.repo is None:
                raise RuntimeError("Repository not initialized")
            try:
                branch_name = ref or self.repo_config.branch or "main"
                content = self.repo.get_contents(path, ref=branch_name)

                if isinstance(content, list):
                    raise ValueError(f"Path {path} is a directory, not a file")

                return base64.b64decode(content.content).decode("utf-8")
            except GithubException as e:
                if e.status == 404:
                    raise FileNotFoundError(f"File {path} not found") from e
                raise

        result = await self._with_retry(_get_file)
        if result is None:
            raise FileNotFoundError(f"File {path} not found")
        return result

    async def apply_remediation(
        self,
        path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
    ) -> RemediationResult:
        """Apply remediation by creating a pull request with the changes."""
        if self.repo is None:
            raise RuntimeError("Repository not initialized")
        try:
            # Use provided branch or create a new one
            if branch is None:
                branch_name = f"sre-fix-{int(datetime.now().timestamp())}"
                await self.create_branch(branch_name)
            else:
                branch_name = branch

            # Update the file in the new branch
            try:
                # Try to get existing file to get its SHA
                existing_file = self.repo.get_contents(path, ref=branch_name)
                if isinstance(existing_file, list):
                    raise ValueError(f"Path {path} is a directory, not a file")
                sha = existing_file.sha
                # Update existing file
                self.repo.update_file(
                    path=path,
                    message=message,
                    content=content,
                    sha=sha,
                    branch=branch_name,
                )
            except GithubException as e:
                if e.status == 404:
                    # File doesn't exist, create it
                    self.repo.create_file(
                        path=path, message=message, content=content, branch=branch_name
                    )
                else:
                    raise

            # Create pull request
            pr = self.repo.create_pull(
                title=f"SRE Fix: {message}",
                body=f"Automated remediation for {path}\n\n{message}",
                head=branch_name,
                base=self.repo_config.branch or "main",
            )

            return RemediationResult(
                success=True,
                status=OperationStatus.SUCCESS,
                commit_id=pr.head.sha,
                message=f"Created PR #{pr.number}: {pr.html_url}",
                details={
                    "pull_request_number": pr.number,
                    "pull_request_url": pr.html_url,
                    "branch_name": branch_name,
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to apply remediation: {str(e)}")
            return RemediationResult(
                success=False, status=OperationStatus.FAILURE, error=str(e)
            )

    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create a new branch in the repository."""

        async def _create():
            if self.repo is None:
                raise RuntimeError("Repository not initialized")
            # Get the source branch reference
            source_branch = base_ref or self.repo_config.branch or "main"
            source_ref = self.repo.get_git_ref(f"heads/{source_branch}")

            # Create new branch with the same commit
            self.repo.create_git_ref(f"refs/heads/{name}", source_ref.object.sha)
            return True

        result = await self._with_retry(_create)
        return result is True

    async def delete_branch(self, name: str) -> bool:
        """Delete a branch from the repository."""

        async def _delete():
            if self.repo is None:
                raise RuntimeError("Repository not initialized")
            try:
                ref = self.repo.get_git_ref(f"heads/{name}")
                ref.delete()
                return True
            except GithubException as e:
                if e.status == 404:
                    self.logger.warning(f"Branch {name} not found")
                    return False
                raise

        result = await self._with_retry(_delete)
        return result is True

    async def list_branches(self) -> List[BranchInfo]:
        """List all branches in the repository."""

        async def _list():
            if self.repo is None:
                raise RuntimeError("Repository not initialized")
            branches = []
            for branch in self.repo.get_branches():
                branches.append(
                    BranchInfo(
                        name=branch.name,
                        sha=branch.commit.sha,
                        is_protected=branch.protected,
                        last_commit=datetime.now(),  # GitHub doesn't provide this easily
                    )
                )
            return branches

        result = await self._with_retry(_list)
        return result or []

    async def get_repository_info(self) -> RepositoryInfo:
        """Get repository information."""
        if self.repo is None:
            raise RuntimeError("Repository not initialized")

        return RepositoryInfo(
            name=self.repo.name,
            owner=self.repo.owner.login,
            default_branch=self.repo.default_branch,
            url=self.repo.html_url,
            is_private=self.repo.private,
            created_at=self.repo.created_at,
            updated_at=self.repo.updated_at,
            description=self.repo.description,
            additional_info={
                "full_name": self.repo.full_name,
                "clone_url": self.repo.clone_url,
                "ssh_url": self.repo.ssh_url,
                "language": self.repo.language,
                "stars": self.repo.stargazers_count,
                "forks": self.repo.forks_count,
            },
        )

    async def check_conflicts(
        self,
        path: str,
        content: str,
        branch: Optional[str] = None,
    ) -> bool:
        """Check if there would be conflicts when applying changes."""
        # For GitHub, we can't easily check conflicts without creating a PR
        # This is a simplified implementation
        return False

    async def resolve_conflicts(
        self,
        path: str,
        content: str,
        strategy: str = "manual",
    ) -> bool:
        """Resolve conflicts by applying changes."""
        # For GitHub, conflict resolution is typically done through PRs
        # This is a placeholder implementation
        return True

    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Execute multiple operations in batch."""
        results = []
        for operation in operations:
            try:
                if operation.operation_type == "update_file":
                    if operation.path and operation.content:
                        await self.apply_remediation(
                            operation.path,
                            operation.content,
                            operation.message or "Batch update",
                        )
                        results.append(
                            OperationResult(
                                operation_id=operation.operation_id,
                                status=OperationStatus.SUCCESS,
                                success=True,
                            )
                        )
                    else:
                        results.append(
                            OperationResult(
                                operation_id=operation.operation_id,
                                status=OperationStatus.FAILURE,
                                success=False,
                                error="Missing path or content",
                            )
                        )
                elif operation.operation_type == "create_branch":
                    if operation.parameters and "name" in operation.parameters:
                        success = await self.create_branch(operation.parameters["name"])
                        results.append(
                            OperationResult(
                                operation_id=operation.operation_id,
                                status=(
                                    OperationStatus.SUCCESS
                                    if success
                                    else OperationStatus.FAILURE
                                ),
                                success=success,
                            )
                        )
                    else:
                        results.append(
                            OperationResult(
                                operation_id=operation.operation_id,
                                status=OperationStatus.FAILURE,
                                success=False,
                                error="Missing branch name",
                            )
                        )
                else:
                    results.append(
                        OperationResult(
                            operation_id=operation.operation_id,
                            status=OperationStatus.FAILURE,
                            success=False,
                            error="Unsupported operation type",
                        )
                    )
            except Exception as e:
                self.logger.error(f"Batch operation failed: {str(e)}")
                results.append(
                    OperationResult(
                        operation_id=operation.operation_id,
                        status=OperationStatus.FAILURE,
                        success=False,
                        error=str(e),
                    )
                )

        return results

    async def get_capabilities(self) -> ProviderCapabilities:
        """Get provider capabilities."""
        return ProviderCapabilities(
            supports_branches=True,
            supports_pull_requests=True,
            supports_direct_commits=True,
            supports_batch_operations=True,
            supports_conflict_resolution=True,
            max_file_size=100 * 1024 * 1024,  # 100MB
            max_batch_size=100,
            additional_capabilities={
                "supports_conflict_detection": False,
                "supports_auto_merge": True,
                "rate_limit_requests_per_hour": 5000,
            },
        )

    async def create_pull_request(
        self, title: str, description: str, head_branch: str, base_branch: str, **kwargs
    ) -> RemediationResult:
        """Create a pull request."""
        if self.repo is None:
            raise RuntimeError("Repository not initialized")
        try:
            pr = self.repo.create_pull(
                title=title,
                body=description,
                head=head_branch,
                base=base_branch,
            )
            return RemediationResult(
                success=True,
                status=OperationStatus.SUCCESS,
                commit_id=pr.head.sha,
                message=f"Pull request created: {pr.html_url}",
                details={"pr_number": pr.number, "pr_url": pr.html_url},
            )
        except Exception as e:
            return RemediationResult(
                success=False,
                status=OperationStatus.FAILURE,
                error=str(e),
            )

    async def create_merge_request(
        self, title: str, description: str, head_branch: str, base_branch: str, **kwargs
    ) -> RemediationResult:
        """Create a merge request (GitHub doesn't support merge requests, use pull requests)."""
        return await self.create_pull_request(
            title, description, head_branch, base_branch, **kwargs
        )

    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if a file exists at the given path."""
        if self.repo is None:
            raise RuntimeError("Repository not initialized")
        try:
            branch_name = ref or self.repo_config.branch or "main"
            content = self.repo.get_contents(path, ref=branch_name)
            return not isinstance(content, list)  # If it's a list, it's a directory
        except Exception:
            return False

    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get information about a specific branch."""
        if self.repo is None:
            raise RuntimeError("Repository not initialized")
        try:
            branch = self.repo.get_branch(name)
            return BranchInfo(
                name=branch.name,
                sha=branch.commit.sha,
                is_protected=branch.protected,
                last_commit=datetime.now(),  # GitHub doesn't provide this easily
            )
        except Exception:
            return None

    async def get_file_info(self, path: str, ref: Optional[str] = None) -> FileInfo:
        """Get information about a file."""
        if self.repo is None:
            raise RuntimeError("Repository not initialized")
        try:
            branch_name = ref or self.repo_config.branch or "main"
            content = self.repo.get_contents(path, ref=branch_name)
            if isinstance(content, list):
                raise ValueError(f"Path {path} is a directory, not a file")
            return FileInfo(
                path=path,
                size=content.size,
                last_modified=datetime.now(),
                sha=content.sha,
                content_type=content.type,
                is_binary=content.encoding == "base64",
            )
        except Exception as e:
            raise FileNotFoundError(f"File {path} not found") from e

    async def refresh_credentials(self) -> bool:
        """Refresh authentication credentials."""
        # For token-based auth, credentials don't need refreshing
        return True

    async def validate_credentials(self) -> bool:
        """Validate that credentials are working."""
        return await self.test_connection()

    async def handle_operation_failure(self, operation: str, error: Exception) -> bool:
        """Handle operation failures with appropriate retry logic."""
        if isinstance(error, GithubException):
            if error.status == 403 and "rate limit exceeded" in str(error).lower():
                self.logger.warning(f"Rate limit exceeded for operation {operation}")
                return True  # Retry
            elif error.status == 404:
                self.logger.error(f"Resource not found for operation {operation}")
                return False  # Don't retry
            elif error.status >= 500:
                self.logger.warning(f"Server error for operation {operation}: {error}")
                return True  # Retry
            else:
                self.logger.error(
                    f"GitHub API error for operation {operation}: {error}"
                )
                return False  # Don't retry
        else:
            self.logger.error(f"Unexpected error for operation {operation}: {error}")
            return False  # Don't retry
