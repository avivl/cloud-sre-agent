# gemini_sre_agent/llm/mirascope_facade.py

"""
Mirascope Integration Facade Module

This module provides a unified facade for Mirascope integration, combining
configuration, client management, response processing, and analytics.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from typing import Any, TypeVar
import uuid

from pydantic import BaseModel

from .mirascope_client import ClientResponse, MirascopeClientManager, get_client_manager
from .mirascope_config import (
    ConfigurationManager,
    MirascopeIntegrationConfig,
    get_config_manager,
)
from .mirascope_response import (
    ProcessedResponse,
    ResponseProcessor,
    get_response_processor,
)

T = TypeVar("T", bound=BaseModel)


class IntegrationStatus(Enum):
    """Status of the integration."""

    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class RequestType(Enum):
    """Types of requests."""

    GENERATE = "generate"
    GENERATE_STRUCTURED = "generate_structured"
    STREAM = "stream"
    VALIDATE = "validate"
    ANALYZE = "analyze"


@dataclass
class IntegrationMetrics:
    """Metrics for the integration."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time_ms: float = 0.0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    provider_usage: dict[str, int] = field(default_factory=dict)
    request_type_usage: dict[str, int] = field(default_factory=dict)
    error_rates: dict[str, float] = field(default_factory=dict)
    last_request_time: datetime | None = None
    uptime_seconds: float = 0.0


