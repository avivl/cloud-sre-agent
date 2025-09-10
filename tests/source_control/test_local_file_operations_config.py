# tests/source_control/test_local_file_operations_config.py

"""
Tests for Local file operations with configuration support.

This module tests the LocalFileOperations class with the new configuration
system to ensure proper error handling and configuration management.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from gemini_sre_agent.source_control.providers.local.local_file_operations import (
    LocalFileOperations,
)
from gemini_sre_agent.source_control.providers.sub_operation_config import (
    SubOperationConfig,
)


class TestLocalFileOperationsConfig:
    """Test LocalFileOperations with configuration support."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def default_config(self):
        """Create default configuration."""
        return SubOperationConfig(
            operation_name="file_operations",
            provider_type="local",
            file_operation_timeout=60.0,
            file_operation_retries=2,
            log_level="INFO",
        )

    @pytest.fixture
    def mock_error_handling_components(self):
        """Create mock error handling components."""
        resilient_manager = MagicMock()
        resilient_manager.execute_with_retry = AsyncMock()

        return {"resilient_manager": resilient_manager}

    @pytest.fixture
    def file_operations(
        self, temp_dir, mock_logger, mock_error_handling_components, default_config
    ):
        """Create LocalFileOperations instance for testing."""
        return LocalFileOperations(
            root_path=temp_dir,
            default_encoding="utf-8",
            backup_files=True,
            backup_directory=None,
            logger=mock_logger,
            error_handling_components=mock_error_handling_components,
            config=default_config,
        )

    def test_initialization_with_config(self, file_operations, default_config):
        """Test initialization with configuration."""
        assert file_operations.config == default_config
        assert file_operations.provider_type == "local"
        assert file_operations.operation_name == "file_operations"

    def test_initialization_without_config(self, temp_dir, mock_logger):
        """Test initialization without configuration (should create default)."""
        file_ops = LocalFileOperations(
            root_path=temp_dir,
            default_encoding="utf-8",
            backup_files=True,
            backup_directory=None,
            logger=mock_logger,
        )

        assert file_ops.config is not None
        assert file_ops.config.operation_name == "file_operations"
        assert file_ops.config.provider_type == "local"

    @pytest.mark.asyncio
    async def test_get_file_content_with_config(self, file_operations, temp_dir):
        """Test get_file_content with configuration support."""
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content, encoding="utf-8")

        # Mock the resilient manager to return the actual result
        async def mock_execute_with_retry(operation_name, func, *args, **kwargs):
            return await func(*args, **kwargs)

        file_operations.error_handling_components[
            "resilient_manager"
        ].execute_with_retry = mock_execute_with_retry

        result = await file_operations.get_file_content("test.txt")

        assert result == test_content

    @pytest.mark.asyncio
    async def test_apply_remediation_with_config(self, file_operations, temp_dir):
        """Test apply_remediation with configuration support."""
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Original content", encoding="utf-8")

        # Mock the resilient manager
        async def mock_execute_with_retry(operation_name, func, *args, **kwargs):
            return await func(*args, **kwargs)

        file_operations.error_handling_components[
            "resilient_manager"
        ].execute_with_retry = mock_execute_with_retry

        result = await file_operations.apply_remediation(
            "test.txt", "Updated content", "Test commit"
        )

        assert result.success is True
        assert "Applied remediation to test.txt" in result.message

    @pytest.mark.asyncio
    async def test_file_exists_with_config(self, file_operations, temp_dir):
        """Test file_exists with configuration support."""
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content", encoding="utf-8")

        # Mock the resilient manager
        async def mock_execute_with_retry(operation_name, func, *args, **kwargs):
            return await func(*args, **kwargs)

        file_operations.error_handling_components[
            "resilient_manager"
        ].execute_with_retry = mock_execute_with_retry

        # Test existing file
        assert await file_operations.file_exists("test.txt") is True

        # Test non-existing file
        assert await file_operations.file_exists("nonexistent.txt") is False

    @pytest.mark.asyncio
    async def test_get_file_info_with_config(self, file_operations, temp_dir):
        """Test get_file_info with configuration support."""
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_content = "Test content"
        test_file.write_text(test_content, encoding="utf-8")

        # Mock the resilient manager
        async def mock_execute_with_retry(operation_name, func, *args, **kwargs):
            return await func(*args, **kwargs)

        file_operations.error_handling_components[
            "resilient_manager"
        ].execute_with_retry = mock_execute_with_retry

        file_info = await file_operations.get_file_info("test.txt")

        assert file_info.path == "test.txt"
        assert file_info.size == len(test_content.encode("utf-8"))
        assert file_info.is_binary is False

    @pytest.mark.asyncio
    async def test_list_files_with_config(self, file_operations, temp_dir):
        """Test list_files with configuration support."""
        # Create test files
        (temp_dir / "file1.txt").write_text("Content 1", encoding="utf-8")
        (temp_dir / "file2.txt").write_text("Content 2", encoding="utf-8")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "file3.txt").write_text("Content 3", encoding="utf-8")

        # Mock the resilient manager
        async def mock_execute_with_retry(operation_name, func, *args, **kwargs):
            return await func(*args, **kwargs)

        file_operations.error_handling_components[
            "resilient_manager"
        ].execute_with_retry = mock_execute_with_retry

        files = await file_operations.list_files()

        assert len(files) == 2  # Only files in root directory
        file_names = [f.path for f in files]
        assert "file1.txt" in file_names
        assert "file2.txt" in file_names

    @pytest.mark.asyncio
    async def test_generate_patch_with_config(self, file_operations):
        """Test generate_patch with configuration support."""
        original = "Line 1\nLine 2\nLine 3"
        modified = "Line 1\nModified Line 2\nLine 3"

        # Mock the resilient manager
        async def mock_execute_with_retry(operation_name, func, *args, **kwargs):
            return await func(*args, **kwargs)

        file_operations.error_handling_components[
            "resilient_manager"
        ].execute_with_retry = mock_execute_with_retry

        patch_result = await file_operations.generate_patch(original, modified)

        assert "Line 2" in patch_result
        assert "Modified Line 2" in patch_result
        assert "Line 1" in patch_result

    @pytest.mark.asyncio
    async def test_apply_patch_with_config(self, file_operations, temp_dir):
        """Test apply_patch with configuration support."""
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Original content", encoding="utf-8")

        # Mock the resilient manager
        async def mock_execute_with_retry(operation_name, func, *args, **kwargs):
            return await func(*args, **kwargs)

        file_operations.error_handling_components[
            "resilient_manager"
        ].execute_with_retry = mock_execute_with_retry

        patch_content = "--- original\n+++ modified\n@@ -1,1 +1,1 @@\n-Original content\n+Modified content"
        result = await file_operations.apply_patch(patch_content, "test.txt")

        assert result is True

    @pytest.mark.asyncio
    async def test_commit_changes_with_config(self, file_operations, temp_dir):
        """Test commit_changes with configuration support."""

        # Mock the resilient manager
        async def mock_execute_with_retry(operation_name, func, *args, **kwargs):
            return await func(*args, **kwargs)

        file_operations.error_handling_components[
            "resilient_manager"
        ].execute_with_retry = mock_execute_with_retry

        result = await file_operations.commit_changes(
            "test.txt", "New content", "Test commit message"
        )

        assert result is True

        # Verify file was created
        test_file = temp_dir / "test.txt"
        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == "New content"

    @pytest.mark.asyncio
    async def test_health_check_with_config(self, file_operations, temp_dir):
        """Test health_check with configuration support."""

        # Mock the resilient manager
        async def mock_execute_with_retry(operation_name, func, *args, **kwargs):
            return await func(*args, **kwargs)

        file_operations.error_handling_components[
            "resilient_manager"
        ].execute_with_retry = mock_execute_with_retry

        result = await file_operations.health_check()

        assert result is True

    def test_performance_stats(self, file_operations):
        """Test performance statistics tracking."""
        # Simulate some operations
        file_operations._operation_count = 5
        file_operations._error_count = 1
        file_operations._total_duration = 2.5

        stats = file_operations.get_performance_stats()

        assert stats["operation_name"] == "file_operations"
        assert stats["provider_type"] == "local"
        assert stats["total_operations"] == 5
        assert stats["error_count"] == 1
        assert stats["error_rate"] == 0.2
        assert stats["average_duration"] == 0.5

    def test_config_update(self, file_operations):
        """Test configuration update."""
        new_config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="local",
            file_operation_timeout=90.0,
            log_level="DEBUG",
        )

        file_operations.update_config(new_config)

        assert file_operations.config == new_config
        assert file_operations.config.file_operation_timeout == 90.0
        assert file_operations.config.log_level == "DEBUG"

    def test_health_status(self, file_operations):
        """Test health status reporting."""
        health_status = file_operations.get_health_status()

        assert "healthy" in health_status
        assert health_status["operation_name"] == "file_operations"
        assert health_status["provider_type"] == "local"
        assert "performance_stats" in health_status
        assert "config" in health_status

    @pytest.mark.asyncio
    async def test_error_handling_disabled(self, temp_dir, mock_logger):
        """Test behavior when error handling is disabled."""
        config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="local",
            error_handling_enabled=False,
        )

        file_ops = LocalFileOperations(
            root_path=temp_dir,
            default_encoding="utf-8",
            backup_files=True,
            backup_directory=None,
            logger=mock_logger,
            config=config,
        )

        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content", encoding="utf-8")

        # Should work without error handling components
        result = await file_ops.get_file_content("test.txt")
        assert result == "Test content"

    @pytest.mark.asyncio
    async def test_operation_type_specific_timeouts(self, temp_dir, mock_logger):
        """Test that operation types use correct timeouts."""
        config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="local",
            file_operation_timeout=0.1,  # Very short timeout
            file_operation_retries=1,
        )

        file_ops = LocalFileOperations(
            root_path=temp_dir,
            default_encoding="utf-8",
            backup_files=True,
            backup_directory=None,
            logger=mock_logger,
            config=config,
        )

        # Mock a slow operation
        async def slow_operation():
            await asyncio.sleep(0.2)  # Longer than timeout
            return "slow_result"

        with pytest.raises(asyncio.TimeoutError):
            await file_ops._execute_with_error_handling(
                "slow_operation", slow_operation, "file"
            )
