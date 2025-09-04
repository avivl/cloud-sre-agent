"""Fallback manager for automatic provider switching."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from .error_classifier import ErrorClassifier

logger = logging.getLogger(__name__)


class FallbackManager:
    """Manages fallback between different providers when failures occur."""

    def __init__(
        self,
        providers: List[str],
        error_classifier: Optional[ErrorClassifier] = None,
        fallback_timeout: float = 30.0,
    ):
        """Initialize the fallback manager.

        Args:
            providers: List of provider names in order of preference
            error_classifier: Error classifier for determining fallback triggers
            fallback_timeout: Timeout for fallback operations
        """
        self.providers = providers
        self.error_classifier = error_classifier or ErrorClassifier()
        self.fallback_timeout = fallback_timeout

        # Provider health tracking
        self._provider_health: Dict[str, bool] = {
            provider: True for provider in providers
        }
        self._provider_failures: Dict[str, int] = {
            provider: 0 for provider in providers
        }
        self._provider_last_failure: Dict[str, float] = {}

        # Statistics
        self._total_requests = 0
        self._total_fallbacks = 0
        self._provider_usage: Dict[str, int] = {provider: 0 for provider in providers}
        self._fallback_successes = 0

    async def execute_with_fallback(
        self,
        provider_funcs: Dict[str, Callable],
        *args,
        **kwargs,
    ) -> Tuple[Any, str]:
        """Execute a function with automatic fallback between providers.

        Args:
            provider_funcs: Dictionary mapping provider names to their functions
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Tuple of (result, provider_used)

        Raises:
            Exception: If all providers fail
        """
        self._total_requests += 1

        # Get providers to try in order of preference
        # Use providers from provider_funcs, but respect health status
        providers_to_try = []
        for provider in self.providers:
            if provider in provider_funcs:
                providers_to_try.append(provider)
        
        # Add any additional providers from provider_funcs that aren't in self.providers
        for provider in provider_funcs:
            if provider not in providers_to_try:
                providers_to_try.append(provider)

        if not providers_to_try:
            raise Exception("No providers available for fallback")

        last_exception = None

        for provider in providers_to_try:
            # Skip unhealthy providers (unless they're the only ones available)
            if not self._provider_health.get(provider, True) and len(providers_to_try) > 1:
                logger.debug(f"Skipping unhealthy provider: {provider}")
                continue

            try:
                logger.debug(f"Attempting request with provider: {provider}")

                # Execute with timeout
                result = await asyncio.wait_for(
                    self._execute_provider_function(
                        provider_funcs[provider], *args, **kwargs
                    ),
                    timeout=self.fallback_timeout,
                )

                # Success - update statistics and health
                self._on_provider_success(provider)
                logger.info(f"Request succeeded with provider: {provider}")

                return result, provider

            except asyncio.TimeoutError:
                logger.warning(
                    f"Provider {provider} timed out after {self.fallback_timeout}s"
                )
                self._on_provider_failure(provider, "timeout")
                last_exception = Exception(f"Provider {provider} timed out")

            except Exception as e:
                logger.warning(f"Provider {provider} failed: {e}")

                # Classify the error
                error_category = self.error_classifier.classify_error(e)

                # Check if this error should trigger fallback
                if self.error_classifier.should_fallback(error_category):
                    self._on_provider_failure(provider, str(e))
                    last_exception = e
                    continue
                else:
                    # Error doesn't warrant fallback, re-raise
                    raise e

        # All providers failed
        self._total_fallbacks += 1
        logger.error("All providers failed during fallback")

        if last_exception:
            raise last_exception
        else:
            raise Exception("All providers failed")

    async def _execute_provider_function(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """Execute a provider function."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    def _get_healthy_providers(self) -> List[str]:
        """Get list of healthy providers in order of preference."""
        healthy = []

        for provider in self.providers:
            if self._provider_health.get(provider, True):
                healthy.append(provider)

        return healthy

    def _on_provider_success(self, provider: str) -> None:
        """Handle successful provider operation."""
        self._provider_health[provider] = True
        self._provider_failures[provider] = 0
        self._provider_usage[provider] += 1

    def _on_provider_failure(self, provider: str, error: str) -> None:
        """Handle failed provider operation."""
        import time

        self._provider_failures[provider] += 1
        self._provider_last_failure[provider] = time.time()

        # Mark provider as unhealthy after multiple failures
        if self._provider_failures[provider] >= 3:
            self._provider_health[provider] = False
            logger.warning(
                f"Provider {provider} marked as unhealthy after {self._provider_failures[provider]} failures"
            )

    def mark_provider_healthy(self, provider: str) -> None:
        """Manually mark a provider as healthy."""
        self._provider_health[provider] = True
        self._provider_failures[provider] = 0
        logger.info(f"Provider {provider} manually marked as healthy")

    def mark_provider_unhealthy(self, provider: str) -> None:
        """Manually mark a provider as unhealthy."""
        self._provider_health[provider] = False
        logger.info(f"Provider {provider} manually marked as unhealthy")

    def get_provider_health(self, provider: str) -> bool:
        """Get health status of a provider."""
        return self._provider_health.get(provider, True)

    def get_provider_stats(self, provider: str) -> Dict[str, Any]:
        """Get statistics for a specific provider."""
        usage = self._provider_usage.get(provider, 0)
        failures = self._provider_failures.get(provider, 0)
        total_successes = max(0, usage - failures)
        
        return {
            "provider": provider,
            "healthy": self._provider_health.get(provider, True),
            "failures": failures,
            "total_failures": failures,
            "usage": usage,
            "total_requests": self._total_requests,
            "total_successes": total_successes,
            "success_rate": (total_successes / max(1, usage)) * 100 if usage > 0 else 0.0,
            "average_response_time": 0.0,  # Not implemented in this version
            "last_failure": self._provider_last_failure.get(provider),
        }

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all providers."""
        sum(self._provider_usage.values())

        return {
            "total_requests": self._total_requests,
            "total_fallbacks": self._total_fallbacks,
            "fallback_successes": self._fallback_successes,
            "fallback_rate": (
                self._total_fallbacks / self._total_requests * 100
                if self._total_requests > 0
                else 0
            ),
            "providers": {
                provider: self.get_provider_stats(provider)
                for provider in self.providers
            },
            "healthy_providers": len(self._get_healthy_providers()),
            "total_providers": len(self.providers),
        }

    def reset_provider_stats(self, provider: Optional[str] = None) -> None:
        """Reset statistics for a provider or all providers."""
        if provider:
            self._provider_failures[provider] = 0
            self._provider_usage[provider] = 0
            if provider in self._provider_last_failure:
                del self._provider_last_failure[provider]
            logger.info(f"Reset stats for provider: {provider}")
        else:
            self._provider_failures = {p: 0 for p in self.providers}
            self._provider_usage = {p: 0 for p in self.providers}
            self._provider_last_failure = {}
            self._total_requests = 0
            self._total_fallbacks = 0
            self._fallback_successes = 0
            logger.info("Reset stats for all providers")

    def add_provider(self, provider: str, position: Optional[int] = None) -> None:
        """Add a new provider to the fallback chain.

        Args:
            provider: Provider name to add
            position: Position to insert at (None for end)
        """
        if provider in self.providers:
            logger.warning(f"Provider {provider} already exists")
            return

        if position is None:
            self.providers.append(provider)
        else:
            self.providers.insert(position, provider)

        # Initialize stats for new provider
        self._provider_health[provider] = True
        self._provider_failures[provider] = 0
        self._provider_usage[provider] = 0

        logger.info(f"Added provider {provider} to fallback chain")

    def remove_provider(self, provider: str) -> bool:
        """Remove a provider from the fallback chain.

        Args:
            provider: Provider name to remove

        Returns:
            True if provider was removed, False if not found
        """
        if provider not in self.providers:
            return False

        self.providers.remove(provider)

        # Clean up stats
        if provider in self._provider_health:
            del self._provider_health[provider]
        if provider in self._provider_failures:
            del self._provider_failures[provider]
        if provider in self._provider_usage:
            del self._provider_usage[provider]
        if provider in self._provider_last_failure:
            del self._provider_last_failure[provider]

        logger.info(f"Removed provider {provider} from fallback chain")
        return True

    def reorder_providers(self, new_order: List[str]) -> None:
        """Reorder providers in the fallback chain.

        Args:
            new_order: New order of provider names
        """
        # Validate that all current providers are in the new order
        if set(new_order) != set(self.providers):
            raise ValueError("New order must contain all current providers")

        self.providers = new_order
        logger.info(f"Reordered providers: {new_order}")
