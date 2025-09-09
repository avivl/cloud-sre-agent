"""Tests for the Local Provider implementation."""

import shutil
import tempfile
from pathlib import Path

import git
import pytest

from gemini_sre_agent.config.source_control_repositories import LocalRepositoryConfig
from gemini_sre_agent.source_control.models import (
    BatchOperation,
    CommitOptions,
    FileOperation,
    PatchFormat,
)
from gemini_sre_agent.source_control.providers.local_provider import LocalProvider


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def git_temp_dir():
    """Create a temporary Git repository for testing."""
    temp_dir = tempfile.mkdtemp()
    repo = git.Repo.init(temp_dir)

    # Create a test file and commit it
    test_file = Path(temp_dir) / "test.txt"
    test_file.write_text("Initial content")

    repo.git.add(A=True)
    repo.git.commit(m="Initial commit")

    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def local_provider_factory(temp_dir):
    """Create a LocalProvider factory for a non-Git directory."""

    def _create_provider():
        config = LocalRepositoryConfig(
            name="test-local-repo", path=temp_dir, git_enabled=False
        )
        return LocalProvider(config.model_dump())

    return _create_provider


@pytest.fixture
def git_provider_factory(git_temp_dir):
    """Create a LocalProvider factory for a Git directory."""

    def _create_provider():
        config = LocalRepositoryConfig(
            name="test-git-repo", path=git_temp_dir, git_enabled=True
        )
        return LocalProvider(config.model_dump())

    return _create_provider


class TestLocalProviderBasic:
    """Test basic functionality of LocalProvider."""

    @pytest.mark.asyncio
    async def test_test_connection(self, local_provider_factory):
        """Test connection to local directory."""
        async with local_provider_factory() as provider:
            assert await provider.test_connection() is True

    @pytest.mark.asyncio
    async def test_init_with_nonexistent_path(self):
        """Test initialization with non-existent path."""
        # This should raise a validation error due to path validation
        with pytest.raises(ValueError, match="Local repository path does not exist"):
            LocalRepositoryConfig(
                name="nonexistent-repo", path="/nonexistent/path", git_enabled=False
            )

    @pytest.mark.asyncio
    async def test_get_repository_info(self, local_provider):
        """Test getting repository information."""
        info = await local_provider.get_repository_info()
        assert info.name == "test-local-repo"
        assert info.is_private is True
        assert "path" in info.additional_info
        assert info.additional_info["git_enabled"] is False

    @pytest.mark.asyncio
    async def test_get_repository_info_git(self, git_provider):
        """Test getting repository information for Git repo."""
        info = await git_provider.get_repository_info()
        assert info.name == "test-git-repo"
        assert info.is_private is True
        assert info.additional_info["git_enabled"] is True
        assert info.additional_info["is_git_repo"] is True


