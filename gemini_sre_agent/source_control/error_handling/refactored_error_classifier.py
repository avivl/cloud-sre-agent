# gemini_sre_agent/source_control/error_handling/refactored_error_classifier.py

"""
Refactored error classifier using modular components.

This module provides a clean, modular implementation of the error classifier
that uses the separated concerns from the refactored modules while maintaining
backward compatibility.
"""

import logging
import time
from typing import Any

from .classification_algorithms import (
    BaseErrorClassifier,
    ClassificationResult,
    ClassifierFactory,
    TrainingData,
)
from .classification_metrics import (
    ClassificationMetricsCollector,
    MetricsSummary,
)
from .core import ErrorClassification, ErrorType
from .error_patterns import (
    get_best_error_match,
    initialize_default_patterns,
)
from .error_types import (
    ErrorTypeRegistry,
    get_error_metadata,
)

logger = logging.getLogger(__name__)


class RefactoredErrorClassifier:
    """Refactored error classifier using modular architecture."""

    def __init__(
        self,
        algorithm: str = "hybrid",
        enable_metrics: bool = True,
        enable_patterns: bool = True,
        training_data: TrainingData | None = None,
    ):
        """Initialize the refactored error classifier."""
        self.logger = logging.getLogger("RefactoredErrorClassifier")
        self.algorithm = algorithm
        self.enable_metrics = enable_metrics
        self.enable_patterns = enable_patterns

        # Initialize core components
        self.error_type_registry = ErrorTypeRegistry()

        # Initialize classification algorithm
        self.classifier = self._initialize_classifier(algorithm, training_data)

        # Initialize pattern matching
        if enable_patterns:
            initialize_default_patterns()

        # Initialize metrics collection
        if enable_metrics:
            self.metrics_collector = ClassificationMetricsCollector("error_classifier")
        else:
            self.metrics_collector = None

        # Backward compatibility classification rules
        self.classification_rules = self._initialize_legacy_rules()

        self.logger.info(
            f"Initialized RefactoredErrorClassifier with algorithm: {algorithm}"
        )

    def _initialize_classifier(
        self, algorithm: str, training_data: TrainingData | None
    ) -> BaseErrorClassifier:
        """Initialize the classification algorithm."""
        classifier = ClassifierFactory.create_classifier(algorithm)

        # Train the classifier if training data is provided
        if training_data:
            classifier.fit(training_data)
        else:
            # Use default training data based on error patterns
            default_training_data = self._create_default_training_data()
            classifier.fit(default_training_data)

        return classifier

    def _create_default_training_data(self) -> TrainingData:
        """Create default training data for the classifier."""
        # Sample error messages and their corresponding types
        error_messages = [
            "Connection timed out after 30 seconds",
            "Network is unreachable",
            "Connection reset by peer",
            "Invalid authentication credentials",
            "Access denied - insufficient permissions",
            "File not found: /path/to/file",
            "Rate limit exceeded - try again later",
            "Internal server error (500)",
            "Bad request - invalid input",
            "SSL certificate verification failed",
            "DNS resolution failed",
            "Disk space full",
            "Configuration error in settings",
            "GitHub merge conflict detected",
            "Git command failed",
            "SSH key authentication failed",
        ]

        error_types = [
            ErrorType.TIMEOUT_ERROR,
            ErrorType.NETWORK_ERROR,
            ErrorType.CONNECTION_RESET_ERROR,
            ErrorType.AUTHENTICATION_ERROR,
            ErrorType.AUTHORIZATION_ERROR,
            ErrorType.FILE_NOT_FOUND_ERROR,
            ErrorType.RATE_LIMIT_ERROR,
            ErrorType.SERVER_ERROR,
            ErrorType.VALIDATION_ERROR,
            ErrorType.SSL_ERROR,
            ErrorType.DNS_ERROR,
            ErrorType.DISK_SPACE_ERROR,
            ErrorType.CONFIGURATION_ERROR,
            ErrorType.GITHUB_MERGE_CONFLICT,
            ErrorType.LOCAL_GIT_ERROR,
            ErrorType.GITHUB_SSH_ERROR,
        ]

        contexts = [{}] * len(error_messages)  # Empty contexts for simplicity
        labels = [error_type.value for error_type in error_types]

        return TrainingData(
            error_messages=error_messages,
            error_types=error_types,
            contexts=contexts,
            labels=labels,
        )

    def _initialize_legacy_rules(self) -> list[Any]:
        """Initialize legacy classification rules for backward compatibility."""
        # These are simplified versions of the original rules
        # They serve as fallbacks when the new system doesn't classify an error
        return [
            self._classify_by_exception_type,
            self._classify_by_error_message,
            self._classify_by_http_status,
        ]

    def classify_error(self, error: Exception) -> ErrorClassification:
        """Classify an error using the modular architecture."""
        start_time = time.time()
        error_message = str(error)

        # Create context for classification
        context = {
            "exception_type": type(error).__name__,
            "error_message": error_message,
            "error_attributes": self._extract_error_attributes(error),
        }

        # Try pattern-based classification first
        best_pattern_match = None
        if self.enable_patterns:
            best_pattern_match = get_best_error_match(error_message, context)

        # Try algorithmic classification
        try:
            classification_result = self.classifier.predict(error_message, context)
        except Exception as e:
            self.logger.warning(f"Algorithmic classification failed: {e}")
            classification_result = None

        # Determine the best classification
        final_error_type = None
        final_confidence = 0.0
        classification_source = "unknown"

        if best_pattern_match and classification_result:
            # Use the result with higher confidence
            if best_pattern_match.confidence > classification_result.confidence:
                final_error_type = best_pattern_match.error_type
                final_confidence = best_pattern_match.confidence
                classification_source = "pattern"
            else:
                final_error_type = classification_result.error_type
                final_confidence = classification_result.confidence
                classification_source = "algorithm"
        elif best_pattern_match:
            final_error_type = best_pattern_match.error_type
            final_confidence = best_pattern_match.confidence
            classification_source = "pattern"
        elif classification_result:
            final_error_type = classification_result.error_type
            final_confidence = classification_result.confidence
            classification_source = "algorithm"

        # Fallback to legacy rules if no classification found
        if final_error_type is None:
            for rule in self.classification_rules:
                legacy_classification = rule(error)
                if legacy_classification:
                    final_error_type = legacy_classification.error_type
                    final_confidence = 0.5  # Default confidence for legacy rules
                    classification_source = "legacy"
                    break

        # Final fallback to unknown error
        if final_error_type is None:
            final_error_type = ErrorType.UNKNOWN_ERROR
            final_confidence = 0.1
            classification_source = "fallback"

        # Get error metadata
        error_metadata = get_error_metadata(final_error_type.value)

        # Create classification result
        classification = ErrorClassification(
            error_type=final_error_type,
            is_retryable=error_metadata.is_retryable if error_metadata else False,
            retry_delay=error_metadata.retry_delay if error_metadata else 0.0,
            max_retries=error_metadata.max_retries if error_metadata else 0,
            should_open_circuit=self._should_open_circuit(
                final_error_type, error_metadata
            ),
            details={
                "error": error_message,
                "exception_type": type(error).__name__,
                "confidence": final_confidence,
                "classification_source": classification_source,
                "error_severity": (
                    error_metadata.severity.value if error_metadata else "unknown"
                ),
                "error_category": (
                    error_metadata.category.value if error_metadata else "unknown"
                ),
                "classification_time_ms": (time.time() - start_time) * 1000,
            },
        )

        # Record metrics if enabled
        if self.metrics_collector and classification_result:
            # For metrics, we need the true label, but in real usage we don't have it
            # So we'll use the final classification as both true and predicted for now
            self.metrics_collector.record_prediction(
                final_error_type,
                classification_result,
                (time.time() - start_time) * 1000,
            )

        self.logger.debug(
            f"Classified error: {final_error_type.value} "
            f"(confidence: {final_confidence:.3f}, source: {classification_source})"
        )

        return classification

    def _extract_error_attributes(self, error: Exception) -> dict[str, Any]:
        """Extract attributes from an error for classification context."""
        attributes = {}

        # Common attributes
        for attr in ["status", "code", "errno", "response", "reason"]:
            if hasattr(error, attr):
                attributes[attr] = getattr(error, attr)

        # HTTP-specific attributes
        if hasattr(error, "response"):
            response = error.response  # type: ignore
            if hasattr(response, "status_code"):
                attributes["status_code"] = response.status_code

        # Request-specific attributes
        if hasattr(error, "request"):
            request = error.request  # type: ignore
            if hasattr(request, "url"):
                attributes["url"] = request.url

        return attributes

    def _should_open_circuit(self, error_type: ErrorType, error_metadata: Any) -> bool:
        """Determine if the circuit breaker should open for this error type."""
        if not error_metadata:
            return True  # Default to opening circuit for unknown errors

        # Don't open circuit for certain error types
        non_circuit_opening_errors = {
            ErrorType.RATE_LIMIT_ERROR,
            ErrorType.AUTHENTICATION_ERROR,
            ErrorType.AUTHORIZATION_ERROR,
            ErrorType.VALIDATION_ERROR,
            ErrorType.NOT_FOUND_ERROR,
            ErrorType.CONFIGURATION_ERROR,
        }

        return error_type not in non_circuit_opening_errors

    def _classify_by_exception_type(
        self, error: Exception
    ) -> ErrorClassification | None:
        """Legacy rule: classify by exception type."""
        error_type_mapping = {
            ConnectionError: ErrorType.NETWORK_ERROR,
            TimeoutError: ErrorType.TIMEOUT_ERROR,
            OSError: ErrorType.NETWORK_ERROR,
            ValueError: ErrorType.VALIDATION_ERROR,
            TypeError: ErrorType.VALIDATION_ERROR,
            FileNotFoundError: ErrorType.FILE_NOT_FOUND_ERROR,
            PermissionError: ErrorType.PERMISSION_DENIED_ERROR,
        }

        exception_type = type(error)
        if exception_type in error_type_mapping:
            error_type = error_type_mapping[exception_type]
            error_metadata = get_error_metadata(error_type.value)

            return ErrorClassification(
                error_type=error_type,
                is_retryable=error_metadata.is_retryable if error_metadata else False,
                retry_delay=error_metadata.retry_delay if error_metadata else 0.0,
                max_retries=error_metadata.max_retries if error_metadata else 0,
                should_open_circuit=self._should_open_circuit(
                    error_type, error_metadata
                ),
                details={"error": str(error), "source": "exception_type"},
            )

        return None

    def _classify_by_error_message(
        self, error: Exception
    ) -> ErrorClassification | None:
        """Legacy rule: classify by error message keywords."""
        error_str = str(error).lower()

        keyword_mappings = {
            "timeout": ErrorType.TIMEOUT_ERROR,
            "connection": ErrorType.NETWORK_ERROR,
            "network": ErrorType.NETWORK_ERROR,
            "unauthorized": ErrorType.AUTHENTICATION_ERROR,
            "forbidden": ErrorType.AUTHORIZATION_ERROR,
            "not found": ErrorType.NOT_FOUND_ERROR,
            "rate limit": ErrorType.RATE_LIMIT_ERROR,
            "server error": ErrorType.SERVER_ERROR,
            "ssl": ErrorType.SSL_ERROR,
            "certificate": ErrorType.SSL_ERROR,
            "dns": ErrorType.DNS_ERROR,
        }

        for keyword, error_type in keyword_mappings.items():
            if keyword in error_str:
                error_metadata = get_error_metadata(error_type.value)

                return ErrorClassification(
                    error_type=error_type,
                    is_retryable=(
                        error_metadata.is_retryable if error_metadata else False
                    ),
                    retry_delay=error_metadata.retry_delay if error_metadata else 0.0,
                    max_retries=error_metadata.max_retries if error_metadata else 0,
                    should_open_circuit=self._should_open_circuit(
                        error_type, error_metadata
                    ),
                    details={
                        "error": str(error),
                        "source": "keyword",
                        "keyword": keyword,
                    },
                )

        return None

    def _classify_by_http_status(
        self, error: Exception
    ) -> ErrorClassification | None:
        """Legacy rule: classify by HTTP status code."""
        status = None

        # Try to extract status code from different error types
        if hasattr(error, "status"):
            status = error.status  # type: ignore
        elif hasattr(error, "status_code"):
            status = error.status_code  # type: ignore
        elif hasattr(error, "response"):
            response = error.response  # type: ignore
            if hasattr(response, "status_code"):
                status = response.status_code

        if status is not None:
            status_mappings = {
                range(500, 600): ErrorType.SERVER_ERROR,
                range(400, 500): ErrorType.VALIDATION_ERROR,
                401: ErrorType.AUTHENTICATION_ERROR,
                403: ErrorType.AUTHORIZATION_ERROR,
                404: ErrorType.NOT_FOUND_ERROR,
                429: ErrorType.RATE_LIMIT_ERROR,
            }

            for status_range, error_type in status_mappings.items():
                if (
                    isinstance(status_range, range) and status in status_range
                ) or status == status_range:
                    error_metadata = get_error_metadata(error_type.value)

                    return ErrorClassification(
                        error_type=error_type,
                        is_retryable=(
                            error_metadata.is_retryable if error_metadata else False
                        ),
                        retry_delay=(
                            error_metadata.retry_delay if error_metadata else 0.0
                        ),
                        max_retries=error_metadata.max_retries if error_metadata else 0,
                        should_open_circuit=self._should_open_circuit(
                            error_type, error_metadata
                        ),
                        details={
                            "error": str(error),
                            "source": "http_status",
                            "status": status,
                        },
                    )

        return None

    def get_performance_summary(self) -> dict[str, Any] | None:
        """Get performance summary from metrics collector."""
        if self.metrics_collector:
            return self.metrics_collector.get_performance_summary()
        return None

    def generate_classification_report(self) -> str | None:
        """Generate classification report from metrics collector."""
        if self.metrics_collector:
            return self.metrics_collector.generate_classification_report()
        return None

    def export_metrics(self) -> MetricsSummary | None:
        """Export metrics summary."""
        if self.metrics_collector:
            return self.metrics_collector.export_metrics(self.algorithm)
        return None

    def reset_metrics(self) -> None:
        """Reset metrics collection."""
        if self.metrics_collector:
            self.metrics_collector.reset_metrics()
            self.logger.info("Reset error classification metrics")

    def retrain_classifier(self, training_data: TrainingData) -> None:
        """Retrain the classification algorithm with new data."""
        try:
            self.classifier.fit(training_data)
            self.logger.info(
                f"Retrained {self.algorithm} classifier with {len(training_data.error_messages)} samples"
            )
        except Exception as e:
            self.logger.error(f"Failed to retrain classifier: {e}")

    def get_algorithm_score(self, test_data: TrainingData) -> float:
        """Get the accuracy score of the current algorithm."""
        try:
            return self.classifier.score(test_data)
        except Exception as e:
            self.logger.error(f"Failed to score classifier: {e}")
            return 0.0

    def predict_error_type(
        self, error_message: str, context: dict[str, Any] | None = None
    ) -> ClassificationResult:
        """Predict error type for a given error message."""
        try:
            return self.classifier.predict(error_message, context)
        except Exception as e:
            self.logger.error(f"Failed to predict error type: {e}")
            return ClassificationResult(
                error_type=ErrorType.UNKNOWN_ERROR,
                confidence=0.0,
                metadata={},
                classification_path=["prediction_failed"],
                matched_patterns=[],
                suggested_actions=["Check error message and try again"],
            )

    def get_available_algorithms(self) -> list[str]:
        """Get list of available classification algorithms."""
        return ClassifierFactory.get_available_algorithms()

    def switch_algorithm(
        self, algorithm: str, training_data: TrainingData | None = None
    ) -> None:
        """Switch to a different classification algorithm."""
        try:
            self.algorithm = algorithm
            self.classifier = self._initialize_classifier(algorithm, training_data)
            self.logger.info(f"Switched to {algorithm} classifier")
        except Exception as e:
            self.logger.error(f"Failed to switch to {algorithm} classifier: {e}")


