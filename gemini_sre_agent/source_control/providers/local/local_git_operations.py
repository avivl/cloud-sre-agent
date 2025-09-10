# gemini_sre_agent/source_control/providers/local/local_git_operations.py

"""
Local Git operations module.

This module handles Git-specific operations for the local provider.
"""

import logging
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from git import GitCommandError, InvalidGitRepositoryError, Repo

from ...models import (
    BranchInfo,
    CommitInfo,
    ConflictInfo,
    RepositoryInfo,
)


class LocalGitOperations:
    """Handles Git-specific operations for local filesystem."""

    def __init__(
        self,
        root_path: Path,
        git_enabled: bool,
        auto_init_git: bool,
        logger: logging.Logger,
        error_handling_components: Optional[Dict[str, Any]] = None,
    ):
        """Initialize Git operations."""
        self.root_path = root_path
        self.git_enabled = git_enabled
        self.auto_init_git = auto_init_git
        self.logger = logger
        self.error_handling_components = error_handling_components
        self.repo: Optional[Repo] = None
        self._initialize_git()

    async def _execute_with_error_handling(
        self, operation_name: str, func, *args, **kwargs
    ):
        """Execute a function with error handling if available."""
        if (
            self.error_handling_components
            and "resilient_manager" in self.error_handling_components
        ):
            resilient_manager = self.error_handling_components["resilient_manager"]
            return await resilient_manager.execute_with_retry(
                operation_name, func, *args, **kwargs
            )

        # Fall back to direct execution
        return await func(*args, **kwargs)

    def _initialize_git(self) -> None:
        """Initialize Git repository if enabled."""
        if not self.git_enabled:
            return

        try:
            self.repo = Repo(self.root_path)
            self.logger.info(f"Git repository found at {self.root_path}")
        except InvalidGitRepositoryError:
            if self.auto_init_git:
                try:
                    self.repo = Repo.init(self.root_path)
                    self.logger.info(f"Initialized Git repository at {self.root_path}")
                except Exception as e:
                    self.logger.error(f"Failed to initialize Git repository: {e}")
                    self.repo = None
            else:
                self.logger.warning(f"No Git repository found at {self.root_path}")
                self.repo = None

    def _validate_git_command(self, command: List[str]) -> bool:
        """Validate Git command for security."""
        if not command:
            return False

        # Only allow specific Git commands for security
        allowed_commands = {
            "add", "branch", "checkout", "commit", "diff", "fetch", "log", "merge",
            "pull", "push", "reset", "show", "status", "tag", "config", "remote",
            "rev-parse", "ls-files", "ls-tree", "cat-file", "show-ref", "for-each-ref"
        }

        # First argument should be a valid Git command
        if command[0] not in allowed_commands:
            self.logger.warning(f"Disallowed Git command: {command[0]}")
            return False

        # Check for potentially dangerous arguments
        dangerous_args = {"--", "|", "&", ";", "`", "$", "(", ")", "<", ">", "~"}
        for arg in command[1:]:
            if any(dangerous in arg for dangerous in dangerous_args):
                self.logger.warning(f"Potentially dangerous argument in Git command: {arg}")
                return False

        return True

    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create a new branch."""
        if not self.repo:
            return False

        async def _create():
            try:
                ref_to_use = base_ref or "main"
                if self.repo:
                    self.repo.git.checkout("-b", name, ref_to_use)
                    return True
                return False
            except GitCommandError as e:
                self.logger.error(f"Failed to create branch {name}: {e}")
                return False

        return await self._execute_with_error_handling("create_branch", _create)

    async def delete_branch(self, name: str) -> bool:
        """Delete a branch."""
        if not self.repo:
            return False

        async def _delete():
            try:
                if self.repo:
                    self.repo.git.branch("-d", name)
                    return True
                return False
            except GitCommandError as e:
                self.logger.error(f"Failed to delete branch {name}: {e}")
                return False

        return await self._execute_with_error_handling("delete_branch", _delete)

    async def list_branches(self) -> List[BranchInfo]:
        """List all branches."""
        if not self.repo:
            return []

        async def _list():
            try:
                branches = []
                if self.repo:
                    for branch in self.repo.branches:
                        branches.append(
                            BranchInfo(
                                name=branch.name,
                                sha=branch.commit.hexsha,
                                is_protected=False,  # Local branches are not protected
                            )
                        )
                return branches
            except Exception as e:
                self.logger.error(f"Failed to list branches: {e}")
                return []

        return await self._execute_with_error_handling("list_branches", _list)

    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get information about a specific branch."""
        if not self.repo:
            return None

        async def _get_info():
            try:
                if self.repo:
                    branch = self.repo.branches[name]
                    return BranchInfo(
                        name=branch.name,
                        sha=branch.commit.hexsha,
                        is_protected=False,
                    )
                return None
            except (KeyError, GitCommandError) as e:
                self.logger.error(f"Failed to get branch info for {name}: {e}")
                return None

        return await self._execute_with_error_handling("get_branch_info", _get_info)

    async def get_current_branch(self) -> str:
        """Get the current branch name."""
        if not self.repo:
            return "main"

        async def _get_current():
            try:
                if self.repo:
                    return self.repo.active_branch.name
                return "main"
            except Exception as e:
                self.logger.error(f"Failed to get current branch: {e}")
                return "main"

        return await self._execute_with_error_handling(
            "get_current_branch", _get_current
        )

    async def get_repository_info(self) -> RepositoryInfo:
        """Get repository information."""
        if not self.repo:
            return RepositoryInfo(
                name=self.root_path.name,
                url=str(self.root_path),
                default_branch="main",
                is_private=True,
                owner="local",
                description="Local repository",
                additional_info={},
            )

        async def _get_info():
            try:
                if self.repo:
                    return RepositoryInfo(
                        name=self.root_path.name,
                        url=str(self.root_path),
                        default_branch=self.repo.active_branch.name,
                        is_private=True,
                        owner="local",
                        description="Local repository",
                        additional_info={
                            "remote_urls": [remote.url for remote in self.repo.remotes],
                            "last_commit": self.repo.head.commit.hexsha,
                        },
                    )
                else:
                    return RepositoryInfo(
                        name=self.root_path.name,
                        url=str(self.root_path),
                        default_branch="main",
                        is_private=True,
                        owner="local",
                        description="Local repository",
                        additional_info={},
                    )
            except Exception as e:
                self.logger.error(f"Failed to get repository info: {e}")
                return RepositoryInfo(
                    name=self.root_path.name,
                    url=str(self.root_path),
                    default_branch="main",
                    is_private=True,
                    owner="local",
                    description="Local repository",
                    additional_info={},
                )

        return await self._execute_with_error_handling("get_repository_info", _get_info)

    async def check_conflicts(
        self,
        file_path: str,
        base_branch: str,
        feature_branch: str,
    ) -> ConflictInfo:
        """Check for conflicts between branches."""
        if not self.repo:
            return ConflictInfo(
                path=file_path,
                conflict_type="no_repo",
                has_conflicts=False,
                conflict_files=[],
                conflict_details={},
            )

        async def _check():
            try:
                if not self.repo:
                    return ConflictInfo(
                        path=file_path,
                        conflict_type="no_repo",
                        has_conflicts=False,
                        conflict_files=[],
                        conflict_details={},
                    )

                # Switch to feature branch
                current_branch = await self.get_current_branch()
                self.repo.git.checkout(feature_branch)

                # Try to merge base branch
                try:
                    self.repo.git.merge(base_branch, "--no-commit", "--no-ff")
                    has_conflicts = False
                    conflict_files = []
                    conflict_details = ""
                except GitCommandError as e:
                    if "conflict" in str(e).lower():
                        has_conflicts = True
                        conflict_files = [file_path]
                        conflict_details = str(e)
                    else:
                        has_conflicts = False
                        conflict_files = []
                        conflict_details = ""

                # Switch back to original branch
                self.repo.git.checkout(current_branch)

                return ConflictInfo(
                    path=file_path,
                    conflict_type="merge",
                    has_conflicts=has_conflicts,
                    conflict_files=conflict_files,
                    conflict_details=(
                        {"message": conflict_details} if conflict_details else {}
                    ),
                )
            except Exception as e:
                self.logger.error(f"Failed to check conflicts: {e}")
                return ConflictInfo(
                    path=file_path,
                    conflict_type="error",
                    has_conflicts=False,
                    conflict_files=[],
                    conflict_details={"error": str(e)},
                )

        return await self._execute_with_error_handling("check_conflicts", _check)

    async def resolve_conflicts(
        self,
        file_path: str,
        resolution: str,
        commit_message: str,
    ) -> bool:
        """Resolve conflicts in a file."""
        if not self.repo:
            return False

        async def _resolve():
            try:
                if not self.repo:
                    return False

                # Add resolved file
                self.repo.git.add(file_path)

                # Commit the resolution
                self.repo.git.commit("-m", commit_message)

                return True
            except GitCommandError as e:
                self.logger.error(f"Failed to resolve conflicts: {e}")
                return False

        return await self._execute_with_error_handling("resolve_conflicts", _resolve)

    async def get_file_history(self, path: str, limit: int = 10) -> List[CommitInfo]:
        """Get file commit history."""
        if not self.repo:
            return []

        async def _get_history():
            try:
                if not self.repo:
                    return []

                commits = []
                for commit in self.repo.iter_commits(paths=path, max_count=limit):
                    commits.append(
                        CommitInfo(
                            sha=commit.hexsha,
                            message=(
                                commit.message.decode("utf-8")
                                if isinstance(commit.message, bytes)
                                else commit.message
                            ),
                            author=commit.author.name or "Unknown",
                            author_email=commit.author.email or "unknown@example.com",
                            committer=commit.committer.name or "Unknown",
                            committer_email=commit.committer.email
                            or "unknown@example.com",
                            date=commit.committed_datetime,
                        )
                    )
                return commits
            except Exception as e:
                self.logger.error(f"Failed to get file history for {path}: {e}")
                return []

        return await self._execute_with_error_handling("get_file_history", _get_history)

    async def diff_between_commits(self, base_sha: str, head_sha: str) -> str:
        """Get diff between two commits."""
        if not self.repo:
            return ""

        async def _get_diff():
            try:
                if not self.repo:
                    return ""
                return self.repo.git.diff(base_sha, head_sha)
            except GitCommandError as e:
                self.logger.error(f"Failed to get diff between commits: {e}")
                return ""

        return await self._execute_with_error_handling(
            "diff_between_commits", _get_diff
        )

    async def execute_git_command(self, command: List[str]) -> str:
        """Execute a Git command and return output."""
        if not self.repo:
            return ""

        # Validate command for security
        if not self._validate_git_command(command):
            self.logger.error(f"Invalid or unsafe Git command: {command}")
            return ""

        async def _execute():
            try:
                # Use shell=False and proper argument list for security
                # Escape arguments to prevent command injection
                safe_command = ["git"] + [shlex.quote(arg) for arg in command]
                result = subprocess.run(
                    safe_command,
                    cwd=str(self.root_path),  # Convert Path to string
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30,  # Add timeout for security
                )
                return result.stdout
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Git command failed: {e}")
                return ""
            except subprocess.TimeoutExpired as e:
                self.logger.error(f"Git command timed out: {e}")
                return ""
            except Exception as e:
                self.logger.error(f"Failed to execute Git command: {e}")
                return ""

        return await self._execute_with_error_handling("execute_git_command", _execute)
