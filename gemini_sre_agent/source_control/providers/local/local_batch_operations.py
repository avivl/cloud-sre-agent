# gemini_sre_agent/source_control/providers/local/local_batch_operations.py

"""
Local batch operations module.

This module handles batch operations for the local provider.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...models import (
    BatchOperation,
    OperationResult,
)


class LocalBatchOperations:
    """Handles batch operations for local filesystem."""

    def __init__(
        self,
        root_path: Path,
        default_encoding: str,
        backup_files: bool,
        backup_directory: Optional[str],
        logger: logging.Logger,
        error_handling_components: Optional[Dict[str, Any]] = None,
    ):
        """Initialize batch operations."""
        self.root_path = root_path
        self.default_encoding = default_encoding
        self.backup_files = backup_files
        self.backup_directory = backup_directory
        self.logger = logger
        self.error_handling_components = error_handling_components

    async def _execute_with_error_handling(
        self, operation_name: str, func, *args, **kwargs
    ):
        """Execute a function with error handling if available."""
        if (
            self.error_handling_components
            and "resilient_manager" in self.error_handling_components
        ):
            resilient_manager = self.error_handling_components["resilient_manager"]
            return await resilient_manager.execute_with_retry(
                operation_name, func, *args, **kwargs
            )

        # Fall back to direct execution
        return await func(*args, **kwargs)

    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Execute multiple operations in batch."""

        async def _batch():
            results = []

            for operation in operations:
                try:
                    if operation.operation_type == "create_file":
                        result = self._create_file(operation)
                    elif operation.operation_type == "update_file":
                        result = self._update_file(operation)
                    elif operation.operation_type == "delete_file":
                        result = self._delete_file(operation)
                    else:
                        result = OperationResult(
                            operation_id=operation.operation_id,
                            success=False,
                            message=f"Unknown operation type: {operation.operation_type}",
                            file_path=operation.file_path,
                            error_details=f"Unknown operation type: {operation.operation_type}",
                            additional_info={},
                        )

                    results.append(result)
                except Exception as e:
                    self.logger.error(
                        f"Failed to execute operation {operation.operation_id}: {e}"
                    )
                    results.append(
                        OperationResult(
                            operation_id=operation.operation_id,
                            success=False,
                            message=f"Operation failed: {e}",
                            file_path=operation.file_path,
                            error_details=str(e),
                            additional_info={},
                        )
                    )

            return results

        return await self._execute_with_error_handling("batch_operations", _batch)

    def _create_file(self, operation: BatchOperation) -> OperationResult:
        """Create a file."""
        try:
            file_path = self.root_path / operation.file_path

            # Create directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file content
            with open(file_path, "w", encoding=self.default_encoding) as f:
                f.write(operation.content or "")

            return OperationResult(
                operation_id=operation.operation_id,
                success=True,
                message=f"Created file {operation.file_path}",
                file_path=operation.file_path,
                error_details="",
                additional_info={},
            )
        except Exception as e:
            return OperationResult(
                operation_id=operation.operation_id,
                success=False,
                message=f"Failed to create file: {e}",
                file_path=operation.file_path,
                error_details=str(e),
                additional_info={},
            )

    def _update_file(self, operation: BatchOperation) -> OperationResult:
        """Update a file."""
        try:
            file_path = self.root_path / operation.file_path

            if not file_path.exists():
                return OperationResult(
                    operation_id=operation.operation_id,
                    success=False,
                    message=f"File {operation.file_path} does not exist",
                    file_path=operation.file_path,
                    error_details="File does not exist",
                    additional_info={},
                )

            # Create backup if enabled
            if self.backup_files:
                self._create_backup(file_path)

            # Write new content
            with open(file_path, "w", encoding=self.default_encoding) as f:
                f.write(operation.content or "")

            return OperationResult(
                operation_id=operation.operation_id,
                success=True,
                message=f"Updated file {operation.file_path}",
                file_path=operation.file_path,
                error_details="",
                additional_info={},
            )
        except Exception as e:
            return OperationResult(
                operation_id=operation.operation_id,
                success=False,
                message=f"Failed to update file: {e}",
                file_path=operation.file_path,
                error_details=str(e),
                additional_info={},
            )

    def _delete_file(self, operation: BatchOperation) -> OperationResult:
        """Delete a file."""
        try:
            file_path = self.root_path / operation.file_path

            if not file_path.exists():
                return OperationResult(
                    operation_id=operation.operation_id,
                    success=False,
                    message=f"File {operation.file_path} does not exist",
                    file_path=operation.file_path,
                    error_details="File does not exist",
                    additional_info={},
                )

            # Create backup if enabled
            if self.backup_files:
                self._create_backup(file_path)

            # Delete file
            file_path.unlink()

            return OperationResult(
                operation_id=operation.operation_id,
                success=True,
                message=f"Deleted file {operation.file_path}",
                file_path=operation.file_path,
                error_details="",
                additional_info={},
            )
        except Exception as e:
            return OperationResult(
                operation_id=operation.operation_id,
                success=False,
                message=f"Failed to delete file: {e}",
                file_path=operation.file_path,
                error_details=str(e),
                additional_info={},
            )

    def _create_backup(self, file_path: Path) -> None:
        """Create a backup of a file."""
        try:
            if not file_path.exists():
                return

            backup_dir = self.backup_directory
            if backup_dir is None:
                backup_dir = self.root_path / ".backups"
            else:
                backup_dir = Path(backup_dir)

            backup_dir.mkdir(parents=True, exist_ok=True)

            # Create backup with timestamp
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.name}.{timestamp}.bak"
            backup_path = backup_dir / backup_name

            import shutil

            shutil.copy2(file_path, backup_path)
            self.logger.info(f"Created backup: {backup_path}")
        except Exception as e:
            self.logger.error(f"Failed to create backup for {file_path}: {e}")
