# gemini_sre_agent/ml/base_prompt_template.py

"""
Base prompt template system for dynamic prompt generation.

This module provides the foundation for creating specialized prompt templates
that can adapt to different contexts and issue types.
"""

from abc import ABC, abstractmethod
import json
import logging
from typing import Any

from .prompt_context_models import PromptContext


class BasePromptTemplate(ABC):
    """Base class for dynamic prompt templates."""

    def __init__(self, template_name: str) -> None:
        """
        Initialize the prompt template.

        Args:
            template_name: Name identifier for this template
        """
        self.template_name = template_name
        self.logger = logging.getLogger(__name__)
        self.system_prompt = self._build_system_prompt()
        self.user_prompt_template = self._build_user_template()

    @abstractmethod
    def _build_system_prompt(self) -> str:
        """Build the system prompt for this template type."""
        pass

    @abstractmethod
    def _build_user_template(self) -> str:
        """Build the user prompt template."""
        pass

    @abstractmethod
    def _get_context_variables(self, context: PromptContext) -> dict[str, Any]:
        """Extract context variables for template formatting."""
        pass

    def generate_prompt(self, context: PromptContext) -> str:
        """
        Generate the complete prompt.

        Args:
            context: Complete context for prompt generation

        Returns:
            Formatted prompt string
        """
        try:
            context_vars = self._get_context_variables(context)

            # Build system prompt
            system_prompt = self.system_prompt

            # Build user prompt with dynamic content
            user_prompt = self.user_prompt_template.format(**context_vars)

            # Add few-shot examples if available
            few_shot_examples = self._get_few_shot_examples(context)
            if few_shot_examples:
                user_prompt += "\n\nFew-shot examples:\n" + few_shot_examples

            # Add validation feedback if this is a refinement
            if context.validation_feedback:
                user_prompt += self._add_validation_feedback(
                    context.validation_feedback
                )

            complete_prompt = f"{system_prompt}\n\n{user_prompt}"

            self.logger.debug(
                f"[{self.template_name}] Generated prompt: {len(complete_prompt)} chars"
            )
            return complete_prompt

        except Exception as e:
            self.logger.error(f"[{self.template_name}] Error generating prompt: {e}")
            raise ValueError(f"Failed to generate prompt: {e}") from e

    def _get_few_shot_examples(self, context: PromptContext) -> str:
        """
        Get relevant few-shot examples for the context.

        Args:
            context: Prompt context

        Returns:
            Formatted few-shot examples string
        """
        # Implementation would retrieve similar examples from database
        # For now, return empty string
        return ""

    def _add_validation_feedback(self, feedback: dict[str, Any]) -> str:
        """
        Add validation feedback to prompt for iterative refinement.

        Args:
            feedback: Validation feedback from previous iteration

        Returns:
            Formatted validation feedback string
        """
        return f"""

VALIDATION FEEDBACK FROM PREVIOUS ITERATION:
- Syntax Issues: {feedback.get('syntax_issues', 'None')}
- Pattern Compliance: {feedback.get('pattern_compliance', 'Passed')}
- Test Results: {feedback.get('test_results', 'Not run')}
- Performance Impact: {feedback.get('performance_impact', 'Unknown')}

Please address the above feedback and provide an improved solution."""

    def validate_context(self, context: PromptContext) -> bool:
        """
        Validate that the context is appropriate for this template.

        Args:
            context: Prompt context to validate

        Returns:
            True if context is valid, False otherwise
        """
        try:
            # Basic validation - check required fields
            if not context.issue_context or not context.repository_context:
                return False

            # Template-specific validation
            return self._validate_template_specific_context(context)

        except Exception as e:
            self.logger.error(f"[{self.template_name}] Context validation error: {e}")
            return False

    def _validate_template_specific_context(self, context: PromptContext) -> bool:
        """
        Template-specific context validation.

        Args:
            context: Prompt context to validate

        Returns:
            True if context is valid for this template
        """
        # Default implementation - can be overridden by subclasses
        return True

    def get_template_info(self) -> dict[str, Any]:
        """
        Get information about this template.

        Returns:
            Dictionary with template information
        """
        return {
            "template_name": self.template_name,
            "template_type": self.__class__.__name__,
            "system_prompt_length": len(self.system_prompt),
            "user_template_length": len(self.user_prompt_template),
        }


class GenericErrorPromptTemplate(BasePromptTemplate):
    """Generic template for unknown or general error types."""

    def _build_system_prompt(self) -> str:
        """Build generic system prompt."""
        return """You are an expert SRE Analysis Agent. Your task is to perform a deep root cause analysis of the provided issue and generate a comprehensive remediation plan focused on SERVICE CODE fixes.

EXPERTISE AREAS:
- System reliability and performance analysis
- Error pattern recognition and classification
- Code remediation and optimization
- Service architecture and dependencies
- Monitoring and observability

CODE GENERATION PRINCIPLES:
1. Always include proper error handling and logging
2. Follow the repository's established coding patterns
3. Consider performance implications of the fix
4. Ensure backward compatibility where possible
5. Include comprehensive error messages for debugging
6. Add appropriate monitoring and alerting

OUTPUT FORMAT:
Provide a structured JSON response with root cause analysis, proposed fix, and complete code implementation."""

    def _build_user_template(self) -> str:
        """Build generic user template."""
        return """ISSUE ANALYSIS REQUEST

Issue Context:
- Issue Type: {issue_type}
- Affected Services: {affected_services}
- Severity Level: {severity_level}/10
- User Impact: {user_impact}
- Business Impact: {business_impact}

Repository Context:
- Technology Stack: {technology_stack}
- Coding Standards: {coding_standards}
- Error Handling Patterns: {error_handling_patterns}
- Testing Patterns: {testing_patterns}

Issue Details:
- Triage Information: {triage_packet}
- Log Context: {log_context}
- Affected Files: {affected_files}
- Related Services: {related_services}

Historical Context:
- Similar Past Issues: {similar_issues}
- Recent Changes: {recent_changes}
- Previous Fixes: {previous_fixes}

Please provide a comprehensive analysis and code fix following the repository's established patterns."""

    def _get_context_variables(self, context: PromptContext) -> dict[str, Any]:
        """Extract context variables for generic template."""
        repo_ctx = context.repository_context
        issue_ctx = context.issue_context

        return {
            "issue_type": issue_ctx.issue_type.value,
            "affected_services": ", ".join(issue_ctx.related_services),
            "severity_level": issue_ctx.severity_level,
            "user_impact": issue_ctx.user_impact,
            "business_impact": issue_ctx.business_impact,
            "technology_stack": json.dumps(repo_ctx.technology_stack),
            "coding_standards": json.dumps(repo_ctx.coding_standards),
            "error_handling_patterns": ", ".join(repo_ctx.error_handling_patterns),
            "testing_patterns": ", ".join(repo_ctx.testing_patterns),
            "triage_packet": json.dumps(issue_ctx.to_dict()),
            "log_context": json.dumps(issue_ctx.temporal_context),
            "affected_files": ", ".join(issue_ctx.affected_files),
            "related_services": ", ".join(issue_ctx.related_services),
            "similar_issues": json.dumps(repo_ctx.historical_fixes[:3]),
            "recent_changes": json.dumps(repo_ctx.recent_changes[:5]),
            "previous_fixes": json.dumps(repo_ctx.historical_fixes[:2]),
        }
