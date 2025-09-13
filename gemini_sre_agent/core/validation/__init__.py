"""Configuration validation system for the Gemini SRE Agent.

This module provides a comprehensive configuration validation framework that supports:
- Schema-based validation using Pydantic models
- Custom validation rules and constraints
- Cross-field validation and dependencies
- Environment-specific validation
- Validation result reporting with detailed error messages
- Validation caching and performance optimization
- Integration with the dependency injection system

The main components are:
- ValidationEngine: Core validation orchestrator
- ValidationRule: Interface for custom validation rules
- ValidationResult: Container for validation results and errors
- SchemaValidator: Pydantic-based schema validation
- CrossFieldValidator: For complex cross-field validations
- EnvironmentValidator: Environment-specific validation logic

Example usage:
    from gemini_sre_agent.core.validation import ValidationEngine, SchemaValidator

    # Create validation engine
    engine = ValidationEngine()

    # Add validators
    engine.add_validator(SchemaValidator(MyConfigModel))
    engine.add_validator(CrossFieldValidator(validate_dependencies))

    # Validate configuration
    result = engine.validate(config_data)
    if not result.is_valid:
        print(f"Validation failed: {result.errors}")
"""

from .engine import ValidationEngine
from .exceptions import (
    CrossFieldValidationError,
    EnvironmentValidationError,
    SchemaValidationError,
    ValidationError,
    ValidationRuleError,
)
from .result import ValidationError as ValidationErrorDetail
from .result import ValidationResult
from .rules import (
    CrossFieldValidator,
    CustomValidator,
    EnvironmentValidator,
    SchemaValidator,
    ValidationRule,
)
from .schema import (
    BaseValidationSchema,
    ConfigValidationSchema,
    LLMValidationSchema,
    ServiceValidationSchema,
)

__all__ = [
    # Engine
    "ValidationEngine",
    # Exceptions
    "ValidationError",
    "ValidationRuleError",
    "SchemaValidationError",
    "CrossFieldValidationError",
    "EnvironmentValidationError",
    # Result
    "ValidationResult",
    "ValidationErrorDetail",
    # Rules
    "ValidationRule",
    "SchemaValidator",
    "CrossFieldValidator",
    "EnvironmentValidator",
    "CustomValidator",
    # Schemas
    "BaseValidationSchema",
    "ConfigValidationSchema",
    "ServiceValidationSchema",
    "LLMValidationSchema",
]
