"""
Comprehensive unit tests for GeminiPromptEngine.

Tests prompt generation, template management, few-shot learning,
and context formatting for pattern classification and confidence assessment.
"""

import json
import tempfile

import pytest

from gemini_sre_agent.ml.gemini_prompt_engine import (
    GeminiPromptEngine,
    PatternContext,
    PromptTemplate,
)


@pytest.fixture
def temp_db_path() -> str:
    """Create a temporary database file path."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        return f.name


@pytest.fixture
def sample_context() -> PatternContext:
    """Create a sample PatternContext for testing."""
    return PatternContext(
        time_window="2024-01-15 10:00-11:00 UTC",
        error_frequency=45,
        error_burst_pattern="High concentration in 5-minute windows",
        temporal_distribution="Rapid onset with sustained elevation",
        affected_services=["api-service", "db-service", "auth-service"],
        primary_service="api-service",
        service_interaction_pattern="Cascading failure from primary to secondary",
        cross_service_timing="Sequential failures within 30 seconds",
        error_types=["ConnectionError", "TimeoutException", "DatabaseException"],
        severity_distribution={"ERROR": 35, "CRITICAL": 10},
        error_messages_sample=[
            "Connection timeout to database",
            "Authentication service unavailable",
            "Request processing failed",
        ],
        error_similarity_score=0.85,
        baseline_comparison="300% above normal baseline",
        trend_analysis="Sharp increase from 10:05, peak at 10:12",
        similar_incidents=["INC-2024-001", "INC-2023-456"],
        recent_changes=["API gateway deployment v2.1.0", "Database schema update"],
        code_changes_context="Recent deployment of auth service v2.1.0",
        static_analysis_findings={"complexity_warnings": 3, "security_issues": 0},
        code_quality_metrics={"coverage": 0.85, "maintainability_index": 7.2},
        dependency_vulnerabilities=["CVE-2024-1234"],
        error_related_files=["auth.py", "middleware.py"],
        recent_commits=["abc123: Fix auth timeout", "def456: Update middleware"],
    )


@pytest.fixture
def sample_evidence_metrics() -> dict:
    """Create sample evidence metrics for testing."""
    return {
        "log_completeness": 92.5,
        "timestamp_consistency": "high",
        "missing_data_rate": 3.2,
        "error_concentration": 0.85,
        "timing_correlation": 0.91,
        "pattern_clarity": "very_clear",
        "topology_alignment": "strong",
        "cross_service_correlation": 0.78,
        "cascade_indicators": "present",
        "error_consistency": 0.88,
        "message_similarity": 0.92,
        "severity_alignment": "high",
        "baseline_deviation": "significant",
        "trend_alignment": "strong",
        "similar_incidents_count": 3,
        "deployment_correlation": "strong",
        "dependency_status": "degraded",
        "resource_pressure": "moderate",
    }


class TestGeminiPromptEngine:
    """Test cases for GeminiPromptEngine."""

    def test_initialization(self, temp_db_path: str) -> None:
        """Test engine initialization with template setup."""
        engine = GeminiPromptEngine(temp_db_path)

        assert len(engine.templates) == 2
        assert "classification" in engine.templates
        assert "confidence" in engine.templates

        # Check classification template
        classification_template = engine.templates["classification"]
        assert isinstance(classification_template, PromptTemplate)
        assert classification_template.name == "pattern_classification"
        assert "SRE pattern recognition" in classification_template.system_prompt
        assert (
            "INCIDENT ANALYSIS REQUEST" in classification_template.user_prompt_template
        )

        # Check confidence template
        confidence_template = engine.templates["confidence"]
        assert isinstance(confidence_template, PromptTemplate)
        assert confidence_template.name == "confidence_assessment"
        assert "confidence assessor" in confidence_template.system_prompt
        assert (
            "CONFIDENCE ASSESSMENT REQUEST" in confidence_template.user_prompt_template
        )

    @pytest.mark.asyncio
    async def test_generate_classification_prompt(
        self, temp_db_path: str, sample_context: PatternContext
    ) -> None:
        """Test classification prompt generation."""
        engine = GeminiPromptEngine(temp_db_path)

        prompt = await engine.generate_classification_prompt(sample_context)

        # Verify prompt structure
        assert isinstance(prompt, str)
        assert len(prompt) > 0

        # Verify system prompt is included
        assert "SRE pattern recognition" in prompt

        # Verify context data is included
        assert "api-service" in prompt
        assert "db-service" in prompt
        assert "45" in prompt  # error_frequency
        assert "ConnectionError" in prompt
        assert "CVE-2024-1234" in prompt
        assert "auth service v2.1.0" in prompt

    @pytest.mark.asyncio
    async def test_generate_confidence_prompt(
        self, temp_db_path: str, sample_evidence_metrics: dict
    ) -> None:
        """Test confidence assessment prompt generation."""
        engine = GeminiPromptEngine(temp_db_path)

        classification_result = {
            "pattern_type": "cascading_failure",
            "confidence_score": 0.87,
            "reasoning": "Multiple service correlation with temporal clustering",
            "severity_assessment": "HIGH",
        }

        prompt = await engine.generate_confidence_prompt(
            classification_result, sample_evidence_metrics
        )

        # Verify prompt structure
        assert isinstance(prompt, str)
        assert len(prompt) > 0

        # Verify system prompt is included
        assert "confidence assessor" in prompt

        # Verify classification result is included
        assert "cascading_failure" in prompt
        assert "0.87" in prompt
        assert "Multiple service correlation" in prompt

        # Verify evidence metrics are included
        assert "92.5%" in prompt  # log_completeness
        assert "high" in prompt  # timestamp_consistency
        assert "0.85" in prompt  # error_concentration

    def test_get_template_config(self, temp_db_path: str) -> None:
        """Test template configuration retrieval."""
        engine = GeminiPromptEngine(temp_db_path)

        config = engine.get_template_config("classification")

        assert "temperature" in config
        assert "max_tokens" in config
        assert "output_format" in config
        assert config["temperature"] == 0.3
        assert config["max_tokens"] == 2048

    def test_get_template_config_invalid_template(self, temp_db_path: str) -> None:
        """Test error handling for invalid template name."""
        engine = GeminiPromptEngine(temp_db_path)

        with pytest.raises(ValueError, match="Template 'invalid' not found"):
            engine.get_template_config("invalid")

    @pytest.mark.asyncio
    async def test_prompt_with_few_shot_examples(
        self, temp_db_path: str, sample_context: PatternContext
    ) -> None:
        """Test prompt generation includes few-shot examples when available."""
        engine = GeminiPromptEngine(temp_db_path)

        # Create few-shot examples file
        few_shot_examples = {
            "classification": [
                {
                    "context": "Database timeout caused service cascade",
                    "classification": "cascade_failure",
                    "reasoning": "Sequential service failures with timing correlation",
                    "affected_services": ["api-service", "db-service"],
                }
            ]
        }

        # Write few-shot examples to file
        with open(temp_db_path, "w", encoding="utf-8") as f:
            json.dump(few_shot_examples, f)

        # Reload engine to pick up examples
        engine = GeminiPromptEngine(temp_db_path)
        prompt = await engine.generate_classification_prompt(sample_context)

        # Verify few-shot example is included
        assert "EXAMPLES OF SIMILAR CLASSIFICATIONS" in prompt
        assert "Database timeout caused service cascade" in prompt

    def test_few_shot_example_loading_error(self, temp_db_path: str) -> None:
        """Test handling of few-shot loading errors."""
        # Create invalid JSON file
        with open(temp_db_path, "w", encoding="utf-8") as f:
            f.write("invalid json content")

        # Should not crash, should return empty examples
        engine = GeminiPromptEngine(temp_db_path)
        assert engine.few_shot_examples == {}

    def test_few_shot_example_missing_file(self, temp_db_path: str) -> None:
        """Test handling when few-shot file doesn't exist."""
        # Use non-existent path
        engine = GeminiPromptEngine("/non/existent/path.json")
        assert engine.few_shot_examples == {}

    def test_few_shot_relevance_scoring(self, temp_db_path: str) -> None:
        """Test few-shot example relevance scoring."""
        engine = GeminiPromptEngine(temp_db_path)

        # Create examples with different service overlaps

        # Test with services that match first and third examples
        services = ["api-service", "queue-service"]
        relevant = engine._get_relevant_few_shot_examples("classification", services)

        # Should return all examples since we have fewer than 3
        assert len(relevant) <= 3

    @pytest.mark.asyncio
    async def test_save_example(self, temp_db_path: str) -> None:
        """Test saving new few-shot examples."""
        engine = GeminiPromptEngine(temp_db_path)

        context = {
            "time_window": "test_window",
            "affected_services": ["test-service"],
            "timestamp": "2024-01-15T10:00:00Z",
        }

        result = {
            "pattern_type": "test_pattern",
            "confidence": 0.9,
            "reasoning": "Test reasoning",
        }

        await engine.save_example("classification", context, result)

        # Verify example was saved
        assert "classification" in engine.few_shot_examples
        assert len(engine.few_shot_examples["classification"]) == 1

        saved_example = engine.few_shot_examples["classification"][0]
        assert saved_example["context"] == context
        assert saved_example["result"] == result

    @pytest.mark.asyncio
    async def test_save_example_limit(self, temp_db_path: str) -> None:
        """Test that saved examples are limited to 100 per template."""
        engine = GeminiPromptEngine(temp_db_path)

        # Add 105 examples
        for i in range(105):
            await engine.save_example(
                "classification",
                {"test": f"context_{i}"},
                {"pattern_type": f"pattern_{i}"},
            )

        # Should only keep the most recent 100
        assert len(engine.few_shot_examples["classification"]) == 100

        # The first 5 should have been removed
        contexts = [
            ex["context"]["test"] for ex in engine.few_shot_examples["classification"]
        ]
        assert "context_0" not in contexts
        assert "context_4" not in contexts
        assert "context_5" in contexts
        assert "context_104" in contexts

    @pytest.mark.asyncio
    async def test_save_example_error_handling(self, temp_db_path: str) -> None:
        """Test error handling during example saving."""
        engine = GeminiPromptEngine("/invalid/path/that/cannot/be/written.json")

        # Should not crash when file cannot be written
        await engine.save_example(
            "classification", {"test": "context"}, {"pattern_type": "test"}
        )

        # Example should still be in memory even if save failed
        assert "classification" in engine.few_shot_examples

    @pytest.mark.asyncio
    async def test_classification_prompt_formatting(
        self, temp_db_path: str, sample_context: PatternContext
    ) -> None:
        """Test detailed formatting of classification prompt."""
        engine = GeminiPromptEngine(temp_db_path)

        prompt = await engine.generate_classification_prompt(sample_context)

        # Check specific formatting
        assert "Time Window:" in prompt
        assert "2024-01-15 10:00-11:00 UTC" in prompt
        assert "Error Count: 45" in prompt
        assert "SERVICE IMPACT:" in prompt
        assert "api-service, db-service, auth-service" in prompt
        assert "Primary Service: api-service" in prompt
        assert "ERROR CHARACTERISTICS:" in prompt
        assert "ConnectionError, TimeoutException, DatabaseException" in prompt
        assert "HISTORICAL CONTEXT:" in prompt
        assert "300% above normal baseline" in prompt
        assert "SOURCE CODE CONTEXT" in prompt
        assert "Recent deployment of auth service v2.1.0" in prompt

    @pytest.mark.asyncio
    async def test_confidence_prompt_formatting(
        self, temp_db_path: str, sample_evidence_metrics: dict
    ) -> None:
        """Test detailed formatting of confidence prompt."""
        engine = GeminiPromptEngine(temp_db_path)

        classification_result = {
            "pattern_type": "cascade_failure",
            "confidence_score": 0.75,
            "reasoning": "Strong temporal correlation",
        }

        prompt = await engine.generate_confidence_prompt(
            classification_result, sample_evidence_metrics
        )

        # Check JSON formatting
        assert '"pattern_type": "cascade_failure"' in prompt
        assert '"confidence_score": 0.75' in prompt
        assert '"reasoning": "Strong temporal correlation"' in prompt

        # Check evidence metrics formatting
        assert "Log completeness: 92.5%" in prompt
        assert "Timestamp consistency: high" in prompt
        assert "Missing data points: 3.2%" in prompt
        assert "Error concentration score: 0.85" in prompt
        assert "Timing correlation strength: 0.91" in prompt
