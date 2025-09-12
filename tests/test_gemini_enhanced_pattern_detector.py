"""
Comprehensive unit tests for GeminiEnhancedPatternDetector.

Tests ensemble pattern detection modes, fallback mechanisms, pattern merging,
confidence thresholding, and feedback processing.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from gemini_sre_agent.ml.gemini_enhanced_pattern_detector import (
    GeminiEnhancedPatternDetector,
)
from gemini_sre_agent.pattern_detector.models import (
    LogEntry,
    PatternMatch,
    PatternType,
    ThresholdResult,
    TimeWindow,
)


class TestGeminiEnhancedPatternDetectorInit:
    """Test GeminiEnhancedPatternDetector initialization."""

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    def test_successful_init(self, mock_pattern_classifier: str, mock_gemini_classifier: str) -> None:
        """Test successful detector initialization."""
        detector = GeminiEnhancedPatternDetector(gemini_api_key="test_key")

        assert detector.ensemble_mode == "gemini_primary"
        assert detector.confidence_threshold == 0.6
        assert detector.fallback_enabled is True
        assert detector.code_context_extractor is None

        mock_gemini_classifier.assert_called_once()
        mock_pattern_classifier.assert_called_once()

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    def test_init_with_custom_config(
        self, mock_pattern_classifier, mock_gemini_classifier
    ):
        """Test initialization with custom configuration."""
        config = {
            "ensemble_mode": "ensemble",
            "gemini_confidence_threshold": 0.8,
            "fallback_enabled": False,
        }
        detector = GeminiEnhancedPatternDetector(
            gemini_api_key="test_key", config=config
        )

        assert detector.ensemble_mode == "ensemble"
        assert detector.confidence_threshold == 0.8
        assert detector.fallback_enabled is False

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    def test_init_with_monitoring_components(
        self, mock_pattern_classifier, mock_gemini_classifier
    ):
        """Test initialization with cost tracker and rate limiter."""
        cost_tracker = Mock()
        rate_limiter = Mock()

        GeminiEnhancedPatternDetector(
            gemini_api_key="test_key",
            cost_tracker=cost_tracker,
            rate_limiter=rate_limiter,
        )

        # Check that GeminiPatternClassifier was initialized with monitoring components
        expected_config = {
            "classification_model": "gemini-1.5-pro",
            "fast_classification_model": "gemini-1.5-flash",
            "confidence_model": "gemini-1.5-pro",
        }
        mock_gemini_classifier.assert_called_once_with(
            api_key="test_key",
            config=expected_config,
            cost_tracker=cost_tracker,
            rate_limiter=rate_limiter,
        )

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    def test_init_with_code_analysis(
        self, mock_pattern_classifier, mock_gemini_classifier
    ):
        """Test initialization with code analysis enabled (currently disabled)."""
        config = {
            "code_analysis": {
                "enabled": True,
                "repository_path": "/path/to/repo",
                "main_branch": "master",
                "enable_static_analysis": True,
            }
        }

        detector = GeminiEnhancedPatternDetector(
            gemini_api_key="test_key", config=config
        )

        # Code analysis is currently disabled, so extractor should be None
        assert detector.code_context_extractor is None


class TestGeminiEnhancedPatternDetectorClassification:
    """Test pattern classification functionality."""

    @pytest.fixture
    def sample_window(self) -> None:
        """Create sample time window with logs."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        window.logs = [
            LogEntry(
                insert_id="log1",
                timestamp=start_time,
                severity="ERROR",
                service_name="api-service",
                error_message="Connection timeout",
                raw_data={},
            ),
            LogEntry(
                insert_id="log2",
                timestamp=start_time,
                severity="CRITICAL",
                service_name="db-service",
                error_message="Database connection failed",
                raw_data={},
            ),
        ]

        return window

    @pytest.fixture
    def sample_threshold_results(self) -> None:
        """Create sample threshold results."""
        return [
            ThresholdResult(
                threshold_type="error_frequency",
                triggered=True,
                score=85.0,
                details={"description": "High error frequency detected"},
                triggering_logs=[],
                affected_services=["api-service"],
            )
        ]

    @pytest.fixture
    def sample_gemini_pattern(self) -> None:
        """Create sample Gemini pattern match."""
        return PatternMatch(
            pattern_type=PatternType.CASCADE_FAILURE,
            confidence_score=0.85,
            primary_service="api-service",
            affected_services=["api-service", "db-service"],
            severity_level="HIGH",
            evidence={"gemini_classification": True},
            remediation_priority="high",
            suggested_actions=["Check service dependencies"],
        )

    @pytest.fixture
    def sample_rule_pattern(self) -> None:
        """Create sample rule-based pattern match."""
        return PatternMatch(
            pattern_type=PatternType.CASCADE_FAILURE,
            confidence_score=0.75,
            primary_service="api-service",
            affected_services=["api-service", "db-service"],
            severity_level="MEDIUM",
            evidence={"rule_based": True},
            remediation_priority="medium",
            suggested_actions=["Review error logs"],
        )

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    @pytest.mark.asyncio
    async def test_rules_only_mode(
        self,
        mock_pattern_classifier_class,
        mock_gemini_classifier_class,
        sample_window,
        sample_threshold_results,
        sample_rule_pattern,
    ):
        """Test rules-only ensemble mode."""
        mock_rule_classifier = Mock()
        mock_rule_classifier.classify_patterns.return_value = [sample_rule_pattern]
        mock_pattern_classifier_class.return_value = mock_rule_classifier

        config = {"ensemble_mode": "rules_only"}
        detector = GeminiEnhancedPatternDetector(
            gemini_api_key="test_key", config=config
        )

        results = await detector.classify_patterns(
            sample_window, sample_threshold_results
        )

        assert len(results) == 1
        assert results[0].pattern_type == PatternType.CASCADE_FAILURE
        mock_rule_classifier.classify_patterns.assert_called_once()

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    @pytest.mark.asyncio
    async def test_gemini_primary_mode_high_confidence(
        self,
        mock_pattern_classifier_class,
        mock_gemini_classifier_class,
        sample_window,
        sample_threshold_results,
        sample_gemini_pattern,
        sample_rule_pattern,
    ):
        """Test Gemini-primary mode with high confidence patterns."""
        mock_gemini_classifier = AsyncMock()
        mock_gemini_classifier.classify_patterns.return_value = [sample_gemini_pattern]
        mock_gemini_classifier_class.return_value = mock_gemini_classifier

        mock_rule_classifier = Mock()
        mock_rule_classifier.classify_patterns.return_value = [sample_rule_pattern]
        mock_pattern_classifier_class.return_value = mock_rule_classifier

        detector = GeminiEnhancedPatternDetector(gemini_api_key="test_key")

        results = await detector.classify_patterns(
            sample_window, sample_threshold_results
        )

        assert len(results) == 1
        pattern = results[0]

        # Should be enhanced with rule-based evidence (when rules also get executed)
        # The confidence should be boosted when both approaches agree
        assert pattern.confidence_score >= sample_gemini_pattern.confidence_score
        if "rule_based_confidence" in pattern.evidence:
            assert pattern.confidence_score > sample_gemini_pattern.confidence_score
            assert "approaches_agree" in pattern.evidence

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    @pytest.mark.asyncio
    async def test_gemini_primary_mode_low_confidence_fallback(
        self,
        mock_pattern_classifier_class,
        mock_gemini_classifier_class,
        sample_window,
        sample_threshold_results,
        sample_rule_pattern,
    ):
        """Test fallback to rules when Gemini confidence is low."""
        # Low confidence Gemini pattern
        low_confidence_pattern = PatternMatch(
            pattern_type=PatternType.SERVICE_DEGRADATION,
            confidence_score=0.4,  # Below threshold
            primary_service="api-service",
            affected_services=["api-service"],
            severity_level="LOW",
            evidence={"gemini_classification": True},
            remediation_priority="low",
            suggested_actions=["Monitor service"],
        )

        mock_gemini_classifier = AsyncMock()
        mock_gemini_classifier.classify_patterns.return_value = [low_confidence_pattern]
        mock_gemini_classifier_class.return_value = mock_gemini_classifier

        mock_rule_classifier = Mock()
        mock_rule_classifier.classify_patterns.return_value = [sample_rule_pattern]
        mock_pattern_classifier_class.return_value = mock_rule_classifier

        detector = GeminiEnhancedPatternDetector(gemini_api_key="test_key")

        results = await detector.classify_patterns(
            sample_window, sample_threshold_results
        )

        # Should use rule-based pattern due to low Gemini confidence
        assert len(results) == 1
        assert results[0].pattern_type == PatternType.CASCADE_FAILURE
        assert results[0].confidence_score == 0.75

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    @pytest.mark.asyncio
    async def test_ensemble_mode(
        self,
        mock_pattern_classifier_class,
        mock_gemini_classifier_class,
        sample_window,
        sample_threshold_results,
        sample_gemini_pattern,
        sample_rule_pattern,
    ):
        """Test ensemble mode combining both approaches."""
        mock_gemini_classifier = AsyncMock()
        mock_gemini_classifier.classify_patterns.return_value = [sample_gemini_pattern]
        mock_gemini_classifier_class.return_value = mock_gemini_classifier

        mock_rule_classifier = Mock()
        mock_rule_classifier.classify_patterns.return_value = [sample_rule_pattern]
        mock_pattern_classifier_class.return_value = mock_rule_classifier

        config = {"ensemble_mode": "ensemble"}
        detector = GeminiEnhancedPatternDetector(
            gemini_api_key="test_key", config=config
        )

        results = await detector.classify_patterns(
            sample_window, sample_threshold_results
        )

        assert len(results) == 1
        pattern = results[0]

        # Should be merged pattern
        assert "ensemble_method" in pattern.evidence
        assert "gemini_weight" in pattern.evidence
        assert "rule_weight" in pattern.evidence

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    @pytest.mark.asyncio
    async def test_error_handling_with_fallback(
        self,
        mock_pattern_classifier_class,
        mock_gemini_classifier_class,
        sample_window,
        sample_threshold_results,
        sample_rule_pattern,
    ):
        """Test error handling with fallback enabled."""
        mock_gemini_classifier = AsyncMock()
        mock_gemini_classifier.classify_patterns.side_effect = Exception("API Error")
        mock_gemini_classifier_class.return_value = mock_gemini_classifier

        mock_rule_classifier = Mock()
        mock_rule_classifier.classify_patterns.return_value = [sample_rule_pattern]
        mock_pattern_classifier_class.return_value = mock_rule_classifier

        detector = GeminiEnhancedPatternDetector(gemini_api_key="test_key")

        results = await detector.classify_patterns(
            sample_window, sample_threshold_results
        )

        # Should fallback to rule-based classification
        assert len(results) == 1
        assert results[0].pattern_type == PatternType.CASCADE_FAILURE

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    @pytest.mark.asyncio
    async def test_error_handling_without_fallback(
        self,
        mock_pattern_classifier_class,
        mock_gemini_classifier_class,
        sample_window,
        sample_threshold_results,
    ):
        """Test error handling with fallback disabled."""
        mock_gemini_classifier = AsyncMock()
        mock_gemini_classifier.classify_patterns.side_effect = Exception("API Error")
        mock_gemini_classifier_class.return_value = mock_gemini_classifier

        config = {"fallback_enabled": False}
        detector = GeminiEnhancedPatternDetector(
            gemini_api_key="test_key", config=config
        )

        results = await detector.classify_patterns(
            sample_window, sample_threshold_results
        )

        # Should return empty list when no fallback
        assert len(results) == 0


