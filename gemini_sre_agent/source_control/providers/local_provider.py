"""Local filesystem provider with Git integration and patch generation capabilities."""

import difflib
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chardet
from git import GitCommandError, InvalidGitRepositoryError, Repo
from patch_ng import PatchSet

from ...config.source_control_repositories import LocalRepositoryConfig
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


class LocalProvider(BaseSourceControlProvider):
    """Provider for local filesystem operations with Git integration and patch generation capabilities."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the local provider with configuration."""
        super().__init__(config)
        # Convert config dict back to LocalRepositoryConfig for type safety
        self.repo_config = LocalRepositoryConfig(**config)
        self.root_path = Path(self.repo_config.path).expanduser().resolve()
        self.git_enabled = getattr(self.repo_config, "git_enabled", False)
        self.auto_init_git = getattr(self.repo_config, "auto_init_git", False)
        self.default_encoding = getattr(self.repo_config, "default_encoding", "utf-8")
        self.backup_files = getattr(self.repo_config, "backup_files", True)
        self.backup_directory = getattr(self.repo_config, "backup_directory", None)

        self.repo: Optional[Repo] = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """Setup resources when entering async context."""
        if self.git_enabled:
            try:
                self.repo = Repo(self.root_path)
                self.logger.info(f"Git repository initialized at {self.root_path}")
            except (GitCommandError, InvalidGitRepositoryError):
                if self.auto_init_git:
                    self.repo = Repo.init(self.root_path)
                    self.logger.info(
                        f"Initialized new Git repository at {self.root_path}"
                    )
                else:
                    self.logger.warning(
                        f"Path {self.root_path} is not a Git repository and auto_init is disabled"
                    )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting async context."""
        self.repo = None

    async def test_connection(self) -> bool:
        """Test if the local path exists and is accessible."""
        return self.root_path.exists() and os.access(self.root_path, os.R_OK | os.W_OK)

    async def get_repository_info(self) -> RepositoryInfo:
        """Get information about the local repository."""
        if self.repo is not None:
            try:
                # Get remote information if available
                remotes = self.repo.remotes
                url = None
                if remotes:
                    url = (
                        remotes.origin.url
                        if "origin" in [r.name for r in remotes]
                        else list(remotes)[0].url
                    )

                return RepositoryInfo(
                    name=self.repo_config.name,
                    url=url,
                    owner=None,  # Local repos don't have owners
                    is_private=True,  # Local repos are always private
                    default_branch=(
                        self.repo.active_branch.name
                        if self.repo.active_branch
                        else "main"
                    ),
                    description=f"Local repository at {self.root_path}",
                    additional_info={
                        "path": str(self.root_path),
                        "git_enabled": self.git_enabled,
                        "is_git_repo": self.repo is not None,
                    },
                )
            except Exception as e:
                self.logger.error(f"Error getting repository info: {e}")
                return RepositoryInfo(
                    name=self.repo_config.name,
                    url=None,
                    is_private=True,
                    additional_info={"error": str(e)},
                )
        else:
            return RepositoryInfo(
                name=self.repo_config.name,
                url=None,
                is_private=True,
                additional_info={
                    "path": str(self.root_path),
                    "git_enabled": self.git_enabled,
                    "is_git_repo": False,
                },
            )

    async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
        """Read a file with proper encoding detection if not specified."""
        file_path = self.root_path / path
        if not file_path.exists():
            raise FileNotFoundError(f"File {path} not found")

        # Read the file in binary mode first
        with open(file_path, "rb") as f:
            content = f.read()

        # Detect encoding if not provided
        detected = chardet.detect(content)
        encoding = detected["encoding"] or self.default_encoding

        # Decode with the detected or provided encoding
        return content.decode(encoding)

    async def write_file(
        self, file_path: str, content: str, encoding: Optional[str] = None
    ) -> bool:
        """Write content to a file with specified encoding."""
        path = self.root_path / file_path

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Use provided encoding or default
        file_encoding = encoding or self.default_encoding

        with open(path, "w", encoding=file_encoding) as f:
            f.write(content)
        return True

    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if a file exists."""
        return (self.root_path / path).exists()

    async def get_file_info(self, path: str, ref: Optional[str] = None) -> FileInfo:
        """Get information about a file."""
        file_path = self.root_path / path

        if not file_path.exists():
            raise FileNotFoundError(f"File {path} not found")

        if file_path.is_dir():
            raise ValueError(f"Path {path} is a directory, not a file")

        stat = file_path.stat()

        # Detect if file is binary
        is_binary = False
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                is_binary = b"\0" in chunk
        except Exception:
            pass

        # Detect encoding
        encoding = None
        if not is_binary:
            try:
                with open(file_path, "rb") as f:
                    content = f.read(1024)
                    detected = chardet.detect(content)
                    encoding = detected["encoding"]
            except Exception:
                pass

        return FileInfo(
            path=path,
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
            is_binary=is_binary,
            encoding=encoding,
        )

    async def list_files(
        self, directory: str = "", pattern: Optional[str] = None
    ) -> List[str]:
        """List files in a directory, optionally filtered by pattern."""
        dir_path = self.root_path / directory
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory {directory} not found")

        files = []
        for item in dir_path.glob("**/*"):
            if item.is_file():
                rel_path = str(item.relative_to(self.root_path))
                if pattern is None or re.search(pattern, rel_path):
                    files.append(rel_path)
        return files

    async def generate_patch(
        self,
        file_path: str,
        new_content: str,
        format: PatchFormat = PatchFormat.UNIFIED,
        context_lines: int = 3,
    ) -> str:
        """Generate a patch between the current file and new content."""
        try:
            current_content = await self.get_file_content(file_path)
        except FileNotFoundError:
            current_content = ""

        current_lines = current_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        if format == PatchFormat.UNIFIED:
            patch = difflib.unified_diff(
                current_lines,
                new_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                n=context_lines,
            )
            return "".join(patch)

        elif format == PatchFormat.CONTEXT:
            patch = difflib.context_diff(
                current_lines,
                new_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                n=context_lines,
            )
            return "".join(patch)

        elif format == PatchFormat.GIT:
            if not self.git_enabled or not self.repo:
                raise ValueError("Git format patches require a Git repository")

            # Create temporary files for the diff
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp_new:
                temp_new.write(new_content)
                temp_new.flush()

                # Use Git's diff command for proper Git format
                cmd = [
                    "git",
                    "-C",
                    str(self.root_path),
                    "diff",
                    "--no-index",
                    f"--unified={context_lines}",
                    "--",
                    file_path,
                    temp_new.name,
                ]

                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, check=False
                    )
                    # Git diff returns exit code 1 when differences are found
                    patch = result.stdout

                    # Fix the paths in the patch to match Git conventions
                    patch = patch.replace(f"a/{file_path}", f"a/{file_path}")
                    patch = patch.replace(f"b/{temp_new.name}", f"b/{file_path}")

                    return patch
                except subprocess.SubprocessError as e:
                    raise RuntimeError(f"Failed to generate Git patch: {str(e)}") from e
        else:
            raise ValueError(f"Unsupported patch format: {format}")

    async def apply_patch(self, patch_content: str, strip: int = 1) -> bool:
        """Apply a patch to the local filesystem."""
        # Create a PatchSet from the patch content using BytesIO
        import io

        patch_set = PatchSet(io.BytesIO(patch_content.encode("utf-8")))

        # Apply the patch using the PatchSet's apply method
        try:
            success = patch_set.apply(strip=strip, root=str(self.root_path))
            if not success:
                self.logger.error("Failed to apply patch")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error applying patch: {e}")
            return False

    async def commit_changes(
        self, file_operations: List[FileOperation], options: CommitOptions
    ) -> str:
        """Apply changes to files and commit them if in a Git repository."""
        if not self.git_enabled and options.commit:
            raise ValueError("Cannot commit changes when Git is not enabled")

        # Apply all file operations
        for op in file_operations:
            if op.operation_type == "write":
                await self.write_file(
                    op.file_path, op.content or "", op.encoding or self.default_encoding
                )
            elif op.operation_type == "delete":
                file_path = self.root_path / op.file_path
                if file_path.exists():
                    file_path.unlink()
            elif op.operation_type == "rename":
                src_path = self.root_path / op.file_path
                if op.new_path:
                    dst_path = self.root_path / op.new_path
                    if src_path.exists():
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        src_path.rename(dst_path)
                else:
                    raise ValueError("new_path is required for rename operations")
            else:
                raise ValueError(f"Unsupported operation type: {op.operation_type}")

        # Commit changes if requested and Git is enabled
        if options.commit and self.git_enabled and self.repo:
            # Add all changes to staging
            if options.files_to_add:
                for file_path in options.files_to_add:
                    self.repo.git.add(file_path)
            else:
                self.repo.git.add(A=True)

            # Create the commit
            commit = self.repo.index.commit(
                message=options.commit_message,
                author=options.author,
                committer=options.committer,
            )

            return str(commit.hexsha)

        return ""

    async def apply_remediation(
        self, path: str, content: str, message: str, branch: Optional[str] = None
    ) -> RemediationResult:
        """Apply a remediation by writing content to a file."""
        try:
            # Write the content to the file
            await self.write_file(path, content)

            # If Git is enabled, commit the changes
            if self.git_enabled and self.repo:
                self.repo.git.add(path)
                commit = self.repo.index.commit(message)
                commit_sha = str(commit.hexsha)
            else:
                commit_sha = None

            return RemediationResult(
                success=True,
                message=f"Successfully applied remediation to {path}",
                file_path=path,
                operation_type="write",
                commit_sha=commit_sha,
            )
        except Exception as e:
            return RemediationResult(
                success=False,
                message=f"Failed to apply remediation to {path}: {str(e)}",
                file_path=path,
                operation_type="write",
                error_details=str(e),
            )

    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create a new branch in the Git repository."""
        if not self.git_enabled or not self.repo:
            raise ValueError("Branch operations require a Git repository")

        try:
            if base_ref:
                base = self.repo.branches[base_ref]
            else:
                base = self.repo.active_branch

            self.repo.create_head(name, base)
            return True
        except GitCommandError as e:
            self.logger.error(f"Failed to create branch: {str(e)}")
            return False

    async def delete_branch(self, name: str) -> bool:
        """Delete a branch in the Git repository."""
        if not self.git_enabled or not self.repo:
            raise ValueError("Branch operations require a Git repository")

        try:
            self.repo.delete_head(name)
            return True
        except GitCommandError as e:
            self.logger.error(f"Failed to delete branch: {str(e)}")
            return False

    async def list_branches(self) -> List[BranchInfo]:
        """List all branches in the repository."""
        if not self.git_enabled or not self.repo:
            return []

        try:
            branches = []
            for branch in self.repo.branches:
                # Get the latest commit for this branch
                latest_commit = branch.commit
                branches.append(
                    BranchInfo(
                        name=branch.name,
                        sha=latest_commit.hexsha,
                        is_protected=False,  # Local repos don't have protection rules
                        last_commit=latest_commit.committed_datetime,
                    )
                )
            return branches
        except Exception as e:
            self.logger.error(f"Failed to list branches: {str(e)}")
            return []

    async def get_current_branch(self) -> Optional[str]:
        """Get the name of the current branch if in a Git repository."""
        if not self.git_enabled or not self.repo:
            return None
        return self.repo.active_branch.name

    async def checkout_branch(self, branch_name: str) -> bool:
        """Checkout a branch in the Git repository."""
        if not self.git_enabled or not self.repo:
            raise ValueError("Branch operations require a Git repository")

        try:
            self.repo.git.checkout(branch_name)
            return True
        except GitCommandError as e:
            self.logger.error(f"Failed to checkout branch: {str(e)}")
            return False

    async def get_status(self) -> Dict[str, List[str]]:
        """Get the status of the Git repository."""
        if not self.git_enabled or not self.repo:
            return {
                "untracked": [],
                "modified": [],
                "added": [],
                "deleted": [],
                "renamed": [],
            }

        status = {
            "untracked": [],
            "modified": [],
            "added": [],
            "deleted": [],
            "renamed": [],
        }

        # Get the status from GitPython
        repo_status = self.repo.git.status(porcelain=True).splitlines()

        for line in repo_status:
            if not line:
                continue

            status_code = line[:2].strip()
            file_path = line[3:].strip()

            # Handle renamed files
            if status_code == "R":
                old_path, new_path = file_path.split(" -> ")
                status["renamed"].append(f"{old_path} -> {new_path}")
            elif status_code == "??":
                status["untracked"].append(file_path)
            elif status_code == "M" or status_code == "MM":
                status["modified"].append(file_path)
            elif status_code == "A":
                status["added"].append(file_path)
            elif status_code == "D":
                status["deleted"].append(file_path)

        return status

    async def execute_git_command(self, *args, **kwargs) -> Tuple[str, str]:
        """Execute a Git command on the local repository."""
        if not self.git_enabled or not self.repo:
            raise ValueError("Git commands require a Git repository")

        try:
            # Convert args to a list of strings
            cmd_args = [str(arg) for arg in args]

            # Execute the Git command
            result = self.repo.git.execute(
                cmd_args, with_stdout=True, with_stderr=True, **kwargs
            )

            # GitPython returns stdout as the result
            stdout = result
            stderr = ""

            return stdout, stderr
        except GitCommandError as e:
            return "", str(e)

    async def get_file_history(
        self, file_path: str, max_entries: int = 10
    ) -> List[CommitInfo]:
        """Get the commit history for a specific file."""
        if not self.git_enabled or not self.repo:
            return []

        try:
            commits = list(
                self.repo.iter_commits(paths=file_path, max_count=max_entries)
            )

            history = []
            for commit in commits:
                history.append(
                    CommitInfo(
                        sha=commit.hexsha,
                        message=commit.message.strip(),
                        author=f"{commit.author.name} <{commit.author.email}>",
                        author_email=commit.author.email,
                        committer=f"{commit.committer.name} <{commit.committer.email}>",
                        committer_email=commit.committer.email,
                        date=commit.committed_datetime,
                        parents=[p.hexsha for p in commit.parents],
                    )
                )

            return history
        except GitCommandError:
            return []

    async def diff_between_commits(
        self, file_path: str, old_commit: str, new_commit: str = "HEAD"
    ) -> str:
        """Get the diff for a file between two commits."""
        if not self.git_enabled or not self.repo:
            raise ValueError("Diff operations require a Git repository")

        try:
            diff = self.repo.git.diff(old_commit, new_commit, "--", file_path)
            return diff
        except GitCommandError as e:
            self.logger.error(f"Failed to get diff: {str(e)}")
            return ""

    async def check_conflicts(
        self, path: str, content: str, branch: Optional[str] = None
    ) -> bool:
        """Check for merge conflicts between two references."""
        if not self.git_enabled or not self.repo:
            return False

        try:
            # For local provider, we can't really check conflicts without more context
            # This is a simplified implementation
            return False
        except Exception:
            return False

    async def resolve_conflicts(
        self, path: str, content: str, strategy: str = "manual"
    ) -> bool:
        """Resolve merge conflicts between two references."""
        if not self.git_enabled or not self.repo:
            raise ValueError("Conflict resolution requires a Git repository")

        try:
            # For local provider, we can't really resolve conflicts without more context
            # This is a simplified implementation
            return True
        except Exception as e:
            self.logger.error(f"Failed to resolve conflicts: {str(e)}")
            return False

    async def create_pull_request(
        self, title: str, description: str, head_branch: str, base_branch: str, **kwargs
    ) -> RemediationResult:
        """Create a pull request (not applicable for local provider)."""
        raise NotImplementedError(
            "Pull requests are not supported for local repositories"
        )

    async def create_merge_request(
        self, title: str, description: str, head_branch: str, base_branch: str, **kwargs
    ) -> RemediationResult:
        """Create a merge request (not applicable for local provider)."""
        raise NotImplementedError(
            "Merge requests are not supported for local repositories"
        )

    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Execute multiple operations in batch."""
        results = []

        for operation in operations:
            try:
                if (
                    operation.operation_type == "write"
                    or operation.operation_type == "write_file"
                ):
                    await self.write_file(operation.file_path, operation.content or "")
                    results.append(
                        OperationResult(
                            operation_id=operation.operation_id,
                            success=True,
                            message=f"Successfully wrote to {operation.file_path}",
                            file_path=operation.file_path,
                        )
                    )
                elif operation.operation_type == "delete":
                    file_path = self.root_path / operation.file_path
                    if file_path.exists():
                        file_path.unlink()
                        results.append(
                            OperationResult(
                                operation_id=operation.operation_id,
                                success=True,
                                message=f"Successfully deleted {operation.file_path}",
                                file_path=operation.file_path,
                            )
                        )
                    else:
                        results.append(
                            OperationResult(
                                operation_id=operation.operation_id,
                                success=False,
                                message=f"File {operation.file_path} not found",
                                file_path=operation.file_path,
                            )
                        )
                else:
                    results.append(
                        OperationResult(
                            operation_id=operation.operation_id,
                            success=False,
                            message=f"Unsupported operation type: {operation.operation_type}",
                            file_path=operation.file_path,
                        )
                    )
            except Exception as e:
                results.append(
                    OperationResult(
                        operation_id=operation.operation_id,
                        success=False,
                        message=f"Operation failed: {str(e)}",
                        file_path=operation.file_path,
                        error_details=str(e),
                    )
                )

        return results

    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get information about a specific branch."""
        if not self.git_enabled or not self.repo:
            return None

        try:
            branch = self.repo.branches[name]
            latest_commit = branch.commit
            return BranchInfo(
                name=branch.name,
                sha=latest_commit.hexsha,
                is_protected=False,
                last_commit=latest_commit.committed_datetime,
            )
        except Exception:
            return None

    async def get_conflict_info(self, path: str) -> Optional[Any]:
        """Get detailed information about conflicts in a file."""
        # Local provider doesn't support conflict detection
        return None

    async def validate_credentials(self) -> bool:
        """Validate that the current credentials are valid."""
        # Local provider doesn't need credentials
        return True

    async def refresh_credentials(self) -> bool:
        """Refresh the credentials used for authentication."""
        # Local provider doesn't need credentials
        return True

    async def get_health_status(self) -> ProviderHealth:
        """Get the health status of the provider."""
        # Simple health check for local provider
        return ProviderHealth(status="healthy", message="Local provider is operational")

    async def get_capabilities(self) -> ProviderCapabilities:
        """Get the capabilities of this provider."""
        return ProviderCapabilities(
            supports_pull_requests=False,
            supports_merge_requests=False,
            supports_direct_commits=True,
            supports_patch_generation=True,
            supports_branch_operations=self.git_enabled,
            supports_file_history=self.git_enabled,
            supports_batch_operations=True,
            supported_patch_formats=[
                PatchFormat.UNIFIED,
                PatchFormat.CONTEXT,
                PatchFormat.GIT,
            ],
            supported_encodings=["utf-8", "ascii", "latin-1"],
        )
