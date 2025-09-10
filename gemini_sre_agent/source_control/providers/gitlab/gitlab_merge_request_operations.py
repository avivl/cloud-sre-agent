# gemini_sre_agent/source_control/providers/gitlab/gitlab_merge_request_operations.py

"""
GitLab merge request operations module.

This module handles merge request operations for the GitLab provider.
"""

import logging
from typing import Any, Dict, List, Optional

import gitlab
from gitlab.exceptions import GitlabGetError

from ...models import (
    ProviderCapabilities,
    RemediationResult,
)


class GitLabMergeRequestOperations:
    """Handles merge request operations for GitLab."""

    def __init__(
        self,
        gl: gitlab.Gitlab,
        project: Any,
        logger: logging.Logger,
        error_handling_components: Optional[Dict[str, Any]] = None,
    ):
        """Initialize merge request operations with GitLab client and project."""
        self.gl = gl
        self.project = project
        self.logger = logger
        self.error_handling_components = error_handling_components

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

    async def get_capabilities(self) -> ProviderCapabilities:
        """Get provider capabilities."""
        return ProviderCapabilities(
            supports_pull_requests=False,
            supports_merge_requests=True,
            supports_direct_commits=True,
            supports_patch_generation=True,
            supports_branch_operations=True,
            supports_file_history=True,
            supports_batch_operations=True,
        )

    async def create_merge_request(
        self,
        title: str,
        description: str,
        source_branch: str,
        target_branch: str,
        **kwargs: Any,
    ) -> RemediationResult:
        """Create a merge request."""

        async def _create():
            try:
                mr = self.project.mergerequests.create(
                    {
                        "title": title,
                        "description": description,
                        "source_branch": source_branch,
                        "target_branch": target_branch,
                        "remove_source_branch": kwargs.get(
                            "remove_source_branch", False
                        ),
                    }
                )

                return RemediationResult(
                    success=True,
                    message=f"Created merge request: {title}",
                    file_path="",
                    operation_type="create_merge_request",
                    commit_sha="",
                    pull_request_url=mr.web_url,
                    error_details="",
                    additional_info={
                        "merge_request_id": mr.iid,
                        "merge_request_url": mr.web_url,
                    },
                )
            except GitlabGetError as e:
                return RemediationResult(
                    success=False,
                    message=f"Failed to create merge request: {e}",
                    file_path="",
                    operation_type="create_merge_request",
                    commit_sha="",
                    pull_request_url="",
                    error_details=str(e),
                    additional_info={},
                )

        return await self._execute_with_error_handling("create_merge_request", _create)

    async def get_merge_request(self, mr_id: int) -> Optional[Dict[str, Any]]:
        """Get a merge request by ID."""

        async def _get():
            try:
                mr = self.project.mergerequests.get(mr_id)
                return {
                    "id": mr.iid,
                    "url": mr.web_url,
                    "state": mr.state,
                    "title": mr.title,
                    "description": mr.description,
                    "source_branch": mr.source_branch,
                    "target_branch": mr.target_branch,
                    "created_at": mr.created_at,
                    "updated_at": mr.updated_at,
                    "merged": mr.state == "merged",
                    "mergeable": mr.merge_status == "can_be_merged",
                    "merge_status": mr.merge_status,
                }
            except GitlabGetError as e:
                if e.response_code == 404:
                    return None
                self.logger.error(f"Failed to get merge request {mr_id}: {e}")
                return None

        return await self._execute_with_error_handling("get_merge_request", _get)

    async def list_merge_requests(
        self,
        state: str = "opened",
        source_branch: Optional[str] = None,
        target_branch: Optional[str] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """List merge requests."""

        async def _list():
            mrs = []
            try:
                params = {"state": state}
                if source_branch:
                    params["source_branch"] = source_branch
                if target_branch:
                    params["target_branch"] = target_branch

                for mr in self.project.mergerequests.list(**params)[:limit]:
                    mrs.append(
                        {
                            "id": mr.iid,
                            "url": mr.web_url,
                            "state": mr.state,
                            "title": mr.title,
                            "description": mr.description,
                            "source_branch": mr.source_branch,
                            "target_branch": mr.target_branch,
                            "created_at": mr.created_at,
                            "updated_at": mr.updated_at,
                            "merged": mr.state == "merged",
                            "mergeable": mr.merge_status == "can_be_merged",
                            "merge_status": mr.merge_status,
                        }
                    )
            except GitlabGetError as e:
                self.logger.error(f"Failed to list merge requests: {e}")

            return mrs

        return await self._execute_with_error_handling("list_merge_requests", _list)

    async def merge_merge_request(
        self,
        mr_id: int,
        merge_method: str = "merge",
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> bool:
        """Merge a merge request."""

        async def _merge():
            try:
                mr = self.project.mergerequests.get(mr_id)
                if mr.merge_status == "can_be_merged":
                    mr.merge(merge_commit_message=commit_message or "")
                    return True
                return False
            except GitlabGetError as e:
                self.logger.error(f"Failed to merge merge request {mr_id}: {e}")
                return False

        return await self._execute_with_error_handling("merge_merge_request", _merge)

    async def close_merge_request(self, mr_id: int) -> bool:
        """Close a merge request."""

        async def _close():
            try:
                mr = self.project.mergerequests.get(mr_id)
                mr.state_event = "close"
                mr.save()
                return True
            except GitlabGetError as e:
                self.logger.error(f"Failed to close merge request {mr_id}: {e}")
                return False

        return await self._execute_with_error_handling("close_merge_request", _close)

    async def reopen_merge_request(self, mr_id: int) -> bool:
        """Reopen a merge request."""

        async def _reopen():
            try:
                mr = self.project.mergerequests.get(mr_id)
                mr.state_event = "reopen"
                mr.save()
                return True
            except GitlabGetError as e:
                self.logger.error(f"Failed to reopen merge request {mr_id}: {e}")
                return False

        return await self._execute_with_error_handling("reopen_merge_request", _reopen)

    async def add_comment(self, mr_id: int, body: str) -> bool:
        """Add a comment to a merge request."""

        async def _add_comment():
            try:
                mr = self.project.mergerequests.get(mr_id)
                mr.notes.create({"body": body})
                return True
            except GitlabGetError as e:
                self.logger.error(f"Failed to add comment to MR {mr_id}: {e}")
                return False

        return await self._execute_with_error_handling("add_comment", _add_comment)

    async def get_merge_request_files(self, mr_id: int) -> List[Dict[str, Any]]:
        """Get files changed in a merge request."""

        async def _get_files():
            files = []
            try:
                mr = self.project.mergerequests.get(mr_id)
                for change in mr.changes():
                    files.append(
                        {
                            "old_path": change["old_path"],
                            "new_path": change["new_path"],
                            "a_mode": change["a_mode"],
                            "b_mode": change["b_mode"],
                            "diff": change["diff"],
                            "new_file": change["new_file"],
                            "renamed_file": change["renamed_file"],
                            "deleted_file": change["deleted_file"],
                        }
                    )
            except GitlabGetError as e:
                self.logger.error(f"Failed to get MR files for {mr_id}: {e}")

            return files

        return await self._execute_with_error_handling(
            "get_merge_request_files", _get_files
        )

    async def get_merge_request_commits(self, mr_id: int) -> List[Dict[str, Any]]:
        """Get commits in a merge request."""

        async def _get_commits():
            commits = []
            try:
                mr = self.project.mergerequests.get(mr_id)
                for commit in mr.commits():
                    commits.append(
                        {
                            "id": commit["id"],
                            "short_id": commit["short_id"],
                            "title": commit["title"],
                            "message": commit["message"],
                            "author_name": commit["author_name"],
                            "author_email": commit["author_email"],
                            "created_at": commit["created_at"],
                            "stats": commit.get("stats", {}),
                        }
                    )
            except GitlabGetError as e:
                self.logger.error(f"Failed to get MR commits for {mr_id}: {e}")

            return commits

        return await self._execute_with_error_handling(
            "get_merge_request_commits", _get_commits
        )
