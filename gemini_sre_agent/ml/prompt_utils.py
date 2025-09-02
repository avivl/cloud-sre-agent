"""
Utility functions for prompt generation and formatting.

This module provides helper functions for building context arguments
and evidence metrics for Gemini prompt templates.
"""

import json
from typing import Any, Dict

from .schemas import PatternContext


def build_context_kwargs(context: PatternContext) -> Dict[str, str]:
    """Build context variables for template formatting."""
    return {
        "primary_service": context.primary_service or "Unknown",
        "affected_services": (
            ", ".join(context.affected_services)
            if context.affected_services
            else "No services identified"
        ),
        "time_window_start": (
            context.time_window_start.isoformat()
            if context.time_window_start
            else "Unknown"
        ),
        "time_window_end": (
            context.time_window_end.isoformat()
            if context.time_window_end
            else "Unknown"
        ),
        "error_patterns": (
            json.dumps(context.error_patterns)
            if context.error_patterns
            else "No error patterns available"
        ),
        "timing_analysis": (
            json.dumps(context.timing_analysis)
            if context.timing_analysis
            else "No timing analysis available"
        ),
        "service_topology": (
            json.dumps(context.service_topology)
            if context.service_topology
            else "No topology information available"
        ),
        "code_changes_context": context.code_changes_context
        or "No code context available",
        "static_analysis_findings": (
            json.dumps(context.static_analysis_findings)
            if context.static_analysis_findings
            else "No static analysis data"
        ),
        "code_quality_metrics": (
            json.dumps(context.code_quality_metrics)
            if context.code_quality_metrics
            else "No quality metrics available"
        ),
        "dependency_vulnerabilities": (
            json.dumps(context.dependency_vulnerabilities)
            if context.dependency_vulnerabilities
            else "No known vulnerabilities"
        ),
        "error_related_files": (
            ", ".join(context.error_related_files)
            if context.error_related_files
            else "No related files identified"
        ),
        "recent_commits": (
            json.dumps(context.recent_commits)
            if context.recent_commits
            else "No recent commits available"
        ),
    }


def build_evidence_kwargs(evidence_metrics: Dict[str, float]) -> Dict[str, Any]:
    """Build evidence metrics for confidence assessment."""
    return {
        "log_completeness": evidence_metrics.get("log_completeness", 85),
        "timestamp_consistency": evidence_metrics.get("timestamp_consistency", "high"),
        "missing_data_rate": evidence_metrics.get("missing_data_rate", 5),
        "error_concentration": evidence_metrics.get("error_concentration", 0.7),
        "timing_correlation": evidence_metrics.get("timing_correlation", 0.8),
        "pattern_clarity": evidence_metrics.get("pattern_clarity", "clear"),
        "topology_alignment": evidence_metrics.get("topology_alignment", "strong"),
        "cross_service_correlation": evidence_metrics.get(
            "cross_service_correlation", 0.6
        ),
        "cascade_indicators": evidence_metrics.get("cascade_indicators", "yes"),
        "error_consistency": evidence_metrics.get("error_consistency", 0.75),
        "message_similarity": evidence_metrics.get("message_similarity", 0.8),
        "severity_alignment": evidence_metrics.get("severity_alignment", "good"),
        "baseline_deviation": evidence_metrics.get("baseline_deviation", "significant"),
        "trend_alignment": evidence_metrics.get("trend_alignment", "consistent"),
        "similar_incidents_count": evidence_metrics.get("similar_incidents_count", 3),
        "deployment_correlation": evidence_metrics.get("deployment_correlation", "low"),
        "dependency_status": evidence_metrics.get("dependency_status", "healthy"),
        "resource_pressure": evidence_metrics.get("resource_pressure", "medium"),
    }
