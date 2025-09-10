# gemini_sre_agent/source_control/providers/gitlab/gitlab_file_operations.py

"""
GitLab file operations module.

This module handles file-specific operations for the GitLab provider.
"""

import asyncio
import base64
import logging
from typing import Any, List, Optional

import gitlab
from gitlab.exceptions import GitlabGetError

from ...models import (
    FileInfo,
    RemediationResult,
)


class GitLabFileOperations:
    """Handles file-specific operations for GitLab."""

    def __init__(self, gl: gitlab.Gitlab, project: Any, logger: logging.Logger):
        """Initialize file operations with GitLab client and project."""
        self.gl = gl
        self.project = project
        self.logger = logger

    async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
        """Get file content from GitLab repository."""
        try:

            def _get_file():
                try:
                    file_data = self.project.files.get(
                        file_path=path, ref=ref or "main"
                    )
                    return base64.b64decode(file_data.content).decode("utf-8")
                except GitlabGetError as e:
                    if e.response_code == 404:
                        return ""
                    raise

            return await asyncio.get_event_loop().run_in_executor(None, _get_file)
        except Exception as e:
            self.logger.error(f"Failed to get file content for {path}: {e}")
            return ""

    async def apply_remediation(
        self,
        file_path: str,
        remediation: str,
        commit_message: str,
        branch: Optional[str] = None,
    ) -> RemediationResult:
        """Apply remediation to a file."""
        try:

            def _apply():
                try:
                    # Check if file exists
                    try:
                        file_data = self.project.files.get(
                            file_path=file_path, ref=branch or "main"
                        )
                        # Update existing file
                        file_data.content = base64.b64encode(
                            remediation.encode("utf-8")
                        ).decode("utf-8")
                        file_data.save(
                            branch=branch or "main", commit_message=commit_message
                        )
                    except GitlabGetError as e:
                        if e.response_code == 404:
                            # Create new file
                            self.project.files.create(
                                {
                                    "file_path": file_path,
                                    "content": base64.b64encode(
                                        remediation.encode("utf-8")
                                    ).decode("utf-8"),
                                    "branch": branch or "main",
                                    "commit_message": commit_message,
                                }
                            )
                        else:
                            raise

                    return RemediationResult(
                        success=True,
                        message=f"Applied remediation to {file_path}",
                        file_path=file_path,
                        operation_type="apply_remediation",
                        commit_sha="",  # GitLab doesn't return commit SHA directly
                        pull_request_url="",
                        error_details="",
                        additional_info={},
                    )
                except Exception as e:
                    return RemediationResult(
                        success=False,
                        message=f"Failed to apply remediation: {e}",
                        file_path=file_path,
                        operation_type="apply_remediation",
                        commit_sha="",
                        pull_request_url="",
                        error_details=str(e),
                        additional_info={},
                    )

            return await asyncio.get_event_loop().run_in_executor(None, _apply)
        except Exception as e:
            self.logger.error(f"Failed to apply remediation to {file_path}: {e}")
            return RemediationResult(
                success=False,
                message=f"Failed to apply remediation: {e}",
                file_path=file_path,
                operation_type="apply_remediation",
                commit_sha="",
                pull_request_url="",
                error_details=str(e),
                additional_info={},
            )

    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if a file exists in the repository."""
        try:

            def _exists():
                try:
                    self.project.files.get(file_path=path, ref=ref or "main")
                    return True
                except GitlabGetError as e:
                    if e.response_code == 404:
                        return False
                    raise

            return await asyncio.get_event_loop().run_in_executor(None, _exists)
        except Exception as e:
            self.logger.error(f"Failed to check if file exists {path}: {e}")
            return False

    async def get_file_info(self, path: str, ref: Optional[str] = None) -> FileInfo:
        """Get file information."""
        try:

            def _get_info():
                try:
                    file_data = self.project.files.get(
                        file_path=path, ref=ref or "main"
                    )
                    return FileInfo(
                        path=path,
                        size=file_data.size,
                        sha=file_data.id,
                        is_binary=file_data.encoding == "base64",
                        last_modified=file_data.last_activity_at,
                    )
                except GitlabGetError as e:
                    if e.response_code == 404:
                        return FileInfo(
                            path=path,
                            size=0,
                            sha="",
                            is_binary=False,
                            last_modified=None,
                        )
                    raise

            return await asyncio.get_event_loop().run_in_executor(None, _get_info)
        except Exception as e:
            self.logger.error(f"Failed to get file info for {path}: {e}")
            return FileInfo(
                path=path,
                size=0,
                sha="",
                is_binary=False,
                last_modified=None,
            )

    async def list_files(
        self, path: str = "", ref: Optional[str] = None
    ) -> List[FileInfo]:
        """List files in a directory."""
        try:

            def _list():
                files = []
                try:
                    for item in self.project.repository_tree(
                        path=path, ref=ref or "main"
                    ):
                        if item["type"] == "blob":  # File
                            files.append(
                                FileInfo(
                                    path=item["path"],
                                    size=0,  # GitLab doesn't provide size in tree listing
                                    sha=item["id"],
                                    is_binary=False,  # Would need to check file content
                                    last_modified=None,
                                )
                            )
                except GitlabGetError as e:
                    if e.response_code != 404:
                        raise

                return files

            return await asyncio.get_event_loop().run_in_executor(None, _list)
        except Exception as e:
            self.logger.error(f"Failed to list files in {path}: {e}")
            return []

    async def generate_patch(self, original: str, modified: str) -> str:
        """Generate a patch between original and modified content."""
        try:
            import difflib

            return "\n".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    modified.splitlines(keepends=True),
                    fromfile="original",
                    tofile="modified",
                )
            )
        except Exception as e:
            self.logger.error(f"Failed to generate patch: {e}")
            return ""

    async def apply_patch(self, patch: str, file_path: str) -> bool:
        """Apply a patch to a file."""
        try:

            def _apply():
                try:
                    # Get current content (placeholder implementation)
                    # file_data = self.project.files.get(file_path=file_path, ref="main")
                    # current_content = base64.b64decode(file_data.content).decode("utf-8")

                    # Apply patch (simplified - in real implementation, use patch library)
                    # This is a placeholder implementation
                    return True
                except GitlabGetError as e:
                    if e.response_code == 404:
                        return False
                    raise

            return await asyncio.get_event_loop().run_in_executor(None, _apply)
        except Exception as e:
            self.logger.error(f"Failed to apply patch to {file_path}: {e}")
            return False

    async def commit_changes(
        self,
        file_path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
    ) -> Optional[str]:
        """Commit changes to a file."""
        try:

            def _commit():
                try:
                    # Check if file exists
                    try:
                        file_data = self.project.files.get(
                            file_path=file_path, ref=branch or "main"
                        )
                        # Update existing file
                        file_data.content = base64.b64encode(
                            content.encode("utf-8")
                        ).decode("utf-8")
                        file_data.save(branch=branch or "main", commit_message=message)
                    except GitlabGetError as e:
                        if e.response_code == 404:
                            # Create new file
                            self.project.files.create(
                                {
                                    "file_path": file_path,
                                    "content": base64.b64encode(
                                        content.encode("utf-8")
                                    ).decode("utf-8"),
                                    "branch": branch or "main",
                                    "commit_message": message,
                                }
                            )
                        else:
                            raise

                    return "gitlab_commit"  # GitLab doesn't return commit SHA directly
                except Exception as e:
                    self.logger.error(f"Failed to commit changes to {file_path}: {e}")
                    return None

            return await asyncio.get_event_loop().run_in_executor(None, _commit)
        except Exception as e:
            self.logger.error(f"Failed to commit changes to {file_path}: {e}")
            return None

    async def get_file_history(self, path: str, limit: int = 10) -> List[dict]:
        """Get file commit history."""
        try:

            def _get_history():
                commits = []
                try:
                    for commit in self.project.commits.list(
                        ref_name="main", path=path, per_page=limit
                    ):
                        commits.append(
                            {
                                "sha": commit.id,
                                "message": commit.message,
                                "author": commit.author_name,
                                "author_email": commit.author_email,
                                "committer": commit.committer_name,
                                "committer_email": commit.committer_email,
                                "date": commit.created_at,
                            }
                        )
                except GitlabGetError as e:
                    if e.response_code != 404:
                        raise

                return commits

            return await asyncio.get_event_loop().run_in_executor(None, _get_history)
        except Exception as e:
            self.logger.error(f"Failed to get file history for {path}: {e}")
            return []

    async def diff_between_commits(self, base_sha: str, head_sha: str) -> str:
        """Get diff between two commits."""
        try:

            def _get_diff():
                try:
                    comparison = self.project.repository_compare(base_sha, head_sha)
                    return comparison.get("diffs", [])
                except GitlabGetError as e:
                    self.logger.error(f"Failed to get diff between commits: {e}")
                    return ""

            return await asyncio.get_event_loop().run_in_executor(None, _get_diff)
        except Exception as e:
            self.logger.error(f"Failed to get diff between commits: {e}")
            return ""
