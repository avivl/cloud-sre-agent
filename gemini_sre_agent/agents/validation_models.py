"""
Comprehensive validation models and utilities for agent data validation.

This module provides enhanced validation logic, custom validators, and validation
utilities for agent-specific data validation patterns including confidence scores,
severity levels, and comprehensive error reporting.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar, Generic
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, ValidationError as PydanticValidationError
from pydantic.validators import str_validator

# ============================================================================
# Validation Error Models
# ============================================================================


class ValidationError(BaseModel):
    """Standardized error reporting for validation failures."""

    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Error message")
    value: Optional[Any] = Field(None, description="Value that caused the error")
    code: Optional[str] = Field(
        None, description="Error code for programmatic handling"
    )
    severity: str = Field("error", description="Severity of the validation error")
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context for the error"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Error timestamp"
    )

    class Config:
        frozen = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class ValidationWarning(BaseModel):
    """Warning for validation issues that don't prevent processing."""

    field: str = Field(..., description="Field with validation warning")
    message: str = Field(..., description="Warning message")
    value: Optional[Any] = Field(None, description="Value that caused the warning")
    code: Optional[str] = Field(None, description="Warning code")
    suggestion: Optional[str] = Field(None, description="Suggested fix")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Warning timestamp"
    )

    class Config:
        frozen = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class ValidationResult(BaseModel):
    """Comprehensive validation result with errors and warnings."""

    is_valid: bool = Field(..., description="Whether validation passed")
    errors: List[ValidationError] = Field(
        default_factory=list, description="Validation errors"
    )
    warnings: List[ValidationWarning] = Field(
        default_factory=list, description="Validation warnings"
    )
    validated_data: Optional[Dict[str, Any]] = Field(
        None, description="Validated and cleaned data"
    )
    validation_time_ms: float = Field(
        ..., description="Time taken for validation in milliseconds"
    )
    validator_used: Optional[str] = Field(
        None, description="Validator that was used"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Validation metadata"
    )

    class Config:
        frozen = True
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============================================================================
# Validation Severity Levels
# ============================================================================


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""

    CRITICAL = "critical"  # Prevents processing
    ERROR = "error"  # Prevents processing
    WARNING = "warning"  # Allows processing with warning
    INFO = "info"  # Informational only


# ============================================================================
# Custom Validators
# ============================================================================


def validate_confidence_score(value: float) -> float:
    """Validate confidence score is between 0.0 and 1.0."""
    if not isinstance(value, (int, float)):
        raise ValueError("Confidence score must be a number")
    if value < 0.0 or value > 1.0:
        raise ValueError("Confidence score must be between 0.0 and 1.0")
    return float(value)


def validate_confidence_threshold(value: float, threshold: float = 0.3) -> float:
    """Validate confidence score meets minimum threshold."""
    validated_value = validate_confidence_score(value)
    if validated_value < threshold:
        raise ValueError(f"Confidence score {validated_value} below threshold {threshold}")
    return validated_value


def validate_severity_level(value: str) -> str:
    """Validate severity level is one of the allowed values."""
    allowed_values = ["critical", "high", "medium", "low", "info"]
    if value.lower() not in allowed_values:
        raise ValueError(f"Severity level must be one of: {', '.join(allowed_values)}")
    return value.lower()


def validate_positive_number(value: Union[int, float]) -> Union[int, float]:
    """Validate that a number is positive."""
    if value < 0:
        raise ValueError("Number must be positive")
    return value


def validate_non_empty_string(value: str) -> str:
    """Validate that a string is not empty."""
    if not value or not value.strip():
        raise ValueError("String cannot be empty")
    return value.strip()


def validate_uuid_format(value: str) -> str:
    """Validate that a string is a valid UUID format."""
    try:
        uuid4(value)
        return value
    except ValueError:
        raise ValueError("Invalid UUID format")


