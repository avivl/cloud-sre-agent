"""
Tests for prompt utility functions.

This module tests utility functions for building context arguments
and evidence metrics for Gemini prompt templates.
"""

import json
from datetime import datetime

import pytest

from gemini_sre_agent.ml.prompt_utils import build_context_kwargs, build_evidence_kwargs
from gemini_sre_agent.ml.schemas import PatternContext


class TestBuildContextKwargs:
    """Test cases for build_context_kwargs function."""

    def test_complete_context(self) -> None:
        """Test building kwargs with complete context data."""
        context = PatternContext(
            primary_service="user-service",
            affected_services=["auth-service", "payment-service"],
            time_window_start=datetime(2024, 1, 15, 10, 0),
            time_window_end=datetime(2024, 1, 15, 11, 0),
            error_patterns={"500_errors": 25, "timeout_errors": 8},
            timing_analysis={"avg_response_time": 1500, "p95_response_time": 3000},
            service_topology={"dependencies": ["database", "redis"]},
            code_changes_context="Deployed version 1.2.3 with auth fixes",
            static_analysis_findings={"warnings": 2, "errors": 0},
            code_quality_metrics={"coverage": 0.92, "complexity": 6.5},
            dependency_vulnerabilities=["CVE-2024-5678"],
            error_related_files=["auth.py", "user.py"],
            recent_commits=["abc123: Fix auth bug", "def456: Update user model"],
        )

        kwargs = build_context_kwargs(context)

        # Verify basic string fields
        assert kwargs["primary_service"] == "user-service"
        assert kwargs["affected_services"] == "auth-service, payment-service"
        assert (
            kwargs["code_changes_context"] == "Deployed version 1.2.3 with auth fixes"
        )
        assert kwargs["error_related_files"] == "auth.py, user.py"

        # Verify datetime formatting
        assert kwargs["time_window_start"] == "2024-01-15T10:00:00"
        assert kwargs["time_window_end"] == "2024-01-15T11:00:00"

        # Verify JSON serialization
        error_patterns = json.loads(kwargs["error_patterns"])
        assert error_patterns == {"500_errors": 25, "timeout_errors": 8}

        timing_analysis = json.loads(kwargs["timing_analysis"])
        assert timing_analysis == {"avg_response_time": 1500, "p95_response_time": 3000}

        static_findings = json.loads(kwargs["static_analysis_findings"])
        assert static_findings == {"warnings": 2, "errors": 0}

    def test_empty_context(self) -> None:
        """Test building kwargs with empty context."""
        context = PatternContext()
        kwargs = build_context_kwargs(context)

        # Verify default values for None fields
        assert kwargs["primary_service"] == "Unknown"
        assert kwargs["affected_services"] == "No services identified"
        assert kwargs["time_window_start"] == "Unknown"
        assert kwargs["time_window_end"] == "Unknown"
        assert kwargs["error_patterns"] == "No error patterns available"
        assert kwargs["timing_analysis"] == "No timing analysis available"
        assert kwargs["service_topology"] == "No topology information available"
        assert kwargs["code_changes_context"] == "No code context available"
        assert kwargs["static_analysis_findings"] == "No static analysis data"
        assert kwargs["code_quality_metrics"] == "No quality metrics available"
        assert kwargs["dependency_vulnerabilities"] == "No known vulnerabilities"
        assert kwargs["error_related_files"] == "No related files identified"
        assert kwargs["recent_commits"] == "No recent commits available"

    def test_partial_context(self) -> None:
        """Test building kwargs with partially filled context."""
        context = PatternContext(
            primary_service="api-gateway",
            error_patterns={"critical_errors": 5},
            # Other fields intentionally left as None/empty
        )

        kwargs = build_context_kwargs(context)

        # Verify filled fields
        assert kwargs["primary_service"] == "api-gateway"
        error_patterns = json.loads(kwargs["error_patterns"])
        assert error_patterns == {"critical_errors": 5}

        # Verify default values for empty fields
        assert kwargs["affected_services"] == "No services identified"
        assert kwargs["timing_analysis"] == "No timing analysis available"

    def test_empty_lists_and_dicts(self) -> None:
        """Test handling of empty lists and dictionaries."""
        context = PatternContext(
            primary_service="test-service",
            affected_services=[],  # Empty list
            error_patterns={},  # Empty dict
            error_related_files=[],  # Empty list
        )

        kwargs = build_context_kwargs(context)

        assert kwargs["primary_service"] == "test-service"
        assert kwargs["affected_services"] == "No services identified"
        assert kwargs["error_patterns"] == "No error patterns available"
        assert kwargs["error_related_files"] == "No related files identified"

    def test_complex_json_serialization(self) -> None:
        """Test JSON serialization of complex nested structures."""
        complex_topology = {
            "services": {
                "frontend": {"dependencies": ["api", "auth"]},
                "api": {"dependencies": ["database", "cache"]},
            },
            "external_dependencies": ["payment-gateway", "email-service"],
        }

        context = PatternContext(
            primary_service="frontend",
            service_topology=complex_topology,
        )

        kwargs = build_context_kwargs(context)

        # Verify complex structure is properly serialized
        topology = json.loads(kwargs["service_topology"])
        assert topology == complex_topology
        assert "frontend" in topology["services"]
        assert "payment-gateway" in topology["external_dependencies"]

    def test_unicode_handling(self) -> None:
        """Test handling of unicode characters in context."""
        context = PatternContext(
            primary_service="测试服务",  # Chinese characters
            code_changes_context="Updated with émojis and spéciàl chars",
            error_related_files=["测试.py", "spéciàl_file.js"],
        )

        kwargs = build_context_kwargs(context)

        assert kwargs["primary_service"] == "测试服务"
        assert "émojis" in kwargs["code_changes_context"]
        assert "测试.py, spéciàl_file.js" == kwargs["error_related_files"]


