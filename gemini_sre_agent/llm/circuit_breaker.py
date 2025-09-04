# gemini_sre_agent/llm/circuit_breaker.py

"""
Circuit breaker implementation for provider resilience.

This module provides circuit breaker functionality to prevent cascading failures
and improve system resilience when dealing with unreliable LLM providers.
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from .error_config import CircuitBreakerConfig


class CircuitStatus(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if system has recovered


@dataclass
class CircuitState:
    """State information for circuit breaker."""
    status: CircuitStatus = CircuitStatus.CLOSED
    failure_count: int = 0
    success_count: int = 0
    call_count: int = 0
    last_state_change: float = 0.0


class CircuitBreaker:
    """Circuit breaker pattern for provider resilience."""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self._states: Dict[str, CircuitState] = {}
        self._lock = asyncio.Lock()

    async def allow_request(self, provider_id: str) -> bool:
        """Check if circuit allows requests for the provider."""
        async with self._lock:
            state = self._get_state(provider_id)
            
            if state.status == CircuitStatus.CLOSED:
                return True
            elif state.status == CircuitStatus.OPEN:
                if time.time() - state.last_state_change > self.config.reset_timeout:
                    self._set_half_open(provider_id)
                    return True
                return False
            else:  # HALF_OPEN
                return state.call_count < self.config.half_open_max_calls

    async def record_success(self, provider_id: str) -> None:
        """Record successful request."""
        async with self._lock:
            state = self._get_state(provider_id)
            if state.status == CircuitStatus.HALF_OPEN:
                state.success_count += 1
                if state.success_count >= self.config.half_open_max_calls:
                    self._set_closed(provider_id)

    async def record_failure(self, provider_id: str) -> None:
        """Record failed request."""
        async with self._lock:
            state = self._get_state(provider_id)
            if state.status == CircuitStatus.CLOSED:
                state.failure_count += 1
                if state.failure_count >= self.config.failure_threshold:
                    self._set_open(provider_id)
            elif state.status == CircuitStatus.HALF_OPEN:
                self._set_open(provider_id)

    def _get_state(self, provider_id: str) -> CircuitState:
        """Get circuit state for provider."""
        if provider_id not in self._states:
            self._states[provider_id] = CircuitState()
        return self._states[provider_id]

    def _set_closed(self, provider_id: str) -> None:
        """Set circuit to closed state."""
        state = self._get_state(provider_id)
        state.status = CircuitStatus.CLOSED
        state.failure_count = 0
        state.success_count = 0
        state.call_count = 0
        state.last_state_change = time.time()

    def _set_open(self, provider_id: str) -> None:
        """Set circuit to open state."""
        state = self._get_state(provider_id)
        state.status = CircuitStatus.OPEN
        state.last_state_change = time.time()

    def _set_half_open(self, provider_id: str) -> None:
        """Set circuit to half-open state."""
        state = self._get_state(provider_id)
        state.status = CircuitStatus.HALF_OPEN
        state.call_count = 0
        state.success_count = 0
        state.last_state_change = time.time()

    async def get_state(self, provider_id: str) -> CircuitStatus:
        """Get current circuit state for provider."""
        async with self._lock:
            return self._get_state(provider_id).status

    async def get_stats(self, provider_id: str) -> Dict[str, Any]:
        """Get circuit breaker statistics for provider."""
        async with self._lock:
            state = self._get_state(provider_id)
            return {
                "status": state.status.value,
                "failure_count": state.failure_count,
                "success_count": state.success_count,
                "call_count": state.call_count,
                "last_state_change": state.last_state_change
            }
