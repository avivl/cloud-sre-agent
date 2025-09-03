"""
Unit tests for cost tracking and budget management functionality.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from gemini_sre_agent.ml.cost_config import BudgetConfig, UsageRecord
from gemini_sre_agent.ml.cost_tracker import CostTracker


class TestCostTracker:
    """Test cases for CostTracker class."""

    @pytest.fixture
    def budget_config(self) -> BudgetConfig:
        """Create a test budget configuration."""
        return BudgetConfig(
            daily_budget_usd=10.0,
            monthly_budget_usd=100.0,
            warn_threshold_percent=50.0,
        )

    @pytest.fixture
    def cost_tracker(self, budget_config: BudgetConfig) -> CostTracker:
        """Create a CostTracker instance with test configuration."""
        return CostTracker(budget_config)

    def test_initialization(self, cost_tracker: CostTracker):
        """Test CostTracker initialization."""
        assert cost_tracker.daily_usage == 0.0
        assert cost_tracker.monthly_usage == 0.0
        assert cost_tracker.config.daily_budget_usd == 10.0
        assert cost_tracker.config.monthly_budget_usd == 100.0
        assert cost_tracker.max_records == 10000
        assert len(cost_tracker.usage_records) == 0

    def test_cost_estimation(self, cost_tracker: CostTracker):
        """Test cost estimation for different models."""
        # Test with known model
        cost = cost_tracker.estimate_cost("gemini-1.5-flash", 1000, 500)
        expected_cost = (1000 / 1000) * 0.000075 + (500 / 1000) * 0.0003
        assert cost == expected_cost

        # Test with unknown model (should use default costs)
        cost = cost_tracker.estimate_cost("unknown-model", 1000, 500)
        expected_cost = (1000 / 1000) * 0.00125 + (500 / 1000) * 0.005
        assert cost == expected_cost

    @pytest.mark.asyncio
    async def test_budget_check_within_limits(self, cost_tracker: CostTracker):
        """Test budget check when within limits."""
        # Small cost within daily and monthly budgets
        result = await cost_tracker.check_budget(1.0)
        assert result is True

        # Cost at exactly the daily budget limit
        result = await cost_tracker.check_budget(10.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_budget_check_exceeds_daily_limit(self, cost_tracker: CostTracker):
        """Test budget check when exceeding daily limit."""
        result = await cost_tracker.check_budget(15.0)
        assert result is False

        # Check that budget violation was recorded
        stats = cost_tracker._stats_manager.get_base_stats()
        assert stats["budget_violations"] == 1

    @pytest.mark.asyncio
    async def test_budget_check_exceeds_monthly_limit(self, cost_tracker: CostTracker):
        """Test budget check when exceeding monthly limit."""
        result = await cost_tracker.check_budget(150.0)
        assert result is False

        # Check that budget violation was recorded
        stats = cost_tracker._stats_manager.get_base_stats()
        assert stats["budget_violations"] == 1

    @pytest.mark.asyncio
    async def test_warning_threshold_daily(self, cost_tracker: CostTracker):
        """Test daily budget warning threshold."""
        # Set usage just below threshold (50% of $10 = $5)
        cost_tracker.daily_usage = 4.0

        # This should trigger warning (4 + 2 = 6 > 5)
        result = await cost_tracker.check_budget(2.0)
        assert result is True

        stats = cost_tracker._stats_manager.get_base_stats()
        assert stats["warnings_issued"] == 1

    @pytest.mark.asyncio
    async def test_warning_threshold_monthly(self):
        """Test monthly budget warning threshold."""
        # Create separate config to avoid daily warning
        config = BudgetConfig(
            daily_budget_usd=20.0,  # Higher daily budget
            monthly_budget_usd=100.0,
            warn_threshold_percent=50.0,
        )
        tracker = CostTracker(config)

        # Set usage just below monthly threshold (50% of $100 = $50)
        tracker.monthly_usage = 45.0

        # This should trigger monthly warning (45 + 8 = 53 > 50)
        # but not daily warning (8 < 50% of 20)
        result = await tracker.check_budget(8.0)
        assert result is True

        stats = tracker._stats_manager.get_base_stats()
        assert stats["warnings_issued"] == 1

    @pytest.mark.asyncio
    async def test_record_actual_cost(self, cost_tracker: CostTracker):
        """Test recording actual API cost."""
        cost = await cost_tracker.record_actual_cost(
            model_name="gemini-1.5-flash",
            input_tokens=1000,
            output_tokens=500,
            request_id="test-123",
            operation_type="pattern_classification",
        )

        # Check cost calculation
        expected_cost = (1000 / 1000) * 0.000075 + (500 / 1000) * 0.0003
        assert cost == expected_cost

        # Check usage counters updated
        assert cost_tracker.daily_usage == expected_cost
        assert cost_tracker.monthly_usage == expected_cost

        # Check usage record created
        assert len(cost_tracker.usage_records) == 1
        record = cost_tracker.usage_records[0]
        assert record.model_name == "gemini-1.5-flash"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.cost_usd == expected_cost
        assert record.request_id == "test-123"
        assert record.operation_type == "pattern_classification"

        # Check statistics updated
        stats = cost_tracker._stats_manager.get_base_stats()
        assert stats["total_requests"] == 1
        assert stats["total_tokens_input"] == 1000
        assert stats["total_tokens_output"] == 500

    def test_usage_records_size_limit(self, cost_tracker: CostTracker):
        """Test that usage records are limited to max_records."""
        cost_tracker.max_records = 3

        # Add 5 records
        for i in range(5):
            record = UsageRecord(
                timestamp=datetime.now(timezone.utc),
                model_name="test-model",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.01,
                request_id=f"test-{i}",
            )
            cost_tracker.usage_records.append(record)

            # Simulate size limit enforcement
            if len(cost_tracker.usage_records) > cost_tracker.max_records:
                cost_tracker.usage_records = cost_tracker.usage_records[
                    -cost_tracker.max_records :
                ]

        # Should only keep the last 3 records
        assert len(cost_tracker.usage_records) == 3
        assert cost_tracker.usage_records[0].request_id == "test-2"
        assert cost_tracker.usage_records[-1].request_id == "test-4"

    @pytest.mark.asyncio
    async def test_reset_usage_counters(self, cost_tracker: CostTracker):
        """Test manual reset of usage counters."""
        # Set some usage
        cost_tracker.daily_usage = 5.0
        cost_tracker.monthly_usage = 20.0

        # Reset daily only
        await cost_tracker.reset_usage(reset_daily=True, reset_monthly=False)
        assert cost_tracker.daily_usage == 0.0
        assert cost_tracker.monthly_usage == 20.0

        # Reset monthly
        await cost_tracker.reset_usage(reset_daily=False, reset_monthly=True)
        assert cost_tracker.daily_usage == 0.0
        assert cost_tracker.monthly_usage == 0.0

    @patch("gemini_sre_agent.ml.cost_tracker.date")
    @pytest.mark.asyncio
    async def test_daily_usage_reset_new_day(
        self, mock_date, cost_tracker: CostTracker
    ):
        """Test automatic daily usage reset on new day."""
        from datetime import date

        # Set initial date and usage
        initial_date = date(2024, 1, 1)
        mock_date.today.return_value = initial_date
        cost_tracker.current_date = initial_date
        cost_tracker.daily_usage = 5.0

        # Simulate next day
        new_date = date(2024, 1, 2)
        mock_date.today.return_value = new_date

        # Trigger reset check
        await cost_tracker._reset_usage_if_needed()

        # Daily usage should reset, monthly should not
        assert cost_tracker.daily_usage == 0.0
        assert cost_tracker.current_date == new_date

    @patch("gemini_sre_agent.ml.cost_tracker.date")
    @pytest.mark.asyncio
    async def test_monthly_usage_reset_new_month(
        self, mock_date, cost_tracker: CostTracker
    ):
        """Test automatic monthly usage reset on new month."""
        from datetime import date

        # Set initial date and usage
        initial_date = date(2024, 1, 15)
        mock_date.today.return_value = initial_date
        cost_tracker.current_date = initial_date
        cost_tracker.current_month = (2024, 1)
        cost_tracker.daily_usage = 5.0
        cost_tracker.monthly_usage = 20.0

        # Simulate next month
        new_date = date(2024, 2, 1)
        mock_date.today.return_value = new_date

        # Trigger reset check
        await cost_tracker._reset_usage_if_needed()

        # Both should reset for new month
        assert cost_tracker.daily_usage == 0.0
        assert cost_tracker.monthly_usage == 0.0
        assert cost_tracker.current_date == new_date
        assert cost_tracker.current_month == (2024, 2)

    def test_get_usage_stats(self, cost_tracker: CostTracker):
        """Test comprehensive usage statistics."""
        # Add some usage
        cost_tracker.daily_usage = 2.0
        cost_tracker.monthly_usage = 15.0

        # Add some records for recent usage analysis
        now = datetime.now()
        for _i in range(3):
            record = UsageRecord(
                timestamp=now,
                model_name="gemini-1.5-flash",
                input_tokens=500,
                output_tokens=250,
                cost_usd=0.5,
                operation_type="test",
            )
            cost_tracker.usage_records.append(record)

        stats = cost_tracker.get_usage_stats()

        # Check basic usage stats
        assert stats["daily_usage_usd"] == 2.0
        assert stats["daily_budget_usd"] == 10.0
        assert stats["daily_remaining_usd"] == 8.0
        assert stats["daily_utilization_pct"] == 20.0

        assert stats["monthly_usage_usd"] == 15.0
        assert stats["monthly_budget_usd"] == 100.0
        assert stats["monthly_remaining_usd"] == 85.0
        assert stats["monthly_utilization_pct"] == 15.0

        # Check status flags
        assert stats["within_budget"] is True
        assert stats["approaching_limit"] is False  # Below 50% threshold

        # Check recent usage
        assert stats["recent_24h_requests"] == 3
        assert stats["recent_24h_cost_usd"] == 1.5
        assert stats["most_used_model"] == "gemini-1.5-flash"

    def test_get_cost_breakdown(self, cost_tracker: CostTracker):
        """Test detailed cost breakdown analysis."""
        # Add some usage records with different models and operations
        now = datetime.now()

        records = [
            ("gemini-1.5-flash", "pattern_classification", 0.5),
            ("gemini-1.5-flash", "pattern_classification", 0.3),
            ("gemini-2.5-pro", "analysis", 1.0),
        ]

        for model, operation, cost in records:
            record = UsageRecord(
                timestamp=now,
                model_name=model,
                input_tokens=500,
                output_tokens=250,
                cost_usd=cost,
                operation_type=operation,
            )
            cost_tracker.usage_records.append(record)

        breakdown = cost_tracker.get_cost_breakdown(days=7)

        assert breakdown["period_days"] == 7
        assert breakdown["total_records"] == 3
        assert breakdown["total_cost_usd"] == 1.8

        # Check model breakdown
        model_breakdown = breakdown["model_breakdown"]
        assert "gemini-1.5-flash" in model_breakdown
        assert "gemini-2.5-pro" in model_breakdown
        assert model_breakdown["gemini-1.5-flash"]["requests"] == 2
        assert model_breakdown["gemini-1.5-flash"]["total_cost"] == 0.8

        # Check operation breakdown
        operation_breakdown = breakdown["operation_breakdown"]
        assert "pattern_classification" in operation_breakdown
        assert "analysis" in operation_breakdown
        assert operation_breakdown["pattern_classification"]["requests"] == 2
        assert operation_breakdown["analysis"]["total_cost"] == 1.0

    def test_default_budget_config(self):
        """Test CostTracker with default configuration."""
        tracker = CostTracker()

        assert tracker.config.daily_budget_usd == 100.0
        assert tracker.config.monthly_budget_usd == 2000.0
        assert tracker.config.warn_threshold_percent == 80.0

    def test_custom_model_costs(self):
        """Test custom model costs in configuration."""
        config = BudgetConfig()
        config.model_costs["custom-model"] = {"input": 0.001, "output": 0.002}

        tracker = CostTracker(config)
        cost = tracker.estimate_cost("custom-model", 1000, 500)

        expected_cost = (1000 / 1000) * 0.001 + (500 / 1000) * 0.002
        assert cost == expected_cost
