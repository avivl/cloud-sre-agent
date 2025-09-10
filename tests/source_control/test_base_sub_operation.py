# tests/source_control/test_base_sub_operation.py

"""
Tests for base sub-operation class.

This module tests the BaseSubOperation class to ensure proper error handling,
configuration management, and performance tracking for sub-operation modules.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_sre_agent.source_control.providers.base_sub_operation import BaseSubOperation
from gemini_sre_agent.source_control.providers.sub_operation_config import SubOperationConfig


class MockSubOperation(BaseSubOperation):
    """Test implementation of BaseSubOperation for testing."""

    def __init__(self, logger, error_handling_components=None, config=None):
        super().__init__(
            logger=logger,
            error_handling_components=error_handling_components,
            config=config,
            provider_type="test",
            operation_name="test_operations"
        )
        self.test_data = []

    async def health_check(self) -> bool:
        """Test health check implementation."""
        return len(self.test_data) >= 0  # Always healthy for testing

    async def test_operation(self, value: str) -> str:
        """Test operation for testing purposes."""
        async def _test():
            self.test_data.append(value)
            return f"processed_{value}"

        return await self._execute_with_error_handling("test_operation", _test, "file")


class TestBaseSubOperation:
    """Test the BaseSubOperation class."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock(spec=logging.Logger)

    @pytest.fixture
    def test_config(self):
        """Create a test configuration."""
        return SubOperationConfig(
            operation_name="test_operations",
            provider_type="test",
            file_operation_timeout=30.0,
            file_operation_retries=2,
            log_level="INFO"
        )

    @pytest.fixture
    def mock_error_handling_components(self):
        """Create mock error handling components."""
        resilient_manager = MagicMock()
        async def mock_execute_with_retry(operation_name, func, *args, **kwargs):
            return await func(*args, **kwargs)
        resilient_manager.execute_with_retry = AsyncMock(side_effect=mock_execute_with_retry)
        
        return {
            "resilient_manager": resilient_manager
        }

    @pytest.fixture
    def sub_operation(self, mock_logger, mock_error_handling_components, test_config):
        """Create a test sub-operation instance."""
        return MockSubOperation(
            logger=mock_logger,
            error_handling_components=mock_error_handling_components,
            config=test_config
        )

    def test_initialization(self, mock_logger, test_config):
        """Test sub-operation initialization."""
        sub_op = MockSubOperation(
            logger=mock_logger,
            config=test_config
        )
        
        assert sub_op.logger == mock_logger
        assert sub_op.config == test_config
        assert sub_op.provider_type == "test"
        assert sub_op.operation_name == "test_operations"
        assert sub_op._operation_count == 0
        assert sub_op._error_count == 0

    def test_initialization_with_default_config(self, mock_logger):
        """Test initialization with default configuration."""
        sub_op = MockSubOperation(logger=mock_logger)
        
        assert sub_op.config is not None
        assert sub_op.config.operation_name == "test_operations"
        assert sub_op.config.provider_type == "test"

    @pytest.mark.asyncio
    async def test_execute_with_error_handling_success(self, sub_operation):
        """Test successful execution with error handling."""
        result = await sub_operation.test_operation("test_value")
        
        assert result == "processed_test_value"
        assert "test_value" in sub_operation.test_data
        assert sub_operation._operation_count == 1
        assert sub_operation._error_count == 0

    @pytest.mark.asyncio
    async def test_execute_with_error_handling_disabled(self, mock_logger, test_config):
        """Test execution with error handling disabled."""
        test_config.error_handling_enabled = False
        sub_op = MockSubOperation(
            logger=mock_logger,
            config=test_config
        )
        
        result = await sub_op.test_operation("test_value")
        
        assert result == "processed_test_value"
        assert "test_value" in sub_op.test_data

    @pytest.mark.asyncio
    async def test_execute_with_error_handling_timeout(self, mock_logger, test_config):
        """Test execution with timeout error."""
        test_config.file_operation_timeout = 0.1  # Very short timeout
        
        sub_op = MockSubOperation(
            logger=mock_logger,
            config=test_config
        )
        
        # Mock a slow operation
        async def slow_operation():
            await asyncio.sleep(0.2)  # Longer than timeout
            return "slow_result"
        
        with pytest.raises(asyncio.TimeoutError):
            await sub_op._execute_with_error_handling("slow_operation", slow_operation, "file")
        
        assert sub_op._error_count == 1

    @pytest.mark.asyncio
    async def test_execute_with_error_handling_exception(self, mock_logger, test_config):
        """Test execution with exception handling."""
        sub_op = MockSubOperation(
            logger=mock_logger,
            config=test_config
        )
        
        # Mock an operation that raises an exception
        async def failing_operation():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            await sub_op._execute_with_error_handling("failing_operation", failing_operation, "file")
        
        assert sub_op._error_count == 1

    @pytest.mark.asyncio
    async def test_execute_with_resilient_manager(self, mock_logger, mock_error_handling_components, test_config):
        """Test execution with resilient manager."""
        sub_op = MockSubOperation(
            logger=mock_logger,
            error_handling_components=mock_error_handling_components,
            config=test_config
        )
        
        result = await sub_op.test_operation("test_value")
        
        assert result == "processed_test_value"  # From actual function execution
        mock_error_handling_components["resilient_manager"].execute_with_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_custom_retry_config(self, mock_logger, mock_error_handling_components, test_config):
        """Test execution with custom retry configuration."""
        test_config.file_operation_retries = 5  # Different from default
        
        sub_op = MockSubOperation(
            logger=mock_logger,
            error_handling_components=mock_error_handling_components,
            config=test_config
        )
        
        await sub_op.test_operation("test_value")
        
        # Verify that resilient manager was called
        mock_error_handling_components["resilient_manager"].execute_with_retry.assert_called_once()

    def test_get_performance_stats(self, sub_operation):
        """Test getting performance statistics."""
        # Simulate some operations
        sub_operation._operation_count = 10
        sub_operation._error_count = 2
        sub_operation._total_duration = 5.0
        
        stats = sub_operation.get_performance_stats()
        
        assert stats["operation_name"] == "test_operations"
        assert stats["provider_type"] == "test"
        assert stats["total_operations"] == 10
        assert stats["error_count"] == 2
        assert stats["error_rate"] == 0.2
        assert stats["average_duration"] == 0.5
        assert stats["total_duration"] == 5.0

    def test_update_config(self, sub_operation, test_config):
        """Test updating configuration."""
        new_config = SubOperationConfig(
            operation_name="updated_ops",
            provider_type="test",
            log_level="DEBUG"
        )
        
        sub_operation.update_config(new_config)
        
        assert sub_operation.config == new_config
        assert sub_operation.config.log_level == "DEBUG"

    def test_get_config(self, sub_operation, test_config):
        """Test getting current configuration."""
        config = sub_operation.get_config()
        
        assert config == test_config

    def test_reset_stats(self, sub_operation):
        """Test resetting performance statistics."""
        # Set some stats
        sub_operation._operation_count = 10
        sub_operation._error_count = 5
        sub_operation._total_duration = 10.0
        
        sub_operation.reset_stats()
        
        assert sub_operation._operation_count == 0
        assert sub_operation._error_count == 0
        assert sub_operation._total_duration == 0.0

    @pytest.mark.asyncio
    async def test_health_check(self, sub_operation):
        """Test health check functionality."""
        health_status = sub_operation.get_health_status()
        
        assert "healthy" in health_status
        assert health_status["operation_name"] == "test_operations"
        assert health_status["provider_type"] == "test"
        assert "performance_stats" in health_status
        assert "config" in health_status

    @pytest.mark.asyncio
    async def test_health_check_implementation(self, sub_operation):
        """Test the health check implementation."""
        # Test with empty data (should be healthy)
        result = await sub_operation.health_check()
        assert result is True
        
        # Add some data (should still be healthy)
        sub_operation.test_data.append("test")
        result = await sub_operation.health_check()
        assert result is True

    def test_logging_setup(self, mock_logger, test_config):
        """Test logging setup."""
        test_config.log_level = "DEBUG"
        
        sub_op = MockSubOperation(
            logger=mock_logger,
            config=test_config
        )
        
        # Verify that the operation logger was created
        assert hasattr(sub_op, 'operation_logger')
        assert sub_op.operation_logger.name == "MockSubOperation.test_operations"

    @pytest.mark.asyncio
    @patch('logging.getLogger')
    async def test_operation_logging(self, mock_get_logger, mock_logger, test_config):
        """Test operation logging."""
        mock_operation_logger = MagicMock()
        mock_get_logger.return_value = mock_operation_logger
        test_config.log_operations = True
        
        sub_op = MockSubOperation(
            logger=mock_logger,
            config=test_config
        )
        sub_op.operation_logger = mock_operation_logger
        
        await sub_op.test_operation("test_value")
        
        # Verify that logging was called
        assert mock_operation_logger.info.called

    @pytest.mark.asyncio
    @patch('logging.getLogger')
    async def test_error_logging(self, mock_get_logger, mock_logger, test_config):
        """Test error logging."""
        mock_operation_logger = MagicMock()
        mock_get_logger.return_value = mock_operation_logger
        test_config.log_errors = True
        
        sub_op = MockSubOperation(
            logger=mock_logger,
            config=test_config
        )
        sub_op.operation_logger = mock_operation_logger
        
        # Mock a failing operation
        async def failing_operation():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await sub_op._execute_with_error_handling("failing_operation", failing_operation, "file")
        
        # Verify that error logging was called
        assert mock_operation_logger.error.called
