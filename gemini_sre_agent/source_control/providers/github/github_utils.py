# gemini_sre_agent/source_control/providers/github_utils.py

"""
GitHub provider utilities module.

This module contains utility functions and helper methods for the GitHub provider.
"""

import asyncio
import logging
from typing import Any, Dict

from github import Github, GithubException
from github.Repository import Repository

from ...models import ProviderHealth


class GitHubUtils:
    """Utility functions for GitHub operations."""

    def __init__(self, client: Github, repo: Repository, logger: logging.Logger):
        """Initialize utilities with GitHub client and repository."""
        self.client = client
        self.repo = repo
        self.logger = logger

    async def get_health_status(self) -> ProviderHealth:
        """Get health status of the GitHub provider."""
        try:
            # Test basic connectivity
            try:
                # Get rate limit info
                rate_limit = self.client.get_rate_limit()
                rate_limit_core = getattr(rate_limit, "core", None)
                remaining = (
                    getattr(rate_limit_core, "remaining", None)
                    if rate_limit_core
                    else None
                )
                limit = (
                    getattr(rate_limit_core, "limit", None) if rate_limit_core else None
                )

                # Get repository info
                repo_name = self.repo.name
                repo_private = self.repo.private

                return ProviderHealth(
                    status="healthy",
                    message="GitHub provider is operational",
                    additional_info={
                        "repository": repo_name,
                        "private": repo_private,
                        "rate_limit": (
                            {
                                "remaining": remaining,
                                "limit": limit,
                                "reset_time": (
                                    getattr(rate_limit_core, "reset", None)
                                    if rate_limit_core
                                    else None
                                ),
                            }
                            if remaining is not None and limit is not None
                            else None
                        ),
                    },
                )
            except GithubException as e:
                if e.status == 401:
                    return ProviderHealth(
                        status="unhealthy",
                        message="Authentication failed",
                        additional_info={"error": str(e), "status_code": e.status},
                    )
                elif e.status == 403:
                    return ProviderHealth(
                        status="unhealthy",
                        message="Access forbidden - check permissions",
                        additional_info={"error": str(e), "status_code": e.status},
                    )
                elif e.status == 404:
                    return ProviderHealth(
                        status="unhealthy",
                        message="Repository not found",
                        additional_info={"error": str(e), "status_code": e.status},
                    )
                else:
                    return ProviderHealth(
                        status="degraded",
                        message=f"GitHub API error: {e}",
                        additional_info={
                            "error": str(e),
                            "status_code": getattr(e, "status", None),
                        },
                    )
        except Exception as e:
            return ProviderHealth(
                status="unhealthy",
                message=f"Unexpected error: {e}",
                additional_info={"error": str(e)},
            )

    async def get_status(self) -> Dict[str, Any]:
        """Get current status of the GitHub provider."""
        try:
            status = {
                "provider": "github",
                "repository": self.repo.name,
                "private": self.repo.private,
                "default_branch": self.repo.default_branch,
            }

            # Get rate limit info
            try:
                rate_limit = self.client.get_rate_limit()
                rate_limit_core = getattr(rate_limit, "core", None)
                if rate_limit_core:
                    status["rate_limit"] = {
                        "remaining": getattr(rate_limit_core, "remaining", None),
                        "limit": getattr(rate_limit_core, "limit", None),
                        "reset_time": getattr(rate_limit_core, "reset", None),
                    }
            except Exception as e:
                self.logger.warning(f"Failed to get rate limit info: {e}")
                status["rate_limit"] = None

            # Get repository stats
            try:
                status["stats"] = {
                    "stars": self.repo.stargazers_count,
                    "forks": self.repo.forks_count,
                    "watchers": self.repo.subscribers_count,
                    "open_issues": self.repo.open_issues_count,
                }
            except Exception as e:
                self.logger.warning(f"Failed to get repository stats: {e}")
                status["stats"] = None

            return status
        except Exception as e:
            self.logger.error(f"Failed to get status: {e}")
            return {
                "provider": "github",
                "error": str(e),
                "status": "error",
            }

    async def execute_git_command(self, command: str, **kwargs) -> Dict[str, Any]:
        """Execute a git command (placeholder for GitHub API operations)."""
        try:
            # GitHub provider doesn't execute git commands directly
            # This is a placeholder for compatibility
            return {
                "success": False,
                "message": "Git commands not supported in GitHub provider",
                "output": "",
                "error": "Use GitHub API methods instead",
            }
        except Exception as e:
            self.logger.error(f"Failed to execute git command: {e}")
            return {
                "success": False,
                "message": f"Command failed: {e}",
                "output": "",
                "error": str(e),
            }

    async def refresh_credentials(self) -> bool:
        """Refresh GitHub credentials."""
        try:
            # For GitHub, credentials are typically tokens that don't need refreshing
            # This is a placeholder for compatibility
            return True
        except Exception as e:
            self.logger.error(f"Failed to refresh credentials: {e}")
            return False

    async def validate_credentials(self) -> bool:
        """Validate GitHub credentials."""
        try:
            # Test credentials by making a simple API call
            self.client.get_user()
            return True
        except Exception as e:
            self.logger.error(f"Failed to validate credentials: {e}")
            return False

    async def handle_operation_failure(self, operation: str, error: Exception) -> bool:
        """Handle operation failures with appropriate retry logic."""
        try:
            if isinstance(error, GithubException):
                if error.status == 401:
                    self.logger.error(f"Authentication failed for {operation}: {error}")
                    return False  # Don't retry auth failures
                elif error.status == 403:
                    self.logger.error(f"Access forbidden for {operation}: {error}")
                    return False  # Don't retry permission failures
                elif error.status == 404:
                    self.logger.error(f"Resource not found for {operation}: {error}")
                    return False  # Don't retry not found
                elif error.status == 422:
                    self.logger.error(f"Validation error for {operation}: {error}")
                    return False  # Don't retry validation errors
                elif error.status == 429:
                    self.logger.warning(f"Rate limited for {operation}: {error}")
                    return True  # Retry rate limit errors
                else:
                    self.logger.error(f"GitHub API error for {operation}: {error}")
                    return True  # Retry other API errors
            else:
                self.logger.error(f"Unexpected error for {operation}: {error}")
                return True  # Retry unexpected errors
        except Exception as e:
            self.logger.error(f"Failed to handle operation failure: {e}")
            return False

    async def _with_retry(self, operation_func, *args, **kwargs):
        """Execute an operation with retry logic."""
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                return await operation_func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise

                should_retry = await self.handle_operation_failure(
                    operation_func.__name__, e
                )
                if not should_retry:
                    raise

                self.logger.warning(
                    f"Retrying {operation_func.__name__} (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(retry_delay * (2**attempt))

    async def test_connection(self) -> bool:
        """Test connection to GitHub."""
        try:
            # Test basic connectivity
            self.client.get_user()
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
