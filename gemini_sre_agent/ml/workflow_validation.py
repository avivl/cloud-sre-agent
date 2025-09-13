# gemini_sre_agent/ml/workflow_validation.py

"""
Workflow validation engine module.

This module handles all validation operations for the workflow orchestrator.
Extracted from unified_workflow_orchestrator_original.py.
"""

import logging
from typing import Any

from .performance import PerformanceConfig
from .prompt_context_models import PromptContext


class WorkflowValidationEngine:
    """
    Manages workflow validation operations.

    This class handles all validation operations including code validation,
    quality checks, and validation result processing with proper error handling.
    """

    def __init__(self, performance_config: PerformanceConfig | None) -> None:
        """
        Initialize the workflow validation engine.

        Args:
            performance_config: Performance configuration
        """
        self.performance_config = performance_config
        self.logger = logging.getLogger(__name__)

        # Initialize validation pipeline (will be injected)
        self.validation_pipeline: Any | None = None

    def set_validation_pipeline(self, validation_pipeline: Any) -> None:
        """Set the validation pipeline."""
        self.validation_pipeline = validation_pipeline

    async def validate_generated_code(
        self, analysis_result: dict[str, Any], prompt_context: PromptContext
    ) -> dict[str, Any]:
        """
        Validate generated code for quality and correctness using the validation pipeline.

        Args:
            analysis_result: Analysis result containing generated code
            prompt_context: Context for validation

        Returns:
            Validation result
        """
        try:
            if not self.validation_pipeline:
                self.logger.warning(
                    "Validation pipeline not set, using basic validation"
                )
                return await self._validate_python_code(
                    analysis_result.get("analysis", {}).get("code_patch", "")
                )

            # Prepare code result for validation pipeline
            code_result = {
                "code_patch": analysis_result.get("analysis", {}).get("code_patch", ""),
                "file_path": analysis_result.get("analysis", {}).get(
                    "file_path", "unknown"
                ),
                "generator_type": prompt_context.generator_type,
                "issue_type": prompt_context.issue_context.issue_type.value,
            }

            # Use the validation pipeline
            validation_result = await self.validation_pipeline.validate_code(
                code_result,
                {
                    "repository_context": prompt_context.repository_context,
                    "issue_context": prompt_context.issue_context,
                },
            )

            # Convert to legacy format for compatibility
            return {
                "is_valid": validation_result.is_valid,
                "overall_score": validation_result.overall_score,
                "issues": [
                    {
                        "id": issue.issue_id,
                        "type": issue.validation_type.value,
                        "level": issue.level.value,
                        "message": issue.message,
                        "description": issue.description,
                        "line_number": issue.line_number,
                        "suggested_fix": issue.suggested_fix,
                    }
                    for issue in validation_result.issues
                ],
                "warnings": [
                    issue
                    for issue in validation_result.issues
                    if issue.level.value == "warning"
                ],
                "suggestions": [
                    {
                        "id": feedback.feedback_id,
                        "category": feedback.category,
                        "message": feedback.message,
                        "suggestion": feedback.suggestion,
                        "priority": feedback.priority,
                    }
                    for feedback in validation_result.feedback
                ],
                "validation_summary": validation_result.get_validation_summary(),
            }

        except Exception as e:
            self.logger.error(f"[VALIDATION] Code validation failed: {e}")
            return {
                "is_valid": False,
                "overall_score": 0.0,
                "issues": [f"Validation error: {e}"],
                "warnings": [],
                "suggestions": [],
                "validation_summary": {"error": str(e)},
            }

    async def _validate_python_code(self, code: str) -> dict[str, Any]:
        """
        Basic Python code validation as fallback.

        Args:
            code: Python code to validate

        Returns:
            Basic validation result
        """
        try:
            if not code.strip():
                return {
                    "is_valid": False,
                    "overall_score": 0.0,
                    "issues": ["Empty code provided"],
                    "warnings": [],
                    "suggestions": [],
                    "validation_summary": {"error": "Empty code"},
                }

            # Basic syntax check
            try:
                compile(code, "<string>", "exec")
                syntax_valid = True
                syntax_issues = []
            except SyntaxError as e:
                syntax_valid = False
                syntax_issues = [f"Syntax error: {e}"]
            except Exception as e:
                syntax_valid = False
                syntax_issues = [f"Compilation error: {e}"]

            # Basic quality checks
            quality_issues = []
            warnings = []
            suggestions = []

            # Check for common issues
            if "TODO" in code:
                warnings.append("Code contains TODO comments")
                suggestions.append("Review and implement TODO items")

            if "pass" in code:
                warnings.append("Code contains 'pass' statements")
                suggestions.append("Implement actual functionality instead of 'pass'")

            if not code.strip().startswith("#"):
                suggestions.append("Add proper documentation and comments")

            # Calculate basic score
            score = 0.0
            if syntax_valid:
                score += 0.5
            if not quality_issues:
                score += 0.3
            if not warnings:
                score += 0.2

            return {
                "is_valid": syntax_valid and len(quality_issues) == 0,
                "overall_score": score,
                "issues": syntax_issues + quality_issues,
                "warnings": warnings,
                "suggestions": suggestions,
                "validation_summary": {
                    "syntax_valid": syntax_valid,
                    "quality_score": score,
                    "total_issues": len(syntax_issues + quality_issues),
                    "total_warnings": len(warnings),
                },
            }

        except Exception as e:
            self.logger.error(f"Basic validation failed: {e}")
            return {
                "is_valid": False,
                "overall_score": 0.0,
                "issues": [f"Validation error: {e}"],
                "warnings": [],
                "suggestions": [],
                "validation_summary": {"error": str(e)},
            }

    async def get_validation_statistics(self) -> dict[str, Any]:
        """
        Get validation statistics for monitoring.

        Returns:
            Dictionary containing validation statistics
        """
        try:
            return {
                "validation_pipeline_available": self.validation_pipeline is not None,
                "performance_config_available": self.performance_config is not None,
            }
        except Exception as e:
            self.logger.error(f"Failed to get validation statistics: {e}")
            return {"error": str(e)}

    async def health_check(self) -> str:
        """
        Perform health check on validation engine components.

        Returns:
            Health status string
        """
        try:
            # Check if essential components are available
            if not self.validation_pipeline:
                return "degraded - validation pipeline not set"

            # Test basic functionality
            try:
                # Test basic validation with minimal data
                test_code = "print('test')"
                result = await self._validate_python_code(test_code)

                if not result.get("is_valid", False):
                    return "unhealthy - basic validation failed"

            except Exception as e:
                return f"unhealthy - validation test failed: {e!s}"

            return "healthy"

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return f"unhealthy - {e!s}"
