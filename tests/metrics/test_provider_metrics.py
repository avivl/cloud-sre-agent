from datetime import datetime, timedelta

from freezegun import freeze_time

from gemini_sre_agent.metrics.enums import ErrorCategory
from gemini_sre_agent.metrics.provider_metrics import ProviderMetrics


def test_provider_metrics_initialization():
    metrics = ProviderMetrics("test_provider")
    assert metrics.provider_id == "test_provider"
    assert metrics.request_count == 0
    assert metrics.success_count == 0
    assert metrics.error_count == 0
    assert metrics.latency_ms == []
    assert metrics.token_counts == {"input": 0, "output": 0}
    assert metrics.costs == []
    assert metrics.last_error_time is None
    assert metrics.health_score == 1.0


def test_record_successful_request():
    metrics = ProviderMetrics("test_provider")
    metrics.record_request(
        latency_ms=100,
        input_tokens=10,
        output_tokens=50,
        cost=0.002,
        success=True,
    )
    assert metrics.request_count == 1
    assert metrics.success_count == 1
    assert metrics.error_count == 0
    assert metrics.latency_ms == [100]
    assert metrics.token_counts["input"] == 10
    assert metrics.token_counts["output"] == 50
    assert metrics.costs == [0.002]
    assert metrics.health_score > 0.9


def test_record_failed_request():
    metrics = ProviderMetrics("test_provider")
    with freeze_time("2025-09-08 12:00:00"):
        metrics.record_request(
            latency_ms=200,
            input_tokens=20,
            output_tokens=0,
            cost=0.001,
            success=False,
            error_category=ErrorCategory.SERVER_ERROR,
        )
        assert metrics.request_count == 1
        assert metrics.success_count == 0
        assert metrics.error_count == 1
        assert metrics.latency_ms == [200]
        assert metrics.token_counts["input"] == 20
        assert metrics.token_counts["output"] == 0
        assert metrics.costs == [0.001]
        assert metrics.last_error_time == datetime(2025, 9, 8, 12, 0, 0)
        assert metrics.error_categories[ErrorCategory.SERVER_ERROR] == 1
        assert metrics.health_score < 1.0


def test_health_scoring():
    metrics = ProviderMetrics("test_provider")

    # 90 successful requests
    for _ in range(90):
        metrics.record_request(
            latency_ms=100,
            input_tokens=10,
            output_tokens=50,
            cost=0.002,
            success=True,
        )

    # 10 failed requests
    with freeze_time("2025-09-08 12:00:00") as frozen_time:
        for _ in range(10):
            metrics.record_request(
                latency_ms=100,
                input_tokens=10,
                output_tokens=0,
                cost=0,
                success=False,
                error_category=ErrorCategory.TRANSIENT,
            )
            frozen_time.tick(delta=timedelta(seconds=10))

    # Health score should reflect 10% error rate
    # and recent errors
    health_score = metrics.calculate_health_score()
    assert 0.5 <= health_score <= 0.7

    # Test high latency
    metrics = ProviderMetrics("test_provider_latency")
    metrics.record_request(
        latency_ms=6000,
        input_tokens=10,
        output_tokens=50,
        cost=0.002,
        success=True,
    )
    assert metrics.health_score < 0.7
