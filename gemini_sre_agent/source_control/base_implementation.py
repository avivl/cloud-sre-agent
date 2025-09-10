# gemini_sre_agent/source_control/base_implementation.py

"""
Base implementation of SourceControlProvider with common functionality.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base import SourceControlProvider
from .error_handling import (
    CircuitBreakerConfig,
    ErrorHandlingFactory,
    ResilientOperationManager,
    RetryConfig,
    create_provider_error_handling,
)
from .metrics import MetricsCollector, OperationMetrics
from .models import (
    BatchOperation,
    ConflictInfo,
    OperationResult,
    ProviderHealth,
    RemediationResult,
)
from .monitoring import MonitoringManager


class BaseSourceControlProvider(SourceControlProvider):
    """Base implementation of SourceControlProvider with common functionality."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration."""
        super().__init__(config)
        self._client = None
        self._rate_limiter = None
        self._retry_config = self.get_config_value("retry", {})
        self._timeout_config = self.get_config_value("timeout", {})

        # Initialize error handling system
        self._error_handling_factory = ErrorHandlingFactory()
        self._error_handling_components = None
        # Initialize resilient operation manager (legacy support)
        circuit_config = CircuitBreakerConfig(
            failure_threshold=self._retry_config.get(
                "circuit_breaker_failure_threshold", 5
            ),
            recovery_timeout=self._retry_config.get(
                "circuit_breaker_recovery_timeout", 60.0
            ),
            success_threshold=self._retry_config.get(
                "circuit_breaker_success_threshold", 3
            ),
            timeout=self._timeout_config.get("default", 30.0),
        )
        retry_config = RetryConfig(
            max_retries=self._retry_config.get("max_retries", 3),
            base_delay=self._retry_config.get("base_delay", 1.0),
            max_delay=self._retry_config.get("max_delay", 60.0),
            backoff_factor=self._retry_config.get("backoff_factor", 2.0),
            jitter=self._retry_config.get("jitter", True),
        )
        self._resilient_manager = ResilientOperationManager(
            circuit_breaker_config=circuit_config, retry_config=retry_config
        )

        # Initialize monitoring
        enable_monitoring = self.get_config_value("monitoring", {}).get("enabled", True)
        if enable_monitoring:
            self.monitoring_manager = MonitoringManager(
                enable_metrics=self.get_config_value("monitoring", {}).get(
                    "enable_metrics", True
                ),
                enable_health_checks=self.get_config_value("monitoring", {}).get(
                    "enable_health_checks", True
                ),
                enable_alerts=self.get_config_value("monitoring", {}).get(
                    "enable_alerts", True
                ),
            )
            self.metrics_collector = MetricsCollector()
            self.operation_metrics = OperationMetrics(self.metrics_collector)
        else:
            self.monitoring_manager = None
            self.metrics_collector = None
            self.operation_metrics = None

    async def _setup_client(self) -> None:
        """Set up the client for the source control system."""
        # To be implemented by subclasses
        pass

    async def _teardown_client(self) -> None:
        """Tear down the client for the source control system."""
        # To be implemented by subclasses
        if self._client:
            self._client = None

    async def _execute_resilient_operation(
        self, operation_name: str, func: Callable, *args, **kwargs
    ) -> Any:
        """Execute an operation with full resilience (circuit breaker + retry)."""
        return await self._resilient_manager.execute_resilient_operation(
            operation_name, func, *args, **kwargs
        )

    def _initialize_error_handling(self, provider_name: str, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the advanced error handling system for a specific provider."""
        try:
            self._error_handling_components = create_provider_error_handling(
                provider_name, config
            )
            self.logger.info(f"Error handling system initialized for {provider_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize error handling for {provider_name}: {e}")
            # Fall back to legacy resilient manager
            self._error_handling_components = None

    async def _execute_with_error_handling(
        self, operation_name: str, func: Callable, *args, **kwargs
    ) -> Any:
        """Execute an operation with advanced error handling."""
        if self._error_handling_components:
            # Use advanced error handling system
            resilient_manager = self._error_handling_components.get("resilient_manager")
            if resilient_manager:
                return await resilient_manager.execute_resilient_operation(
                    operation_name, func, *args, **kwargs
                )

        # Fall back to legacy resilient manager
        return await self._execute_resilient_operation(operation_name, func, *args, **kwargs)

    async def handle_operation_failure(self, operation: str, error: Exception) -> bool:
        """Default implementation for handling operation failures."""
        self.logger.error(f"Operation {operation} failed: {str(error)}")

        # Check if this is a retryable error
        if self._is_retryable_error(error):
            return await self.retry_operation(operation)

        return False

    async def retry_operation(
        self, operation: str, max_retries: Optional[int] = None
    ) -> bool:
        """Retry a failed operation with exponential backoff."""
        if max_retries is None:
            max_retries = self._retry_config.get("max_retries", 3)

        base_delay = self._retry_config.get("base_delay", 1.0)
        max_delay = self._retry_config.get("max_delay", 60.0)

        for attempt in range(max_retries or 0):
            try:
                self.logger.info(
                    f"Retrying operation {operation} (attempt {attempt + 1}/{max_retries})"
                )

                # Calculate delay with exponential backoff
                delay = min(base_delay * (2**attempt), max_delay)
                await asyncio.sleep(delay)

                # The actual retry logic should be implemented by the caller
                # This is just a placeholder for the retry mechanism
                return True

            except Exception as e:
                self.logger.warning(f"Retry attempt {attempt + 1} failed: {e}")
                if attempt == (max_retries or 0) - 1:
                    self.logger.error(
                        f"All retry attempts failed for operation {operation}"
                    )
                    return False

        return False

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable."""
        retryable_errors = self._retry_config.get(
            "retryable_errors",
            ["ConnectionError", "TimeoutError", "RateLimitError", "TemporaryError"],
        )

        error_type = type(error).__name__
        return error_type in retryable_errors

    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Default implementation for batch operations."""
        results = []

        for i, operation in enumerate(operations):
            try:
                result = await self._execute_single_operation(operation)
                results.append(
                    OperationResult(
                        operation_id=f"batch_{i}",
                        success=True,
                        message="Operation completed successfully",
                        file_path=operation.file_path,
                        additional_info={
                            "operation_type": operation.operation_type,
                            "result": result,
                        },
                    )
                )
            except Exception as e:
                self.logger.error(f"Batch operation {i} failed: {e}")
                results.append(
                    OperationResult(
                        operation_id=f"batch_{i}",
                        success=False,
                        message=f"Operation failed: {str(e)}",
                        file_path=operation.file_path,
                        error_details=str(e),
                        additional_info={"operation_type": operation.operation_type},
                    )
                )

        return results

    async def _execute_single_operation(self, operation: BatchOperation) -> Any:
        """Execute a single operation from a batch."""
        operation_type = operation.operation_type

        if operation_type == "update_file":
            if operation.file_path is None or operation.content is None:
                raise ValueError(
                    "Path and content are required for update_file operation"
                )
            return await self.apply_remediation(
                operation.file_path, operation.content, "Batch update"
            )
        elif operation_type == "delete_file":
            # This would need to be implemented by subclasses
            raise NotImplementedError("Delete file operation not implemented")
        elif operation_type == "create_branch":
            name = (
                operation.additional_params.get("name")
                if operation.additional_params
                else None
            )
            if name is None:
                raise ValueError("Branch name is required for create_branch operation")
            return await self.create_branch(
                name,
                (
                    operation.additional_params.get("base_ref")
                    if operation.additional_params
                    else None
                ),
            )
        else:
            raise ValueError(f"Unknown operation type: {operation_type}")

    async def get_health_status(self) -> ProviderHealth:
        """Get the health status of the provider."""
        # Get health from resilient manager
        resilient_health = self._resilient_manager.get_health_status()

        # Also perform basic health check
        try:
            basic_health = await self.health_check()
            # Combine both health checks
            return ProviderHealth(
                status=(
                    resilient_health.status
                    if resilient_health.status == "unhealthy"
                    else basic_health.status
                ),
                message=f"Resilient: {resilient_health.message}, Basic: {basic_health.message}",
                additional_info={
                    "resilient_health": resilient_health.additional_info,
                    "basic_health": basic_health.additional_info,
                },
            )
        except Exception as e:
            self.logger.error(f"Basic health check failed: {e}")
            return resilient_health

    async def check_conflicts(
        self, path: str, content: str, branch: Optional[str] = None
    ) -> bool:
        """Default implementation for conflict checking."""
        # This is a simplified implementation
        # Real implementations would check for actual merge conflicts
        try:
            current_content = await self.get_file_content(path, branch)
            return current_content != content
        except Exception:
            # If we can't read the file, assume no conflicts
            return False

    async def resolve_conflicts(
        self, path: str, content: str, strategy: str = "manual"
    ) -> bool:
        """Default implementation for conflict resolution."""
        if strategy == "manual":
            self.logger.warning(f"Manual conflict resolution required for {path}")
            return False
        elif strategy == "auto":
            # Attempt automatic resolution
            try:
                await self.apply_remediation(
                    path, content, f"Auto-resolve conflicts in {path}"
                )
                return True
            except Exception as e:
                self.logger.error(f"Auto conflict resolution failed: {e}")
                return False
        else:
            raise ValueError(f"Unknown conflict resolution strategy: {strategy}")

    async def get_conflict_info(self, path: str) -> Optional[ConflictInfo]:
        """Get detailed information about conflicts in a file."""
        # This is a placeholder implementation
        # Real implementations would analyze the file for conflict markers
        return None

    def _create_remediation_result(
        self,
        success: bool,
        message: str,
        file_path: str,
        operation_type: str,
        commit_sha: Optional[str] = None,
        pull_request_url: Optional[str] = None,
        error_details: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> RemediationResult:
        """Helper method to create a RemediationResult."""
        return RemediationResult(
            success=success,
            message=message,
            file_path=file_path,
            operation_type=operation_type,
            commit_sha=commit_sha,
            pull_request_url=pull_request_url,
            error_details=error_details,
            additional_info=additional_info or {},
        )

    def _create_operation_result(
        self,
        operation_id: str,
        success: bool,
        message: str,
        file_path: Optional[str] = None,
        error_details: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> OperationResult:
        """Helper method to create an OperationResult."""
        return OperationResult(
            operation_id=operation_id,
            success=success,
            message=message,
            file_path=file_path,
            error_details=error_details,
            additional_info=additional_info or {},
        )

    def _log_operation(
        self, operation: str, success: bool, details: Optional[Dict[str, Any]] = None
    ):
        """Log an operation with details."""
        level = logging.INFO if success else logging.ERROR
        message = f"Operation '{operation}' {'succeeded' if success else 'failed'}"

        if details:
            message += f" - {details}"

        self.logger.log(level, message)

    async def get_comprehensive_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status including monitoring data."""
        if not self.monitoring_manager:
            return {"error": "Monitoring not enabled"}

        # Get basic health status
        basic_health = await self.get_health_status()

        # Run comprehensive health checks
        health_checks = await self.monitoring_manager.run_health_checks([self])

        # Get monitoring summary
        monitoring_summary = self.monitoring_manager.get_monitoring_summary()

        # Get metrics summary if available
        metrics_summary = {}
        if self.metrics_collector:
            metrics_summary = await self.metrics_collector.get_metrics_summary()

        return {
            "basic_health": {
                "status": basic_health.status,
                "message": basic_health.message,
                "details": basic_health.additional_info,
            },
            "comprehensive_checks": health_checks.get(self.__class__.__name__, []),
            "monitoring": monitoring_summary,
            "metrics": metrics_summary,
            "timestamp": datetime.now().isoformat(),
        }

    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary for this provider."""
        if not self.metrics_collector:
            return {"error": "Metrics collection not enabled"}

        return await self.metrics_collector.get_metrics_summary()

    async def get_operation_statistics(
        self, operation_name: Optional[str] = None, window_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get operation statistics for this provider."""
        if not self.operation_metrics:
            return {"error": "Operation metrics not enabled"}

        return await self.operation_metrics.get_operation_statistics(
            self.__class__.__name__, operation_name, window_minutes
        )
