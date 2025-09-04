"""Tests for ResilienceManager."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from gemini_sre_agent.resilience.circuit_breaker import CircuitBreakerOpenException
from gemini_sre_agent.resilience.resilience_manager import ResilienceManager


@pytest.fixture
def resilience_manager():
    """Create a ResilienceManager instance."""
    return ResilienceManager(
        providers=["gemini", "openai", "anthropic"],
        max_retries=3,
        base_delay=0.1,  # Fast for testing
        max_delay=1.0,
        jitter=False,  # Disable jitter for predictable testing
        circuit_breaker_threshold=2,
        circuit_breaker_timeout=1.0,
        fallback_timeout=5.0,
        use_tenacity=False,  # Use custom retry handler for testing
    )


@pytest.fixture
def mock_provider_func():
    """Create a mock provider function."""
    return AsyncMock()


class TestResilienceManager:
    """Test cases for ResilienceManager."""

    def test_initialization(self):
        """Test ResilienceManager initialization."""
        manager = ResilienceManager()
        assert manager.providers == []
        assert manager.max_retries == 3
        assert manager.base_delay == 1.0
        assert manager.max_delay == 60.0
        assert manager.jitter is True
        assert manager.circuit_breaker_threshold == 5
        assert manager.circuit_breaker_timeout == 60.0
        assert manager.fallback_timeout == 30.0

    def test_initialization_with_params(self, resilience_manager):
        """Test ResilienceManager initialization with parameters."""
        assert resilience_manager.providers == ["gemini", "openai", "anthropic"]
        assert resilience_manager.max_retries == 3
        assert resilience_manager.base_delay == 0.1
        assert resilience_manager.max_delay == 1.0
        assert resilience_manager.jitter is False
        assert resilience_manager.circuit_breaker_threshold == 2
        assert resilience_manager.circuit_breaker_timeout == 1.0
        assert resilience_manager.fallback_timeout == 5.0

    @pytest.mark.asyncio
    async def test_execute_with_resilience_success(
        self, resilience_manager, mock_provider_func
    ):
        """Test successful execution with resilience."""
        mock_provider_func.return_value = "success"

        result, provider = await resilience_manager.execute_with_resilience(
            mock_provider_func, "gemini"
        )

        assert result == "success"
        assert provider == "gemini"
        assert resilience_manager._total_requests == 1
        assert resilience_manager._total_successes == 1

    @pytest.mark.asyncio
    async def test_execute_with_resilience_retry_success(
        self, resilience_manager, mock_provider_func
    ):
        """Test successful execution after retries."""
        # First two calls fail, third succeeds
        mock_provider_func.side_effect = [
            Exception("fail"),
            Exception("fail"),
            "success",
        ]

        result, provider = await resilience_manager.execute_with_resilience(
            mock_provider_func, "gemini"
        )

        assert result == "success"
        assert provider == "gemini"
        assert mock_provider_func.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_resilience_circuit_breaker(
        self, resilience_manager, mock_provider_func
    ):
        """Test circuit breaker functionality."""
        # Make enough failures to open circuit breaker
        mock_provider_func.side_effect = Exception("fail")

        # First few calls should fail normally
        for _ in range(2):
            with pytest.raises(Exception):
                await resilience_manager.execute_with_resilience(
                    mock_provider_func, "gemini"
                )

        # Circuit breaker should now be open
        with pytest.raises(CircuitBreakerOpenException):
            await resilience_manager.execute_with_resilience(
                mock_provider_func, "gemini", enable_fallback=False
            )

    @pytest.mark.asyncio
    async def test_execute_with_resilience_fallback(
        self, resilience_manager, mock_provider_func
    ):
        """Test fallback functionality."""

        # Create different functions for different providers
        async def gemini_func(*args, **kwargs):
            raise Exception("provider_failure")

        async def openai_func(*args, **kwargs):
            return "fallback_success"

        async def anthropic_func(*args, **kwargs):
            return "fallback_success"

        # Mock the function to return different functions based on provider
        def get_provider_func(provider):
            if provider == "gemini":
                return gemini_func
            elif provider == "openai":
                return openai_func
            elif provider == "anthropic":
                return anthropic_func
            else:
                return mock_provider_func

        # Override the _try_fallback method to use different functions
        original_try_fallback = resilience_manager._try_fallback

        async def mock_try_fallback(original_func, *args, **kwargs):
            # Create provider functions dictionary with different functions
            provider_funcs = {}
            for provider in resilience_manager.providers:
                provider_funcs[provider] = get_provider_func(provider)

            result, provider_used = (
                await resilience_manager.fallback_manager.execute_with_fallback(
                    provider_funcs, *args, **kwargs
                )
            )
            return result, provider_used

        resilience_manager._try_fallback = mock_try_fallback

        try:
            result, provider = await resilience_manager.execute_with_resilience(
                gemini_func, "gemini"
            )

            assert result == "fallback_success"
            assert provider in ["openai", "anthropic"]  # One of the fallback providers
        finally:
            resilience_manager._try_fallback = original_try_fallback

    @pytest.mark.asyncio
    async def test_execute_with_resilience_all_fail(
        self, resilience_manager, mock_provider_func
    ):
        """Test when all providers fail."""
        # Clear circuit breaker state to ensure clean test
        resilience_manager.clear_all_circuit_breakers()

        mock_provider_func.side_effect = Exception("all_fail")

        # After circuit breaker opens, it should raise CircuitBreakerOpenException
        with pytest.raises(CircuitBreakerOpenException):
            await resilience_manager.execute_with_resilience(
                mock_provider_func, "gemini"
            )

    @pytest.mark.asyncio
    async def test_execute_with_resilience_disabled_features(
        self, resilience_manager, mock_provider_func
    ):
        """Test execution with disabled resilience features."""
        mock_provider_func.return_value = "success"

        result, provider = await resilience_manager.execute_with_resilience(
            mock_provider_func,
            "gemini",
            enable_circuit_breaker=False,
            enable_retry=False,
            enable_fallback=False,
        )

        assert result == "success"
        assert provider == "gemini"

    def test_get_circuit_breaker(self, resilience_manager):
        """Test getting circuit breaker for a provider."""
        breaker = resilience_manager.get_circuit_breaker("gemini")
        assert breaker.name == "gemini"
        assert breaker.failure_threshold == 2
        assert breaker.recovery_timeout == 1.0

    def test_reset_circuit_breaker(self, resilience_manager):
        """Test resetting circuit breaker."""
        breaker = resilience_manager.get_circuit_breaker("gemini")

        # Simulate some failures
        breaker._failure_count = 3
        breaker._state = breaker._state.OPEN

        result = resilience_manager.reset_circuit_breaker("gemini")
        assert result is True
        assert breaker._failure_count == 0

    def test_reset_circuit_breaker_nonexistent(self, resilience_manager):
        """Test resetting non-existent circuit breaker."""
        result = resilience_manager.reset_circuit_breaker("nonexistent")
        assert result is False

    def test_mark_provider_healthy(self, resilience_manager):
        """Test marking provider as healthy."""
        resilience_manager.mark_provider_healthy("gemini")
        assert resilience_manager.get_provider_health("gemini") is True

    def test_mark_provider_unhealthy(self, resilience_manager):
        """Test marking provider as unhealthy."""
        resilience_manager.mark_provider_unhealthy("gemini")
        assert resilience_manager.get_provider_health("gemini") is False

    def test_get_provider_health(self, resilience_manager):
        """Test getting provider health status."""
        health = resilience_manager.get_provider_health("gemini")
        assert isinstance(health, bool)

    def test_get_comprehensive_stats(self, resilience_manager):
        """Test getting comprehensive statistics."""
        stats = resilience_manager.get_comprehensive_stats()

        assert "resilience_manager" in stats
        assert "circuit_breakers" in stats
        assert "retry_handler" in stats
        assert "error_classifier" in stats
        assert "fallback_manager" in stats

        assert stats["resilience_manager"]["total_requests"] == 0
        assert stats["resilience_manager"]["total_successes"] == 0
        assert stats["resilience_manager"]["total_failures"] == 0

    def test_get_provider_stats(self, resilience_manager):
        """Test getting provider-specific statistics."""
        stats = resilience_manager.get_provider_stats("gemini")

        assert stats["provider"] == "gemini"
        assert "healthy" in stats
        assert "circuit_breaker" in stats
        assert "fallback" in stats

    def test_configure_provider(self, resilience_manager):
        """Test configuring provider-specific settings."""
        resilience_manager.configure_provider(
            "gemini",
            max_retries=5,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=2.0,
        )

        breaker = resilience_manager.get_circuit_breaker("gemini")
        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 2.0

    def test_add_provider(self, resilience_manager):
        """Test adding a provider."""
        initial_count = len(resilience_manager.providers)

        resilience_manager.add_provider("new_provider")

        assert len(resilience_manager.providers) == initial_count + 1
        assert "new_provider" in resilience_manager.providers

    def test_remove_provider(self, resilience_manager):
        """Test removing a provider."""
        initial_count = len(resilience_manager.providers)

        result = resilience_manager.remove_provider("gemini")

        assert result is True
        assert len(resilience_manager.providers) == initial_count - 1
        assert "gemini" not in resilience_manager.providers

    def test_remove_provider_nonexistent(self, resilience_manager):
        """Test removing a non-existent provider."""
        result = resilience_manager.remove_provider("nonexistent")
        assert result is True  # Should return True even if not found

    def test_health_check(self, resilience_manager):
        """Test health check functionality."""
        health = resilience_manager.health_check()

        assert "healthy_providers" in health
        assert "total_providers" in health
        assert "health_percentage" in health
        assert "circuit_breakers_healthy" in health
        assert "fallback_available" in health

        assert health["total_providers"] == 3
        assert health["fallback_available"] is True

    @pytest.mark.asyncio
    async def test_timeout_handling(self, resilience_manager, mock_provider_func):
        """Test timeout handling in fallback."""

        # Make the function hang
        async def hanging_func(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than fallback timeout
            return "success"

        mock_provider_func.side_effect = hanging_func

        with pytest.raises(Exception):
            await resilience_manager.execute_with_resilience(
                mock_provider_func, "gemini"
            )

    @pytest.mark.asyncio
    async def test_error_classification_integration(
        self, resilience_manager, mock_provider_func
    ):
        """Test integration with error classification."""
        # Clear circuit breaker state to ensure clean test
        resilience_manager.clear_all_circuit_breakers()

        # Test with a rate limit error
        class RateLimitError(Exception):
            pass

        mock_provider_func.side_effect = RateLimitError("rate limit exceeded")

        # After circuit breaker opens, it should raise CircuitBreakerOpenException
        with pytest.raises(CircuitBreakerOpenException):
            await resilience_manager.execute_with_resilience(
                mock_provider_func, "gemini"
            )

        # Should have attempted retries
        assert mock_provider_func.call_count > 1

    def test_reset_all_circuit_breakers(self, resilience_manager):
        """Test resetting all circuit breakers."""
        # Create some circuit breakers with failures
        breaker1 = resilience_manager.get_circuit_breaker("gemini")
        breaker2 = resilience_manager.get_circuit_breaker("openai")

        breaker1._failure_count = 3
        breaker2._failure_count = 2

        resilience_manager.reset_all_circuit_breakers()

        assert breaker1._failure_count == 0
        assert breaker2._failure_count == 0

    @pytest.mark.asyncio
    async def test_sync_function_execution(self, resilience_manager):
        """Test execution with synchronous functions."""

        def sync_func():
            return "sync_success"

        result, provider = await resilience_manager.execute_with_resilience(
            sync_func, "gemini"
        )

        assert result == "sync_success"
        assert provider == "gemini"

    @pytest.mark.asyncio
    async def test_sync_function_with_exception(self, resilience_manager):
        """Test execution with synchronous function that raises exception."""
        # Clear circuit breaker state to ensure clean test
        resilience_manager.clear_all_circuit_breakers()

        def sync_func():
            raise ValueError("sync_error")

        # After circuit breaker opens, it should raise CircuitBreakerOpenException
        with pytest.raises(CircuitBreakerOpenException):
            await resilience_manager.execute_with_resilience(sync_func, "gemini")