class TestGeminiEnhancedPatternDetectorPatternMerging:
    """Test pattern merging functionality."""

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    def test_merge_patterns_high_confidence(
        self, mock_pattern_classifier, mock_gemini_classifier
    ):
        """Test merging patterns with high Gemini confidence."""
        detector = GeminiEnhancedPatternDetector(gemini_api_key="test_key")

        gemini_pattern = PatternMatch(
            pattern_type=PatternType.CASCADE_FAILURE,
            confidence_score=0.9,  # High confidence
            primary_service="api-service",
            affected_services=["api-service", "db-service"],
            severity_level="HIGH",
            evidence={"gemini_classification": True},
            remediation_priority="high",
            suggested_actions=["Check dependencies"],
        )

        rule_pattern = PatternMatch(
            pattern_type=PatternType.CASCADE_FAILURE,
            confidence_score=0.8,
            primary_service="api-service",
            affected_services=["api-service", "cache-service"],
            severity_level="CRITICAL",
            evidence={"rule_based": True},
            remediation_priority="high",
            suggested_actions=["Review logs"],
        )

        merged = detector._merge_patterns(gemini_pattern, rule_pattern)

        # Should use weighted combination favoring Gemini (0.7 weight)
        expected_confidence = 0.9 * 0.7 + 0.8 * 0.3
        assert abs(merged.confidence_score - expected_confidence) < 0.01

        # Should take highest severity (CRITICAL > HIGH)
        assert merged.severity_level == "CRITICAL"

        # Should merge services
        assert "api-service" in merged.affected_services
        assert "db-service" in merged.affected_services
        assert "cache-service" in merged.affected_services

        # Should combine actions
        assert "Check dependencies" in merged.suggested_actions
        assert "Review logs" in merged.suggested_actions

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    def test_merge_patterns_low_confidence(
        self, mock_pattern_classifier, mock_gemini_classifier
    ):
        """Test merging patterns with low Gemini confidence."""
        detector = GeminiEnhancedPatternDetector(gemini_api_key="test_key")

        gemini_pattern = PatternMatch(
            pattern_type=PatternType.CASCADE_FAILURE,
            confidence_score=0.5,  # Low confidence
            primary_service="api-service",
            affected_services=["api-service"],
            severity_level="MEDIUM",
            evidence={"gemini_classification": True},
            remediation_priority="medium",
            suggested_actions=["Monitor"],
        )

        rule_pattern = PatternMatch(
            pattern_type=PatternType.CASCADE_FAILURE,
            confidence_score=0.8,
            primary_service="api-service",
            affected_services=["api-service"],
            severity_level="HIGH",
            evidence={"rule_based": True},
            remediation_priority="high",
            suggested_actions=["Investigate"],
        )

        merged = detector._merge_patterns(gemini_pattern, rule_pattern)

        # Should use weighted combination favoring rules (0.6 weight)
        expected_confidence = 0.5 * 0.4 + 0.8 * 0.6
        assert abs(merged.confidence_score - expected_confidence) < 0.01

        # Should have ensemble evidence
        assert "ensemble_method" in merged.evidence
        assert merged.evidence["gemini_weight"] == 0.4
        assert merged.evidence["rule_weight"] == 0.6


