# gemini_sre_agent/source_control/error_handling/advanced_circuit_breaker.py

"""
Advanced circuit breaker implementation with adaptive thresholds and intelligent state management.

This module provides an enhanced circuit breaker with:
- Adaptive failure thresholds based on historical data
- Custom state transition callbacks
- Performance-based circuit opening
- Intelligent recovery strategies
- Multi-dimensional failure analysis
"""

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from .core import (
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerTimeoutError,
    CircuitState,
    ErrorType,
)
from .metrics_integration import ErrorHandlingMetrics


class AdaptiveThresholds:
    """Manages adaptive thresholds based on historical performance data."""

    def __init__(self, base_threshold: int = 5, learning_window: int = 100):
        self.base_threshold = base_threshold
        self.learning_window = learning_window
        self.recent_failures = deque(maxlen=learning_window)
        self.recent_successes = deque(maxlen=learning_window)
        self.performance_history = deque(maxlen=learning_window)

    def add_failure(self, error_type: ErrorType, response_time: float) -> None:
        """Record a failure for threshold calculation."""
        self.recent_failures.append(
            {
                "timestamp": datetime.now(),
                "error_type": error_type,
                "response_time": response_time,
            }
        )

    def add_success(self, response_time: float) -> None:
        """Record a success for threshold calculation."""
        self.recent_successes.append(
            {
                "timestamp": datetime.now(),
                "response_time": response_time,
            }
        )
        self.performance_history.append(response_time)

    def get_adaptive_threshold(self) -> int:
        """Calculate adaptive failure threshold based on historical data."""
        if len(self.recent_failures) < 10:
            return self.base_threshold

        # Calculate failure rate over recent window
        recent_window = datetime.now() - timedelta(minutes=5)
        recent_failures = [
            f for f in self.recent_failures if f["timestamp"] > recent_window
        ]
        recent_successes = [
            s for s in self.recent_successes if s["timestamp"] > recent_window
        ]

        total_recent = len(recent_failures) + len(recent_successes)
        if total_recent == 0:
            return self.base_threshold

        failure_rate = len(recent_failures) / total_recent

        # Adjust threshold based on failure rate
        if failure_rate > 0.5:  # High failure rate
            return max(3, self.base_threshold // 2)
        elif failure_rate < 0.1:  # Low failure rate
            return min(20, self.base_threshold * 2)
        else:
            return self.base_threshold

    def get_performance_threshold(self) -> float:
        """Calculate performance-based threshold for circuit opening."""
        if len(self.performance_history) < 5:
            return 5.0  # Default 5 second threshold

        # Calculate 95th percentile response time
        sorted_times = sorted(self.performance_history)
        percentile_95_index = int(len(sorted_times) * 0.95)
        return sorted_times[percentile_95_index] * 2  # 2x 95th percentile


class StateTransitionCallback:
    """Handles custom state transition callbacks."""

    def __init__(self):
        self.callbacks: Dict[Tuple[CircuitState, CircuitState], List[Callable]] = {}

    def register_callback(
        self,
        from_state: CircuitState,
        to_state: CircuitState,
        callback: Callable[[str, CircuitState, CircuitState], None],
    ) -> None:
        """Register a callback for state transitions."""
        key = (from_state, to_state)
        if key not in self.callbacks:
            self.callbacks[key] = []
        self.callbacks[key].append(callback)

    async def execute_callbacks(
        self, name: str, from_state: CircuitState, to_state: CircuitState
    ) -> None:
        """Execute all registered callbacks for a state transition."""
        key = (from_state, to_state)
        if key in self.callbacks:
            for callback in self.callbacks[key]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(name, from_state, to_state)
                    else:
                        callback(name, from_state, to_state)
                except Exception as e:
                    logging.getLogger("StateTransitionCallback").error(
                        f"Error in state transition callback: {e}"
                    )


class MultiDimensionalFailureAnalyzer:
    """Analyzes failures across multiple dimensions for intelligent circuit management."""

    def __init__(self):
        self.failure_patterns = {
            "timeout_errors": deque(maxlen=50),
            "network_errors": deque(maxlen=50),
            "auth_errors": deque(maxlen=50),
            "rate_limit_errors": deque(maxlen=50),
            "server_errors": deque(maxlen=50),
        }

    def analyze_failure(
        self, error_type: ErrorType, response_time: float
    ) -> Dict[str, Any]:
        """Analyze a failure and return insights."""
        now = datetime.now()

        # Categorize error
        if error_type == ErrorType.TIMEOUT_ERROR:
            self.failure_patterns["timeout_errors"].append(now)
        elif error_type == ErrorType.NETWORK_ERROR:
            self.failure_patterns["network_errors"].append(now)
        elif error_type == ErrorType.AUTHENTICATION_ERROR:
            self.failure_patterns["auth_errors"].append(now)
        elif error_type == ErrorType.RATE_LIMIT_ERROR:
            self.failure_patterns["rate_limit_errors"].append(now)
        else:
            self.failure_patterns["server_errors"].append(now)

        # Analyze patterns
        analysis = {
            "error_type": error_type,
            "response_time": response_time,
            "patterns": self._analyze_patterns(),
            "recommendations": self._get_recommendations(),
        }

        return analysis

    def _analyze_patterns(self) -> Dict[str, Any]:
        """Analyze failure patterns across dimensions."""
        now = datetime.now()
        recent_window = timedelta(minutes=5)

        patterns = {}
        for pattern_name, failures in self.failure_patterns.items():
            recent_failures = [f for f in failures if now - f < recent_window]
            patterns[pattern_name] = {
                "count": len(recent_failures),
                "frequency": len(recent_failures) / 5,  # per minute
                "trend": self._calculate_trend(failures, recent_window),
            }

        return patterns

    def _calculate_trend(self, failures: deque, window: timedelta) -> str:
        """Calculate trend direction for failures."""
        if len(failures) < 4:
            return "stable"

        now = datetime.now()
        recent = [f for f in failures if now - f < window]
        older = [f for f in failures if now - f >= window and now - f < window * 2]

        if len(recent) > len(older) * 1.5:
            return "increasing"
        elif len(recent) < len(older) * 0.5:
            return "decreasing"
        else:
            return "stable"

    def _get_recommendations(self) -> List[str]:
        """Get recommendations based on failure analysis."""
        recommendations = []
        patterns = self._analyze_patterns()

        if patterns.get("timeout_errors", {}).get("frequency", 0) > 2:
            recommendations.append("Consider increasing timeout values")

        if patterns.get("rate_limit_errors", {}).get("frequency", 0) > 1:
            recommendations.append("Implement exponential backoff for rate limits")

        if patterns.get("network_errors", {}).get("frequency", 0) > 3:
            recommendations.append("Check network connectivity and retry policies")

        if patterns.get("auth_errors", {}).get("count", 0) > 0:
            recommendations.append("Verify authentication credentials")

        return recommendations


class AdvancedCircuitBreaker:
    """Advanced circuit breaker with adaptive thresholds and intelligent state management."""

    def __init__(
        self,
        config: CircuitBreakerConfig,
        name: str = "default",
        metrics: Optional[ErrorHandlingMetrics] = None,
    ):
        self.config = config
        self.name = name
        self.logger = logging.getLogger(f"AdvancedCircuitBreaker.{name}")
        self.metrics = metrics

        # Core circuit state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None

        # Advanced features
        self.adaptive_thresholds = AdaptiveThresholds(
            base_threshold=config.failure_threshold
        )
        self.state_callbacks = StateTransitionCallback()
        self.failure_analyzer = MultiDimensionalFailureAnalyzer()

        # Performance tracking
        self.response_times = deque(maxlen=100)
        self.consecutive_failures = 0
        self.consecutive_successes = 0

        # Statistics
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0
        self.state_transitions = 0

    def register_state_callback(
        self,
        from_state: CircuitState,
        to_state: CircuitState,
        callback: Callable[[str, CircuitState, CircuitState], None],
    ) -> None:
        """Register a callback for state transitions."""
        self.state_callbacks.register_callback(from_state, to_state, callback)

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        if self.state != CircuitState.OPEN:
            return False

        if self.last_failure_time is None:
            return True

        # Use adaptive recovery timeout based on failure patterns
        base_timeout = self.config.recovery_timeout
        failure_analysis = self.failure_analyzer._analyze_patterns()

        # Increase timeout for persistent issues
        if failure_analysis.get("server_errors", {}).get("frequency", 0) > 5:
            timeout_multiplier = 2.0
        elif failure_analysis.get("network_errors", {}).get("frequency", 0) > 3:
            timeout_multiplier = 1.5
        else:
            timeout_multiplier = 1.0

        return (datetime.now() - self.last_failure_time).total_seconds() >= (
            base_timeout * timeout_multiplier
        )

    async def _transition_state(self, new_state: CircuitState) -> None:
        """Transition to a new state with callbacks."""
        if self.state == new_state:
            return

        old_state = self.state
        self.state = new_state
        self.state_transitions += 1

        self.logger.info(
            f"Circuit breaker {self.name} transitioned from {old_state.value} to {new_state.value}"
        )

        # Execute state transition callbacks
        await self.state_callbacks.execute_callbacks(self.name, old_state, new_state)

        # Record state change in metrics
        if self.metrics:
            await self.metrics.record_circuit_breaker_state_change(
                self.name, old_state, new_state, "unknown"
            )

    async def _record_success(self, response_time: float) -> None:
        """Record a successful operation with performance tracking."""
        self.success_count += 1
        self.total_successes += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = datetime.now()

        # Track response time
        self.response_times.append(response_time)
        self.adaptive_thresholds.add_success(response_time)

        if self.state == CircuitState.HALF_OPEN:
            # Use adaptive success threshold
            success_threshold = max(3, self.config.success_threshold)
            if self.success_count >= success_threshold:
                await self._transition_state(CircuitState.CLOSED)
                self.failure_count = 0
                self.success_count = 0
                self.logger.info(
                    f"Circuit breaker {self.name} closed after {self.success_count} successful operations"
                )

    async def _record_failure(
        self, error_type: ErrorType, response_time: float
    ) -> None:
        """Record a failed operation with multi-dimensional analysis."""
        self.failure_count += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = datetime.now()

        # Analyze failure
        failure_analysis = self.failure_analyzer.analyze_failure(
            error_type, response_time
        )
        self.adaptive_thresholds.add_failure(error_type, response_time)

        # Log analysis and recommendations
        if failure_analysis["recommendations"]:
            self.logger.warning(
                f"Failure analysis for {self.name}: {failure_analysis['recommendations']}"
            )

        # Use adaptive threshold for circuit opening
        adaptive_threshold = self.adaptive_thresholds.get_adaptive_threshold()

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= adaptive_threshold:
                await self._transition_state(CircuitState.OPEN)
                self.logger.warning(
                    f"Circuit breaker {self.name} opened after {self.failure_count} failures "
                    f"(adaptive threshold: {adaptive_threshold})"
                )
        elif self.state == CircuitState.HALF_OPEN:
            await self._transition_state(CircuitState.OPEN)
            self.success_count = 0
            self.logger.warning(
                f"Circuit breaker {self.name} reopened after failure in half-open state"
            )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with advanced circuit breaker protection."""
        start_time = time.time()
        self.total_requests += 1

        # Check if circuit should be reset
        if self._should_attempt_reset():
            await self._transition_state(CircuitState.HALF_OPEN)
            self.success_count = 0
            self.logger.info(f"Circuit breaker {self.name} moved to half-open state")

        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            if self.metrics:
                duration = time.time() - start_time
                await self.metrics.record_operation_failure(
                    "circuit_breaker_open",
                    "unknown",
                    duration,
                    ErrorType.TEMPORARY_ERROR,
                    0,
                )
            raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is open")

        try:
            # Execute the function with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs), timeout=self.config.timeout
            )

            response_time = time.time() - start_time
            await self._record_success(response_time)

            # Record success in metrics
            if self.metrics:
                await self.metrics.record_operation_success(
                    "circuit_breaker_call", "unknown", response_time, 0
                )

            return result

        except asyncio.TimeoutError as e:
            response_time = time.time() - start_time
            await self._record_failure(ErrorType.TIMEOUT_ERROR, response_time)

            # Record timeout in metrics
            if self.metrics:
                await self.metrics.record_operation_failure(
                    "circuit_breaker_timeout",
                    "unknown",
                    response_time,
                    ErrorType.TIMEOUT_ERROR,
                    0,
                )

            raise CircuitBreakerTimeoutError(
                f"Operation timed out after {self.config.timeout}s"
            ) from e
        except Exception as e:
            response_time = time.time() - start_time

            # Classify error type
            error_type = self._classify_error(e)
            await self._record_failure(error_type, response_time)

            # Record failure in metrics
            if self.metrics:
                await self.metrics.record_operation_failure(
                    "circuit_breaker_failure",
                    "unknown",
                    response_time,
                    error_type,
                    0,
                )

            raise e from e

    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error type for analysis."""
        error_str = str(error).lower()

        if "timeout" in error_str or isinstance(error, asyncio.TimeoutError):
            return ErrorType.TIMEOUT_ERROR
        elif "network" in error_str or "connection" in error_str:
            return ErrorType.NETWORK_ERROR
        elif "auth" in error_str or "unauthorized" in error_str:
            return ErrorType.AUTHENTICATION_ERROR
        elif "rate limit" in error_str or "quota" in error_str:
            return ErrorType.RATE_LIMIT_ERROR
        elif "server error" in error_str or "internal" in error_str:
            return ErrorType.SERVER_ERROR
        else:
            return ErrorType.UNKNOWN_ERROR

    def get_advanced_stats(self) -> Dict[str, Any]:
        """Get comprehensive circuit breaker statistics."""
        patterns = self.failure_analyzer._analyze_patterns()

        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "state_transitions": self.state_transitions,
            "adaptive_threshold": self.adaptive_thresholds.get_adaptive_threshold(),
            "performance_threshold": self.adaptive_thresholds.get_performance_threshold(),
            "average_response_time": (
                sum(self.response_times) / len(self.response_times)
                if self.response_times
                else 0
            ),
            "failure_patterns": patterns,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
            "last_success_time": (
                self.last_success_time.isoformat() if self.last_success_time else None
            ),
            "failure_rate": self.total_failures / max(self.total_requests, 1),
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status with recommendations."""
        stats = self.get_advanced_stats()
        patterns = stats["failure_patterns"]

        health_score = 100
        issues = []

        # Check failure rate
        if stats["failure_rate"] > 0.5:
            health_score -= 30
            issues.append("High failure rate")
        elif stats["failure_rate"] > 0.2:
            health_score -= 15
            issues.append("Elevated failure rate")

        # Check response times
        if stats["average_response_time"] > stats["performance_threshold"]:
            health_score -= 20
            issues.append("Slow response times")

        # Check failure patterns
        for pattern_name, pattern_data in patterns.items():
            if pattern_data["frequency"] > 2:
                health_score -= 10
                issues.append(f"Frequent {pattern_name}")

        # Check consecutive failures
        if stats["consecutive_failures"] > 5:
            health_score -= 25
            issues.append("Many consecutive failures")

        return {
            "health_score": max(0, health_score),
            "status": (
                "healthy"
                if health_score > 80
                else "degraded" if health_score > 50 else "unhealthy"
            ),
            "issues": issues,
            "recommendations": self.failure_analyzer._get_recommendations(),
            "stats": stats,
        }
