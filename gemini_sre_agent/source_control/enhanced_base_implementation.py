# gemini_sre_agent/source_control/enhanced_base_implementation.py

"""
Enhanced base implementation of SourceControlProvider with comprehensive error handling.

This module provides an enhanced base implementation that integrates the new error handling
system including circuit breakers, retry mechanisms, error classification, graceful degradation,
health checks, and metrics collection.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from .base import SourceControlProvider
from .error_handling import (
    CircuitBreakerConfig,
    ErrorClassifier,
    ErrorHandlingMetrics,
    HealthCheckManager,
    OperationCircuitBreakerConfig,
    ResilientOperationManager,
    RetryConfig,
    create_graceful_degradation_manager,
)
from .metrics import MetricsCollector, OperationMetrics
from .models import (
    BatchOperation,
    OperationResult,
    ProviderHealth,
    RemediationResult,
)
from .monitoring import MonitoringManager


class EnhancedBaseSourceControlProvider(SourceControlProvider):
    """Enhanced base implementation with comprehensive error handling."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize with enhanced error handling configuration."""
        super().__init__(config)
        self._client = None
        self._rate_limiter = None
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize error handling components
        self._initialize_error_handling(config)

        # Initialize monitoring
        self._initialize_monitoring(config)

    def _initialize_error_handling(self, config: Dict[str, Any]) -> None:
        """Initialize the comprehensive error handling system."""
        # Get error handling configuration
        error_handling_config = self.get_config_value("error_handling", {})

        # Initialize error classifier
        self.error_classifier = ErrorClassifier()

        # Initialize metrics collector
        self.metrics_collector = MetricsCollector()

        # Initialize error handling metrics
        self.error_handling_metrics = ErrorHandlingMetrics(self.metrics_collector)

        # Initialize circuit breaker configuration
        circuit_config = self._create_circuit_breaker_config(error_handling_config)
        operation_circuit_config = self._create_operation_circuit_breaker_config(
            error_handling_config
        )

        # Initialize retry configuration
        retry_config = self._create_retry_config(error_handling_config)

        # Initialize resilient operation manager
        self.resilient_manager = ResilientOperationManager(
            circuit_breaker_config=circuit_config,
            operation_circuit_breaker_config=operation_circuit_config,
            retry_config=retry_config,
            metrics=self.error_handling_metrics,
        )

        # Initialize graceful degradation manager
        self.graceful_degradation_manager = create_graceful_degradation_manager(
            self.resilient_manager,
        )

        # Initialize health check manager
        self.health_check_manager = HealthCheckManager(
            self.resilient_manager,
        )

    def _create_circuit_breaker_config(
        self, error_handling_config: Dict[str, Any]
    ) -> CircuitBreakerConfig:
        """Create circuit breaker configuration from config."""
        circuit_config = error_handling_config.get("circuit_breaker", {})
        return CircuitBreakerConfig(
            failure_threshold=circuit_config.get("failure_threshold", 5),
            recovery_timeout=circuit_config.get("recovery_timeout", 60.0),
            success_threshold=circuit_config.get("success_threshold", 3),
            timeout=circuit_config.get("timeout", 30.0),
        )

    def _create_operation_circuit_breaker_config(
        self, error_handling_config: Dict[str, Any]
    ) -> OperationCircuitBreakerConfig:
        """Create operation-specific circuit breaker configuration."""
        return OperationCircuitBreakerConfig()

    def _create_retry_config(
        self, error_handling_config: Dict[str, Any]
    ) -> RetryConfig:
        """Create retry configuration from config."""
        retry_config = error_handling_config.get("retry", {})
        return RetryConfig(
            max_retries=retry_config.get("max_retries", 3),
            base_delay=retry_config.get("base_delay", 1.0),
            max_delay=retry_config.get("max_delay", 60.0),
            backoff_factor=retry_config.get("backoff_factor", 2.0),
            jitter=retry_config.get("jitter", True),
        )

    def _initialize_monitoring(self, config: Dict[str, Any]) -> None:
        """Initialize monitoring components."""
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
            self.operation_metrics = OperationMetrics(self.metrics_collector)
        else:
            self.monitoring_manager = None
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
        """Execute an operation with comprehensive error handling."""
        try:
            # Use the resilient manager for circuit breaker and retry logic
            result = await self.resilient_manager.execute_resilient_operation(
                operation_name, func, *args, **kwargs
            )

            # Record success metrics
            await self.error_handling_metrics.record_operation_success(
                operation_name, "unknown", 0.0, 0
            )

            return result

        except Exception as e:
            # Classify the error
            error_classification = self.error_classifier.classify_error(e)

            # Record error metrics
            await self.error_handling_metrics.record_error(
                error_classification.error_type,
                operation_name,
                "unknown",
                error_classification.is_retryable,
            )

            # Use graceful degradation if available
            if self.graceful_degradation_manager:
                try:
                    return await self.graceful_degradation_manager.execute_with_graceful_degradation(
                        operation_name, func, *args, **kwargs
                    )
                except Exception as degradation_error:
                    self.logger.error(
                        f"Graceful degradation failed for {operation_name}: {degradation_error}"
                    )
                    raise e from degradation_error

            raise e

    async def _execute_with_error_handling(
        self, operation_name: str, func: Callable, *args, **kwargs
    ) -> Any:
        """Execute an operation with full error handling including graceful degradation."""
        try:
            return await self._execute_resilient_operation(
                operation_name, func, *args, **kwargs
            )
        except Exception as e:
            # If graceful degradation is available, try it
            if self.graceful_degradation_manager:
                try:
                    return await self.graceful_degradation_manager.execute_with_graceful_degradation(
                        operation_name, func, *args, **kwargs
                    )
                except Exception as degradation_error:
                    self.logger.error(
                        f"Graceful degradation failed for {operation_name}: {degradation_error}"
                    )
                    raise e from degradation_error
            raise e

    async def get_health_status(self) -> ProviderHealth:
        """Get comprehensive health status including error handling metrics."""
        try:
            # Get basic provider health
            basic_health = await self._get_basic_health_status()

            # Get error handling health
            error_handling_health = self.health_check_manager.get_overall_health()

            # Combine health information
            overall_status = "healthy"
            if (
                basic_health.status != "healthy"
                or error_handling_health.get("status") != "healthy"
            ):
                overall_status = "unhealthy"

            return ProviderHealth(
                status=overall_status,
                message=f"Provider health: {basic_health.message}. Error handling: {error_handling_health.get('message', 'Unknown')}",
                additional_info={
                    "basic_health": basic_health.additional_info,
                    "error_handling_health": error_handling_health,
                    "circuit_breakers": self.health_check_manager.get_circuit_breaker_health(),
                    "operation_types": self.health_check_manager.get_operation_type_health(),
                },
            )
        except Exception as e:
            return ProviderHealth(
                status="unhealthy",
                message=f"Health check failed: {str(e)}",
                additional_info={"error": str(e)},
            )

    async def _get_basic_health_status(self) -> ProviderHealth:
        """Get basic provider health status. To be implemented by subclasses."""
        return ProviderHealth(
            status="healthy", message="Basic health check passed", additional_info={}
        )

    async def handle_operation_failure(self, operation: str, error: Exception) -> bool:
        """Enhanced operation failure handling with error classification."""
        self.logger.error(f"Operation {operation} failed: {str(error)}")

        # Classify the error
        error_classification = self.error_classifier.classify_error(error)

        # Record error metrics
        await self.error_handling_metrics.record_error(
            error_classification.error_type,
            operation,
            "unknown",
            error_classification.is_retryable,
        )

        # Check if this is a retryable error
        if error_classification.is_retryable:
            self.logger.info(
                f"Error is retryable, attempting retry for operation: {operation}"
            )
            return True

        self.logger.warning(f"Error is not retryable for operation: {operation}")
        return False

    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Enhanced batch operations with comprehensive error handling."""
        results = []

        for i, operation in enumerate(operations):
            try:
                result = await self._execute_with_error_handling(
                    f"batch_operation_{i}", self._execute_single_operation, operation
                )
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

                # Classify the error
                error_classification = self.error_classifier.classify_error(e)

                # Record error metrics
                await self.error_handling_metrics.record_operation_failure(
                    f"batch_operation_{i}",
                    "unknown",
                    0.0,
                    error_classification.error_type,
                    0,
                )

                results.append(
                    OperationResult(
                        operation_id=f"batch_{i}",
                        success=False,
                        message=f"Operation failed: {str(e)}",
                        file_path=operation.file_path,
                        error_details=str(e),
                        additional_info={
                            "operation_type": operation.operation_type,
                            "error_classification": {
                                "error_type": error_classification.error_type.value,
                                "is_retryable": error_classification.is_retryable,
                                "retry_delay": error_classification.retry_delay,
                            },
                        },
                    )
                )

        return results

    async def _execute_single_operation(self, operation: BatchOperation) -> Any:
        """Execute a single operation from a batch."""
        operation_type = operation.operation_type

        if operation_type == "update_file":
            if operation.file_path is None or operation.content is None:
                raise ValueError(
                    "file_path and content are required for update_file operation"
                )
            return await self.commit_changes(
                operation.file_path, operation.content, "Batch update"
            )
        elif operation_type == "create_file":
            if operation.file_path is None or operation.content is None:
                raise ValueError(
                    "file_path and content are required for create_file operation"
                )
            return await self.commit_changes(
                operation.file_path, operation.content, "Batch create"
            )
        elif operation_type == "delete_file":
            if operation.file_path is None:
                raise ValueError("file_path is required for delete_file operation")
            # Implement delete file logic here
            return True
        else:
            raise ValueError(f"Unsupported operation type: {operation_type}")

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with fallback to default."""
        return self.config.get(key, default)

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self._teardown_client()

        # Cleanup error handling components
        if hasattr(self, "health_check_manager"):
            # Health check manager cleanup if needed
            pass

        if hasattr(self, "graceful_degradation_manager"):
            # Graceful degradation manager cleanup if needed
            pass

    # Abstract methods that must be implemented by subclasses
    async def get_capabilities(self) -> Any:
        """Get provider capabilities. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement get_capabilities")

    async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
        """Get file content. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement get_file_content")

    async def apply_remediation(
        self, path: str, content: str, message: str, branch: Optional[str] = None
    ) -> RemediationResult:
        """Apply remediation. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement apply_remediation")

    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if file exists. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement file_exists")

    async def get_file_info(self, path: str, ref: Optional[str] = None) -> Any:
        """Get file information. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement get_file_info")

    async def list_files(self, path: str = "", ref: Optional[str] = None) -> List[Any]:
        """List files. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement list_files")

    async def generate_patch(self, original: str, modified: str) -> str:
        """Generate patch. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement generate_patch")

    async def apply_patch(self, patch: str, file_path: str) -> bool:
        """Apply patch. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement apply_patch")

    async def commit_changes(
        self, file_path: str, content: str, message: str, branch: Optional[str] = None
    ) -> Optional[str]:
        """Commit changes. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement commit_changes")

    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create branch. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement create_branch")

    async def delete_branch(self, name: str) -> bool:
        """Delete branch. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement delete_branch")

    async def list_branches(self) -> List[Any]:
        """List branches. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement list_branches")

    async def get_branch_info(self, name: str) -> Optional[Any]:
        """Get branch info. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement get_branch_info")

    async def get_current_branch(self) -> str:
        """Get current branch. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement get_current_branch")

    async def get_repository_info(self) -> Any:
        """Get repository info. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement get_repository_info")

    async def check_conflicts(
        self, path: str, content: str, branch: Optional[str] = None
    ) -> bool:
        """Check conflicts. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement check_conflicts")

    async def resolve_conflicts(
        self, path: str, content: str, strategy: str = "manual"
    ) -> bool:
        """Resolve conflicts. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement resolve_conflicts")

    async def get_file_history(self, path: str, limit: int = 10) -> List[Any]:
        """Get file history. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement get_file_history")

    async def diff_between_commits(self, base_sha: str, head_sha: str) -> str:
        """Get diff between commits. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement diff_between_commits")

    async def create_pull_request(
        self,
        title: str,
        description: str,
        head_branch: str,
        base_branch: str,
        **kwargs: Any,
    ) -> RemediationResult:
        """Create pull request. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement create_pull_request")

    async def create_merge_request(
        self,
        title: str,
        description: str,
        head_branch: str,
        base_branch: str,
        **kwargs: Any,
    ) -> RemediationResult:
        """Create merge request. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement create_merge_request")
