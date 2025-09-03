"""
Unit tests for adaptive rate limiting functionality.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_sre_agent.ml.adaptive_rate_limiter import AdaptiveRateLimiter
from gemini_sre_agent.ml.rate_limiter_config import (
    CircuitState,
    RateLimiterConfig,
    UrgencyLevel,
)


class TestAdaptiveRateLimiter:
    """Test cases for AdaptiveRateLimiter class."""

    @pytest.fixture
    def config(self) -> RateLimiterConfig:
        """Create a test rate limiter configuration."""
        return RateLimiterConfig(
            max_consecutive_errors=2,
            base_backoff_seconds=1,
            max_backoff_seconds=5,
            circuit_open_duration_seconds=10,
            recovery_test_interval_seconds=5,
            rate_limit_reset_minutes=1,
        )

    @pytest.fixture
    def rate_limiter(self, config: RateLimiterConfig) -> AdaptiveRateLimiter:
        """Create an AdaptiveRateLimiter instance with test configuration."""
        return AdaptiveRateLimiter(config)

    @pytest.fixture
    def cost_tracker(self) -> AsyncMock:
        """Create a mock cost tracker."""
        mock_tracker = AsyncMock()
        mock_tracker.check_budget = AsyncMock(return_value=True)
        return mock_tracker

    def test_initialization(self, rate_limiter: AdaptiveRateLimiter):
        """Test AdaptiveRateLimiter initialization."""
        assert rate_limiter.consecutive_errors == 0
        assert rate_limiter.current_backoff_seconds == 1
        assert rate_limiter.circuit_state == CircuitState.CLOSED
        assert rate_limiter.rate_limit_hit is False
        assert rate_limiter.last_rate_limit_time is None
        assert rate_limiter.successful_requests == 0
        assert rate_limiter.total_requests == 0

    def test_initialization_with_default_config(self):
        """Test initialization with default configuration."""
        rate_limiter = AdaptiveRateLimiter()
        assert rate_limiter.config.max_consecutive_errors == 3
        assert rate_limiter.config.base_backoff_seconds == 1
        assert rate_limiter.config.max_backoff_seconds == 60

    @pytest.mark.asyncio
    async def test_should_allow_request_normal_operation(
        self, rate_limiter: AdaptiveRateLimiter, cost_tracker: AsyncMock
    ):
        """Test normal request allowing when no issues."""
        result = await rate_limiter.should_allow_request(
            UrgencyLevel.MEDIUM, cost_tracker
        )
        assert result is True
        assert rate_limiter.total_requests == 1

    @pytest.mark.asyncio
    async def test_budget_exceeded_allows_critical(
        self, rate_limiter: AdaptiveRateLimiter, cost_tracker: AsyncMock
    ):
        """Test that critical requests are allowed even when budget exceeded."""
        cost_tracker.check_budget.return_value = False

        result = await rate_limiter.should_allow_request(
            UrgencyLevel.CRITICAL, cost_tracker
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_budget_exceeded_rejects_low_urgency(
        self, rate_limiter: AdaptiveRateLimiter, cost_tracker: AsyncMock
    ):
        """Test that low urgency requests are rejected when budget exceeded."""
        cost_tracker.check_budget.return_value = False

        result = await rate_limiter.should_allow_request(UrgencyLevel.LOW, cost_tracker)
        assert result is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_allows_critical(
        self, rate_limiter: AdaptiveRateLimiter, cost_tracker: AsyncMock
    ):
        """Test that critical requests are allowed even when circuit is open."""
        # Force circuit to open
        rate_limiter.circuit_state = CircuitState.OPEN

        result = await rate_limiter.should_allow_request(
            UrgencyLevel.CRITICAL, cost_tracker
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_rejects_medium(
        self, rate_limiter: AdaptiveRateLimiter, cost_tracker: AsyncMock
    ):
        """Test that medium urgency requests are rejected when circuit is open."""
        # Force circuit to open
        rate_limiter.circuit_state = CircuitState.OPEN

        result = await rate_limiter.should_allow_request(
            UrgencyLevel.MEDIUM, cost_tracker
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_rate_limit_active_skips_low_urgency(
        self, rate_limiter: AdaptiveRateLimiter, cost_tracker: AsyncMock
    ):
        """Test that low urgency requests are skipped when rate limited."""
        # Set rate limit as active
        rate_limiter.rate_limit_hit = True
        rate_limiter.last_rate_limit_time = datetime.now()

        result = await rate_limiter.should_allow_request(UrgencyLevel.LOW, cost_tracker)
        assert result is False

    @pytest.mark.asyncio
    async def test_rate_limit_allows_high_urgency(
        self, rate_limiter: AdaptiveRateLimiter, cost_tracker: AsyncMock
    ):
        """Test that high urgency requests are allowed even when rate limited."""
        # Set rate limit as active
        rate_limiter.rate_limit_hit = True
        rate_limiter.last_rate_limit_time = datetime.now()

        result = await rate_limiter.should_allow_request(
            UrgencyLevel.HIGH, cost_tracker
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_backoff_applied_with_errors(
        self, rate_limiter: AdaptiveRateLimiter, cost_tracker: AsyncMock
    ):
        """Test that backoff is applied when there are consecutive errors."""
        rate_limiter.consecutive_errors = 1
        rate_limiter.current_backoff_seconds = 2

        with patch("asyncio.sleep") as mock_sleep:
            result = await rate_limiter.should_allow_request(
                UrgencyLevel.MEDIUM, cost_tracker
            )

        assert result is True
        mock_sleep.assert_called_once_with(2)

    @pytest.mark.asyncio
    async def test_record_success_resets_errors(
        self, rate_limiter: AdaptiveRateLimiter
    ):
        """Test that recording success resets error counters."""
        rate_limiter.consecutive_errors = 3
        rate_limiter.current_backoff_seconds = 8

        await rate_limiter.record_success()

        assert rate_limiter.consecutive_errors == 0
        assert rate_limiter.current_backoff_seconds == 1
        assert rate_limiter.successful_requests == 1
        assert rate_limiter.rate_limit_hit is False

    @pytest.mark.asyncio
    async def test_record_success_closes_half_open_circuit(
        self, rate_limiter: AdaptiveRateLimiter
    ):
        """Test that success closes a half-open circuit."""
        rate_limiter.circuit_state = CircuitState.HALF_OPEN
        rate_limiter.circuit_opened_at = datetime.now()

        await rate_limiter.record_success()

        assert rate_limiter.circuit_state == CircuitState.CLOSED
        assert rate_limiter.circuit_opened_at is None

    @pytest.mark.asyncio
    async def test_record_rate_limit_error(self, rate_limiter: AdaptiveRateLimiter):
        """Test recording rate limit error."""
        await rate_limiter.record_rate_limit_error()

        assert rate_limiter.rate_limit_hit is True
        assert rate_limiter.last_rate_limit_time is not None
        assert rate_limiter.consecutive_errors == 1
        assert rate_limiter.current_backoff_seconds == 2  # Doubled from initial 1

    @pytest.mark.asyncio
    async def test_record_api_error(self, rate_limiter: AdaptiveRateLimiter):
        """Test recording API error."""
        await rate_limiter.record_api_error()

        assert rate_limiter.consecutive_errors == 1
        assert rate_limiter.current_backoff_seconds == 2

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_max_errors(
        self, rate_limiter: AdaptiveRateLimiter
    ):
        """Test that circuit breaker opens after max consecutive errors."""
        assert rate_limiter.config.max_consecutive_errors == 2

        # First error
        await rate_limiter.record_api_error()
        assert rate_limiter.circuit_state == CircuitState.CLOSED

        # Second error should open circuit
        await rate_limiter.record_api_error()
        assert rate_limiter.circuit_state == CircuitState.OPEN
        assert rate_limiter.circuit_opened_at is not None

    @patch("gemini_sre_agent.ml.adaptive_rate_limiter.datetime")
    def test_circuit_state_transitions_to_half_open(
        self, mock_datetime: MagicMock, rate_limiter: AdaptiveRateLimiter
    ):
        """Test circuit breaker transitions from OPEN to HALF_OPEN."""
        # Set up initial state
        initial_time = datetime.now()
        later_time = initial_time + timedelta(seconds=15)  # After duration

        mock_datetime.now.return_value = later_time

        rate_limiter.circuit_state = CircuitState.OPEN
        rate_limiter.circuit_opened_at = initial_time

        # Call method that checks circuit state
        rate_limiter._update_circuit_state()

        assert rate_limiter.circuit_state == CircuitState.HALF_OPEN
        assert rate_limiter.last_recovery_attempt == later_time

    def test_exponential_backoff(self, rate_limiter: AdaptiveRateLimiter):
        """Test exponential backoff calculation."""
        rate_limiter.current_backoff_seconds = 2
        rate_limiter._update_backoff()
        assert rate_limiter.current_backoff_seconds == 4

        rate_limiter._update_backoff()
        assert rate_limiter.current_backoff_seconds == 5  # Max is 5 in test config

        # Should not exceed max
        rate_limiter._update_backoff()
        assert rate_limiter.current_backoff_seconds == 5

    def test_rate_limit_expiration(self, rate_limiter: AdaptiveRateLimiter):
        """Test that rate limit expires after duration."""
        # Set rate limit as active but expired
        rate_limiter.rate_limit_hit = True
        rate_limiter.last_rate_limit_time = datetime.now() - timedelta(minutes=2)

        assert rate_limiter._is_rate_limit_active() is False
        assert rate_limiter._get_rate_limit_reset_seconds() == 0

    def test_rate_limit_reset_calculation(self, rate_limiter: AdaptiveRateLimiter):
        """Test rate limit reset time calculation."""
        # Set rate limit as recently active
        rate_limiter.rate_limit_hit = True
        rate_limiter.last_rate_limit_time = datetime.now() - timedelta(seconds=30)

        assert rate_limiter._is_rate_limit_active() is True
        reset_seconds = rate_limiter._get_rate_limit_reset_seconds()
        assert 25 <= reset_seconds <= 35  # Should be around 30 seconds

    def test_get_status_metrics(self, rate_limiter: AdaptiveRateLimiter):
        """Test status metrics retrieval."""
        # Set up some state
        rate_limiter.total_requests = 10
        rate_limiter.successful_requests = 8
        rate_limiter.consecutive_errors = 1
        rate_limiter.current_backoff_seconds = 4

        status = rate_limiter.get_status()

        assert status["circuit_state"] == "CLOSED"
        assert status["consecutive_errors"] == 1
        assert status["current_backoff_seconds"] == 4
        assert status["total_requests"] == 10
        assert status["successful_requests"] == 8
        assert status["success_rate_pct"] == 80.0
        assert status["rate_limit_active"] is False

    def test_rate_limit_active_status(self, rate_limiter: AdaptiveRateLimiter):
        """Test rate limit active status in metrics."""
        # Set active rate limit
        rate_limiter.rate_limit_hit = True
        rate_limiter.last_rate_limit_time = datetime.now() - timedelta(seconds=30)

        status = rate_limiter.get_status()

        assert status["rate_limit_active"] is True
        assert status["rate_limit_reset_in_seconds"] > 0

    @pytest.mark.asyncio
    async def test_complex_scenario_budget_and_circuit(
        self, rate_limiter: AdaptiveRateLimiter, cost_tracker: AsyncMock
    ):
        """Test complex scenario with budget exceeded and circuit issues."""
        # Set up both budget exceeded and circuit open
        cost_tracker.check_budget.return_value = False
        rate_limiter.circuit_state = CircuitState.OPEN

        # Critical should still be allowed
        result = await rate_limiter.should_allow_request(
            UrgencyLevel.CRITICAL, cost_tracker
        )
        assert result is True

        # Medium should be rejected
        result = await rate_limiter.should_allow_request(
            UrgencyLevel.MEDIUM, cost_tracker
        )
        assert result is False

    def test_success_rate_calculation_edge_cases(self):
        """Test success rate calculation with edge cases."""
        from gemini_sre_agent.ml.rate_limiter_config import RateLimiterMetrics

        # Zero requests
        assert RateLimiterMetrics.calculate_success_rate(0, 0) == 0.0

        # All successful
        assert RateLimiterMetrics.calculate_success_rate(10, 10) == 100.0

        # No successes
        assert RateLimiterMetrics.calculate_success_rate(0, 10) == 0.0

        # Partial success
        assert RateLimiterMetrics.calculate_success_rate(7, 10) == 70.0

    def test_critical_override_logic(self):
        """Test critical override decision logic."""
        from gemini_sre_agent.ml.rate_limiter_config import RateLimiterMetrics

        # Non-critical should not override
        metrics = RateLimiterMetrics(success_rate=0.3)
        assert RateLimiterMetrics.should_allow_critical_override(metrics) is False

        # Critical with budget exceeded should override
        metrics = RateLimiterMetrics(success_rate=0.8)
        assert RateLimiterMetrics.should_allow_critical_override(metrics) is True

        # Critical with circuit open should override
        metrics = RateLimiterMetrics(success_rate=0.6)
        assert RateLimiterMetrics.should_allow_critical_override(metrics) is True

        # Critical with no issues should not need override
        metrics = RateLimiterMetrics(success_rate=0.9)
        assert RateLimiterMetrics.should_allow_critical_override(metrics) is True

    def test_rate_limit_skip_logic(self):
        """Test rate limit skip decision logic."""
        from gemini_sre_agent.ml.rate_limiter_config import RateLimiterMetrics

        # No rate limit active - should not skip
        metrics = RateLimiterMetrics(rate_limited_requests=0, total_requests=10)
        assert RateLimiterMetrics.should_skip_for_rate_limit(metrics) is False

        # Rate limit active, low urgency - should skip
        metrics = RateLimiterMetrics(rate_limited_requests=9, total_requests=10)
        assert RateLimiterMetrics.should_skip_for_rate_limit(metrics) is True

        # Rate limit active, medium urgency - should skip
        metrics = RateLimiterMetrics(rate_limited_requests=8, total_requests=10)
        assert RateLimiterMetrics.should_skip_for_rate_limit(metrics) is True

        # Rate limit active, high urgency - should not skip
        metrics = RateLimiterMetrics(rate_limited_requests=5, total_requests=10)
        assert RateLimiterMetrics.should_skip_for_rate_limit(metrics) is False

        # Rate limit active, critical urgency - should not skip
        metrics = RateLimiterMetrics(rate_limited_requests=3, total_requests=10)
        assert RateLimiterMetrics.should_skip_for_rate_limit(metrics) is False
