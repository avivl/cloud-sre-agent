# gemini_sre_agent/ml/validation/validation_models.py

"""
Validation models for code validation pipeline.

This module defines the data models used for code validation,
including validation results, issues, and feedback.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ValidationLevel(Enum):
    """Validation severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationType(Enum):
    """Types of validation checks."""

    SYNTAX = "syntax"
    PATTERN_COMPLIANCE = "pattern_compliance"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BEST_PRACTICES = "best_practices"
    TESTING = "testing"
    DOCUMENTATION = "documentation"


@dataclass
class ValidationIssue:
    """Represents a validation issue found in generated code."""

    issue_id: str
    validation_type: ValidationType
    level: ValidationLevel
    message: str
    description: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    file_path: Optional[str] = None
    suggested_fix: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ValidationFeedback:
    """Feedback for code improvement."""

    feedback_id: str
    category: str
    message: str
    suggestion: str
    priority: int  # 1-10, higher is more important
    examples: Optional[List[str]] = None
    references: Optional[List[str]] = None


@dataclass
class ValidationResult:
    """Result of code validation."""

    is_valid: bool
    overall_score: float  # 0.0 to 1.0
    issues: List[ValidationIssue]
    feedback: List[ValidationFeedback]
    validation_metadata: Dict[str, Any]

    # Validation type results
    syntax_valid: bool = True
    pattern_compliant: bool = True
    security_valid: bool = True
    performance_valid: bool = True

    # Detailed scores
    syntax_score: float = 1.0
    pattern_score: float = 1.0
    security_score: float = 1.0
    performance_score: float = 1.0

    def get_issues_by_level(self, level: ValidationLevel) -> List[ValidationIssue]:
        """Get issues filtered by severity level."""
        return [issue for issue in self.issues if issue.level == level]

    def get_issues_by_type(
        self, validation_type: ValidationType
    ) -> List[ValidationIssue]:
        """Get issues filtered by validation type."""
        return [
            issue for issue in self.issues if issue.validation_type == validation_type
        ]

    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return len(self.get_issues_by_level(ValidationLevel.CRITICAL)) > 0

    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.get_issues_by_level(ValidationLevel.ERROR)) > 0

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get a summary of validation results."""
        return {
            "is_valid": self.is_valid,
            "overall_score": self.overall_score,
            "total_issues": len(self.issues),
            "critical_issues": len(self.get_issues_by_level(ValidationLevel.CRITICAL)),
            "errors": len(self.get_issues_by_level(ValidationLevel.ERROR)),
            "warnings": len(self.get_issues_by_level(ValidationLevel.WARNING)),
            "info": len(self.get_issues_by_level(ValidationLevel.INFO)),
            "scores": {
                "syntax": self.syntax_score,
                "pattern": self.pattern_score,
                "security": self.security_score,
                "performance": self.performance_score,
            },
            "validation_types": {
                "syntax_valid": self.syntax_valid,
                "pattern_compliant": self.pattern_compliant,
                "security_valid": self.security_valid,
                "performance_valid": self.performance_valid,
            },
        }
