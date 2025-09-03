# gemini_sre_agent/config/errors.py

"""
Enhanced error handling and reporting for configuration management.
"""

from typing import Any, Dict, List, Optional


class ConfigError(Exception):
    """Base configuration error."""

    def __init__(
        self,
        message: str,
        config_file: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        self.message = message
        self.config_file = config_file
        self.original_error = original_error
        super().__init__(self.message)

    def __str__(self) -> str:
        base_msg = self.message
        if self.config_file:
            base_msg = f"{base_msg} (file: {self.config_file})"
        if self.original_error:
            base_msg = f"{base_msg} - Original error: {self.original_error}"
        return base_msg


class ConfigValidationError(ConfigError):
    """Configuration validation error with enhanced formatting."""

    def __init__(
        self,
        message: str,
        errors: List[Dict[str, Any]],
        config_file: Optional[str] = None,
    ):
        self.message = message
        self.errors = errors
        self.config_file = config_file
        super().__init__(self.message, config_file)

    def format_errors(self) -> str:
        """Format validation errors for display with enhanced context."""
        formatted = [
            f"Configuration validation failed in {self.config_file or 'unknown file'}:"
        ]

        for i, error in enumerate(self.errors, 1):
            field = " → ".join(str(loc) for loc in error["loc"])
            formatted.append(f"  ❌ {i}. {field}: {error['msg']}")

            # Add input context if available
            if "input" in error:
                input_value = error["input"]
                if isinstance(input_value, str) and len(input_value) > 50:
                    input_value = input_value[:47] + "..."
                formatted.append(f"     Input: {input_value}")

            # Add type context if available
            if "type" in error:
                formatted.append(f"     Expected type: {error['type']}")

        return "\n".join(formatted)

    def get_summary(self) -> str:
        """Get a summary of validation errors."""
        error_count = len(self.errors)
        if error_count == 1:
            return "1 validation error found"
        else:
            return f"{error_count} validation errors found"


class ConfigFileError(ConfigError):
    """Configuration file related errors."""

    pass


class ConfigEnvironmentError(ConfigError):
    """Environment variable related errors."""

    pass


class ConfigSchemaError(ConfigError):
    """Configuration schema related errors."""

    pass
