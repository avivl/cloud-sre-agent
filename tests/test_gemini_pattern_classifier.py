"""
Comprehensive unit tests for GeminiPatternClassifier.

Tests cover pattern classification, confidence assessment, model selection,
structured output parsing, and performance tracking.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from gemini_sre_agent.ml.gemini_api_client import GeminiResponse
from gemini_sre_agent.ml.gemini_pattern_classifier import GeminiPatternClassifier
from gemini_sre_agent.pattern_detector.models import LogEntry, PatternType, TimeWindow


class TestGeminiPatternClassifierInit:
    """Test GeminiPatternClassifier initialization."""

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    def test_successful_init(self, mock_gemini_client_class):
        """Test successful classifier initialization."""
        classifier = GeminiPatternClassifier(api_key="test_key")

        assert classifier._classification_count == 0
        assert classifier._successful_classifications == 0
        assert classifier.confidence_assessment_threshold == 0.7
        mock_gemini_client_class.assert_called_once()

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    def test_init_with_custom_config(self, mock_gemini_client_class):
        """Test initialization with custom configuration."""
        config = {"confidence_threshold": 0.8}
        classifier = GeminiPatternClassifier(api_key="test_key", config=config)

        assert classifier.confidence_assessment_threshold == 0.8

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    def test_init_with_monitoring_components(self, mock_gemini_client_class):
        """Test initialization with cost tracker and rate limiter."""
        cost_tracker = Mock()
        rate_limiter = Mock()

        classifier = GeminiPatternClassifier(
            api_key="test_key", cost_tracker=cost_tracker, rate_limiter=rate_limiter
        )

        # Check that GeminiAPIClient was initialized with monitoring components
        mock_gemini_client_class.assert_called_once_with(
            api_key="test_key", cost_tracker=cost_tracker, rate_limiter=rate_limiter
        )


class TestGeminiPatternClassifierClassification:
    """Test pattern classification functionality."""

    @pytest.fixture
    def sample_window(self):
        """Create sample time window with logs."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        # Add sample logs
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
    def sample_threshold_results(self):
        """Create sample threshold results."""
        return [
            {
                "type": "error_frequency",
                "triggered": True,
                "score": 85.0,
                "description": "High error frequency detected",
                "triggering_logs": [],
            }
        ]

    @pytest.fixture
    def mock_gemini_response(self):
        """Create mock successful Gemini response."""
        classification_result = {
            "pattern_type": "cascade_failure",
            "confidence_score": 0.85,
            "reasoning": "Multiple service failures with temporal correlation",
            "key_indicators": ["cross-service errors", "temporal clustering"],
            "severity_assessment": "HIGH",
            "affected_services_analysis": {
                "primary": "api-service",
                "secondary": ["db-service", "auth-service"],
            },
            "recommended_actions": ["Check service dependencies", "Review logs"],
        }

        return GeminiResponse(
            success=True,
            content=json.dumps(classification_result),
            parsed_json=classification_result,
            tokens_used=150,
            latency_ms=250.0,
            model_used="gemini-1.5-pro",
        )

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    @pytest.mark.asyncio
    async def test_successful_classification(
        self,
        mock_gemini_client_class,
        sample_window,
        sample_threshold_results,
        mock_gemini_response,
    ):
        """Test successful pattern classification."""
        mock_gemini_client = AsyncMock()
        mock_gemini_client.generate_response.return_value = mock_gemini_response
        mock_gemini_client_class.return_value = mock_gemini_client

        classifier = GeminiPatternClassifier(api_key="test_key")
        results = await classifier.classify_patterns(
            sample_window, sample_threshold_results
        )

        assert len(results) == 1
        pattern_match = results[0]

        assert pattern_match.pattern_type == PatternType.CASCADE_FAILURE
        assert pattern_match.confidence_score == 0.85
        assert pattern_match.severity_level == "HIGH"
        assert pattern_match.primary_service == "api-service"
        assert "db-service" in pattern_match.affected_services
        assert "Check service dependencies" in pattern_match.suggested_actions

        # Verify API call was made
        mock_gemini_client.generate_response.assert_called_once()

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    @pytest.mark.asyncio
    async def test_low_confidence_triggers_assessment(
        self,
        mock_gemini_client_class,
        sample_window,
        sample_threshold_results,
    ):
        """Test that low confidence triggers confidence assessment."""
        # Mock low confidence classification
        low_confidence_result = {
            "pattern_type": "service_degradation",
            "confidence_score": 0.5,  # Below threshold
            "reasoning": "Uncertain classification",
            "severity_assessment": "MEDIUM",
            "affected_services_analysis": {"primary": "api-service", "secondary": []},
            "recommended_actions": ["Investigation needed"],
        }

        # Mock confidence assessment result
        confidence_result = {
            "overall_confidence": 0.6,
            "confidence_level": "MEDIUM",
            "confidence_reasoning": "Limited evidence available",
            "factor_scores": {"temporal": 0.4, "severity": 0.8},
            "reliability_indicators": ["Multiple service correlation"],
            "uncertainty_sources": ["Limited historical data"],
        }

        mock_gemini_client = AsyncMock()
        # First call returns low confidence classification
        mock_gemini_client.generate_response.side_effect = [
            GeminiResponse(
                success=True,
                content=json.dumps(low_confidence_result),
                parsed_json=low_confidence_result,
                tokens_used=100,
                latency_ms=200.0,
                model_used="gemini-1.5-flash",
            ),
            # Second call returns confidence assessment
            GeminiResponse(
                success=True,
                content=json.dumps(confidence_result),
                parsed_json=confidence_result,
                tokens_used=75,
                latency_ms=150.0,
                model_used="gemini-1.5-flash",
            ),
        ]
        mock_gemini_client_class.return_value = mock_gemini_client

        classifier = GeminiPatternClassifier(api_key="test_key")
        results = await classifier.classify_patterns(
            sample_window, sample_threshold_results
        )

        assert len(results) == 1
        pattern_match = results[0]

        # Should use confidence assessment result
        assert pattern_match.confidence_score == 0.6
        assert "confidence_assessment" in pattern_match.evidence

        # Verify both API calls were made
        assert mock_gemini_client.generate_response.call_count == 2

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    @pytest.mark.asyncio
    async def test_api_failure_handling(
        self,
        mock_gemini_client_class,
        sample_window,
        sample_threshold_results,
    ):
        """Test handling of API failures."""
        mock_gemini_client = AsyncMock()
        mock_gemini_client.generate_response.return_value = GeminiResponse(
            success=False,
            error_message="API rate limit exceeded",
            tokens_used=0,
            latency_ms=100.0,
            model_used="gemini-1.5-flash",
        )
        mock_gemini_client_class.return_value = mock_gemini_client

        classifier = GeminiPatternClassifier(api_key="test_key")
        results = await classifier.classify_patterns(
            sample_window, sample_threshold_results
        )

        assert len(results) == 0

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    @pytest.mark.asyncio
    async def test_invalid_json_response(
        self,
        mock_gemini_client_class,
        sample_window,
        sample_threshold_results,
    ):
        """Test handling of invalid JSON responses."""
        mock_gemini_client = AsyncMock()
        mock_gemini_client.generate_response.return_value = GeminiResponse(
            success=True,
            content="Invalid JSON response",
            parsed_json={},  # Empty parsed JSON
            tokens_used=50,
            latency_ms=100.0,
            model_used="gemini-1.5-flash",
        )
        mock_gemini_client_class.return_value = mock_gemini_client

        classifier = GeminiPatternClassifier(api_key="test_key")
        results = await classifier.classify_patterns(
            sample_window, sample_threshold_results
        )

        assert len(results) == 0

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    @pytest.mark.asyncio
    async def test_unknown_pattern_type(
        self,
        mock_gemini_client_class,
        sample_window,
        sample_threshold_results,
    ):
        """Test handling of unknown pattern types."""
        unknown_pattern_result = {
            "pattern_type": "unknown_pattern_type",
            "confidence_score": 0.9,
            "reasoning": "High confidence but unknown pattern",
            "severity_assessment": "HIGH",
            "affected_services_analysis": {"primary": "api-service", "secondary": []},
        }

        mock_gemini_client = AsyncMock()
        mock_gemini_client.generate_response.return_value = GeminiResponse(
            success=True,
            content=json.dumps(unknown_pattern_result),
            parsed_json=unknown_pattern_result,
            tokens_used=100,
            latency_ms=200.0,
            model_used="gemini-1.5-flash",
        )
        mock_gemini_client_class.return_value = mock_gemini_client

        classifier = GeminiPatternClassifier(api_key="test_key")
        results = await classifier.classify_patterns(
            sample_window, sample_threshold_results
        )

        # Should return empty list for unknown pattern type
        assert len(results) == 0


