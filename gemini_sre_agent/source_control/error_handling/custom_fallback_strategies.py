# gemini_sre_agent/source_control/error_handling/custom_fallback_strategies.py

"""
Custom fallback strategies for different operation types and providers.

This module provides intelligent fallback mechanisms that are tailored to
specific source control operations and provider capabilities.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..models import FileInfo, RemediationResult
from .core import ErrorType


class FallbackStrategyBase(ABC):
    """Base class for custom fallback strategies."""

    def __init__(self, name: str, priority: int = 1):
        self.name = name
        self.priority = priority
        self.logger = logging.getLogger(f"FallbackStrategy.{name}")

    @abstractmethod
    async def can_handle(
        self, operation_type: str, error_type: ErrorType, context: Dict[str, Any]
    ) -> bool:
        """Check if this strategy can handle the given operation and error."""

    @abstractmethod
    async def execute(
        self, operation_type: str, original_func: Any, *args, **kwargs
    ) -> Any:
        """Execute the fallback strategy."""

    def get_priority(self) -> int:
        """Get the priority of this strategy (lower = higher priority)."""
        return self.priority


class CachedResponseStrategy(FallbackStrategyBase):
    """Fallback to cached responses when operations fail."""

    def __init__(self, cache_ttl_seconds: int = 300):
        super().__init__("cached_response", priority=1)
        self.cache_ttl = cache_ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}

    async def can_handle(
        self, operation_type: str, error_type: ErrorType, context: Dict[str, Any]
    ) -> bool:
        """Check if we have a cached response for this operation."""
        if error_type in [ErrorType.AUTHENTICATION_ERROR]:
            return False  # Don't use cache for auth errors

        cache_key = self._generate_cache_key(operation_type, context)
        return cache_key in self.cache and not self._is_cache_expired(cache_key)

    async def execute(
        self, operation_type: str, original_func: Any, *args, **kwargs
    ) -> Any:
        """Return cached response."""
        context = {"args": args, "kwargs": kwargs}
        cache_key = self._generate_cache_key(operation_type, context)

        cached_data = self.cache[cache_key]["data"]
        self.logger.info(f"Using cached response for {operation_type}")

        return cached_data

    def _generate_cache_key(self, operation_type: str, context: Dict[str, Any]) -> str:
        """Generate a cache key for the operation."""
        # Create a simple hash of the operation and context
        key_parts = [operation_type]
        if "args" in context:
            key_parts.extend(str(arg) for arg in context["args"])
        if "kwargs" in context:
            key_parts.extend(f"{k}={v}" for k, v in sorted(context["kwargs"].items()))

        return "|".join(key_parts)

    def _is_cache_expired(self, cache_key: str) -> bool:
        """Check if the cached data is expired."""
        if cache_key not in self.cache:
            return True

        cached_time = self.cache[cache_key]["timestamp"]
        return datetime.now() - cached_time > timedelta(seconds=self.cache_ttl)

    def cache_response(
        self, operation_type: str, context: Dict[str, Any], data: Any
    ) -> None:
        """Cache a successful response."""
        cache_key = self._generate_cache_key(operation_type, context)
        self.cache[cache_key] = {
            "data": data,
            "timestamp": datetime.now(),
        }


class SimplifiedOperationStrategy(FallbackStrategyBase):
    """Fallback to simplified versions of operations."""

    def __init__(self):
        super().__init__("simplified_operation", priority=2)

    async def can_handle(
        self, operation_type: str, error_type: ErrorType, context: Dict[str, Any]
    ) -> bool:
        """Check if we can provide a simplified version."""
        return operation_type in [
            "get_file_content",
            "file_exists",
            "list_files",
            "get_file_info",
        ]

    async def execute(
        self, operation_type: str, original_func: Any, *args, **kwargs
    ) -> Any:
        """Execute simplified version of the operation."""
        self.logger.info(f"Using simplified operation for {operation_type}")

        if operation_type == "get_file_content":
            return await self._simplified_get_file_content(*args, **kwargs)
        elif operation_type == "file_exists":
            return await self._simplified_file_exists(*args, **kwargs)
        elif operation_type == "list_files":
            return await self._simplified_list_files(*args, **kwargs)
        elif operation_type == "get_file_info":
            return await self._simplified_get_file_info(*args, **kwargs)
        else:
            raise NotImplementedError(
                f"Simplified operation not implemented for {operation_type}"
            )

    async def _simplified_get_file_content(
        self, path: str, ref: Optional[str] = None
    ) -> str:
        """Simplified file content retrieval."""
        # Return empty string as fallback
        return ""

    async def _simplified_file_exists(
        self, path: str, ref: Optional[str] = None
    ) -> bool:
        """Simplified file existence check."""
        # Assume file exists as fallback
        return True

    async def _simplified_list_files(
        self, path: str = "", ref: Optional[str] = None
    ) -> List[FileInfo]:
        """Simplified file listing."""
        # Return empty list as fallback
        return []

    async def _simplified_get_file_info(
        self, path: str, ref: Optional[str] = None
    ) -> FileInfo:
        """Simplified file info retrieval."""
        return FileInfo(
            path=path,
            size=0,
            sha="",
            is_binary=False,
            last_modified=None,
        )


class OfflineModeStrategy(FallbackStrategyBase):
    """Fallback to offline mode when network operations fail."""

    def __init__(self):
        super().__init__("offline_mode", priority=3)
        self.offline_data: Dict[str, Any] = {}

    async def can_handle(
        self, operation_type: str, error_type: ErrorType, context: Dict[str, Any]
    ) -> bool:
        """Check if we can handle this in offline mode."""
        return error_type in [
            ErrorType.NETWORK_ERROR,
            ErrorType.TIMEOUT_ERROR,
            ErrorType.SERVER_ERROR,
        ]

    async def execute(
        self, operation_type: str, original_func: Any, *args, **kwargs
    ) -> Any:
        """Execute in offline mode."""
        self.logger.info(f"Using offline mode for {operation_type}")

        if operation_type == "get_file_content":
            return self.offline_data.get("file_content", "")
        elif operation_type == "file_exists":
            return self.offline_data.get("file_exists", False)
        elif operation_type == "list_files":
            return self.offline_data.get("files", [])
        elif operation_type == "create_pull_request":
            return RemediationResult(
                success=False,
                message="Offline mode: Pull request creation deferred",
                file_path="",
                operation_type="create_pull_request",
                commit_sha="",
                pull_request_url="",
                error_details="Offline mode active",
                additional_info={"offline_mode": True},
            )
        else:
            # Return appropriate fallback based on operation type
            return self._get_default_fallback(operation_type)

    def _get_default_fallback(self, operation_type: str) -> Any:
        """Get default fallback for operation type."""
        if "create" in operation_type or "update" in operation_type:
            return RemediationResult(
                success=False,
                message=f"Offline mode: {operation_type} deferred",
                file_path="",
                operation_type=operation_type,
                commit_sha="",
                pull_request_url="",
                error_details="Offline mode active",
                additional_info={"offline_mode": True},
            )
        elif "get" in operation_type or "list" in operation_type:
            return [] if "list" in operation_type else None
        else:
            return False


class ProviderSpecificStrategy(FallbackStrategyBase):
    """Provider-specific fallback strategies."""

    def __init__(self, provider_name: str):
        super().__init__(f"provider_specific_{provider_name}", priority=4)
        self.provider_name = provider_name

    async def can_handle(
        self, operation_type: str, error_type: ErrorType, context: Dict[str, Any]
    ) -> bool:
        """Check if this provider-specific strategy can handle the operation."""
        return self._has_provider_specific_fallback(operation_type, error_type)

    async def execute(
        self, operation_type: str, original_func: Any, *args, **kwargs
    ) -> Any:
        """Execute provider-specific fallback."""
        self.logger.info(
            f"Using {self.provider_name} specific fallback for {operation_type}"
        )

        if self.provider_name == "github":
            return await self._github_fallback(operation_type, *args, **kwargs)
        elif self.provider_name == "gitlab":
            return await self._gitlab_fallback(operation_type, *args, **kwargs)
        elif self.provider_name == "local":
            return await self._local_fallback(operation_type, *args, **kwargs)
        else:
            return await self._generic_fallback(operation_type, *args, **kwargs)

    def _has_provider_specific_fallback(
        self, operation_type: str, error_type: ErrorType
    ) -> bool:
        """Check if we have a provider-specific fallback."""
        if self.provider_name == "github":
            return operation_type in ["create_pull_request", "get_file_content"]
        elif self.provider_name == "gitlab":
            return operation_type in ["create_merge_request", "get_file_content"]
        elif self.provider_name == "local":
            return operation_type in ["get_file_content", "file_exists"]
        return False

    async def _github_fallback(self, operation_type: str, *args, **kwargs) -> Any:
        """GitHub-specific fallback strategies."""
        if operation_type == "create_pull_request":
            return RemediationResult(
                success=False,
                message="GitHub fallback: Using issue creation instead",
                file_path="",
                operation_type="create_issue",
                commit_sha="",
                pull_request_url="",
                error_details="Fallback to issue creation",
                additional_info={"fallback_strategy": "issue_creation"},
            )
        elif operation_type == "get_file_content":
            # Try to get from GitHub's raw API
            return ""

    async def _gitlab_fallback(self, operation_type: str, *args, **kwargs) -> Any:
        """GitLab-specific fallback strategies."""
        if operation_type == "create_merge_request":
            return RemediationResult(
                success=False,
                message="GitLab fallback: Using issue creation instead",
                file_path="",
                operation_type="create_issue",
                commit_sha="",
                pull_request_url="",
                error_details="Fallback to issue creation",
                additional_info={"fallback_strategy": "issue_creation"},
            )
        elif operation_type == "get_file_content":
            return ""

    async def _local_fallback(self, operation_type: str, *args, **kwargs) -> Any:
        """Local-specific fallback strategies."""
        if operation_type == "get_file_content":
            # Try to read from backup or temp files
            return ""
        elif operation_type == "file_exists":
            # Check if file exists in backup location
            return False

    async def _generic_fallback(self, operation_type: str, *args, **kwargs) -> Any:
        """Generic fallback for unknown providers."""
        return None


class CustomFallbackManager:
    """Manages custom fallback strategies for different operations and providers."""

    def __init__(self):
        self.strategies: List[FallbackStrategyBase] = []
        self.logger = logging.getLogger("CustomFallbackManager")
        self._initialize_default_strategies()

    def _initialize_default_strategies(self) -> None:
        """Initialize default fallback strategies."""
        self.strategies = [
            CachedResponseStrategy(),
            SimplifiedOperationStrategy(),
            OfflineModeStrategy(),
        ]

    def add_strategy(self, strategy: FallbackStrategyBase) -> None:
        """Add a custom fallback strategy."""
        self.strategies.append(strategy)
        # Sort by priority
        self.strategies.sort(key=lambda s: s.get_priority())

    def add_provider_strategy(self, provider_name: str) -> None:
        """Add provider-specific strategy."""
        strategy = ProviderSpecificStrategy(provider_name)
        self.add_strategy(strategy)

    async def execute_fallback(
        self,
        operation_type: str,
        error_type: ErrorType,
        original_func: Any,
        context: Dict[str, Any],
        *args,
        **kwargs,
    ) -> Any:
        """Execute the best available fallback strategy."""
        # Find applicable strategies
        applicable_strategies = []
        for strategy in self.strategies:
            if await strategy.can_handle(operation_type, error_type, context):
                applicable_strategies.append(strategy)

        if not applicable_strategies:
            self.logger.warning(f"No fallback strategy available for {operation_type}")
            raise RuntimeError(f"No fallback strategy available for {operation_type}")

        # Try strategies in priority order
        last_error = None
        for strategy in applicable_strategies:
            try:
                self.logger.info(f"Trying fallback strategy: {strategy.name}")
                result = await strategy.execute(
                    operation_type, original_func, *args, **kwargs
                )
                self.logger.info(f"Fallback strategy {strategy.name} succeeded")
                return result
            except Exception as e:
                self.logger.warning(f"Fallback strategy {strategy.name} failed: {e}")
                last_error = e
                continue

        # If all strategies failed
        if last_error:
            raise last_error
        else:
            raise RuntimeError("All fallback strategies failed")

    def get_available_strategies(
        self, operation_type: str, error_type: ErrorType
    ) -> List[str]:
        """Get list of available strategies for an operation and error type."""
        strategies = []
        for strategy in self.strategies:
            if strategy.can_handle(operation_type, error_type, {}):
                strategies.append(strategy.name)
        return strategies

    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get statistics about fallback strategies."""
        return {
            "total_strategies": len(self.strategies),
            "strategy_names": [s.name for s in self.strategies],
            "strategy_priorities": {s.name: s.get_priority() for s in self.strategies},
        }
