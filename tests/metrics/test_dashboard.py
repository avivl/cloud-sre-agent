from unittest.mock import MagicMock

import pytest

from gemini_sre_agent.metrics.dashboard import DashboardDataGenerator
from gemini_sre_agent.metrics.metrics_manager import MetricsManager


@pytest.fixture
def mock_metrics_manager():
    """Fixture for a mocked MetricsManager."""
    mock_manager = MagicMock(spec=MetricsManager)
    provider1_metrics = MagicMock()
    provider1_metrics.request_count = 10
    provider1_metrics.success_count = 8
    provider1_metrics.latency_ms = [100, 150]
    provider1_metrics.costs = [0.002, 0.003]
    provider1_metrics.health_score = 0.8

    provider2_metrics = MagicMock()
    provider2_metrics.request_count = 5
    provider2_metrics.success_count = 5
    provider2_metrics.latency_ms = [200]
    provider2_metrics.costs = [0.004]
    provider2_metrics.health_score = 0.95

    mock_manager.provider_metrics = {
        "provider1": provider1_metrics,
        "provider2": provider2_metrics,
    }
    return mock_manager


def test_generate_overview_data(mock_metrics_manager):
    generator = DashboardDataGenerator(mock_metrics_manager)
    overview_data = generator.generate_overview_data()

    assert overview_data["total_requests"] == 15
    assert overview_data["success_rate"] == 13 / 15
    assert overview_data["avg_latency"] == (100 + 150 + 200) / 3
    assert overview_data["total_cost"] == 0.002 + 0.003 + 0.004
    assert overview_data["provider_health"] == {"provider1": 0.8, "provider2": 0.95}
