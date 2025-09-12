"""Validation rules for the configuration validation system."""

import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type, Union

from pydantic import BaseModel, ValidationError as PydanticValidationError

from .exceptions import (
    ValidationRuleError,
    SchemaValidationError,
    CrossFieldValidationError,
    EnvironmentValidationError
)
from .result import ValidationResult, ValidationError


class ValidationRule(ABC):
    """Base class for validation rules."""
    
    def __init__(self, name: str, description: Optional[str] = None):
        """Initialize the validation rule.
        
        Args:
            name: Name of the rule
            description: Optional description of the rule
        """
        self.name = name
        self.description = description or f"Validation rule: {name}"
    
    @abstractmethod
    def validate(self, data: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate the data.
        
        Args:
            data: Data to validate
            context: Optional validation context
            
        Returns:
            Validation result
        """
        pass
    
    def __str__(self) -> str:
        """String representation of the rule.
        
        Returns:
            String representation
        """
        return f"{self.name}: {self.description}"


class SchemaValidator(ValidationRule):
    """Validator for Pydantic schema validation."""
    
    def __init__(
        self,
        schema_class: Type[BaseModel],
        name: Optional[str] = None,
        strict: bool = True
    ):
        """Initialize the schema validator.
        
        Args:
            schema_class: Pydantic model class to validate against
            name: Optional name for the validator
            strict: Whether to use strict validation
        """
        self.schema_class = schema_class
        self.strict = strict
        super().__init__(
            name or f"SchemaValidator({schema_class.__name__})",
            f"Validates data against {schema_class.__name__} schema"
        )
    
    def validate(self, data: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate data against the schema.
        
        Args:
            data: Data to validate
            context: Optional validation context
            
        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)
        
        try:
            if self.strict:
                self.schema_class.model_validate(data)
            else:
                self.schema_class.model_validate(data, strict=False)
        except PydanticValidationError as e:
            result.is_valid = False
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                message = error["msg"]
                error_type = error["type"]
                
                result.add_error(
                    message=f"{message} (type: {error_type})",
                    field=field,
                    value=error.get("input"),
                    rule_name=self.name,
                    context={"error_type": error_type, "schema": self.schema_class.__name__}
                )
        except Exception as e:
            result.is_valid = False
            result.add_error(
                message=f"Schema validation failed: {str(e)}",
                rule_name=self.name,
                context={"exception": str(e), "schema": self.schema_class.__name__}
            )
        
        return result


class CrossFieldValidator(ValidationRule):
    """Validator for cross-field validation logic."""
    
    def __init__(
        self,
        validation_func: Callable[[Any, Optional[Dict[str, Any]]], ValidationResult],
        name: Optional[str] = None,
        fields: Optional[List[str]] = None
    ):
        """Initialize the cross-field validator.
        
        Args:
            validation_func: Function that performs cross-field validation
            name: Optional name for the validator
            fields: List of fields involved in the validation
        """
        self.validation_func = validation_func
        self.fields = fields or []
        super().__init__(
            name or "CrossFieldValidator",
            f"Validates relationships between fields: {', '.join(self.fields)}"
        )
    
    def validate(self, data: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate cross-field relationships.
        
        Args:
            data: Data to validate
            context: Optional validation context
            
        Returns:
            Validation result
        """
        try:
            return self.validation_func(data, context)
        except Exception as e:
            result = ValidationResult(is_valid=False)
            result.add_error(
                message=f"Cross-field validation failed: {str(e)}",
                rule_name=self.name,
                context={"exception": str(e), "fields": self.fields}
            )
            return result


class EnvironmentValidator(ValidationRule):
    """Validator for environment-specific validation."""
    
    def __init__(
        self,
        environment: str,
        required_fields: Optional[List[str]] = None,
        forbidden_fields: Optional[List[str]] = None,
        field_constraints: Optional[Dict[str, Dict[str, Any]]] = None,
        name: Optional[str] = None
    ):
        """Initialize the environment validator.
        
        Args:
            environment: Target environment
            required_fields: Fields required for this environment
            forbidden_fields: Fields forbidden for this environment
            field_constraints: Field-specific constraints
            name: Optional name for the validator
        """
        self.environment = environment
        self.required_fields = required_fields or []
        self.forbidden_fields = forbidden_fields or []
        self.field_constraints = field_constraints or {}
        super().__init__(
            name or f"EnvironmentValidator({environment})",
            f"Validates configuration for {environment} environment"
        )
    
    def validate(self, data: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate environment-specific requirements.
        
        Args:
            data: Data to validate
            context: Optional validation context
            
        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)
        
        # Check if data is a dictionary
        if not isinstance(data, dict):
            result.add_error(
                message="Environment validation requires dictionary data",
                rule_name=self.name
            )
            return result
        
        # Check required fields
        for field in self.required_fields:
            if field not in data or data[field] is None:
                result.add_error(
                    message=f"Field '{field}' is required for {self.environment} environment",
                    field=field,
                    rule_name=self.name,
                    suggestions=[f"Add '{field}' to your configuration"]
                )
        
        # Check forbidden fields
        for field in self.forbidden_fields:
            if field in data and data[field] is not None:
                result.add_error(
                    message=f"Field '{field}' is not allowed in {self.environment} environment",
                    field=field,
                    value=data[field],
                    rule_name=self.name,
                    suggestions=[f"Remove '{field}' from your configuration"]
                )
        
        # Check field constraints
        for field, constraints in self.field_constraints.items():
            if field in data:
                value = data[field]
                for constraint_name, constraint_value in constraints.items():
                    if not self._check_constraint(field, value, constraint_name, constraint_value):
                        result.add_error(
                            message=f"Field '{field}' violates {constraint_name} constraint: {constraint_value}",
                            field=field,
                            value=value,
                            rule_name=self.name
                        )
        
        return result
    
    def _check_constraint(
        self,
        field: str,
        value: Any,
        constraint_name: str,
        constraint_value: Any
    ) -> bool:
        """Check a field constraint.
        
        Args:
            field: Field name
            value: Field value
            constraint_name: Name of the constraint
            constraint_value: Constraint value
            
        Returns:
            True if constraint is satisfied, False otherwise
        """
        if constraint_name == "min_length" and isinstance(value, (str, list)):
            return len(value) >= constraint_value
        elif constraint_name == "max_length" and isinstance(value, (str, list)):
            return len(value) <= constraint_value
        elif constraint_name == "min_value" and isinstance(value, (int, float)):
            return value >= constraint_value
        elif constraint_name == "max_value" and isinstance(value, (int, float)):
            return value <= constraint_value
        elif constraint_name == "pattern" and isinstance(value, str):
            import re
            return bool(re.match(constraint_value, value))
        elif constraint_name == "choices" and isinstance(constraint_value, list):
            return value in constraint_value
        elif constraint_name == "type" and isinstance(value, constraint_value):
            return True
        
        return True  # Unknown constraint, assume valid


class CustomValidator(ValidationRule):
    """Validator for custom validation logic."""
    
    def __init__(
        self,
        validation_func: Callable[[Any, Optional[Dict[str, Any]]], bool],
        error_message: str,
        name: Optional[str] = None,
        field: Optional[str] = None
    ):
        """Initialize the custom validator.
        
        Args:
            validation_func: Function that returns True if validation passes
            error_message: Error message if validation fails
            name: Optional name for the validator
            field: Optional field name for the validation
        """
        self.validation_func = validation_func
        self.error_message = error_message
        self.field = field
        super().__init__(
            name or "CustomValidator",
            f"Custom validation: {error_message}"
        )
    
    def validate(self, data: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate using custom logic.
        
        Args:
            data: Data to validate
            context: Optional validation context
            
        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)
        
        try:
            if not self.validation_func(data, context):
                result.add_error(
                    message=self.error_message,
                    field=self.field,
                    rule_name=self.name
                )
        except Exception as e:
            result.add_error(
                message=f"Custom validation failed: {str(e)}",
                field=self.field,
                rule_name=self.name,
                context={"exception": str(e)}
            )
        
        return result


class CompositeValidator(ValidationRule):
    """Validator that combines multiple validation rules."""
    
    def __init__(
        self,
        validators: List[ValidationRule],
        name: Optional[str] = None,
        stop_on_first_error: bool = False
    ):
        """Initialize the composite validator.
        
        Args:
            validators: List of validators to combine
            name: Optional name for the validator
            stop_on_first_error: Whether to stop on first error
        """
        self.validators = validators
        self.stop_on_first_error = stop_on_first_error
        super().__init__(
            name or "CompositeValidator",
            f"Combines {len(validators)} validation rules"
        )
    
    def validate(self, data: Any, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate using all validators.
        
        Args:
            data: Data to validate
            context: Optional validation context
            
        Returns:
            Combined validation result
        """
        result = ValidationResult(is_valid=True)
        
        for validator in self.validators:
            try:
                validator_result = validator.validate(data, context)
                result = result.merge(validator_result)
                
                if self.stop_on_first_error and not result.is_valid:
                    break
            except Exception as e:
                result.add_error(
                    message=f"Validator '{validator.name}' failed: {str(e)}",
                    rule_name=self.name,
                    context={"validator": validator.name, "exception": str(e)}
                )
                if self.stop_on_first_error:
                    break
        
        return result
