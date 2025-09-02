# gemini_sre_agent/ml/code_generation_models.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class CodeQualityLevel(Enum):
    """Quality levels for generated code"""

    POOR = 1
    FAIR = 2
    GOOD = 3
    EXCELLENT = 4
    OUTSTANDING = 5


@dataclass
class ValidationIssue:
    """Represents a validation issue found in generated code"""

    issue_id: str
    severity: ValidationSeverity
    category: str
    message: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    file_path: Optional[str] = None
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of code validation"""

    is_valid: bool
    severity: ValidationSeverity
    issues: List[ValidationIssue] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    quality_score: float = 0.0
    validation_time: datetime = field(default_factory=datetime.now)

    def add_issue(self, issue: ValidationIssue):
        """Add a validation issue"""
        self.issues.append(issue)
        if issue.severity == ValidationSeverity.CRITICAL:
            self.is_valid = False

    def add_suggestion(self, suggestion: str):
        """Add a suggestion for improvement"""
        self.suggestions.append(suggestion)

    def get_critical_issues(self) -> List[ValidationIssue]:
        """Get all critical validation issues"""
        return [
            issue
            for issue in self.issues
            if issue.severity == ValidationSeverity.CRITICAL
        ]

    def get_high_priority_issues(self) -> List[ValidationIssue]:
        """Get all high and critical priority issues"""
        return [
            issue
            for issue in self.issues
            if issue.severity.value >= ValidationSeverity.HIGH.value
        ]


@dataclass
class CodeFix:
    """Represents a generated code fix"""

    code: str
    language: str
    file_path: str
    original_issue: str
    fix_description: str
    tests: Optional[str] = None
    documentation: Optional[str] = None
    validation_results: Optional[ValidationResult] = None
    generation_time: datetime = field(default_factory=datetime.now)
    iteration_count: int = 0
    quality_score: float = 0.0

    def __post_init__(self):
        """Post-initialization hook to set quality score if validation results are provided"""
        if self.validation_results:
            self.quality_score = self.validation_results.quality_score

    def add_validation_result(self, result: ValidationResult):
        """Add validation results to the code fix"""
        self.validation_results = result
        self.quality_score = result.quality_score

    def increment_iteration(self):
        """Increment the iteration count"""
        self.iteration_count += 1

    def is_high_quality(self) -> bool:
        """Check if the code fix meets high quality standards"""
        if not self.validation_results:
            return False
        return (
            self.validation_results.is_valid
            and self.quality_score >= 8.0
            and len(self.validation_results.get_high_priority_issues()) == 0
        )


@dataclass
class CodePattern:
    """Represents a code pattern for specific domains"""

    pattern_id: str
    name: str
    description: str
    domain: str
    pattern_type: str
    code_template: str
    validation_rules: List[str] = field(default_factory=list)
    best_practices: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

    def apply(self, code: str, context: Dict[str, Any]) -> str:
        """Apply the pattern to the given code"""
        # This is a simplified implementation
        # In practice, this would use more sophisticated pattern matching and replacement
        return code.replace("{{pattern_placeholder}}", self.code_template)


@dataclass
class ValidationRule:
    """Represents a validation rule for code generation"""

    rule_id: str
    name: str
    description: str
    domain: str
    rule_type: str
    severity: ValidationSeverity
    validation_function: str  # Name of the validation function
    parameters: Dict[str, Any] = field(default_factory=dict)

    def get_severity_value(self) -> int:
        """Get the numeric severity value"""
        return self.severity.value


@dataclass
class CodeGenerationContext:
    """Context specific to code generation tasks"""

    task_type: str = "code_generation"
    domain: str = "general"
    complexity_score: int = 5
    max_iterations: int = 3
    validation_level: str = "standard"
    quality_threshold: float = 7.0
    human_review_required: bool = False
    learning_enabled: bool = True

    def requires_strict_validation(self) -> bool:
        """Check if strict validation is required"""
        return self.validation_level == "strict"

    def should_escalate_to_human(self) -> bool:
        """Check if the issue should be escalated to human review"""
        return (
            self.complexity_score >= 8
            or self.human_review_required
            or self.domain == "security"
        )


@dataclass
class CodeGenerationResult:
    """Result of a code generation operation"""

    success: bool
    code_fix: Optional[CodeFix] = None
    validation_result: Optional[ValidationResult] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    generation_time_ms: int = 0
    iteration_count: int = 0
    quality_score: float = 0.0

    def is_high_quality(self) -> bool:
        """Check if the result meets high quality standards"""
        if not self.success or not self.code_fix:
            return False
        return self.code_fix.is_high_quality()

    def add_warning(self, warning: str):
        """Add a warning message"""
        self.warnings.append(warning)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the generation result"""
        return {
            "success": self.success,
            "quality_score": self.quality_score,
            "iteration_count": self.iteration_count,
            "validation_passed": (
                self.validation_result.is_valid if self.validation_result else False
            ),
            "critical_issues": (
                len(self.validation_result.get_critical_issues())
                if self.validation_result
                else 0
            ),
            "generation_time_ms": self.generation_time_ms,
            "warnings_count": len(self.warnings),
        }
