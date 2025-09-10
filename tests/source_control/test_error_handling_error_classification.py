"""
Unit tests for ErrorClassifier.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from gemini_sre_agent.source_control.error_handling.core import (
    ErrorType,
)
from gemini_sre_agent.source_control.error_handling.error_classification import (
    ErrorClassifier,
)


class TestErrorClassifier:
    """Test cases for ErrorClassifier."""

    @pytest.fixture
    def error_classifier(self):
        """Create an ErrorClassifier instance for testing."""
        return ErrorClassifier()

    def test_error_classifier_initialization(self, error_classifier):
        """Test ErrorClassifier initialization."""
        assert error_classifier.logger.name == "ErrorClassifier"
        assert len(error_classifier.classification_rules) == 10

    def test_classify_network_errors(self, error_classifier):
        """Test classification of network errors."""
        error = ConnectionError("Connection failed")
        classification = error_classifier._classify_network_errors(error)

        assert classification is not None
        assert classification.error_type == ErrorType.NETWORK_ERROR
        assert classification.is_retryable is True
        assert classification.retry_delay == 1.0
        assert classification.max_retries == 5
        assert classification.should_open_circuit is True

    def test_classify_timeout_errors(self, error_classifier):
        """Test classification of timeout errors."""
        error = asyncio.TimeoutError("Operation timed out")
        classification = error_classifier._classify_timeout_errors(error)

        assert classification is not None
        assert classification.error_type == ErrorType.TIMEOUT_ERROR
        assert classification.is_retryable is True
        assert classification.retry_delay == 2.0
        assert classification.max_retries == 3

    def test_classify_rate_limit_errors(self, error_classifier):
        """Test classification of rate limit errors."""
        error = Exception("Rate limit exceeded")
        classification = error_classifier._classify_rate_limit_errors(error)

        assert classification is not None
        assert classification.error_type == ErrorType.RATE_LIMIT_ERROR
        assert classification.is_retryable is True
        assert classification.retry_delay == 5.0
        assert classification.max_retries == 3
        assert classification.should_open_circuit is False

    def test_classify_http_errors(self, error_classifier):
        """Test classification of HTTP errors."""
        error = MagicMock()
        error.status = 500
        classification = error_classifier._classify_http_errors(error)

        assert classification is not None
        assert classification.error_type == ErrorType.SERVER_ERROR
        assert classification.is_retryable is True
        assert classification.retry_delay == 2.0
        assert classification.max_retries == 3

    def test_classify_authentication_errors(self, error_classifier):
        """Test classification of authentication errors."""
        error = Exception("Unauthorized access")
        classification = error_classifier._classify_authentication_errors(error)

        assert classification is not None
        assert classification.error_type == ErrorType.AUTHENTICATION_ERROR
        assert classification.is_retryable is False
        assert classification.retry_delay == 0.0
        assert classification.max_retries == 0

    def test_classify_validation_errors(self, error_classifier):
        """Test classification of validation errors."""
        error = ValueError("Invalid value")
        classification = error_classifier._classify_validation_errors(error)

        assert classification is not None
        assert classification.error_type == ErrorType.VALIDATION_ERROR
        assert classification.is_retryable is False
        assert classification.retry_delay == 0.0
        assert classification.max_retries == 0

    def test_classify_error_unknown_error(self, error_classifier):
        """Test classification of unknown errors."""
        error = Exception("Unknown error")
        classification = error_classifier.classify_error(error)

        assert classification.error_type == ErrorType.UNKNOWN_ERROR
        assert classification.is_retryable is False
        assert classification.retry_delay == 0.0
        assert classification.max_retries == 0
        assert classification.should_open_circuit is True
