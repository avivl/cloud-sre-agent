from unittest.mock import MagicMock

import pytest

from gemini_sre_agent.metrics.analytics import PerformanceAnalytics
from gemini_sre_agent.metrics.metrics_manager import MetricsManager


@pytest.fixture
def mock_metrics_manager():
    """Fixture for a mocked MetricsManager."""
    mock_manager = MagicMock(spec=MetricsManager)
    provider1_metrics = MagicMock()
    provider1_metrics.success_count = 8
    provider1_metrics.costs = [0.002, 0.003]

    provider2_metrics = MagicMock()
    provider2_metrics.success_count = 0
    provider2_metrics.costs = [0.004]

    mock_manager.provider_metrics = {
        "provider1": provider1_metrics,
        "provider2": provider2_metrics,
    }
    return mock_manager


def test_calculate_cost_efficiency(mock_metrics_manager):
    analytics = PerformanceAnalytics(mock_metrics_manager)

    # Test with a provider with successful requests
    cost_efficiency1 = analytics.calculate_cost_efficiency("provider1")
    assert cost_efficiency1 == (0.002 + 0.003) / 8

    # Test with a provider with no successful requests
    cost_efficiency2 = analytics.calculate_cost_efficiency("provider2")
    assert cost_efficiency2 == 0.0

    # Test with a non-existent provider
    cost_efficiency3 = analytics.calculate_cost_efficiency("non_existent_provider")
    assert cost_efficiency3 == 0.0
