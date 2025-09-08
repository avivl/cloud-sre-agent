"""
Tests for FewShotManager database management and example selection.

This module tests few-shot learning example storage, retrieval,
validation, and statistics for Gemini prompt engineering.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from gemini_sre_agent.ml.few_shot_manager import (
    FewShotExample,
    FewShotManager,
    FewShotSource,
)
from gemini_sre_agent.ml.schemas import PatternContext


@pytest.fixture
def temp_db_path() -> str:
    """Create a temporary database file path."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        return f.name


@pytest.fixture
def sample_example() -> FewShotExample:
    """Create a sample FewShotExample for testing."""
    return FewShotExample(
        input_context="Database connection timeout causing 500 errors",
        expected_output={
            "pattern_type": "dependency_failure",
            "confidence": 0.89,
            "severity": "high",
            "evidence": [{"type": "timeout", "description": "Database timeout"}],
        },
        pattern_type="dependency_failure",
        source=FewShotSource.PRODUCTION_VALIDATION,
        timestamp=datetime(2024, 1, 15, 12, 30),
        validated=True,
        confidence_score=0.92,
    )


class TestFewShotExample:
    """Test cases for FewShotExample dataclass."""

    def test_example_creation(self, sample_example: FewShotExample) -> None:
        """Test FewShotExample creation and attributes."""
        assert (
            sample_example.input_context
            == "Database connection timeout causing 500 errors"
        )
        assert sample_example.pattern_type == "dependency_failure"
        assert sample_example.source == FewShotSource.PRODUCTION_VALIDATION
        assert sample_example.validated is True
        assert sample_example.confidence_score == 0.92

    def test_example_to_dict(self, sample_example: FewShotExample) -> None:
        """Test conversion to dictionary for storage."""
        result = sample_example.to_dict()

        assert isinstance(result, dict)
        assert result["input"] == sample_example.input_context
        assert result["output"] == sample_example.expected_output
        assert result["pattern_type"] == "dependency_failure"
        assert result["source"] == "production_validation"
        assert result["validated"] is True
        assert result["confidence_score"] == 0.92
        assert "timestamp" in result

    def test_example_from_dict(self, sample_example: FewShotExample) -> None:
        """Test creation from dictionary."""
        example_dict = sample_example.to_dict()
        restored_example = FewShotExample.from_dict(example_dict)

        assert restored_example.input_context == sample_example.input_context
        assert restored_example.expected_output == sample_example.expected_output
        assert restored_example.pattern_type == sample_example.pattern_type
        assert restored_example.source == sample_example.source
        assert restored_example.validated == sample_example.validated
        assert restored_example.confidence_score == sample_example.confidence_score

    def test_example_roundtrip_serialization(
        self, sample_example: FewShotExample
    ) -> None:
        """Test complete serialization roundtrip."""
        # Convert to dict, then back to object
        example_dict = sample_example.to_dict()
        restored_example = FewShotExample.from_dict(example_dict)

        # Convert restored object back to dict
        restored_dict = restored_example.to_dict()

        # Should be identical
        assert example_dict == restored_dict


