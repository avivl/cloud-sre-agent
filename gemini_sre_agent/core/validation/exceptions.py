"""Exceptions for the configuration validation system."""

from typing import Any, Dict, List, Optional


class ValidationError(Exception):
    """Base exception for validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None):
        """Initialize the validation error.
        
        Args:
            message: Error message
            field: Field that caused the error
            value: Value that caused the error
        """
        self.message = message
        self.field = field
        self.value = value
        super().__init__(message)


class ValidationRuleError(ValidationError):
    """Raised when a validation rule fails."""
    
    def __init__(
        self,
        rule_name: str,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Initialize the validation rule error.
        
        Args:
            rule_name: Name of the rule that failed
            message: Error message
            field: Field that caused the error
            value: Value that caused the error
            context: Additional context for the error
        """
        self.rule_name = rule_name
        self.context = context or {}
        super().__init__(message, field, value)


class SchemaValidationError(ValidationError):
    """Raised when schema validation fails."""
    
    def __init__(
        self,
        schema_name: str,
        errors: List[Dict[str, Any]],
        field: Optional[str] = None,
        value: Optional[Any] = None
    ):
        """Initialize the schema validation error.
        
        Args:
            schema_name: Name of the schema that failed
            errors: List of validation errors from Pydantic
            field: Field that caused the error
            value: Value that caused the error
        """
        self.schema_name = schema_name
        self.errors = errors
        super().__init__(f"Schema validation failed for {schema_name}", field, value)


class CrossFieldValidationError(ValidationError):
    """Raised when cross-field validation fails."""
    
    def __init__(
        self,
        fields: List[str],
        message: str,
        values: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Initialize the cross-field validation error.
        
        Args:
            fields: List of fields involved in the validation
            message: Error message
            values: Values of the fields that caused the error
            context: Additional context for the error
        """
        self.fields = fields
        self.values = values or {}
        self.context = context or {}
        super().__init__(message)


class EnvironmentValidationError(ValidationError):
    """Raised when environment-specific validation fails."""
    
    def __init__(
        self,
        environment: str,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        required_for_env: Optional[List[str]] = None
    ):
        """Initialize the environment validation error.
        
        Args:
            environment: Environment that failed validation
            message: Error message
            field: Field that caused the error
            value: Value that caused the error
            required_for_env: List of environments where this field is required
        """
        self.environment = environment
        self.required_for_env = required_for_env or []
        super().__init__(message, field, value)


class ValidationTimeoutError(ValidationError):
    """Raised when validation times out."""
    
    def __init__(self, timeout_seconds: float, message: Optional[str] = None):
        """Initialize the validation timeout error.
        
        Args:
            timeout_seconds: Timeout in seconds
            message: Optional custom error message
        """
        self.timeout_seconds = timeout_seconds
        if message is None:
            message = f"Validation timed out after {timeout_seconds} seconds"
        super().__init__(message)


class ValidationDependencyError(ValidationError):
    """Raised when a validation dependency is missing."""
    
    def __init__(
        self,
        dependency: str,
        message: Optional[str] = None,
        field: Optional[str] = None
    ):
        """Initialize the validation dependency error.
        
        Args:
            dependency: Name of the missing dependency
            message: Optional custom error message
            field: Field that requires the dependency
        """
        self.dependency = dependency
        if message is None:
            message = f"Validation dependency '{dependency}' is missing"
        super().__init__(message, field)


class ValidationCacheError(ValidationError):
    """Raised when validation caching fails."""
    
    def __init__(
        self,
        cache_key: str,
        message: Optional[str] = None,
        operation: Optional[str] = None
    ):
        """Initialize the validation cache error.
        
        Args:
            cache_key: Cache key that failed
            message: Optional custom error message
            operation: Operation that failed (get, set, delete)
        """
        self.cache_key = cache_key
        self.operation = operation
        if message is None:
            message = f"Validation cache {operation or 'operation'} failed for key '{cache_key}'"
        super().__init__(message)
