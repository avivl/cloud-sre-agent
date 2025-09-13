# gemini_sre_agent/source_control/error_handling/error_classification.py

"""
Error classification and analysis for source control operations.

This module provides comprehensive error classification logic using modular
components for pattern detection, classification algorithms, and metrics collection.
"""

from dataclasses import dataclass
import logging
from typing import Any

from .classification_algorithms import (
    BaseErrorClassifier,
    ClassificationResult,
    ClassificationStrategy,
    HybridClassifier,
    PatternBasedClassifier,
    RuleBasedClassifier,
    create_error_classification,
)
from .classification_metrics import (
    ClassificationMetricsCollector,
    MetricsComparator,
    MetricsSummary,
)
from .core import ErrorClassification, ErrorType
from .error_patterns import (
    PatternMatch,
    PatternMatcher,
    PatternMatcherFactory,
    initialize_default_patterns,
)
from .error_types import error_type_registry

logger = logging.getLogger(__name__)


@dataclass
class ErrorClassifierConfig:
    """Configuration for the ErrorClassifier."""

    strategy: ClassificationStrategy = ClassificationStrategy.HYBRID
    enable_pattern_matching: bool = True
    enable_metrics_collection: bool = True
    confidence_threshold: float = 0.5
    fallback_to_unknown: bool = True
    custom_patterns: dict[str, Any] | None = None
    algorithm_config: dict[str, Any] | None = None