def validate_timestamp(value: Union[str, datetime]) -> datetime:
    """Validate and convert timestamp to datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError("Invalid timestamp format")
    raise ValueError("Timestamp must be a string or datetime object")


def validate_enum_value(value: Any, enum_class: type) -> Any:
    """Validate that a value is a valid enum member."""
    if not isinstance(value, enum_class):
        if isinstance(value, str):
            try:
                return enum_class(value)
            except ValueError:
                raise ValueError(f"Invalid {enum_class.__name__} value: {value}")
        else:
            raise ValueError(f"Value must be a {enum_class.__name__} or string")
    return value


# ============================================================================
# Validation Schemas
# ============================================================================


class MetricValidationSchema(BaseModel):
    """Validation schema for metrics data."""

    name: str = Field(..., description="Metric name")
    value: Union[int, float] = Field(..., description="Metric value")
    unit: Optional[str] = Field(None, description="Metric unit")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Metric timestamp"
    )
    tags: Dict[str, str] = Field(
        default_factory=dict, description="Metric tags"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        return validate_non_empty_string(v)

    @field_validator("value")
    @classmethod
    def validate_value(cls, v):
        return validate_positive_number(v)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v):
        return validate_timestamp(v)


class LogValidationSchema(BaseModel):
    """Validation schema for log data."""

    level: str = Field(..., description="Log level")
    message: str = Field(..., description="Log message")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Log timestamp"
    )
    source: Optional[str] = Field(None, description="Log source")
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Log context"
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v):
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Log level must be one of: {', '.join(allowed_levels)}")
        return v.upper()

    @field_validator("message")
    @classmethod
    def validate_message(cls, v):
        return validate_non_empty_string(v)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v):
        return validate_timestamp(v)


class CodeAnalysisValidationSchema(BaseModel):
    """Validation schema for code analysis results."""

    file_path: str = Field(..., description="File path")
    line_number: int = Field(..., ge=1, description="Line number")
    issue_type: str = Field(..., description="Issue type")
    severity: str = Field(..., description="Issue severity")
    message: str = Field(..., description="Issue message")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    rule_id: Optional[str] = Field(None, description="Rule identifier")

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v):
        return validate_non_empty_string(v)

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v):
        return validate_severity_level(v)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v):
        return validate_confidence_score(v)

    @field_validator("message")
    @classmethod
    def validate_message(cls, v):
        return validate_non_empty_string(v)


# ============================================================================
# Validation Decorators
# ============================================================================


def validate_with_schema(schema_class: type) -> Callable:
    """Decorator to validate function arguments with a Pydantic schema."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                # Validate kwargs with the schema
                validated_data = schema_class(**kwargs)
                return func(*args, **validated_data.model_dump())
            except PydanticValidationError as e:
                raise ValueError(f"Validation failed: {e}")
        return wrapper
    return decorator


def validate_confidence(func: Callable) -> Callable:
    """Decorator to validate confidence parameters."""
    def wrapper(*args, **kwargs):
        if 'confidence' in kwargs:
            kwargs['confidence'] = validate_confidence_score(kwargs['confidence'])
        return func(*args, **kwargs)
    return wrapper


def validate_severity(func: Callable) -> Callable:
    """Decorator to validate severity parameters."""
    def wrapper(*args, **kwargs):
        if 'severity' in kwargs:
            kwargs['severity'] = validate_severity_level(kwargs['severity'])
        return func(*args, **kwargs)
    return wrapper


# ============================================================================
# Validation Utilities
# ============================================================================


