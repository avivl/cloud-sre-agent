# gemini_sre_agent/llm/service_base.py

"""
Base classes and common types for enhanced LLM service.

This module provides the abstract base class and common types for implementing
the enhanced LLM service with intelligent model selection capabilities.

Classes:
    BaseLLMService: Abstract base class for LLM services
    ServiceContext: Context data for service operations
    ServiceResult: Result data from service operations
    ServiceMetrics: Metrics data for service performance

Author: Gemini SRE Agent
Created: 2024
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from .base import ModelType
from .config import LLMConfig
from .model_registry import ModelInfo
from .model_scorer import ModelScorer, ScoringWeights
from .model_selector import SelectionStrategy
from .performance_cache import PerformanceMonitor

# Type aliases
T = TypeVar("T", bound=Any)
PromptType = Any


class ServiceOperation(Enum):
    """Enumeration of available service operations."""

    STRUCTURED_GENERATION = "structured_generation"
    TEXT_GENERATION = "text_generation"
    FALLBACK_GENERATION = "fallback_generation"
    HEALTH_CHECK = "health_check"


@dataclass
class ServiceContext:
    """Context data for service operations."""

    operation: ServiceOperation
    model: Optional[str] = None
    model_type: Optional[ModelType] = None
    provider: Optional[str] = None
    selection_strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE
    custom_weights: Optional[ScoringWeights] = None
    max_cost: Optional[float] = None
    min_performance: Optional[float] = None
    min_reliability: Optional[float] = None
    required_capabilities: Optional[List[str]] = None
    max_attempts: int = 3
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ServiceResult:
    """Result data from service operations."""

    success: bool
    content: Union[str, Any]
    model_used: str
    provider_used: str
    execution_time_ms: float
    operation: ServiceOperation
    fallback_used: bool = False
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ServiceMetrics:
    """Metrics data for service performance."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0
    model_usage_counts: Optional[Dict[str, int]] = None
    provider_usage_counts: Optional[Dict[str, int]] = None
    operation_counts: Optional[Dict[ServiceOperation, int]] = None
    last_updated: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.model_usage_counts is None:
            self.model_usage_counts = {}
        if self.provider_usage_counts is None:
            self.provider_usage_counts = {}
        if self.operation_counts is None:
            self.operation_counts = {}


class BaseLLMService(ABC):
    """Abstract base class for LLM services with intelligent model selection."""

    def __init__(
        self,
        config: LLMConfig,
        model_registry: Optional[ModelInfo] = None,
        performance_monitor: Optional[PerformanceMonitor] = None,
    ):
        """Initialize the base LLM service.

        Args:
            config: LLM configuration
            model_registry: Optional model registry instance
            performance_monitor: Optional performance monitor instance
        """
        self.config = config
        self.model_registry = model_registry
        self.performance_monitor = performance_monitor or PerformanceMonitor()
        self.model_scorer = ModelScorer()

        # Track service metrics
        self._service_metrics = ServiceMetrics()
        self._selection_stats: Dict[str, int] = {}
        self._last_selection_time: Dict[str, float] = {}

    @abstractmethod
    async def generate_structured(
        self,
        prompt: Union[str, Any],
        response_model: Type[T],
        context: Optional[ServiceContext] = None,
        **kwargs: Any,
    ) -> T:
        """Generate a structured response with intelligent model selection.

        Args:
            prompt: Input prompt
            response_model: Pydantic model for structured response
            context: Optional service context
            **kwargs: Additional arguments

        Returns:
            Structured response of type T
        """
        pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: Union[str, Any],
        context: Optional[ServiceContext] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a plain text response with intelligent model selection.

        Args:
            prompt: Input prompt
            context: Optional service context
            **kwargs: Additional arguments

        Returns:
            Text response
        """
        pass

    @abstractmethod
    async def generate_with_fallback(
        self,
        prompt: Union[str, Any],
        response_model: Optional[Type[T]] = None,
        context: Optional[ServiceContext] = None,
        **kwargs: Any,
    ) -> Union[str, T]:
        """Generate response with automatic fallback chain execution.

        Args:
            prompt: Input prompt
            response_model: Optional Pydantic model for structured response
            context: Optional service context
            **kwargs: Additional arguments

        Returns:
            Response (text or structured)
        """
        pass

    def _update_service_metrics(
        self,
        success: bool,
        latency_ms: float,
        model_used: str,
        provider_used: str,
        operation: ServiceOperation,
    ):
        """Update service metrics.

        Args:
            success: Whether the operation was successful
            latency_ms: Execution latency in milliseconds
            model_used: Model that was used
            provider_used: Provider that was used
            operation: Type of operation performed
        """
        self._service_metrics.total_requests += 1

        if success:
            self._service_metrics.successful_requests += 1
        else:
            self._service_metrics.failed_requests += 1

        # Update latency metrics
        if latency_ms < self._service_metrics.min_latency_ms:
            self._service_metrics.min_latency_ms = latency_ms
        if latency_ms > self._service_metrics.max_latency_ms:
            self._service_metrics.max_latency_ms = latency_ms

        # Update average latency
        total = self._service_metrics.total_requests
        current_avg = self._service_metrics.average_latency_ms
        self._service_metrics.average_latency_ms = (
            current_avg * (total - 1) + latency_ms
        ) / total

        # Update usage counts
        if self._service_metrics.model_usage_counts is not None:
            self._service_metrics.model_usage_counts[model_used] = (
                self._service_metrics.model_usage_counts.get(model_used, 0) + 1
            )
        if self._service_metrics.provider_usage_counts is not None:
            self._service_metrics.provider_usage_counts[provider_used] = (
                self._service_metrics.provider_usage_counts.get(provider_used, 0) + 1
            )
        if self._service_metrics.operation_counts is not None:
            self._service_metrics.operation_counts[operation] = (
                self._service_metrics.operation_counts.get(operation, 0) + 1
            )

        self._service_metrics.last_updated = datetime.now()

    def _update_selection_stats(
        self, model_name: str, strategy: SelectionStrategy
    ) -> None:
        """Update selection statistics.

        Args:
            model_name: Name of the selected model
            strategy: Selection strategy used
        """
        key = f"{model_name}:{strategy.value}"
        self._selection_stats[key] = self._selection_stats.get(key, 0) + 1
        self._last_selection_time[model_name] = time.time()

    def get_service_metrics(self) -> ServiceMetrics:
        """Get current service metrics.

        Returns:
            Current service metrics
        """
        return self._service_metrics

    def get_selection_stats(self) -> Dict[str, Any]:
        """Get model selection statistics.

        Returns:
            Dictionary containing selection statistics
        """
        return {
            "selection_counts": self._selection_stats.copy(),
            "last_selection_times": self._last_selection_time.copy(),
            "performance_cache_stats": self.performance_monitor.get_cache_stats(),
        }

    def reset_metrics(self) -> None:
        """Reset all service metrics."""
        self._service_metrics = ServiceMetrics()
        self._selection_stats.clear()
        self._last_selection_time.clear()

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the service.

        Returns:
            Dictionary containing health status and metrics
        """
        return {
            "status": "healthy",
            "total_requests": self._service_metrics.total_requests,
            "success_rate": (
                self._service_metrics.successful_requests
                / max(1, self._service_metrics.total_requests)
            ),
            "average_latency_ms": self._service_metrics.average_latency_ms,
            "available_models": len(self._service_metrics.model_usage_counts or {}),
            "available_providers": len(
                self._service_metrics.provider_usage_counts or {}
            ),
        }
