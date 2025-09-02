"""
Tests for threshold evaluation logic.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from gemini_sre_agent.pattern_detector.models import (
    LogEntry,
    ThresholdConfig,
    ThresholdType,
    TimeWindow,
)
from gemini_sre_agent.pattern_detector.threshold_evaluator import ThresholdEvaluator


class TestThresholdEvaluator:
    """Test ThresholdEvaluator functionality."""

    @pytest.fixture
    def sample_window_with_errors(self):
        """Create a sample window with error logs."""
        window = TimeWindow(
            start_time=datetime(2025, 1, 27, 10, 0, 0), duration_minutes=5
        )
        for i in range(10):
            severity = "ERROR" if i < 5 else "INFO"
            if i < 3:
                service = "service-a"
            elif i < 8:
                service = "service-b"
            else:
                service = "service-a"
            log = LogEntry(
                insert_id=f"log-{i}",
                timestamp=window.start_time + timedelta(seconds=i * 10),
                severity=severity,
                service_name=service,
                raw_data={"severity": severity},
            )
            window.add_log(log)
        return window

    @pytest.fixture
    def sample_window_low_errors(self):
        """Create a sample window with few errors."""
        window = TimeWindow(
            start_time=datetime(2025, 1, 27, 10, 5, 0), duration_minutes=5
        )
        for i in range(10):
            severity = "ERROR" if i == 0 else "INFO"
            log = LogEntry(
                insert_id=f"log-low-{i}",
                timestamp=window.start_time + timedelta(seconds=i * 10),
                severity=severity,
                service_name="service-a",
                raw_data={"severity": severity},
            )
            window.add_log(log)
        return window

    def test_threshold_evaluator_initialization(self):
        """Test ThresholdEvaluator initialization."""
        configs = [
            ThresholdConfig(threshold_type=ThresholdType.ERROR_FREQUENCY, min_value=5.0)
        ]
        evaluator = ThresholdEvaluator(configs)
        assert len(evaluator.threshold_configs) == 1
        assert evaluator.baseline_tracker is not None

    def test_error_frequency_threshold_triggered(self, sample_window_with_errors):
        """Test error frequency threshold when triggered."""
        config = ThresholdConfig(
            threshold_type=ThresholdType.ERROR_FREQUENCY,
            min_value=5.0,
            min_error_count=3,
        )
        evaluator = ThresholdEvaluator([config])
        results = evaluator.evaluate_window(sample_window_with_errors)
        assert len(results) == 1
        result = results[0]
        assert result.threshold_type == ThresholdType.ERROR_FREQUENCY
        assert result.triggered is True
        assert result.score == 5.0
        assert len(result.triggering_logs) == 5
        assert len(result.affected_services) == 2
        assert "service-a" in result.affected_services
        assert "service-b" in result.affected_services

    def test_error_frequency_threshold_not_triggered(self, sample_window_low_errors):
        """Test error frequency threshold when not triggered."""
        config = ThresholdConfig(
            threshold_type=ThresholdType.ERROR_FREQUENCY,
            min_value=5.0,
            min_error_count=3,
        )
        evaluator = ThresholdEvaluator([config])
        results = evaluator.evaluate_window(sample_window_low_errors)
        assert len(results) == 1
        result = results[0]
        assert result.threshold_type == ThresholdType.ERROR_FREQUENCY
        assert result.triggered is False
        assert result.score == 1.0
        assert len(result.triggering_logs) == 1

    def test_error_rate_threshold_with_baseline(self, sample_window_with_errors):
        """Test error rate threshold against baseline."""
        config = ThresholdConfig(
            threshold_type=ThresholdType.ERROR_RATE,
            min_value=15.0,
            min_rate_increase=20.0,
        )
        evaluator = ThresholdEvaluator([config])
        baseline_window = TimeWindow(
            start_time=datetime(2025, 1, 27, 9, 0, 0), duration_minutes=5
        )
        for i in range(10):
            log = LogEntry(
                insert_id=f"baseline-{i}",
                timestamp=baseline_window.start_time + timedelta(seconds=i * 10),
                severity="ERROR" if i == 0 else "INFO",
                raw_data={"severity": "ERROR" if i == 0 else "INFO"},
            )
            baseline_window.add_log(log)
        evaluator.baseline_tracker.update_baseline(baseline_window)
        results = evaluator.evaluate_window(sample_window_with_errors)
        result = results[0]
        assert result.threshold_type == ThresholdType.ERROR_RATE
        assert result.triggered is True
        assert result.details["current_rate"] == 50.0
        assert result.details["baseline_rate"] == 10.0

    def test_service_impact_threshold_triggered(self, sample_window_with_errors):
        """Test service impact threshold when triggered."""
        config = ThresholdConfig(
            threshold_type=ThresholdType.SERVICE_IMPACT,
            min_value=2.0,
            min_affected_services=2,
        )
        evaluator = ThresholdEvaluator([config])
        results = evaluator.evaluate_window(sample_window_with_errors)
        result = results[0]
        assert result.threshold_type == ThresholdType.SERVICE_IMPACT
        assert result.triggered is True
        assert result.score == 2.0
        assert len(result.affected_services) == 2

    def test_service_impact_threshold_not_triggered(self, sample_window_low_errors):
        """Test service impact threshold when not triggered."""
        config = ThresholdConfig(
            threshold_type=ThresholdType.SERVICE_IMPACT,
            min_value=2.0,
            min_affected_services=2,
        )
        evaluator = ThresholdEvaluator([config])
        results = evaluator.evaluate_window(sample_window_low_errors)
        result = results[0]
        assert result.threshold_type == ThresholdType.SERVICE_IMPACT
        assert result.triggered is False
        assert result.score == 1.0
        assert len(result.affected_services) == 1

    def test_severity_weighted_threshold(self, sample_window_with_errors):
        """Test severity-weighted threshold."""
        config = ThresholdConfig(
            threshold_type=ThresholdType.SEVERITY_WEIGHTED,
            min_value=30.0,
            severity_weights={"ERROR": 5.0, "INFO": 1.0, "CRITICAL": 10.0},
        )
        evaluator = ThresholdEvaluator([config])
        results = evaluator.evaluate_window(sample_window_with_errors)
        result = results[0]
        assert result.threshold_type == ThresholdType.SEVERITY_WEIGHTED
        assert result.triggered is True
        assert result.score == 30.0
        assert len(result.triggering_logs) == 5

    def test_cascade_failure_threshold_triggered(self, sample_window_with_errors):
        """Test cascade failure threshold when triggered."""
        config = ThresholdConfig(
            threshold_type=ThresholdType.CASCADE_FAILURE,
            min_value=2.0,
            cascade_min_services=2,
        )
        evaluator = ThresholdEvaluator([config])
        results = evaluator.evaluate_window(sample_window_with_errors)
        result = results[0]
        assert result.threshold_type == ThresholdType.CASCADE_FAILURE
        assert result.triggered is True
        assert result.score == 2.0
        assert len(result.affected_services) == 2

    def test_cascade_failure_threshold_not_triggered(self, sample_window_low_errors):
        """Test cascade failure threshold when not triggered."""
        config = ThresholdConfig(
            threshold_type=ThresholdType.CASCADE_FAILURE,
            min_value=2.0,
            cascade_min_services=2,
        )
        evaluator = ThresholdEvaluator([config])
        results = evaluator.evaluate_window(sample_window_low_errors)
        result = results[0]
        assert result.threshold_type == ThresholdType.CASCADE_FAILURE
        assert result.triggered is False
        assert result.score == 1.0

    def test_multiple_thresholds_evaluation(self, sample_window_with_errors):
        """Test evaluating multiple thresholds simultaneously."""
        configs = [
            ThresholdConfig(
                threshold_type=ThresholdType.ERROR_FREQUENCY,
                min_value=3.0,
                min_error_count=3,
            ),
            ThresholdConfig(
                threshold_type=ThresholdType.SERVICE_IMPACT,
                min_value=2.0,
                min_affected_services=2,
            ),
        ]
        evaluator = ThresholdEvaluator(configs)
        results = evaluator.evaluate_window(sample_window_with_errors)
        assert len(results) == 2
        frequency_result = next(
            r for r in results if r.threshold_type == ThresholdType.ERROR_FREQUENCY
        )
        impact_result = next(
            r for r in results if r.threshold_type == ThresholdType.SERVICE_IMPACT
        )
        assert frequency_result.triggered is True
        assert impact_result.triggered is True

    def test_unknown_threshold_type_error(self, sample_window_with_errors):
        """Test error handling for unknown threshold type."""
        config = ThresholdConfig(threshold_type="unknown_threshold", min_value=5.0)
        evaluator = ThresholdEvaluator([config])
        with patch(
            "gemini_sre_agent.pattern_detector.threshold_evaluator.logger"
        ) as mock_logger:
            results = evaluator.evaluate_window(sample_window_with_errors)
            assert mock_logger.error.call_count == 1
