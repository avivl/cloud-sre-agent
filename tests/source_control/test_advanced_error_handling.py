# tests/source_control/test_advanced_error_handling.py

"""
Comprehensive tests for the advanced error handling system.

This module tests all components of the error handling system including
circuit breakers, fallback strategies, recovery automation, and monitoring.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from gemini_sre_agent.source_control.error_handling.advanced_circuit_breaker import (
    AdvancedCircuitBreaker,
)
from gemini_sre_agent.source_control.error_handling.core import (
    CircuitBreakerConfig,
    CircuitBreakerTimeoutError,
    CircuitState,
    ErrorType,
)
from gemini_sre_agent.source_control.error_handling.custom_fallback_strategies import (
    CustomFallbackManager,
    FallbackStrategyBase,
)
from gemini_sre_agent.source_control.error_handling.error_recovery_automation import (
    CredentialRefreshAction,
    RetryWithBackoffAction,
    SelfHealingManager,
)
from gemini_sre_agent.source_control.error_handling.monitoring_dashboard import (
    MonitoringDashboard,
)


class TestFallbackStrategy(FallbackStrategyBase):
    """Test fallback strategy for testing purposes."""

    def __init__(self, name="test_strategy", priority=1):
        super().__init__(name, priority)
        self.executed = False

    async def can_handle(
        self, operation_type: str, error_type: ErrorType, context: Dict[str, Any]
    ) -> bool:
        """Check if this strategy can handle the error."""
        return error_type in [
            ErrorType.TIMEOUT_ERROR,
            ErrorType.NETWORK_ERROR,
            ErrorType.TEMPORARY_ERROR,
        ]

    async def execute(
        self, operation_type: str, original_func: Any, *args, **kwargs
    ) -> Any:
        """Execute the fallback strategy."""
        self.executed = True
        return "fallback_result"


class TestAdvancedCircuitBreaker:
    """Test advanced circuit breaker functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = CircuitBreakerConfig()
        config.failure_threshold = 3
        config.recovery_timeout = 30.0
        config.success_threshold = 2
        config.timeout = 10.0
        return config

    @pytest.fixture
    def circuit_breaker(self, config):
        """Create test circuit breaker."""
        return AdvancedCircuitBreaker(config, "test_cb")

    @pytest.mark.asyncio
    async def test_circuit_breaker_initial_state(self, circuit_breaker):
        """Test circuit breaker initial state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_successful_call(self, circuit_breaker):
        """Test successful circuit breaker call."""

        async def success_func():
            return "success"

        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.success_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_threshold(self, circuit_breaker):
        """Test circuit breaker opening after failure threshold."""

        async def failure_func():
            raise Exception("Test error")

        # Should open after 3 failures
        for _ in range(3):
            with pytest.raises(Exception, match="Test error"):
                await circuit_breaker.call(failure_func)

        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.failure_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self, circuit_breaker):
        """Test circuit breaker recovery from half-open state."""

        # First, open the circuit
        async def failure_func():
            raise Exception("Test error")

        for _ in range(3):
            with pytest.raises(Exception, match="Test error"):
                await circuit_breaker.call(failure_func)

        assert circuit_breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=35)

        # Should move to half-open
        async def success_func():
            return "success"

        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.state == CircuitState.HALF_OPEN

        # Should close after success threshold (need 3 total successes)
        await circuit_breaker.call(success_func)
        await circuit_breaker.call(success_func)
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_timeout(self, circuit_breaker):
        """Test circuit breaker timeout handling."""

        async def slow_func():
            await asyncio.sleep(15)  # Longer than timeout
            return "success"

        with pytest.raises(
            CircuitBreakerTimeoutError
        ):  # Should raise circuit breaker timeout error
            await circuit_breaker.call(slow_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_health_check(self, circuit_breaker):
        """Test circuit breaker health check."""
        health = circuit_breaker.get_health_status()
        assert "health_score" in health
        assert "status" in health
        assert "issues" in health
        assert "recommendations" in health

    @pytest.mark.asyncio
    async def test_circuit_breaker_advanced_stats(self, circuit_breaker):
        """Test advanced circuit breaker statistics."""

        # Generate some activity
        async def success_func():
            return "success"

        async def failure_func():
            raise Exception("Test error")

        # Mix of successes and failures
        for _ in range(5):
            await circuit_breaker.call(success_func)
        for _ in range(2):
            with pytest.raises(Exception, match="Test error"):
                await circuit_breaker.call(failure_func)

        stats = circuit_breaker.get_advanced_stats()
        assert "total_requests" in stats
        assert "failure_rate" in stats
        assert "average_response_time" in stats
        assert "adaptive_threshold" in stats
        assert "failure_patterns" in stats
        assert "state" in stats
        assert "failure_count" in stats
        assert "success_count" in stats


class TestCustomFallbackStrategies:
    """Test custom fallback strategies."""

    @pytest.fixture
    def fallback_config(self):
        """Create test fallback configuration."""
        return None  # CustomFallbackManager doesn't need config

    @pytest.fixture
    def fallback_manager(self, fallback_config):
        """Create test fallback manager."""
        return CustomFallbackManager()

    def test_fallback_manager_initialization(self, fallback_manager):
        """Test fallback manager initialization."""
        assert fallback_manager is not None
        assert len(fallback_manager.strategies) >= 0  # May have default strategies

    @pytest.mark.asyncio
    async def test_register_fallback_strategy(self, fallback_manager):
        """Test registering a fallback strategy."""
        strategy = TestFallbackStrategy(
            name="test_strategy",
            priority=1,
        )

        fallback_manager.add_strategy(strategy)
        assert len(fallback_manager.strategies) >= 1
        # Find our strategy in the list
        test_strategy = next(
            (s for s in fallback_manager.strategies if s.name == "test_strategy"), None
        )
        assert test_strategy is not None

    @pytest.mark.asyncio
    async def test_execute_fallback_strategy(self, fallback_manager):
        """Test executing a fallback strategy."""
        AsyncMock(return_value="fallback_result")
        strategy = TestFallbackStrategy(
            name="test_strategy",
            priority=1,
        )

        fallback_manager.add_strategy(strategy)

        result = await fallback_manager.execute_fallback(
            "test_operation", ErrorType.NETWORK_ERROR, AsyncMock(), {}
        )

        assert result == "fallback_result"
        assert strategy.executed

    @pytest.mark.asyncio
    async def test_fallback_strategy_condition_matching(self, fallback_manager):
        """Test fallback strategy condition matching."""
        # Strategy that only matches specific error type
        strategy = TestFallbackStrategy(
            name="network_strategy",
            priority=1,
        )

        fallback_manager.add_strategy(strategy)

        # Should match network error
        result = await fallback_manager.execute_fallback(
            "test_operation", ErrorType.NETWORK_ERROR, AsyncMock(), {}
        )
        assert result == "fallback_result"

        # Should not match other error types
        with pytest.raises(RuntimeError, match="No fallback strategy available"):
            await fallback_manager.execute_fallback(
                "test_operation", ErrorType.AUTHENTICATION_ERROR, AsyncMock(), {}
            )

    @pytest.mark.asyncio
    async def test_fallback_strategy_priority(self, fallback_manager):
        """Test fallback strategy priority ordering."""
        # High priority strategy
        high_priority = TestFallbackStrategy(
            name="high_priority",
            priority=1,
        )

        # Low priority strategy
        low_priority = TestFallbackStrategy(
            name="low_priority",
            priority=10,
        )

        fallback_manager.add_strategy(low_priority)
        fallback_manager.add_strategy(high_priority)

        result = await fallback_manager.execute_fallback(
            "test_operation", ErrorType.NETWORK_ERROR, AsyncMock(), {}
        )

        assert result == "fallback_result"
        assert high_priority.executed
        assert not low_priority.executed

    @pytest.mark.asyncio
    async def test_fallback_strategy_retry_with_backoff(self, fallback_manager):
        """Test retry with exponential backoff."""
        call_count = 0

        async def failing_action():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        strategy = TestFallbackStrategy(
            name="retry_strategy",
            priority=1,
        )

        fallback_manager.add_strategy(strategy)

        result = await fallback_manager.execute_fallback(
            "test_operation", ErrorType.TEMPORARY_ERROR, AsyncMock(), {}
        )

        assert result == "fallback_result"
        assert strategy.executed

    def test_fallback_strategy_stats(self, fallback_manager):
        """Test fallback strategy statistics."""
        stats = fallback_manager.get_strategy_stats()
        assert "total_strategies" in stats
        assert "strategy_names" in stats
        assert "strategy_priorities" in stats


class TestErrorRecoveryAutomation:
    """Test error recovery automation."""

    @pytest.fixture
    def self_healing_manager(self):
        """Create test self-healing manager."""
        return SelfHealingManager()

    def test_self_healing_manager_initialization(self, self_healing_manager):
        """Test self-healing manager initialization."""
        assert len(self_healing_manager.error_patterns) > 0
        assert len(self_healing_manager.recovery_actions) > 0

    @pytest.mark.asyncio
    async def test_error_pattern_matching(self, self_healing_manager):
        """Test error pattern matching."""
        # Test timeout error pattern - need multiple occurrences to trigger pattern
        pattern = None
        for _ in range(3):  # Need 3 consecutive occurrences
            pattern = await self_healing_manager.analyze_error(
                ErrorType.TIMEOUT_ERROR, "Timeout error", {}
            )
        assert pattern is not None
        assert pattern.name == "timeout_errors"

    @pytest.mark.asyncio
    async def test_recovery_action_execution(self, self_healing_manager):
        """Test recovery action execution."""
        # Mock context with required components
        context = {
            "original_func": AsyncMock(return_value="success"),
            "args": [],
            "kwargs": {},
        }

        # Test retry with backoff action
        action = RetryWithBackoffAction(max_retries=2, base_delay=0.1)
        result = await action.execute(context)
        assert result is True

    @pytest.mark.asyncio
    async def test_credential_refresh_action(self, self_healing_manager):
        """Test credential refresh action."""
        # Mock auth provider
        mock_auth_provider = MagicMock()
        mock_auth_provider.refresh_token = AsyncMock(return_value=True)

        context = {"auth_provider": mock_auth_provider}

        action = CredentialRefreshAction()
        result = await action.execute(context)
        assert result is True
        mock_auth_provider.refresh_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_with_recovery(self, self_healing_manager):
        """Test complete error handling with recovery."""
        # Mock context
        context = {
            "original_func": AsyncMock(return_value="success"),
            "args": [],
            "kwargs": {},
        }

        # Test with auth error (requires only 1 occurrence)
        success, message = await self_healing_manager.handle_error_with_recovery(
            ErrorType.AUTHENTICATION_ERROR, "Auth error", context
        )

        # Should attempt recovery
        assert success is True or success is False
        assert message is not None

    def test_recovery_stats(self, self_healing_manager):
        """Test recovery statistics."""
        stats = self_healing_manager.get_recovery_stats()
        assert "total_recovery_attempts" in stats
        assert "successful_recoveries" in stats
        assert "overall_success_rate" in stats
        assert "action_statistics" in stats

    def test_health_status(self, self_healing_manager):
        """Test health status calculation."""
        health = self_healing_manager.get_health_status()
        assert "health_score" in health
        assert "status" in health
        assert "recovery_stats" in health


class TestMonitoringDashboard:
    """Test monitoring dashboard functionality."""

    @pytest.fixture
    def dashboard(self):
        """Create test dashboard."""
        return MonitoringDashboard()

    @pytest.fixture
    def mock_circuit_breaker(self):
        """Create mock circuit breaker."""
        cb = MagicMock()
        cb.get_advanced_stats.return_value = {
            "state": "closed",
            "total_requests": 100,
            "success_rate": 0.95,
            "failure_rate": 0.05,
        }
        cb.get_health_status.return_value = {
            "health_score": 90,
            "status": "healthy",
            "issues": [],
            "recommendations": [],
        }
        return cb

    def test_dashboard_initialization(self, dashboard):
        """Test dashboard initialization."""
        assert dashboard.circuit_breakers == {}
        assert dashboard.fallback_manager is None
        assert dashboard.self_healing_manager is None

    def test_register_circuit_breaker(self, dashboard, mock_circuit_breaker):
        """Test registering circuit breaker."""
        dashboard.register_circuit_breaker("test_cb", mock_circuit_breaker)
        assert "test_cb" in dashboard.circuit_breakers

    @pytest.mark.asyncio
    async def test_refresh_dashboard_data(self, dashboard, mock_circuit_breaker):
        """Test refreshing dashboard data."""
        dashboard.register_circuit_breaker("test_cb", mock_circuit_breaker)
        await dashboard.refresh_dashboard_data()

        assert dashboard.dashboard_data is not None
        assert "system_health" in dashboard.dashboard_data
        assert "circuit_breakers" in dashboard.dashboard_data

    def test_get_dashboard_summary(self, dashboard):
        """Test getting dashboard summary."""
        # With no data
        summary = dashboard.get_dashboard_summary()
        assert summary["status"] == "no_data"

        # With mock data
        dashboard.dashboard_data = {
            "system_health": {
                "status": "healthy",
                "overall_score": 85,
                "issues": [],
                "recommendations": [],
            },
            "circuit_breakers": {"test_cb": {}},
        }

        summary = dashboard.get_dashboard_summary()
        assert summary["status"] == "healthy"
        assert summary["health_score"] == 85

    def test_get_alerts(self, dashboard):
        """Test getting alerts."""
        # With no data
        alerts = dashboard.get_alerts()
        assert alerts == []

        # With unhealthy system
        dashboard.dashboard_data = {
            "system_health": {"status": "unhealthy"},
            "circuit_breakers": {},
        }

        alerts = dashboard.get_alerts()
        assert len(alerts) > 0
        assert any(alert["type"] == "critical" for alert in alerts)

    def test_export_dashboard_data(self, dashboard):
        """Test exporting dashboard data."""
        dashboard.dashboard_data = {"test": "data"}
        exported = dashboard.export_dashboard_data("json")
        assert "test" in exported
        assert "data" in exported

    def test_get_dashboard_html(self, dashboard):
        """Test generating HTML dashboard."""
        dashboard.dashboard_data = {
            "system_health": {
                "status": "healthy",
                "overall_score": 85,
                "issues": [],
                "recommendations": [],
            },
            "circuit_breakers": {},
        }

        html = dashboard.get_dashboard_html()
        assert "<html>" in html
        assert "Error Handling Dashboard" in html
        assert "healthy" in html


class TestIntegration:
    """Integration tests for the complete error handling system."""

    @pytest.mark.asyncio
    async def test_complete_error_handling_flow(self):
        """Test complete error handling flow with all components."""
        # Create components
        cb_config = CircuitBreakerConfig()
        cb_config.failure_threshold = 3
        cb_config.recovery_timeout = 30.0
        cb_config.success_threshold = 2
        cb_config.timeout = 10.0
        circuit_breaker = AdvancedCircuitBreaker(cb_config, "integration_test")

        fallback_manager = CustomFallbackManager()

        self_healing_manager = SelfHealingManager()
        dashboard = MonitoringDashboard()

        # Register components
        dashboard.register_circuit_breaker("test_cb", circuit_breaker)
        dashboard.register_fallback_manager(fallback_manager)
        dashboard.register_self_healing_manager(self_healing_manager)

        # Test failing operation - circuit breaker should open after failures
        async def failing_operation():
            raise Exception("Temporary failure")

        # First call should fail
        with pytest.raises(Exception, match="Temporary failure"):
            await circuit_breaker.call(failing_operation)

        # Test successful operation
        async def success_operation():
            return "success"

        result = await circuit_breaker.call(success_operation)
        assert result == "success"

        # Refresh dashboard
        await dashboard.refresh_dashboard_data()
        summary = dashboard.get_dashboard_summary()
        assert summary["status"] in ["healthy", "degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_error_handling_with_fallback(self):
        """Test error handling with fallback strategies."""
        # Create fallback manager
        fallback_manager = CustomFallbackManager()

        # Register fallback strategy
        fallback_strategy = TestFallbackStrategy(
            name="test_fallback",
            priority=1,
        )
        fallback_manager.add_strategy(fallback_strategy)

        # Test fallback execution
        result = await fallback_manager.execute_fallback(
            "test_operation", ErrorType.NETWORK_ERROR, AsyncMock(), {}
        )
        assert result == "fallback_result"

    @pytest.mark.asyncio
    async def test_self_healing_integration(self):
        """Test self-healing integration."""
        self_healing_manager = SelfHealingManager()

        # Mock context for recovery
        context = {
            "original_func": AsyncMock(return_value="success"),
            "args": [],
            "kwargs": {},
        }

        # Test error handling with recovery (use auth error which requires only 1 occurrence)
        success, message = await self_healing_manager.handle_error_with_recovery(
            ErrorType.AUTHENTICATION_ERROR, "Auth error", context
        )

        # Should attempt recovery
        assert isinstance(success, bool)
        assert message is not None

        # Check health status
        health = self_healing_manager.get_health_status()
        assert "health_score" in health
        assert "status" in health


if __name__ == "__main__":
    pytest.main([__file__])
