# gemini_sre_agent/llm/utils.py

"""
Utility functions for LLM operations.

This module provides utility functions for parsing structured output,
error handling, and other common LLM operations.
"""

import json
import re
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def parse_structured_output(text: str, model: Type[T]) -> T:
    """
    Parse text into a structured Pydantic model.

    Args:
        text: Text to parse
        model: Pydantic model class

    Returns:
        Parsed model instance

    Raises:
        ValueError: If parsing fails
    """
    try:
        # First try to parse as JSON
        data = json.loads(text)
        return model.parse_obj(data)
    except json.JSONDecodeError:
        # If not valid JSON, try to extract JSON from text
        try:
            # Look for JSON-like structure between ``` or {}
            json_match = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                return model.parse_obj(data)
            else:
                raise ValueError("Could not extract JSON from response")
        except Exception as e:
            raise ValueError(f"Failed to parse structured output: {str(e)}") from e


def extract_json_from_text(text: str) -> dict:
    """
    Extract JSON object from text that may contain other content.

    Args:
        text: Text that may contain JSON

    Returns:
        Extracted JSON as dictionary

    Raises:
        ValueError: If no valid JSON found
    """
    # Try direct JSON parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Look for JSON in code blocks
    json_patterns = [
        r"```json\n(.*?)\n```",
        r"```\n(.*?)\n```",
        r"`(.*?)`",
        r"\{.*\}",  # Simple object pattern
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

    raise ValueError("No valid JSON found in text")


def sanitize_prompt(prompt: str) -> str:
    """
    Sanitize a prompt by removing potentially sensitive information.

    Args:
        prompt: Original prompt text

    Returns:
        Sanitized prompt text
    """
    # Remove common patterns that might contain sensitive data
    patterns_to_remove = [
        r'api[_-]?key["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]+["\']?',
        r'password["\']?\s*[:=]\s*["\']?[^\s"\']+["\']?',
        r'token["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]+["\']?',
        r'secret["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]+["\']?',
    ]

    sanitized = prompt
    for pattern in patterns_to_remove:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)

    return sanitized


def estimate_tokens(text: str) -> int:
    """
    Rough estimation of token count for text.

    This is a simple approximation. For accurate token counting,
    use the specific tokenizer for the model being used.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count
    """
    # Rough approximation: 1 token ≈ 4 characters for English text
    # This varies by language and model
    return len(text) // 4


def format_model_name(provider: str, model: str) -> str:
    """
    Format model name for LiteLLM compatibility.

    Args:
        provider: Provider name
        model: Model name

    Returns:
        Formatted model name for LiteLLM
    """
    # LiteLLM uses specific prefixes for different providers
    provider_prefixes = {
        "openai": "",
        "anthropic": "claude-",
        "gemini": "gemini/",
        "grok": "grok-",
        "bedrock": "bedrock/",
        "ollama": "ollama/",
    }

    prefix = provider_prefixes.get(provider, f"{provider}/")
    return f"{prefix}{model}"


def validate_model_name(model_name: str) -> bool:
    """
    Validate that a model name is properly formatted.

    Args:
        model_name: Model name to validate

    Returns:
        True if valid, False otherwise
    """
    if not model_name or not isinstance(model_name, str):
        return False

    # Basic validation: should not be empty and should not contain invalid characters
    invalid_chars = ["<", ">", ":", '"', "|", "?", "*"]
    return not any(char in model_name for char in invalid_chars)