class TestLocalProviderFileOperations:
    """Test file operations of LocalProvider."""

    @pytest.mark.asyncio
    async def test_read_write_file(self, local_provider, temp_dir):
        """Test reading and writing files."""
        # Test writing a file
        test_content = "Hello, world!"
        await local_provider.write_file("test.txt", test_content)

        # Verify the file exists
        assert Path(temp_dir, "test.txt").exists()

        # Test reading the file
        read_content = await local_provider.get_file_content("test.txt")
        assert read_content == test_content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, local_provider):
        """Test reading a non-existent file."""
        with pytest.raises(FileNotFoundError):
            await local_provider.get_file_content("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_write_file_with_encoding(self, local_provider, temp_dir):
        """Test writing a file with specific encoding."""
        # Test writing a file with specific encoding
        test_content = "こんにちは世界"  # Hello world in Japanese
        await local_provider.write_file("japanese.txt", test_content, encoding="utf-8")

        # Verify the file exists
        assert Path(temp_dir, "japanese.txt").exists()

        # Test reading with auto-detection
        read_content = await local_provider.get_file_content("japanese.txt")
        assert read_content == test_content

    @pytest.mark.asyncio
    async def test_file_exists(self, local_provider, temp_dir):
        """Test file existence checking."""
        # Create a file
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("test content")

        # Test file exists
        assert await local_provider.file_exists("test.txt") is True
        assert await local_provider.file_exists("nonexistent.txt") is False

    @pytest.mark.asyncio
    async def test_get_file_info(self, local_provider, temp_dir):
        """Test getting file information."""
        # Create a file
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("test content")

        # Get file info
        file_info = await local_provider.get_file_info("test.txt")
        assert file_info.path == "test.txt"
        assert file_info.size > 0
        assert file_info.is_binary is False
        assert file_info.encoding is not None

    @pytest.mark.asyncio
    async def test_get_file_info_nonexistent(self, local_provider):
        """Test getting file info for non-existent file."""
        with pytest.raises(FileNotFoundError):
            await local_provider.get_file_info("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_get_file_info_directory(self, local_provider, temp_dir):
        """Test getting file info for directory."""
        # Create a directory
        test_dir = Path(temp_dir) / "test_dir"
        test_dir.mkdir()

        with pytest.raises(ValueError, match="is a directory, not a file"):
            await local_provider.get_file_info("test_dir")

    @pytest.mark.asyncio
    async def test_list_files(self, local_provider, temp_dir):
        """Test listing files in directory."""
        # Create multiple files
        await local_provider.write_file("file1.txt", "Content 1")
        await local_provider.write_file("file2.txt", "Content 2")
        await local_provider.write_file("subdir/file3.txt", "Content 3")

        # List all files
        files = await local_provider.list_files()
        assert len(files) == 3
        assert "file1.txt" in files
        assert "file2.txt" in files
        assert "subdir/file3.txt" in files

        # List files with pattern
        txt_files = await local_provider.list_files(pattern=r"\.txt$")
        assert len(txt_files) == 3

        # List files in subdirectory
        subdir_files = await local_provider.list_files(directory="subdir")
        assert len(subdir_files) == 1
        assert "subdir/file3.txt" in subdir_files

    @pytest.mark.asyncio
    async def test_list_files_nonexistent_directory(self, local_provider):
        """Test listing files in non-existent directory."""
        with pytest.raises(FileNotFoundError):
            await local_provider.list_files(directory="nonexistent")


class TestLocalProviderPatchGeneration:
    """Test patch generation functionality."""

    @pytest.mark.asyncio
    async def test_unified_patch_generation(self, local_provider, temp_dir):
        """Test unified patch generation."""
        # Create a file
        original_content = "Line 1\nLine 2\nLine 3\n"
        await local_provider.write_file("test.txt", original_content)

        # Generate a patch
        new_content = "Line 1\nModified Line 2\nLine 3\n"
        patch_content = await local_provider.generate_patch(
            "test.txt", new_content, format=PatchFormat.UNIFIED
        )

        # Verify patch format
        assert "--- a/test.txt" in patch_content
        assert "+++ b/test.txt" in patch_content
        assert "-Line 2" in patch_content
        assert "+Modified Line 2" in patch_content

    @pytest.mark.asyncio
    async def test_context_patch_generation(self, local_provider, temp_dir):
        """Test context patch generation."""
        # Create a file
        original_content = "Line 1\nLine 2\nLine 3\n"
        await local_provider.write_file("test.txt", original_content)

        # Generate a patch
        new_content = "Line 1\nModified Line 2\nLine 3\n"
        patch_content = await local_provider.generate_patch(
            "test.txt", new_content, format=PatchFormat.CONTEXT
        )

        # Verify patch format
        assert "*** a/test.txt" in patch_content
        assert "--- b/test.txt" in patch_content
        assert "! Line 2" in patch_content
        assert "! Modified Line 2" in patch_content

    @pytest.mark.asyncio
    async def test_git_patch_generation(self, git_provider, git_temp_dir):
        """Test Git patch generation."""
        # Create a file
        original_content = "Line 1\nLine 2\nLine 3\n"
        await git_provider.write_file("test.txt", original_content)

        # Generate a patch
        new_content = "Line 1\nModified Line 2\nLine 3\n"
        patch_content = await git_provider.generate_patch(
            "test.txt", new_content, format=PatchFormat.GIT
        )

        # Verify patch format
        assert "diff --git" in patch_content
        assert "--- a/test.txt" in patch_content
        assert "+++ b/test.txt" in patch_content
        assert "-Line 2" in patch_content
        assert "+Modified Line 2" in patch_content

    @pytest.mark.asyncio
    async def test_git_patch_generation_non_git(self, local_provider):
        """Test Git patch generation in non-Git directory."""
        with pytest.raises(
            ValueError, match="Git format patches require a Git repository"
        ):
            await local_provider.generate_patch(
                "test.txt", "content", format=PatchFormat.GIT
            )

    @pytest.mark.asyncio
    async def test_apply_patch(self, local_provider, temp_dir):
        """Test applying a patch."""
        # Create a file
        original_content = "Line 1\nLine 2\nLine 3\n"
        await local_provider.write_file("test.txt", original_content)

        # Generate a patch
        new_content = "Line 1\nModified Line 2\nLine 3\n"
        patch_content = await local_provider.generate_patch("test.txt", new_content)

        # Apply the patch
        success = await local_provider.apply_patch(patch_content)
        assert success is True

        # Verify the file was updated
        updated_content = await local_provider.get_file_content("test.txt")
        assert updated_content == new_content

    @pytest.mark.asyncio
    async def test_patch_for_new_file(self, local_provider, temp_dir):
        """Test patch generation for a new file."""
        # Generate a patch for a non-existent file
        new_content = "New file content\n"
        patch_content = await local_provider.generate_patch("new_file.txt", new_content)

        # Apply the patch
        success = await local_provider.apply_patch(patch_content)
        assert success is True

        # Verify the file was created
        assert await local_provider.file_exists("new_file.txt")
        content = await local_provider.get_file_content("new_file.txt")
        assert content == new_content


class TestLocalProviderGitIntegration:
    """Test Git integration functionality."""

    @pytest.mark.asyncio
    async def test_commit_changes(self, git_provider, git_temp_dir):
        """Test committing changes."""
        # Create file operations
        file_ops = [
            FileOperation(
                operation_type="write",
                file_path="new_file.txt",
                content="New file content",
            ),
            FileOperation(
                operation_type="write", file_path="test.txt", content="Updated content"
            ),
        ]

        # Commit options
        options = CommitOptions(commit=True, commit_message="Test commit")

        # Commit changes
        commit_id = await git_provider.commit_changes(file_ops, options)

        # Verify commit was created
        assert len(commit_id) == 40  # SHA-1 hash length

        # Verify files were updated
        assert await git_provider.get_file_content("new_file.txt") == "New file content"
        assert await git_provider.get_file_content("test.txt") == "Updated content"

    @pytest.mark.asyncio
    async def test_commit_changes_without_git(self, local_provider):
        """Test committing changes without Git enabled."""
        file_ops = [
            FileOperation(
                operation_type="write", file_path="test.txt", content="content"
            )
        ]
        options = CommitOptions(commit=True, commit_message="Test commit")

        with pytest.raises(
            ValueError, match="Cannot commit changes when Git is not enabled"
        ):
            await local_provider.commit_changes(file_ops, options)

    @pytest.mark.asyncio
    async def test_apply_remediation(self, git_provider, git_temp_dir):
        """Test applying remediation."""
        result = await git_provider.apply_remediation(
            "test.txt", "New content", "Fix issue"
        )

        assert result.success is True
        assert result.file_path == "test.txt"
        assert result.commit_sha is not None
        assert await git_provider.get_file_content("test.txt") == "New content"

    @pytest.mark.asyncio
    async def test_branch_operations(self, git_provider):
        """Test branch operations."""
        # Get current branch
        current_branch = await git_provider.get_current_branch()
        assert current_branch == "main"

        # Create a new branch
        success = await git_provider.create_branch("test-branch")
        assert success is True

        # Checkout the new branch
        success = await git_provider.checkout_branch("test-branch")
        assert success is True

        # Verify current branch changed
        current_branch = await git_provider.get_current_branch()
        assert current_branch == "test-branch"

    @pytest.mark.asyncio
    async def test_branch_operations_non_git(self, local_provider):
        """Test branch operations in non-Git directory."""
        with pytest.raises(
            ValueError, match="Branch operations require a Git repository"
        ):
            await local_provider.create_branch("test-branch")

    @pytest.mark.asyncio
    async def test_list_branches(self, git_provider):
        """Test listing branches."""
        branches = await git_provider.list_branches()
        assert len(branches) >= 1
        branch_names = [b.name for b in branches]
        assert "main" in branch_names

    @pytest.mark.asyncio
    async def test_git_status(self, git_provider, git_temp_dir):
        """Test getting Git status."""
        # Create an untracked file
        Path(git_temp_dir, "untracked.txt").write_text("Untracked content")

        # Modify an existing file
        await git_provider.write_file("test.txt", "Modified content")

        # Get status
        status = await git_provider.get_status()

        # Verify status
        assert "untracked.txt" in status["untracked"]
        assert "test.txt" in status["modified"]

    @pytest.mark.asyncio
    async def test_execute_git_command(self, git_provider):
        """Test executing Git commands."""
        # Execute a simple Git command
        stdout, stderr = await git_provider.execute_git_command(
            "rev-parse", "--abbrev-ref", "HEAD"
        )

        # Verify command output
        assert stdout.strip() == "main"
        assert stderr == ""

    @pytest.mark.asyncio
    async def test_execute_git_command_non_git(self, local_provider):
        """Test executing Git commands in non-Git directory."""
        with pytest.raises(ValueError, match="Git commands require a Git repository"):
            await local_provider.execute_git_command("status")

    @pytest.mark.asyncio
    async def test_get_file_history(self, git_provider, git_temp_dir):
        """Test getting file history."""
        # Make a commit to the test file
        await git_provider.write_file("test.txt", "Updated content")
        await git_provider.commit_changes(
            [
                FileOperation(
                    operation_type="write",
                    file_path="test.txt",
                    content="Updated content",
                )
            ],
            CommitOptions(commit=True, commit_message="Update test file"),
        )

        # Get file history
        history = await git_provider.get_file_history("test.txt")
        assert len(history) >= 1
        assert history[0].message == "Update test file"

    @pytest.mark.asyncio
    async def test_diff_between_commits(self, git_provider, git_temp_dir):
        """Test getting diff between commits."""
        # Make a commit
        await git_provider.write_file("test.txt", "Updated content")
        await git_provider.commit_changes(
            [
                FileOperation(
                    operation_type="write",
                    file_path="test.txt",
                    content="Updated content",
                )
            ],
            CommitOptions(commit=True, commit_message="Update test file"),
        )

        # Get diff
        diff = await git_provider.diff_between_commits("test.txt", "HEAD~1", "HEAD")
        assert "Updated content" in diff

    @pytest.mark.asyncio
    async def test_diff_between_commits_non_git(self, local_provider):
        """Test getting diff in non-Git directory."""
        with pytest.raises(
            ValueError, match="Diff operations require a Git repository"
        ):
            await local_provider.diff_between_commits("test.txt", "HEAD~1", "HEAD")


class TestLocalProviderBatchOperations:
    """Test batch operations functionality."""

    @pytest.mark.asyncio
    async def test_batch_operations(self, local_provider, temp_dir):
        """Test batch operations."""
        operations = [
            BatchOperation(
                operation_id="op1",
                operation_type="write",
                file_path="file1.txt",
                content="Content 1",
            ),
            BatchOperation(
                operation_id="op2",
                operation_type="write",
                file_path="file2.txt",
                content="Content 2",
            ),
        ]

        results = await local_provider.batch_operations(operations)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].file_path == "file1.txt"
        assert results[1].file_path == "file2.txt"

        # Verify files were created
        assert await local_provider.file_exists("file1.txt")
        assert await local_provider.file_exists("file2.txt")

    @pytest.mark.asyncio
    async def test_batch_operations_with_errors(self, local_provider):
        """Test batch operations with errors."""
        operations = [
            BatchOperation(
                operation_id="op1",
                operation_type="invalid",
                file_path="file1.txt",
                content="Content 1",
            )
        ]

        results = await local_provider.batch_operations(operations)

        assert len(results) == 1
        assert results[0].success is False
        assert "Unsupported operation type" in results[0].message


class TestLocalProviderCapabilities:
    """Test provider capabilities."""

    @pytest.mark.asyncio
    async def test_get_capabilities(self, local_provider):
        """Test getting provider capabilities."""
        capabilities = await local_provider.get_capabilities()

        assert capabilities.supports_direct_commits is True
        assert capabilities.supports_patch_generation is True
        assert capabilities.supports_batch_operations is True
        assert capabilities.supports_pull_requests is False
        assert capabilities.supports_merge_requests is False

    @pytest.mark.asyncio
    async def test_get_capabilities_git(self, git_provider):
        """Test getting capabilities for Git-enabled provider."""
        capabilities = await git_provider.get_capabilities()

        assert capabilities.supports_branch_operations is True
        assert capabilities.supports_file_history is True


class TestLocalProviderErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_error_handling_invalid_operation_type(self, git_provider):
        """Test error handling for invalid operation type."""
        file_ops = [
            FileOperation(
                operation_type="invalid", file_path="test.txt", content="Test content"
            )
        ]

        options = CommitOptions(commit=True, commit_message="Test commit")

        with pytest.raises(ValueError, match="Unsupported operation type"):
            await git_provider.commit_changes(file_ops, options)

    @pytest.mark.asyncio
    async def test_error_handling_invalid_patch_format(self, local_provider):
        """Test error handling for invalid patch format."""
        with pytest.raises(ValueError, match="Unsupported patch format"):
            await local_provider.generate_patch("test.txt", "content", format="invalid")

    @pytest.mark.asyncio
    async def test_error_handling_apply_patch_invalid(self, local_provider):
        """Test error handling for invalid patch application."""
        invalid_patch = "This is not a valid patch format"
        with pytest.raises((ValueError, TypeError)):  # patch-ng will raise an exception
            await local_provider.apply_patch(invalid_patch)
