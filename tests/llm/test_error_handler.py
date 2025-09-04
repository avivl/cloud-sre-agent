# tests/llm/test_error_handler.py

"""
Tests for the enhanced error handling and recovery system.

This module tests the error categorization, circuit breaker, deduplication,
and recovery strategies for the multi-LLM provider system.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch

from gemini_sre_agent.llm.error_handler import (
    ErrorCategory,
    ErrorHandlerConfig,
    EnhancedErrorHandler,
    RequestContext
)
from gemini_sre_agent.llm.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from gemini_sre_agent.llm.deduplicator import RequestDeduplicator, DeduplicationConfig


class TestErrorCategory:
    """Test error categorization functionality."""

    def test_error_categorization(self):
        """Test error categorization based on patterns."""
        config = ErrorHandlerConfig()
        handler = EnhancedErrorHandler(config)
        
        # Test timeout error
        timeout_error = TimeoutError("Request timed out")
        assert handler.categorize_error(timeout_error) == ErrorCategory.TIMEOUT
        
        # Test rate limit error
        rate_limit_error = Exception("rate limit exceeded")
        assert handler.categorize_error(rate_limit_error) == ErrorCategory.RATE_LIMITED
        
        # Test authentication error
        auth_error = Exception("authentication failed")
        assert handler.categorize_error(auth_error) == ErrorCategory.AUTHENTICATION
        
        # Test network error
        network_error = Exception("network connection failed")
        assert handler.categorize_error(network_error) == ErrorCategory.NETWORK


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_states(self):
        """Test circuit breaker state transitions."""
        config = CircuitBreakerConfig(failure_threshold=3, reset_timeout=1.0)
        breaker = CircuitBreaker(config)
        provider_id = "test_provider"
        
        # Test initial state (closed)
        assert await breaker.allow_request(provider_id) is True
        
        # Test transition to open after failures
        for _ in range(3):
            await breaker.record_failure(provider_id)
        assert await breaker.allow_request(provider_id) is False
        
        # Test half-open state after timeout
        await asyncio.sleep(1.1)  # Wait for reset timeout
        assert await breaker.allow_request(provider_id) is True
        
        # Test transition back to closed after successes
        for _ in range(3):
            await breaker.record_success(provider_id)
        assert await breaker.allow_request(provider_id) is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_concurrent_access(self):
        """Test circuit breaker with concurrent access."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(config)
        provider_id = "test_provider"
        
        # Simulate concurrent failures
        tasks = [breaker.record_failure(provider_id) for _ in range(10)]
        await asyncio.gather(*tasks)
        
        # Should be open after threshold
        assert await breaker.allow_request(provider_id) is False


class TestRequestDeduplicator:
    """Test request deduplication functionality."""

    @pytest.mark.asyncio
    async def test_deduplication(self):
        """Test request deduplication."""
        config = DeduplicationConfig(ttl=60.0, enabled=True)
        deduplicator = RequestDeduplicator(config)
        
        request = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7
        }
        
        # First request should not be cached
        cached_response = await deduplicator.get_cached_response(request)
        assert cached_response is None
        
        # Cache a response
        test_response = "Hello, world!"
        await deduplicator.cache_response(request, test_response)
        
        # Second identical request should return cached response
        cached_response = await deduplicator.get_cached_response(request)
        assert cached_response == test_response

    @pytest.mark.asyncio
    async def test_deduplication_disabled(self):
        """Test deduplication when disabled."""
        config = DeduplicationConfig(enabled=False)
        deduplicator = RequestDeduplicator(config)
        
        request = {"model": "gpt-3.5-turbo", "messages": []}
        
        # Should return None even if response is cached
        await deduplicator.cache_response(request, "test")
        cached_response = await deduplicator.get_cached_response(request)
        assert cached_response is None

    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Test cache expiration."""
        config = DeduplicationConfig(ttl=0.1)  # Very short TTL
        deduplicator = RequestDeduplicator(config)
        
        request = {"model": "gpt-3.5-turbo", "messages": []}
        
        # Cache response
        await deduplicator.cache_response(request, "test")
        
        # Should be available immediately
        cached_response = await deduplicator.get_cached_response(request)
        assert cached_response == "test"
        
        # Wait for expiration
        await asyncio.sleep(0.2)
        
        # Should be expired
        cached_response = await deduplicator.get_cached_response(request)
        assert cached_response is None


class TestEnhancedErrorHandler:
    """Test enhanced error handler functionality."""

    @pytest.mark.asyncio
    async def test_error_handling_flow(self):
        """Test complete error handling flow."""
        config = ErrorHandlerConfig()
        handler = EnhancedErrorHandler(config)
        
        context = RequestContext(
            provider_id="test_provider",
            request_id="test_request_123"
        )
        
        # Test transient error handling
        transient_error = Exception("temporary failure")
        result = await handler.handle_error(transient_error, context)
        assert result == "retry"
        
        # Test permanent error handling
        permanent_error = Exception("permanent failure")
        result = await handler.handle_error(permanent_error, context)
        assert result is None

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with error handler."""
        config = ErrorHandlerConfig()
        handler = EnhancedErrorHandler(config)
        
        context = RequestContext(
            provider_id="test_provider",
            request_id="test_request_123"
        )
        
        # Simulate provider failures to trigger circuit breaker
        for _ in range(6):  # More than failure threshold
            provider_error = Exception("service unavailable")
            await handler.handle_error(provider_error, context)
        
        # Circuit should be open
        assert await handler.should_circuit_break("test_provider") is True

    @pytest.mark.asyncio
    async def test_error_analytics(self):
        """Test error analytics functionality."""
        config = ErrorHandlerConfig()
        handler = EnhancedErrorHandler(config)
        
        context = RequestContext(
            provider_id="test_provider",
            request_id="test_request_123"
        )
        
        # Record some errors
        await handler.handle_error(Exception("test error 1"), context)
        await handler.handle_error(Exception("test error 2"), context)
        
        # Get error summary
        summary = await handler.get_error_summary()
        assert summary["total_errors"] >= 2
        assert "test_provider" in summary["provider_errors"]

    @pytest.mark.asyncio
    async def test_recovery_strategies(self):
        """Test different recovery strategies."""
        config = ErrorHandlerConfig()
        handler = EnhancedErrorHandler(config)
        
        # Test rate limit recovery
        rate_limit_strategy = await handler.get_recovery_strategy(ErrorCategory.RATE_LIMITED)
        assert rate_limit_strategy == "exponential_backoff"
        
        # Test provider failure recovery
        provider_failure_strategy = await handler.get_recovery_strategy(ErrorCategory.PROVIDER_FAILURE)
        assert provider_failure_strategy == "circuit_breaker_fallback"
        
        # Test permanent error recovery
        permanent_strategy = await handler.get_recovery_strategy(ErrorCategory.PERMANENT)
        assert permanent_strategy == "no_retry"


class TestErrorHandlerConfig:
    """Test error handler configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ErrorHandlerConfig()
        
        assert config.max_retries == 3
        assert config.retry_delay_base == 1.0
        assert config.retry_delay_max == 30.0
        assert config.circuit_breaker_config.failure_threshold == 5
        assert config.deduplication_config.enabled is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ErrorHandlerConfig(
            max_retries=5,
            retry_delay_base=2.0,
            retry_delay_max=60.0
        )
        
        assert config.max_retries == 5
        assert config.retry_delay_base == 2.0
        assert config.retry_delay_max == 60.0
