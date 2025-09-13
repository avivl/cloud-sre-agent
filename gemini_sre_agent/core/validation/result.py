"""Validation result classes for the configuration validation system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidationSeverity(Enum):
    """Severity levels for validation errors."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationError:
    """Represents a single validation error."""

    message: str
    field: str | None = None
    value: Any | None = None
    severity: ValidationSeverity = ValidationSeverity.ERROR
    rule_name: str | None = None
    context: dict[str, Any] = field(default_factory=dict)  # type: ignore
    suggestions: list[str] = field(default_factory=list)  # type: ignore

    def to_dict(self) -> dict[str, Any]:
        """Convert the error to a dictionary.

        Returns:
            Dictionary representation of the error
        """
        return {
            "message": self.message,
            "field": self.field,
            "value": self.value,
            "severity": self.severity.value,
            "rule_name": self.rule_name,
            "context": self.context,
            "suggestions": self.suggestions,
        }


@dataclass
class ValidationResult:
    """Container for validation results."""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    info: list[ValidationError] = field(default_factory=list)
    validation_time_ms: float = 0.0
    schema_version: str | None = None
    environment: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_error(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        rule_name: str | None = None,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Add an error to the result.

        Args:
            message: Error message
            field: Field that caused the error
            value: Value that caused the error
            rule_name: Name of the rule that failed
            context: Additional context
            suggestions: Suggested fixes
        """
        error = ValidationError(
            message=message,
            field=field,
            value=value,
            severity=ValidationSeverity.ERROR,
            rule_name=rule_name,
            context=context or {},
            suggestions=suggestions or [],
        )
        self.errors.append(error)
        self.is_valid = False

    def add_warning(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        rule_name: str | None = None,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Add a warning to the result.

        Args:
            message: Warning message
            field: Field that caused the warning
            value: Value that caused the warning
            rule_name: Name of the rule that generated the warning
            context: Additional context
            suggestions: Suggested fixes
        """
        warning = ValidationError(
            message=message,
            field=field,
            value=value,
            severity=ValidationSeverity.WARNING,
            rule_name=rule_name,
            context=context or {},
            suggestions=suggestions or [],
        )
        self.warnings.append(warning)

    def add_info(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        rule_name: str | None = None,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Add an info message to the result.

        Args:
            message: Info message
            field: Field related to the info
            value: Value related to the info
            rule_name: Name of the rule that generated the info
            context: Additional context
            suggestions: Additional suggestions
        """
        info = ValidationError(
            message=message,
            field=field,
            value=value,
            severity=ValidationSeverity.INFO,
            rule_name=rule_name,
            context=context or {},
            suggestions=suggestions or [],
        )
        self.info.append(info)

    def get_errors_by_field(self, field: str) -> list[ValidationError]:
        """Get all errors for a specific field.

        Args:
            field: Field name

        Returns:
            List of errors for the field
        """
        return [error for error in self.errors if error.field == field]

    def get_errors_by_severity(
        self, severity: ValidationSeverity
    ) -> list[ValidationError]:
        """Get all errors by severity level.

        Args:
            severity: Severity level

        Returns:
            List of errors with the specified severity
        """
        return [error for error in self.errors if error.severity == severity]

    def get_errors_by_rule(self, rule_name: str) -> list[ValidationError]:
        """Get all errors from a specific rule.

        Args:
            rule_name: Rule name

        Returns:
            List of errors from the rule
        """
        return [error for error in self.errors if error.rule_name == rule_name]

    def has_errors(self) -> bool:
        """Check if there are any errors.

        Returns:
            True if there are errors, False otherwise
        """
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if there are any warnings.

        Returns:
            True if there are warnings, False otherwise
        """
        return len(self.warnings) > 0

    def has_critical_errors(self) -> bool:
        """Check if there are any critical errors.

        Returns:
            True if there are critical errors, False otherwise
        """
        return any(
            error.severity == ValidationSeverity.CRITICAL for error in self.errors
        )

    def get_error_summary(self) -> dict[str, int]:
        """Get a summary of errors by severity.

        Returns:
            Dictionary with error counts by severity
        """
        summary = {}
        for severity in ValidationSeverity:
            count = len(self.get_errors_by_severity(severity))
            if count > 0:
                summary[severity.value] = count
        return summary

    def format_errors(
        self, include_warnings: bool = True, include_info: bool = False
    ) -> str:
        """Format errors as a human-readable string.

        Args:
            include_warnings: Whether to include warnings
            include_info: Whether to include info messages

        Returns:
            Formatted error string
        """
        lines = []

        if self.errors:
            lines.append("Errors:")
            for error in self.errors:
                field_info = f" (field: {error.field})" if error.field else ""
                lines.append(f"  - {error.message}{field_info}")
                if error.suggestions:
                    for suggestion in error.suggestions:
                        lines.append(f"    Suggestion: {suggestion}")

        if include_warnings and self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                field_info = f" (field: {warning.field})" if warning.field else ""
                lines.append(f"  - {warning.message}{field_info}")
                if warning.suggestions:
                    for suggestion in warning.suggestions:
                        lines.append(f"    Suggestion: {suggestion}")

        if include_info and self.info:
            lines.append("Info:")
            for info in self.info:
                field_info = f" (field: {info.field})" if info.field else ""
                lines.append(f"  - {info.message}{field_info}")
                if info.suggestions:
                    for suggestion in info.suggestions:
                        lines.append(f"    Suggestion: {suggestion}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert the result to a dictionary.

        Returns:
            Dictionary representation of the result
        """
        return {
            "is_valid": self.is_valid,
            "errors": [error.to_dict() for error in self.errors],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "info": [info.to_dict() for info in self.info],
            "validation_time_ms": self.validation_time_ms,
            "schema_version": self.schema_version,
            "environment": self.environment,
            "metadata": self.metadata,
            "summary": self.get_error_summary(),
        }

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge another validation result into this one.

        Args:
            other: Other validation result to merge

        Returns:
            New merged validation result
        """
        merged = ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
            info=self.info + other.info,
            validation_time_ms=self.validation_time_ms + other.validation_time_ms,
            schema_version=self.schema_version or other.schema_version,
            environment=self.environment or other.environment,
            metadata={**self.metadata, **other.metadata},
        )
        return merged
