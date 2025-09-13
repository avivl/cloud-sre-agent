"""
Tests for pattern classification logic.
"""

from datetime import datetime, timedelta

import pytest

from gemini_sre_agent.pattern_detector.models import (
    LogEntry,
    ThresholdResult,
    ThresholdType,
    TimeWindow,
)
from gemini_sre_agent.pattern_detector.pattern_classifier import PatternClassifier


class TestPatternClassifier:
    """Test PatternClassifier functionality."""

    @pytest.fixture
    def classifier(self) -> None:
        """Create a pattern classifier for testing."""
        return PatternClassifier()

    @pytest.fixture
    def cascade_failure_window(self) -> None:
        """Create a window simulating cascade failure."""
        window = TimeWindow(
            start_time=datetime(2025, 1, 27, 10, 0, 0), duration_minutes=5
        )
        services = ["auth-service", "billing-service", "notification-service"]
        for i in range(15):
            service = services[i % len(services)]
            severity = "ERROR" if i < 12 else "CRITICAL"
            log = LogEntry(
                insert_id=f"cascade-{i}",
                timestamp=window.start_time + timedelta(seconds=i * 5),
                severity=severity,
                service_name=service,
                error_message=f"Service {service} connection failed",
                raw_data={"severity": severity},
            )
            window.add_log(log)
        return window

    @pytest.fixture
    def service_degradation_window(self) -> None:
        """Create a window simulating service degradation."""
        window = TimeWindow(
            start_time=datetime(2025, 1, 27, 10, 5, 0), duration_minutes=5
        )
        for i in range(10):
            service = "billing-service" if i < 8 else "auth-service"
            severity = "ERROR"
            log = LogEntry(
                insert_id=f"degradation-{i}",
                timestamp=window.start_time + timedelta(seconds=i * 30),
                severity=severity,
                service_name=service,
                error_message=f"Database query failed in {service}",
                raw_data={"severity": severity},
            )
            window.add_log(log)
        return window

    @pytest.fixture
    def configuration_issue_window(self) -> None:
        """Create a window simulating configuration issues."""
        window = TimeWindow(
            start_time=datetime(2025, 1, 27, 10, 10, 0), duration_minutes=5
        )
        config_errors = [
            "Invalid configuration parameter",
            "Missing required setting",
            "Configuration file not found",
            "Invalid config value for timeout",
            "Configuration validation failed",
        ]
        for i, error_msg in enumerate(config_errors):
            log = LogEntry(
                insert_id=f"config-{i}",
                timestamp=window.start_time + timedelta(seconds=i * 10),
                severity="ERROR",
                service_name="config-service",
                error_message=error_msg,
                raw_data={"severity": "ERROR"},
            )
            window.add_log(log)
        for i in range(5):
            log = LogEntry(
                insert_id=f"normal-{i}",
                timestamp=window.start_time + timedelta(seconds=100 + i * 30),
                severity="INFO",
                service_name="other-service",
                error_message="Normal operation",
                raw_data={"severity": "INFO"},
            )
            window.add_log(log)
        return window

    @pytest.fixture
    def triggered_threshold_results(self) -> None:
        """Create threshold results that should trigger pattern detection."""
        return [
            ThresholdResult(
                threshold_type=ThresholdType.ERROR_FREQUENCY,
                triggered=True,
                score=12.0,
                details={"error_count": 12},
                triggering_logs=[],
                affected_services=["auth-service", "billing-service"],
            ),
            ThresholdResult(
                threshold_type=ThresholdType.SERVICE_IMPACT,
                triggered=True,
                score=2.0,
                details={"affected_services": 2},
                triggering_logs=[],
                affected_services=["auth-service", "billing-service"],
            ),
        ]

    def test_classifier_initialization(self, classifier: str) -> None:
        """Test PatternClassifier initialization."""
        assert classifier is not None
        assert classifier.classification_rules is not None
        expected_rules = [
            "cascade_failure",
            "service_degradation",
            "traffic_spike",
            "configuration_issue",
            "dependency_failure",
            "resource_exhaustion",
        ]
        for rule_type in expected_rules:
            assert rule_type in classifier.classification_rules
            assert "min_confidence" in classifier.classification_rules[rule_type]

    def test_no_patterns_when_no_triggered_thresholds(
        self, classifier, cascade_failure_window
    ):
        """Test that no patterns are detected when no thresholds are triggered."""
        threshold_results = [
            ThresholdResult(
                threshold_type=ThresholdType.ERROR_FREQUENCY,
                triggered=False,
                score=2.0,
                details={"error_count": 2},
                triggering_logs=[],
                affected_services=[],
            )
        ]
        patterns = classifier.classify_patterns(
            cascade_failure_window, threshold_results
        )
        assert len(patterns) == 0

    def test_severity_level_calculation(self, classifier: str) -> None:
        """Test severity level calculation from logs."""
        critical_logs = [
            LogEntry(
                insert_id=f"critical-{i}",
                timestamp=datetime(2025, 1, 27, 10, 0, 0),
                severity="CRITICAL" if i < 2 else "ERROR",
                service_name="test-service",
                raw_data={"severity": "CRITICAL" if i < 2 else "ERROR"},
            )
            for i in range(5)
        ]
        severity = classifier._determine_severity_level(critical_logs)
        assert severity == "CRITICAL"

        error_logs = [
            LogEntry(
                insert_id=f"error-{i}",
                timestamp=datetime(2025, 1, 27, 10, 0, 0),
                severity="ERROR" if i < 3 else "INFO",
                service_name="test-service",
                raw_data={"severity": "ERROR" if i < 3 else "INFO"},
            )
            for i in range(10)
        ]
        severity = classifier._determine_severity_level(error_logs)
        assert severity == "HIGH"

        info_logs = [
            LogEntry(
                insert_id=f"info-{i}",
                timestamp=datetime(2025, 1, 27, 10, 0, 0),
                severity="INFO",
                service_name="test-service",
                raw_data={"severity": "INFO"},
            )
            for i in range(10)
        ]
        severity = classifier._determine_severity_level(info_logs)
        assert severity == "LOW"

    def test_primary_service_identification(self, classifier: str) -> None:
        """Test identification of primary service from logs."""
        logs = [
            LogEntry(
                insert_id="1",
                timestamp=datetime(2025, 1, 27, 10, 0, 0),
                severity="ERROR",
                service_name="service-a",
                raw_data={"severity": "ERROR"},
            ),
            LogEntry(
                insert_id="2",
                timestamp=datetime(2025, 1, 27, 10, 0, 0),
                severity="ERROR",
                service_name="service-a",
                raw_data={"severity": "ERROR"},
            ),
            LogEntry(
                insert_id="3",
                timestamp=datetime(2025, 1, 27, 10, 0, 0),
                severity="ERROR",
                service_name="service-b",
                raw_data={"severity": "ERROR"},
            ),
        ]
        primary_service = classifier._identify_primary_service(logs)
        assert primary_service == "service-a"

        logs_no_service = [
            LogEntry(
                insert_id="1",
                timestamp=datetime(2025, 1, 27, 10, 0, 0),
                severity="ERROR",
                service_name=None,
                raw_data={"severity": "ERROR"},
            )
        ]
        primary_service = classifier._identify_primary_service(logs_no_service)
        assert primary_service is None
