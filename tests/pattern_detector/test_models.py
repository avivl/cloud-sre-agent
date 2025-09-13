"""
Tests for the data models in the pattern detection system.
"""

from datetime import UTC, datetime

from gemini_sre_agent.pattern_detector.models import (
    ConfidenceFactors,
    ConfidenceRule,
    ConfidenceScore,
    LogEntry,
    PatternMatch,
    PatternType,
    ThresholdConfig,
    ThresholdType,
    TimeWindow,
)


class TestLogEntry:
    """Test LogEntry creation and parsing functionality."""

    def test_log_entry_basic_creation(self) -> None:
        """Test basic LogEntry creation with all fields provided."""
        timestamp = datetime.now(UTC)
        raw_data = {"severity": "ERROR", "textPayload": "Test error"}

        log_entry = LogEntry(
            insert_id="test-123",
            timestamp=timestamp,
            severity="ERROR",
            service_name="test-service",
            error_message="Test error",
            raw_data=raw_data,
        )

        assert log_entry.insert_id == "test-123"
        assert log_entry.timestamp == timestamp
        assert log_entry.severity == "ERROR"
        assert log_entry.service_name == "test-service"
        assert log_entry.error_message == "Test error"
        assert log_entry.raw_data == raw_data

    def test_log_entry_timestamp_extraction(self) -> None:
        """Test automatic timestamp extraction from raw data."""
        raw_data = {
            "timestamp": "2025-01-27T10:00:00Z",
            "severity": "ERROR",
            "textPayload": "Test error",
        }

        log_entry = LogEntry(insert_id="test-123", raw_data=raw_data)

        assert log_entry.timestamp.year == 2025
        assert log_entry.timestamp.month == 1
        assert log_entry.timestamp.day == 27
        assert log_entry.timestamp.hour == 10

    def test_log_entry_service_name_extraction(self) -> None:
        """Test automatic service name extraction from resource labels."""
        raw_data = {
            "timestamp": "2025-01-27T10:00:00Z",
            "resource": {
                "type": "cloud_run_revision",
                "labels": {
                    "service_name": "billing-service",
                    "revision_name": "billing-service-001",
                },
            },
            "severity": "ERROR",
        }

        log_entry = LogEntry(insert_id="test-123", raw_data=raw_data)

        assert log_entry.service_name == "billing-service"

    def test_log_entry_function_name_extraction(self) -> None:
        """Test service name extraction from function_name label."""
        raw_data = {
            "timestamp": "2025-01-27T10:00:00Z",
            "resource": {
                "type": "cloud_function",
                "labels": {"function_name": "payment-processor"},
            },
            "severity": "ERROR",
        }

        log_entry = LogEntry(insert_id="test-123", raw_data=raw_data)

        assert log_entry.service_name == "payment-processor"

    def test_log_entry_error_message_extraction(self) -> None:
        """Test automatic error message extraction from textPayload."""
        raw_data = {
            "timestamp": "2025-01-27T10:00:00Z",
            "textPayload": "Database connection failed: timeout after 30s",
            "severity": "ERROR",
        }

        log_entry = LogEntry(insert_id="test-123", raw_data=raw_data)

        assert (
            log_entry.error_message == "Database connection failed: timeout after 30s"
        )

    def test_log_entry_invalid_timestamp_fallback(self) -> None:
        """Test fallback to current time for invalid timestamps."""
        raw_data = {"timestamp": "invalid-timestamp", "severity": "ERROR"}

        before_creation = datetime.now(UTC)
        log_entry = LogEntry(insert_id="test-123", raw_data=raw_data)
        after_creation = datetime.now(UTC)

        assert before_creation <= log_entry.timestamp <= after_creation


