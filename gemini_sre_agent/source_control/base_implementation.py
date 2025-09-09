# gemini_sre_agent/source_control/base_implementation.py

"""
Base implementation of SourceControlProvider with common functionality.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .base import SourceControlProvider
from .models import (
    BatchOperation,
    ConflictInfo,
    OperationResult,
    OperationStatus,
    ProviderHealth,
    RemediationResult,
)


class BaseSourceControlProvider(SourceControlProvider):
    """Base implementation of SourceControlProvider with common functionality."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration."""
        super().__init__(config)
        self._client = None
        self._rate_limiter = None
        self._retry_config = self.get_config_value("retry", {})
        self._timeout_config = self.get_config_value("timeout", {})

    async def _setup_client(self) -> None:
        """Set up the client for the source control system."""
        # To be implemented by subclasses
        pass

    async def _teardown_client(self) -> None:
        """Tear down the client for the source control system."""
        # To be implemented by subclasses
        if self._client:
            self._client = None

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
                        status=OperationStatus.SUCCESS,
                        success=True,
                        result=result,
                        details={"operation_type": operation.operation_type},
                    )
                )
            except Exception as e:
                self.logger.error(f"Batch operation {i} failed: {e}")
                results.append(
                    OperationResult(
                        operation_id=f"batch_{i}",
                        status=OperationStatus.FAILURE,
                        success=False,
                        error=str(e),
                        details={"operation_type": operation.operation_type},
                    )
                )

        return results

    async def _execute_single_operation(self, operation: BatchOperation) -> Any:
        """Execute a single operation from a batch."""
        operation_type = operation.operation_type

        if operation_type == "update_file":
            if operation.path is None or operation.content is None:
                raise ValueError(
                    "Path and content are required for update_file operation"
                )
            return await self.apply_remediation(
                operation.path, operation.content, operation.message or "Batch update"
            )
        elif operation_type == "delete_file":
            # This would need to be implemented by subclasses
            raise NotImplementedError("Delete file operation not implemented")
        elif operation_type == "create_branch":
            name = operation.parameters.get("name")
            if name is None:
                raise ValueError("Branch name is required for create_branch operation")
            return await self.create_branch(name, operation.parameters.get("base_ref"))
        else:
            raise ValueError(f"Unknown operation type: {operation_type}")

    async def get_health_status(self) -> ProviderHealth:
        """Get the health status of the provider."""
        return await self.health_check()

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
        status: OperationStatus,
        commit_id: Optional[str] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> RemediationResult:
        """Helper method to create a RemediationResult."""
        return RemediationResult(
            success=success,
            status=status,
            commit_id=commit_id,
            message=message,
            error=error,
            details=details or {},
        )

    def _create_operation_result(
        self,
        operation_id: str,
        success: bool,
        status: OperationStatus,
        result: Any = None,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> OperationResult:
        """Helper method to create an OperationResult."""
        return OperationResult(
            operation_id=operation_id,
            status=status,
            success=success,
            result=result,
            error=error,
            details=details or {},
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
