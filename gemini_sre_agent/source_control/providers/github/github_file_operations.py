# gemini_sre_agent/source_control/providers/github/github_file_operations.py

"""
GitHub file operations module.

This module handles file-specific operations for the GitHub provider.
"""

import asyncio
import base64
import difflib
import logging
from typing import Any, Dict, List, Optional

from github import Github, GithubException
from github.Repository import Repository

from ...models import (
    CommitInfo,
    FileInfo,
    RemediationResult,
)


class GitHubFileOperations:
    """Handles file-specific operations for GitHub."""

    def __init__(
        self,
        client: Github,
        repo: Repository,
        logger: logging.Logger,
        error_handling_components: Optional[Dict[str, Any]] = None,
    ):
        """Initialize file operations with GitHub client and repository."""
        self.client = client
        self.repo = repo
        self.logger = logger
        self.error_handling_components = error_handling_components

    async def _execute_with_error_handling(
        self, operation_name: str, func, *args, **kwargs
    ):
        """Execute an operation with error handling if available."""
        if self.error_handling_components:
            resilient_manager = self.error_handling_components.get("resilient_manager")
            if resilient_manager:
                return await resilient_manager.execute_resilient_operation(
                    operation_name, func, *args, **kwargs
                )

        # Fall back to direct execution
        return await func(*args, **kwargs)

    async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
        """Get file content from GitHub repository."""

        async def _get_file():
            try:
                if ref is None:
                    contents = self.repo.get_contents(path)
                else:
                    contents = self.repo.get_contents(path, ref=ref)
                if isinstance(contents, list):
                    # If it's a list, we can't get content directly
                    return ""
                elif hasattr(contents, "content"):
                    return base64.b64decode(contents.content).decode("utf-8")
                return ""
            except GithubException as e:
                if e.status == 404:
                    return ""
                raise

        return await self._execute_with_error_handling("get_file_content", _get_file)

    async def apply_remediation(
        self,
        file_path: str,
        remediation: str,
        commit_message: str,
        branch: Optional[str] = None,
    ) -> RemediationResult:
        """Apply remediation to a file."""

        async def _apply():
            try:
                # Get current file content
                if branch is None:
                    contents = self.repo.get_contents(file_path)
                else:
                    contents = self.repo.get_contents(file_path, ref=branch)

                if isinstance(contents, list):
                    # If it's a list, we can't get content directly
                    return RemediationResult(
                        success=False,
                        message="File not found or is a directory",
                        file_path=file_path,
                        operation_type="apply_remediation",
                        commit_sha="",
                        pull_request_url="",
                        error_details="File not found or is a directory",
                        additional_info={},
                    )

                if hasattr(contents, "sha"):
                    sha = contents.sha
                else:
                    sha = None

                # Update file with remediation
                if sha:
                    commit = self.repo.update_file(
                        path=file_path,
                        message=commit_message,
                        content=remediation,
                        sha=sha,
                        branch=branch,  # type: ignore
                    )
                else:
                    commit = self.repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=remediation,
                        branch=branch,  # type: ignore
                    )

                return RemediationResult(
                    success=True,
                    message=f"Applied remediation to {file_path}",
                    file_path=file_path,
                    operation_type="apply_remediation",
                    commit_sha=commit["commit"].sha,
                    pull_request_url="",
                    error_details="",
                    additional_info={},
                )
            except GithubException as e:
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

        return await self._execute_with_error_handling("apply_remediation", _apply)

    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if a file exists in the repository."""

        async def _exists():
            try:
                if ref is None:
                    self.repo.get_contents(path)
                else:
                    self.repo.get_contents(path, ref=ref)
                return True
            except GithubException as e:
                if e.status == 404:
                    return False
                raise

        return await self._execute_with_error_handling("file_exists", _exists)

    async def get_file_info(self, path: str, ref: Optional[str] = None) -> FileInfo:
        """Get file information."""

        async def _get_info():
            try:
                if ref is None:
                    contents = self.repo.get_contents(path)
                else:
                    contents = self.repo.get_contents(path, ref=ref)
                if isinstance(contents, list):
                    # If it's a list, we can't get file info directly
                    return FileInfo(
                        path=path,
                        size=0,
                        sha="",
                        is_binary=False,
                        last_modified=None,
                    )
                else:
                    return FileInfo(
                        path=path,
                        size=contents.size,  # type: ignore
                        sha=contents.sha,  # type: ignore
                        is_binary=contents.type == "file" and contents.size > 0,  # type: ignore
                        last_modified=(
                            contents.last_modified  # type: ignore
                            if hasattr(contents, "last_modified")
                            and contents.last_modified
                            else None
                        ),
                    )
            except GithubException as e:
                if e.status == 404:
                    return FileInfo(
                        path=path,
                        size=0,
                        sha="",
                        is_binary=False,
                        last_modified=None,
                    )
                raise

        return await self._execute_with_error_handling("get_file_info", _get_info)

    async def list_files(
        self, path: str = "", ref: Optional[str] = None
    ) -> List[FileInfo]:
        """List files in a directory."""
        try:

            def _list():
                files = []
                try:
                    if ref is None:
                        contents = self.repo.get_contents(path)
                    else:
                        contents = self.repo.get_contents(path, ref=ref)

                    if isinstance(contents, list):
                        for item in contents:
                            files.append(
                                FileInfo(
                                    path=item.path,  # type: ignore
                                    size=item.size,  # type: ignore
                                    sha=item.sha,  # type: ignore
                                    is_binary=item.type == "file" and item.size > 0,  # type: ignore
                                    last_modified=(
                                        item.last_modified  # type: ignore
                                        if hasattr(item, "last_modified")
                                        and item.last_modified
                                        else None
                                    ),
                                )
                            )
                    else:
                        # Single file
                        files.append(
                            FileInfo(
                                path=contents.path,  # type: ignore
                                size=contents.size,  # type: ignore
                                sha=contents.sha,  # type: ignore
                                is_binary=contents.type == "file" and contents.size > 0,  # type: ignore
                                last_modified=(
                                    contents.last_modified  # type: ignore
                                    if hasattr(contents, "last_modified")
                                    and contents.last_modified
                                    else None
                                ),
                            )
                        )
                except GithubException as e:
                    if e.status != 404:
                        raise

                return files

            return await asyncio.get_event_loop().run_in_executor(None, _list)
        except Exception as e:
            self.logger.error(f"Failed to list files in {path}: {e}")
            return []

    async def generate_patch(self, original: str, modified: str) -> str:
        """Generate a patch between original and modified content."""
        try:

            def _generate():
                return "\n".join(
                    difflib.unified_diff(
                        original.splitlines(keepends=True),
                        modified.splitlines(keepends=True),
                        fromfile="original",
                        tofile="modified",
                    )
                )

            return await asyncio.get_event_loop().run_in_executor(None, _generate)
        except Exception as e:
            self.logger.error(f"Failed to generate patch: {e}")
            return ""

    async def apply_patch(self, patch: str, file_path: str) -> bool:
        """Apply a patch to a file."""
        try:

            def _apply():
                try:
                    # Get current content
                    contents = self.repo.get_contents(file_path)
                    if isinstance(contents, list):
                        return False

                    # Apply patch (simplified - in real implementation, use patch library)
                    # This is a placeholder implementation
                    # current_content = base64.b64decode(contents.content).decode("utf-8")
                    return True
                except GithubException as e:
                    if e.status == 404:
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
                        if branch is None:
                            file_obj = self.repo.get_contents(file_path)
                        else:
                            file_obj = self.repo.get_contents(file_path, ref=branch)
                        # Update existing file
                        if isinstance(file_obj, list):
                            # If it's a list, we can't get sha directly
                            raise GithubException(404, "File not found")
                        commit = self.repo.update_file(
                            path=file_path,
                            message=message,
                            content=content,
                            sha=file_obj.sha,  # type: ignore
                            branch=branch,  # type: ignore
                        )
                    except GithubException as e:
                        if e.status == 404:
                            # Create new file
                            commit = self.repo.create_file(
                                path=file_path,
                                message=message,
                                content=content,
                                branch=branch,  # type: ignore
                            )
                        else:
                            raise

                    return commit["commit"].sha
                except GithubException as e:
                    self.logger.error(f"Failed to commit changes to {file_path}: {e}")
                    return None

            return await asyncio.get_event_loop().run_in_executor(None, _commit)
        except Exception as e:
            self.logger.error(f"Failed to commit changes to {file_path}: {e}")
            return None

    async def get_file_history(self, path: str, limit: int = 10) -> List[CommitInfo]:
        """Get file commit history."""
        try:

            def _get_history():
                commits = []
                try:
                    for commit in self.repo.get_commits(path=path)[:limit]:
                        commits.append(
                            CommitInfo(
                                sha=commit.sha,  # type: ignore
                                message=commit.commit.message,  # type: ignore
                                author=commit.commit.author.name,  # type: ignore
                                author_email=commit.commit.author.email,  # type: ignore
                                committer=commit.commit.committer.name,  # type: ignore
                                committer_email=commit.commit.committer.email,  # type: ignore
                                date=commit.commit.author.date,  # type: ignore
                            )
                        )
                except GithubException as e:
                    if e.status != 404:
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
                    comparison = self.repo.compare(base_sha, head_sha)
                    return getattr(comparison, "patch", "")
                except GithubException as e:
                    self.logger.error(f"Failed to get diff between commits: {e}")
                    return ""

            return await asyncio.get_event_loop().run_in_executor(None, _get_diff)
        except Exception as e:
            self.logger.error(f"Failed to get diff between commits: {e}")
            return ""
