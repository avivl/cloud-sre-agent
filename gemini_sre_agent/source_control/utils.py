# gemini_sre_agent/source_control/utils.py

"""
Utility functions for source control operations.
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Type

from .base import SourceControlProvider
from .models import OperationStatus, ProviderHealth


async def with_provider(
    provider_class: Type[SourceControlProvider],
    config: Dict[str, Any],
    operation: Callable[[SourceControlProvider], Awaitable[Any]],
) -> Any:
    """
    Execute an operation with a provider using async context manager.

    Args:
        provider_class: The provider class to instantiate
        config: Configuration for the provider
        operation: Async function that takes a provider and returns a result

    Returns:
        The result of the operation

    Example:
        result = await with_provider(
            GitHubProvider,
            config,
            lambda provider: provider.get_file_content('path/to/file')
        )
    """
    async with provider_class(config) as provider:
        return await operation(provider)


async def execute_with_retry(
    operation: Callable[[], Awaitable[Any]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
) -> Any:
    """
    Execute an operation with retry logic and exponential backoff.

    Args:
        operation: The async operation to execute
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Factor to multiply delay by for each retry

    Returns:
        The result of the operation

    Raises:
        Exception: The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await operation()
        except Exception as e:
            last_exception = e

            if attempt == max_retries:
                # Last attempt failed, raise the exception
                raise e

            # Calculate delay with exponential backoff
            delay = min(base_delay * (backoff_factor**attempt), max_delay)

            logging.getLogger(__name__).warning(
                f"Operation failed (attempt {attempt + 1}/{max_retries + 1}), "
                f"retrying in {delay:.2f}s: {e}"
            )

            await asyncio.sleep(delay)

    # This should never be reached, but just in case
    if last_exception is not None:
        raise last_exception
    raise RuntimeError("Retry operation failed without exception")


async def health_check_providers(
    providers: list[SourceControlProvider],
) -> Dict[str, ProviderHealth]:
    """
    Perform health checks on multiple providers concurrently.

    Args:
        providers: List of provider instances to check

    Returns:
        Dictionary mapping provider names to their health status
    """

    async def check_provider(
        provider: SourceControlProvider,
    ) -> tuple[str, ProviderHealth]:
        health = await provider.get_health_status()
        return provider.__class__.__name__, health

    # Execute all health checks concurrently
    results = await asyncio.gather(
        *[check_provider(provider) for provider in providers], return_exceptions=True
    )

    health_status = {}
    for result in results:
        if isinstance(result, Exception):
            logging.getLogger(__name__).error(f"Health check failed: {result}")
            continue

        if isinstance(result, tuple) and len(result) == 2:
            name, health = result
            health_status[name] = health

    return health_status


def validate_operation_status(status: OperationStatus) -> bool:
    """
    Validate that an operation status is valid.

    Args:
        status: The operation status to validate

    Returns:
        True if the status is valid, False otherwise
    """
    return status in OperationStatus


def is_successful_status(status: OperationStatus) -> bool:
    """
    Check if an operation status indicates success.

    Args:
        status: The operation status to check

    Returns:
        True if the status indicates success, False otherwise
    """
    return status == OperationStatus.SUCCESS


def is_retryable_status(status: OperationStatus) -> bool:
    """
    Check if an operation status indicates the operation should be retried.

    Args:
        status: The operation status to check

    Returns:
        True if the status indicates the operation should be retried, False otherwise
    """
    retryable_statuses = {
        OperationStatus.RATE_LIMITED,
        OperationStatus.TIMEOUT,
        OperationStatus.PENDING,
    }
    return status in retryable_statuses


def is_fatal_status(status: OperationStatus) -> bool:
    """
    Check if an operation status indicates a fatal error that should not be retried.

    Args:
        status: The operation status to check

    Returns:
        True if the status indicates a fatal error, False otherwise
    """
    fatal_statuses = {
        OperationStatus.UNAUTHORIZED,
        OperationStatus.NOT_FOUND,
        OperationStatus.INVALID_INPUT,
    }
    return status in fatal_statuses


async def timeout_operation(
    operation: Callable[[], Awaitable[Any]], timeout_seconds: float
) -> Any:
    """
    Execute an operation with a timeout.

    Args:
        operation: The async operation to execute
        timeout_seconds: Timeout in seconds

    Returns:
        The result of the operation

    Raises:
        asyncio.TimeoutError: If the operation times out
    """
    return await asyncio.wait_for(operation(), timeout=timeout_seconds)


def create_operation_id(
    operation_type: str, path: Optional[str] = None, timestamp: Optional[float] = None
) -> str:
    """
    Create a unique operation ID.

    Args:
        operation_type: Type of operation
        path: Optional file path
        timestamp: Optional timestamp (defaults to current time)

    Returns:
        A unique operation ID
    """
    if timestamp is None:
        timestamp = asyncio.get_event_loop().time()

    if path is not None:
        # Sanitize path for use in ID
        safe_path = path.replace("/", "_").replace("\\", "_")
        return f"{operation_type}_{safe_path}_{int(timestamp)}"
    else:
        return f"{operation_type}_{int(timestamp)}"


def sanitize_branch_name(name: str) -> str:
    """
    Sanitize a branch name to be valid for most source control systems.

    Args:
        name: The branch name to sanitize

    Returns:
        A sanitized branch name
    """
    # Remove or replace invalid characters
    invalid_chars = [" ", "~", "^", ":", "?", "*", "[", "\\", "..", "@{", "//"]

    sanitized = name
    for char in invalid_chars:
        sanitized = sanitized.replace(char, "_")

    # Remove leading dots and slashes
    sanitized = sanitized.lstrip("./")

    # Ensure it's not empty and not too long
    if not sanitized:
        sanitized = "branch"

    if len(sanitized) > 100:
        sanitized = sanitized[:100]

    return sanitized


def sanitize_commit_message(message: str) -> str:
    """
    Sanitize a commit message to be valid for most source control systems.

    Args:
        message: The commit message to sanitize

    Returns:
        A sanitized commit message
    """
    # Remove or replace invalid characters
    sanitized = message.replace("\r\n", "\n").replace("\r", "\n")

    # Remove trailing whitespace from each line
    lines = [line.rstrip() for line in sanitized.split("\n")]

    # Remove empty lines at the end
    while lines and not lines[-1]:
        lines.pop()

    # Join lines back together
    sanitized = "\n".join(lines)

    # Ensure it's not empty
    if not sanitized.strip():
        sanitized = "No message"

    return sanitized
