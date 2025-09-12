"""
Tests for the confidence scoring system.
"""

from datetime import datetime, timedelta, timezone

import pytest

from gemini_sre_agent.pattern_detector.confidence_scorer import ConfidenceScorer
from gemini_sre_agent.pattern_detector.models import (
    ConfidenceFactors,
    LogEntry,
    PatternType,
    ThresholdResult,
    ThresholdType,
    TimeWindow,
)


class TestConfidenceScorer:
    """Test ConfidenceScorer comprehensive scoring engine."""

    @pytest.fixture
    def sample_logs(self) -> None:
        """Create sample log entries for testing."""
        base_time = datetime.now(timezone.utc)
        logs = []
        for i in range(10):
            logs.append(
                LogEntry(
                    insert_id=f"log-{i}",
                    timestamp=base_time + timedelta(seconds=i * 30),
                    severity="ERROR" if i % 2 == 0 else "WARNING",
                    service_name=f"service-{i % 3}",
                    error_message=f"Database connection failed: timeout after {i}s",
                    raw_data={},
                )
            )
        return logs

    @pytest.fixture
    def sample_window(self, sample_logs: str) -> None:
        """Create a sample time window with logs."""
        base_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=base_time, duration_minutes=5)
        for log in sample_logs:
            window.add_log(log)
        return window

    @pytest.fixture
    def sample_threshold_results(self, sample_logs: str) -> None:
        """Create sample threshold results."""
        return [
            ThresholdResult(
                threshold_type=ThresholdType.ERROR_FREQUENCY,
                triggered=True,
                score=8.5,
                details={
                    "baseline": 3.0,
                    "current_value": 25.0,
                    "threshold_value": 10.0,
                    "reason": "High error frequency detected",
                },
                triggering_logs=sample_logs[:5],
                affected_services=["service-0", "service-1"],
            ),
            ThresholdResult(
                threshold_type=ThresholdType.SERVICE_IMPACT,
                triggered=True,
                score=7.2,
                details={
                    "baseline": 2.0,
                    "current_value": 5.0,
                    "threshold_value": 3.0,
                    "reason": "Multiple services impacted",
                },
                triggering_logs=sample_logs[5:],
                affected_services=["service-0", "service-1", "service-2"],
            ),
        ]

    def test_confidence_scorer_initialization(self) -> None:
        """Test ConfidenceScorer initialization."""
        scorer = ConfidenceScorer()
        assert scorer.confidence_rules is not None
        assert PatternType.CASCADE_FAILURE in scorer.confidence_rules

    def test_calculate_confidence_score(
        self, sample_window, sample_threshold_results, sample_logs
    ):
        """Test comprehensive confidence score calculation."""
        scorer = ConfidenceScorer()
        confidence_score = scorer.calculate_confidence(
            pattern_type=PatternType.CASCADE_FAILURE,
            window=sample_window,
            logs=sample_logs,
            additional_context={"recent_deployment": True},
        )
        assert 0.0 <= confidence_score.overall_score <= 1.0
        assert confidence_score.confidence_level in [
            "VERY_LOW",
            "LOW",
            "MEDIUM",
            "HIGH",
            "VERY_HIGH",
        ]
        assert len(confidence_score.explanation) > 0
        assert len(confidence_score.factor_scores) > 0

    def test_calculate_raw_factors(
        self, sample_window, sample_threshold_results, sample_logs
    ):
        """Test calculation of raw confidence factors."""
        scorer = ConfidenceScorer()
        raw_factors = scorer._calculate_raw_factors(
            window=sample_window,
            logs=sample_logs,
            context={},
        )
        for factor_name in ConfidenceFactors.__dict__:
            if not factor_name.startswith("__"):
                factor_key = getattr(ConfidenceFactors, factor_name)
                assert factor_key in raw_factors
                assert isinstance(raw_factors[factor_key], float)

    def test_time_concentration_factor(self, sample_window: str, sample_logs: str) -> None:
        """Test time concentration factor calculation."""
        scorer = ConfidenceScorer()
        concentrated_logs = sample_logs[:5]
        concentration = scorer._calculate_time_concentration(
            concentrated_logs, sample_window
        )
        assert concentration > 0.5
        dispersed_logs = [sample_logs[0], sample_logs[-1]]
        concentration = scorer._calculate_time_concentration(
            dispersed_logs, sample_window
        )
        assert concentration < 0.5

    def test_service_distribution_factor(self, sample_logs: str) -> None:
        """Test service distribution factor calculation."""
        scorer = ConfidenceScorer()
        distribution = scorer._calculate_service_distribution(sample_logs)
        assert distribution > 0.5
        uneven_logs = sample_logs[:8]
        distribution = scorer._calculate_service_distribution(uneven_logs)
        assert distribution > 0.5

    def test_message_similarity_factor(self, sample_logs: str) -> None:
        """Test error message similarity factor calculation."""
        scorer = ConfidenceScorer()
        similar_logs = [
            LogEntry(
                insert_id="1",
                timestamp=datetime.now(),
                severity="ERROR",
                error_message="Database connection failed",
                raw_data={},
            ),
            LogEntry(
                insert_id="2",
                timestamp=datetime.now(),
                severity="ERROR",
                error_message="Database connection timeout",
                raw_data={},
            ),
        ]
        similarity = scorer._calculate_message_similarity(similar_logs)
        assert similarity == 0.5
        dissimilar_logs = [
            LogEntry(
                insert_id="1",
                timestamp=datetime.now(),
                severity="ERROR",
                error_message="Null pointer exception",
                raw_data={},
            ),
            LogEntry(
                insert_id="2",
                timestamp=datetime.now(),
                severity="ERROR",
                error_message="File not found",
                raw_data={},
            ),
        ]
        similarity = scorer._calculate_message_similarity(dissimilar_logs)
        assert similarity < 0.5

    def test_confidence_level_determination(self) -> None:
        """Test determination of confidence level from score."""
        scorer = ConfidenceScorer()
        assert scorer._determine_confidence_level(0.95) == "VERY_HIGH"
        assert scorer._determine_confidence_level(0.8) == "HIGH"
        assert scorer._determine_confidence_level(0.6) == "MEDIUM"
        assert scorer._determine_confidence_level(0.3) == "LOW"
        assert scorer._determine_confidence_level(0.1) == "VERY_LOW"

    def test_explanation_generation(self) -> None:
        """Test generation of human-readable explanation."""
        scorer = ConfidenceScorer()
        factor_scores = {
            ConfidenceFactors.ERROR_FREQUENCY: 0.8,
            ConfidenceFactors.TIME_CONCENTRATION: 0.7,
            ConfidenceFactors.SERVICE_COUNT: 0.6,
        }
        raw_factors = {
            ConfidenceFactors.ERROR_FREQUENCY: 25.0,
            ConfidenceFactors.TIME_CONCENTRATION: 0.9,
            ConfidenceFactors.SERVICE_COUNT: 3.0,
        }
        explanation = scorer._generate_explanation(
            pattern_type=PatternType.CASCADE_FAILURE,
            factor_scores=factor_scores,
            raw_factors=raw_factors,
        )
        assert len(explanation) > 1
        assert "cascade_failure" in explanation[0].lower()
        assert "error_frequency" in " ".join(explanation).lower()
        assert "time_concentration" in " ".join(explanation).lower()
