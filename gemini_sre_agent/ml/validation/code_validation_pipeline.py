# gemini_sre_agent/ml/validation/code_validation_pipeline.py

"""
Code validation pipeline for enhanced code generation.

This module provides comprehensive validation capabilities for generated code,
including syntax validation, pattern compliance, security review, and performance analysis.
"""

import ast
import logging
import re
from typing import Any, Dict, List, Optional

from .validation_models import (
    ValidationFeedback,
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
    ValidationType,
)


class CodeValidationPipeline:
    """Validates generated code before PR creation."""

    def __init__(self):
        """Initialize the validation pipeline."""
        self.logger = logging.getLogger(__name__)

        # Security patterns to check for
        self.security_patterns = {
            "sql_injection": [
                r"execute\s*\(\s*['\"].*%s.*['\"]",
                r"cursor\.execute\s*\(\s*['\"].*\+.*['\"]",
                r"query\s*=\s*['\"].*\+.*['\"]",
            ],
            "xss": [
                r"innerHTML\s*=",
                r"document\.write\s*\(",
                r"eval\s*\(",
            ],
            "path_traversal": [
                r"open\s*\(\s*['\"].*\.\./.*['\"]",
                r"file\s*\(\s*['\"].*\.\./.*['\"]",
            ],
            "hardcoded_secrets": [
                r"password\s*=\s*['\"][^'\"]+['\"]",
                r"api_key\s*=\s*['\"][^'\"]+['\"]",
                r"secret\s*=\s*['\"][^'\"]+['\"]",
            ],
        }

        # Performance anti-patterns
        self.performance_anti_patterns = {
            "n_plus_one": [
                r"for\s+\w+\s+in\s+\w+:\s*\n.*\.query\(",
                r"for\s+\w+\s+in\s+\w+:\s*\n.*\.get\(",
            ],
            "inefficient_loops": [
                r"for\s+\w+\s+in\s+range\s*\(\s*len\s*\(",
                r"while\s+True:",
            ],
            "memory_leaks": [
                r"global\s+\w+",
                r"\.append\s*\(\s*\[\s*\]\s*\)",
            ],
        }

        # Best practices patterns
        self.best_practices_patterns = {
            "error_handling": [
                r"try:",
                r"except\s+\w+:",
                r"finally:",
            ],
            "logging": [
                r"logging\.",
                r"logger\.",
            ],
            "type_hints": [
                r"def\s+\w+\s*\(\s*\w+:\s*\w+",
                r"->\s*\w+",
            ],
            "docstrings": [
                r'""".*"""',
                r"'''.*'''",
            ],
        }

    async def validate_code(
        self, code_result: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Multi-level validation of generated code.

        Args:
            code_result: Generated code result containing code_patch and metadata
            context: Additional context for validation

        Returns:
            ValidationResult with comprehensive validation details
        """
        try:
            self.logger.info("Starting code validation pipeline")

            # Extract code and metadata
            code_patch = code_result.get("code_patch", "")
            file_path = code_result.get("file_path", "unknown")
            generator_type = code_result.get("generator_type", "unknown")

            if not code_patch.strip():
                return self._create_empty_code_result()

            # Initialize validation result
            validation_result = ValidationResult(
                is_valid=True,
                overall_score=1.0,
                issues=[],
                feedback=[],
                validation_metadata={
                    "file_path": file_path,
                    "generator_type": generator_type,
                    "code_length": len(code_patch),
                },
            )

            # 1. Syntax validation
            syntax_result = await self._validate_syntax(code_patch, file_path)
            validation_result.issues.extend(syntax_result.issues)
            validation_result.syntax_valid = syntax_result.is_valid
            validation_result.syntax_score = syntax_result.overall_score

            # 2. Pattern compliance validation
            pattern_result = await self._validate_patterns(
                code_patch, generator_type, context
            )
            validation_result.issues.extend(pattern_result.issues)
            validation_result.pattern_compliant = pattern_result.is_valid
            validation_result.pattern_score = pattern_result.overall_score

            # 3. Security validation
            security_result = await self._security_review(code_patch, file_path)
            validation_result.issues.extend(security_result.issues)
            validation_result.security_valid = security_result.is_valid
            validation_result.security_score = security_result.overall_score

            # 4. Performance validation
            performance_result = await self._assess_performance_impact(
                code_patch, context
            )
            validation_result.issues.extend(performance_result.issues)
            validation_result.performance_valid = performance_result.is_valid
            validation_result.performance_score = performance_result.overall_score

            # 5. Best practices validation
            best_practices_result = await self._validate_best_practices(
                code_patch, context
            )
            validation_result.issues.extend(best_practices_result.issues)
            validation_result.feedback.extend(best_practices_result.feedback)

            # Calculate overall validation result
            validation_result.is_valid = all(
                [
                    validation_result.syntax_valid,
                    validation_result.pattern_compliant,
                    validation_result.security_valid,
                    validation_result.performance_valid,
                    not validation_result.has_critical_issues(),
                ]
            )

            # Calculate overall score
            validation_result.overall_score = (
                validation_result.syntax_score * 0.2
                + validation_result.pattern_score * 0.3
                + validation_result.security_score * 0.3
                + validation_result.performance_score * 0.2
            )

            # Apply penalty for critical issues
            if validation_result.has_critical_issues():
                validation_result.overall_score *= 0.5

            self.logger.info(
                f"Validation completed: valid={validation_result.is_valid}, "
                f"score={validation_result.overall_score:.2f}, "
                f"issues={len(validation_result.issues)}"
            )

            return validation_result

        except Exception as e:
            self.logger.error(f"Validation pipeline failed: {e}")
            return self._create_error_result(str(e))

    async def _validate_syntax(self, code: str, file_path: str) -> ValidationResult:
        """Validate Python syntax."""
        issues = []

        try:
            # Try to compile the code
            ast.parse(code)
            syntax_score = 1.0
        except SyntaxError as e:
            issues.append(
                ValidationIssue(
                    issue_id="syntax_error",
                    validation_type=ValidationType.SYNTAX,
                    level=ValidationLevel.ERROR,
                    message=f"Syntax error: {e.msg}",
                    description=f"Python syntax error at line {e.lineno}, column {e.offset}",
                    line_number=e.lineno,
                    column_number=e.offset,
                    file_path=file_path,
                    suggested_fix="Fix the syntax error according to Python grammar rules",
                )
            )
            syntax_score = 0.0
        except Exception as e:
            issues.append(
                ValidationIssue(
                    issue_id="syntax_parse_error",
                    validation_type=ValidationType.SYNTAX,
                    level=ValidationLevel.ERROR,
                    message=f"Code parsing failed: {str(e)}",
                    description="Unable to parse the generated code",
                    file_path=file_path,
                    suggested_fix="Check for malformed code or missing imports",
                )
            )
            syntax_score = 0.0

        return ValidationResult(
            is_valid=len(issues) == 0,
            overall_score=syntax_score,
            issues=issues,
            feedback=[],
            validation_metadata={"validation_type": "syntax"},
        )

    async def _validate_patterns(
        self, code: str, generator_type: str, context: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """Validate code against domain-specific patterns."""
        issues = []
        feedback = []

        # Check for TODO/FIXME comments
        if "TODO" in code or "FIXME" in code:
            issues.append(
                ValidationIssue(
                    issue_id="incomplete_implementation",
                    validation_type=ValidationType.PATTERN_COMPLIANCE,
                    level=ValidationLevel.WARNING,
                    message="Code contains TODO/FIXME comments",
                    description="Generated code contains placeholder comments indicating incomplete implementation",
                    suggested_fix="Complete the implementation or remove TODO/FIXME comments",
                )
            )

        # Check for print statements (should use logging)
        if "print(" in code and "logging" not in code:
            issues.append(
                ValidationIssue(
                    issue_id="print_statements",
                    validation_type=ValidationType.BEST_PRACTICES,
                    level=ValidationLevel.WARNING,
                    message="Code uses print statements instead of logging",
                    description="Print statements should be replaced with proper logging",
                    suggested_fix="Replace print() calls with logging statements",
                )
            )

        # Generator-specific pattern validation
        if generator_type == "api_error":
            await self._validate_api_patterns(code, issues, feedback)
        elif generator_type == "database_error":
            await self._validate_database_patterns(code, issues, feedback)
        elif generator_type == "security_error":
            await self._validate_security_patterns(code, issues, feedback)

        pattern_score = max(0.0, 1.0 - (len(issues) * 0.2))

        return ValidationResult(
            is_valid=len(issues) == 0,
            overall_score=pattern_score,
            issues=issues,
            feedback=feedback,
            validation_metadata={
                "validation_type": "pattern_compliance",
                "generator_type": generator_type,
            },
        )

    async def _security_review(self, code: str, file_path: str) -> ValidationResult:
        """Perform security review of generated code."""
        issues = []

        for security_type, patterns in self.security_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    issues.append(
                        ValidationIssue(
                            issue_id=f"security_{security_type}",
                            validation_type=ValidationType.SECURITY,
                            level=ValidationLevel.CRITICAL,
                            message=f"Potential {security_type.replace('_', ' ')} vulnerability",
                            description=f"Code pattern matches known {security_type} vulnerability pattern",
                            line_number=self._get_line_number(code, match.start()),
                            file_path=file_path,
                            suggested_fix=f"Review and fix potential {security_type} vulnerability",
                        )
                    )

        security_score = max(0.0, 1.0 - (len(issues) * 0.3))

        return ValidationResult(
            is_valid=len(issues) == 0,
            overall_score=security_score,
            issues=issues,
            feedback=[],
            validation_metadata={"validation_type": "security"},
        )

    async def _assess_performance_impact(
        self, code: str, context: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """Assess performance impact of generated code."""
        issues = []

        for perf_type, patterns in self.performance_anti_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    issues.append(
                        ValidationIssue(
                            issue_id=f"performance_{perf_type}",
                            validation_type=ValidationType.PERFORMANCE,
                            level=ValidationLevel.WARNING,
                            message=f"Potential {perf_type.replace('_', ' ')} issue",
                            description=f"Code pattern may cause {perf_type.replace('_', ' ')} problems",
                            line_number=self._get_line_number(code, match.start()),
                            suggested_fix=f"Optimize code to avoid {perf_type.replace('_', ' ')} issues",
                        )
                    )

        performance_score = max(0.0, 1.0 - (len(issues) * 0.15))

        return ValidationResult(
            is_valid=len(issues) == 0,
            overall_score=performance_score,
            issues=issues,
            feedback=[],
            validation_metadata={"validation_type": "performance"},
        )

    async def _validate_best_practices(
        self, code: str, context: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """Validate code against best practices."""
        issues = []
        feedback = []

        # Check for error handling
        if not any(
            re.search(pattern, code)
            for pattern in self.best_practices_patterns["error_handling"]
        ):
            feedback.append(
                ValidationFeedback(
                    feedback_id="error_handling_missing",
                    category="best_practices",
                    message="Consider adding error handling",
                    suggestion="Add try-except blocks for robust error handling",
                    priority=7,
                    examples=[
                        "try:\n    # risky operation\nexcept SpecificException as e:\n    # handle error"
                    ],
                )
            )

        # Check for logging
        if not any(
            re.search(pattern, code)
            for pattern in self.best_practices_patterns["logging"]
        ):
            feedback.append(
                ValidationFeedback(
                    feedback_id="logging_missing",
                    category="best_practices",
                    message="Consider adding logging",
                    suggestion="Add logging statements for better observability",
                    priority=6,
                    examples=[
                        "import logging\nlogger = logging.getLogger(__name__)\nlogger.info('Operation completed')"
                    ],
                )
            )

        # Check for type hints
        if not any(
            re.search(pattern, code)
            for pattern in self.best_practices_patterns["type_hints"]
        ):
            feedback.append(
                ValidationFeedback(
                    feedback_id="type_hints_missing",
                    category="best_practices",
                    message="Consider adding type hints",
                    suggestion="Add type hints for better code documentation and IDE support",
                    priority=5,
                    examples=[
                        "def function(param: str) -> int:\n    return len(param)"
                    ],
                )
            )

        return ValidationResult(
            is_valid=True,  # Best practices are suggestions, not errors
            overall_score=1.0,
            issues=issues,
            feedback=feedback,
            validation_metadata={"validation_type": "best_practices"},
        )

    async def _validate_api_patterns(
        self,
        code: str,
        issues: List[ValidationIssue],
        feedback: List[ValidationFeedback],
    ):
        """Validate API-specific patterns."""
        # Check for authentication
        if "auth" not in code.lower() and "token" not in code.lower():
            feedback.append(
                ValidationFeedback(
                    feedback_id="api_auth_missing",
                    category="api_security",
                    message="Consider adding authentication",
                    suggestion="Add proper authentication mechanisms for API endpoints",
                    priority=8,
                )
            )

        # Check for input validation
        if "validate" not in code.lower() and "schema" not in code.lower():
            feedback.append(
                ValidationFeedback(
                    feedback_id="api_validation_missing",
                    category="api_security",
                    message="Consider adding input validation",
                    suggestion="Add input validation to prevent malformed requests",
                    priority=7,
                )
            )

    async def _validate_database_patterns(
        self,
        code: str,
        issues: List[ValidationIssue],
        feedback: List[ValidationFeedback],
    ):
        """Validate database-specific patterns."""
        # Check for connection handling
        if "connection" in code.lower() and "close" not in code.lower():
            issues.append(
                ValidationIssue(
                    issue_id="db_connection_not_closed",
                    validation_type=ValidationType.PATTERN_COMPLIANCE,
                    level=ValidationLevel.WARNING,
                    message="Database connection may not be properly closed",
                    description="Code opens database connection but doesn't ensure it's closed",
                    suggested_fix="Use context managers or ensure connections are closed",
                )
            )

    async def _validate_security_patterns(
        self,
        code: str,
        issues: List[ValidationIssue],
        feedback: List[ValidationFeedback],
    ):
        """Validate security-specific patterns."""
        # Check for input sanitization
        if (
            "input" in code.lower()
            and "sanitize" not in code.lower()
            and "escape" not in code.lower()
        ):
            feedback.append(
                ValidationFeedback(
                    feedback_id="input_sanitization_missing",
                    category="security",
                    message="Consider adding input sanitization",
                    suggestion="Sanitize user inputs to prevent injection attacks",
                    priority=9,
                )
            )

    def _get_line_number(self, code: str, position: int) -> int:
        """Get line number from character position."""
        return code[:position].count("\n") + 1

    def _create_empty_code_result(self) -> ValidationResult:
        """Create validation result for empty code."""
        return ValidationResult(
            is_valid=False,
            overall_score=0.0,
            issues=[
                ValidationIssue(
                    issue_id="empty_code",
                    validation_type=ValidationType.SYNTAX,
                    level=ValidationLevel.ERROR,
                    message="Generated code is empty",
                    description="No code was generated",
                    suggested_fix="Generate actual code implementation",
                )
            ],
            feedback=[],
            validation_metadata={"validation_type": "empty_code"},
        )

    def _create_error_result(self, error_message: str) -> ValidationResult:
        """Create validation result for validation errors."""
        return ValidationResult(
            is_valid=False,
            overall_score=0.0,
            issues=[
                ValidationIssue(
                    issue_id="validation_error",
                    validation_type=ValidationType.SYNTAX,
                    level=ValidationLevel.ERROR,
                    message=f"Validation failed: {error_message}",
                    description="Code validation pipeline encountered an error",
                    suggested_fix="Review the generated code and validation process",
                )
            ],
            feedback=[],
            validation_metadata={
                "validation_type": "validation_error",
                "error": error_message,
            },
        )
