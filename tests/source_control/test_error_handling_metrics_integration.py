"""
Unit tests for ErrorHandlingMetrics.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from gemini_sre_agent.source_control.error_handling.core import CircuitState, ErrorType
from gemini_sre_agent.source_control.error_handling.metrics_integration import (
    ErrorHandlingMetrics,
)
from gemini_sre_agent.source_control.metrics.core import MetricType


class TestErrorHandlingMetrics:
    """Test cases for ErrorHandlingMetrics."""

    @pytest.fixture
    def mock_metrics_collector(self):
        """Create a mock MetricsCollector."""
        collector = MagicMock()
        collector.record_metric = AsyncMock()
        return collector

    @pytest.fixture
    def error_handling_metrics(self, mock_metrics_collector):
        """Create an ErrorHandlingMetrics instance for testing."""
        return ErrorHandlingMetrics(mock_metrics_collector)

    def test_error_handling_metrics_initialization(self, mock_metrics_collector):
        """Test ErrorHandlingMetrics initialization."""
        metrics = ErrorHandlingMetrics(mock_metrics_collector)
        assert metrics.metrics_collector == mock_metrics_collector
        assert metrics.logger.name == "ErrorHandlingMetrics"

    def test_error_handling_metrics_initialization_default_collector(self):
        """Test ErrorHandlingMetrics initialization with default collector."""
        metrics = ErrorHandlingMetrics()
        assert metrics.metrics_collector is not None
        assert metrics.logger.name == "ErrorHandlingMetrics"

    @pytest.mark.asyncio
    async def test_record_error_basic(
        self, error_handling_metrics, mock_metrics_collector
    ):
        """Test recording a basic error."""
        await error_handling_metrics.record_error(
            error_type=ErrorType.NETWORK_ERROR,
            operation_name="test_operation",
            provider="github",
            is_retryable=True,
        )

        # Verify record_metric was called for error count
        mock_metrics_collector.record_metric.assert_called_with(
            name="source_control_errors_total",
            value=1.0,
            metric_type=MetricType.COUNTER,
            tags={
                "error_type": "network_error",
                "operation": "test_operation",
                "provider": "github",
                "is_retryable": "True",
            },
            unit="errors",
        )

    @pytest.mark.asyncio
    async def test_record_error_with_retry_count(
        self, error_handling_metrics, mock_metrics_collector
    ):
        """Test recording an error with retry count."""
        await error_handling_metrics.record_error(
            error_type=ErrorType.TIMEOUT_ERROR,
            operation_name="test_operation",
            provider="gitlab",
            is_retryable=True,
            retry_count=3,
        )

        # Should be called twice: once for error count, once for retry count
        assert mock_metrics_collector.record_metric.call_count == 2

    @pytest.mark.asyncio
    async def test_record_error_with_details(
        self, error_handling_metrics, mock_metrics_collector
    ):
        """Test recording an error with details."""
        error_details = {"status_code": 500, "message": "Internal server error"}

        await error_handling_metrics.record_error(
            error_type=ErrorType.SERVER_ERROR,
            operation_name="test_operation",
            provider="github",
            is_retryable=True,
            error_details=error_details,
        )

        # Should be called twice: once for error count, once for error details
        assert mock_metrics_collector.record_metric.call_count == 2

    @pytest.mark.asyncio
    async def test_record_circuit_breaker_state_change(
        self, error_handling_metrics, mock_metrics_collector
    ):
        """Test recording circuit breaker state changes."""
        await error_handling_metrics.record_circuit_breaker_state_change(
            circuit_name="test_circuit",
            old_state=CircuitState.CLOSED,
            new_state=CircuitState.OPEN,
            operation_type="file_operations",
        )

        # Should be called twice: once for state change count, once for current state gauge
        assert mock_metrics_collector.record_metric.call_count == 2

    @pytest.mark.asyncio
    async def test_record_retry_attempt(
        self, error_handling_metrics, mock_metrics_collector
    ):
        """Test recording a retry attempt."""
        await error_handling_metrics.record_retry_attempt(
            operation_name="test_operation",
            provider="github",
            attempt_number=2,
            delay_seconds=1.5,
            error_type=ErrorType.RATE_LIMIT_ERROR,
        )

        # Should be called twice: once for retry count, once for delay histogram
        assert mock_metrics_collector.record_metric.call_count == 2

    @pytest.mark.asyncio
    async def test_record_operation_success(
        self, error_handling_metrics, mock_metrics_collector
    ):
        """Test recording a successful operation."""
        await error_handling_metrics.record_operation_success(
            operation_name="test_operation", provider="github", duration_seconds=2.5
        )

        # Should be called twice: once for operation count, once for duration histogram
        assert mock_metrics_collector.record_metric.call_count == 2

    @pytest.mark.asyncio
    async def test_record_operation_success_with_retries(
        self, error_handling_metrics, mock_metrics_collector
    ):
        """Test recording a successful operation with retries."""
        await error_handling_metrics.record_operation_success(
            operation_name="test_operation",
            provider="github",
            duration_seconds=2.5,
            retry_count=3,
        )

        # Should be called three times: operation count, duration histogram, retry count
        assert mock_metrics_collector.record_metric.call_count == 3

    @pytest.mark.asyncio
    async def test_record_operation_failure(
        self, error_handling_metrics, mock_metrics_collector
    ):
        """Test recording a failed operation."""
        await error_handling_metrics.record_operation_failure(
            operation_name="test_operation",
            provider="github",
            duration_seconds=1.0,
            error_type=ErrorType.AUTHENTICATION_ERROR,
        )

        # Should be called twice: once for operation count, once for duration histogram
        assert mock_metrics_collector.record_metric.call_count == 2

    @pytest.mark.asyncio
    async def test_record_operation_failure_with_retries(
        self, error_handling_metrics, mock_metrics_collector
    ):
        """Test recording a failed operation with retries."""
        await error_handling_metrics.record_operation_failure(
            operation_name="test_operation",
            provider="github",
            duration_seconds=1.0,
            error_type=ErrorType.NETWORK_ERROR,
            retry_count=2,
        )

        # Should be called three times: operation count, duration histogram, retry count
        assert mock_metrics_collector.record_metric.call_count == 3

    @pytest.mark.asyncio
    async def test_record_circuit_breaker_stats(
        self, error_handling_metrics, mock_metrics_collector
    ):
        """Test recording circuit breaker statistics."""
        await error_handling_metrics.record_circuit_breaker_stats(
            circuit_name="test_circuit",
            operation_type="file_operations",
            state=CircuitState.OPEN,
            failure_count=5,
            success_count=10,
            total_requests=15,
            failure_rate=0.33,
        )

        # Should be called four times: failures, successes, requests, failure rate
        assert mock_metrics_collector.record_metric.call_count == 4

    @pytest.mark.asyncio
    async def test_record_health_check(
        self, error_handling_metrics, mock_metrics_collector
    ):
        """Test recording health check results."""
        await error_handling_metrics.record_health_check(
            provider="github", is_healthy=True, response_time_ms=150.0
        )

        # Should be called twice: once for health check count, once for response time histogram
        assert mock_metrics_collector.record_metric.call_count == 2

    @pytest.mark.asyncio
    async def test_record_health_check_with_error(
        self, error_handling_metrics, mock_metrics_collector
    ):
        """Test recording health check results with error."""
        await error_handling_metrics.record_health_check(
            provider="github",
            is_healthy=False,
            response_time_ms=5000.0,
            error_message="Connection timeout",
        )

        # Should be called three times: health check count, response time histogram, error count
        assert mock_metrics_collector.record_metric.call_count == 3

    def test_get_error_rate_by_provider(self, error_handling_metrics):
        """Test getting error rate by provider."""
        # This method currently returns 0.0 as a placeholder
        rate = error_handling_metrics.get_error_rate_by_provider("github", 5)
        assert rate == 0.0

    def test_get_circuit_breaker_health(self, error_handling_metrics):
        """Test getting circuit breaker health."""
        # This method currently returns empty dict as a placeholder
        health = error_handling_metrics.get_circuit_breaker_health("test_circuit")
        assert health == {}

    def test_get_operation_metrics(self, error_handling_metrics):
        """Test getting operation metrics."""
        # This method currently returns empty dict as a placeholder
        metrics = error_handling_metrics.get_operation_metrics(
            "test_operation", "github", 5
        )
        assert metrics == {}

    @pytest.mark.asyncio
    async def test_record_error_handles_exception(self, error_handling_metrics):
        """Test that record_error handles exceptions gracefully."""
        # Create a metrics collector that raises an exception
        mock_collector = MagicMock()
        mock_collector.record_metric = AsyncMock(side_effect=Exception("Metrics error"))

        metrics = ErrorHandlingMetrics(mock_collector)

        # Should not raise an exception
        await metrics.record_error(
            error_type=ErrorType.NETWORK_ERROR,
            operation_name="test_operation",
            provider="github",
            is_retryable=True,
        )

    @pytest.mark.asyncio
    async def test_record_circuit_breaker_state_change_handles_exception(
        self, error_handling_metrics
    ):
        """Test that record_circuit_breaker_state_change handles exceptions gracefully."""
        # Create a metrics collector that raises an exception
        mock_collector = MagicMock()
        mock_collector.record_metric = AsyncMock(side_effect=Exception("Metrics error"))

        metrics = ErrorHandlingMetrics(mock_collector)

        # Should not raise an exception
        await metrics.record_circuit_breaker_state_change(
            circuit_name="test_circuit",
            old_state=CircuitState.CLOSED,
            new_state=CircuitState.OPEN,
            operation_type="file_operations",
        )

    @pytest.mark.asyncio
    async def test_record_retry_attempt_handles_exception(self, error_handling_metrics):
        """Test that record_retry_attempt handles exceptions gracefully."""
        # Create a metrics collector that raises an exception
        mock_collector = MagicMock()
        mock_collector.record_metric = AsyncMock(side_effect=Exception("Metrics error"))

        metrics = ErrorHandlingMetrics(mock_collector)

        # Should not raise an exception
        await metrics.record_retry_attempt(
            operation_name="test_operation",
            provider="github",
            attempt_number=1,
            delay_seconds=1.0,
            error_type=ErrorType.RATE_LIMIT_ERROR,
        )

    @pytest.mark.asyncio
    async def test_record_operation_success_handles_exception(
        self, error_handling_metrics
    ):
        """Test that record_operation_success handles exceptions gracefully."""
        # Create a metrics collector that raises an exception
        mock_collector = MagicMock()
        mock_collector.record_metric = AsyncMock(side_effect=Exception("Metrics error"))

        metrics = ErrorHandlingMetrics(mock_collector)

        # Should not raise an exception
        await metrics.record_operation_success(
            operation_name="test_operation", provider="github", duration_seconds=1.0
        )

    @pytest.mark.asyncio
    async def test_record_operation_failure_handles_exception(
        self, error_handling_metrics
    ):
        """Test that record_operation_failure handles exceptions gracefully."""
        # Create a metrics collector that raises an exception
        mock_collector = MagicMock()
        mock_collector.record_metric = AsyncMock(side_effect=Exception("Metrics error"))

        metrics = ErrorHandlingMetrics(mock_collector)

        # Should not raise an exception
        await metrics.record_operation_failure(
            operation_name="test_operation",
            provider="github",
            duration_seconds=1.0,
            error_type=ErrorType.AUTHENTICATION_ERROR,
        )

    @pytest.mark.asyncio
    async def test_record_circuit_breaker_stats_handles_exception(
        self, error_handling_metrics
    ):
        """Test that record_circuit_breaker_stats handles exceptions gracefully."""
        # Create a metrics collector that raises an exception
        mock_collector = MagicMock()
        mock_collector.record_metric = AsyncMock(side_effect=Exception("Metrics error"))

        metrics = ErrorHandlingMetrics(mock_collector)

        # Should not raise an exception
        await metrics.record_circuit_breaker_stats(
            circuit_name="test_circuit",
            operation_type="file_operations",
            state=CircuitState.OPEN,
            failure_count=5,
            success_count=10,
            total_requests=15,
            failure_rate=0.33,
        )

    @pytest.mark.asyncio
    async def test_record_health_check_handles_exception(self, error_handling_metrics):
        """Test that record_health_check handles exceptions gracefully."""
        # Create a metrics collector that raises an exception
        mock_collector = MagicMock()
        mock_collector.record_metric = AsyncMock(side_effect=Exception("Metrics error"))

        metrics = ErrorHandlingMetrics(mock_collector)

        # Should not raise an exception
        await metrics.record_health_check(
            provider="github", is_healthy=True, response_time_ms=150.0
        )
