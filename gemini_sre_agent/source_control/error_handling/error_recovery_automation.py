# gemini_sre_agent/source_control/error_handling/error_recovery_automation.py

"""
Automated error recovery and self-healing capabilities.

This module provides intelligent error recovery mechanisms that can automatically
detect, diagnose, and recover from common failure scenarios in source control operations.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .core import CircuitState, ErrorType


class ErrorPattern:
    """Represents a pattern of errors for automated recovery."""

    def __init__(
        self,
        name: str,
        error_types: List[ErrorType],
        conditions: Dict[str, Any],
        recovery_action: str,
        priority: int = 1,
    ):
        self.name = name
        self.error_types = error_types
        self.conditions = conditions
        self.recovery_action = recovery_action
        self.priority = priority
        self.last_seen: Optional[datetime] = None
        self.occurrence_count = 0


class RecoveryAction:
    """Base class for recovery actions."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"RecoveryAction.{name}")

    async def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if this recovery action can be executed."""
        return True

    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute the recovery action."""
        raise NotImplementedError

    def get_priority(self) -> int:
        """Get the priority of this action (lower = higher priority)."""
        return 1


class RetryWithBackoffAction(RecoveryAction):
    """Recovery action that retries with exponential backoff."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        super().__init__("retry_with_backoff")
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute retry with backoff."""
        func = context.get("original_func")
        args = context.get("args", [])
        kwargs = context.get("kwargs", {})

        if not func:
            return False

        for attempt in range(self.max_retries):
            try:
                delay = self.base_delay * (2**attempt)
                await asyncio.sleep(delay)

                await func(*args, **kwargs)
                self.logger.info(f"Recovery successful on attempt {attempt + 1}")
                return True
            except Exception as e:
                self.logger.warning(f"Recovery attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    return False

        return False


class CredentialRefreshAction(RecoveryAction):
    """Recovery action that refreshes authentication credentials."""

    def __init__(self):
        super().__init__("credential_refresh")

    async def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if credentials can be refreshed."""
        return "auth_provider" in context

    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute credential refresh."""
        auth_provider = context.get("auth_provider")
        if not auth_provider:
            return False

        try:
            # Attempt to refresh credentials
            if hasattr(auth_provider, "refresh_token"):
                await auth_provider.refresh_token()
                self.logger.info("Credentials refreshed successfully")
                return True
            else:
                self.logger.warning("Auth provider does not support token refresh")
                return False
        except Exception as e:
            self.logger.error(f"Failed to refresh credentials: {e}")
            return False


class ConnectionResetAction(RecoveryAction):
    """Recovery action that resets network connections."""

    def __init__(self):
        super().__init__("connection_reset")

    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute connection reset."""
        client = context.get("client")
        if not client:
            return False

        try:
            # Close and recreate connection
            if hasattr(client, "close"):
                await client.close()

            if hasattr(client, "reconnect"):
                await client.reconnect()

            self.logger.info("Connection reset successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to reset connection: {e}")
            return False


class CircuitBreakerResetAction(RecoveryAction):
    """Recovery action that resets circuit breakers."""

    def __init__(self):
        super().__init__("circuit_breaker_reset")

    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute circuit breaker reset."""
        circuit_breaker = context.get("circuit_breaker")
        if not circuit_breaker:
            return False

        try:
            # Reset circuit breaker to closed state
            circuit_breaker.state = CircuitState.CLOSED
            circuit_breaker.failure_count = 0
            circuit_breaker.success_count = 0
            circuit_breaker.last_failure_time = None

            self.logger.info("Circuit breaker reset successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to reset circuit breaker: {e}")
            return False


class ConfigurationUpdateAction(RecoveryAction):
    """Recovery action that updates configuration based on error patterns."""

    def __init__(self):
        super().__init__("configuration_update")

    async def execute(self, context: Dict[str, Any]) -> bool:
        """Execute configuration update."""
        config_manager = context.get("config_manager")
        if not config_manager:
            return False

        try:
            # Update configuration based on error patterns
            error_type = context.get("error_type")
            if error_type == ErrorType.TIMEOUT_ERROR:
                # Increase timeout values
                await self._increase_timeouts(config_manager)
            elif error_type == ErrorType.RATE_LIMIT_ERROR:
                # Increase retry delays
                await self._increase_retry_delays(config_manager)

            self.logger.info("Configuration updated successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to update configuration: {e}")
            return False

    async def _increase_timeouts(self, config_manager: Any) -> None:
        """Increase timeout values in configuration."""
        if hasattr(config_manager, "update_timeout"):
            await config_manager.update_timeout(multiplier=1.5)

    async def _increase_retry_delays(self, config_manager: Any) -> None:
        """Increase retry delays in configuration."""
        if hasattr(config_manager, "update_retry_delay"):
            await config_manager.update_retry_delay(multiplier=2.0)


class SelfHealingManager:
    """Manages automated error recovery and self-healing."""

    def __init__(self):
        self.logger = logging.getLogger("SelfHealingManager")
        self.error_patterns: List[ErrorPattern] = []
        self.recovery_actions: List[RecoveryAction] = []
        self.recovery_history: List[Dict[str, Any]] = []
        self._initialize_default_patterns()
        self._initialize_default_actions()

    def _initialize_default_patterns(self) -> None:
        """Initialize default error patterns."""
        self.error_patterns = [
            ErrorPattern(
                name="timeout_errors",
                error_types=[ErrorType.TIMEOUT_ERROR],
                conditions={"consecutive_count": 3, "time_window": 300},
                recovery_action="retry_with_backoff",
                priority=1,
            ),
            ErrorPattern(
                name="auth_errors",
                error_types=[ErrorType.AUTHENTICATION_ERROR],
                conditions={"consecutive_count": 1},
                recovery_action="credential_refresh",
                priority=1,
            ),
            ErrorPattern(
                name="network_errors",
                error_types=[ErrorType.NETWORK_ERROR],
                conditions={"consecutive_count": 2, "time_window": 60},
                recovery_action="connection_reset",
                priority=2,
            ),
            ErrorPattern(
                name="rate_limit_errors",
                error_types=[ErrorType.RATE_LIMIT_ERROR],
                conditions={"consecutive_count": 1},
                recovery_action="configuration_update",
                priority=3,
            ),
            ErrorPattern(
                name="circuit_breaker_open",
                error_types=[ErrorType.TEMPORARY_ERROR],
                conditions={"consecutive_count": 1},
                recovery_action="circuit_breaker_reset",
                priority=1,
            ),
        ]

    def _initialize_default_actions(self) -> None:
        """Initialize default recovery actions."""
        self.recovery_actions = [
            RetryWithBackoffAction(),
            CredentialRefreshAction(),
            ConnectionResetAction(),
            CircuitBreakerResetAction(),
            ConfigurationUpdateAction(),
        ]

    def add_error_pattern(self, pattern: ErrorPattern) -> None:
        """Add a custom error pattern."""
        self.error_patterns.append(pattern)
        self.logger.info(f"Added error pattern: {pattern.name}")

    def add_recovery_action(self, action: RecoveryAction) -> None:
        """Add a custom recovery action."""
        self.recovery_actions.append(action)
        self.logger.info(f"Added recovery action: {action.name}")

    async def analyze_error(
        self,
        error_type: ErrorType,
        error_message: str,
        context: Dict[str, Any],
    ) -> Optional[ErrorPattern]:
        """Analyze an error and find matching patterns."""
        now = datetime.now()

        for pattern in self.error_patterns:
            if error_type not in pattern.error_types:
                continue

            # Increment occurrence count first
            pattern.occurrence_count += 1
            pattern.last_seen = now

            # Check if pattern conditions are met
            if await self._check_pattern_conditions(pattern, now):
                self.logger.info(f"Error pattern matched: {pattern.name}")
                return pattern

        return None

    async def _check_pattern_conditions(
        self, pattern: ErrorPattern, current_time: datetime
    ) -> bool:
        """Check if pattern conditions are met."""
        conditions = pattern.conditions

        # Check consecutive count
        consecutive_count = conditions.get("consecutive_count", 1)
        self.logger.debug(
            f"Pattern {pattern.name}: occurrence_count={pattern.occurrence_count}, consecutive_count={consecutive_count}"
        )
        if pattern.occurrence_count < consecutive_count - 1:
            self.logger.debug(f"Pattern {pattern.name}: consecutive count not met")
            return False

        # Check time window
        time_window = conditions.get("time_window")
        if time_window and pattern.last_seen:
            time_diff = (current_time - pattern.last_seen).total_seconds()
            if time_diff > time_window:
                pattern.occurrence_count = 0  # Reset count
                self.logger.debug(
                    f"Pattern {pattern.name}: time window exceeded, resetting count"
                )
                return False

        self.logger.debug(f"Pattern {pattern.name}: conditions met")
        return True

    async def execute_recovery(
        self,
        pattern: ErrorPattern,
        context: Dict[str, Any],
    ) -> bool:
        """Execute recovery actions for a matched pattern."""
        recovery_action_name = pattern.recovery_action
        action = self._find_recovery_action(recovery_action_name)

        if not action:
            self.logger.warning(f"Recovery action not found: {recovery_action_name}")
            return False

        if not await action.can_execute(context):
            self.logger.warning(f"Recovery action cannot execute: {action.name}")
            return False

        try:
            self.logger.info(f"Executing recovery action: {action.name}")
            success = await action.execute(context)

            # Record recovery attempt
            self.recovery_history.append(
                {
                    "timestamp": datetime.now(),
                    "pattern": pattern.name,
                    "action": action.name,
                    "success": success,
                    "context": context,
                }
            )

            if success:
                self.logger.info(f"Recovery action {action.name} succeeded")
                pattern.occurrence_count = 0  # Reset count on success
            else:
                self.logger.warning(f"Recovery action {action.name} failed")

            return success

        except Exception as e:
            self.logger.error(f"Recovery action {action.name} raised exception: {e}")
            return False

    def _find_recovery_action(self, action_name: str) -> Optional[RecoveryAction]:
        """Find a recovery action by name."""
        for action in self.recovery_actions:
            if action.name == action_name:
                return action
        return None

    async def handle_error_with_recovery(
        self,
        error_type: ErrorType,
        error_message: str,
        context: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """Handle an error with automated recovery."""
        # Analyze error for patterns
        pattern = await self.analyze_error(error_type, error_message, context)

        if not pattern:
            self.logger.debug("No error pattern matched for recovery")
            return False, None

        # Execute recovery
        success = await self.execute_recovery(pattern, context)

        if success:
            return True, f"Recovery successful using {pattern.recovery_action}"
        else:
            return False, f"Recovery failed using {pattern.recovery_action}"

    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get statistics about recovery operations."""
        total_attempts = len(self.recovery_history)
        successful_attempts = sum(1 for r in self.recovery_history if r["success"])

        # Group by action
        action_stats = {}
        for record in self.recovery_history:
            action = record["action"]
            if action not in action_stats:
                action_stats[action] = {"total": 0, "successful": 0}
            action_stats[action]["total"] += 1
            if record["success"]:
                action_stats[action]["successful"] += 1

        # Calculate success rates
        for action in action_stats:
            total = action_stats[action]["total"]
            successful = action_stats[action]["successful"]
            action_stats[action]["success_rate"] = (
                successful / total if total > 0 else 0
            )

        return {
            "total_recovery_attempts": total_attempts,
            "successful_recoveries": successful_attempts,
            "overall_success_rate": (
                successful_attempts / total_attempts if total_attempts > 0 else 0
            ),
            "action_statistics": action_stats,
            "pattern_occurrences": {
                p.name: p.occurrence_count for p in self.error_patterns
            },
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the self-healing system."""
        stats = self.get_recovery_stats()

        # Calculate health score
        health_score = 100
        if stats["overall_success_rate"] < 0.5:
            health_score -= 30
        elif stats["overall_success_rate"] < 0.8:
            health_score -= 15

        # Check for patterns with high occurrence counts
        for pattern in self.error_patterns:
            if pattern.occurrence_count > 10:
                health_score -= 10

        return {
            "health_score": max(0, health_score),
            "status": (
                "healthy"
                if health_score > 80
                else "degraded" if health_score > 50 else "unhealthy"
            ),
            "recovery_stats": stats,
            "active_patterns": [
                p.name for p in self.error_patterns if p.occurrence_count > 0
            ],
        }
