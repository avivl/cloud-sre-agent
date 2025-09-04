"""
Provider Validation Framework.

This module provides comprehensive validation tools to verify that provider
implementations are correct and complete.
"""

import inspect
import logging
from typing import Any, Dict, List, Type

from ..base import LLMProvider
from ..config import LLMProviderConfig

logger = logging.getLogger(__name__)


class ProviderValidator:
    """
    Comprehensive validator for provider implementations.

    Validates that provider classes are correctly implemented and meet
    all requirements for the provider framework.
    """

    def __init__(self):
        self.validation_rules = {
            "inheritance": self._validate_inheritance,
            "abstract_methods": self._validate_abstract_methods,
            "constructor": self._validate_constructor,
            "config_validation": self._validate_config_validation,
            "method_signatures": self._validate_method_signatures,
            "error_handling": self._validate_error_handling,
            "documentation": self._validate_documentation,
        }

    def validate_provider_class(self, provider_class: Type[LLMProvider]) -> List[str]:
        """
        Validate a provider class implementation.

        Args:
            provider_class: The provider class to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        for rule_name, validator_func in self.validation_rules.items():
            try:
                rule_errors = validator_func(provider_class)
                errors.extend(rule_errors)
            except Exception as e:
                errors.append(f"Validation rule '{rule_name}' failed: {e}")

        return errors

    def _validate_inheritance(self, provider_class: Type[LLMProvider]) -> List[str]:
        """Validate that the class properly inherits from LLMProvider."""
        errors = []

        if not issubclass(provider_class, LLMProvider):
            errors.append("Provider class must inherit from LLMProvider")

        if provider_class == LLMProvider:
            errors.append("Provider class cannot be the abstract base class itself")

        return errors

    def _validate_abstract_methods(
        self, provider_class: Type[LLMProvider]
    ) -> List[str]:
        """Validate that all abstract methods are implemented."""
        errors = []

        # Get all abstract methods from LLMProvider
        abstract_methods = set()
        for base in LLMProvider.__mro__:
            for name, method in base.__dict__.items():
                if getattr(method, "__isabstractmethod__", False):
                    abstract_methods.add(name)

        # Check if all abstract methods are implemented
        for method_name in abstract_methods:
            if not hasattr(provider_class, method_name):
                errors.append(
                    f"Missing implementation of abstract method: {method_name}"
                )
            else:
                method = getattr(provider_class, method_name)
                if getattr(method, "__isabstractmethod__", False):
                    errors.append(f"Abstract method {method_name} is not implemented")

        return errors

    def _validate_constructor(self, provider_class: Type[LLMProvider]) -> List[str]:
        """Validate the constructor signature and implementation."""
        errors = []

        # Check constructor signature
        init_method = getattr(provider_class, "__init__", None)
        if not init_method:
            errors.append("Provider class must have an __init__ method")
            return errors

        # Get constructor signature
        sig = inspect.signature(init_method)
        params = list(sig.parameters.keys())

        # Should have 'self' and 'config' parameters
        if len(params) < 2:
            errors.append("Constructor must accept 'config' parameter")
        elif params[1] != "config":
            errors.append("Constructor's first parameter must be 'config'")

        # Check if config parameter has proper type annotation
        config_param = sig.parameters.get("config")
        if config_param and config_param.annotation != inspect.Parameter.empty:
            if not (
                config_param.annotation == LLMProviderConfig
                or str(config_param.annotation).endswith("LLMProviderConfig")
            ):
                errors.append("Config parameter should be typed as LLMProviderConfig")

        return errors

    def _validate_config_validation(
        self, provider_class: Type[LLMProvider]
    ) -> List[str]:
        """Validate that config validation is implemented."""
        errors = []

        # Check if validate_config class method exists
        if not hasattr(provider_class, "validate_config"):
            errors.append("Provider class must implement validate_config class method")
        else:
            validate_method = provider_class.validate_config

            # Check if it's a class method
            if not isinstance(validate_method, classmethod):
                errors.append("validate_config must be a class method")

            # Check signature
            sig = inspect.signature(validate_method.__func__)
            params = list(sig.parameters.keys())

            if len(params) < 2:
                errors.append("validate_config must accept 'config' parameter")
            elif params[1] != "config":
                errors.append("validate_config's first parameter must be 'config'")

        return errors

    def _validate_method_signatures(
        self, provider_class: Type[LLMProvider]
    ) -> List[str]:
        """Validate method signatures match the interface."""
        errors = []

        # Define expected method signatures
        expected_signatures = {
            "generate": ["self", "request"],
            "generate_stream": ["self", "request"],
            "health_check": ["self"],
            "supports_streaming": ["self"],
            "supports_tools": ["self"],
            "get_available_models": ["self"],
            "embeddings": ["self", "text"],
            "token_count": ["self", "text"],
            "cost_estimate": ["self", "input_tokens", "output_tokens"],
        }

        for method_name, expected_params in expected_signatures.items():
            if hasattr(provider_class, method_name):
                method = getattr(provider_class, method_name)
                sig = inspect.signature(method)
                actual_params = list(sig.parameters.keys())

                if actual_params != expected_params:
                    errors.append(
                        f"Method {method_name} has incorrect signature. "
                        f"Expected {expected_params}, got {actual_params}"
                    )

        return errors

    def _validate_error_handling(self, provider_class: Type[LLMProvider]) -> List[str]:
        """Validate that proper error handling is implemented."""
        errors = []

        # Check if the class has proper error handling in key methods
        key_methods = ["generate", "health_check"]

        for method_name in key_methods:
            if hasattr(provider_class, method_name):
                method = getattr(provider_class, method_name)
                source = inspect.getsource(method)

                # Check for basic error handling patterns
                if "try:" not in source and "except" not in source:
                    errors.append(f"Method {method_name} should include error handling")

        return errors

    def _validate_documentation(self, provider_class: Type[LLMProvider]) -> List[str]:
        """Validate that the class has proper documentation."""
        errors = []

        # Check class docstring
        if not provider_class.__doc__:
            errors.append("Provider class should have a docstring")
        elif len(provider_class.__doc__.strip()) < 20:
            errors.append("Provider class docstring should be more descriptive")

        # Check key method docstrings
        key_methods = [
            "generate",
            "health_check",
            "supports_streaming",
            "supports_tools",
        ]

        for method_name in key_methods:
            if hasattr(provider_class, method_name):
                method = getattr(provider_class, method_name)
                if not method.__doc__:
                    errors.append(f"Method {method_name} should have a docstring")

        return errors

    def validate_provider_instance(self, provider: LLMProvider) -> List[str]:
        """
        Validate a provider instance.

        Args:
            provider: The provider instance to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Test basic functionality
        try:
            # Test health check
            import asyncio

            if asyncio.iscoroutinefunction(provider.health_check):
                # This would need to be run in an async context
                pass
            else:
                health_result = provider.health_check()
                if not isinstance(health_result, bool):
                    errors.append("health_check should return a boolean")
        except Exception as e:
            errors.append(f"health_check failed: {e}")

        # Test model mapping
        try:
            models = provider.get_available_models()
            if not isinstance(models, dict):
                errors.append("get_available_models should return a dictionary")
            elif not models:
                errors.append("get_available_models should return at least one model")
        except Exception as e:
            errors.append(f"get_available_models failed: {e}")

        # Test capability methods
        try:
            streaming = provider.supports_streaming()
            if not isinstance(streaming, bool):
                errors.append("supports_streaming should return a boolean")
        except Exception as e:
            errors.append(f"supports_streaming failed: {e}")

        try:
            tools = provider.supports_tools()
            if not isinstance(tools, bool):
                errors.append("supports_tools should return a boolean")
        except Exception as e:
            errors.append(f"supports_tools failed: {e}")

        return errors

    def validate_config(
        self, config: LLMProviderConfig, provider_class: Type[LLMProvider]
    ) -> List[str]:
        """
        Validate a configuration against a provider class.

        Args:
            config: The configuration to validate
            provider_class: The provider class to validate against

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        try:
            # Use the provider's own validation
            provider_class.validate_config(config)
        except Exception as e:
            errors.append(f"Config validation failed: {e}")

        # Additional validation checks
        if not config.api_key:
            errors.append("API key is required")

        if config.base_url and not str(config.base_url).startswith(
            ("http://", "https://")
        ):
            errors.append("Base URL must start with http:// or https://")

        if config.timeout and config.timeout <= 0:
            errors.append("Timeout must be positive")

        if config.max_retries and config.max_retries < 0:
            errors.append("Max retries must be non-negative")

        return errors

    def generate_validation_report(
        self, provider_class: Type[LLMProvider]
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive validation report.

        Args:
            provider_class: The provider class to validate

        Returns:
            Dictionary containing validation results and recommendations
        """
        errors = self.validate_provider_class(provider_class)

        report = {
            "provider_name": provider_class.__name__,
            "is_valid": len(errors) == 0,
            "errors": errors,
            "recommendations": [],
            "code_quality_score": 0,
        }

        # Calculate code quality score
        total_checks = len(self.validation_rules)
        passed_checks = total_checks - len(errors)
        report["code_quality_score"] = (passed_checks / total_checks) * 100

        # Generate recommendations
        if not errors:
            report["recommendations"].append(
                "Provider implementation is valid and ready for use"
            )
        else:
            report["recommendations"].append(
                "Fix the validation errors before using this provider"
            )

            if any("docstring" in error for error in errors):
                report["recommendations"].append("Add comprehensive documentation")

            if any("error_handling" in error for error in errors):
                report["recommendations"].append("Implement proper error handling")

        return report

    def validate_provider_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate a provider implementation file.

        Args:
            file_path: Path to the provider implementation file

        Returns:
            Dictionary containing validation results
        """
        import importlib.util

        try:
            # Load the module
            spec = importlib.util.spec_from_file_location("provider_module", file_path)
            if not spec or not spec.loader:
                return {"error": "Could not load module from file"}

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find provider classes
            provider_classes = []
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, LLMProvider) and obj != LLMProvider:
                    provider_classes.append(obj)

            if not provider_classes:
                return {"error": "No provider classes found in file"}

            # Validate each provider class
            results = {}
            for provider_class in provider_classes:
                results[provider_class.__name__] = self.generate_validation_report(
                    provider_class
                )

            return {
                "file_path": file_path,
                "providers": results,
                "total_providers": len(provider_classes),
            }

        except Exception as e:
            return {"error": f"Failed to validate file: {e}"}
