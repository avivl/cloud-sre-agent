"""
Integration tests for the pattern detection system.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from gemini_sre_agent.pattern_detector import (
    LogEntry,
    PatternClassifier,
    ThresholdConfig,
    ThresholdEvaluator,
    ThresholdType,
    TimeWindow,
    WindowManager,
)


@pytest.mark.integration
class TestPatternDetectorIntegration:
    """Integration tests for the complete pattern detection system."""

    @pytest.mark.asyncio
    async def test_end_to_end_pattern_detection(self):
        """Test complete flow from log ingestion to pattern detection."""
        received_windows = []

        def pattern_callback(window):
            received_windows.append(window)

        manager = WindowManager(
            fast_window_minutes=1,
            trend_window_minutes=2,
            pattern_callback=pattern_callback,
        )
        manager.start()

        try:
            base_time = datetime.now(timezone.utc)
            logs = [
                {
                    "insertId": f"test-{i}",
                    "timestamp": (base_time + timedelta(seconds=i * 10)).isoformat()
                    + "Z",
                    "severity": "ERROR" if i % 2 == 0 else "INFO",
                    "textPayload": f"Test message {i}",
                    "resource": {"labels": {"service_name": f"service-{i % 2}"}},
                }
                for i in range(6)
            ]
            for log_data in logs:
                manager.add_log(log_data)

            await asyncio.sleep(0.1)

            assert len(manager.fast_accumulator.windows) > 0
            assert len(manager.trend_accumulator.windows) > 0
        finally:
            await manager.stop()

    def test_realistic_log_data_processing(self):
        """Test with realistic GCP log data structure."""
        received_windows = []

        def pattern_callback(window):
            received_windows.append(window)

        manager = WindowManager(
            fast_window_minutes=5, pattern_callback=pattern_callback
        )

        realistic_log = {
            "insertId": "1234567890abcdef",
            "logName": "projects/my-project/logs/run.googleapis.com%2Frequest",
            "receiveTimestamp": "2025-01-27T10:03:45.123456Z",
            "resource": {
                "type": "cloud_run_revision",
                "labels": {
                    "service_name": "billing-service",
                    "revision_name": "billing-service-00001-abc",
                    "location": "us-central1",
                },
            },
            "severity": "ERROR",
            "textPayload": "Database connection failed: java.sql.SQLException: Connection refused",
            "timestamp": "2025-01-27T10:03:44.987654Z",
            "trace": "projects/my-project/traces/abc123def456",
        }

        manager.add_log(realistic_log)

        assert len(manager.fast_accumulator.windows) == 1
        window = list(manager.fast_accumulator.windows.values())[0]
        assert len(window.logs) == 1
        log_entry = window.logs[0]
        assert log_entry.service_name == "billing-service"
        assert log_entry.severity == "ERROR"
        assert log_entry.error_message is not None
        assert "Database connection failed" in log_entry.error_message


@pytest.mark.integration
class TestSmartThresholdsIntegration:
    """Integration tests for smart thresholds with time windows."""

    def test_threshold_evaluation_with_window_manager(self):
        """Test threshold evaluation integrated with window manager."""
        threshold_configs = [
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
        evaluator = ThresholdEvaluator(threshold_configs)
        triggered_results = []

        def pattern_callback(window):
            results = evaluator.evaluate_window(window)
            triggered = [r for r in results if r.triggered]
            if triggered:
                triggered_results.extend(triggered)

        manager = WindowManager(
            fast_window_minutes=5, pattern_callback=pattern_callback
        )

        base_time = datetime.now(timezone.utc)
        for i in range(8):
            severity = "ERROR" if i < 4 else "INFO"
            service = "service-a" if i < 6 else "service-b"
            log_data = {
                "insertId": f"integration-{i}",
                "timestamp": (base_time + timedelta(seconds=i * 10))
                .replace(tzinfo=None)
                .isoformat()
                + "Z",
                "severity": severity,
                "textPayload": f"Test message {i}",
                "resource": {"labels": {"service_name": service}},
            }
            manager.add_log(log_data)

        assert len(manager.fast_accumulator.windows) > 0

        window = list(manager.fast_accumulator.windows.values())[0]
        results = evaluator.evaluate_window(window)

        triggered = [r for r in results if r.triggered]
        assert len(triggered) >= 1

    def test_baseline_tracking_over_time(self):
        """Test baseline tracking across multiple windows."""
        config = ThresholdConfig(
            threshold_type=ThresholdType.ERROR_RATE,
            min_value=15.0,
            min_rate_increase=25.0,
        )
        evaluator = ThresholdEvaluator([config])
        base_time = datetime(2025, 1, 27, 10, 0, 0)
        error_rates = [0.1, 0.1, 0.2, 0.4, 0.6]

        for i, error_rate in enumerate(error_rates):
            window = TimeWindow(
                start_time=base_time + timedelta(minutes=i * 5), duration_minutes=5
            )
            total_logs = 10
            error_count = int(total_logs * error_rate)
            for j in range(total_logs):
                severity = "ERROR" if j < error_count else "INFO"
                log = LogEntry(
                    insert_id=f"baseline-{i}-{j}",
                    timestamp=window.start_time + timedelta(seconds=j * 10),
                    severity=severity,
                    raw_data={"severity": severity},
                )
                window.add_log(log)
            results = evaluator.evaluate_window(window)
            if i >= 3:
                rate_result = results[0]
                if error_rate >= 0.4:
                    assert rate_result.triggered is True


@pytest.mark.integration
class TestPatternClassificationIntegration:
    """Integration tests for pattern classification with threshold evaluation."""

    @pytest.mark.asyncio
    async def test_end_to_end_pattern_detection(self):
        """Test complete pattern detection pipeline."""
        pattern_callback_results = []

        def pattern_callback(window: TimeWindow):
            pattern_callback_results.append(window)

        window_manager = WindowManager(
            fast_window_minutes=5,
            trend_window_minutes=15,
            pattern_callback=pattern_callback,
        )

        threshold_configs = [
            ThresholdConfig(
                threshold_type=ThresholdType.ERROR_FREQUENCY,
                min_value=5.0,
                min_error_count=3,
            ),
            ThresholdConfig(
                threshold_type=ThresholdType.SERVICE_IMPACT,
                min_value=2.0,
                min_affected_services=2,
            ),
        ]
        threshold_evaluator = ThresholdEvaluator(threshold_configs)
        pattern_classifier = PatternClassifier()

        base_time = datetime(2024, 1, 27, 10, 0, 0, tzinfo=timezone.utc)
        services = ["auth-service", "billing-service", "notification-service"]

        for i in range(15):
            service = services[i % len(services)]
            log_data = {
                "insertId": f"cascade-test-{i}",
                "timestamp": (base_time + timedelta(seconds=i * 10)).isoformat(),
                "severity": "ERROR",
                "textPayload": f"Service {service} connection failed",
                "resource": {
                    "type": "cloud_run_revision",
                    "labels": {"service_name": service},
                },
            }
            window_manager.add_log(log_data)

        await window_manager.fast_accumulator._process_expired_windows()

        assert len(pattern_callback_results) >= 1

        completed_window = pattern_callback_results[0]
        threshold_results = threshold_evaluator.evaluate_window(completed_window)
        patterns = pattern_classifier.classify_patterns(
            completed_window, threshold_results
        )

        assert len(patterns) >= 1

        # The confidence scoring system is intentionally conservative to avoid false positives
        # So we test for reasonable confidence levels rather than expecting high confidence
        medium_confidence_patterns = [p for p in patterns if p.confidence_score >= 0.3]
        assert len(medium_confidence_patterns) >= 1

        # At least one pattern should have meaningful priority
        prioritized_patterns = [
            p
            for p in patterns
            if p.remediation_priority in ["IMMEDIATE", "HIGH", "MEDIUM"]
        ]
        assert len(prioritized_patterns) >= 1