class TestGeminiPatternClassifierHelpers:
    """Test helper methods."""

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    def test_model_selection_simple_case(self, mock_gemini_client_class):
        """Test model selection for simple incidents."""
        classifier = GeminiPatternClassifier(api_key="test_key")

        window = TimeWindow(start_time=datetime.now(timezone.utc), duration_minutes=5)
        window.logs = [
            LogEntry(
                insert_id="log1",
                timestamp=window.start_time,
                severity="ERROR",
                service_name="api-service",
                error_message="Simple error",
                raw_data={},
            )
        ]

        model = classifier._select_model(window, [])
        assert model == "gemini-1.5-flash"

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    def test_model_selection_complex_case(self, mock_gemini_client_class):
        """Test model selection for complex incidents."""
        classifier = GeminiPatternClassifier(api_key="test_key")

        window = TimeWindow(start_time=datetime.now(timezone.utc), duration_minutes=60)

        # Create many logs from multiple services
        window.logs = []
        for i in range(1500):  # High log count
            for service in ["api", "db", "auth", "cache", "queue"]:  # Many services
                window.logs.append(
                    LogEntry(
                        insert_id=f"log{i}_{service}",
                        timestamp=window.start_time,
                        severity="ERROR",
                        service_name=f"{service}-service",
                        error_message=f"Error {i}",
                        raw_data={},
                    )
                )

        # Many threshold violations
        threshold_results = [{"type": f"threshold_{i}"} for i in range(30)]

        model = classifier._select_model(window, threshold_results)
        assert model == "gemini-1.5-pro"

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    def test_pattern_type_mapping(self, mock_gemini_client_class):
        """Test pattern type string to enum mapping."""
        classifier = GeminiPatternClassifier(api_key="test_key")

        assert (
            classifier._map_pattern_type("cascade_failure")
            == PatternType.CASCADE_FAILURE
        )
        assert (
            classifier._map_pattern_type("service_degradation")
            == PatternType.SERVICE_DEGRADATION
        )
        assert classifier._map_pattern_type("unknown_pattern") is None

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    def test_affected_services_extraction(self, mock_gemini_client_class):
        """Test extraction of affected services from pattern data."""
        classifier = GeminiPatternClassifier(api_key="test_key")

        pattern_data = {
            "affected_services_analysis": {
                "primary": "api-service",
                "secondary": ["db-service", "auth-service"],
            }
        }

        services = classifier._extract_affected_services(pattern_data)
        assert "api-service" in services
        assert "db-service" in services
        assert "auth-service" in services
        assert len(services) == 3

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    def test_performance_stats(self, mock_gemini_client_class):
        """Test performance statistics calculation."""
        classifier = GeminiPatternClassifier(api_key="test_key")

        # Simulate some classifications
        classifier._classification_count = 10
        classifier._successful_classifications = 8

        stats = classifier.get_performance_stats()

        assert stats["total_classifications"] == 10
        assert stats["successful_classifications"] == 8
        assert stats["success_rate_percent"] == 80.0
        assert stats["confidence_threshold"] == 0.7


