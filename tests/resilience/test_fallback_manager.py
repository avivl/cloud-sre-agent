"""Tests for FallbackManager."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from gemini_sre_agent.resilience.fallback_manager import FallbackManager


@pytest.fixture
def fallback_manager():
    """Create a FallbackManager instance."""
    return FallbackManager(
        providers=["gemini", "openai", "anthropic"],
        fallback_timeout=0.5,  # Fast for testing
    )


@pytest.fixture
def mock_provider_func():
    """Create a mock provider function."""
    return AsyncMock()


class TestFallbackManager:
    """Test cases for FallbackManager."""

    def test_initialization(self):
        """Test FallbackManager initialization."""
        manager = FallbackManager(providers=[])
        assert manager.providers == []
        assert manager.fallback_timeout == 30.0
        assert manager._provider_health == {}

    def test_initialization_with_params(self, fallback_manager):
        """Test FallbackManager initialization with parameters."""
        assert fallback_manager.providers == ["gemini", "openai", "anthropic"]
        assert fallback_manager.fallback_timeout == 0.5
        assert len(fallback_manager._provider_health) == 3

    def test_add_provider(self, fallback_manager):
        """Test adding a provider."""
        initial_count = len(fallback_manager.providers)

        fallback_manager.add_provider("new_provider")

        assert len(fallback_manager.providers) == initial_count + 1
        assert "new_provider" in fallback_manager.providers

    def test_remove_provider(self, fallback_manager):
        """Test removing a provider."""
        initial_count = len(fallback_manager.providers)

        result = fallback_manager.remove_provider("gemini")

        assert result is True
        assert len(fallback_manager.providers) == initial_count - 1
        assert "gemini" not in fallback_manager.providers

    def test_remove_provider_nonexistent(self, fallback_manager):
        """Test removing a non-existent provider."""
        result = fallback_manager.remove_provider("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_execute_with_fallback_success_first_provider(
        self, fallback_manager, mock_provider_func
    ):
        """Test successful execution with first provider."""
        mock_provider_func.return_value = "success"

        provider_funcs = {"gemini": mock_provider_func}

        result, provider = await fallback_manager.execute_with_fallback(provider_funcs)

        assert result == "success"
        assert provider == "gemini"
        assert mock_provider_func.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_with_fallback_success_second_provider(
        self, fallback_manager, mock_provider_func
    ):
        """Test successful execution with second provider after first fails."""
        # First call fails, second succeeds
        mock_provider_func.side_effect = [Exception("fail"), "success"]

        provider_funcs = {
            "gemini": mock_provider_func,
            "openai": mock_provider_func,
        }

        result, provider = await fallback_manager.execute_with_fallback(provider_funcs)

        assert result == "success"
        assert provider == "openai"  # Second provider
        assert mock_provider_func.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_fallback_all_fail(
        self, fallback_manager, mock_provider_func
    ):
        """Test when all providers fail."""
        mock_provider_func.side_effect = Exception("all_fail")

        provider_funcs = {
            "gemini": mock_provider_func,
            "openai": mock_provider_func,
            "anthropic": mock_provider_func,
        }

        with pytest.raises(Exception, match="all_fail"):
            await fallback_manager.execute_with_fallback(provider_funcs)

        # Should have tried all providers
        assert mock_provider_func.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_fallback_timeout(
        self, fallback_manager, mock_provider_func
    ):
        """Test timeout handling in fallback."""

        # Make the function hang
        async def hanging_func(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than timeout
            return "success"

        mock_provider_func.side_effect = hanging_func

        provider_funcs = {"gemini": mock_provider_func}

        with pytest.raises(Exception):
            await fallback_manager.execute_with_fallback(provider_funcs)

    @pytest.mark.asyncio
    async def test_execute_with_fallback_custom_timeout(self, mock_provider_func):
        """Test fallback with custom timeout."""
        manager = FallbackManager(
            providers=["gemini", "openai"],
            fallback_timeout=0.1,  # Very short timeout
        )

        # Make the function hang
        async def hanging_func(*args, **kwargs):
            await asyncio.sleep(1.0)  # Longer than timeout
            return "success"

        mock_provider_func.side_effect = hanging_func

        provider_funcs = {"gemini": mock_provider_func}

        with pytest.raises(Exception):
            await manager.execute_with_fallback(provider_funcs)

    @pytest.mark.asyncio
    async def test_execute_with_fallback_sync_function(self, fallback_manager):
        """Test fallback with synchronous function."""
        call_count = 0

        def sync_func(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("sync fail")
            return "sync success"

        provider_funcs = {
            "gemini": sync_func,
            "openai": sync_func,
        }

        result, provider = await fallback_manager.execute_with_fallback(provider_funcs)

        assert result == "sync success"
        assert provider == "openai"  # Second provider
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_fallback_sync_function_all_fail(self, fallback_manager):
        """Test fallback with synchronous function that always fails."""
        call_count = 0

        def sync_fail_func(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ValueError("sync always fail")

        provider_funcs = {
            "gemini": sync_fail_func,
            "openai": sync_fail_func,
            "anthropic": sync_fail_func,
        }

        with pytest.raises(ValueError, match="sync always fail"):
            await fallback_manager.execute_with_fallback(provider_funcs)

        assert call_count == 3  # All providers

    @pytest.mark.asyncio
    async def test_execute_with_fallback_function_with_arguments(
        self, fallback_manager, mock_provider_func
    ):
        """Test fallback with function that takes arguments."""
        mock_provider_func.return_value = "success"

        provider_funcs = {"gemini": mock_provider_func}

        result, provider = await fallback_manager.execute_with_fallback(
            provider_funcs, "arg1", "arg2", kwarg1="value1"
        )

        assert result == "success"
        assert provider == "gemini"

        # Check that arguments were passed correctly
        mock_provider_func.assert_called_once_with("arg1", "arg2", kwarg1="value1")

    @pytest.mark.asyncio
    async def test_execute_with_fallback_function_with_arguments_failure(
        self, fallback_manager, mock_provider_func
    ):
        """Test fallback with function that takes arguments and fails."""
        # First call fails, second succeeds
        mock_provider_func.side_effect = [Exception("fail"), "success"]

        provider_funcs = {
            "gemini": mock_provider_func,
            "openai": mock_provider_func,
        }

        result, provider = await fallback_manager.execute_with_fallback(
            provider_funcs, "arg1", "arg2", kwarg1="value1"
        )

        assert result == "success"
        assert provider == "openai"

        # Check that arguments were passed to both calls
        assert mock_provider_func.call_count == 2
        expected_call = (("arg1", "arg2"), {"kwarg1": "value1"})
        assert mock_provider_func.call_args_list[0] == expected_call
        assert mock_provider_func.call_args_list[1] == expected_call

    def test_get_provider_stats(self, fallback_manager):
        """Test getting provider statistics."""
        stats = fallback_manager.get_provider_stats("gemini")

        assert stats["provider"] == "gemini"
        assert stats["total_requests"] == 0
        assert stats["total_successes"] == 0
        assert stats["total_failures"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["average_response_time"] == 0.0

    def test_get_provider_stats_nonexistent(self, fallback_manager):
        """Test getting statistics for non-existent provider."""
        stats = fallback_manager.get_provider_stats("nonexistent")

        assert stats["provider"] == "nonexistent"
        assert stats["total_requests"] == 0
        assert stats["total_successes"] == 0
        assert stats["total_failures"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["average_response_time"] == 0.0

    def test_get_all_provider_stats(self, fallback_manager):
        """Test getting statistics for all providers."""
        all_stats = fallback_manager.get_all_stats()

        assert "total_requests" in all_stats
        assert "total_fallbacks" in all_stats
        assert "providers" in all_stats
        assert len(all_stats["providers"]) == 3

        for provider, stats in all_stats["providers"].items():
            assert stats["provider"] == provider
            assert stats["healthy"] is True
            assert stats["failures"] == 0
            assert stats["usage"] == 0

    def test_reset_provider_stats(self, fallback_manager):
        """Test resetting provider statistics."""
        # Simulate some stats
        fallback_manager._provider_usage["gemini"] = 10

        fallback_manager.reset_provider_stats("gemini")

        stats = fallback_manager.get_provider_stats("gemini")
        assert stats["failures"] == 0
        assert stats["usage"] == 0

    def test_reset_provider_stats_nonexistent(self, fallback_manager):
        """Test resetting statistics for non-existent provider."""
        fallback_manager.reset_provider_stats("nonexistent")
        # Should not raise an exception

    def test_reset_all_provider_stats(self, fallback_manager):
        """Test resetting all provider statistics."""
        # Simulate some stats for all providers
        for provider in fallback_manager.providers:
            fallback_manager._provider_usage[provider] = 5

        fallback_manager.reset_provider_stats()

        for provider in fallback_manager.providers:
            stats = fallback_manager.get_provider_stats(provider)
            assert stats["failures"] == 0
            assert stats["usage"] == 0

    def test_provider_health_tracking(self, fallback_manager):
        """Test provider health tracking."""
        # Test initial health state
        assert fallback_manager._provider_health["gemini"] is True
        assert fallback_manager._provider_health["openai"] is True
        assert fallback_manager._provider_health["anthropic"] is True

        # Test marking provider as unhealthy
        fallback_manager._provider_health["gemini"] = False
        assert fallback_manager._provider_health["gemini"] is False

    def test_provider_failure_tracking(self, fallback_manager):
        """Test provider failure tracking."""
        # Test initial failure count
        assert fallback_manager._provider_failures["gemini"] == 0

        # Test incrementing failure count
        fallback_manager._provider_failures["gemini"] = 5
        assert fallback_manager._provider_failures["gemini"] == 5

    def test_provider_usage_tracking(self, fallback_manager):
        """Test provider usage tracking."""
        # Test initial usage count
        assert fallback_manager._provider_usage["gemini"] == 0

        # Test incrementing usage count
        fallback_manager._provider_usage["gemini"] = 10
        assert fallback_manager._provider_usage["gemini"] == 10

    @pytest.mark.asyncio
    async def test_concurrent_fallback_executions(
        self, fallback_manager, mock_provider_func
    ):
        """Test concurrent fallback executions."""
        mock_provider_func.return_value = "success"

        provider_funcs = {"gemini": mock_provider_func}

        # Execute multiple concurrent calls
        tasks = [
            fallback_manager.execute_with_fallback(provider_funcs) for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for result, provider in results:
            assert result == "success"
            assert provider == "gemini"

    @pytest.mark.asyncio
    async def test_concurrent_fallback_executions_with_failures(
        self, fallback_manager, mock_provider_func
    ):
        """Test concurrent fallback executions with some failures."""
        # Each call tries gemini (fails) then openai (succeeds), so we need 6 side effects for 3 calls
        mock_provider_func.side_effect = [
            Exception("fail"),
            "success",  # Call 1: gemini fails, openai succeeds
            Exception("fail"),
            "success",  # Call 2: gemini fails, openai succeeds
            Exception("fail"),
            "success",  # Call 3: gemini fails, openai succeeds
        ]

        provider_funcs = {
            "gemini": mock_provider_func,
            "openai": mock_provider_func,
        }

        # Execute multiple concurrent calls
        tasks = [
            fallback_manager.execute_with_fallback(provider_funcs) for _ in range(3)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        for result, provider in results:
            assert result == "success"
            assert provider == "openai"  # Second provider

    @pytest.mark.asyncio
    async def test_fallback_with_different_primary_providers(
        self, fallback_manager, mock_provider_func
    ):
        """Test fallback with different primary providers."""
        mock_provider_func.return_value = "success"

        # Test with different primary providers
        primary_providers = ["gemini", "openai", "anthropic"]

        for primary in primary_providers:
            provider_funcs = {primary: mock_provider_func}
            result, provider = await fallback_manager.execute_with_fallback(
                provider_funcs
            )
            assert result == "success"
            assert provider == primary

    def test_provider_stats_tracking(self, fallback_manager):
        """Test that provider statistics are tracked correctly."""
        # Simulate some stats
        fallback_manager._provider_usage["gemini"] = 10
        fallback_manager._total_requests = 10
        fallback_manager._total_fallbacks = 2

        stats = fallback_manager.get_provider_stats("gemini")

        assert stats["usage"] == 10
        assert stats["failures"] == 0

    def test_provider_stats_success_rate_calculation(self, fallback_manager):
        """Test success rate calculation."""
        # Test with no requests
        stats = fallback_manager.get_provider_stats("gemini")
        assert stats["healthy"] is True

        # Test with some usage and failures
        fallback_manager._provider_usage["gemini"] = 5
        fallback_manager._provider_failures["gemini"] = 5
        fallback_manager._total_requests = 5

        stats = fallback_manager.get_provider_stats("gemini")
        assert stats["total_requests"] == 5
        assert stats["success_rate"] == 0.0  # 0 successes out of 5 usage
