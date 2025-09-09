"""Simple tests for the Local Provider implementation."""

import shutil
import tempfile
from pathlib import Path

import git
import pytest

from gemini_sre_agent.config.source_control_repositories import LocalRepositoryConfig
from gemini_sre_agent.source_control.models import (
    BatchOperation,
    CommitOptions,
    FileInfo,
    FileOperation,
    PatchFormat,
    ProviderCapabilities,
    ProviderHealth,
    RepositoryInfo,
)
from gemini_sre_agent.source_control.providers.local_provider import LocalProvider


class TestLocalProviderSimple:
    """Simple tests for LocalProvider."""

    @pytest.mark.asyncio
    async def test_basic_functionality(self):
        """Test basic functionality of LocalProvider."""
        temp_dir = tempfile.mkdtemp()
        try:
            config = LocalRepositoryConfig(
                name="test-local", path=temp_dir, git_enabled=False
            )

            async with LocalProvider(config.model_dump()) as provider:
                # Test connection
                assert await provider.test_connection() is True

                # Test repository info
                info = await provider.get_repository_info()
                assert isinstance(info, RepositoryInfo)
                assert info.name == "test-local"

                # Test file operations
                await provider.write_file("test.txt", "Hello, world!")
                assert await provider.file_exists("test.txt") is True

                content = await provider.get_file_content("test.txt")
                assert content == "Hello, world!"

                # Test file info
                file_info = await provider.get_file_info("test.txt")
                assert isinstance(file_info, FileInfo)
                assert file_info.path == "test.txt"

                # Test list files
                files = await provider.list_files()
                assert "test.txt" in files

                # Test capabilities
                capabilities = await provider.get_capabilities()
                assert isinstance(capabilities, ProviderCapabilities)
                assert capabilities.supports_direct_commits is True

                # Test health status
                health = await provider.get_health_status()
                assert isinstance(health, ProviderHealth)
                assert health.status == "healthy"

        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_git_functionality(self):
        """Test Git functionality of LocalProvider."""
        temp_dir = tempfile.mkdtemp()
        try:
            # Initialize Git repository
            repo = git.Repo.init(temp_dir)
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("Initial content")
            repo.git.add(A=True)
            repo.git.commit(m="Initial commit")

            config = LocalRepositoryConfig(
                name="test-git", path=temp_dir, git_enabled=True
            )

            async with LocalProvider(config.model_dump()) as provider:
                # Test Git operations
                current_branch = await provider.get_current_branch()
                assert current_branch == "main"

                # Test branch operations
                success = await provider.create_branch("test-branch")
                assert success is True

                success = await provider.checkout_branch("test-branch")
                assert success is True

                # Test commit operations
                file_ops = [
                    FileOperation(
                        operation_type="write",
                        file_path="new_file.txt",
                        content="New file content",
                    )
                ]
                options = CommitOptions(commit=True, commit_message="Test commit")

                commit_id = await provider.commit_changes(file_ops, options)
                assert len(commit_id) == 40  # Git SHA length

                # Test file history
                history = await provider.get_file_history("new_file.txt")
                assert len(history) == 1
                assert history[0].message == "Test commit"

        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_patch_generation(self):
        """Test patch generation functionality."""
        temp_dir = tempfile.mkdtemp()
        try:
            config = LocalRepositoryConfig(
                name="test-patch", path=temp_dir, git_enabled=False
            )

            async with LocalProvider(config.model_dump()) as provider:
                # Create initial file
                original_content = "Line 1\nLine 2\nLine 3\n"
                await provider.write_file("test.txt", original_content)

                # Generate patch
                new_content = "Line 1\nModified Line 2\nLine 3\n"
                patch = await provider.generate_patch(
                    "test.txt", new_content, format=PatchFormat.UNIFIED
                )

                assert "--- a/test.txt" in patch
                assert "+++ b/test.txt" in patch
                assert "-Line 2" in patch
                assert "+Modified Line 2" in patch

                # Apply patch
                success = await provider.apply_patch(patch)
                assert success is True

                # Verify content
                updated_content = await provider.get_file_content("test.txt")
                assert updated_content == new_content

        finally:
            shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_batch_operations(self):
        """Test batch operations functionality."""
        temp_dir = tempfile.mkdtemp()
        try:
            config = LocalRepositoryConfig(
                name="test-batch", path=temp_dir, git_enabled=False
            )

            async with LocalProvider(config.model_dump()) as provider:
                # Test batch operations
                operations = [
                    BatchOperation(
                        operation_id="op1",
                        operation_type="write_file",
                        file_path="file1.txt",
                        content="Content 1",
                    ),
                    BatchOperation(
                        operation_id="op2",
                        operation_type="write_file",
                        file_path="file2.txt",
                        content="Content 2",
                    ),
                ]

                results = await provider.batch_operations(operations)
                assert len(results) == 2
                assert all(r.success for r in results)

                # Verify files were created
                assert await provider.file_exists("file1.txt")
                assert await provider.file_exists("file2.txt")

        finally:
            shutil.rmtree(temp_dir)