class TestGeminiPatternClassifierPrompts:
    """Test prompt building functionality."""

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    def test_classification_prompt_building(self, mock_gemini_client_class):
        """Test classification prompt construction."""
        classifier = GeminiPatternClassifier(api_key="test_key")

        window = TimeWindow(start_time=datetime.now(timezone.utc), duration_minutes=15)
        window.logs = [
            LogEntry(
                insert_id="log1",
                timestamp=window.start_time,
                severity="ERROR",
                service_name="api-service",
                error_message="Database timeout",
                raw_data={},
            )
        ]

        threshold_results = [
            {
                "type": "error_frequency",
                "description": "High error frequency",
                "triggered": True,
            }
        ]

        historical_context = {"similar_count": 3, "trend_analysis": "Increasing"}
        code_context = {"recent_commits": ["abc123"], "changes_summary": "API updates"}

        prompt = classifier._build_classification_prompt(
            window, threshold_results, historical_context, code_context
        )

        assert "TIME WINDOW:" in prompt
        assert "SERVICE ERRORS:" in prompt
        assert "api-service" in prompt
        assert "THRESHOLD VIOLATIONS:" in prompt
        assert "HISTORICAL CONTEXT:" in prompt
        assert "SOURCE CODE CONTEXT:" in prompt

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    def test_confidence_prompt_building(self, mock_gemini_client_class):
        """Test confidence assessment prompt construction."""
        classifier = GeminiPatternClassifier(api_key="test_key")

        pattern_data = {
            "pattern_type": "cascade_failure",
            "confidence_score": 0.6,
            "reasoning": "Multiple service failures detected",
        }

        window = TimeWindow(start_time=datetime.now(timezone.utc), duration_minutes=10)
        window.logs = [Mock()]

        prompt = classifier._build_confidence_prompt(pattern_data, window)

        assert "cascade_failure" in prompt
        assert "0.6" in prompt
        assert "Multiple service failures detected" in prompt
        assert "TIME WINDOW CHARACTERISTICS:" in prompt

    @patch("gemini_sre_agent.ml.gemini_pattern_classifier.GeminiAPIClient")
    def test_schema_building(self, mock_gemini_client_class):
        """Test JSON schema construction for structured output."""
        classifier = GeminiPatternClassifier(api_key="test_key")

        # Test classification schema
        classification_schema = classifier._build_classification_schema()
        assert classification_schema["type"] == "object"
        assert "pattern_type" in classification_schema["properties"]
        assert "confidence_score" in classification_schema["properties"]
        assert (
            "cascade_failure"
            in classification_schema["properties"]["pattern_type"]["enum"]
        )

        # Test confidence schema
        confidence_schema = classifier._build_confidence_schema()
        assert confidence_schema["type"] == "object"
        assert "overall_confidence" in confidence_schema["properties"]
        assert "confidence_level" in confidence_schema["properties"]