class TestFewShotManager:
    """Test cases for FewShotManager."""

    def test_manager_initialization(self, temp_db_path: str) -> None:
        """Test manager initialization."""
        manager = FewShotManager(temp_db_path)

        assert manager.db_path == Path(temp_db_path)
        assert isinstance(manager.examples, dict)
        assert len(manager.examples) == 0  # Should start empty

    @pytest.mark.asyncio
    async def test_add_example(self, temp_db_path: str) -> None:
        """Test adding examples to the manager."""
        manager = FewShotManager(temp_db_path)

        await manager.add_example(
            pattern_type="cascading_failure",
            input_context="Service A failure caused downstream failures",
            expected_output={
                "pattern_type": "cascading_failure",
                "confidence": 0.95,
                "severity": "critical",
            },
            source=FewShotSource.EXPERT_CURATION,
            confidence_score=0.98,
        )

        # Verify example was added
        assert "cascading_failure" in manager.examples
        assert len(manager.examples["cascading_failure"]) == 1

        example = manager.examples["cascading_failure"][0]
        assert example.pattern_type == "cascading_failure"
        assert example.source == FewShotSource.EXPERT_CURATION
        assert example.confidence_score == 0.98

    def test_select_examples_empty_database(self, temp_db_path: str) -> None:
        """Test example selection with empty database."""
        manager = FewShotManager(temp_db_path)
        context = PatternContext()

        examples = manager.select_examples(context, max_examples=3)

        assert isinstance(examples, list)
        assert len(examples) == 0

    @pytest.mark.asyncio
    async def test_select_examples_with_data(self, temp_db_path: str) -> None:
        """Test example selection with available data."""
        manager = FewShotManager(temp_db_path)

        # Add multiple examples
        patterns_and_contexts = [
            ("dependency_failure", "Database timeout", 0.95),
            ("performance_degradation", "Slow response times", 0.88),
            ("cascading_failure", "Service cascade", 0.92),
        ]

        for pattern, context, confidence in patterns_and_contexts:
            await manager.add_example(
                pattern_type=pattern,
                input_context=context,
                expected_output={"pattern_type": pattern, "confidence": confidence},
                confidence_score=confidence,
            )

        # Select examples
        context = PatternContext(primary_service="test-service")
        examples = manager.select_examples(context, max_examples=2)

        assert isinstance(examples, list)
        assert len(examples) <= 2

        # Verify format of returned examples
        for example in examples:
            assert "Example Classification:" in example
            assert "Input:" in example
            assert "Output:" in example

    def test_get_statistics_empty(self, temp_db_path: str) -> None:
        """Test statistics with empty database."""
        manager = FewShotManager(temp_db_path)
        stats = manager.get_statistics()

        assert stats["total_examples"] == 0
        assert stats["pattern_counts"] == {}
        assert stats["source_distribution"] == {}
        assert stats["validation_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_statistics_with_data(self, temp_db_path: str) -> None:
        """Test statistics calculation with data."""
        manager = FewShotManager(temp_db_path)

        # Add examples with different sources and validation status
        examples_data = [
            ("pattern1", FewShotSource.HUMAN_FEEDBACK, True),
            ("pattern1", FewShotSource.EXPERT_CURATION, True),
            ("pattern2", FewShotSource.AUTOMATED_VALIDATION, False),
            ("pattern2", FewShotSource.PRODUCTION_VALIDATION, True),
        ]

        for pattern, source, validated in examples_data:
            example = FewShotExample(
                input_context=f"Test for {pattern}",
                expected_output={"pattern_type": pattern},
                pattern_type=pattern,
                source=source,
                timestamp=datetime.now(),
                validated=validated,
            )

            if pattern not in manager.examples:
                manager.examples[pattern] = []
            manager.examples[pattern].append(example)

        stats = manager.get_statistics()

        assert stats["total_examples"] == 4
        assert stats["pattern_counts"]["pattern1"] == 2
        assert stats["pattern_counts"]["pattern2"] == 2
        assert stats["source_distribution"]["human_feedback"] == 1
        assert stats["source_distribution"]["expert_curation"] == 1
        assert stats["validation_rate"] == 75.0  # 3 out of 4 validated

    @pytest.mark.asyncio
    async def test_persistence_save_and_load(self, temp_db_path: str) -> None:
        """Test saving and loading examples from database."""
        # Create manager and add example
        manager1 = FewShotManager(temp_db_path)

        await manager1.add_example(
            pattern_type="test_pattern",
            input_context="Test input",
            expected_output={"test": "output"},
            source=FewShotSource.HUMAN_FEEDBACK,
        )

        # Create new manager with same database path
        manager2 = FewShotManager(temp_db_path)

        # Should load the previously saved example
        assert "test_pattern" in manager2.examples
        assert len(manager2.examples["test_pattern"]) == 1

        example = manager2.examples["test_pattern"][0]
        assert example.input_context == "Test input"
        assert example.expected_output == {"test": "output"}
        assert example.source == FewShotSource.HUMAN_FEEDBACK

    def test_load_examples_nonexistent_file(self, temp_db_path: str) -> None:
        """Test loading examples when database file doesn't exist."""
        # Use non-existent file path
        nonexistent_path = temp_db_path + "_nonexistent"

        # Should not raise exception, should initialize empty
        manager = FewShotManager(nonexistent_path)
        assert isinstance(manager.examples, dict)
        assert len(manager.examples) == 0

    def test_load_examples_corrupted_file(self, temp_db_path: str) -> None:
        """Test loading examples with corrupted JSON file."""
        # Write invalid JSON to file
        with open(temp_db_path, "w") as f:
            f.write("invalid json content")

        # Should handle gracefully
        manager = FewShotManager(temp_db_path)
        assert isinstance(manager.examples, dict)
        assert len(manager.examples) == 0

    @pytest.mark.asyncio
    async def test_save_examples_error_handling(self, temp_db_path: str) -> None:
        """Test error handling during save operations."""
        manager = FewShotManager(temp_db_path)

        # Mock Path.mkdir to raise exception
        with patch.object(Path, "mkdir", side_effect=PermissionError("No permission")):
            # Should not crash, should log error
            await manager.add_example(
                pattern_type="test",
                input_context="test",
                expected_output={"test": True},
            )

            # Example should still be in memory even if save failed
            assert "test" in manager.examples

    def test_confidence_score_ordering(self, temp_db_path: str) -> None:
        """Test that examples are ordered by confidence score."""
        manager = FewShotManager(temp_db_path)

        # Add examples with different confidence scores
        examples_data = [
            ("pattern1", "Low confidence example", 0.6),
            ("pattern1", "High confidence example", 0.95),
            ("pattern1", "Medium confidence example", 0.8),
        ]

        for pattern, context, confidence in examples_data:
            example = FewShotExample(
                input_context=context,
                expected_output={"pattern_type": pattern},
                pattern_type=pattern,
                source=FewShotSource.HUMAN_FEEDBACK,
                timestamp=datetime.now(),
                confidence_score=confidence,
            )

            if pattern not in manager.examples:
                manager.examples[pattern] = []
            manager.examples[pattern].append(example)

        # Select examples - should return highest confidence first
        context = PatternContext()
        examples = manager.select_examples(context, max_examples=2)

        # Should contain the high confidence example
        high_conf_found = any("High confidence example" in ex for ex in examples)
        assert high_conf_found

    @pytest.mark.asyncio
    async def test_multiple_patterns_selection(self, temp_db_path: str) -> None:
        """Test selection across multiple pattern types."""
        manager = FewShotManager(temp_db_path)

        # Add examples for different patterns
        patterns = [
            "cascading_failure",
            "dependency_failure",
            "performance_degradation",
        ]

        for pattern in patterns:
            await manager.add_example(
                pattern_type=pattern,
                input_context=f"Example for {pattern}",
                expected_output={"pattern_type": pattern, "confidence": 0.9},
            )

        # Select examples - should get one from each pattern type (up to max_examples)
        context = PatternContext()
        examples = manager.select_examples(context, max_examples=3)

        assert len(examples) <= 3

        # Should have examples from different patterns
        example_text = " ".join(examples)
        for pattern in patterns:
            if len(examples) >= patterns.index(pattern) + 1:
                assert pattern in example_text

    def test_validation_rate_calculation(self, temp_db_path: str) -> None:
        """Test validation rate calculation with mixed validation status."""
        manager = FewShotManager(temp_db_path)

        # Add examples with different validation status
        validation_statuses = [True, True, False, True, False]  # 60% validated

        for i, validated in enumerate(validation_statuses):
            example = FewShotExample(
                input_context=f"Example {i}",
                expected_output={"test": i},
                pattern_type="test_pattern",
                source=FewShotSource.HUMAN_FEEDBACK,
                timestamp=datetime.now(),
                validated=validated,
            )

            if "test_pattern" not in manager.examples:
                manager.examples["test_pattern"] = []
            manager.examples["test_pattern"].append(example)

        stats = manager.get_statistics()
        assert stats["validation_rate"] == 60.0  # 3 out of 5 validated