# Backward compatibility alias
ErrorClassifier = RefactoredErrorClassifier


# Factory function for creating error classifiers
def create_error_classifier(
    algorithm: str = "hybrid",
    enable_metrics: bool = True,
    enable_patterns: bool = True,
    training_data: TrainingData | None = None,
) -> RefactoredErrorClassifier:
    """Create an error classifier with the specified configuration."""
    return RefactoredErrorClassifier(
        algorithm=algorithm,
        enable_metrics=enable_metrics,
        enable_patterns=enable_patterns,
        training_data=training_data,
    )


# Configuration for different use cases
def create_production_classifier() -> RefactoredErrorClassifier:
    """Create an error classifier optimized for production use."""
    return RefactoredErrorClassifier(
        algorithm="hybrid",
        enable_metrics=True,
        enable_patterns=True,
    )


def create_development_classifier() -> RefactoredErrorClassifier:
    """Create an error classifier optimized for development use."""
    return RefactoredErrorClassifier(
        algorithm="rule_based",
        enable_metrics=True,
        enable_patterns=True,
    )


def create_testing_classifier() -> RefactoredErrorClassifier:
    """Create an error classifier optimized for testing."""
    return RefactoredErrorClassifier(
        algorithm="pattern_based",
        enable_metrics=False,
        enable_patterns=True,
    )
