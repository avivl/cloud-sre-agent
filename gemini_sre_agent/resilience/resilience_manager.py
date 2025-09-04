"""Main resilience manager orchestrating all resilience patterns."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerManager,
    CircuitBreakerOpenException,
)
from .error_classifier import ErrorClassifier
from .fallback_manager import FallbackManager
from .retry_handler import RetryHandler, TenacityRetryHandler

logger = logging.getLogger(__name__)


class ResilienceManager:
    """Main resilience manager coordinating circuit breakers, retries, and fallbacks."""

    def __init__(
        self,
        providers: Optional[List[str]] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
        fallback_timeout: float = 30.0,
        use_tenacity: bool = True,
    ):
        """Initialize the resilience manager.

        Args:
            providers: List of provider names for fallback
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff
            max_delay: Maximum delay for retries
            jitter: Whether to add jitter to retry delays
            circuit_breaker_threshold: Failure threshold for circuit breaker
            circuit_breaker_timeout: Timeout before circuit breaker recovery
            fallback_timeout: Timeout for fallback operations
            use_tenacity: Whether to use tenacity library for retries
        """
        self.providers = providers or []
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.fallback_timeout = fallback_timeout

        # Initialize components
        self.error_classifier = ErrorClassifier()
        self.circuit_breaker_manager = CircuitBreakerManager()

        # Initialize retry handler
        if use_tenacity:
            self.retry_handler = TenacityRetryHandler(
                max_attempts=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                jitter=jitter,
            )
        else:
            self.retry_handler = RetryHandler(
                max_attempts=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                jitter=jitter,
                error_classifier=self.error_classifier,
            )

        # Initialize fallback manager if providers are specified
        self.fallback_manager = None
        if self.providers:
            self.fallback_manager = FallbackManager(
                providers=self.providers,
                error_classifier=self.error_classifier,
                fallback_timeout=fallback_timeout,
            )

        # Statistics
        self._total_requests = 0
        self._total_successes = 0
        self._total_failures = 0
        self._circuit_breaker_trips = 0
        self._fallback_attempts = 0

    async def execute_with_resilience(
        self,
        func: Callable,
        provider: str,
        *args,
        enable_circuit_breaker: bool = True,
        enable_retry: bool = True,
        enable_fallback: bool = True,
        **kwargs,
    ) -> Tuple[Any, str]:
        """Execute a function with full resilience patterns.

        Args:
            func: Function to execute
            provider: Provider name for circuit breaker and fallback
            *args: Function arguments
            enable_circuit_breaker: Whether to use circuit breaker
            enable_retry: Whether to use retry logic
            enable_fallback: Whether to use fallback
            **kwargs: Function keyword arguments

        Returns:
            Tuple of (result, provider_used)

        Raises:
            Exception: If all resilience patterns fail
        """
        self._total_requests += 1

        # Get circuit breaker for this provider
        circuit_breaker = None
        if enable_circuit_breaker:
            circuit_breaker = self.circuit_breaker_manager.get_breaker(
                name=provider,
                failure_threshold=self.circuit_breaker_threshold,
                recovery_timeout=self.circuit_breaker_timeout,
            )

        # Define the execution function with circuit breaker
        async def execute_with_circuit_breaker():
            if circuit_breaker:
                return await circuit_breaker.call(func, *args, **kwargs)
            else:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

        # Try with retry logic
        try:
            if enable_retry:
                result = await asyncio.wait_for(
                    self.retry_handler.execute_with_retry(execute_with_circuit_breaker),
                    timeout=self.fallback_timeout,
                )
            else:
                result = await asyncio.wait_for(
                    execute_with_circuit_breaker(), timeout=self.fallback_timeout
                )

            self._total_successes += 1
            return result, provider

        except CircuitBreakerOpenException:
            self._circuit_breaker_trips += 1
            logger.warning(f"Circuit breaker open for provider {provider}")

            # Try fallback if available and enabled
            if enable_fallback and self.fallback_manager:
                try:
                    return await self._try_fallback(func, *args, **kwargs)
                except Exception:
                    # If fallback also fails, re-raise the original circuit breaker exception
                    raise CircuitBreakerOpenException(
                        f"Circuit breaker '{provider}' is OPEN. "
                        f"Last failure: {self.circuit_breaker_manager.get_breaker(provider)._last_failure_time}"
                    ) from None
            else:
                raise

        except Exception as e:
            self._total_failures += 1
            logger.error(f"Request failed for provider {provider}: {e}")

            # Try fallback if available
            if enable_fallback and self.fallback_manager:
                return await self._try_fallback(func, *args, **kwargs)
            else:
                raise

    async def _try_fallback(
        self,
        original_func: Callable,
        *args,
        **kwargs,
    ) -> Tuple[Any, str]:
        """Try fallback to other providers.

        Args:
            original_func: Original function that failed
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Tuple of (result, provider_used)

        Raises:
            Exception: If all fallback providers fail
        """
        if not self.fallback_manager:
            raise Exception("No fallback manager available")

        self._fallback_attempts += 1

        # Create provider functions dictionary
        provider_funcs = {}
        for provider in self.providers:
            # For now, use the same function for all providers
            # In a real implementation, this would be provider-specific
            provider_funcs[provider] = original_func

        try:
            result, provider_used = await self.fallback_manager.execute_with_fallback(
                provider_funcs, *args, **kwargs
            )

            logger.info(f"Fallback succeeded with provider: {provider_used}")
            return result, provider_used

        except Exception as e:
            logger.error(f"All fallback providers failed: {e}")
            raise

    def get_circuit_breaker(self, provider: str) -> CircuitBreaker:
        """Get circuit breaker for a specific provider."""
        return self.circuit_breaker_manager.get_breaker(
            name=provider,
            failure_threshold=self.circuit_breaker_threshold,
            recovery_timeout=self.circuit_breaker_timeout,
        )

    def reset_circuit_breaker(self, provider: str) -> bool:
        """Reset circuit breaker for a specific provider."""
        return self.circuit_breaker_manager.reset_breaker(provider)

    def reset_all_circuit_breakers(self) -> None:
        """Reset all circuit breakers."""
        self.circuit_breaker_manager.reset_all()

    def clear_all_circuit_breakers(self) -> None:
        """Clear all circuit breakers from the manager."""
        self.circuit_breaker_manager.clear_all()

    def mark_provider_healthy(self, provider: str) -> None:
        """Mark a provider as healthy."""
        if self.fallback_manager:
            self.fallback_manager.mark_provider_healthy(provider)

    def mark_provider_unhealthy(self, provider: str) -> None:
        """Mark a provider as unhealthy."""
        if self.fallback_manager:
            self.fallback_manager.mark_provider_unhealthy(provider)

    def get_provider_health(self, provider: str) -> bool:
        """Get health status of a provider."""
        if self.fallback_manager:
            return self.fallback_manager.get_provider_health(provider)
        return True

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for all resilience components."""
        stats = {
            "resilience_manager": {
                "total_requests": self._total_requests,
                "total_successes": self._total_successes,
                "total_failures": self._total_failures,
                "success_rate": (
                    self._total_successes / self._total_requests * 100
                    if self._total_requests > 0
                    else 0
                ),
                "circuit_breaker_trips": self._circuit_breaker_trips,
                "fallback_attempts": self._fallback_attempts,
            },
            "circuit_breakers": self.circuit_breaker_manager.get_all_stats(),
            "retry_handler": self.retry_handler.get_stats(),
            "error_classifier": self.error_classifier.get_classification_stats(),
        }

        if self.fallback_manager:
            stats["fallback_manager"] = self.fallback_manager.get_all_stats()

        return stats

    def get_provider_stats(self, provider: str) -> Dict[str, Any]:
        """Get statistics for a specific provider."""
        stats = {
            "provider": provider,
            "healthy": self.get_provider_health(provider),
            "circuit_breaker": self.get_circuit_breaker(provider).get_stats(),
        }

        if self.fallback_manager:
            stats["fallback"] = self.fallback_manager.get_provider_stats(provider)

        return stats

    def configure_provider(
        self,
        provider: str,
        max_retries: Optional[int] = None,
        circuit_breaker_threshold: Optional[int] = None,
        circuit_breaker_timeout: Optional[float] = None,
    ) -> None:
        """Configure resilience settings for a specific provider.

        Args:
            provider: Provider name
            max_retries: Maximum retry attempts
            circuit_breaker_threshold: Circuit breaker failure threshold
            circuit_breaker_timeout: Circuit breaker recovery timeout
        """
        # Update circuit breaker settings
        if circuit_breaker_threshold is not None or circuit_breaker_timeout is not None:
            breaker = self.get_circuit_breaker(provider)
            if circuit_breaker_threshold is not None:
                breaker.failure_threshold = circuit_breaker_threshold
            if circuit_breaker_timeout is not None:
                breaker.recovery_timeout = circuit_breaker_timeout

        logger.info(f"Updated configuration for provider {provider}")

    def add_provider(self, provider: str, position: Optional[int] = None) -> None:
        """Add a provider to the resilience system."""
        if provider not in self.providers:
            self.providers.append(provider)

        if self.fallback_manager:
            self.fallback_manager.add_provider(provider, position)

        logger.info(f"Added provider {provider} to resilience system")

    def remove_provider(self, provider: str) -> bool:
        """Remove a provider from the resilience system."""
        if provider in self.providers:
            self.providers.remove(provider)

        if self.fallback_manager:
            self.fallback_manager.remove_provider(provider)

        return True

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the resilience system."""
        healthy_providers = 0
        total_providers = len(self.providers)

        for provider in self.providers:
            if self.get_provider_health(provider):
                healthy_providers += 1

        return {
            "healthy_providers": healthy_providers,
            "total_providers": total_providers,
            "health_percentage": (
                healthy_providers / total_providers * 100 if total_providers > 0 else 0
            ),
            "circuit_breakers_healthy": all(
                breaker.state.value == "closed"
                for breaker in self.circuit_breaker_manager._breakers.values()
            ),
            "fallback_available": self.fallback_manager is not None,
        }
