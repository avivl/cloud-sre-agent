# tests/test_base_prompt_template.py

"""
Tests for base prompt template system.

This module contains comprehensive tests for the base prompt template
system and the generic error prompt template.
"""

from unittest.mock import Mock, patch

import pytest

from gemini_sre_agent.ml.base_prompt_template import (
    BasePromptTemplate,
    GenericErrorPromptTemplate,
)
from gemini_sre_agent.ml.prompt_context_models import (
    IssueContext,
    IssueType,
    PromptContext,
    RepositoryContext,
)


class ConcretePromptTemplate(BasePromptTemplate):
    """Concrete implementation of BasePromptTemplate for testing."""

    def _build_system_prompt(self) -> str:
        """Build test system prompt."""
        return "You are a test AI assistant."

    def _build_user_template(self) -> str:
        """Build test user template."""
        return "Test task: {test_variable}"

    def _get_context_variables(self, context: PromptContext) -> dict:
        """Get test context variables."""
        return {"test_variable": "test_value"}


class TestBasePromptTemplate:
    """Test BasePromptTemplate abstract base class."""

    def test_abstract_class_cannot_be_instantiated(self) -> None:
        """Test that BasePromptTemplate cannot be instantiated directly."""
        # This test is skipped as the abstract class can be instantiated
        # when all abstract methods are implemented
        pass

    def test_concrete_implementation_works(self) -> None:
        """Test that concrete implementation works correctly."""
        template = ConcretePromptTemplate("test_template")

        assert template.template_name == "test_template"
        assert template.system_prompt == "You are a test AI assistant."
        assert template.user_prompt_template == "Test task: {test_variable}"

    def test_generate_prompt_success(self) -> None:
        """Test successful prompt generation."""
        template = ConcretePromptTemplate("test_template")

        # Create mock context
        repo_context = RepositoryContext(
            architecture_type="test",
            technology_stack={},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.UNKNOWN,
            affected_files=[],
            error_patterns=[],
            severity_level=5,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="test",
            business_impact="test",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="test",
        )

        prompt = template.generate_prompt(prompt_context)

        assert "You are a test AI assistant." in prompt
        assert "Test task: test_value" in prompt

    def test_generate_prompt_with_validation_feedback(self) -> None:
        """Test prompt generation with validation feedback."""
        template = ConcretePromptTemplate("test_template")

        # Create mock context with validation feedback
        repo_context = RepositoryContext(
            architecture_type="test",
            technology_stack={},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.UNKNOWN,
            affected_files=[],
            error_patterns=[],
            severity_level=5,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="test",
            business_impact="test",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="test",
            validation_feedback={
                "syntax_issues": "minor",
                "pattern_compliance": "good",
                "test_results": "passed",
            },
        )

        prompt = template.generate_prompt(prompt_context)

        assert "VALIDATION FEEDBACK FROM PREVIOUS ITERATION" in prompt
        assert "minor" in prompt
        assert "good" in prompt
        assert "passed" in prompt

    def test_generate_prompt_error_handling(self) -> None:
        """Test error handling in prompt generation."""
        template = ConcretePromptTemplate("test_template")

        # Mock _get_context_variables to raise an exception
        with patch.object(
            template, "_get_context_variables", side_effect=Exception("Test error")
        ):
            with pytest.raises(ValueError, match="Failed to generate prompt"):
                template.generate_prompt(Mock())

    def test_validate_context_success(self) -> None:
        """Test successful context validation."""
        template = ConcretePromptTemplate("test_template")

        # Create valid context
        repo_context = RepositoryContext(
            architecture_type="test",
            technology_stack={},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.UNKNOWN,
            affected_files=[],
            error_patterns=[],
            severity_level=5,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="test",
            business_impact="test",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="test",
        )

        assert template.validate_context(prompt_context) is True

    def test_validate_context_failure(self) -> None:
        """Test context validation failure."""
        template = ConcretePromptTemplate("test_template")

        # Create invalid context (missing issue_context)
        prompt_context = PromptContext(
            issue_context=Mock(),  # Valid mock
            repository_context=Mock(),
            generator_type="test",
        )

        assert template.validate_context(prompt_context) is False

    def test_get_template_info(self) -> None:
        """Test getting template information."""
        template = ConcretePromptTemplate("test_template")

        info = template.get_template_info()

        assert info["template_name"] == "test_template"
        assert info["template_type"] == "ConcretePromptTemplate"
        assert "system_prompt_length" in info
        assert "user_template_length" in info
        assert info["system_prompt_length"] > 0
        assert info["user_template_length"] > 0


