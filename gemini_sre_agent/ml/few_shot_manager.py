# gemini_sre_agent/ml/few_shot_manager.py

"""
Few-shot learning manager for enhanced code generation.

This module manages few-shot examples and context for improving
code generation quality through example-based learning.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .schemas import BaseSchema


@dataclass
class PatternContext(BaseSchema):
    """Context for pattern-based few-shot learning."""

    pattern_type: str
    context_data: Dict[str, Any]
    examples: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class FewShotManager:
    """
    Manages few-shot examples and context for code generation.

    This class provides functionality to store, retrieve, and manage
    few-shot examples that can be used to improve code generation quality.
    """

    def __init__(self, max_examples: int = 100):
        """
        Initialize the few-shot manager.

        Args:
            max_examples: Maximum number of examples to store
        """
        self.max_examples = max_examples
        self.examples: List[Dict[str, Any]] = []
        self.pattern_contexts: Dict[str, PatternContext] = {}

    def add_example(self, example: Dict[str, Any]) -> bool:
        """
        Add a new few-shot example.

        Args:
            example: Example data to add

        Returns:
            True if example was added successfully
        """
        if len(self.examples) >= self.max_examples:
            # Remove oldest example
            self.examples.pop(0)

        self.examples.append(example)
        return True

    def get_examples(
        self, pattern_type: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get few-shot examples.

        Args:
            pattern_type: Optional pattern type to filter by
            limit: Maximum number of examples to return

        Returns:
            List of examples
        """
        if pattern_type:
            filtered_examples = [
                ex for ex in self.examples if ex.get("pattern_type") == pattern_type
            ]
            return filtered_examples[:limit]

        return self.examples[:limit]

    def add_pattern_context(self, pattern_type: str, context: PatternContext) -> None:
        """
        Add pattern context for few-shot learning.

        Args:
            pattern_type: Type of pattern
            context: Pattern context data
        """
        self.pattern_contexts[pattern_type] = context

    def get_pattern_context(self, pattern_type: str) -> Optional[PatternContext]:
        """
        Get pattern context for a specific pattern type.

        Args:
            pattern_type: Type of pattern

        Returns:
            Pattern context if found, None otherwise
        """
        return self.pattern_contexts.get(pattern_type)

    def clear_examples(self) -> None:
        """Clear all stored examples."""
        self.examples.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            "total_examples": len(self.examples),
            "pattern_types": len(self.pattern_contexts),
            "max_examples": self.max_examples,
        }
