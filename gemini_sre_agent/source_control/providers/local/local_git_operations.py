# gemini_sre_agent/source_control/providers/local/local_git_operations.py

"""
Local Git operations module.

This module handles Git-specific operations for the local provider.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Optional

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
    ):
        """Initialize Git operations."""
        self.root_path = root_path
        self.git_enabled = git_enabled
        self.auto_init_git = auto_init_git
        self.logger = logger
        self.repo: Optional[Repo] = None
        self._initialize_git()

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

    def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create a new branch."""
        if not self.repo:
            return False

        try:
            base_ref = base_ref or "main"
            self.repo.git.checkout("-b", name, base_ref)
            return True
        except GitCommandError as e:
            self.logger.error(f"Failed to create branch {name}: {e}")
            return False

    def delete_branch(self, name: str) -> bool:
        """Delete a branch."""
        if not self.repo:
            return False

        try:
            self.repo.git.branch("-d", name)
            return True
        except GitCommandError as e:
            self.logger.error(f"Failed to delete branch {name}: {e}")
            return False

    def list_branches(self) -> List[BranchInfo]:
        """List all branches."""
        if not self.repo:
            return []

        try:
            branches = []
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

    def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get information about a specific branch."""
        if not self.repo:
            return None

        try:
            branch = self.repo.branches[name]
            return BranchInfo(
                name=branch.name,
                sha=branch.commit.hexsha,
                is_protected=False,
            )
        except (KeyError, GitCommandError) as e:
            self.logger.error(f"Failed to get branch info for {name}: {e}")
            return None

    def get_current_branch(self) -> str:
        """Get the current branch name."""
        if not self.repo:
            return "main"

        try:
            return self.repo.active_branch.name
        except Exception as e:
            self.logger.error(f"Failed to get current branch: {e}")
            return "main"

    def get_repository_info(self) -> RepositoryInfo:
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

        try:
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

    def check_conflicts(
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

        try:
            # Switch to feature branch
            current_branch = self.get_current_branch()
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

    def resolve_conflicts(
        self,
        file_path: str,
        resolution: str,
        commit_message: str,
    ) -> bool:
        """Resolve conflicts in a file."""
        if not self.repo:
            return False

        try:
            # Add resolved file
            self.repo.git.add(file_path)

            # Commit the resolution
            self.repo.git.commit("-m", commit_message)

            return True
        except GitCommandError as e:
            self.logger.error(f"Failed to resolve conflicts: {e}")
            return False

    def get_file_history(self, path: str, limit: int = 10) -> List[CommitInfo]:
        """Get file commit history."""
        if not self.repo:
            return []

        try:
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
                        committer_email=commit.committer.email or "unknown@example.com",
                        date=commit.committed_datetime,
                    )
                )
            return commits
        except Exception as e:
            self.logger.error(f"Failed to get file history for {path}: {e}")
            return []

    def diff_between_commits(self, base_sha: str, head_sha: str) -> str:
        """Get diff between two commits."""
        if not self.repo:
            return ""

        try:
            return self.repo.git.diff(base_sha, head_sha)
        except GitCommandError as e:
            self.logger.error(f"Failed to get diff between commits: {e}")
            return ""

    def execute_git_command(self, command: List[str]) -> str:
        """Execute a Git command and return output."""
        if not self.repo:
            return ""

        try:
            result = subprocess.run(
                ["git"] + command,
                cwd=self.root_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git command failed: {e}")
            return ""
        except Exception as e:
            self.logger.error(f"Failed to execute Git command: {e}")
            return ""