class TestTimeWindow:
    """Test TimeWindow functionality."""

    def test_time_window_creation(self) -> None:
        """Test basic TimeWindow creation."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        assert window.start_time == start_time
        assert window.duration_minutes == 5
        assert window.end_time == datetime(2025, 1, 27, 10, 5, 0)
        assert len(window.logs) == 0

    def test_time_window_is_active(self) -> None:
        """Test window active status checking."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        assert window.is_active(datetime(2025, 1, 27, 10, 3, 0)) is True
        assert window.is_active(datetime(2025, 1, 27, 10, 5, 0)) is False
        assert window.is_active(datetime(2025, 1, 27, 10, 6, 0)) is False

    def test_time_window_is_expired(self) -> None:
        """Test window expiration checking."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        assert window.is_expired(datetime(2025, 1, 27, 10, 3, 0)) is False
        assert window.is_expired(datetime(2025, 1, 27, 10, 5, 0)) is True
        assert window.is_expired(datetime(2025, 1, 27, 10, 6, 0)) is True

    def test_time_window_accepts_log(self) -> None:
        """Test log acceptance logic."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        log_before = LogEntry(
            insert_id="before",
            timestamp=datetime(2025, 1, 27, 9, 59, 0),
            severity="ERROR",
            raw_data={},
        )
        log_within = LogEntry(
            insert_id="within",
            timestamp=datetime(2025, 1, 27, 10, 3, 0),
            severity="ERROR",
            raw_data={},
        )
        log_after = LogEntry(
            insert_id="after",
            timestamp=datetime(2025, 1, 27, 10, 6, 0),
            severity="ERROR",
            raw_data={},
        )

        assert window.accepts_log(log_before) is False
        assert window.accepts_log(log_within) is True
        assert window.accepts_log(log_after) is False

    def test_time_window_add_log(self) -> None:
        """Test adding logs to window."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        valid_log = LogEntry(
            insert_id="valid",
            timestamp=datetime(2025, 1, 27, 10, 3, 0),
            severity="ERROR",
            raw_data={},
        )
        invalid_log = LogEntry(
            insert_id="invalid",
            timestamp=datetime(2025, 1, 27, 10, 6, 0),
            severity="ERROR",
            raw_data={},
        )

        assert window.add_log(valid_log) is True
        assert len(window.logs) == 1
        assert window.logs[0] == valid_log

        assert window.add_log(invalid_log) is False
        assert len(window.logs) == 1

    def test_time_window_get_error_logs(self) -> None:
        """Test filtering for error-level logs."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        logs = [
            LogEntry(
                insert_id="info", timestamp=start_time, severity="INFO", raw_data={}
            ),
            LogEntry(
                insert_id="error", timestamp=start_time, severity="ERROR", raw_data={}
            ),
            LogEntry(
                insert_id="critical",
                timestamp=start_time,
                severity="CRITICAL",
                raw_data={},
            ),
            LogEntry(
                insert_id="warning",
                timestamp=start_time,
                severity="WARNING",
                raw_data={},
            ),
        ]

        for log in logs:
            window.add_log(log)

        error_logs = window.get_error_logs()
        assert len(error_logs) == 2
        assert error_logs[0].severity == "ERROR"
        assert error_logs[1].severity == "CRITICAL"

    def test_time_window_get_service_groups(self) -> None:
        """Test grouping logs by service."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        logs = [
            LogEntry(
                insert_id="1",
                timestamp=start_time,
                service_name="service-a",
                severity="ERROR",
                raw_data={},
            ),
            LogEntry(
                insert_id="2",
                timestamp=start_time,
                service_name="service-a",
                severity="INFO",
                raw_data={},
            ),
            LogEntry(
                insert_id="3",
                timestamp=start_time,
                service_name="service-b",
                severity="ERROR",
                raw_data={},
            ),
            LogEntry(
                insert_id="4",
                timestamp=start_time,
                service_name=None,
                severity="WARN",
                raw_data={},
            ),
        ]

        for log in logs:
            window.add_log(log)

        groups = window.get_service_groups()
        assert len(groups) == 3
        assert len(groups["service-a"]) == 2
        assert len(groups["service-b"]) == 1
        assert len(groups["unknown"]) == 1


class TestThresholdConfig:
    """Test ThresholdConfig functionality."""

    def test_threshold_config_creation(self) -> None:
        """Test basic ThresholdConfig creation."""
        config = ThresholdConfig(
            threshold_type=ThresholdType.ERROR_FREQUENCY,
            min_value=5.0,
            min_error_count=3,
        )

        assert config.threshold_type == ThresholdType.ERROR_FREQUENCY
        assert config.min_value == 5.0
        assert config.min_error_count == 3
        assert config.min_rate_increase == 10.0

    def test_threshold_config_defaults(self) -> None:
        """Test ThresholdConfig default values."""
        config = ThresholdConfig(
            threshold_type=ThresholdType.ERROR_RATE, min_value=15.0
        )

        assert config.min_error_count == 3
        assert config.min_rate_increase == 10.0
        assert config.baseline_window_count == 12
        assert config.min_affected_services == 2
        assert "CRITICAL" in config.severity_weights
        assert config.severity_weights["CRITICAL"] == 10.0


class TestPatternType:
    """Test PatternType enumeration."""

    def test_pattern_type_constants(self) -> None:
        """Test that all pattern types are defined correctly."""
        assert PatternType.SPORADIC_ERRORS == "sporadic_errors"
        assert PatternType.SERVICE_DEGRADATION == "service_degradation"
        assert PatternType.CASCADE_FAILURE == "cascade_failure"
        assert PatternType.TRAFFIC_SPIKE == "traffic_spike"
        assert PatternType.CONFIGURATION_ISSUE == "configuration_issue"
        assert PatternType.DEPENDENCY_FAILURE == "dependency_failure"
        assert PatternType.RESOURCE_EXHAUSTION == "resource_exhaustion"


class TestPatternMatch:
    """Test PatternMatch dataclass."""

    def test_pattern_match_creation(self) -> None:
        """Test creating PatternMatch objects."""
        pattern = PatternMatch(
            pattern_type=PatternType.SERVICE_DEGRADATION,
            confidence_score=0.85,
            primary_service="billing-service",
            affected_services=["billing-service"],
            severity_level="HIGH",
            evidence={"error_count": 15},
            remediation_priority="HIGH",
            suggested_actions=["Restart service", "Check logs"],
        )

        assert pattern.pattern_type == PatternType.SERVICE_DEGRADATION
        assert pattern.confidence_score == 0.85
        assert pattern.primary_service == "billing-service"
        assert pattern.affected_services == ["billing-service"]
        assert pattern.severity_level == "HIGH"
        assert pattern.evidence == {"error_count": 15}
        assert pattern.remediation_priority == "HIGH"
        assert len(pattern.suggested_actions) == 2


class TestConfidenceFactors:
    """Test ConfidenceFactors enumeration."""

    def test_confidence_factors_enum_values(self) -> None:
        """Test that all confidence factors are properly defined."""
        expected_factors = [
            "TIME_CONCENTRATION",
            "TIME_CORRELATION",
            "RAPID_ONSET",
            "GRADUAL_ONSET",
            "SERVICE_COUNT",
            "SERVICE_DISTRIBUTION",
            "CROSS_SERVICE_CORRELATION",
            "ERROR_FREQUENCY",
            "ERROR_SEVERITY",
            "ERROR_TYPE_CONSISTENCY",
            "MESSAGE_SIMILARITY",
            "BASELINE_DEVIATION",
            "TREND_ANALYSIS",
            "SEASONAL_PATTERN",
            "DEPENDENCY_STATUS",
            "RESOURCE_UTILIZATION",
            "DEPLOYMENT_CORRELATION",
        ]

        for factor in expected_factors:
            assert hasattr(ConfidenceFactors, factor)
            assert isinstance(getattr(ConfidenceFactors, factor), str)


class TestConfidenceRule:
    """Test ConfidenceRule data structure."""

    def test_confidence_rule_creation(self) -> None:
        """Test ConfidenceRule creation with all parameters."""
        rule = ConfidenceRule(
            factor_type=ConfidenceFactors.ERROR_FREQUENCY,
            weight=0.8,
            threshold=10.0,
            max_contribution=0.95,
            decay_function="linear",
            parameters={"min_value": 5, "max_value": 100},
        )

        assert rule.factor_type == ConfidenceFactors.ERROR_FREQUENCY
        assert rule.weight == 0.8
        assert rule.threshold == 10.0
        assert rule.max_contribution == 0.95
        assert rule.decay_function == "linear"
        assert rule.parameters == {"min_value": 5, "max_value": 100}

    def test_confidence_rule_defaults(self) -> None:
        """Test ConfidenceRule default values."""
        rule = ConfidenceRule(
            factor_type=ConfidenceFactors.TIME_CONCENTRATION, weight=0.5
        )

        assert rule.threshold is None
        assert rule.max_contribution == 1.0
        assert rule.decay_function is None
        assert rule.parameters == {}


class TestConfidenceScore:
    """Test ConfidenceScore data structure."""

    def test_confidence_score_creation(self) -> None:
        """Test ConfidenceScore creation with comprehensive data."""
        factor_scores = {
            ConfidenceFactors.ERROR_FREQUENCY: 0.8,
            ConfidenceFactors.ERROR_SEVERITY: 0.9,
        }

        score = ConfidenceScore(
            overall_score=0.85,
            factor_scores=factor_scores,
            raw_factors={"error_frequency": 0.9, "service_impact": 0.8},
            confidence_level="HIGH",
            explanation=["High log volume and severe errors indicate cascade failure"],
        )

        assert score.overall_score == 0.85
        assert score.factor_scores == factor_scores
        assert score.raw_factors == {"error_frequency": 0.9, "service_impact": 0.8}
        assert score.confidence_level == "HIGH"
        assert "cascade failure" in score.explanation[0].lower()