@dataclass
class RequestContext:
    """Context for a request."""

    request_id: str
    request_type: RequestType
    provider: str | None = None
    model: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class AnalyticsCollector:
    """Collects and analyzes integration metrics."""

    def __init__(self) -> None:
        self.metrics = IntegrationMetrics()
        self.request_history: list[dict[str, Any]] = []
        self.logger = logging.getLogger(__name__)
        self._start_time = datetime.now()

    def record_request(
        self,
        context: RequestContext,
        success: bool,
        response_time_ms: float,
        tokens_used: int | None = None,
        cost_usd: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record a request in analytics."""
        self.metrics.total_requests += 1

        if success:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1

        # Update response time
        if self.metrics.total_requests == 1:
            self.metrics.average_response_time_ms = response_time_ms
        else:
            self.metrics.average_response_time_ms = (
                self.metrics.average_response_time_ms
                * (self.metrics.total_requests - 1)
                + response_time_ms
            ) / self.metrics.total_requests

        # Update token and cost metrics
        if tokens_used:
            self.metrics.total_tokens_used += tokens_used

        if cost_usd:
            self.metrics.total_cost_usd += cost_usd

        # Update provider usage
        if context.provider:
            self.metrics.provider_usage[context.provider] = (
                self.metrics.provider_usage.get(context.provider, 0) + 1
            )

        # Update request type usage
        request_type = context.request_type.value
        self.metrics.request_type_usage[request_type] = (
            self.metrics.request_type_usage.get(request_type, 0) + 1
        )

        # Update error rates
        if not success and error_message:
            error_type = self._categorize_error(error_message)
            self.metrics.error_rates[error_type] = (
                self.metrics.error_rates.get(error_type, 0) + 1
            )

        self.metrics.last_request_time = datetime.now()
        self.metrics.uptime_seconds = (
            datetime.now() - self._start_time
        ).total_seconds()

        # Store request history
        self.request_history.append(
            {
                "request_id": context.request_id,
                "request_type": request_type,
                "provider": context.provider,
                "model": context.model,
                "success": success,
                "response_time_ms": response_time_ms,
                "tokens_used": tokens_used,
                "cost_usd": cost_usd,
                "error_message": error_message,
                "timestamp": context.created_at.isoformat(),
            }
        )

        # Keep only last 1000 requests in memory
        if len(self.request_history) > 1000:
            self.request_history = self.request_history[-1000:]

    def _categorize_error(self, error_message: str) -> str:
        """Categorize error message into error type."""
        error_lower = error_message.lower()

        if "timeout" in error_lower:
            return "timeout"
        elif "rate limit" in error_lower:
            return "rate_limit"
        elif "authentication" in error_lower or "unauthorized" in error_lower:
            return "authentication"
        elif "validation" in error_lower:
            return "validation"
        elif "network" in error_lower or "connection" in error_lower:
            return "network"
        else:
            return "unknown"

    def get_metrics(self) -> IntegrationMetrics:
        """Get current metrics."""
        return self.metrics

    def get_health_status(self) -> dict[str, Any]:
        """Get health status based on metrics."""
        if self.metrics.total_requests == 0:
            return {"status": "no_requests", "message": "No requests processed yet"}

        success_rate = self.metrics.successful_requests / self.metrics.total_requests

        if success_rate >= 0.95:
            status = "healthy"
        elif success_rate >= 0.8:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "success_rate": success_rate,
            "total_requests": self.metrics.total_requests,
            "average_response_time_ms": self.metrics.average_response_time_ms,
            "uptime_seconds": self.metrics.uptime_seconds,
        }

    def get_provider_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics by provider."""
        stats = {}

        for provider, count in self.metrics.provider_usage.items():
            provider_requests = [
                req for req in self.request_history if req.get("provider") == provider
            ]

            if provider_requests:
                success_count = sum(
                    1 for req in provider_requests if req.get("success", False)
                )
                success_rate = success_count / len(provider_requests)
                avg_response_time = sum(
                    req.get("response_time_ms", 0) for req in provider_requests
                ) / len(provider_requests)

                stats[provider] = {
                    "total_requests": count,
                    "success_rate": success_rate,
                    "average_response_time_ms": avg_response_time,
                }

        return stats


class MirascopeIntegrationFacade:
    """Main facade for Mirascope integration."""

    def __init__(
        self,
        config_manager: ConfigurationManager | None = None,
        client_manager: MirascopeClientManager | None = None,
        response_processor: ResponseProcessor | None = None,
    ):
        """Initialize the integration facade."""
        self.config_manager = config_manager or get_config_manager()
        self.client_manager = client_manager or get_client_manager()
        self.response_processor = response_processor or get_response_processor()
        self.analytics = AnalyticsCollector()
        self.logger = logging.getLogger(__name__)
        self.status = IntegrationStatus.INITIALIZING
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the integration."""
        try:
            # Validate configuration
            config_errors = self.config_manager.validate_config()
            if config_errors:
                self.logger.error(f"Configuration errors: {config_errors}")
                self.status = IntegrationStatus.ERROR
                return

            # Check client availability
            available_clients = self.client_manager.get_available_clients()
            if not available_clients:
                self.logger.error("No available clients")
                self.status = IntegrationStatus.ERROR
                return

            self.status = IntegrationStatus.READY
            self.logger.info("Mirascope integration initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize integration: {e}")
            self.status = IntegrationStatus.ERROR

    async def generate(
        self,
        prompt: str,
        provider: str | None = None,
        model: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> ProcessedResponse:
        """Generate a response with full processing."""
        context = RequestContext(
            request_id=str(uuid.uuid4()),
            request_type=RequestType.GENERATE,
            provider=provider,
            model=model,
            user_id=user_id,
            session_id=session_id,
            metadata=kwargs,
        )

        start_time = datetime.now()
        success = False
        error_message = None

        try:
            # Generate response
            response = await self.client_manager.generate_with_fallback(
                prompt=prompt, preferred_provider=provider, **kwargs
            )

            # Process response
            processed_response = self.response_processor.process_response(response)

            success = processed_response.status.value == "success"
            if not success:
                error_message = (
                    f"Processing failed: {processed_response.metadata.errors}"
                )

            # Record analytics
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            self.analytics.record_request(
                context=context,
                success=success,
                response_time_ms=response_time,
                tokens_used=response.tokens_used,
                cost_usd=response.cost_usd,
                error_message=error_message,
            )

            return processed_response

        except Exception as e:
            error_message = str(e)
            response_time = (datetime.now() - start_time).total_seconds() * 1000

            self.analytics.record_request(
                context=context,
                success=False,
                response_time_ms=response_time,
                error_message=error_message,
            )

            # Return error response
            from .mirascope_response import ResponseMetadata, ResponseStatus

            return ProcessedResponse(
                original_response=ClientResponse(
                    content="",
                    model=model or "unknown",
                    provider=provider or "unknown",
                    request_id=context.request_id,
                ),
                processed_content="",
                status=ResponseStatus.UNKNOWN_ERROR,
                metadata=ResponseMetadata(processing_time_ms=0.0),
            )

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        provider: str | None = None,
        model: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> tuple[ProcessedResponse, T | None]:
        """Generate a structured response."""
        context = RequestContext(
            request_id=str(uuid.uuid4()),
            request_type=RequestType.GENERATE_STRUCTURED,
            provider=provider,
            model=model,
            user_id=user_id,
            session_id=session_id,
            metadata=kwargs,
        )

        start_time = datetime.now()
        success = False
        error_message = None
        structured_data = None

        try:
            # Generate structured response
            structured_data = (
                await self.client_manager.generate_structured_with_fallback(
                    prompt=prompt,
                    response_model=response_model,
                    preferred_provider=provider,
                    **kwargs,
                )
            )

            # Create a mock ClientResponse for processing
            mock_response = ClientResponse(
                content=str(structured_data),
                model=model or "unknown",
                provider=provider or "unknown",
                request_id=context.request_id,
            )

            # Process response
            processed_response, parsed_structured_data = (
                self.response_processor.process_structured_response(
                    mock_response, response_model
                )
            )

            success = (
                processed_response.status.value == "success"
                and structured_data is not None
            )
            if not success:
                error_message = f"Structured generation failed: {processed_response.metadata.errors}"

            # Record analytics
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            self.analytics.record_request(
                context=context,
                success=success,
                response_time_ms=response_time,
                error_message=error_message,
            )

            return processed_response, structured_data

        except Exception as e:
            error_message = str(e)
            response_time = (datetime.now() - start_time).total_seconds() * 1000

            self.analytics.record_request(
                context=context,
                success=False,
                response_time_ms=response_time,
                error_message=error_message,
            )

            # Return error response
            from .mirascope_response import ResponseMetadata, ResponseStatus

            return (
                ProcessedResponse(
                    original_response=ClientResponse(
                        content="",
                        model=model or "unknown",
                        provider=provider or "unknown",
                        request_id=context.request_id,
                    ),
                    processed_content="",
                    status=ResponseStatus.UNKNOWN_ERROR,
                    metadata=ResponseMetadata(processing_time_ms=0.0),
                ),
                None,
            )

    async def stream_generate(
        self,
        prompt: str,
        provider: str | None = None,
        model: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Generate a streaming response."""
        context = RequestContext(
            request_id=str(uuid.uuid4()),
            request_type=RequestType.STREAM,
            provider=provider,
            model=model,
            user_id=user_id,
            session_id=session_id,
            metadata=kwargs,
        )

        start_time = datetime.now()

        try:
            client = self.client_manager.get_client(provider)
            if not client:
                raise RuntimeError("No available client")

            # Stream response
            stream = await client.stream_generate(prompt, **kwargs)
            async for chunk in stream:
                yield chunk

            # Record successful streaming request
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            self.analytics.record_request(
                context=context, success=True, response_time_ms=response_time
            )

        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            self.analytics.record_request(
                context=context,
                success=False,
                response_time_ms=response_time,
                error_message=str(e),
            )
            raise

    def get_health_status(self) -> dict[str, Any]:
        """Get comprehensive health status."""
        return {
            "integration_status": self.status.value,
            "configuration_valid": len(self.config_manager.validate_config()) == 0,
            "available_clients": len(self.client_manager.get_available_clients()),
            "analytics": self.analytics.get_health_status(),
            "client_health": self.client_manager.get_client_health(),
        }

    def get_metrics(self) -> dict[str, Any]:
        """Get comprehensive metrics."""
        return {
            "integration_metrics": self.analytics.get_metrics(),
            "client_metrics": self.client_manager.get_metrics(),
            "provider_stats": self.analytics.get_provider_stats(),
        }

    def get_configuration(self) -> MirascopeIntegrationConfig:
        """Get current configuration."""
        return self.config_manager.get_config()

    def update_configuration(self, **kwargs) -> None:
        """Update configuration."""
        self.config_manager.update_config(**kwargs)
        self.logger.info("Configuration updated")

    def add_provider(self, name: str, provider_config) -> None:
        """Add a new provider."""
        self.config_manager.add_provider(name, provider_config)
        # Reinitialize client manager with new provider
        self.client_manager._initialize_clients()
        self.logger.info(f"Added provider: {name}")

    def remove_provider(self, name: str) -> bool:
        """Remove a provider."""
        success = self.config_manager.remove_provider(name)
        if success:
            # Reinitialize client manager
            self.client_manager._initialize_clients()
            self.logger.info(f"Removed provider: {name}")
        return success

    def export_analytics(self, file_path: str) -> bool:
        """Export analytics data to file."""
        try:
            import json

            data = {
                "metrics": self.analytics.get_metrics(),
                "request_history": self.analytics.request_history,
                "exported_at": datetime.now().isoformat(),
            }
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            self.logger.info(f"Analytics exported to {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to export analytics: {e}")
            return False


# Global integration facade instance
_integration_facade: MirascopeIntegrationFacade | None = None


def get_integration_facade() -> MirascopeIntegrationFacade:
    """Get the global integration facade instance."""
    global _integration_facade
    if _integration_facade is None:
        _integration_facade = MirascopeIntegrationFacade()
    return _integration_facade


def create_integration_facade(
    config_manager: ConfigurationManager | None = None,
    client_manager: MirascopeClientManager | None = None,
    response_processor: ResponseProcessor | None = None,
) -> MirascopeIntegrationFacade:
    """Create a new integration facade instance."""
    return MirascopeIntegrationFacade(
        config_manager, client_manager, response_processor
    )
