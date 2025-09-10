# gemini_sre_agent/source_control/providers/github/github_batch_operations.py

"""
GitHub batch operations module.

This module handles batch operations for the GitHub provider.
"""

import logging
from typing import Any, Dict, List, Optional

from github import Github, GithubException
from github.Repository import Repository

from ...models import (
    BatchOperation,
    OperationResult,
)


class GitHubBatchOperations:
    """Handles batch operations for GitHub."""

    def __init__(
        self,
        client: Github,
        repo: Repository,
        logger: logging.Logger,
        error_handling_components: Optional[Dict[str, Any]] = None,
    ):
        """Initialize batch operations with GitHub client and repository."""
        self.client = client
        self.repo = repo
        self.logger = logger
        self.error_handling_components = error_handling_components

    async def _execute_with_error_handling(
        self, operation_name: str, func, *args, **kwargs
    ):
        """Execute an operation with error handling if available."""
        if self.error_handling_components:
            resilient_manager = self.error_handling_components.get("resilient_manager")
            if resilient_manager:
                return await resilient_manager.execute_resilient_operation(
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
                        # Create file
                        self.repo.create_file(
                            path=operation.file_path,
                            message=(
                                operation.additional_params.get(
                                    "message", "Create file"
                                )
                                if operation.additional_params
                                else "Create file"
                            ),
                            content=operation.content or "",
                            branch=operation.additional_params.get("branch") if operation.additional_params else None,  # type: ignore
                        )
                        results.append(
                            OperationResult(
                                operation_id=operation.operation_id,
                                success=True,
                                message=f"Created file {operation.file_path}",
                                file_path=operation.file_path,
                                error_details="",
                                additional_info={},
                            )
                        )
                    elif operation.operation_type == "update_file":
                        # Update file
                        file_obj = self.repo.get_contents(operation.file_path)
                        if isinstance(file_obj, list):
                            results.append(
                                OperationResult(
                                    operation_id=operation.operation_id,
                                    success=False,
                                    message=f"File {operation.file_path} is a directory",
                                    file_path=operation.file_path,
                                    error_details="File is a directory",
                                    additional_info={},
                                )
                            )
                            continue

                        self.repo.update_file(
                            path=operation.file_path,
                            message=(
                                operation.additional_params.get(
                                    "message", "Update file"
                                )
                                if operation.additional_params
                                else "Update file"
                            ),
                            content=operation.content or "",
                            sha=file_obj.sha,  # type: ignore
                            branch=operation.additional_params.get("branch") if operation.additional_params else None,  # type: ignore
                        )
                        results.append(
                            OperationResult(
                                operation_id=operation.operation_id,
                                success=True,
                                message=f"Updated file {operation.file_path}",
                                file_path=operation.file_path,
                                error_details="",
                                additional_info={},
                            )
                        )
                    elif operation.operation_type == "delete_file":
                        # Delete file
                        file_obj = self.repo.get_contents(operation.file_path)
                        if isinstance(file_obj, list):
                            results.append(
                                OperationResult(
                                    operation_id=operation.operation_id,
                                    success=False,
                                    message=f"File {operation.file_path} is a directory",
                                    file_path=operation.file_path,
                                    error_details="File is a directory",
                                    additional_info={},
                                )
                            )
                            continue

                        self.repo.delete_file(
                            path=operation.file_path,
                            message=(
                                operation.additional_params.get(
                                    "message", "Delete file"
                                )
                                if operation.additional_params
                                else "Delete file"
                            ),
                            sha=file_obj.sha,  # type: ignore
                            branch=operation.additional_params.get("branch") if operation.additional_params else None,  # type: ignore
                        )
                        results.append(
                            OperationResult(
                                operation_id=operation.operation_id,
                                success=True,
                                message=f"Deleted file {operation.file_path}",
                                file_path=operation.file_path,
                                error_details="",
                                additional_info={},
                            )
                        )
                    else:
                        results.append(
                            OperationResult(
                                operation_id=operation.operation_id,
                                success=False,
                                message=f"Unknown operation type: {operation.operation_type}",
                                file_path=operation.file_path,
                                error_details=f"Unknown operation type: {operation.operation_type}",
                                additional_info={},
                            )
                        )
                except GithubException as e:
                    results.append(
                        OperationResult(
                            operation_id=operation.operation_id,
                            success=False,
                            message=f"Failed to execute {operation.operation_type}: {e}",
                            file_path=operation.file_path,
                            error_details=str(e),
                            additional_info={},
                        )
                    )
            return results

        return await self._execute_with_error_handling("batch_operations", _batch)
