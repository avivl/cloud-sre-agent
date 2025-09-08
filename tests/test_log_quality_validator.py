"""
Comprehensive unit tests for LogQualityValidator.

Tests log quality validation including completeness assessment,
noise detection, consistency checking, and duplicate analysis.
"""

from datetime import datetime, timedelta
from typing import List

import pytest

from gemini_sre_agent.ml.log_quality_validator import LogQualityValidator
from gemini_sre_agent.ml.validation_config import (
    LogEntry,
    QualityThresholds,
    TimeWindow,
    ValidationMetrics,
    ValidationRules,
)


class TestLogQualityValidator:
    """Test suite for LogQualityValidator class."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.validator = LogQualityValidator()
        self.base_time = datetime.now()

    def create_test_log(
        self,
        service_name: str = "test-service",
        error_message: str = "Test error message",
        severity: str = "ERROR",
        timestamp: datetime = None,
    ) -> LogEntry:
        """Create a test log entry with specified parameters."""
        return LogEntry(
            timestamp=timestamp or self.base_time,
            service_name=service_name,
            error_message=error_message,
            severity=severity,
            trace_id="trace-123",
            span_id="span-456",
        )

    def create_test_window(self, logs: List[LogEntry]) -> TimeWindow:
        """Create a test time window with specified logs."""
        return TimeWindow(
            start_time=self.base_time,
            end_time=self.base_time + timedelta(minutes=10),
            logs=logs,
        )

    def test_validator_initialization_default_thresholds(self):
        """Test validator initialization with default thresholds."""
        validator = LogQualityValidator()
        assert validator.thresholds.min_completeness == 0.80
        assert validator.thresholds.max_noise_ratio == 0.20
        assert validator.thresholds.min_consistency == 0.70
        assert validator.thresholds.max_duplicate_ratio == 0.30

    def test_validator_initialization_custom_thresholds(self):
        """Test validator initialization with custom thresholds."""
        custom_thresholds = QualityThresholds(
            min_completeness=0.90,
            max_noise_ratio=0.10,
            min_consistency=0.80,
            max_duplicate_ratio=0.20,
        )
        validator = LogQualityValidator(custom_thresholds)
        assert validator.thresholds.min_completeness == 0.90
        assert validator.thresholds.max_noise_ratio == 0.10

    def test_empty_log_assessment(self):
        """Test quality assessment with empty logs."""
        empty_window = self.create_test_window([])
        metrics = self.validator.assess_log_quality(empty_window)

        expected = ValidationMetrics.empty_metrics()
        assert metrics == expected

    def test_perfect_quality_logs(self):
        """Test quality assessment with perfect logs."""
        perfect_logs = [
            self.create_test_log(f"service-{i}", f"Error message {i}", "ERROR")
            for i in range(10)
        ]
        window = self.create_test_window(perfect_logs)
        metrics = self.validator.assess_log_quality(window)

        assert metrics["completeness"] == 1.0
        assert metrics["noise_ratio"] == 0.0
        assert metrics["consistency"] == 1.0  # All identical patterns
        assert metrics["duplicate_ratio"] == 0.0
        assert metrics["passes_threshold"] is True
        assert metrics["total_logs_analyzed"] == 10

    def test_completeness_calculation(self):
        """Test completeness calculation with missing fields."""
        logs = [
            self.create_test_log("service-1", "Complete log", "ERROR"),  # Complete
            LogEntry(
                self.base_time, service_name="service-2"
            ),  # Missing message/severity
            LogEntry(
                self.base_time, error_message="Missing service"
            ),  # Missing service
            LogEntry(self.base_time, severity="INFO"),  # Missing service/message
            self.create_test_log("service-5", "Another complete", "WARN"),  # Complete
        ]
        window = self.create_test_window(logs)
        metrics = self.validator.assess_log_quality(window)

        # 2 complete out of 5 logs = 0.4 completeness
        assert metrics["completeness"] == 0.4

    def test_noise_ratio_calculation(self):
        """Test noise ratio calculation with various log types."""
        logs = [
            self.create_test_log(
                "service-1", "Normal error message", "ERROR"
            ),  # Not noisy
            self.create_test_log(
                "service-2", "Debug info", "DEBUG"
            ),  # Noisy - debug level
            self.create_test_log("service-3", "Short", "ERROR"),  # Noisy - too short
            self.create_test_log("service-4", "", "INFO"),  # Noisy - empty message
            self.create_test_log(
                "service-5", "Another normal error", "WARN"
            ),  # Not noisy
        ]
        window = self.create_test_window(logs)
        metrics = self.validator.assess_log_quality(window)

        # 3 noisy out of 5 logs = 0.6 noise ratio
        assert metrics["noise_ratio"] == 0.6

    def test_consistency_calculation(self):
        """Test consistency calculation with message patterns."""
        logs = [
            self.create_test_log(
                "service-1", "Connection failed to 192.168.1.1", "ERROR"
            ),
            self.create_test_log("service-2", "Connection failed to 10.0.0.1", "ERROR"),
            self.create_test_log(
                "service-3", "Connection failed to 172.16.0.1", "ERROR"
            ),
            self.create_test_log("service-4", "Database timeout occurred", "ERROR"),
            self.create_test_log(
                "service-5", "Connection failed to 127.0.0.1", "ERROR"
            ),
        ]
        window = self.create_test_window(logs)
        metrics = self.validator.assess_log_quality(window)

        # 4 similar "Connection failed" patterns out of 5 = 0.8 consistency
        assert metrics["consistency"] == 0.8

    def test_duplicate_ratio_calculation(self):
        """Test duplicate ratio calculation."""
        logs = [
            self.create_test_log("service-1", "Unique message", "ERROR"),
            self.create_test_log("service-2", "Duplicate message", "ERROR"),
            self.create_test_log("service-3", "Duplicate message", "ERROR"),
            self.create_test_log("service-4", "Duplicate message", "ERROR"),
            self.create_test_log("service-5", "Another unique", "ERROR"),
        ]
        window = self.create_test_window(logs)
        metrics = self.validator.assess_log_quality(window)

        # 2 duplicate occurrences out of 5 logs = 0.4 duplicate ratio
        assert metrics["duplicate_ratio"] == 0.4

    def test_validation_passes_all_thresholds(self):
        """Test validation passes when all thresholds are met."""
        # Create high-quality logs that meet all thresholds
        logs = [
            self.create_test_log(
                f"service-{i % 3}", f"Standard error pattern {i}", "ERROR"
            )
            for i in range(10)
        ]
        window = self.create_test_window(logs)

        assert self.validator.validate_for_processing(window) is True

    def test_validation_fails_completeness(self):
        """Test validation fails when completeness threshold is not met."""
        # Most logs missing essential fields
        logs = [
            self.create_test_log("service-1", "Complete log", "ERROR"),  # 1 complete
            LogEntry(self.base_time),  # Incomplete
            LogEntry(self.base_time),  # Incomplete
            LogEntry(self.base_time),  # Incomplete
            LogEntry(self.base_time),  # Incomplete
        ]
        window = self.create_test_window(logs)

        # Completeness = 0.2, below threshold of 0.8
        assert self.validator.validate_for_processing(window) is False

    def test_validation_fails_noise_ratio(self):
        """Test validation fails when noise ratio exceeds threshold."""
        # Mostly noisy logs
        logs = [
            self.create_test_log("service-1", "Good message", "ERROR"),  # Not noisy
            self.create_test_log("service-2", "X", "DEBUG"),  # Noisy - short + debug
            self.create_test_log("service-3", "Y", "DEBUG"),  # Noisy
            self.create_test_log("service-4", "", "TRACE"),  # Noisy - empty + trace
            self.create_test_log("service-5", "Z", "DEBUG"),  # Noisy
        ]
        window = self.create_test_window(logs)

        # Noise ratio = 0.8, above threshold of 0.2
        assert self.validator.validate_for_processing(window) is False

    def test_validation_fails_consistency(self):
        """Test validation fails when consistency is too low."""
        # Very inconsistent messages with truly different patterns
        logs = [
            self.create_test_log("service-1", "Database connection timeout", "ERROR"),
            self.create_test_log(
                "service-2", "Authentication failed for user", "ERROR"
            ),
            self.create_test_log("service-3", "File not found in filesystem", "ERROR"),
            self.create_test_log(
                "service-4", "Memory allocation error occurred", "ERROR"
            ),
            self.create_test_log(
                "service-5", "Network socket closed unexpectedly", "ERROR"
            ),
        ]
        window = self.create_test_window(logs)
        metrics = self.validator.assess_log_quality(window)

        # Each message has a unique pattern, consistency will be 1/5 = 0.2, below threshold of 0.7
        assert metrics["consistency"] == 0.2
        assert self.validator.validate_for_processing(window) is False

    def test_validation_fails_duplicate_ratio(self):
        """Test validation fails when duplicate ratio exceeds threshold."""
        # Too many duplicates
        duplicate_message = "Same error message repeated"
        logs = [
            self.create_test_log("service-1", "Unique message", "ERROR"),  # Unique
            self.create_test_log(
                "service-2", duplicate_message, "ERROR"
            ),  # Duplicate 1
            self.create_test_log(
                "service-3", duplicate_message, "ERROR"
            ),  # Duplicate 2
            self.create_test_log(
                "service-4", duplicate_message, "ERROR"
            ),  # Duplicate 3
            self.create_test_log(
                "service-5", duplicate_message, "ERROR"
            ),  # Duplicate 4
        ]
        window = self.create_test_window(logs)

        # Duplicate ratio = 0.6 (3 extra duplicates / 5 total), above threshold of 0.3
        assert self.validator.validate_for_processing(window) is False

    def test_quality_recommendations_poor_completeness(self):
        """Test quality recommendations for poor completeness."""
        logs = [LogEntry(self.base_time) for _ in range(5)]  # All incomplete
        window = self.create_test_window(logs)
        metrics = self.validator.assess_log_quality(window)
        recommendations = self.validator.get_quality_recommendations(metrics)

        completeness_rec = next(
            (r for r in recommendations if "completeness" in r.lower()), None
        )
        assert completeness_rec is not None
        assert "service_name, error_message, and severity" in completeness_rec

    def test_quality_recommendations_high_noise(self):
        """Test quality recommendations for high noise ratio."""
        logs = [
            self.create_test_log("service", "X", "DEBUG") for _ in range(5)
        ]  # All noisy
        window = self.create_test_window(logs)
        metrics = self.validator.assess_log_quality(window)
        recommendations = self.validator.get_quality_recommendations(metrics)

        noise_rec = next((r for r in recommendations if "noise" in r.lower()), None)
        assert noise_rec is not None
        assert "DEBUG/TRACE" in noise_rec

    def test_quality_recommendations_low_consistency(self):
        """Test quality recommendations for low consistency."""
        # Use truly different message patterns to get low consistency
        logs = [
            self.create_test_log("service-1", "Database connection failed", "ERROR"),
            self.create_test_log("service-2", "Authentication error occurred", "ERROR"),
            self.create_test_log("service-3", "File system access denied", "ERROR"),
            self.create_test_log("service-4", "Memory allocation failed", "ERROR"),
            self.create_test_log("service-5", "Network timeout detected", "ERROR"),
        ]
        window = self.create_test_window(logs)
        metrics = self.validator.assess_log_quality(window)
        recommendations = self.validator.get_quality_recommendations(metrics)

        consistency_rec = next(
            (r for r in recommendations if "consistency" in r.lower()), None
        )
        assert consistency_rec is not None
        assert "standardize log formats" in consistency_rec

    def test_quality_recommendations_high_duplicates(self):
        """Test quality recommendations for high duplicate ratio."""
        logs = [
            self.create_test_log("service", "Same message", "ERROR") for _ in range(5)
        ]  # All duplicates
        window = self.create_test_window(logs)
        metrics = self.validator.assess_log_quality(window)
        recommendations = self.validator.get_quality_recommendations(metrics)

        duplicate_rec = next(
            (r for r in recommendations if "duplicate" in r.lower()), None
        )
        assert duplicate_rec is not None
        assert "deduplication or rate limiting" in duplicate_rec

    def test_quality_recommendations_good_quality(self):
        """Test quality recommendations for good quality logs."""
        logs = [
            self.create_test_log(f"service-{i % 2}", f"Error pattern {i}", "ERROR")
            for i in range(10)
        ]
        window = self.create_test_window(logs)
        metrics = self.validator.assess_log_quality(window)
        recommendations = self.validator.get_quality_recommendations(metrics)

        assert len(recommendations) == 1
        assert "meets all thresholds" in recommendations[0]

    def test_pattern_extraction_normalization(self):
        """Test message pattern extraction and normalization."""
        validator = self.validator

        # Test number normalization
        pattern1 = validator._extract_message_pattern("Error code 404 encountered")
        pattern2 = validator._extract_message_pattern("Error code 500 encountered")
        assert (
            pattern1 == pattern2
        )  # Both should normalize to "Error code N encountered"

        # Test UUID normalization (8+ hex chars)
        uuid_pattern1 = validator._extract_message_pattern(
            "User abc123def456 not found"
        )
        uuid_pattern2 = validator._extract_message_pattern(
            "User 1234567890abcdef not found"
        )
        assert uuid_pattern1 == uuid_pattern2  # Both should use ID placeholder

        # Test IP address normalization
        ip_pattern1 = validator._extract_message_pattern(
            "Connection to 192.168.1.1 failed"
        )
        ip_pattern2 = validator._extract_message_pattern(
            "Connection to 10.0.0.1 failed"
        )
        assert ip_pattern1 == ip_pattern2  # Both should use IP placeholder

    def test_noisy_log_detection(self):
        """Test noisy log detection logic."""
        validator = self.validator

        # Test short message detection
        short_log = LogEntry(self.base_time, error_message="Short", severity="ERROR")
        assert validator._is_noisy_log(short_log) is True

        # Test debug level detection
        debug_log = LogEntry(
            self.base_time, error_message="Debug information", severity="DEBUG"
        )
        assert validator._is_noisy_log(debug_log) is True

        # Test trace level detection
        trace_log = LogEntry(
            self.base_time, error_message="Trace information", severity="TRACE"
        )
        assert validator._is_noisy_log(trace_log) is True

        # Test empty message detection
        empty_log = LogEntry(self.base_time, error_message="", severity="ERROR")
        assert validator._is_noisy_log(empty_log) is True

        # Test good log
        good_log = self.create_test_log("service", "Proper error message", "ERROR")
        assert validator._is_noisy_log(good_log) is False

    def test_overall_quality_calculation(self):
        """Test overall quality score calculation."""
        # Create mixed quality logs
        logs = [
            self.create_test_log("service-1", "Good error message", "ERROR"),  # Good
            self.create_test_log("service-2", "Another good message", "ERROR"),  # Good
            LogEntry(self.base_time, service_name="service-3"),  # Incomplete
            self.create_test_log("service-4", "X", "DEBUG"),  # Noisy
            self.create_test_log("service-5", "Final good message", "ERROR"),  # Good
        ]
        window = self.create_test_window(logs)
        metrics = self.validator.assess_log_quality(window)

        # Overall quality should be average of quality factors
        expected_quality = (
            metrics["quality_factors"]["completeness"]
            + metrics["quality_factors"]["low_noise"]
            + metrics["quality_factors"]["consistency"]
            + metrics["quality_factors"]["low_duplicates"]
        ) / 4

        assert abs(metrics["overall_quality"] - expected_quality) < 1e-10


class TestValidationConfig:
    """Test suite for validation configuration classes."""

    def test_log_entry_creation(self):
        """Test LogEntry creation and post_init."""
        timestamp = datetime.now()
        log_entry = LogEntry(timestamp=timestamp, service_name="test-service")

        assert log_entry.timestamp == timestamp
        assert log_entry.service_name == "test-service"
        assert log_entry.metadata == {}  # Should be initialized in post_init

    def test_quality_thresholds_defaults(self):
        """Test QualityThresholds default values."""
        thresholds = QualityThresholds()

        assert thresholds.min_completeness == 0.80
        assert thresholds.max_noise_ratio == 0.20
        assert thresholds.min_consistency == 0.70
        assert thresholds.max_duplicate_ratio == 0.30
        assert thresholds.overall_quality_threshold == 0.75

    def test_time_window_creation(self):
        """Test TimeWindow creation and validation."""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)
        logs = [LogEntry(start_time)]

        window = TimeWindow(start_time=start_time, end_time=end_time, logs=logs)

        assert window.start_time == start_time
        assert window.end_time == end_time
        assert window.logs == logs
        assert window.duration_seconds == 3600.0  # 1 hour
        assert window.log_count == 1

    def test_time_window_invalid_times(self):
        """Test TimeWindow validation with invalid time range."""
        start_time = datetime.now()
        end_time = start_time - timedelta(hours=1)  # End before start

        with pytest.raises(ValueError, match="start_time must be before end_time"):
            TimeWindow(start_time=start_time, end_time=end_time, logs=[])

    def test_validation_metrics_helpers(self):
        """Test ValidationMetrics helper methods."""
        # Test empty metrics
        empty = ValidationMetrics.empty_metrics()
        assert empty["overall_quality"] == 0.0
        assert empty["noise_ratio"] == 1.0
        assert empty["passes_threshold"] is False

        # Test quality score formatting
        assert ValidationMetrics.format_quality_score(0.75) == "75.0%"
        assert ValidationMetrics.format_quality_score(0.0) == "0.0%"

        # Test quality level categorization
        assert ValidationMetrics.categorize_quality_level(0.95) == "EXCELLENT"
        assert ValidationMetrics.categorize_quality_level(0.85) == "GOOD"
        assert ValidationMetrics.categorize_quality_level(0.75) == "FAIR"
        assert ValidationMetrics.categorize_quality_level(0.60) == "POOR"
        assert ValidationMetrics.categorize_quality_level(0.30) == "CRITICAL"

    def test_validation_rules_helpers(self):
        """Test ValidationRules helper methods."""
        timestamp = datetime.now()

        # Test complete log
        complete_log = LogEntry(
            timestamp=timestamp,
            service_name="test-service",
            error_message="Test error",
            severity="ERROR",
        )
        assert ValidationRules.is_essential_field_complete(complete_log) is True

        # Test incomplete log
        incomplete_log = LogEntry(timestamp=timestamp, service_name="test-service")
        assert ValidationRules.is_essential_field_complete(incomplete_log) is False

        # Test noisy severity detection
        assert ValidationRules.is_noisy_severity("DEBUG") is True
        assert ValidationRules.is_noisy_severity("TRACE") is True
        assert ValidationRules.is_noisy_severity("ERROR") is False
        assert ValidationRules.is_noisy_severity(None) is False

        # Test message length validation
        assert ValidationRules.is_message_too_short("Short") is True
        assert ValidationRules.is_message_too_short("This is a longer message") is False
        assert ValidationRules.is_message_too_short("") is True
        assert ValidationRules.is_message_too_short(None) is True


if __name__ == "__main__":
    pytest.main([__file__])
