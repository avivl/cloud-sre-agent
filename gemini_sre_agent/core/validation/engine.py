"""Validation engine for the configuration validation system."""

import time
from typing import Any, Dict, List, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from .exceptions import ValidationTimeoutError, ValidationDependencyError
from .result import ValidationResult
from .rules import ValidationRule, CompositeValidator


class ValidationEngine:
    """Main validation engine that orchestrates validation rules."""
    
    def __init__(
        self,
        max_workers: int = 4,
        timeout_seconds: Optional[float] = None,
        enable_caching: bool = True
    ):
        """Initialize the validation engine.
        
        Args:
            max_workers: Maximum number of worker threads for parallel validation
            timeout_seconds: Timeout for validation operations
            enable_caching: Whether to enable validation result caching
        """
        self.max_workers = max_workers
        self.timeout_seconds = timeout_seconds
        self.enable_caching = enable_caching
        
        self._validators: List[ValidationRule] = []
        self._cache: Dict[str, ValidationResult] = {}
        self._cache_lock = Lock()
        self._dependencies: Dict[str, List[str]] = {}
    
    def add_validator(self, validator: ValidationRule) -> None:
        """Add a validation rule to the engine.
        
        Args:
            validator: Validation rule to add
        """
        self._validators.append(validator)
    
    def add_validators(self, validators: List[ValidationRule]) -> None:
        """Add multiple validation rules to the engine.
        
        Args:
            validators: List of validation rules to add
        """
        self._validators.extend(validators)
    
    def remove_validator(self, name: str) -> bool:
        """Remove a validation rule by name.
        
        Args:
            name: Name of the validator to remove
            
        Returns:
            True if removed, False if not found
        """
        for i, validator in enumerate(self._validators):
            if validator.name == name:
                del self._validators[i]
                return True
        return False
    
    def get_validator(self, name: str) -> Optional[ValidationRule]:
        """Get a validation rule by name.
        
        Args:
            name: Name of the validator
            
        Returns:
            Validation rule or None if not found
        """
        for validator in self._validators:
            if validator.name == name:
                return validator
        return None
    
    def list_validators(self) -> List[str]:
        """Get list of validator names.
        
        Returns:
            List of validator names
        """
        return [validator.name for validator in self._validators]
    
    def add_dependency(self, validator_name: str, depends_on: List[str]) -> None:
        """Add a dependency for a validator.
        
        Args:
            validator_name: Name of the validator
            depends_on: List of validator names this validator depends on
        """
        self._dependencies[validator_name] = depends_on
    
    def validate(
        self,
        data: Any,
        context: Optional[Dict[str, Any]] = None,
        validators: Optional[List[str]] = None,
        parallel: bool = True
    ) -> ValidationResult:
        """Validate data using registered validators.
        
        Args:
            data: Data to validate
            context: Optional validation context
            validators: Optional list of validator names to use
            parallel: Whether to run validators in parallel
            
        Returns:
            Validation result
        """
        start_time = time.time()
        
        # Get validators to use
        validators_to_use = self._get_validators_to_use(validators)
        
        # Check dependencies
        self._check_dependencies(validators_to_use)
        
        # Check cache if enabled
        cache_key = None
        if self.enable_caching:
            cache_key = self._generate_cache_key(data, context, validators)
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                return cached_result
        
        # Create composite validator
        composite = CompositeValidator(validators_to_use, stop_on_first_error=False)
        
        # Run validation
        if parallel and len(validators_to_use) > 1:
            result = self._validate_parallel(composite, data, context)
        else:
            result = self._validate_sequential(composite, data, context)
        
        # Set timing
        result.validation_time_ms = (time.time() - start_time) * 1000
        
        # Cache result if enabled
        if self.enable_caching and cache_key is not None:
            self._cache_result(cache_key, result)
        
        return result
    
    def validate_field(
        self,
        data: Any,
        field: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate a specific field.
        
        Args:
            data: Data to validate
            field: Field name to validate
            context: Optional validation context
            
        Returns:
            Validation result
        """
        # Extract field value
        field_value = self._extract_field_value(data, field)
        
        # Create field-specific context
        field_context = (context or {}).copy()
        field_context["field"] = field
        field_context["field_value"] = field_value
        
        # Run validation
        return self.validate(data, field_context)
    
    def clear_cache(self) -> None:
        """Clear the validation cache."""
        with self._cache_lock:
            self._cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._cache_lock:
            return {
                "cache_size": len(self._cache),
                "cache_enabled": self.enable_caching,
                "max_workers": self.max_workers,
                "timeout_seconds": self.timeout_seconds
            }
    
    def _get_validators_to_use(self, validator_names: Optional[List[str]]) -> List[ValidationRule]:
        """Get validators to use for validation.
        
        Args:
            validator_names: Optional list of validator names
            
        Returns:
            List of validators to use
        """
        if validator_names is None:
            return self._validators
        
        validators = []
        for name in validator_names:
            validator = self.get_validator(name)
            if validator is not None:
                validators.append(validator)
        
        return validators
    
    def _check_dependencies(self, validators: List[ValidationRule]) -> None:
        """Check that all dependencies are satisfied.
        
        Args:
            validators: List of validators to check
            
        Args:
            ValidationDependencyError: If dependencies are not satisfied
        """
        validator_names = {validator.name for validator in validators}
        
        for validator in validators:
            if validator.name in self._dependencies:
                for dependency in self._dependencies[validator.name]:
                    if dependency not in validator_names:
                        raise ValidationDependencyError(
                            dependency,
                            f"Validator '{validator.name}' depends on '{dependency}' which is not available"
                        )
    
    def _validate_parallel(
        self,
        composite: CompositeValidator,
        data: Any,
        context: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """Run validation in parallel.
        
        Args:
            composite: Composite validator
            data: Data to validate
            context: Optional validation context
            
        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit validation tasks
            future_to_validator = {
                executor.submit(validator.validate, data, context): validator
                for validator in composite.validators
            }
            
            # Collect results
            for future in as_completed(future_to_validator, timeout=self.timeout_seconds):
                validator = future_to_validator[future]
                try:
                    validator_result = future.result()
                    result = result.merge(validator_result)
                except Exception as e:
                    result.add_error(
                        message=f"Validator '{validator.name}' failed: {str(e)}",
                        rule_name=validator.name,
                        context={"exception": str(e)}
                    )
        
        return result
    
    def _validate_sequential(
        self,
        composite: CompositeValidator,
        data: Any,
        context: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """Run validation sequentially.
        
        Args:
            composite: Composite validator
            data: Data to validate
            context: Optional validation context
            
        Returns:
            Validation result
        """
        return composite.validate(data, context)
    
    def _extract_field_value(self, data: Any, field: str) -> Any:
        """Extract field value from data.
        
        Args:
            data: Data to extract from
            field: Field name (supports dot notation)
            
        Returns:
            Field value or None if not found
        """
        if not isinstance(data, dict):
            return None
        
        # Handle dot notation
        keys = field.split(".")
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    def _generate_cache_key(
        self,
        data: Any,
        context: Optional[Dict[str, Any]],
        validators: Optional[List[str]]
    ) -> str:
        """Generate cache key for validation result.
        
        Args:
            data: Data to validate
            context: Optional validation context
            validators: Optional list of validator names
            
        Returns:
            Cache key
        """
        import hashlib
        import json
        
        # Create hashable representation
        cache_data = {
            "data": data,
            "context": context or {},
            "validators": validators or [v.name for v in self._validators]
        }
        
        # Generate hash
        cache_str = json.dumps(cache_data, sort_keys=True, default=str)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[ValidationResult]:
        """Get cached validation result.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached result or None
        """
        if not self.enable_caching:
            return None
        
        with self._cache_lock:
            return self._cache.get(cache_key)
    
    def _cache_result(self, cache_key: str, result: ValidationResult) -> None:
        """Cache validation result.
        
        Args:
            cache_key: Cache key
            result: Validation result to cache
        """
        if not self.enable_caching:
            return
        
        with self._cache_lock:
            self._cache[cache_key] = result
