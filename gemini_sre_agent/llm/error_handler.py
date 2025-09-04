# gemini_sre_agent/llm/error_handler.py

"""
Enhanced error handling and recovery system for multi-LLM provider support.

This module provides comprehensive error categorization, recovery strategies,
circuit breaker implementation, and request deduplication for improved system resilience.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from .circuit_breaker import CircuitBreaker
from .deduplicator import RequestDeduplicator
from .error_analytics import ErrorAnalytics
from .error_config import ErrorCategory, ErrorHandlerConfig, RequestContext

logger = logging.getLogger(__name__)










class EnhancedErrorHandler:
    """Enhanced error handling with categorization and recovery strategies."""

    def __init__(self, config: ErrorHandlerConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.error_patterns = self._load_error_patterns()
        self.circuit_breaker = CircuitBreaker(config.circuit_breaker_config)
        self.deduplicator = RequestDeduplicator(config.deduplication_config)
        self.analytics = ErrorAnalytics()

    def _load_error_patterns(self) -> Dict[str, ErrorCategory]:
        """Load error patterns for categorization."""
        return {
            "rate limit": ErrorCategory.RATE_LIMITED,
            "quota exceeded": ErrorCategory.QUOTA_EXCEEDED,
            "authentication": ErrorCategory.AUTHENTICATION,
            "unauthorized": ErrorCategory.AUTHENTICATION,
            "timeout": ErrorCategory.TIMEOUT,
            "network": ErrorCategory.NETWORK,
            "connection": ErrorCategory.NETWORK,
            "service unavailable": ErrorCategory.PROVIDER_FAILURE,
            "internal server error": ErrorCategory.PROVIDER_FAILURE,
        }

    def categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error based on patterns and type."""
        error_message = str(error).lower()
        
        # Check against known patterns
        for pattern, category in self.error_patterns.items():
            if pattern in error_message:
                return category
        
        # Type-based categorization
        if isinstance(error, TimeoutError):
            return ErrorCategory.TIMEOUT
        elif isinstance(error, ConnectionError):
            return ErrorCategory.NETWORK
        elif isinstance(error, PermissionError):
            return ErrorCategory.AUTHENTICATION
        
        # Default to permanent for unknown errors
        return ErrorCategory.PERMANENT

    async def handle_error(
        self, 
        error: Exception, 
        context: RequestContext
    ) -> Optional[Any]:
        """Main error handling entry point."""
        category = self.categorize_error(error)
        await self.analytics.record_error(error, category, context)
        
        self.logger.warning(
            f"Error {category.name} for provider {context.provider_id}: {str(error)}"
        )
        
        # Check circuit breaker for provider failures
        if category == ErrorCategory.PROVIDER_FAILURE:
            await self.circuit_breaker.record_failure(context.provider_id)
            if not await self.circuit_breaker.allow_request(context.provider_id):
                self.logger.info(f"Circuit breaker open for {context.provider_id}")
                return None
        
        # Apply recovery strategy based on category
        if category == ErrorCategory.TRANSIENT:
            return await self._handle_transient(error, context)
        elif category == ErrorCategory.RATE_LIMITED:
            return await self._handle_rate_limited(error, context)
        elif category == ErrorCategory.TIMEOUT:
            return await self._handle_timeout(error, context)
        elif category == ErrorCategory.NETWORK:
            return await self._handle_network(error, context)
        
        # For permanent errors, don't retry
        return None

    async def _handle_transient(self, error: Exception, context: RequestContext) -> Optional[Any]:
        """Handle transient errors with retry."""
        if context.retry_count < context.max_retries:
            delay = min(
                self.config.retry_delay_base * (2 ** context.retry_count),
                self.config.retry_delay_max
            )
            self.logger.info(f"Retrying in {delay}s (attempt {context.retry_count + 1})")
            await asyncio.sleep(delay)
            return "retry"
        return None

    async def _handle_rate_limited(self, error: Exception, context: RequestContext) -> Optional[Any]:
        """Handle rate limit errors with backoff."""
        delay = min(60.0, self.config.retry_delay_base * (2 ** context.retry_count))
        self.logger.info(f"Rate limited, backing off for {delay}s")
        await asyncio.sleep(delay)
        return "retry"

    async def _handle_timeout(self, error: Exception, context: RequestContext) -> Optional[Any]:
        """Handle timeout errors."""
        if context.retry_count < context.max_retries:
            delay = self.config.retry_delay_base * 2
            self.logger.info(f"Timeout, retrying in {delay}s")
            await asyncio.sleep(delay)
            return "retry"
        return None

    async def _handle_network(self, error: Exception, context: RequestContext) -> Optional[Any]:
        """Handle network errors."""
        if context.retry_count < context.max_retries:
            delay = min(
                self.config.retry_delay_base * (2 ** context.retry_count),
                self.config.retry_delay_max
            )
            self.logger.info(f"Network error, retrying in {delay}s")
            await asyncio.sleep(delay)
            return "retry"
        return None

    async def get_recovery_strategy(self, category: ErrorCategory) -> str:
        """Get recovery strategy for error category."""
        strategies = {
            ErrorCategory.TRANSIENT: "exponential_backoff_retry",
            ErrorCategory.PROVIDER_FAILURE: "circuit_breaker_fallback",
            ErrorCategory.RATE_LIMITED: "exponential_backoff",
            ErrorCategory.QUOTA_EXCEEDED: "switch_provider",
            ErrorCategory.AUTHENTICATION: "check_credentials",
            ErrorCategory.TIMEOUT: "increase_timeout_retry",
            ErrorCategory.NETWORK: "exponential_backoff_retry",
            ErrorCategory.PERMANENT: "no_retry",
        }
        return strategies.get(category, "no_retry")

    async def should_circuit_break(self, provider_id: str) -> bool:
        """Check if circuit breaker should prevent requests."""
        return not await self.circuit_breaker.allow_request(provider_id)

    async def record_success(self, provider_id: str) -> None:
        """Record successful request for circuit breaker."""
        await self.circuit_breaker.record_success(provider_id)

    async def get_error_summary(self) -> Dict[str, Any]:
        """Get comprehensive error summary."""
        return await self.analytics.get_error_summary()
