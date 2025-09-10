# gemini_sre_agent/source_control/base.py

"""
Abstract base class for source control providers with async context manager support.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import (
    BatchOperation,
    BranchInfo,
    ConflictInfo,
    FileInfo,
    OperationResult,
    ProviderCapabilities,
    ProviderHealth,
    RemediationResult,
    RepositoryInfo,
)


class SourceControlProvider(ABC):
    """Abstract base class defining the interface for source control providers."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration."""
        self.config = config
        self._initialized = False
        self.logger = logging.getLogger(self.__class__.__name__)

    # Core connection and validation methods
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the connection to the source control system is working."""
        pass

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Validate that the current credentials are valid."""
        pass

    @abstractmethod
    async def refresh_credentials(self) -> bool:
        """Refresh the credentials used for authentication."""
        pass

    # Repository information methods
    @abstractmethod
    async def get_repository_info(self) -> RepositoryInfo:
        """Get information about the repository."""
        pass

    @abstractmethod
    async def get_capabilities(self) -> ProviderCapabilities:
        """Get the capabilities supported by this provider."""
        pass

    @abstractmethod
    async def get_health_status(self) -> ProviderHealth:
        """Get the health status of the provider."""
        pass

    # File operations
    @abstractmethod
    async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
        """Retrieve content of a file at a specific path and reference."""
        pass

    @abstractmethod
    async def get_file_info(self, path: str, ref: Optional[str] = None) -> FileInfo:
        """Get information about a file."""
        pass

    @abstractmethod
    async def file_exists(self, path: str, ref: Optional[str] = None) -> bool:
        """Check if a file exists at the given path."""
        pass

    # Branch operations
    @abstractmethod
    async def create_branch(self, name: str, base_ref: Optional[str] = None) -> bool:
        """Create a new branch from the specified reference."""
        pass

    @abstractmethod
    async def delete_branch(self, name: str) -> bool:
        """Delete the specified branch."""
        pass

    @abstractmethod
    async def list_branches(self) -> List[BranchInfo]:
        """List all branches in the repository."""
        pass

    @abstractmethod
    async def get_branch_info(self, name: str) -> Optional[BranchInfo]:
        """Get information about a specific branch."""
        pass

    # Remediation operations
    @abstractmethod
    async def apply_remediation(
        self, path: str, content: str, message: str, branch: Optional[str] = None
    ) -> RemediationResult:
        """Apply a remediation to a file and commit the changes."""
        pass

    @abstractmethod
    async def create_pull_request(
        self, title: str, description: str, head_branch: str, base_branch: str, **kwargs
    ) -> RemediationResult:
        """Create a pull request (if supported by provider)."""
        pass

    @abstractmethod
    async def create_merge_request(
        self, title: str, description: str, head_branch: str, base_branch: str, **kwargs
    ) -> RemediationResult:
        """Create a merge request (if supported by provider)."""
        pass

    # Conflict resolution
    @abstractmethod
    async def check_conflicts(
        self, path: str, content: str, branch: Optional[str] = None
    ) -> bool:
        """Check if applying content to a file would cause conflicts."""
        pass

    @abstractmethod
    async def resolve_conflicts(
        self, path: str, content: str, strategy: str = "manual"
    ) -> bool:
        """Attempt to resolve conflicts for a file."""
        pass

    @abstractmethod
    async def get_conflict_info(self, path: str) -> Optional[ConflictInfo]:
        """Get detailed information about conflicts in a file."""
        pass

    # Batch operations
    @abstractmethod
    async def batch_operations(
        self, operations: List[BatchOperation]
    ) -> List[OperationResult]:
        """Execute multiple operations as a batch."""
        pass

    # Error handling and recovery
    @abstractmethod
    async def handle_operation_failure(self, operation: str, error: Exception) -> bool:
        """Handle a failure during an operation."""
        pass

    @abstractmethod
    async def retry_operation(self, operation: str, max_retries: int = 3) -> bool:
        """Retry a failed operation."""
        pass

    # Async context manager support
    async def __aenter__(self) -> "SourceControlProvider":
        """Initialize resources when entering the context."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up resources when exiting the context."""
        await self.cleanup()

    async def initialize(self) -> None:
        """Initialize resources needed by the provider."""
        if self._initialized:
            return

        self.logger.info("Initializing source control provider")
        await self._setup_client()
        self._initialized = True
        self.logger.info("Source control provider initialized successfully")

    async def cleanup(self) -> None:
        """Clean up resources used by the provider."""
        if not self._initialized:
            return

        self.logger.info("Cleaning up source control provider")
        await self._teardown_client()
        self._initialized = False
        self.logger.info("Source control provider cleaned up successfully")

    @abstractmethod
    async def _setup_client(self) -> None:
        """Set up the client for the source control system."""
        pass

    @abstractmethod
    async def _teardown_client(self) -> None:
        """Tear down the client for the source control system."""
        pass

    # Utility methods
    def is_initialized(self) -> bool:
        """Check if the provider is initialized."""
        return self._initialized

    async def ensure_initialized(self) -> None:
        """Ensure the provider is initialized."""
        if not self._initialized:
            await self.initialize()

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with optional default."""
        return self.config.get(key, default)

    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration values."""
        self.config.update(updates)

    # Health check and monitoring
    async def health_check(self) -> ProviderHealth:
        """Perform a comprehensive health check."""
        try:
            start_time = asyncio.get_event_loop().time()

            # Test basic connectivity
            connection_ok = await self.test_connection()

            # Test credentials
            credentials_ok = await self.validate_credentials()

            # Calculate response time
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000

            is_healthy = connection_ok and credentials_ok

            return ProviderHealth(
                status="healthy" if is_healthy else "unhealthy",
                message="Health check passed" if is_healthy else "Health check failed",
                is_healthy=is_healthy,
                last_check=datetime.now(),
                response_time_ms=response_time,
                error_message=None if is_healthy else "Health check failed",
                warnings=[],
                additional_info={},
            )

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return ProviderHealth(
                status="unhealthy",
                message=f"Health check failed: {e}",
                is_healthy=False,
                last_check=datetime.now(),
                response_time_ms=None,
                error_message=str(e),
                warnings=[],
                additional_info={},
            )