class ErrorClassifier:
    """Refactored error classifier using modular components."""

    def __init__(self, config: ErrorClassifierConfig | None = None) -> None:
        """Initialize the error classifier with modular components."""
        self.config = config or ErrorClassifierConfig()
        self.logger = logging.getLogger("ErrorClassifier")

        # Initialize classification algorithm
        self.classifier = self._create_classifier()

        # Initialize pattern matching if enabled
        self.pattern_matcher = None
        if self.config.enable_pattern_matching:
            self.pattern_matcher = self._create_pattern_matcher()

        # Initialize metrics collection if enabled
        self.metrics_collector = None
        if self.config.enable_metrics_collection:
            self.metrics_collector = ClassificationMetricsCollector("error_classifier")

        # Initialize default patterns
        if self.config.enable_pattern_matching:
            initialize_default_patterns()

        self.logger.info(
            f"Initialized ErrorClassifier with strategy: {self.config.strategy}"
        )

    def _create_classifier(self) -> BaseErrorClassifier:
        """Create the classification algorithm based on configuration."""
        algorithm_config = self.config.algorithm_config or {}

        if self.config.strategy == ClassificationStrategy.RULE_BASED:
            return RuleBasedClassifier(**algorithm_config)
        elif self.config.strategy == ClassificationStrategy.PATTERN_BASED:
            return PatternBasedClassifier(**algorithm_config)
        elif self.config.strategy == ClassificationStrategy.HYBRID:
            return HybridClassifier(**algorithm_config)
        else:
            # Fallback to hybrid
            return HybridClassifier(**algorithm_config)

    def _create_pattern_matcher(self) -> PatternMatcher | None:
        """Create pattern matcher based on configuration."""
        if self.config.custom_patterns:
            # Use custom pattern configuration
            matcher_type = self.config.custom_patterns.get("type", "regex")
            config = self.config.custom_patterns.get("config")
            return PatternMatcherFactory.create_matcher(matcher_type, config=config)
        else:
            # Use default regex matcher
            return PatternMatcherFactory.create_matcher("regex", "default")

    def classify_error(self, error: Exception) -> ErrorClassification:
        """Classify an error using the modular classification system."""
        import time

        start_time = time.time()

        try:
            # Convert exception to string for pattern matching
            error_text = str(error)
            error_context = {
                "error_type": type(error).__name__,
                "error_module": getattr(error, "__module__", "unknown"),
                "error_context": self._determine_error_context(error),
            }

            # Try pattern-based classification first if enabled
            if self.pattern_matcher and self.config.enable_pattern_matching:
                pattern_result = self._classify_with_patterns(error_text, error_context)
                if (
                    pattern_result
                    and pattern_result.confidence >= self.config.confidence_threshold
                ):
                    classification = self._convert_pattern_result_to_classification(
                        pattern_result, error
                    )
                    self._record_metrics(error, classification, start_time)
                    return classification

            # Fall back to algorithm-based classification
            classification = create_error_classification(error, self.config.strategy)

            # Record metrics if enabled
            self._record_metrics(error, classification, start_time)

            return classification

        except Exception as e:
            self.logger.error(f"Error during classification: {e}")

            # Return fallback classification
            if self.config.fallback_to_unknown:
                fallback_classification = ErrorClassification(
                    error_type=ErrorType.UNKNOWN_ERROR,
                    is_retryable=False,
                    retry_delay=0.0,
                    max_retries=0,
                    should_open_circuit=False,
                    details={"error": str(error), "classification_error": str(e)},
                )
                self._record_metrics(error, fallback_classification, start_time)
                return fallback_classification
            else:
                raise

    def _classify_with_patterns(
        self, error_text: str, context: dict[str, Any]
    ) -> PatternMatch | None:
        """Classify error using pattern matching."""
        if not self.pattern_matcher:
            return None

        try:
            matches = self.pattern_matcher.match(error_text, context)
            return matches[0] if matches else None
        except Exception as e:
            self.logger.warning(f"Pattern matching failed: {e}")
            return None

    def _convert_pattern_result_to_classification(
        self, pattern_result: PatternMatch, error: Exception
    ) -> ErrorClassification:
        """Convert pattern match result to ErrorClassification."""
        # Get metadata for the error type
        metadata = error_type_registry.get_metadata(pattern_result.error_type.value)

        if metadata:
            return ErrorClassification(
                error_type=pattern_result.error_type,
                is_retryable=metadata.is_retryable,
                retry_delay=metadata.retry_delay,
                max_retries=metadata.max_retries,
                should_open_circuit=metadata.should_open_circuit,
                details={
                    "error": str(error),
                    "pattern": pattern_result.pattern,
                    "confidence": pattern_result.confidence,
                    "matched_text": pattern_result.matched_text,
                    "metadata": pattern_result.metadata,
                },
            )
        else:
            # Fallback to basic classification
            return ErrorClassification(
                error_type=pattern_result.error_type,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=3,
                should_open_circuit=True,
                details={
                    "error": str(error),
                    "pattern": pattern_result.pattern,
                    "confidence": pattern_result.confidence,
                    "matched_text": pattern_result.matched_text,
                },
            )

    def _convert_classification_result_to_classification(
        self, classification_result: ClassificationResult, error: Exception
    ) -> ErrorClassification:
        """Convert ClassificationResult to ErrorClassification."""
        # Get metadata for the error type
        metadata = error_type_registry.get_metadata(
            classification_result.error_type.value
        )

        if metadata:
            return ErrorClassification(
                error_type=classification_result.error_type,
                is_retryable=metadata.is_retryable,
                retry_delay=metadata.retry_delay,
                max_retries=metadata.max_retries,
                should_open_circuit=metadata.should_open_circuit,
                details={
                    "error": str(error),
                    "confidence": classification_result.confidence,
                    "strategy": (
                        classification_result.classification_strategy.value
                        if hasattr(classification_result, "classification_strategy")
                        else "unknown"
                    ),
                    "metadata": classification_result.metadata,
                },
            )
        else:
            # Fallback to basic classification
            return ErrorClassification(
                error_type=classification_result.error_type,
                is_retryable=True,
                retry_delay=1.0,
                max_retries=3,
                should_open_circuit=True,
                details={
                    "error": str(error),
                    "confidence": classification_result.confidence,
                    "strategy": (
                        classification_result.classification_strategy.value
                        if hasattr(classification_result, "classification_strategy")
                        else "unknown"
                    ),
                },
            )

    def _determine_error_context(self, error: Exception) -> str:
        """Determine the context of the error for better classification."""
        error_str = str(error).lower()

        # Network-related context
        if any(
            term in error_str
            for term in ["network", "connection", "timeout", "dns", "ssl"]
        ):
            return "network"

        # Authentication context
        elif any(
            term in error_str
            for term in ["auth", "unauthorized", "forbidden", "credentials"]
        ):
            return "authentication"

        # File system context
        elif any(
            term in error_str
            for term in ["file", "directory", "path", "permission", "disk"]
        ):
            return "filesystem"

        # API context
        elif any(
            term in error_str
            for term in ["api", "http", "request", "response", "status"]
        ):
            return "api"

        # Git context
        elif any(
            term in error_str
            for term in ["git", "merge", "conflict", "branch", "commit"]
        ):
            return "git"

        # Provider context
        elif any(
            term in error_str for term in ["github", "gitlab", "bitbucket", "azure"]
        ):
            return "provider"

        return "unknown"

    def _record_metrics(
        self, error: Exception, classification: ErrorClassification, start_time: float
    ) -> None:
        """Record metrics for the classification if enabled."""
        if not self.metrics_collector:
            return

        try:
            import time

            prediction_time_ms = (time.time() - start_time) * 1000

            # Create a mock ClassificationResult for metrics
            metadata = error_type_registry.get_metadata(classification.error_type.value)
            if metadata is None:
                # Create fallback metadata
                from .error_types import ErrorCategory, ErrorSeverity, ErrorTypeMetadata

                metadata = ErrorTypeMetadata(
                    category=ErrorCategory.UNKNOWN,
                    severity=ErrorSeverity.MEDIUM,
                    is_retryable=classification.is_retryable,
                    retry_delay=classification.retry_delay,
                    max_retries=classification.max_retries,
                    should_open_circuit=classification.should_open_circuit,
                    description=f"Unknown {classification.error_type.value}",
                    keywords=[],
                    patterns=[],
                )

            classification_result = ClassificationResult(
                error_type=classification.error_type,
                confidence=(
                    classification.details.get("confidence", 0.5)
                    if classification.details
                    else 0.5
                ),
                metadata=metadata,
                classification_strategy=ClassificationStrategy.HYBRID,
                details={"message": f"Classified {type(error).__name__}"},
            )

            # For metrics, we need a true label - use the error type if we can determine it
            true_label = self._infer_true_label(error)

            self.metrics_collector.record_prediction(
                true_label=true_label,
                predicted_result=classification_result,
                prediction_time_ms=prediction_time_ms,
            )
        except Exception as e:
            self.logger.warning(f"Failed to record metrics: {e}")

    def _infer_true_label(self, error: Exception) -> ErrorType:
        """Infer the true label for metrics (best effort)."""
        # This is a simplified approach - in practice, you'd want more sophisticated logic
        error_str = str(error).lower()

        # Simple keyword-based inference
        if "timeout" in error_str:
            return ErrorType.TIMEOUT_ERROR
        elif "network" in error_str or "connection" in error_str:
            return ErrorType.NETWORK_ERROR
        elif "auth" in error_str or "unauthorized" in error_str:
            return ErrorType.AUTHENTICATION_ERROR
        elif "not found" in error_str or "404" in error_str:
            return ErrorType.NOT_FOUND_ERROR
        elif "rate limit" in error_str or "quota" in error_str:
            return ErrorType.RATE_LIMIT_ERROR
        elif "validation" in error_str or "invalid" in error_str:
            return ErrorType.VALIDATION_ERROR
        else:
            return ErrorType.UNKNOWN_ERROR

    def get_metrics_summary(self) -> MetricsSummary | None:
        """Get metrics summary if metrics collection is enabled."""
        if self.metrics_collector:
            return self.metrics_collector.export_metrics(self.config.strategy.value)
        return None

    def get_performance_report(self) -> str | None:
        """Get performance report if metrics collection is enabled."""
        if self.metrics_collector:
            return self.metrics_collector.generate_classification_report()
        return None

    def reset_metrics(self) -> None:
        """Reset metrics if metrics collection is enabled."""
        if self.metrics_collector:
            self.metrics_collector.reset_metrics()

    def add_custom_pattern(
        self, pattern: Any, error_type: ErrorType, confidence: float = 1.0
    ) -> None:
        """Add a custom pattern to the pattern matcher."""
        if self.pattern_matcher and hasattr(self.pattern_matcher, "add_pattern"):
            self.pattern_matcher.add_pattern(pattern, error_type, confidence)
            self.logger.info(f"Added custom pattern for {error_type}: {pattern}")

    def get_classification_statistics(self) -> dict[str, Any] | None:
        """Get classification statistics if metrics collection is enabled."""
        if self.metrics_collector:
            return self.metrics_collector.get_performance_summary()
        return None

    def compare_with_original_classifier(
        self, original_classifier: "ErrorClassifier", test_errors: list[Exception]
    ) -> MetricsComparator | None:
        """Compare performance with the original classifier."""
        if not self.metrics_collector:
            return None

        # This would require implementing the comparison logic
        # For now, return None as this is a placeholder
        self.logger.info("Classifier comparison not yet implemented")
        return None


# Backward compatibility functions
def create_error_classifier(
    config: ErrorClassifierConfig | None = None,
) -> ErrorClassifier:
    """Create an ErrorClassifier instance with the given configuration."""
    return ErrorClassifier(config)


def classify_error(
    error: Exception, config: ErrorClassifierConfig | None = None
) -> ErrorClassification:
    """Classify an error using the default classifier configuration."""
    classifier = ErrorClassifier(config)
    return classifier.classify_error(error)


# Legacy compatibility - maintain the same interface as the original
def create_legacy_classifier() -> ErrorClassifier:
    """Create a classifier with legacy configuration for backward compatibility."""
    config = ErrorClassifierConfig(
        strategy=ClassificationStrategy.RULE_BASED,
        enable_pattern_matching=False,
        enable_metrics_collection=False,
        confidence_threshold=0.5,
        fallback_to_unknown=True,
    )
    return ErrorClassifier(config)
