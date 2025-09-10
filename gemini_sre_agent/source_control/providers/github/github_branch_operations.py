# gemini_sre_agent/source_control/providers/github/github_branch_operations.py

"""
GitHub branch operations module.

This module handles branch-specific operations for the GitHub provider.
"""

import asyncio
import logging
from typing import List, Optional

from github import Github, GithubException
from github.Repository import Repository

from ...models import (
    BranchInfo,
    ConflictInfo,
    RepositoryInfo,
)


class GitHubBranchOperations:
    """Handles branch-specific operations for GitHub."""

    def __init__(self, client: Github, repo: Repository, logger: logging.Logger):
        """Initialize branch operations with GitHub client and repository."""
        self.client = client
        self.repo = repo
        self.logger = logger

    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create a new branch."""
        try:

            def _create():
                try:
                    ref_to_use = base_ref or self.repo.default_branch
                    base_ref_obj = self.repo.get_git_ref(f"heads/{ref_to_use}")
                    self.repo.create_git_ref(
                        f"refs/heads/{name}", base_ref_obj.object.sha
                    )
                    return True
                except GithubException as e:
                    self.logger.error(f"Failed to create branch {name}: {e}")
                    return False

            return await asyncio.get_event_loop().run_in_executor(None, _create)
        except Exception as e:
            self.logger.error(f"Failed to create branch {name}: {e}")
            return False

    async def delete_branch(self, name: str) -> bool:
        """Delete a branch."""
        try:

            def _delete():
                try:
                    ref = self.repo.get_git_ref(f"heads/{name}")
                    ref.delete()
                    return True
                except GithubException as e:
                    self.logger.error(f"Failed to delete branch {name}: {e}")
                    return False

            return await asyncio.get_event_loop().run_in_executor(None, _delete)
        except Exception as e:
            self.logger.error(f"Failed to delete branch {name}: {e}")
            return False

    async def list_branches(self) -> List[BranchInfo]:
        """List all branches."""
        try:

            def _list():
                branches = []
                try:
                    for branch in self.repo.get_branches():
                        branches.append(
                            BranchInfo(
                                name=branch.name,
                                sha=branch.commit.sha,  # type: ignore
                                is_protected=branch.protected,  # type: ignore
                            )
                        )
                except GithubException as e:
                    self.logger.error(f"Failed to list branches: {e}")

                return branches

            return await asyncio.get_event_loop().run_in_executor(None, _list)
        except Exception as e:
            self.logger.error(f"Failed to list branches: {e}")
            return []

    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get information about a specific branch."""
        try:

            def _get():
                try:
                    branch = self.repo.get_branch(name)
                    return BranchInfo(
                        name=branch.name,
                        sha=branch.commit.sha,  # type: ignore
                        is_protected=branch.protected,  # type: ignore
                    )
                except GithubException as e:
                    if e.status == 404:
                        return None
                    self.logger.error(f"Failed to get branch info for {name}: {e}")
                    return None

            return await asyncio.get_event_loop().run_in_executor(None, _get)
        except Exception as e:
            self.logger.error(f"Failed to get branch info for {name}: {e}")
            return None

    async def get_current_branch(self) -> str:
        """Get the current branch name."""
        try:

            def _get():
                try:
                    return self.repo.default_branch
                except GithubException as e:
                    self.logger.error(f"Failed to get current branch: {e}")
                    return "main"

            return await asyncio.get_event_loop().run_in_executor(None, _get)
        except Exception as e:
            self.logger.error(f"Failed to get current branch: {e}")
            return "main"

    async def get_repository_info(self) -> RepositoryInfo:
        """Get repository information."""
        try:

            def _get():
                try:
                    return RepositoryInfo(
                        name=self.repo.name,
                        url=self.repo.html_url,
                        default_branch=self.repo.default_branch,
                        is_private=self.repo.private,
                        owner=self.repo.owner.login,  # type: ignore
                        description=self.repo.description or "",
                        additional_info={
                            "created_at": (
                                self.repo.created_at.isoformat()
                                if self.repo.created_at
                                else None
                            ),
                            "updated_at": (
                                self.repo.updated_at.isoformat()
                                if self.repo.updated_at
                                else None
                            ),
                        },
                    )
                except GithubException as e:
                    self.logger.error(f"Failed to get repository info: {e}")
                    return RepositoryInfo(
                        name="",
                        url="",
                        default_branch="main",
                        is_private=False,
                        owner="",
                        description="",
                        additional_info={},
                    )

            return await asyncio.get_event_loop().run_in_executor(None, _get)
        except Exception as e:
            self.logger.error(f"Failed to get repository info: {e}")
            return RepositoryInfo(
                name="",
                url="",
                default_branch="main",
                is_private=False,
                owner="",
                description="",
                additional_info={},
            )

    async def check_conflicts(
        self,
        file_path: str,
        base_branch: str,
        feature_branch: str,
    ) -> ConflictInfo:
        """Check for conflicts between branches."""
        try:

            def _check():
                try:
                    # Get file content from both branches
                    base_content = self.repo.get_contents(file_path, ref=base_branch)
                    feature_content = self.repo.get_contents(
                        file_path, ref=feature_branch
                    )

                    if isinstance(base_content, list) or isinstance(
                        feature_content, list
                    ):
                        return ConflictInfo(
                            path=file_path,
                            conflict_type="directory",
                            has_conflicts=False,
                            conflict_files=[],
                            conflict_details={},
                        )

                    base_text = (
                        base_content.content if hasattr(base_content, "content") else ""
                    )
                    feature_text = (
                        feature_content.content
                        if hasattr(feature_content, "content")
                        else ""
                    )

                    has_conflicts = base_text != feature_text

                    return ConflictInfo(
                        path=file_path,
                        conflict_type="content",
                        has_conflicts=has_conflicts,
                        conflict_files=[file_path] if has_conflicts else [],
                        conflict_details=(
                            {
                                "message": f"Content differs between {base_branch} and {feature_branch}"
                            }
                            if has_conflicts
                            else {}
                        ),
                    )
                except GithubException as e:
                    if e.status == 404:
                        return ConflictInfo(
                            path=file_path,
                            conflict_type="not_found",
                            has_conflicts=False,
                            conflict_files=[],
                            conflict_details={},
                        )
                    self.logger.error(f"Failed to check conflicts: {e}")
                    return ConflictInfo(
                        path=file_path,
                        conflict_type="error",
                        has_conflicts=False,
                        conflict_files=[],
                        conflict_details={"error": str(e)},
                    )

            return await asyncio.get_event_loop().run_in_executor(None, _check)
        except Exception as e:
            self.logger.error(f"Failed to check conflicts: {e}")
            return ConflictInfo(
                path=file_path,
                conflict_type="error",
                has_conflicts=False,
                conflict_files=[],
                conflict_details={"error": str(e)},
            )

    async def resolve_conflicts(
        self,
        file_path: str,
        resolution: str,
        commit_message: str,
    ) -> bool:
        """Resolve conflicts in a file."""
        try:

            def _resolve():
                try:
                    # Get current file content
                    contents = self.repo.get_contents(file_path)
                    if isinstance(contents, list):
                        return False

                    # Update file with resolution
                    self.repo.update_file(
                        path=file_path,
                        message=commit_message,
                        content=resolution,
                        sha=contents.sha,  # type: ignore
                    )
                    return True
                except GithubException as e:
                    self.logger.error(f"Failed to resolve conflicts: {e}")
                    return False

            return await asyncio.get_event_loop().run_in_executor(None, _resolve)
        except Exception as e:
            self.logger.error(f"Failed to resolve conflicts: {e}")
            return False
