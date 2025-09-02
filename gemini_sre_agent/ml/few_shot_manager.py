"""
Few-shot learning management for Gemini prompt engineering.

This module provides database management and example selection for few-shot
learning in pattern detection, supporting validation and confidence scoring.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

from .schemas import PatternContext


class FewShotSource(str, Enum):
    """Sources for few-shot examples."""

    HUMAN_FEEDBACK = "human_feedback"
    AUTOMATED_VALIDATION = "automated_validation"
    EXPERT_CURATION = "expert_curation"
    PRODUCTION_VALIDATION = "production_validation"


@dataclass
class FewShotExample:
    """Container for few-shot learning examples."""

    input_context: str
    expected_output: Dict[str, Any]
    pattern_type: str
    source: FewShotSource
    timestamp: datetime
    validated: bool = True
    confidence_score: float = 0.95

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "input": self.input_context,
            "output": self.expected_output,
            "pattern_type": self.pattern_type,
            "source": self.source.value,
            "timestamp": self.timestamp.isoformat(),
            "validated": self.validated,
            "confidence_score": self.confidence_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FewShotExample":
        """Create from dictionary."""
        return cls(
            input_context=data["input"],
            expected_output=data["output"],
            pattern_type=data["pattern_type"],
            source=FewShotSource(data["source"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            validated=data.get("validated", True),
            confidence_score=data.get("confidence_score", 0.95),
        )


class FewShotManager:
    """Manages few-shot learning examples for prompt engineering."""

    def __init__(self, db_path: str = "few_shot_examples.json"):
        """Initialize manager with database path."""
        self.db_path = Path(db_path)
        self.examples: Dict[str, List[FewShotExample]] = {}
        self.logger = logging.getLogger(__name__)
        self._load_examples()

    async def add_example(
        self,
        pattern_type: str,
        input_context: str,
        expected_output: Dict[str, Any],
        source: FewShotSource = FewShotSource.HUMAN_FEEDBACK,
        confidence_score: float = 0.95,
    ) -> None:
        """Add validated few-shot example to the database."""
        example = FewShotExample(
            input_context=input_context,
            expected_output=expected_output,
            pattern_type=pattern_type,
            source=source,
            timestamp=datetime.now(),
            confidence_score=confidence_score,
        )

        if pattern_type not in self.examples:
            self.examples[pattern_type] = []

        self.examples[pattern_type].append(example)
        await self._save_examples()

        self.logger.info(
            "[FEW_SHOT] Added example for %s (source: %s)",
            pattern_type,
            source.value,
        )

    def select_examples(
        self, context: PatternContext, max_examples: int = 3
    ) -> List[str]:
        """Select most relevant few-shot examples for context."""
        formatted_examples = []

        # Simple selection based on pattern relevance and confidence
        for _pattern_type, pattern_examples in self.examples.items():
            if len(formatted_examples) >= max_examples:
                break

            # Get highest confidence examples first
            sorted_examples = sorted(
                pattern_examples, key=lambda x: x.confidence_score, reverse=True
            )

            for example in sorted_examples[:1]:  # One example per pattern type
                formatted_example = (
                    f"Example Classification:\n"
                    f"Input: {example.input_context[:200]}...\n"
                    f"Output: {json.dumps(example.expected_output, indent=2)}\n"
                )
                formatted_examples.append(formatted_example)

        return formatted_examples[:max_examples]

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about few-shot examples."""
        total_examples = sum(len(examples) for examples in self.examples.values())
        pattern_counts = {
            pattern: len(examples) for pattern, examples in self.examples.items()
        }

        source_counts = {}
        for examples in self.examples.values():
            for example in examples:
                source_counts[example.source.value] = (
                    source_counts.get(example.source.value, 0) + 1
                )

        return {
            "total_examples": total_examples,
            "pattern_counts": pattern_counts,
            "source_distribution": source_counts,
            "validation_rate": self._calculate_validation_rate(),
        }

    def _load_examples(self) -> None:
        """Load few-shot examples from database file."""
        try:
            if self.db_path.exists():
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for pattern_type, examples_data in data.items():
                    self.examples[pattern_type] = [
                        FewShotExample.from_dict(example_data)
                        for example_data in examples_data
                    ]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.warning("[FEW_SHOT] Failed to load examples: %s", e)
            self.examples = {}

    async def _save_examples(self) -> None:
        """Save few-shot examples to database file."""
        try:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                pattern_type: [example.to_dict() for example in examples]
                for pattern_type, examples in self.examples.items()
            }

            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error("[FEW_SHOT] Failed to save examples: %s", e)

    def _calculate_validation_rate(self) -> float:
        """Calculate percentage of validated examples."""
        total_examples = 0
        validated_examples = 0

        for examples in self.examples.values():
            for example in examples:
                total_examples += 1
                if example.validated:
                    validated_examples += 1

        return (
            (validated_examples / total_examples * 100) if total_examples > 0 else 0.0
        )
