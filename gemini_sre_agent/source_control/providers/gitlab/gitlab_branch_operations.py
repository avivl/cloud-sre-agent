# gemini_sre_agent/source_control/providers/gitlab/gitlab_branch_operations.py

"""
GitLab branch operations module.

This module handles branch-specific operations for the GitLab provider.
"""

import asyncio
import base64
import logging
from typing import Any, List, Optional

import gitlab
from gitlab.exceptions import GitlabGetError

from ...models import (
    BranchInfo,
    ConflictInfo,
    RepositoryInfo,
)


class GitLabBranchOperations:
    """Handles branch-specific operations for GitLab."""

    def __init__(self, gl: gitlab.Gitlab, project: Any, logger: logging.Logger):
        """Initialize branch operations with GitLab client and project."""
        self.gl = gl
        self.project = project
        self.logger = logger

    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create a new branch."""
        try:

            def _create():
                try:
                    ref = base_ref or "main"
                    self.project.branches.create(
                        {
                            "branch": name,
                            "ref": ref,
                        }
                    )
                    return True
                except GitlabGetError as e:
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
                    branch = self.project.branches.get(name)
                    branch.delete()
                    return True
                except GitlabGetError as e:
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
                    for branch in self.project.branches.list():
                        branches.append(
                            BranchInfo(
                                name=branch.name,
                                sha=branch.commit["id"],
                                is_protected=branch.protected,
                            )
                        )
                except GitlabGetError as e:
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
                    branch = self.project.branches.get(name)
                    return BranchInfo(
                        name=branch.name,
                        sha=branch.commit["id"],
                        is_protected=branch.protected,
                    )
                except GitlabGetError as e:
                    if e.response_code == 404:
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
                    return self.project.default_branch
                except Exception as e:
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
                        name=self.project.name,
                        url=self.project.web_url,
                        default_branch=self.project.default_branch,
                        is_private=self.project.visibility == "private",
                        owner=self.project.owner["username"],
                        description=self.project.description or "",
                        additional_info={
                            "created_at": self.project.created_at,
                            "last_activity_at": self.project.last_activity_at,
                            "star_count": self.project.star_count,
                            "forks_count": self.project.forks_count,
                        },
                    )
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
                    base_content = self.project.files.get(
                        file_path=file_path, ref=base_branch
                    )
                    feature_content = self.project.files.get(
                        file_path=file_path, ref=feature_branch
                    )

                    base_text = base64.b64decode(base_content.content).decode("utf-8")
                    feature_text = base64.b64decode(feature_content.content).decode(
                        "utf-8"
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
                except GitlabGetError as e:
                    if e.response_code == 404:
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
                    file_data = self.project.files.get(file_path=file_path, ref="main")

                    # Update file with resolution
                    file_data.content = base64.b64encode(
                        resolution.encode("utf-8")
                    ).decode("utf-8")
                    file_data.save(branch="main", commit_message=commit_message)

                    return True
                except GitlabGetError as e:
                    self.logger.error(f"Failed to resolve conflicts: {e}")
                    return False

            return await asyncio.get_event_loop().run_in_executor(None, _resolve)
        except Exception as e:
            self.logger.error(f"Failed to resolve conflicts: {e}")
            return False
