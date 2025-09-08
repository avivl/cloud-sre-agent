"""
Structured Logging System for LLM Operations.

This module provides structured logging capabilities using structlog for
comprehensive observability of LLM operations, including request/response
tracking, performance metrics, and error context.
"""

import logging
from contextvars import ContextVar
from typing import Any, Dict, Optional

try:
    import structlog

    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False
    structlog = None

from ..base import LLMRequest, LLMResponse

# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)

logger = logging.getLogger(__name__)


class StructuredLogger:
    """Structured logger for LLM operations with context tracking."""

    def __init__(self, name: str = __name__):
        """Initialize the structured logger."""
        self.name = name
        self._setup_structlog()

    def _setup_structlog(self):
        """Setup structlog configuration if available."""
        if not STRUCTLOG_AVAILABLE or structlog is None:
            logger.warning("structlog not available, falling back to standard logging")
            self.logger = logging.getLogger(self.name)
            return

        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        self.logger = structlog.get_logger(self.name)

    def _get_context(self) -> Dict[str, Any]:
        """Get current context variables."""
        context = {}
        if request_id_var.get():
            context["request_id"] = request_id_var.get()
        if session_id_var.get():
            context["session_id"] = session_id_var.get()
        if user_id_var.get():
            context["user_id"] = user_id_var.get()
        return context

    def _log_with_context(self, level: str, message: str, **kwargs):
        """Log with context variables."""
        context = self._get_context()
        context.update(kwargs)

        if STRUCTLOG_AVAILABLE:
            getattr(self.logger, level)(message, **context)
        else:
            # Fallback to standard logging
            log_message = f"{message} | Context: {context}"
            getattr(logger, level)(log_message)

    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self._log_with_context("info", message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self._log_with_context("warning", message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self._log_with_context("error", message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self._log_with_context("debug", message, **kwargs)


class LLMRequestLogger:
    """Specialized logger for LLM request/response tracking."""

    def __init__(self):
        """Initialize the LLM request logger."""
        self.structured_logger = StructuredLogger("llm_requests")

    def log_request_start(
        self, request: LLMRequest, provider: str, model: str, **kwargs
    ):
        """Log the start of an LLM request."""
        self.structured_logger.info(
            "LLM request started",
            provider=provider,
            model=model,
            model_type=str(request.model_type),
            prompt_length=len(request.prompt) if request.prompt else 0,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            **kwargs,
        )

    def log_request_success(
        self,
        request: LLMRequest,
        response: LLMResponse,
        provider: str,
        model: str,
        duration_ms: float,
        **kwargs,
    ):
        """Log successful LLM request completion."""
        self.structured_logger.info(
            "LLM request completed successfully",
            provider=provider,
            model=model,
            model_type=str(request.model_type),
            duration_ms=duration_ms,
            input_tokens=response.usage.get("input_tokens", 0) if response.usage else 0,
            output_tokens=(
                response.usage.get("output_tokens", 0) if response.usage else 0
            ),
            total_tokens=response.usage.get("total_tokens", 0) if response.usage else 0,
            response_length=len(response.content) if response.content else 0,
            **kwargs,
        )

    def log_request_error(
        self,
        request: LLMRequest,
        error: Exception,
        provider: str,
        model: str,
        duration_ms: float,
        **kwargs,
    ):
        """Log LLM request error."""
        self.structured_logger.error(
            "LLM request failed",
            provider=provider,
            model=model,
            model_type=str(request.model_type),
            duration_ms=duration_ms,
            error_type=type(error).__name__,
            error_message=str(error),
            **kwargs,
        )

    def log_model_selection(
        self,
        selected_provider: str,
        selected_model: str,
        selection_reason: str,
        alternatives: list,
        **kwargs,
    ):
        """Log model selection decision."""
        self.structured_logger.info(
            "Model selected",
            selected_provider=selected_provider,
            selected_model=selected_model,
            selection_reason=selection_reason,
            alternatives=alternatives,
            **kwargs,
        )

    def log_cost_estimation(
        self,
        provider: str,
        model: str,
        estimated_cost: float,
        input_tokens: int,
        output_tokens: int,
        **kwargs,
    ):
        """Log cost estimation."""
        self.structured_logger.info(
            "Cost estimated",
            provider=provider,
            model=model,
            estimated_cost=estimated_cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_per_1k_tokens=(
                estimated_cost / ((input_tokens + output_tokens) / 1000)
                if (input_tokens + output_tokens) > 0
                else 0
            ),
            **kwargs,
        )


class PerformanceLogger:
    """Specialized logger for performance metrics."""

    def __init__(self):
        """Initialize the performance logger."""
        self.structured_logger = StructuredLogger("llm_performance")

    def log_latency(
        self, operation: str, duration_ms: float, provider: str, model: str, **kwargs
    ):
        """Log operation latency."""
        self.structured_logger.info(
            "Operation latency",
            operation=operation,
            duration_ms=duration_ms,
            provider=provider,
            model=model,
            **kwargs,
        )

    def log_throughput(
        self, operation: str, requests_per_second: float, provider: str, **kwargs
    ):
        """Log throughput metrics."""
        self.structured_logger.info(
            "Throughput metrics",
            operation=operation,
            requests_per_second=requests_per_second,
            provider=provider,
            **kwargs,
        )

    def log_resource_usage(
        self, memory_usage_mb: float, cpu_usage_percent: float, **kwargs
    ):
        """Log resource usage metrics."""
        self.structured_logger.info(
            "Resource usage",
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent,
            **kwargs,
        )


class ErrorLogger:
    """Specialized logger for error tracking and context."""

    def __init__(self):
        """Initialize the error logger."""
        self.structured_logger = StructuredLogger("llm_errors")

    def log_provider_error(
        self,
        provider: str,
        model: str,
        error: Exception,
        request_context: Dict[str, Any],
        **kwargs,
    ):
        """Log provider-specific error with full context."""
        self.structured_logger.error(
            "Provider error occurred",
            provider=provider,
            model=model,
            error_type=type(error).__name__,
            error_message=str(error),
            request_context=request_context,
            **kwargs,
        )

    def log_circuit_breaker_trip(
        self, provider: str, failure_count: int, failure_threshold: int, **kwargs
    ):
        """Log circuit breaker activation."""
        self.structured_logger.warning(
            "Circuit breaker tripped",
            provider=provider,
            failure_count=failure_count,
            failure_threshold=failure_threshold,
            **kwargs,
        )

    def log_rate_limit_exceeded(
        self, provider: str, rate_limit: int, current_requests: int, **kwargs
    ):
        """Log rate limit exceeded."""
        self.structured_logger.warning(
            "Rate limit exceeded",
            provider=provider,
            rate_limit=rate_limit,
            current_requests=current_requests,
            **kwargs,
        )


# Global logger instances
request_logger = LLMRequestLogger()
performance_logger = PerformanceLogger()
error_logger = ErrorLogger()


def set_request_context(
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """Set context variables for request tracking."""
    if request_id:
        request_id_var.set(request_id)
    if session_id:
        session_id_var.set(session_id)
    if user_id:
        user_id_var.set(user_id)


def clear_request_context():
    """Clear all context variables."""
    request_id_var.set(None)
    session_id_var.set(None)
    user_id_var.set(None)


def get_request_context() -> Dict[str, Any]:
    """Get current request context."""
    context = {}
    if request_id_var.get():
        context["request_id"] = request_id_var.get()
    if session_id_var.get():
        context["session_id"] = session_id_var.get()
    if user_id_var.get():
        context["user_id"] = user_id_var.get()
    return context