class TestGeminiEnhancedPatternDetectorFeedback:
    """Test feedback processing functionality."""

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    @pytest.mark.asyncio
    async def test_process_feedback(
        self, mock_pattern_classifier, mock_gemini_classifier
    ):
        """Test processing feedback for continuous learning."""
        mock_gemini_classifier_instance = AsyncMock()
        mock_gemini_classifier.return_value = mock_gemini_classifier_instance

        detector = GeminiEnhancedPatternDetector(gemini_api_key="test_key")

        # Should not raise exception - feedback processing is implemented as logging for now
        await detector.process_feedback(
            window_id="window_123",
            predicted_pattern="cascade_failure",
            actual_pattern="service_degradation",
            user_id="user_456",
            notes="Pattern was actually service degradation",
        )

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    @pytest.mark.asyncio
    async def test_process_feedback_error_handling(
        self, mock_pattern_classifier, mock_gemini_classifier
    ):
        """Test error handling during feedback processing."""
        detector = GeminiEnhancedPatternDetector(gemini_api_key="test_key")

        # Should not raise exception even with None values
        await detector.process_feedback(
            window_id="window_123",
            predicted_pattern="cascade_failure",
            actual_pattern="service_degradation",
            user_id="user_456",
            notes=None,
        )


class TestGeminiEnhancedPatternDetectorStats:
    """Test performance statistics functionality."""

    @patch(
        "gemini_sre_agent.ml.gemini_enhanced_pattern_detector.GeminiPatternClassifier"
    )
    @patch("gemini_sre_agent.ml.gemini_enhanced_pattern_detector.PatternClassifier")
    def test_get_performance_stats(
        self, mock_pattern_classifier, mock_gemini_classifier
    ):
        """Test performance statistics retrieval."""
        mock_gemini_classifier_instance = Mock()
        mock_gemini_classifier_instance.get_performance_stats.return_value = {
            "total_classifications": 10,
            "successful_classifications": 8,
            "success_rate_percent": 80.0,
        }
        mock_gemini_classifier.return_value = mock_gemini_classifier_instance

        detector = GeminiEnhancedPatternDetector(gemini_api_key="test_key")

        stats = detector.get_performance_stats()

        assert stats["ensemble_mode"] == "gemini_primary"
        assert stats["confidence_threshold"] == 0.6
        assert stats["fallback_enabled"] is True
        assert "gemini_stats" in stats
        assert stats["gemini_stats"]["total_classifications"] == 10
