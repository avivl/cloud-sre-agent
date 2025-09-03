# gemini_sre_agent/ml/prompt_utils.py

"""
Utility functions for prompt processing and manipulation.

This module provides helper functions for working with prompts,
templates, and prompt-related operations.
"""

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


def build_context_kwargs(context_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build keyword arguments for context-based prompts.

    Args:
        context_data: Context data dictionary

    Returns:
        Formatted keyword arguments
    """
    return {
        "context": context_data.get("context", ""),
        "issue_type": context_data.get("issue_type", "unknown"),
        "severity": context_data.get("severity", "medium"),
    }


def build_evidence_kwargs(evidence_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build keyword arguments for evidence-based prompts.

    Args:
        evidence_data: Evidence data dictionary

    Returns:
        Formatted keyword arguments
    """
    return {
        "evidence": evidence_data.get("evidence", ""),
        "confidence": evidence_data.get("confidence", 0.5),
        "source": evidence_data.get("source", "unknown"),
    }


class PatternContext:
    """Context for pattern-based prompt generation."""

    def __init__(self, pattern_type: str, data: Dict[str, Any]):
        self.pattern_type = pattern_type
        self.data = data
