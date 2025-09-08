from unittest.mock import MagicMock

import pytest

from gemini_sre_agent.llm.config import LLMConfig
from gemini_sre_agent.metrics.config import MetricsConfig
from gemini_sre_agent.metrics.metrics_manager import MetricsManager


@pytest.fixture
def mock_config_manager():
    """Fixture for a mocked ConfigManager."""
    mock_config = LLMConfig(
        providers={},
        metrics_config=MetricsConfig(alert_thresholds={"health_score": 0.7}),
    )
    mock_manager = MagicMock()
    mock_manager.get_config.return_value = mock_config
    return mock_manager


def test_metrics_manager_initialization(mock_config_manager):
    manager = MetricsManager(mock_config_manager)
    assert manager.config_manager == mock_config_manager
    assert manager.provider_metrics == {}
    assert manager.alert_thresholds == {"health_score": 0.7}


@pytest.mark.asyncio
async def test_record_provider_request(mock_config_manager):
    manager = MetricsManager(mock_config_manager)
    await manager.record_provider_request(
        provider_id="test_provider",
        latency_ms=100,
        input_tokens=10,
        output_tokens=50,
        cost=0.002,
        success=True,
    )
    assert "test_provider" in manager.provider_metrics
    provider_metrics = manager.provider_metrics["test_provider"]
    assert provider_metrics.request_count == 1
    assert provider_metrics.success_count == 1


def test_get_provider_health(mock_config_manager):
    manager = MetricsManager(mock_config_manager)
    assert manager.get_provider_health("non_existent_provider") == 1.0

    manager.provider_metrics["test_provider"] = MagicMock()
    manager.provider_metrics["test_provider"].health_score = 0.85
    assert manager.get_provider_health("test_provider") == 0.85


@pytest.mark.asyncio
async def test_get_dashboard_data(mock_config_manager):
    manager = MetricsManager(mock_config_manager)
    await manager.record_provider_request(
        provider_id="test_provider_1",
        latency_ms=100,
        input_tokens=10,
        output_tokens=50,
        cost=0.002,
        success=True,
    )
    await manager.record_provider_request(
        provider_id="test_provider_2",
        latency_ms=200,
        input_tokens=20,
        output_tokens=100,
        cost=0.004,
        success=True,
    )
    dashboard_data = manager.get_dashboard_data()
    assert dashboard_data["total_requests"] == 2
    assert dashboard_data["success_rate"] == 1.0
    assert dashboard_data["avg_latency"] == 150.0
    assert dashboard_data["total_cost"] == 0.006
    assert "test_provider_1" in dashboard_data["provider_health"]
    assert "test_provider_2" in dashboard_data["provider_health"]


@pytest.mark.asyncio
async def test_rank_providers(mock_config_manager):
    manager = MetricsManager(mock_config_manager)
    await manager.record_provider_request(
        provider_id="test_provider_1",
        latency_ms=100,
        input_tokens=10,
        output_tokens=50,
        cost=0.002,
        success=True,
    )
    await manager.record_provider_request(
        provider_id="test_provider_2",
        latency_ms=5000,
        input_tokens=10,
        output_tokens=50,
        cost=0.002,
        success=False,
    )
    ranked = manager.rank_providers(metric="health")
    assert len(ranked) == 2
    assert ranked[0][0] == "test_provider_1"
    assert ranked[1][0] == "test_provider_2"
    assert ranked[0][1] > ranked[1][1]
