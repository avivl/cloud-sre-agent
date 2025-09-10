"""
Optimized LLM Service with Performance Enhancements.

This module provides a high-performance version of the enhanced LLM service
that integrates with the performance optimization system to meet the < 10ms
overhead requirement.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

try:
    from mirascope.llm import Provider
except ImportError:
    Provider = None  # type: ignore

from pydantic import BaseModel

from .base import ModelType
from .common.enums import ProviderType
from .config import LLMConfig
from .enhanced_service import EnhancedLLMService
from .factory import get_provider_factory
from .model_selector import SelectionStrategy
from .performance_cache import PerformanceMonitor
from .performance_optimizer import (
    BatchProcessor,
    LazyLoader,
    PerformanceOptimizer,
    cached_model_selection,
)

# Type alias for better type checking
PromptType = Any

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class OptimizedLLMService(Generic[T]):
    """
    High-performance LLM service with comprehensive optimizations.

    Integrates performance optimization system to meet < 10ms overhead requirement
    while maintaining all functionality of the enhanced LLM service.
    """

    def __init__(
        self,
        config: LLMConfig,
        enable_optimizations: bool = True,
        batch_size: int = 10,
        max_wait_ms: float = 5.0,
    ):
        """Initialize the optimized LLM service."""
        self.config = config
        self.enable_optimizations = enable_optimizations
        self.logger = logging.getLogger(__name__)

        # Initialize performance optimizer
        self.performance_optimizer = (
            PerformanceOptimizer(config) if enable_optimizations else None
        )

        # Initialize batch processor for concurrent operations
        self.batch_processor = (
            BatchProcessor(batch_size, max_wait_ms) if enable_optimizations else None
        )

        # Lazy load expensive components
        self._enhanced_service_loader = LazyLoader(self._create_enhanced_service)
        self._provider_factory_loader = LazyLoader(self._create_provider_factory)
        self._performance_monitor_loader = LazyLoader(self._create_performance_monitor)

        # Cache for frequently accessed data
        self._model_cache: Dict[str, Any] = {}
        self._provider_cache: Dict[str, Any] = {}

        # Performance tracking
        self._operation_times: Dict[str, List[float]] = {}
        self._total_operations = 0

        self.logger.info(
            "OptimizedLLMService initialized with performance optimizations"
        )

    async def _create_enhanced_service(self) -> EnhancedLLMService:
        """Lazy create enhanced LLM service."""
        return EnhancedLLMService(self.config)

    async def _create_provider_factory(self):
        """Lazy create provider factory."""
        return get_provider_factory()

    async def _create_performance_monitor(self) -> PerformanceMonitor:
        """Lazy create performance monitor."""
        return PerformanceMonitor()

    async def _ensure_initialized(self) -> None:
        """Ensure all components are initialized."""
        if not self.enable_optimizations:
            return

        # Initialize performance optimizer with lazy-loaded components
        enhanced_service = await self._enhanced_service_loader.get()

        if self.performance_optimizer and not hasattr(
            self.performance_optimizer, "_initialized"
        ):
            await self.performance_optimizer.initialize(
                enhanced_service.model_registry,
                enhanced_service.model_scorer,
            )

    async def generate_structured(
        self,
        prompt: Union[str, Any],
        response_model: Type[T],
        model: Optional[str] = None,
        model_type: Optional[ModelType] = None,
        provider: Optional[str] = None,
        selection_strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE,
        custom_weights: Optional[Any] = None,
        max_cost: Optional[float] = None,
        min_performance: Optional[float] = None,
        min_reliability: Optional[float] = None,
        **kwargs: Any,
    ) -> T:
        """Generate structured response with performance optimizations."""
        start_time = time.time()

        try:
            # Ensure components are initialized
            await self._ensure_initialized()

            # Get enhanced service
            enhanced_service = await self._enhanced_service_loader.get()

            if self.enable_optimizations and self.performance_optimizer:
                # Use optimized model selection
                selected_model, selection_result = (
                    await self.performance_optimizer.get_optimized_model_selection(
                        model_type=model_type,
                        provider=provider,
                        selection_strategy=selection_strategy,
                        max_cost=max_cost,
                        min_performance=min_performance,
                        min_reliability=min_reliability,
                        model_selector=enhanced_service.model_selector,
                    )
                )

                # Use the selected model for generation
                model = selected_model.name
            else:
                # Fallback to standard selection
                pass

            # Generate response using enhanced service
            result = await enhanced_service.generate_structured(
                prompt=prompt,
                response_model=response_model,
                model=model,
                model_type=model_type,
                provider=provider,
                selection_strategy=selection_strategy,
                custom_weights=custom_weights,
                max_cost=max_cost,
                min_performance=min_performance,
                min_reliability=min_reliability,
                **kwargs,
            )

            # Track performance
            execution_time = (time.time() - start_time) * 1000
            self._track_operation_time("generate_structured", execution_time)

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self._track_operation_time("generate_structured_error", execution_time)
            self.logger.error(f"Error in generate_structured: {e}")
            raise

    async def generate_text(
        self,
        prompt: Union[str, Any],
        model: Optional[str] = None,
        model_type: Optional[ModelType] = None,
        provider: Optional[str] = None,
        selection_strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE,
        **kwargs: Any,
    ) -> str:
        """Generate text response with performance optimizations."""
        start_time = time.time()

        try:
            # Ensure components are initialized
            await self._ensure_initialized()

            # Get enhanced service
            enhanced_service = await self._enhanced_service_loader.get()

            if self.enable_optimizations and self.performance_optimizer:
                # Use optimized model selection
                selected_model, selection_result = (
                    await self.performance_optimizer.get_optimized_model_selection(
                        model_type=model_type,
                        provider=provider,
                        selection_strategy=selection_strategy,
                        max_cost=None,
                        min_performance=None,
                        min_reliability=None,
                        model_selector=enhanced_service.model_selector,
                    )
                )

                # Use the selected model for generation
                model = selected_model.name

            # Generate response using enhanced service
            result = await enhanced_service.generate_text(
                prompt=prompt,
                model=model,
                model_type=model_type,
                provider=provider,
                selection_strategy=selection_strategy,
                **kwargs,
            )

            # Track performance
            execution_time = (time.time() - start_time) * 1000
            self._track_operation_time("generate_text", execution_time)

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self._track_operation_time("generate_text_error", execution_time)
            self.logger.error(f"Error in generate_text: {e}")
            raise

    @cached_model_selection(ttl_seconds=60.0)
    async def get_available_models(
        self,
        model_type: Optional[ModelType] = None,
        provider: Optional[ProviderType] = None,
    ) -> List[str]:
        """Get available models with caching."""
        await self._ensure_initialized()

        enhanced_service = await self._enhanced_service_loader.get()

        if self.enable_optimizations and self.performance_optimizer:
            # Use optimized registry
            if model_type:
                models = await self.performance_optimizer.optimized_registry.get_models_by_type(
                    model_type
                )
            elif provider:
                models = await self.performance_optimizer.optimized_registry.get_models_by_provider(
                    provider
                )
            else:
                models = (
                    await self.performance_optimizer.optimized_registry.get_all_models()
                )

            return [model.name for model in models]
        else:
            # Fallback to standard registry
            all_models = enhanced_service.model_registry.get_all_models()
            return [model.name for model in all_models]

    async def batch_generate_structured(
        self,
        requests: List[Dict[str, Any]],
        response_model: Type[T],
        **kwargs: Any,
    ) -> List[T]:
        """Batch generate structured responses with optimizations."""
        if not self.enable_optimizations or not self.batch_processor:
            # Fallback to sequential processing
            results = []
            for request in requests:
                result = await self.generate_structured(
                    prompt=request["prompt"],
                    response_model=response_model,
                    **{**kwargs, **request.get("options", {})},
                )
                results.append(result)
            return results

        # Use batch processor for concurrent execution
        tasks = []
        for request in requests:
            task = self.batch_processor.add_operation(
                self.generate_structured,
                prompt=request["prompt"],
                response_model=response_model,
                **{**kwargs, **request.get("options", {})},
            )
            tasks.append(task)

        return await asyncio.gather(*tasks)

    def _track_operation_time(self, operation: str, execution_time_ms: float) -> None:
        """Track operation execution times for performance monitoring."""
        if operation not in self._operation_times:
            self._operation_times[operation] = []

        self._operation_times[operation].append(execution_time_ms)
        self._total_operations += 1

        # Keep only last 100 measurements to prevent memory growth
        if len(self._operation_times[operation]) > 100:
            self._operation_times[operation] = self._operation_times[operation][-100:]

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        stats = {
            "total_operations": self._total_operations,
            "optimizations_enabled": self.enable_optimizations,
            "operation_times": {},
        }

        # Calculate average times for each operation
        for operation, times in self._operation_times.items():
            if times:
                stats["operation_times"][operation] = {
                    "count": len(times),
                    "avg_ms": round(sum(times) / len(times), 2),
                    "min_ms": round(min(times), 2),
                    "max_ms": round(max(times), 2),
                    "p95_ms": (
                        round(sorted(times)[int(len(times) * 0.95)], 2)
                        if len(times) > 1
                        else times[0]
                    ),
                }

        # Add optimizer stats if available
        if self.performance_optimizer:
            stats["optimizer_stats"] = (
                self.performance_optimizer.get_performance_stats()
            )

        return stats

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check with performance metrics."""
        start_time = time.time()

        try:
            # Check if components are properly initialized
            await self._ensure_initialized()

            await self._enhanced_service_loader.get()

            # Basic health check
            health_status = {
                "status": "healthy",
                "initialization_time_ms": round((time.time() - start_time) * 1000, 2),
                "optimizations_enabled": self.enable_optimizations,
                "total_operations": self._total_operations,
            }

            # Add performance stats
            health_status["performance_stats"] = self.get_performance_stats()

            return health_status

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "initialization_time_ms": round((time.time() - start_time) * 1000, 2),
            }

    async def clear_caches(self) -> None:
        """Clear all performance caches."""
        if self.performance_optimizer:
            await self.performance_optimizer.model_selection_cache._cache.clear()
            self.performance_optimizer.optimized_registry._model_cache.clear()

        self._model_cache.clear()
        self._provider_cache.clear()

        self.logger.info("All performance caches cleared")

    async def warmup(self) -> None:
        """Warm up the service by pre-initializing components."""
        start_time = time.time()

        try:
            # Pre-initialize all components
            await self._ensure_initialized()

            # Pre-load some common models
            enhanced_service = await self._enhanced_service_loader.get()
            common_models = ["gpt-3.5-turbo", "claude-3-haiku", "gemini-1.5-flash"]

            for model_name in common_models:
                try:
                    model_info = enhanced_service.model_registry.get_model(model_name)
                    if model_info:
                        # Pre-compute some scores
                        context = (
                            enhanced_service.model_scorer._create_default_context()
                        )
                        enhanced_service.model_scorer.score_model(model_info, context)
                except Exception as e:
                    self.logger.debug(f"Failed to warmup model {model_name}: {e}")

            warmup_time = (time.time() - start_time) * 1000
            self.logger.info(f"Service warmup completed in {warmup_time:.2f}ms")

        except Exception as e:
            self.logger.error(f"Service warmup failed: {e}")
            raise
