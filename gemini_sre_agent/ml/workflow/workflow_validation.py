# gemini_sre_agent/ml/workflow/workflow_validation.py

"""
Workflow validation module for the unified workflow orchestrator.

This module handles validation operations within the workflow, including
code validation, prompt validation, and solution validation.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ...core.interfaces import ProcessableComponent
from ...core.types import ConfigDict, Timestamp

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """
    Result of workflow validation operations.

    This class holds the results of validation operations including
    validation status, errors, warnings, and recommendations.
    """

    # Validation metadata
    validation_id: str
    workflow_id: str
    validation_type: str
    timestamp: Timestamp

    # Validation results
    is_valid: bool
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    recommendations: List[str]
    confidence_score: float

    # Performance metrics
    validation_duration: float
    items_validated: int
    success: bool
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        return {
            "validation_id": self.validation_id,
            "workflow_id": self.workflow_id,
            "validation_type": self.validation_type,
            "timestamp": self.timestamp,
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "confidence_score": self.confidence_score,
            "validation_duration": self.validation_duration,
            "items_validated": self.items_validated,
            "success": self.success,
            "error_message": self.error_message,
        }


class WorkflowValidationEngine(ProcessableComponent[Dict[str, Any], ValidationResult]):
    """
    Validation engine for workflow operations.

    This class handles all validation operations within the workflow,
    including code validation, prompt validation, and solution validation.
    """

    def __init__(
        self,
        component_id: str = "workflow_validation_engine",
        name: str = "Workflow Validation Engine",
        config: Optional[ConfigDict] = None,
    ) -> None:
        """
        Initialize the workflow validation engine.

        Args:
            component_id: Unique identifier for the component
            name: Human-readable name for the component
            config: Optional initial configuration
        """
        super().__init__(component_id, name, config)

        # Validation tracking
        self.validation_count = 0
        self.total_validation_time = 0.0
        self.successful_validations = 0
        self.failed_validations = 0
        self.error_count = 0

        # Validation rules
        self.validation_rules = self._initialize_validation_rules()

    async def validate_code(
        self,
        code_content: str,
        file_path: str,
        workflow_id: str,
        validation_type: str = "syntax",
    ) -> ValidationResult:
        """
        Validate code content for syntax, style, and best practices.

        Args:
            code_content: Code content to validate
            file_path: File path for context
            workflow_id: Workflow identifier
            validation_type: Type of validation to perform

        Returns:
            Validation result
        """
        start_time = time.time()
        validation_id = f"code_val_{workflow_id}_{int(time.time())}"

        try:
            logger.info(
                f"Starting {validation_type} code validation for workflow {workflow_id}"
            )

            # Perform code validation
            errors = []
            warnings = []
            recommendations = []

            # Basic syntax validation
            syntax_errors = self._validate_syntax(code_content, file_path)
            errors.extend(syntax_errors)

            # Style validation
            if validation_type in ["style", "comprehensive"]:
                style_warnings = self._validate_style(code_content, file_path)
                warnings.extend(style_warnings)

            # Best practices validation
            if validation_type in ["best_practices", "comprehensive"]:
                best_practice_warnings = self._validate_best_practices(
                    code_content, file_path
                )
                warnings.extend(best_practice_warnings)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                code_content, errors, warnings
            )

            # Calculate confidence score
            confidence_score = self._calculate_confidence(errors, warnings)

            # Determine if valid
            is_valid = len(errors) == 0

            validation_duration = time.time() - start_time

            result = ValidationResult(
                validation_id=validation_id,
                workflow_id=workflow_id,
                validation_type=validation_type,
                timestamp=time.time(),
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                recommendations=recommendations,
                confidence_score=confidence_score,
                validation_duration=validation_duration,
                items_validated=1,
                success=True,
            )

            # Update metrics
            self.validation_count += 1
            self.total_validation_time += validation_duration
            self.successful_validations += 1

            logger.info(
                f"Completed code validation {validation_id} in {validation_duration:.3f}s"
            )
            return result

        except Exception as e:
            validation_duration = time.time() - start_time
            error_msg = f"Code validation failed: {str(e)}"

            logger.error(f"Code validation {validation_id} failed: {error_msg}")

            result = ValidationResult(
                validation_id=validation_id,
                workflow_id=workflow_id,
                validation_type=validation_type,
                timestamp=time.time(),
                is_valid=False,
                errors=[{"type": "validation_error", "message": error_msg}],
                warnings=[],
                recommendations=[],
                confidence_score=0.0,
                validation_duration=validation_duration,
                items_validated=1,
                success=False,
                error_message=error_msg,
            )

            # Update metrics
            self.validation_count += 1
            self.total_validation_time += validation_duration
            self.failed_validations += 1

            return result

    async def validate_prompts(
        self,
        prompts: List[str],
        workflow_id: str,
        validation_type: str = "completeness",
    ) -> ValidationResult:
        """
        Validate prompts for completeness and quality.

        Args:
            prompts: List of prompts to validate
            workflow_id: Workflow identifier
            validation_type: Type of validation to perform

        Returns:
            Validation result
        """
        start_time = time.time()
        validation_id = f"prompt_val_{workflow_id}_{int(time.time())}"

        try:
            logger.info(
                f"Starting {validation_type} prompt validation for workflow {workflow_id}"
            )

            # Perform prompt validation
            errors = []
            warnings = []
            recommendations = []

            for i, prompt in enumerate(prompts):
                # Basic completeness validation
                if validation_type in ["completeness", "comprehensive"]:
                    completeness_errors = self._validate_prompt_completeness(prompt, i)
                    errors.extend(completeness_errors)

                # Quality validation
                if validation_type in ["quality", "comprehensive"]:
                    quality_warnings = self._validate_prompt_quality(prompt, i)
                    warnings.extend(quality_warnings)

                # Clarity validation
                if validation_type in ["clarity", "comprehensive"]:
                    clarity_warnings = self._validate_prompt_clarity(prompt, i)
                    warnings.extend(clarity_warnings)

            # Generate recommendations
            recommendations = self._generate_prompt_recommendations(
                prompts, errors, warnings
            )

            # Calculate confidence score
            confidence_score = self._calculate_confidence(errors, warnings)

            # Determine if valid
            is_valid = len(errors) == 0

            validation_duration = time.time() - start_time

            result = ValidationResult(
                validation_id=validation_id,
                workflow_id=workflow_id,
                validation_type=validation_type,
                timestamp=time.time(),
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                recommendations=recommendations,
                confidence_score=confidence_score,
                validation_duration=validation_duration,
                items_validated=len(prompts),
                success=True,
            )

            # Update metrics
            self.validation_count += 1
            self.total_validation_time += validation_duration
            self.successful_validations += 1

            logger.info(
                f"Completed prompt validation {validation_id} in {validation_duration:.3f}s"
            )
            return result

        except Exception as e:
            validation_duration = time.time() - start_time
            error_msg = f"Prompt validation failed: {str(e)}"

            logger.error(f"Prompt validation {validation_id} failed: {error_msg}")

            result = ValidationResult(
                validation_id=validation_id,
                workflow_id=workflow_id,
                validation_type=validation_type,
                timestamp=time.time(),
                is_valid=False,
                errors=[{"type": "validation_error", "message": error_msg}],
                warnings=[],
                recommendations=[],
                confidence_score=0.0,
                validation_duration=validation_duration,
                items_validated=len(prompts),
                success=False,
                error_message=error_msg,
            )

            # Update metrics
            self.validation_count += 1
            self.total_validation_time += validation_duration
            self.failed_validations += 1

            return result

    def process(self, input_data: Dict[str, Any]) -> ValidationResult:
        """
        Process validation request (synchronous wrapper).

        Args:
            input_data: Validation request data

        Returns:
            Validation result
        """
        # This is a synchronous wrapper for the async methods
        # In practice, this would be called from an async context
        raise NotImplementedError("Use async methods for validation operations")

    def initialize(self) -> None:
        """Initialize the component."""
        self._status = "initialized"
        logger.info(f"Initialized {self.name}")

    def shutdown(self) -> None:
        """Shutdown the component."""
        self._status = "shutdown"
        logger.info(f"Shutdown {self.name}")

    def configure(self, config: ConfigDict) -> None:
        """
        Configure the component with new settings.

        Args:
            config: Configuration dictionary
        """
        self._config.update(config)
        logger.info(f"Configured {self.name}")

    def validate_config(self, config: ConfigDict) -> bool:
        """
        Validate a configuration.

        Args:
            config: Configuration to validate

        Returns:
            True if valid, False otherwise
        """
        return isinstance(config, dict)

    def set_state(self, key: str, value: Any) -> None:
        """
        Set a state value.

        Args:
            key: State key
            value: State value
        """
        self._state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """
        Get a state value.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        return self._state.get(key, default)

    def clear_state(self, key: Optional[str] = None) -> None:
        """
        Clear state values.

        Args:
            key: Specific key to clear, or None to clear all
        """
        if key is None:
            self._state.clear()
        else:
            self._state.pop(key, None)

    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect component metrics.

        Returns:
            Dictionary containing metrics
        """
        return self.get_validation_metrics()

    def _initialize_validation_rules(self) -> Dict[str, Any]:
        """
        Initialize validation rules for different types of content.

        Returns:
            Dictionary containing validation rules
        """
        return {
            "code": {
                "syntax": {
                    "python": ["indentation", "brackets", "quotes"],
                    "javascript": ["semicolons", "brackets", "quotes"],
                },
                "style": {
                    "line_length": 120,
                    "function_length": 50,
                    "class_length": 200,
                },
                "best_practices": {
                    "naming_conventions": True,
                    "docstrings": True,
                    "type_hints": True,
                },
            },
            "prompts": {
                "completeness": {
                    "min_length": 10,
                    "required_elements": ["task", "context", "output_format"],
                },
                "quality": {
                    "clarity_score": 0.7,
                    "specificity_score": 0.8,
                },
                "clarity": {
                    "avoid_ambiguity": True,
                    "use_examples": True,
                },
            },
        }

    def _validate_syntax(
        self, code_content: str, file_path: str
    ) -> List[Dict[str, Any]]:
        """
        Validate code syntax.

        Args:
            code_content: Code content to validate
            file_path: File path for context

        Returns:
            List of syntax errors
        """
        errors = []

        # Basic syntax validation
        if not code_content.strip():
            errors.append(
                {
                    "type": "syntax_error",
                    "message": "Empty code content",
                    "file": file_path,
                    "line": 0,
                    "column": 0,
                }
            )
            return errors

        # Check for basic Python syntax issues
        if file_path.endswith(".py"):
            # Check for unmatched brackets
            if code_content.count("(") != code_content.count(")"):
                errors.append(
                    {
                        "type": "syntax_error",
                        "message": "Unmatched parentheses",
                        "file": file_path,
                        "line": 0,
                        "column": 0,
                    }
                )

            if code_content.count("[") != code_content.count("]"):
                errors.append(
                    {
                        "type": "syntax_error",
                        "message": "Unmatched square brackets",
                        "file": file_path,
                        "line": 0,
                        "column": 0,
                    }
                )

            if code_content.count("{") != code_content.count("}"):
                errors.append(
                    {
                        "type": "syntax_error",
                        "message": "Unmatched curly braces",
                        "file": file_path,
                        "line": 0,
                        "column": 0,
                    }
                )

        return errors

    def _validate_style(
        self, code_content: str, file_path: str
    ) -> List[Dict[str, Any]]:
        """
        Validate code style.

        Args:
            code_content: Code content to validate
            file_path: File path for context

        Returns:
            List of style warnings
        """
        warnings = []

        # Check line length
        lines = code_content.split("\n")
        for i, line in enumerate(lines):
            if len(line) > 120:
                warnings.append(
                    {
                        "type": "style_warning",
                        "message": f"Line too long ({len(line)} characters)",
                        "file": file_path,
                        "line": i + 1,
                        "column": 0,
                    }
                )

        return warnings

    def _validate_best_practices(
        self, code_content: str, file_path: str
    ) -> List[Dict[str, Any]]:
        """
        Validate code best practices.

        Args:
            code_content: Code content to validate
            file_path: File path for context

        Returns:
            List of best practice warnings
        """
        warnings = []

        # Check for docstrings in functions and classes
        lines = code_content.split("\n")

        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped.startswith("def "):
                # Check if next non-empty line is a docstring
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if next_line:
                        if not next_line.startswith('"""') and not next_line.startswith(
                            "'''"
                        ):
                            warnings.append(
                                {
                                    "type": "best_practice_warning",
                                    "message": "Function missing docstring",
                                    "file": file_path,
                                    "line": i + 1,
                                    "column": 0,
                                }
                            )
                        break

            elif stripped.startswith("class "):
                # Check if next non-empty line is a docstring
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if next_line:
                        if not next_line.startswith('"""') and not next_line.startswith(
                            "'''"
                        ):
                            warnings.append(
                                {
                                    "type": "best_practice_warning",
                                    "message": "Class missing docstring",
                                    "file": file_path,
                                    "line": i + 1,
                                    "column": 0,
                                }
                            )
                        break

        return warnings

    def _validate_prompt_completeness(
        self, prompt: str, index: int
    ) -> List[Dict[str, Any]]:
        """
        Validate prompt completeness.

        Args:
            prompt: Prompt to validate
            index: Prompt index

        Returns:
            List of completeness errors
        """
        errors = []

        if len(prompt.strip()) < 10:
            errors.append(
                {
                    "type": "completeness_error",
                    "message": "Prompt too short",
                    "prompt_index": index,
                    "line": 0,
                    "column": 0,
                }
            )

        return errors

    def _validate_prompt_quality(self, prompt: str, index: int) -> List[Dict[str, Any]]:
        """
        Validate prompt quality.

        Args:
            prompt: Prompt to validate
            index: Prompt index

        Returns:
            List of quality warnings
        """
        warnings = []

        # Check for clarity indicators
        if "?" in prompt and len(prompt.split("?")) > 3:
            warnings.append(
                {
                    "type": "quality_warning",
                    "message": "Prompt may be too complex with multiple questions",
                    "prompt_index": index,
                    "line": 0,
                    "column": 0,
                }
            )

        return warnings

    def _validate_prompt_clarity(self, prompt: str, index: int) -> List[Dict[str, Any]]:
        """
        Validate prompt clarity.

        Args:
            prompt: Prompt to validate
            index: Prompt index

        Returns:
            List of clarity warnings
        """
        warnings = []

        # Check for ambiguous terms
        ambiguous_terms = ["it", "this", "that", "thing", "stuff"]
        for term in ambiguous_terms:
            if term in prompt.lower():
                warnings.append(
                    {
                        "type": "clarity_warning",
                        "message": f"Prompt contains ambiguous term: '{term}'",
                        "prompt_index": index,
                        "line": 0,
                        "column": 0,
                    }
                )

        return warnings

    def _generate_recommendations(
        self,
        code_content: str,
        errors: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Generate recommendations based on validation results.

        Args:
            code_content: Code content that was validated
            errors: List of errors found
            warnings: List of warnings found

        Returns:
            List of recommendations
        """
        recommendations = []

        if errors:
            recommendations.append("Fix syntax errors before proceeding")

        if warnings:
            recommendations.append(
                "Consider addressing style and best practice warnings"
            )

        if not code_content.strip():
            recommendations.append("Add meaningful code content")

        return recommendations

    def _generate_prompt_recommendations(
        self,
        prompts: List[str],
        errors: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Generate recommendations for prompts based on validation results.

        Args:
            prompts: List of prompts that were validated
            errors: List of errors found
            warnings: List of warnings found

        Returns:
            List of recommendations
        """
        recommendations = []

        if errors:
            recommendations.append("Fix completeness errors in prompts")

        if warnings:
            recommendations.append("Consider improving prompt quality and clarity")

        if len(prompts) == 0:
            recommendations.append("Add at least one prompt")

        return recommendations

    def _calculate_confidence(
        self, errors: List[Dict[str, Any]], warnings: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate confidence score based on validation results.

        Args:
            errors: List of errors found
            warnings: List of warnings found

        Returns:
            Confidence score (0.0-1.0)
        """
        if errors:
            return 0.0

        if warnings:
            return 0.7

        return 1.0

    def get_validation_metrics(self) -> Dict[str, Any]:
        """
        Get validation performance metrics.

        Returns:
            Dictionary containing validation metrics
        """
        return {
            "total_validations": self.validation_count,
            "successful_validations": self.successful_validations,
            "failed_validations": self.failed_validations,
            "success_rate": (
                (self.successful_validations / self.validation_count * 100)
                if self.validation_count > 0
                else 0.0
            ),
            "total_validation_time": self.total_validation_time,
            "average_validation_time": (
                (self.total_validation_time / self.validation_count)
                if self.validation_count > 0
                else 0.0
            ),
        }

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get the component's health status.

        Returns:
            Dictionary containing health status information
        """
        metrics = self.get_validation_metrics()

        return {
            "component_id": self.component_id,
            "name": self.name,
            "status": self.status,
            "healthy": self.check_health(),
            "validation_metrics": metrics,
            "processing_count": self.processing_count,
            "last_processed_at": self.last_processed_at,
        }

    def check_health(self) -> bool:
        """
        Check if the component is healthy.

        Returns:
            True if healthy, False otherwise
        """
        return (
            self.status != "error"
            and self.error_count == 0
            and self.failed_validations
            < self.successful_validations  # More successes than failures
        )
