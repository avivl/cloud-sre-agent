"""GitLab provider implementation for source control operations."""

import logging
from typing import Any, Dict, List, Optional, Tuple

import gitlab
from gitlab.exceptions import GitlabGetError

from ...config.source_control_repositories import GitLabRepositoryConfig
from ..base_implementation import BaseSourceControlProvider
from ..models import (
    BatchOperation,
    BranchInfo,
    CommitInfo,
    CommitOptions,
    FileInfo,
    FileOperation,
    OperationResult,
    PatchFormat,
    ProviderCapabilities,
    ProviderHealth,
    RemediationResult,
    RepositoryInfo,
)
from .gitlab_models import (
    GitLabCredentials,
)


class GitLabProvider(BaseSourceControlProvider):
    """GitLab provider implementation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the GitLab provider."""
        super().__init__(config)
        self.repo_config = GitLabRepositoryConfig(**config)
        self.credentials: Optional[GitLabCredentials] = None
        self.gl: Optional[gitlab.Gitlab] = None
        self.project: Optional[gitlab.objects.Project] = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    async def initialize(self):
        """Initialize the GitLab connection and project."""
        try:
            # Get credentials from credential manager
            if hasattr(self, "credential_manager") and self.credential_manager:
                creds = await self.credential_manager.get_credentials(
                    self.repo_config.credential_id
                )
                if creds:
                    self.credentials = GitLabCredentials(
                        token=creds.get("token", ""),
                        url=creds.get("url", "https://gitlab.com"),
                        api_version=creds.get("api_version", "v4"),
                        timeout=creds.get("timeout", 30),
                        ssl_verify=creds.get("ssl_verify", True),
                    )
                else:
                    raise ValueError(
                        f"Credentials not found for {self.repo_config.credential_id}"
                    )
            else:
                raise ValueError("Credential manager not available")

            # Initialize GitLab client
            self.gl = gitlab.Gitlab(
                self.credentials.url,
                private_token=self.credentials.token,
                api_version=self.credentials.api_version,
                timeout=self.credentials.timeout,
                ssl_verify=self.credentials.ssl_verify,
            )

            # Test authentication
            await self.test_connection()

            # Get project
            self.project = self.gl.projects.get(self.repo_config.project_id)
            self.logger.info(f"Connected to GitLab project: {self.project.name}")

        except Exception as e:
            self.logger.error(f"Failed to initialize GitLab provider: {e}")
            raise

    async def cleanup(self):
        """Clean up resources."""
        self.gl = None
        self.project = None

    async def test_connection(self) -> bool:
        """Test the connection to GitLab."""
        try:
            if not self.gl:
                return False

            # Test authentication by getting current user
            user = self.gl.user
            self.logger.info(f"Connected as user: {user.username}")
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    async def get_repository_info(self) -> RepositoryInfo:
        """Get information about the repository."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            return RepositoryInfo(
                name=self.project.name,
                url=self.project.web_url,
                owner=self.project.namespace.get("full_path", "").split("/")[0],
                is_private=self.project.visibility == "private",
                default_branch=self.project.default_branch,
                description=self.project.description,
                additional_info={
                    "project_id": self.project.id,
                    "path": self.project.path,
                    "full_path": self.project.path_with_namespace,
                    "visibility": self.project.visibility,
                    "created_at": (
                        self.project.created_at.isoformat()
                        if self.project.created_at
                        else None
                    ),
                    "last_activity_at": (
                        self.project.last_activity_at.isoformat()
                        if self.project.last_activity_at
                        else None
                    ),
                },
            )
        except Exception as e:
            self.logger.error(f"Failed to get repository info: {e}")
            raise

    async def read_file(self, file_path: str, ref: str = "main") -> str:
        """Read a file from the repository."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            file_content = self.project.files.get(file_path, ref=ref)
            return file_content.decode().decode("utf-8")
        except GitlabGetError as e:
            if e.response_code == 404:
                raise FileNotFoundError(f"File {file_path} not found")
            raise
        except Exception as e:
            self.logger.error(f"Failed to read file {file_path}: {e}")
            raise

    async def write_file(
        self,
        file_path: str,
        content: str,
        message: str = "Update file",
        branch: str = "main",
    ) -> bool:
        """Write content to a file in the repository."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            # Check if file exists
            try:
                existing_file = self.project.files.get(file_path, ref=branch)
                # Update existing file
                existing_file.content = content
                existing_file.save(branch=branch, commit_message=message)
            except GitlabGetError:
                # Create new file
                self.project.files.create(
                    {
                        "file_path": file_path,
                        "branch": branch,
                        "content": content,
                        "commit_message": message,
                    }
                )

            return True
        except Exception as e:
            self.logger.error(f"Failed to write file {file_path}: {e}")
            return False

    async def file_exists(self, file_path: str, ref: str = "main") -> bool:
        """Check if a file exists in the repository."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            self.project.files.get(file_path, ref=ref)
            return True
        except GitlabGetError:
            return False
        except Exception as e:
            self.logger.error(f"Failed to check file existence {file_path}: {e}")
            return False

    async def get_file_info(self, file_path: str, ref: str = "main") -> FileInfo:
        """Get information about a file."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            file_data = self.project.files.get(file_path, ref=ref)
            return FileInfo(
                path=file_path,
                size=file_data.size,
                last_modified=file_data.last_activity_at,
                sha=file_data.id,
                is_binary=file_data.encoding == "base64",
                encoding=file_data.encoding,
            )
        except GitlabGetError as e:
            if e.response_code == 404:
                raise FileNotFoundError(f"File {file_path} not found")
            raise
        except Exception as e:
            self.logger.error(f"Failed to get file info {file_path}: {e}")
            raise

    async def list_files(self, directory: str = "", ref: str = "main") -> List[str]:
        """List files in a directory."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            items = self.project.repository_tree(
                ref=ref, path=directory, recursive=True
            )
            files = []
            for item in items:
                if item["type"] == "blob":  # Only files, not directories
                    files.append(item["path"])
            return files
        except Exception as e:
            self.logger.error(f"Failed to list files in {directory}: {e}")
            return []

    async def generate_patch(
        self,
        file_path: str,
        new_content: str,
        format: PatchFormat = PatchFormat.UNIFIED,
    ) -> str:
        """Generate a patch for file changes."""
        # GitLab doesn't have a direct patch generation API, so we'll use Git diff
        try:
            # Get current content
            current_content = await self.read_file(file_path)

            # Generate unified diff
            import difflib

            patch = difflib.unified_diff(
                current_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                n=3,
            )
            return "".join(patch)
        except Exception as e:
            self.logger.error(f"Failed to generate patch for {file_path}: {e}")
            raise

    async def apply_patch(self, patch_content: str, branch: str = "main") -> bool:
        """Apply a patch to the repository."""
        # GitLab doesn't have direct patch application, so we'll need to parse and apply manually
        # This is a simplified implementation
        try:
            # Parse patch content and apply changes
            # This would need more sophisticated patch parsing
            self.logger.warning("Patch application not fully implemented for GitLab")
            return False
        except Exception as e:
            self.logger.error(f"Failed to apply patch: {e}")
            return False

    async def commit_changes(
        self, file_operations: List[FileOperation], options: CommitOptions
    ) -> str:
        """Commit changes to the repository."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            # Create a new branch if specified
            if options.branch and options.branch != "main":
                await self.create_branch(options.branch)

            # Apply file operations
            for op in file_operations:
                if op.operation_type == "write":
                    await self.write_file(
                        op.file_path,
                        op.content or "",
                        options.commit_message,
                        options.branch or "main",
                    )
                elif op.operation_type == "delete":
                    # Delete file
                    try:
                        file_to_delete = self.project.files.get(
                            op.file_path, ref=options.branch or "main"
                        )
                        file_to_delete.delete(
                            branch=options.branch or "main",
                            commit_message=options.commit_message,
                        )
                    except GitlabGetError:
                        pass  # File doesn't exist, nothing to delete

            # Return the latest commit SHA
            commits = self.project.commits.list(
                ref_name=options.branch or "main", per_page=1
            )
            if commits:
                return commits[0].id
            return ""
        except Exception as e:
            self.logger.error(f"Failed to commit changes: {e}")
            raise

    async def apply_remediation(
        self, path: str, content: str, message: str, branch: Optional[str] = None
    ) -> RemediationResult:
        """Apply a remediation by writing content to a file."""
        try:
            success = await self.write_file(path, content, message, branch or "main")
            if success:
                return RemediationResult(
                    success=True,
                    message=f"Successfully applied remediation to {path}",
                    file_path=path,
                    operation_type="write",
                )
            else:
                return RemediationResult(
                    success=False,
                    message=f"Failed to apply remediation to {path}",
                    file_path=path,
                    operation_type="write",
                    error_details="Write operation failed",
                )
        except Exception as e:
            return RemediationResult(
                success=False,
                message=f"Error applying remediation to {path}: {str(e)}",
                file_path=path,
                operation_type="write",
                error_details=str(e),
            )

    async def create_branch(self, name: str, source_branch: str = "main") -> bool:
        """Create a new branch."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            self.project.branches.create({"branch": name, "ref": source_branch})
            return True
        except Exception as e:
            self.logger.error(f"Failed to create branch {name}: {e}")
            return False

    async def delete_branch(self, name: str) -> bool:
        """Delete a branch."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            branch = self.project.branches.get(name)
            branch.delete()
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete branch {name}: {e}")
            return False

    async def list_branches(self) -> List[BranchInfo]:
        """List all branches."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            branches = self.project.branches.list()
            branch_infos = []
            for branch in branches:
                branch_infos.append(
                    BranchInfo(
                        name=branch.name,
                        sha=branch.commit["id"],
                        is_protected=branch.protected,
                        last_commit=branch.commit["committed_date"],
                    )
                )
            return branch_infos
        except Exception as e:
            self.logger.error(f"Failed to list branches: {e}")
            return []

    async def get_current_branch(self) -> str:
        """Get the current branch name."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            # GitLab doesn't have a concept of "current branch" for API operations
            # Return the default branch
            return self.project.default_branch
        except Exception as e:
            self.logger.error(f"Failed to get current branch: {e}")
            return "main"

    async def checkout_branch(self, name: str) -> bool:
        """Checkout a branch (not applicable for GitLab API)."""
        # GitLab API doesn't support checkout operations
        # This would be handled by the client-side Git operations
        self.logger.warning("Branch checkout not supported via GitLab API")
        return False

    async def get_status(self) -> Dict[str, Any]:
        """Get the repository status."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            # GitLab doesn't have a direct status API like Git
            # Return basic project information
            return {
                "project_id": self.project.id,
                "default_branch": self.project.default_branch,
                "last_activity": (
                    self.project.last_activity_at.isoformat()
                    if self.project.last_activity_at
                    else None
                ),
                "visibility": self.project.visibility,
            }
        except Exception as e:
            self.logger.error(f"Failed to get status: {e}")
            return {}

    async def execute_git_command(self, *args: str) -> Tuple[str, str]:
        """Execute a Git command (not applicable for GitLab API)."""
        # GitLab API doesn't support direct Git command execution
        self.logger.warning("Git command execution not supported via GitLab API")
        return "", "Git command execution not supported via GitLab API"

    async def get_file_history(
        self, file_path: str, max_entries: int = 10
    ) -> List[CommitInfo]:
        """Get the commit history for a specific file."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            commits = self.project.commits.list(
                ref_name="main", path=file_path, per_page=max_entries
            )
            history = []
            for commit in commits:
                history.append(
                    CommitInfo(
                        sha=commit.id,
                        message=commit.message,
                        author=commit.author_name,
                        author_email=commit.author_email,
                        committer=commit.committer_name,
                        committer_email=commit.committer_email,
                        date=commit.committed_date,
                        parents=commit.parent_ids,
                    )
                )
            return history
        except Exception as e:
            self.logger.error(f"Failed to get file history for {file_path}: {e}")
            return []

    async def diff_between_commits(
        self, file_path: str, old_commit: str, new_commit: str = "HEAD"
    ) -> str:
        """Get the diff for a file between two commits."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            # Get diff between commits
            diff = self.project.repository_compare(old_commit, new_commit)
            # Find the diff for the specific file
            for change in diff["diffs"]:
                if change["new_path"] == file_path or change["old_path"] == file_path:
                    return change["diff"]
            return ""
        except Exception as e:
            self.logger.error(f"Failed to get diff for {file_path}: {e}")
            return ""

    async def check_conflicts(
        self, path: str, content: str, branch: Optional[str] = None
    ) -> bool:
        """Check for merge conflicts."""
        # GitLab handles conflict detection through merge request creation
        # This is a simplified implementation
        return False

    async def resolve_conflicts(
        self, path: str, content: str, strategy: str = "manual"
    ) -> bool:
        """Resolve merge conflicts."""
        # GitLab handles conflict resolution through merge request interface
        # This is a simplified implementation
        return False

    async def create_pull_request(
        self, title: str, description: str, head_branch: str, base_branch: str, **kwargs
    ) -> RemediationResult:
        """Create a pull request (GitLab uses merge requests)."""
        return await self.create_merge_request(
            title, description, head_branch, base_branch, **kwargs
        )

    async def create_merge_request(
        self, title: str, description: str, head_branch: str, base_branch: str, **kwargs
    ) -> RemediationResult:
        """Create a merge request."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            mr = self.project.mergerequests.create(
                {
                    "source_branch": head_branch,
                    "target_branch": base_branch,
                    "title": title,
                    "description": description,
                    **kwargs,
                }
            )
            return RemediationResult(
                success=True,
                message=f"Successfully created merge request #{mr.iid}",
                pull_request_url=mr.web_url,
            )
        except Exception as e:
            self.logger.error(f"Failed to create merge request: {e}")
            return RemediationResult(
                success=False,
                message=f"Failed to create merge request: {str(e)}",
                error_details=str(e),
            )

    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Execute multiple operations in batch."""
        results = []
        for operation in operations:
            try:
                if operation.operation_type == "write":
                    success = await self.write_file(
                        operation.file_path,
                        operation.content or "",
                        operation.message or "Batch operation",
                    )
                    results.append(
                        OperationResult(
                            operation_id=operation.operation_id,
                            file_path=operation.file_path,
                            operation_type=operation.operation_type,
                            success=success,
                            message=f"Write operation {'succeeded' if success else 'failed'}",
                        )
                    )
                else:
                    results.append(
                        OperationResult(
                            operation_id=operation.operation_id,
                            file_path=operation.file_path,
                            operation_type=operation.operation_type,
                            success=False,
                            message=f"Unsupported operation type: {operation.operation_type}",
                        )
                    )
            except Exception as e:
                results.append(
                    OperationResult(
                        operation_id=operation.operation_id,
                        file_path=operation.file_path,
                        operation_type=operation.operation_type,
                        success=False,
                        message=f"Operation failed: {str(e)}",
                        error_details=str(e),
                    )
                )
        return results

    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get information about a specific branch."""
        if not self.project:
            raise RuntimeError("Provider not initialized")

        try:
            branch = self.project.branches.get(name)
            return BranchInfo(
                name=branch.name,
                sha=branch.commit["id"],
                is_protected=branch.protected,
                last_commit=branch.commit["committed_date"],
            )
        except Exception as e:
            self.logger.error(f"Failed to get branch info for {name}: {e}")
            return None

    async def get_capabilities(self) -> ProviderCapabilities:
        """Get the capabilities of this provider."""
        return ProviderCapabilities(
            supports_pull_requests=False,
            supports_merge_requests=True,
            supports_direct_commits=True,
            supports_patch_generation=True,
            supports_branch_operations=True,
            supports_file_history=True,
            supports_batch_operations=True,
            max_file_size=100 * 1024 * 1024,  # 100MB GitLab limit
            supported_patch_formats=[PatchFormat.UNIFIED],
            supported_encodings=["utf-8", "base64"],
        )

    async def get_health_status(self) -> ProviderHealth:
        """Get the health status of the provider."""
        try:
            if await self.test_connection():
                return ProviderHealth(
                    status="healthy",
                    message="GitLab provider is operational",
                    details={
                        "project_id": self.project.id if self.project else None,
                        "project_name": self.project.name if self.project else None,
                    },
                )
            else:
                return ProviderHealth(
                    status="unhealthy",
                    message="GitLab provider connection failed",
                )
        except Exception as e:
            return ProviderHealth(
                status="unhealthy",
                message=f"GitLab provider error: {str(e)}",
            )

    async def get_file_content(self, file_path: str, ref: str = "main") -> str:
        """Get the content of a file."""
        return await self.read_file(file_path, ref)

    async def validate_credentials(self) -> bool:
        """Validate the current credentials."""
        return await self.test_connection()

    async def refresh_credentials(self) -> bool:
        """Refresh the current credentials."""
        # GitLab tokens don't typically need refreshing
        # This could be extended to handle token refresh if needed
        return await self.test_connection()
