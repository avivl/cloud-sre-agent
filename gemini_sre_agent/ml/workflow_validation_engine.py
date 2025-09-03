# gemini_sre_agent/ml/workflow_validation_engine.py

"""
Workflow Validation Engine for enhanced code generation.

This module handles code validation, quality checking, and validation
result processing for the unified workflow orchestrator.
"""

import logging
from typing import Any, Dict

from .prompt_context_models import PromptContext
from .validation import CodeValidationPipeline


class WorkflowValidationEngine:
    """
    Handles code validation and quality checking for the workflow orchestrator.

    This class manages:
    - Code validation using the validation pipeline
    - Python code syntax and quality validation
    - Validation result processing and formatting
    - Legacy format compatibility
    """

    def __init__(self):
        """Initialize the validation engine."""
        self.validation_pipeline = CodeValidationPipeline()
        self.logger = logging.getLogger(__name__)

    async def validate_generated_code(
        self, analysis_result: Dict[str, Any], prompt_context: PromptContext
    ) -> Dict[str, Any]:
        """
        Validate generated code for quality and correctness using the validation pipeline.

        Args:
            analysis_result: Analysis result containing generated code
            prompt_context: Context for validation

        Returns:
            Validation result
        """
        try:
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
            return self._format_validation_result(validation_result)

        except Exception as e:
            self.logger.error(f"[VALIDATION] Code validation failed: {e}")
            return self._create_error_validation_result(str(e))

    async def validate_python_code(self, code: str) -> Dict[str, Any]:
        """
        Validate Python code for syntax and common issues.

        Args:
            code: Python code to validate

        Returns:
            Validation result dictionary
        """
        validation_result = {
            "is_valid": True,
            "issues": [],
            "warnings": [],
            "suggestions": [],
        }

        try:
            # Check Python syntax
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            validation_result["is_valid"] = False
            validation_result["issues"].append(f"Syntax error: {e}")

        # Check for common Python issues
        if "import *" in code:
            validation_result["warnings"].append("Avoid wildcard imports")

        if "global " in code:
            validation_result["suggestions"].append(
                "Consider avoiding global variables"
            )

        return validation_result

    def _format_validation_result(self, validation_result) -> Dict[str, Any]:
        """
        Format validation result to legacy format for compatibility.

        Args:
            validation_result: Validation result from pipeline

        Returns:
            Formatted validation result
        """
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

    def _create_error_validation_result(self, error_message: str) -> Dict[str, Any]:
        """
        Create error validation result.

        Args:
            error_message: Error message

        Returns:
            Error validation result
        """
        return {
            "is_valid": False,
            "overall_score": 0.0,
            "issues": [f"Validation error: {error_message}"],
            "warnings": [],
            "suggestions": [],
            "validation_summary": {"error": error_message},
        }

    def get_validation_pipeline(self) -> CodeValidationPipeline:
        """
        Get the validation pipeline instance.

        Returns:
            CodeValidationPipeline instance
        """
        return self.validation_pipeline

    async def validate_code_with_custom_rules(
        self, code: str, custom_rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate code with custom validation rules.

        Args:
            code: Code to validate
            custom_rules: Custom validation rules

        Returns:
            Validation result
        """
        try:
            # This could be extended to support custom validation rules
            # For now, use the standard validation pipeline
            code_result = {
                "code_patch": code,
                "file_path": custom_rules.get("file_path", "unknown"),
                "generator_type": custom_rules.get("generator_type", "unknown"),
                "issue_type": custom_rules.get("issue_type", "unknown"),
            }

            validation_result = await self.validation_pipeline.validate_code(
                code_result, custom_rules.get("context", {})
            )

            return self._format_validation_result(validation_result)

        except Exception as e:
            self.logger.error(f"Custom validation failed: {e}")
            return self._create_error_validation_result(str(e))
