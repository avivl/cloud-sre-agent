# gemini_sre_agent/ml/prompt_utils.py

"""
Utility functions for prompt processing and manipulation.

This module provides helper functions for working with prompts,
templates, and prompt-related operations.
"""

import json
import re
from typing import Any, Dict, List


def format_prompt(template: str, **kwargs: Any) -> str:
    """
    Format a prompt template with provided variables.

    Args:
        template: Prompt template string
        **kwargs: Variables to substitute in the template

    Returns:
        Formatted prompt string
    """
    return template.format(**kwargs)


def extract_variables(template: str) -> List[str]:
    """
    Extract variable names from a prompt template.

    Args:
        template: Prompt template string

    Returns:
        List of variable names found in the template
    """
    pattern = r"\{(\w+)\}"
    return re.findall(pattern, template)


def validate_prompt(prompt: str) -> bool:
    """
    Validate a prompt string.

    Args:
        prompt: Prompt string to validate

    Returns:
        True if prompt is valid, False otherwise
    """
    if not prompt or not prompt.strip():
        return False

    # Check for reasonable length
    if len(prompt) > 100000:  # 100k characters
        return False

    return True


def sanitize_prompt(prompt: str) -> str:
    """
    Sanitize a prompt string by removing potentially harmful content.

    Args:
        prompt: Prompt string to sanitize

    Returns:
        Sanitized prompt string
    """
    # Remove excessive whitespace
    prompt = re.sub(r"\s+", " ", prompt.strip())

    # Remove potential injection patterns (basic)
    prompt = re.sub(r"<script.*?</script>", "", prompt, flags=re.IGNORECASE | re.DOTALL)

    return prompt


def truncate_prompt(prompt: str, max_length: int = 50000) -> str:
    """
    Truncate a prompt to a maximum length.

    Args:
        prompt: Prompt string to truncate
        max_length: Maximum length in characters

    Returns:
        Truncated prompt string
    """
    if len(prompt) <= max_length:
        return prompt

    return prompt[:max_length] + "..."


def count_tokens_estimate(text: str) -> int:
    """
    Estimate token count for a text string.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count
    """
    # Rough estimation: 1 token ≈ 4 characters
    return len(text) // 4


def merge_prompts(prompts: List[str], separator: str = "\n\n") -> str:
    """
    Merge multiple prompts into a single prompt.

    Args:
        prompts: List of prompt strings
        separator: Separator to use between prompts

    Returns:
        Merged prompt string
    """
    return separator.join(filter(None, prompts))


def build_context_kwargs(context_data: Any) -> Dict[str, Any]:
    """
    Build keyword arguments for context-based prompts.

    Args:
        context_data: Context data (PatternContext object or dict)

    Returns:
        Formatted keyword arguments with normalized dict keys for JSON compatibility
    """
    # Handle both PatternContext objects and dictionaries
    if hasattr(context_data, '__dict__'):
        data = context_data.__dict__
    else:
        data = context_data if isinstance(context_data, dict) else {}
    
    def normalize_dict_keys(obj: Any) -> Any:
        """Recursively normalize dict keys to strings for JSON compatibility."""
        if isinstance(obj, dict):
            return {str(k): normalize_dict_keys(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [normalize_dict_keys(item) for item in obj]
        elif hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        else:
            return obj
    
    # Convert complex objects to JSON strings for template compatibility
    def safe_json_serialize(obj: Any) -> str:
        """Safely serialize objects to JSON strings."""
        try:
            normalized = normalize_dict_keys(obj)
            return json.dumps(normalized, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(obj)
    
    # Handle list fields by joining with commas
    def safe_list_join(obj: Any, default: str = "Unknown") -> str:
        """Safely join list items or return default."""
        if isinstance(obj, list) and obj:
            return ", ".join(str(item) for item in obj)
        return default
    
    return {
        "primary_service": data.get("primary_service", "Unknown"),
        "affected_services": safe_list_join(data.get("affected_services"), "No services identified"),
        "time_window_start": data.get("time_window_start", "Unknown"),
        "time_window_end": data.get("time_window_end", "Unknown"),
        "error_patterns": safe_json_serialize(data.get("error_patterns", {})),
        "timing_analysis": safe_json_serialize(data.get("timing_analysis", {})),
        "service_topology": safe_json_serialize(data.get("service_topology", {})),
        "code_changes_context": data.get("code_changes_context", "No recent changes"),
        "static_analysis_findings": safe_json_serialize(data.get("static_analysis_findings", {})),
        "code_quality_metrics": safe_json_serialize(data.get("code_quality_metrics", {})),
        "dependency_vulnerabilities": safe_list_join(data.get("dependency_vulnerabilities"), "No vulnerabilities identified"),
        "error_related_files": safe_list_join(data.get("error_related_files"), "No related files identified"),
        "recent_commits": safe_list_join(data.get("recent_commits"), "No recent commits"),
    }


def build_evidence_kwargs(evidence_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build keyword arguments for evidence-based prompts.

    Args:
        evidence_data: Evidence data dictionary

    Returns:
        Formatted keyword arguments with normalized dict keys for JSON compatibility
    """
    def normalize_dict_keys(obj: Any) -> Any:
        """Recursively normalize dict keys to strings for JSON compatibility."""
        if isinstance(obj, dict):
            return {str(k): normalize_dict_keys(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [normalize_dict_keys(item) for item in obj]
        else:
            return obj
    
    # Convert complex objects to JSON strings for template compatibility
    def safe_json_serialize(obj: Any) -> str:
        """Safely serialize objects to JSON strings."""
        try:
            normalized = normalize_dict_keys(obj)
            return json.dumps(normalized, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(obj)
    
    return {
        "log_completeness": evidence_data.get("log_completeness", 0.0),
        "timestamp_consistency": evidence_data.get("timestamp_consistency", "unknown"),
        "missing_data_rate": evidence_data.get("missing_data_rate", 0.0),
        "error_concentration": evidence_data.get("error_concentration", 0.0),
        "timing_correlation": evidence_data.get("timing_correlation", "unknown"),
        "pattern_clarity": evidence_data.get("pattern_clarity", "unknown"),
        "topology_alignment": evidence_data.get("topology_alignment", "unknown"),
        "cross_service_correlation": evidence_data.get("cross_service_correlation", "unknown"),
        "cascade_indicators": evidence_data.get("cascade_indicators", "unknown"),
        "error_consistency": evidence_data.get("error_consistency", "unknown"),
        "message_similarity": evidence_data.get("message_similarity", "unknown"),
        "severity_alignment": evidence_data.get("severity_alignment", "unknown"),
        "baseline_deviation": evidence_data.get("baseline_deviation", "unknown"),
        "trend_alignment": evidence_data.get("trend_alignment", "unknown"),
        "similar_incidents_count": evidence_data.get("similar_incidents_count", 0),
        "deployment_correlation": evidence_data.get("deployment_correlation", "unknown"),
        "dependency_status": evidence_data.get("dependency_status", "unknown"),
        "resource_pressure": evidence_data.get("resource_pressure", "unknown"),
    }


class PatternContext:
    """Context for pattern-based prompt generation."""

    def __init__(self, pattern_type: str, data: Dict[str, Any]):
        self.pattern_type = pattern_type
        self.data = data