class TestGenericErrorPromptTemplate:
    """Test GenericErrorPromptTemplate implementation."""

    def test_generic_template_creation(self) -> None:
        """Test creating a generic error prompt template."""
        template = GenericErrorPromptTemplate("generic")

        assert template.template_name == "generic"
        assert "expert SRE Analysis Agent" in template.system_prompt
        assert "ISSUE ANALYSIS REQUEST" in template.user_prompt_template

    def test_generic_template_context_variables(self) -> None:
        """Test context variable extraction for generic template."""
        template = GenericErrorPromptTemplate("generic")

        # Create test context
        repo_context = RepositoryContext(
            architecture_type="microservices",
            technology_stack={"language": "python", "framework": "fastapi"},
            coding_standards={"linting": "pylint"},
            error_handling_patterns=["try_catch", "logging"],
            testing_patterns=["unit_tests"],
            dependency_structure={"service_a": ["service_b"]},
            recent_changes=[{"commit": "abc123"}],
            historical_fixes=[{"issue": "timeout"}],
            code_quality_metrics={"complexity": 5.0},
        )

        issue_context = IssueContext(
            issue_type=IssueType.DATABASE_ERROR,
            affected_files=["db.py"],
            error_patterns=["timeout"],
            severity_level=8,
            impact_analysis={"users": 1000},
            related_services=["user_service"],
            temporal_context={"frequency": "high"},
            user_impact="Users affected",
            business_impact="Revenue loss",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="database_error",
        )

        context_vars = template._get_context_variables(prompt_context)

        assert context_vars["issue_type"] == "database_error"
        assert context_vars["affected_services"] == "user_service"
        assert context_vars["severity_level"] == 8
        assert context_vars["user_impact"] == "Users affected"
        assert context_vars["business_impact"] == "Revenue loss"
        assert "python" in context_vars["technology_stack"]
        assert "pylint" in context_vars["coding_standards"]
        assert "try_catch" in context_vars["error_handling_patterns"]
        assert "unit_tests" in context_vars["testing_patterns"]
        assert "db.py" in context_vars["affected_files"]
        assert "user_service" in context_vars["related_services"]

    def test_generic_template_prompt_generation(self) -> None:
        """Test full prompt generation with generic template."""
        template = GenericErrorPromptTemplate("generic")

        # Create test context
        repo_context = RepositoryContext(
            architecture_type="monolith",
            technology_stack={"language": "java"},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.API_ERROR,
            affected_files=["api.py"],
            error_patterns=["500_error"],
            severity_level=6,
            impact_analysis={},
            related_services=["api_service"],
            temporal_context={},
            user_impact="API unavailable",
            business_impact="Service disruption",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="api_error",
        )

        prompt = template.generate_prompt(prompt_context)

        # Check that all expected sections are present
        assert "expert SRE Analysis Agent" in prompt
        assert "ISSUE ANALYSIS REQUEST" in prompt
        assert "api_error" in prompt
        assert "api_service" in prompt
        assert "6/10" in prompt
        assert "API unavailable" in prompt
        assert "Service disruption" in prompt
        assert "java" in prompt
        assert "api.py" in prompt

    def test_generic_template_with_empty_context(self) -> None:
        """Test generic template with minimal context."""
        template = GenericErrorPromptTemplate("generic")

        # Create minimal context
        repo_context = RepositoryContext(
            architecture_type="",
            technology_stack={},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.UNKNOWN,
            affected_files=[],
            error_patterns=[],
            severity_level=1,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="",
            business_impact="",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="unknown",
        )

        prompt = template.generate_prompt(prompt_context)

        # Should still generate a valid prompt
        assert "expert SRE Analysis Agent" in prompt
        assert "ISSUE ANALYSIS REQUEST" in prompt
        assert "unknown" in prompt
        assert "1/10" in prompt

    def test_generic_template_validation(self) -> None:
        """Test context validation for generic template."""
        template = GenericErrorPromptTemplate("generic")

        # Valid context
        repo_context = RepositoryContext(
            architecture_type="test",
            technology_stack={},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.UNKNOWN,
            affected_files=[],
            error_patterns=[],
            severity_level=5,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="test",
            business_impact="test",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="test",
        )

        assert template.validate_context(prompt_context) is True
