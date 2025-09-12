# gemini_sre_agent/core/exceptions/base.py

"""
Base exception hierarchy for the Gemini SRE Agent system.

This module defines the core exception classes that form the foundation
of the error handling system across all components.
"""

from typing import Any, Dict, Optional


class GeminiSREAgentError(Exception):
    """
    Base exception class for all Gemini SRE Agent errors.

    This is the root exception class that all other exceptions in the system
    should inherit from. It provides common functionality for error handling
    and logging.

    Attributes:
        message: The error message describing what went wrong
        error_code: Optional error code for programmatic error handling
        details: Optional dictionary containing additional error details
        original_error: Optional reference to the original exception that caused this error
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """
        Initialize the base exception.

        Args:
            message: Human-readable error message
            error_code: Optional error code for programmatic handling
            details: Optional additional error details
            original_error: Optional original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error

    def __str__(self) -> str:
        """Return string representation of the exception."""
        base_msg = f"{self.__class__.__name__}: {self.message}"
        if self.error_code:
            base_msg += f" (Code: {self.error_code})"
        return base_msg

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for serialization.

        Returns:
            Dictionary representation of the exception
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
            "original_error": str(self.original_error) if self.original_error else None,
        }


class ConfigurationError(GeminiSREAgentError):
    """
    Exception raised for configuration-related errors.

    This exception is raised when there are issues with configuration
    files, environment variables, or configuration validation.
    """

    pass


class ValidationError(GeminiSREAgentError):
    """
    Exception raised for data validation errors.

    This exception is raised when input data fails validation checks
    or when data format is incorrect.
    """

    pass


class ServiceError(GeminiSREAgentError):
    """
    Exception raised for service-related errors.

    This exception is raised when there are issues with external services,
    API calls, or service availability.
    """

    pass


class ProcessingError(GeminiSREAgentError):
    """
    Exception raised for data processing errors.

    This exception is raised when there are issues during data processing,
    analysis, or transformation operations.
    """

    pass


class AgentError(GeminiSREAgentError):
    """
    Exception raised for agent-related errors.

    This exception is raised when there are issues with agent operations,
    such as prompt processing, response generation, or agent coordination.
    """

    pass


class LLMError(GeminiSREAgentError):
    """
    Exception raised for LLM-related errors.

    This exception is raised when there are issues with LLM providers,
    API calls, model responses, or LLM configuration.
    """

    pass


class MonitoringError(GeminiSREAgentError):
    """
    Exception raised for monitoring-related errors.

    This exception is raised when there are issues with monitoring systems,
    metrics collection, or alerting.
    """

    pass


class ResilienceError(GeminiSREAgentError):
    """
    Exception raised for resilience-related errors.

    This exception is raised when there are issues with circuit breakers,
    retry mechanisms, or other resilience patterns.
    """

    pass
