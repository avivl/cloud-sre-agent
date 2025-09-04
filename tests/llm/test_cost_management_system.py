"""
Comprehensive tests for the Dynamic Cost Management System.

Tests all components: DynamicCostManager, CostOptimizer, BudgetManager, and CostAnalytics.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from gemini_sre_agent.llm.budget_manager import (
    BudgetConfig,
    BudgetManager,
    BudgetPeriod,
    EnforcementPolicy,
)
from gemini_sre_agent.llm.cost_analytics import AnalyticsConfig, CostAnalytics
from gemini_sre_agent.llm.cost_management import (
    CostManagementConfig,
    DynamicCostManager,
    ModelPricing,
    ProviderType,
    UsageRecord,
)
from gemini_sre_agent.llm.cost_management_integration import (
    IntegratedCostManager,
    create_default_cost_manager,
)
from gemini_sre_agent.llm.cost_optimizer import (
    CostOptimizer,
    OptimizationConfig,
)


class TestDynamicCostManager:
    """Test the DynamicCostManager class."""

    @pytest.fixture
    def cost_manager(self):
        """Create a DynamicCostManager instance for testing."""
        config = CostManagementConfig(
            cache_duration_minutes=5,
            refresh_interval_minutes=1,
            enable_auto_refresh=False,
            fallback_pricing=True,
        )
        return DynamicCostManager(config)

    @pytest.mark.asyncio
    async def test_estimate_cost(self, cost_manager):
        """Test cost estimation."""
        # Mock pricing data
        cost_manager.pricing_cache = {
            "openai": {
                "gpt-4": ModelPricing(
                    input_cost_per_1k=0.03,
                    output_cost_per_1k=0.06,
                    last_updated=datetime.now(),
                )
            }
        }

        cost = await cost_manager.estimate_cost("openai", "gpt-4", 1000, 500)
        assert cost == 0.06  # (1000 * 0.03 + 500 * 0.06) / 1000

    @pytest.mark.asyncio
    async def test_estimate_cost_fallback(self, cost_manager):
        """Test cost estimation with fallback pricing."""
        # No pricing data in cache
        cost_manager.pricing_cache = {}

        cost = await cost_manager.estimate_cost("openai", "gpt-4", 1000, 500)
        # Should use fallback pricing
        assert cost > 0

    @pytest.mark.asyncio
    async def test_refresh_pricing_data(self, cost_manager):
        """Test pricing data refresh."""
        with patch.object(cost_manager, "_fetch_provider_pricing") as mock_fetch:
            mock_fetch.return_value = {
                "openai": {
                    "gpt-4": ModelPricing(
                        input_cost_per_1k=0.03,
                        output_cost_per_1k=0.06,
                        last_updated=datetime.now(),
                    )
                }
            }

            await cost_manager.refresh_pricing_data()

            assert "openai" in cost_manager.pricing_cache
            assert "gpt-4" in cost_manager.pricing_cache["openai"]

    def test_get_pricing_info(self, cost_manager):
        """Test getting pricing information."""
        # Add some pricing data
        cost_manager.pricing_cache = {
            "openai": {
                "gpt-4": ModelPricing(
                    input_cost_per_1k=0.03,
                    output_cost_per_1k=0.06,
                    last_updated=datetime.now(),
                )
            }
        }

        pricing = cost_manager.get_pricing_info("openai", "gpt-4")
        assert pricing is not None
        assert pricing.input_cost_per_1k == 0.03
        assert pricing.output_cost_per_1k == 0.06

        # Test non-existent provider/model
        pricing = cost_manager.get_pricing_info("nonexistent", "model")
        assert pricing is None

    def test_is_pricing_stale(self, cost_manager):
        """Test pricing staleness check."""
        # Fresh pricing
        fresh_pricing = ModelPricing(
            input_cost_per_1k=0.03, output_cost_per_1k=0.06, last_updated=datetime.now()
        )
        assert not cost_manager._is_pricing_stale(fresh_pricing)

        # Stale pricing
        stale_pricing = ModelPricing(
            input_cost_per_1k=0.03,
            output_cost_per_1k=0.06,
            last_updated=datetime.now() - timedelta(hours=2),
        )
        assert cost_manager._is_pricing_stale(stale_pricing)


class TestCostOptimizer:
    """Test the CostOptimizer class."""

    @pytest.fixture
    def cost_optimizer(self):
        """Create a CostOptimizer instance for testing."""
        config = OptimizationConfig(
            enable_optimization=True,
            cost_weight=0.4,
            performance_weight=0.3,
            quality_weight=0.3,
            min_confidence_threshold=0.7,
        )
        return CostOptimizer(config)

    @pytest.mark.asyncio
    async def test_get_optimal_provider(self, cost_optimizer):
        """Test getting optimal provider."""
        with patch.object(cost_optimizer, "_get_available_providers") as mock_providers:
            mock_providers.return_value = ["openai", "anthropic", "google"]

            with patch.object(cost_optimizer, "_evaluate_provider") as mock_evaluate:
                mock_evaluate.side_effect = [
                    (0.8, 0.9, 0.85),  # openai
                    (0.7, 0.95, 0.8),  # anthropic
                    (0.9, 0.8, 0.75),  # google
                ]

                provider, model, score = await cost_optimizer.get_optimal_provider(
                    "text", 1000, 500
                )

                assert provider in ["openai", "anthropic", "google"]
                assert model is not None
                assert score > 0

    def test_calculate_optimization_score(self, cost_optimizer):
        """Test optimization score calculation."""
        score = cost_optimizer._calculate_optimization_score(0.8, 0.9, 0.85)
        expected = 0.4 * 0.8 + 0.3 * 0.9 + 0.3 * 0.85
        assert abs(score - expected) < 0.001

    def test_get_optimization_recommendations(self, cost_optimizer):
        """Test getting optimization recommendations."""
        # Mock usage data
        usage_data = {
            "openai": {"cost": 100, "requests": 50, "success_rate": 0.95},
            "anthropic": {"cost": 80, "requests": 40, "success_rate": 0.98},
        }

        recommendations = cost_optimizer.get_optimization_recommendations(usage_data)

        assert isinstance(recommendations, list)
        # Should recommend switching to cheaper provider if quality is similar
        if recommendations:
            assert "provider_switch" in [rec["type"] for rec in recommendations]


class TestBudgetManager:
    """Test the BudgetManager class."""

    @pytest.fixture
    def budget_manager(self):
        """Create a BudgetManager instance for testing."""
        config = BudgetConfig(
            budget_limit=100.0,
            budget_period=BudgetPeriod.MONTHLY,
            enforcement_policy=EnforcementPolicy.WARN,
            auto_reset=True,
        )
        return BudgetManager(config)

    def test_add_usage_record(self, budget_manager):
        """Test adding usage records."""
        record = UsageRecord(
            timestamp=datetime.now(),
            provider=ProviderType.OPENAI,
            model="gpt-4",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.06,
            success=True,
            response_time_ms=1500,
            tokens_used=1500,
        )

        budget_manager.add_usage_record(record)

        assert len(budget_manager.usage_records) == 1
        assert budget_manager.get_current_spend() == 0.06

    def test_budget_status(self, budget_manager):
        """Test budget status calculation."""
        # Add some usage
        record = UsageRecord(
            timestamp=datetime.now(),
            provider=ProviderType.OPENAI,
            model="gpt-4",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=50.0,
            success=True,
            response_time_ms=1500,
            tokens_used=1500,
        )
        budget_manager.add_usage_record(record)

        status = budget_manager.get_budget_status()

        assert status.current_spend == 50.0
        assert status.remaining_budget == 50.0
        assert status.usage_percentage == 50.0
        assert status.status == "healthy"

    def test_can_make_request(self, budget_manager):
        """Test request budget check."""
        # Test within budget
        can_make, message = budget_manager.can_make_request(10.0)
        assert can_make
        assert "within budget" in message

        # Test exceeding budget
        can_make, message = budget_manager.can_make_request(150.0)
        assert not can_make
        assert "exceed budget" in message

    def test_budget_thresholds(self, budget_manager):
        """Test budget threshold alerts."""
        # Add usage to trigger 50% threshold
        record = UsageRecord(
            timestamp=datetime.now(),
            provider=ProviderType.OPENAI,
            model="gpt-4",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=50.0,
            success=True,
            response_time_ms=1500,
            tokens_used=1500,
        )
        budget_manager.add_usage_record(record)

        # Should have triggered 50% threshold alert
        alerts = budget_manager.get_recent_alerts(1)
        assert len(alerts) > 0
        assert any(alert.threshold_percentage == 0.5 for alert in alerts)

    def test_spending_breakdown(self, budget_manager):
        """Test spending breakdown."""
        # Add usage records
        records = [
            UsageRecord(
                timestamp=datetime.now(),
                provider=ProviderType.OPENAI,
                model="gpt-4",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=30.0,
                success=True,
                response_time_ms=1500,
                tokens_used=1500,
            ),
            UsageRecord(
                timestamp=datetime.now(),
                provider=ProviderType.ANTHROPIC,
                model="claude-3",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=20.0,
                success=True,
                response_time_ms=1200,
                tokens_used=1500,
            ),
        ]

        for record in records:
            budget_manager.add_usage_record(record)

        breakdown = budget_manager.get_spending_breakdown()

        assert breakdown["total_spend"] == 50.0
        assert "openai" in breakdown["by_provider"]
        assert "anthropic" in breakdown["by_provider"]
        assert breakdown["by_provider"]["openai"]["cost"] == 30.0
        assert breakdown["by_provider"]["anthropic"]["cost"] == 20.0


class TestCostAnalytics:
    """Test the CostAnalytics class."""

    @pytest.fixture
    def cost_analytics(self):
        """Create a CostAnalytics instance for testing."""
        config = AnalyticsConfig(retention_days=30, cost_optimization_threshold=0.1)
        return CostAnalytics(config)

    def test_add_usage_record(self, cost_analytics):
        """Test adding usage records."""
        record = UsageRecord(
            timestamp=datetime.now(),
            provider=ProviderType.OPENAI,
            model="gpt-4",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.06,
            success=True,
            response_time_ms=1500,
            tokens_used=1500,
        )

        cost_analytics.add_usage_record(record)

        assert len(cost_analytics.usage_records) == 1

    def test_cost_trends(self, cost_analytics):
        """Test cost trends analysis."""
        # Add usage records for different days
        base_date = datetime.now() - timedelta(days=5)
        for i in range(5):
            record = UsageRecord(
                timestamp=base_date + timedelta(days=i),
                provider=ProviderType.OPENAI,
                model="gpt-4",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=10.0 + i,  # Increasing cost
                success=True,
                response_time_ms=1500,
                tokens_used=1500,
            )
            cost_analytics.add_usage_record(record)

        trends = cost_analytics.get_cost_trends(
            base_date, base_date + timedelta(days=4), "daily"
        )

        assert len(trends) == 5
        assert trends[0].total_cost == 10.0
        assert trends[-1].total_cost == 14.0

    def test_provider_comparison(self, cost_analytics):
        """Test provider comparison."""
        # Add usage records for different providers
        records = [
            UsageRecord(
                timestamp=datetime.now(),
                provider=ProviderType.OPENAI,
                model="gpt-4",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=30.0,
                success=True,
                response_time_ms=1500,
                tokens_used=1500,
            ),
            UsageRecord(
                timestamp=datetime.now(),
                provider=ProviderType.ANTHROPIC,
                model="claude-3",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=20.0,
                success=True,
                response_time_ms=1200,
                tokens_used=1500,
            ),
        ]

        for record in records:
            cost_analytics.add_usage_record(record)

        comparisons = cost_analytics.get_provider_comparison()

        assert len(comparisons) == 2
        assert any(comp.provider == ProviderType.OPENAI for comp in comparisons)
        assert any(comp.provider == ProviderType.ANTHROPIC for comp in comparisons)

    def test_optimization_recommendations(self, cost_analytics):
        """Test optimization recommendations."""
        # Add usage records that would trigger recommendations
        records = [
            UsageRecord(
                timestamp=datetime.now(),
                provider=ProviderType.OPENAI,
                model="gpt-4",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=50.0,  # Expensive
                success=True,
                response_time_ms=1500,
                tokens_used=1500,
            ),
            UsageRecord(
                timestamp=datetime.now(),
                provider=ProviderType.ANTHROPIC,
                model="claude-3",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=30.0,  # Cheaper
                success=True,
                response_time_ms=1200,
                tokens_used=1500,
            ),
        ]

        for record in records:
            cost_analytics.add_usage_record(record)

        recommendations = cost_analytics.get_optimization_recommendations(30)

        assert isinstance(recommendations, list)
        # Should recommend switching to cheaper provider
        if recommendations:
            assert any(rec.type == "provider_switch" for rec in recommendations)

    def test_cost_summary(self, cost_analytics):
        """Test cost summary generation."""
        # Add some usage records
        records = [
            UsageRecord(
                timestamp=datetime.now(),
                provider=ProviderType.OPENAI,
                model="gpt-4",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=30.0,
                success=True,
                response_time_ms=1500,
                tokens_used=1500,
            ),
            UsageRecord(
                timestamp=datetime.now(),
                provider=ProviderType.ANTHROPIC,
                model="claude-3",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=20.0,
                success=False,  # One failed request
                response_time_ms=1200,
                tokens_used=1500,
            ),
        ]

        for record in records:
            cost_analytics.add_usage_record(record)

        summary = cost_analytics.get_cost_summary()

        assert summary["summary"]["total_cost"] == 50.0
        assert summary["summary"]["total_requests"] == 2
        assert summary["summary"]["successful_requests"] == 1
        assert summary["summary"]["success_rate"] == 50.0
        assert "openai" in summary["provider_breakdown"]
        assert "anthropic" in summary["provider_breakdown"]


class TestIntegratedCostManager:
    """Test the IntegratedCostManager class."""

    @pytest.fixture
    def integrated_manager(self):
        """Create an IntegratedCostManager instance for testing."""
        return create_default_cost_manager(
            budget_limit=100.0,
            budget_period="monthly",
            enable_optimization=True,
            enable_analytics=True,
        )

    @pytest.mark.asyncio
    async def test_estimate_request_cost(self, integrated_manager):
        """Test request cost estimation."""
        with patch.object(
            integrated_manager.cost_manager, "estimate_cost"
        ) as mock_estimate:
            mock_estimate.return_value = 0.06

            cost = await integrated_manager.estimate_request_cost(
                "openai", "gpt-4", 1000, 500
            )

            assert cost == 0.06
            mock_estimate.assert_called_once_with("openai", "gpt-4", 1000, 500)

    @pytest.mark.asyncio
    async def test_can_make_request(self, integrated_manager):
        """Test request budget check."""
        with patch.object(
            integrated_manager.cost_manager, "estimate_cost"
        ) as mock_estimate:
            mock_estimate.return_value = 10.0

            can_make, message = await integrated_manager.can_make_request(
                "openai", "gpt-4", 1000, 500
            )

            assert can_make
            assert "within budget" in message

    @pytest.mark.asyncio
    async def test_get_optimal_provider(self, integrated_manager):
        """Test getting optimal provider."""
        with patch.object(
            integrated_manager.cost_optimizer, "get_optimal_provider"
        ) as mock_optimal:
            mock_optimal.return_value = ("openai", "gpt-4", 0.85)

            provider, model, score = await integrated_manager.get_optimal_provider(
                "text", 1000, 500
            )

            assert provider == "openai"
            assert model == "gpt-4"
            assert score == 0.85

    def test_record_request(self, integrated_manager):
        """Test recording a request."""
        integrated_manager.record_request(
            "openai", "gpt-4", 1000, 500, 0.06, True, 1500
        )

        # Check that records were added to both systems
        assert len(integrated_manager.budget_manager.usage_records) == 1
        assert len(integrated_manager.analytics.usage_records) == 1

        record = integrated_manager.budget_manager.usage_records[0]
        assert record.provider == ProviderType.OPENAI
        assert record.model == "gpt-4"
        assert record.cost_usd == 0.06
        assert record.success is True

    def test_get_budget_status(self, integrated_manager):
        """Test getting budget status."""
        status = integrated_manager.get_budget_status()

        assert "budget_limit" in status
        assert "current_spend" in status
        assert "remaining_budget" in status
        assert "usage_percentage" in status
        assert "status" in status

    def test_get_cost_analytics(self, integrated_manager):
        """Test getting cost analytics."""
        analytics = integrated_manager.get_cost_analytics()

        assert "summary" in analytics
        assert "provider_breakdown" in analytics
        assert "model_breakdown" in analytics

    def test_get_optimization_recommendations(self, integrated_manager):
        """Test getting optimization recommendations."""
        recommendations = integrated_manager.get_optimization_recommendations()

        assert isinstance(recommendations, list)
        # Should be empty for new system
        assert len(recommendations) == 0

    def test_get_system_health(self, integrated_manager):
        """Test getting system health."""
        health = integrated_manager.get_system_health()

        assert "status" in health
        assert "budget_status" in health
        assert "issues" in health
        assert "recommendations_count" in health
        assert health["status"] == "healthy"  # Should be healthy for new system

    def test_export_analytics_data(self, integrated_manager):
        """Test exporting analytics data."""
        data = integrated_manager.export_analytics_data("json")

        # Should be valid JSON
        parsed_data = json.loads(data)
        assert "usage_records" in parsed_data
        assert isinstance(parsed_data["usage_records"], list)


class TestCreateDefaultCostManager:
    """Test the create_default_cost_manager function."""

    def test_create_default_cost_manager(self):
        """Test creating a default cost manager."""
        manager = create_default_cost_manager(
            budget_limit=200.0,
            budget_period="weekly",
            enable_optimization=True,
            enable_analytics=True,
        )

        assert isinstance(manager, IntegratedCostManager)
        assert manager.budget_manager.config.budget_limit == 200.0
        assert manager.budget_manager.config.budget_period == BudgetPeriod.WEEKLY
        assert manager.cost_optimizer.config.enable_optimization is True
        assert manager.analytics.config.retention_days == 90


if __name__ == "__main__":
    pytest.main([__file__])
