# gemini_sre_agent/core/quality/exceptions.py
"""
Quality gate exceptions.

This module defines custom exceptions for the quality gate system.
"""



class QualityGateError(Exception):
    """Base exception for quality gate errors."""

    def __init__(self, message: str, details: dict | None = None):
        """Initialize the quality gate error.
        
        Args:
            message: Error message.
            details: Additional error details.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(QualityGateError):
    """Exception raised when validation fails."""

    def __init__(self, message: str, validation_type: str, details: dict | None = None):
        """Initialize the validation error.
        
        Args:
            message: Error message.
            validation_type: Type of validation that failed.
            details: Additional error details.
        """
        super().__init__(message, details)
        self.validation_type = validation_type


class QualityGateFailureError(QualityGateError):
    """Exception raised when a quality gate fails."""

    def __init__(self, gate_name: str, message: str, details: dict | None = None):
        """Initialize the quality gate failure error.
        
        Args:
            gate_name: Name of the failed gate.
            message: Error message.
            details: Additional error details.
        """
        super().__init__(f"Quality gate '{gate_name}' failed: {message}", details)
        self.gate_name = gate_name


class ConfigurationError(QualityGateError):
    """Exception raised when configuration is invalid."""

    def __init__(self, message: str, config_key: str | None = None, details: dict | None = None):
        """Initialize the configuration error.
        
        Args:
            message: Error message.
            config_key: Configuration key that caused the error.
            details: Additional error details.
        """
        super().__init__(message, details)
        self.config_key = config_key


class ToolExecutionError(QualityGateError):
    """Exception raised when a quality tool execution fails."""

    def __init__(
        self, 
        tool_name: str, 
        message: str, 
        exit_code: int | None = None, 
        details: dict | None = None
    ):
        """Initialize the tool execution error.
        
        Args:
            tool_name: Name of the tool that failed.
            message: Error message.
            exit_code: Exit code from the tool.
            details: Additional error details.
        """
        super().__init__(f"Tool '{tool_name}' execution failed: {message}", details)
        self.tool_name = tool_name
        self.exit_code = exit_code


class ReportGenerationError(QualityGateError):
    """Exception raised when report generation fails."""

    def __init__(self, message: str, report_type: str | None = None, details: dict | None = None):
        """Initialize the report generation error.
        
        Args:
            message: Error message.
            report_type: Type of report that failed to generate.
            details: Additional error details.
        """
        super().__init__(message, details)
        self.report_type = report_type
