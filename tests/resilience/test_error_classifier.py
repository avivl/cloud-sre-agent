"""Tests for ErrorClassifier."""

import pytest

from gemini_sre_agent.resilience.error_classifier import (
    ErrorCategory,
    ErrorClassifier,
)


@pytest.fixture
def error_classifier():
    """Create an ErrorClassifier instance."""
    return ErrorClassifier()


@pytest.fixture
def request_context():
    """Create a request context dict."""
    return {
        "provider": "gemini",
        "model": "gemini-pro",
        "operation": "chat_completion",
        "request_id": "test-123",
        "user_id": "user-456",
    }


class TestErrorCategory:
    """Test cases for ErrorCategory enum."""

    def test_error_categories(self):
        """Test that all expected error categories exist."""
        expected_categories = [
            "TRANSIENT",
            "PROVIDER_FAILURE",
            "PERMANENT",
            "RATE_LIMITED",
            "QUOTA_EXCEEDED",
            "AUTHENTICATION",
            "TIMEOUT",
            "NETWORK",
        ]

        for category in expected_categories:
            assert hasattr(ErrorCategory, category)
            assert getattr(ErrorCategory, category) == category.lower()

    def test_error_category_values(self):
        """Test error category values."""
        assert ErrorCategory.TRANSIENT == "transient"
        assert ErrorCategory.PROVIDER_FAILURE == "provider_failure"
        assert ErrorCategory.PERMANENT == "permanent"
        assert ErrorCategory.RATE_LIMITED == "rate_limited"
        assert ErrorCategory.QUOTA_EXCEEDED == "quota_exceeded"
        assert ErrorCategory.AUTHENTICATION == "authentication"
        assert ErrorCategory.TIMEOUT == "timeout"
        assert ErrorCategory.NETWORK == "network"


class TestRequestContext:
    """Test cases for request context dict."""

    def test_request_context_creation(self):
        """Test request context creation."""
        context = {
            "provider": "test_provider",
            "model": "test_model",
            "operation": "test_operation",
            "request_id": "test-123",
            "user_id": "user-456",
        }

        assert context["provider"] == "test_provider"
        assert context["model"] == "test_model"
        assert context["operation"] == "test_operation"
        assert context["request_id"] == "test-123"
        assert context["user_id"] == "user-456"

    def test_request_context_defaults(self):
        """Test request context with default values."""
        context = {}

        assert context.get("provider") is None
        assert context.get("model") is None
        assert context.get("operation") is None
        assert context.get("request_id") is None
        assert context.get("user_id") is None