class TestBuildEvidenceKwargs:
    """Test cases for build_evidence_kwargs function."""

    def test_complete_evidence_metrics(self) -> None:
        """Test building kwargs with complete evidence metrics."""
        evidence_metrics = {
            "log_completeness": 95.5,
            "timestamp_consistency": "excellent",
            "missing_data_rate": 2.1,
            "error_concentration": 0.89,
            "timing_correlation": 0.94,
            "pattern_clarity": "very_clear",
            "topology_alignment": "perfect",
            "cross_service_correlation": 0.82,
            "cascade_indicators": "strong",
            "error_consistency": 0.91,
            "message_similarity": 0.87,
            "severity_alignment": "excellent",
            "baseline_deviation": "significant",
            "trend_alignment": "consistent",
            "similar_incidents_count": 7,
            "deployment_correlation": "high",
            "dependency_status": "degraded",
            "resource_pressure": "critical",
        }

        kwargs = build_evidence_kwargs(evidence_metrics)

        # Verify all metrics are preserved
        assert kwargs["log_completeness"] == 95.5
        assert kwargs["timestamp_consistency"] == "excellent"
        assert kwargs["missing_data_rate"] == 2.1
        assert kwargs["error_concentration"] == 0.89
        assert kwargs["timing_correlation"] == 0.94
        assert kwargs["pattern_clarity"] == "very_clear"
        assert kwargs["similar_incidents_count"] == 7

    def test_empty_evidence_metrics(self) -> None:
        """Test building kwargs with empty evidence metrics."""
        evidence_metrics = {}
        kwargs = build_evidence_kwargs(evidence_metrics)

        # Verify default values are used
        assert kwargs["log_completeness"] == 85
        assert kwargs["timestamp_consistency"] == "high"
        assert kwargs["missing_data_rate"] == 5
        assert kwargs["error_concentration"] == 0.7
        assert kwargs["timing_correlation"] == 0.8
        assert kwargs["pattern_clarity"] == "clear"
        assert kwargs["topology_alignment"] == "strong"
        assert kwargs["cross_service_correlation"] == 0.6
        assert kwargs["cascade_indicators"] == "yes"
        assert kwargs["error_consistency"] == 0.75
        assert kwargs["message_similarity"] == 0.8
        assert kwargs["severity_alignment"] == "good"
        assert kwargs["baseline_deviation"] == "significant"
        assert kwargs["trend_alignment"] == "consistent"
        assert kwargs["similar_incidents_count"] == 3
        assert kwargs["deployment_correlation"] == "low"
        assert kwargs["dependency_status"] == "healthy"
        assert kwargs["resource_pressure"] == "medium"

    def test_partial_evidence_metrics(self) -> None:
        """Test building kwargs with partial evidence metrics."""
        evidence_metrics = {
            "log_completeness": 78.5,
            "error_concentration": 0.95,
            "similar_incidents_count": 12,
            # Other metrics intentionally omitted
        }

        kwargs = build_evidence_kwargs(evidence_metrics)

        # Verify provided metrics are used
        assert kwargs["log_completeness"] == 78.5
        assert kwargs["error_concentration"] == 0.95
        assert kwargs["similar_incidents_count"] == 12

        # Verify defaults for omitted metrics
        assert kwargs["timestamp_consistency"] == "high"
        assert kwargs["missing_data_rate"] == 5
        assert kwargs["timing_correlation"] == 0.8

    def test_edge_case_values(self) -> None:
        """Test handling of edge case values."""
        evidence_metrics = {
            "log_completeness": 0.0,  # Minimum value
            "missing_data_rate": 100.0,  # Maximum percentage
            "error_concentration": 1.0,  # Maximum correlation
            "timing_correlation": 0.0,  # Minimum correlation
            "similar_incidents_count": 0,  # No similar incidents
        }

        kwargs = build_evidence_kwargs(evidence_metrics)

        assert kwargs["log_completeness"] == 0.0
        assert kwargs["missing_data_rate"] == 100.0
        assert kwargs["error_concentration"] == 1.0
        assert kwargs["timing_correlation"] == 0.0
        assert kwargs["similar_incidents_count"] == 0

    def test_numeric_vs_string_values(self) -> None:
        """Test that numeric and string values are handled appropriately."""
        evidence_metrics = {
            "log_completeness": 88.7,  # Numeric
            "timestamp_consistency": "moderate",  # String
            "error_concentration": 0.76,  # Numeric float
            "similar_incidents_count": 5,  # Numeric int
        }

        kwargs = build_evidence_kwargs(evidence_metrics)

        # Verify types are preserved
        assert isinstance(kwargs["log_completeness"], float)
        assert isinstance(kwargs["timestamp_consistency"], str)
        assert isinstance(kwargs["error_concentration"], float)
        assert isinstance(kwargs["similar_incidents_count"], int)

        assert kwargs["log_completeness"] == 88.7
        assert kwargs["timestamp_consistency"] == "moderate"

    def test_all_metric_keys_present(self) -> None:
        """Test that all expected metric keys are present in output."""
        evidence_metrics = {"log_completeness": 90}  # Only one metric provided
        kwargs = build_evidence_kwargs(evidence_metrics)

        expected_keys = {
            "log_completeness",
            "timestamp_consistency",
            "missing_data_rate",
            "error_concentration",
            "timing_correlation",
            "pattern_clarity",
            "topology_alignment",
            "cross_service_correlation",
            "cascade_indicators",
            "error_consistency",
            "message_similarity",
            "severity_alignment",
            "baseline_deviation",
            "trend_alignment",
            "similar_incidents_count",
            "deployment_correlation",
            "dependency_status",
            "resource_pressure",
        }

        # Verify all expected keys are present
        assert set(kwargs.keys()) == expected_keys

    def test_kwargs_return_types(self) -> None:
        """Test that kwargs returns proper types for template formatting."""
        evidence_metrics = {
            "log_completeness": 92.3,
            "timestamp_consistency": "high",
        }

        kwargs = build_evidence_kwargs(evidence_metrics)

        # Should return a dictionary suitable for string formatting
        assert isinstance(kwargs, dict)

        # All values should be serializable for template formatting
        for key, value in kwargs.items():
            assert isinstance(value, (int, float, str))

            # Test that values can be used in string formatting
            try:
                formatted = f"Value: {value}"
                assert isinstance(formatted, str)
            except Exception as e:
                pytest.fail(f"Failed to format {key}={value}: {e}")

    def test_negative_values_handling(self) -> None:
        """Test handling of negative values in metrics."""
        evidence_metrics = {
            "log_completeness": -5.0,  # Invalid but should be preserved
            "error_concentration": -0.1,  # Invalid correlation
            "similar_incidents_count": -1,  # Invalid count
        }

        kwargs = build_evidence_kwargs(evidence_metrics)

        # Should preserve even invalid values (validation is not this function's job)
        assert kwargs["log_completeness"] == -5.0
        assert kwargs["error_concentration"] == -0.1
        assert kwargs["similar_incidents_count"] == -1
