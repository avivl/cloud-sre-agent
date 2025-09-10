# gemini_sre_agent/source_control/providers/github_pull_requests.py

"""
GitHub provider pull request operations module.

This module handles pull request and merge request operations for the GitHub provider.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from github import Github, GithubException
from github.Repository import Repository

from ...models import ProviderCapabilities


class GitHubPullRequests:
    """Handles pull request operations for GitHub."""

    def __init__(self, client: Github, repo: Repository, logger: logging.Logger):
        """Initialize pull request operations with GitHub client and repository."""
        self.client = client
        self.repo = repo
        self.logger = logger

    async def get_capabilities(self) -> ProviderCapabilities:
        """Get provider capabilities."""
        return ProviderCapabilities(
            supports_pull_requests=True,
            supports_merge_requests=False,  # GitHub uses pull requests
            supports_direct_commits=True,
            supports_patch_generation=True,
            supports_branch_operations=True,
            supports_file_history=True,
            supports_batch_operations=True,
        )

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
        draft: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Create a pull request."""
        try:

            def _create():
                try:
                    pr = self.repo.create_pull(
                        title=title,
                        body=body,
                        head=head_branch,
                        base=base_branch,
                        draft=draft,
                    )
                    return {
                        "number": pr.number,
                        "url": pr.html_url,
                        "state": pr.state,
                        "title": pr.title,
                        "body": pr.body,
                        "head": {
                            "ref": pr.head.ref,
                            "sha": pr.head.sha,
                        },
                        "base": {
                            "ref": pr.base.ref,
                            "sha": pr.base.sha,
                        },
                        "created_at": (
                            pr.created_at.isoformat() if pr.created_at else None
                        ),
                        "updated_at": (
                            pr.updated_at.isoformat() if pr.updated_at else None
                        ),
                    }
                except GithubException as e:
                    self.logger.error(f"Failed to create pull request: {e}")
                    return None

            return await asyncio.get_event_loop().run_in_executor(None, _create)
        except Exception as e:
            self.logger.error(f"Failed to create pull request: {e}")
            return None

    async def create_merge_request(
        self,
        title: str,
        description: str,
        source_branch: str,
        target_branch: str,
    ) -> Optional[Dict[str, Any]]:
        """Create a merge request (GitHub uses pull requests)."""
        # GitHub doesn't have merge requests, redirect to pull request
        return await self.create_pull_request(
            title=title,
            body=description,
            head_branch=source_branch,
            base_branch=target_branch,
        )

    async def get_pull_request(self, number: int) -> Optional[Dict[str, Any]]:
        """Get a pull request by number."""
        try:

            def _get():
                try:
                    pr = self.repo.get_pull(number)
                    return {
                        "number": pr.number,
                        "url": pr.html_url,
                        "state": pr.state,
                        "title": pr.title,
                        "body": pr.body,
                        "head": {
                            "ref": pr.head.ref,
                            "sha": pr.head.sha,
                        },
                        "base": {
                            "ref": pr.base.ref,
                            "sha": pr.base.sha,
                        },
                        "created_at": (
                            pr.created_at.isoformat() if pr.created_at else None
                        ),
                        "updated_at": (
                            pr.updated_at.isoformat() if pr.updated_at else None
                        ),
                        "merged": pr.merged,
                        "mergeable": pr.mergeable,
                        "mergeable_state": pr.mergeable_state,
                    }
                except GithubException as e:
                    if e.status == 404:
                        return None
                    raise

            return await asyncio.get_event_loop().run_in_executor(None, _get)
        except Exception as e:
            self.logger.error(f"Failed to get pull request {number}: {e}")
            return None

    async def list_pull_requests(
        self,
        state: str = "open",
        head: Optional[str] = None,
        base: Optional[str] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """List pull requests."""
        try:

            def _list():
                prs = []
                try:
                    params = {"state": state}
                    if head:
                        params["head"] = head
                    if base:
                        params["base"] = base

                    for pr in self.repo.get_pulls(**params)[:limit]:
                        prs.append(
                            {
                                "number": pr.number,  # type: ignore
                                "url": pr.html_url,  # type: ignore
                                "state": pr.state,  # type: ignore
                                "title": pr.title,  # type: ignore
                                "body": pr.body,  # type: ignore
                                "head": {
                                    "ref": pr.head.ref,  # type: ignore
                                    "sha": pr.head.sha,  # type: ignore
                                },
                                "base": {
                                    "ref": pr.base.ref,  # type: ignore
                                    "sha": pr.base.sha,  # type: ignore
                                },
                                "created_at": pr.created_at.isoformat() if pr.created_at else None,  # type: ignore
                                "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,  # type: ignore
                                "merged": pr.merged,  # type: ignore
                                "mergeable": pr.mergeable,  # type: ignore
                                "mergeable_state": pr.mergeable_state,  # type: ignore
                            }
                        )
                except GithubException as e:
                    self.logger.error(f"Failed to list pull requests: {e}")

                return prs

            return await asyncio.get_event_loop().run_in_executor(None, _list)
        except Exception as e:
            self.logger.error(f"Failed to list pull requests: {e}")
            return []

    async def merge_pull_request(
        self,
        number: int,
        merge_method: str = "merge",
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> bool:
        """Merge a pull request."""
        try:

            def _merge():
                try:
                    pr = self.repo.get_pull(number)
                    if pr.mergeable:
                        merge_result = pr.merge(
                            merge_method=merge_method,
                            commit_title=commit_title,  # type: ignore
                            commit_message=commit_message,  # type: ignore
                        )
                        return merge_result.merged
                    return False
                except GithubException as e:
                    self.logger.error(f"Failed to merge pull request {number}: {e}")
                    return False

            return await asyncio.get_event_loop().run_in_executor(None, _merge)
        except Exception as e:
            self.logger.error(f"Failed to merge pull request {number}: {e}")
            return False

    async def close_pull_request(self, number: int) -> bool:
        """Close a pull request."""
        try:

            def _close():
                try:
                    pr = self.repo.get_pull(number)
                    pr.edit(state="closed")
                    return True
                except GithubException as e:
                    self.logger.error(f"Failed to close pull request {number}: {e}")
                    return False

            return await asyncio.get_event_loop().run_in_executor(None, _close)
        except Exception as e:
            self.logger.error(f"Failed to close pull request {number}: {e}")
            return False

    async def add_comment(self, number: int, body: str) -> bool:
        """Add a comment to a pull request."""
        try:

            def _add_comment():
                try:
                    pr = self.repo.get_pull(number)
                    pr.create_issue_comment(body)
                    return True
                except GithubException as e:
                    self.logger.error(f"Failed to add comment to PR {number}: {e}")
                    return False

            return await asyncio.get_event_loop().run_in_executor(None, _add_comment)
        except Exception as e:
            self.logger.error(f"Failed to add comment to PR {number}: {e}")
            return False

    async def get_pull_request_files(self, number: int) -> List[Dict[str, Any]]:
        """Get files changed in a pull request."""
        try:

            def _get_files():
                files = []
                try:
                    pr = self.repo.get_pull(number)
                    for file in pr.get_files():
                        files.append(
                            {
                                "filename": file.filename,
                                "status": file.status,
                                "additions": file.additions,
                                "deletions": file.deletions,
                                "changes": file.changes,
                                "patch": file.patch,
                                "blob_url": file.blob_url,
                                "raw_url": file.raw_url,
                                "contents_url": file.contents_url,
                            }
                        )
                except GithubException as e:
                    self.logger.error(f"Failed to get PR files for {number}: {e}")

                return files

            return await asyncio.get_event_loop().run_in_executor(None, _get_files)
        except Exception as e:
            self.logger.error(f"Failed to get PR files for {number}: {e}")
            return []

    async def get_pull_request_commits(self, number: int) -> List[Dict[str, Any]]:
        """Get commits in a pull request."""
        try:

            def _get_commits():
                commits = []
                try:
                    pr = self.repo.get_pull(number)
                    for commit in pr.get_commits():
                        commits.append(
                            {
                                "sha": commit.sha,
                                "message": commit.commit.message,
                                "author": {
                                    "name": commit.commit.author.name,
                                    "email": commit.commit.author.email,
                                    "date": commit.commit.author.date.isoformat(),
                                },
                                "committer": {
                                    "name": commit.commit.committer.name,
                                    "email": commit.commit.committer.email,
                                    "date": commit.commit.committer.date.isoformat(),
                                },
                                "url": commit.html_url,
                                "stats": (
                                    {
                                        "additions": commit.stats.additions,
                                        "deletions": commit.stats.deletions,
                                        "total": commit.stats.total,
                                    }
                                    if hasattr(commit, "stats") and commit.stats
                                    else None
                                ),
                            }
                        )
                except GithubException as e:
                    self.logger.error(f"Failed to get PR commits for {number}: {e}")

                return commits

            return await asyncio.get_event_loop().run_in_executor(None, _get_commits)
        except Exception as e:
            self.logger.error(f"Failed to get PR commits for {number}: {e}")
            return []
