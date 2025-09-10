# gemini_sre_agent/source_control/providers/base_sub_operation.py

"""
Base sub-operation module.

This module provides a base class for sub-operation modules with
configuration support and enhanced error handling capabilities.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

from .sub_operation_config import SubOperationConfig, get_sub_operation_config

T = TypeVar("T")


class BaseSubOperation(ABC):
    """Base class for sub-operation modules with configuration support."""

    def __init__(
        self,
        logger: logging.Logger,
        error_handling_components: Optional[Dict[str, Any]] = None,
        config: Optional[SubOperationConfig] = None,
        provider_type: str = "unknown",
        operation_name: str = "unknown",
    ):
        """Initialize base sub-operation."""
        self.logger = logger
        self.error_handling_components = error_handling_components or {}
        self.provider_type = provider_type
        self.operation_name = operation_name

        # Load configuration
        if config:
            self.config = config
        else:
            # Try to get existing config or create default
            existing_config = get_sub_operation_config(provider_type, operation_name)
            if existing_config:
                self.config = existing_config
            else:
                from .sub_operation_config import create_sub_operation_config

                self.config = create_sub_operation_config(provider_type, operation_name)

        # Initialize operation-specific logger
        self.operation_logger = logging.getLogger(
            f"{self.__class__.__name__}.{operation_name}"
        )
        self._setup_logging()

        # Performance tracking
        self._operation_count = 0
        self._error_count = 0
        self._total_duration = 0.0

    def _setup_logging(self) -> None:
        """Setup operation-specific logging."""
        if self.config.log_level:
            level = getattr(logging, self.config.log_level.upper(), logging.INFO)
            self.operation_logger.setLevel(level)

    async def _execute_with_error_handling(
        self,
        operation_name: str,
        func: Callable[..., Awaitable[T]],
        operation_type: str = "default",
        *args,
        **kwargs,
    ) -> T:
        """Execute a function with enhanced error handling and configuration."""
        if not self.config.error_handling_enabled:
            return await func(*args, **kwargs)

        # Get operation-specific settings
        timeout = self.config.get_operation_timeout(operation_type)
        max_retries = self.config.get_operation_retries(operation_type)

        # Log operation start if enabled
        if self.config.log_operations:
            self.operation_logger.info(
                f"Starting {operation_name} (type: {operation_type})"
            )

        start_time = asyncio.get_event_loop().time()

        try:
            # Use resilient manager if available
            if "resilient_manager" in self.error_handling_components:
                resilient_manager = self.error_handling_components["resilient_manager"]

                # Create operation-specific retry config if needed
                if max_retries != 3:  # Default retry count
                    from ..error_handling.core import RetryConfig

                    retry_config = RetryConfig(
                        max_retries=max_retries,
                        base_delay=1.0,
                        max_delay=60.0,
                        backoff_factor=2.0,
                        jitter=True,
                    )
                    # Temporarily override retry config
                    original_config = resilient_manager.retry_config
                    resilient_manager.retry_config = retry_config

                    try:
                        result = await resilient_manager.execute_with_retry(
                            operation_name, func, *args, **kwargs
                        )
                    finally:
                        # Restore original config
                        resilient_manager.retry_config = original_config
                else:
                    result = await resilient_manager.execute_with_retry(
                        operation_name, func, *args, **kwargs
                    )
            else:
                # Fall back to direct execution with timeout
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)

            # Log success if enabled
            if self.config.log_operations:
                duration = asyncio.get_event_loop().time() - start_time
                self.operation_logger.info(
                    f"Completed {operation_name} in {duration:.3f}s"
                )

            # Update performance metrics
            self._operation_count += 1
            self._total_duration += asyncio.get_event_loop().time() - start_time

            return result

        except asyncio.TimeoutError as e:
            self._error_count += 1
            if self.config.log_errors:
                self.operation_logger.error(
                    f"Operation {operation_name} timed out after {timeout}s"
                )
            raise e
        except Exception as e:
            self._error_count += 1
            if self.config.log_errors:
                self.operation_logger.error(f"Operation {operation_name} failed: {e}")
            raise e

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for this sub-operation."""
        avg_duration = self._total_duration / max(self._operation_count, 1)
        error_rate = self._error_count / max(self._operation_count, 1)

        return {
            "operation_name": self.operation_name,
            "provider_type": self.provider_type,
            "total_operations": self._operation_count,
            "error_count": self._error_count,
            "error_rate": error_rate,
            "average_duration": avg_duration,
            "total_duration": self._total_duration,
        }

    def update_config(self, new_config: SubOperationConfig) -> None:
        """Update configuration for this sub-operation."""
        self.config = new_config
        self._setup_logging()
        self.logger.info(f"Updated configuration for {self.operation_name}")

    def get_config(self) -> SubOperationConfig:
        """Get current configuration."""
        return self.config

    def reset_stats(self) -> None:
        """Reset performance statistics."""
        self._operation_count = 0
        self._error_count = 0
        self._total_duration = 0.0
        self.logger.info(f"Reset performance statistics for {self.operation_name}")

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the sub-operation is healthy."""
        pass

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status information."""
        stats = self.get_performance_stats()
        return {
            "healthy": stats["error_rate"] < 0.5,  # Less than 50% error rate
            "operation_name": self.operation_name,
            "provider_type": self.provider_type,
            "performance_stats": stats,
            "config": self.config.to_dict(),
        }
