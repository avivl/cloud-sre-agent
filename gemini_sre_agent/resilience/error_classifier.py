"""Error classification system for different error types."""

import logging
from enum import Enum
from typing import Any, Dict, Optional, Type

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """Categories of errors for classification."""

    TRANSIENT = "transient"  # Temporary errors that might succeed on retry
    RATE_LIMITED = "rate_limited"  # Rate limit exceeded
    AUTHENTICATION = "authentication"  # Authentication/authorization errors
    QUOTA_EXCEEDED = "quota_exceeded"  # Quota/billing limits exceeded
    TIMEOUT = "timeout"  # Request timeout
    NETWORK = "network"  # Network connectivity issues
    PROVIDER_FAILURE = "provider_failure"  # Provider service issues
    PERMANENT = "permanent"  # Permanent errors that won't succeed on retry


class ErrorClassifier:
    """Classifies errors into categories for appropriate handling."""

    def __init__(self):
        """Initialize the error classifier with default patterns."""
        self._error_patterns: Dict[ErrorCategory, list] = {
            ErrorCategory.RATE_LIMITED: [
                "rate limit exceeded",
                "rate_limit_exceeded",
                "too many requests",
                "throttled",
                "quota exceeded",
                "rate limit hit",
                "429",
            ],
            ErrorCategory.AUTHENTICATION: [
                "unauthorized",
                "forbidden",
                "authentication",
                "invalid api key",
                "invalid token",
                "access denied",
                "401",
                "403",
                "auth",
                "permission denied",
                "invalid credentials",
            ],
            ErrorCategory.QUOTA_EXCEEDED: [
                "billing",
                "payment required",
                "insufficient funds",
                "usage limit",
                "quota limit",
                "402",
                "billing limit",
            ],
            ErrorCategory.TIMEOUT: [
                "timeout",
                "timed out",
                "request timeout",
                "connection timeout",
                "read timeout",
                "408",
                "timeout error",
                "deadline exceeded",
            ],
            ErrorCategory.NETWORK: [
                "connection",
                "network",
                "dns",
                "resolve",
                "unreachable",
                "connection refused",
                "connection reset",
                "network error",
                "connection error",
                "socket error",
            ],
            ErrorCategory.PROVIDER_FAILURE: [
                "provider error",
                "service error",
                "api error",
                "endpoint error",
                "service unavailable",
                "maintenance",
                "outage",
                "internal server error",
                "bad gateway",
                "500",
                "502",
                "503",
            ],
            ErrorCategory.PERMANENT: [
                "not found",
                "invalid request",
                "bad request",
                "malformed",
                "validation error",
                "400",
                "404",
                "422",
                "invalid",
                "unsupported",
                "deprecated",
                "not implemented",
            ],
            ErrorCategory.TRANSIENT: [
                "temporary",
                "retry",
                "busy",
                "unavailable",
                "service temporarily unavailable",
                "rate limit",
                "throttled",
            ],
        }

        # HTTP status code mappings
        self._status_code_mappings: Dict[int, ErrorCategory] = {
            400: ErrorCategory.PERMANENT,
            401: ErrorCategory.AUTHENTICATION,
            402: ErrorCategory.QUOTA_EXCEEDED,
            403: ErrorCategory.AUTHENTICATION,
            404: ErrorCategory.PERMANENT,
            408: ErrorCategory.TIMEOUT,
            409: ErrorCategory.TRANSIENT,
            422: ErrorCategory.PERMANENT,
            429: ErrorCategory.RATE_LIMITED,
            500: ErrorCategory.PROVIDER_FAILURE,
            502: ErrorCategory.PROVIDER_FAILURE,
            503: ErrorCategory.PROVIDER_FAILURE,
            504: ErrorCategory.TIMEOUT,
        }

        # Exception type mappings
        self._exception_mappings: Dict[Type[Exception], ErrorCategory] = {
            ConnectionError: ErrorCategory.NETWORK,
            TimeoutError: ErrorCategory.TIMEOUT,
            OSError: ErrorCategory.NETWORK,
        }

    def classify_error(
        self,
        error: Exception,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> ErrorCategory:
        """Classify an error into a category.

        Args:
            error: The exception that occurred
            status_code: HTTP status code if available
            error_message: Error message if available
            provider: Provider name for context

        Returns:
            Error category for the error
        """
        # Check status code first (most reliable)
        if status_code is not None:
            category = self._status_code_mappings.get(status_code)
            if category:
                logger.debug(
                    f"Classified error by status code {status_code}: {category}"
                )
                return category

        # Extract status code from error message if not provided
        error_str = str(error)
        extracted_status_code = self._extract_status_code_from_message(error_str)
        if extracted_status_code is not None:
            category = self._status_code_mappings.get(extracted_status_code)
            if category:
                logger.debug(
                    f"Classified error by extracted status code {extracted_status_code}: {category}"
                )
                return category

        # Check exception type
        error_type = type(error)
        for exc_type, category in self._exception_mappings.items():
            if issubclass(error_type, exc_type):
                logger.debug(
                    f"Classified error by exception type {error_type.__name__}: {category}"
                )
                return category

        # Check error message patterns
        if error_message:
            error_message_lower = error_message.lower()
            for category, patterns in self._error_patterns.items():
                for pattern in patterns:
                    if pattern in error_message_lower:
                        logger.debug(
                            f"Classified error by message pattern '{pattern}': {category}"
                        )
                        return category

        # Check error string representation
        error_str_lower = error_str.lower()
        for category, patterns in self._error_patterns.items():
            for pattern in patterns:
                if pattern in error_str_lower:
                    logger.debug(
                        f"Classified error by error string pattern '{pattern}': {category}"
                    )
                    return category

        # Default classification based on provider context
        if provider:
            logger.debug(
                f"Using provider-specific default classification for {provider}"
            )
            return self._get_provider_default_category(provider)

        # Default to provider failure for unknown errors
        logger.debug("Using default classification: PROVIDER_FAILURE")
        return ErrorCategory.PROVIDER_FAILURE

    def _get_provider_default_category(self, provider: str) -> ErrorCategory:
        """Get default error category for a specific provider."""
        provider_defaults = {
            "gemini": ErrorCategory.PROVIDER_FAILURE,
            "openai": ErrorCategory.PROVIDER_FAILURE,
            "anthropic": ErrorCategory.PROVIDER_FAILURE,
            "grok": ErrorCategory.PROVIDER_FAILURE,
            "bedrock": ErrorCategory.PROVIDER_FAILURE,
            "ollama": ErrorCategory.NETWORK,  # Local service, likely network issues
        }

        return provider_defaults.get(provider.lower(), ErrorCategory.TRANSIENT)

    def _extract_status_code_from_message(self, error_message: str) -> Optional[int]:
        """Extract HTTP status code from error message.

        Args:
            error_message: Error message to extract status code from

        Returns:
            Status code if found, None otherwise
        """
        import re

        # Look for patterns like "429 Client Error", "500 Server Error", etc.
        patterns = [
            r"(\d{3})\s+(?:Client|Server)\s+Error",
            r"HTTP\s+(\d{3})",
            r"Status\s+(\d{3})",
            r"(\d{3})\s+Error",
        ]

        for pattern in patterns:
            match = re.search(pattern, error_message)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue

        return None

    def is_retryable(self, category: ErrorCategory) -> bool:
        """Check if an error category is retryable.

        Args:
            category: Error category to check

        Returns:
            True if the error should be retried
        """
        retryable_categories = {
            ErrorCategory.TRANSIENT,
            ErrorCategory.RATE_LIMITED,
            ErrorCategory.TIMEOUT,
            ErrorCategory.NETWORK,
            ErrorCategory.PROVIDER_FAILURE,
        }

        return category in retryable_categories

    def get_retry_delay(
        self,
        category: ErrorCategory,
        attempt: int,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ) -> float:
        """Get retry delay for an error category.

        Args:
            category: Error category
            attempt: Current attempt number (0-based)
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds

        Returns:
            Delay in seconds before next retry
        """
        if category == ErrorCategory.RATE_LIMITED:
            # Longer delay for rate limits
            delay = min(base_delay * (2**attempt) * 2, max_delay)
        elif category == ErrorCategory.QUOTA_EXCEEDED:
            # Very long delay for quota issues
            delay = min(base_delay * (2**attempt) * 5, max_delay * 2)
        elif category == ErrorCategory.TIMEOUT:
            # Moderate delay for timeouts
            delay = min(base_delay * (2**attempt), max_delay)
        else:
            # Standard exponential backoff
            delay = min(base_delay * (2**attempt), max_delay)

        return delay

    def should_fallback(self, category: ErrorCategory) -> bool:
        """Check if an error should trigger fallback to another provider.

        Args:
            category: Error category to check

        Returns:
            True if fallback should be attempted
        """
        fallback_categories = {
            ErrorCategory.PROVIDER_FAILURE,
            ErrorCategory.QUOTA_EXCEEDED,
            ErrorCategory.AUTHENTICATION,
            ErrorCategory.PERMANENT,
        }

        return category in fallback_categories

    def add_error_pattern(self, category: ErrorCategory, pattern: str) -> None:
        """Add a custom error pattern for classification.

        Args:
            category: Error category
            pattern: Pattern to match in error messages
        """
        if category not in self._error_patterns:
            self._error_patterns[category] = []

        self._error_patterns[category].append(pattern.lower())
        logger.info(f"Added error pattern '{pattern}' for category {category}")

    def add_status_code_mapping(
        self, status_code: int, category: ErrorCategory
    ) -> None:
        """Add a custom status code mapping.

        Args:
            status_code: HTTP status code
            category: Error category to map to
        """
        self._status_code_mappings[status_code] = category
        logger.info(f"Added status code mapping {status_code} -> {category}")

    def add_exception_mapping(
        self, exception_type: Type[Exception], category: ErrorCategory
    ) -> None:
        """Add a custom exception type mapping.

        Args:
            exception_type: Exception type to map
            category: Error category to map to
        """
        self._exception_mappings[exception_type] = category
        logger.info(f"Added exception mapping {exception_type.__name__} -> {category}")

    def get_classification_stats(self) -> Dict[str, Any]:
        """Get statistics about error classifications."""
        return {
            "error_patterns": {
                category.value: len(patterns)
                for category, patterns in self._error_patterns.items()
            },
            "status_code_mappings": len(self._status_code_mappings),
            "exception_mappings": len(self._exception_mappings),
            "total_patterns": sum(
                len(patterns) for patterns in self._error_patterns.values()
            ),
        }