class TestErrorClassifier:
    """Test cases for ErrorClassifier."""

    def test_initialization(self, error_classifier):
        """Test ErrorClassifier initialization."""
        assert error_classifier is not None
        assert hasattr(error_classifier, "classify_error")

    def test_classify_timeout_error(self, error_classifier, request_context):
        """Test classification of timeout errors."""
        timeout_error = TimeoutError("Request timed out")

        category = error_classifier.classify_error(timeout_error)
        assert category == ErrorCategory.TIMEOUT

    def test_classify_asyncio_timeout_error(self, error_classifier, request_context):
        """Test classification of asyncio timeout errors."""
        import asyncio

        timeout_error = asyncio.TimeoutError("Async operation timed out")

        category = error_classifier.classify_error(timeout_error)
        assert category == ErrorCategory.TIMEOUT

    def test_classify_connection_error(self, error_classifier, request_context):
        """Test classification of connection errors."""
        connection_error = ConnectionError("Connection failed")

        category = error_classifier.classify_error(connection_error)
        assert category == ErrorCategory.NETWORK

    def test_classify_os_error(self, error_classifier, request_context):
        """Test classification of OS errors."""
        os_error = OSError("Network unreachable")

        category = error_classifier.classify_error(os_error)
        assert category == ErrorCategory.NETWORK

    def test_classify_http_error_429(self, error_classifier, request_context):
        """Test classification of HTTP 429 (rate limit) errors."""
        # Test with error message containing 429
        http_error = Exception("429 Client Error: Too Many Requests")

        category = error_classifier.classify_error(http_error)
        assert category == ErrorCategory.RATE_LIMITED

    def test_classify_http_error_401(self, error_classifier, request_context):
        """Test classification of HTTP 401 (unauthorized) errors."""
        # Test with error message containing 401
        http_error = Exception("401 Client Error: Unauthorized")

        category = error_classifier.classify_error(http_error)
        assert category == ErrorCategory.AUTHENTICATION

    def test_classify_http_error_403(self, error_classifier, request_context):
        """Test classification of HTTP 403 (forbidden) errors."""
        # Test with error message containing 403
        http_error = Exception("403 Client Error: Forbidden")

        category = error_classifier.classify_error(http_error)
        assert category == ErrorCategory.AUTHENTICATION

    def test_classify_http_error_500(self, error_classifier, request_context):
        """Test classification of HTTP 500 (server error) errors."""
        # Test with error message containing 500
        http_error = Exception("500 Server Error: Internal Server Error")

        category = error_classifier.classify_error(http_error)
        assert category == ErrorCategory.PROVIDER_FAILURE

    def test_classify_http_error_400(self, error_classifier, request_context):
        """Test classification of HTTP 400 (bad request) errors."""
        # Test with error message containing 400
        http_error = Exception("400 Client Error: Bad Request")

        category = error_classifier.classify_error(http_error)
        assert category == ErrorCategory.PERMANENT

    def test_classify_http_error_404(self, error_classifier, request_context):
        """Test classification of HTTP 404 (not found) errors."""
        # Test with error message containing 404
        http_error = Exception("404 Client Error: Not Found")

        category = error_classifier.classify_error(http_error)
        assert category == ErrorCategory.PERMANENT

    def test_classify_http_error_422(self, error_classifier, request_context):
        """Test classification of HTTP 422 (unprocessable entity) errors."""
        # Test with error message containing 422
        http_error = Exception("422 Client Error: Unprocessable Entity")

        category = error_classifier.classify_error(http_error)
        assert category == ErrorCategory.PERMANENT

    def test_classify_unknown_exception(self, error_classifier, request_context):
        """Test classification of unknown exceptions."""
        unknown_error = Exception("Unknown error")

        category = error_classifier.classify_error(unknown_error)
        assert category == ErrorCategory.PROVIDER_FAILURE

    def test_classify_error_with_none_context(self, error_classifier):
        """Test classification with None context."""
        timeout_error = TimeoutError("Request timed out")

        category = error_classifier.classify_error(timeout_error)
        assert category == ErrorCategory.TIMEOUT

    def test_classify_error_with_minimal_context(self, error_classifier):
        """Test classification with minimal context."""
        timeout_error = TimeoutError("Request timed out")

        category = error_classifier.classify_error(timeout_error)
        assert category == ErrorCategory.TIMEOUT

    def test_classify_error_with_full_context(self, error_classifier, request_context):
        """Test classification with full context."""
        timeout_error = TimeoutError("Request timed out")

        category = error_classifier.classify_error(timeout_error)
        assert category == ErrorCategory.TIMEOUT

    def test_classify_error_message_patterns(self, error_classifier, request_context):
        """Test classification based on error message patterns."""
        # Test rate limit patterns
        rate_limit_errors = [
            "Rate limit exceeded",
            "Too many requests",
            "Quota exceeded",
            "Rate limit hit",
        ]

        for error_msg in rate_limit_errors:
            error = Exception(error_msg)
            category = error_classifier.classify_error(error)
            assert category == ErrorCategory.RATE_LIMITED

        # Test authentication patterns
        auth_errors = [
            "Invalid API key",
            "Authentication failed",
            "Unauthorized",
            "Forbidden",
            "Permission denied",
        ]

        for error_msg in auth_errors:
            error = Exception(error_msg)
            category = error_classifier.classify_error(error)
            assert category == ErrorCategory.AUTHENTICATION

        # Test timeout patterns
        timeout_errors = [
            "Request timed out",
            "Timeout",
            "Deadline exceeded",
            "Connection timeout",
        ]

        for error_msg in timeout_errors:
            error = Exception(error_msg)
            category = error_classifier.classify_error(error)
            assert category == ErrorCategory.TIMEOUT

        # Test network patterns
        network_errors = [
            "Connection failed",
            "Network unreachable",
            "Connection refused",
            "DNS resolution failed",
        ]

        for error_msg in network_errors:
            error = Exception(error_msg)
            category = error_classifier.classify_error(error)
            assert category == ErrorCategory.NETWORK