class ValidationUtils:
    """Utility class for common validation operations."""

    @staticmethod
    def validate_agent_response_data(data: Dict[str, Any]) -> ValidationResult:
        """Validate agent response data structure."""
        errors = []
        warnings = []
        start_time = datetime.now(timezone.utc)

        # Required fields validation
        required_fields = ["agent_id", "agent_type", "status"]
        for field in required_fields:
            if field not in data:
                errors.append(ValidationError(
                    field=field,
                    message=f"Required field '{field}' is missing",
                    severity=ValidationSeverity.ERROR
                ))

        # Confidence score validation
        if "confidence" in data:
            try:
                validate_confidence_score(data["confidence"])
            except ValueError as e:
                errors.append(ValidationError(
                    field="confidence",
                    message=str(e),
                    value=data["confidence"],
                    severity=ValidationSeverity.ERROR
                ))

        # Severity level validation
        if "severity" in data:
            try:
                validate_severity_level(data["severity"])
            except ValueError as e:
                errors.append(ValidationError(
                    field="severity",
                    message=str(e),
                    value=data["severity"],
                    severity=ValidationSeverity.ERROR
                ))

        # Timestamp validation
        if "timestamp" in data:
            try:
                validate_timestamp(data["timestamp"])
            except ValueError as e:
                errors.append(ValidationError(
                    field="timestamp",
                    message=str(e),
                    value=data["timestamp"],
                    severity=ValidationSeverity.ERROR
                ))

        # Calculate validation time
        end_time = datetime.now(timezone.utc)
        validation_time_ms = (end_time - start_time).total_seconds() * 1000

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validated_data=data if len(errors) == 0 else None,
            validation_time_ms=validation_time_ms,
            validator_used="agent_response_validator"
        )

    @staticmethod
    def validate_workflow_data(data: Dict[str, Any]) -> ValidationResult:
        """Validate workflow data structure."""
        errors = []
        warnings = []
        start_time = datetime.now(timezone.utc)

        # Required fields validation
        required_fields = ["workflow_id", "workflow_name", "workflow_type"]
        for field in required_fields:
            if field not in data:
                errors.append(ValidationError(
                    field=field,
                    message=f"Required field '{field}' is missing",
                    severity=ValidationSeverity.ERROR
                ))

        # Steps validation
        if "steps" in data:
            if not isinstance(data["steps"], list):
                errors.append(ValidationError(
                    field="steps",
                    message="Steps must be a list",
                    value=data["steps"],
                    severity=ValidationSeverity.ERROR
                ))
            else:
                for i, step in enumerate(data["steps"]):
                    if not isinstance(step, dict):
                        errors.append(ValidationError(
                            field=f"steps[{i}]",
                            message="Step must be a dictionary",
                            value=step,
                            severity=ValidationSeverity.ERROR
                        ))
                    elif "step_id" not in step:
                        errors.append(ValidationError(
                            field=f"steps[{i}].step_id",
                            message="Step ID is required",
                            severity=ValidationSeverity.ERROR
                        ))

        # Calculate validation time
        end_time = datetime.now(timezone.utc)
        validation_time_ms = (end_time - start_time).total_seconds() * 1000

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validated_data=data if len(errors) == 0 else None,
            validation_time_ms=validation_time_ms,
            validator_used="workflow_validator"
        )

    @staticmethod
    def aggregate_validation_results(results: List[ValidationResult]) -> ValidationResult:
        """Aggregate multiple validation results into one."""
        all_errors = []
        all_warnings = []
        total_time = 0.0
        validators_used = []

        for result in results:
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
            total_time += result.validation_time_ms
            if result.validator_used:
                validators_used.append(result.validator_used)

        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            validated_data=None,  # Cannot aggregate validated data
            validation_time_ms=total_time,
            validator_used=", ".join(validators_used) if validators_used else None
        )

    @staticmethod
    def create_validation_error(
        field: str,
        message: str,
        value: Any = None,
        code: str = None,
        severity: str = "error"
    ) -> ValidationError:
        """Create a validation error with standard format."""
        return ValidationError(
            field=field,
            message=message,
            value=value,
            code=code,
            severity=severity
        )

    @staticmethod
    def create_validation_warning(
        field: str,
        message: str,
        value: Any = None,
        code: str = None,
        suggestion: str = None
    ) -> ValidationWarning:
        """Create a validation warning with standard format."""
        return ValidationWarning(
            field=field,
            message=message,
            value=value,
            code=code,
            suggestion=suggestion
        )


# ============================================================================
# Validation Registry
# ============================================================================


class ValidationRegistry:
    """Registry for validation functions and schemas."""

    _validators: Dict[str, Callable] = {}
    _schemas: Dict[str, type] = {}

    @classmethod
    def register_validator(cls, name: str, validator: Callable) -> None:
        """Register a validation function."""
        cls._validators[name] = validator

    @classmethod
    def register_schema(cls, name: str, schema: type) -> None:
        """Register a validation schema."""
        cls._schemas[name] = schema

    @classmethod
    def get_validator(cls, name: str) -> Optional[Callable]:
        """Get a registered validator."""
        return cls._validators.get(name)

    @classmethod
    def get_schema(cls, name: str) -> Optional[type]:
        """Get a registered schema."""
        return cls._schemas.get(name)

    @classmethod
    def list_validators(cls) -> List[str]:
        """List all registered validators."""
        return list(cls._validators.keys())

    @classmethod
    def list_schemas(cls) -> List[str]:
        """List all registered schemas."""
        return list(cls._schemas.keys())


# Register default validators and schemas
ValidationRegistry.register_validator("confidence_score", validate_confidence_score)
ValidationRegistry.register_validator("severity_level", validate_severity_level)
ValidationRegistry.register_validator("positive_number", validate_positive_number)
ValidationRegistry.register_validator("non_empty_string", validate_non_empty_string)
ValidationRegistry.register_validator("uuid_format", validate_uuid_format)
ValidationRegistry.register_validator("timestamp", validate_timestamp)

ValidationRegistry.register_schema("metric", MetricValidationSchema)
ValidationRegistry.register_schema("log", LogValidationSchema)
ValidationRegistry.register_schema("code_analysis", CodeAnalysisValidationSchema)
