# gemini_sre_agent/source_control/error_handling/classification_algorithms.py

"""
Machine learning-style classification algorithms for error classification.

This module provides scikit-learn compatible interfaces for error classification,
enabling the use of various classification strategies and algorithms.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from .core import ErrorClassification, ErrorType
from .error_types import ErrorCategory, ErrorSeverity, ErrorTypeMetadata


def _get_metadata_or_fallback(error_type: ErrorType) -> ErrorTypeMetadata:
    """Get metadata for error type or return fallback if not found."""
    from .error_types import error_type_registry

    metadata = error_type_registry.get_metadata(error_type.value)
    if metadata:
        return metadata

    # Fallback metadata
    return ErrorTypeMetadata(
        category=ErrorCategory.UNKNOWN,
        severity=ErrorSeverity.MEDIUM,
        is_retryable=False,
        retry_delay=0.0,
        max_retries=0,
        should_open_circuit=True,
        description=f"Unknown {error_type.value}",
        keywords=[],
        patterns=[],
    )


class ClassificationStrategy(Enum):
    """Available classification strategies."""

    RULE_BASED = "rule_based"
    PATTERN_BASED = "pattern_based"
    HYBRID = "hybrid"
    MACHINE_LEARNING = "machine_learning"


@dataclass
class ClassificationResult:
    """Result of error classification."""

    error_type: ErrorType
    confidence: float
    metadata: ErrorTypeMetadata
    classification_strategy: ClassificationStrategy
    details: Dict[str, Any]


class BaseErrorClassifier(Protocol):
    """Protocol for error classification algorithms following sklearn patterns."""

    def fit(self, X: List[Exception], y: List[ErrorType]) -> "BaseErrorClassifier":
        """Fit the classifier to training data."""
        ...

    def predict(self, X: List[Exception]) -> List[ErrorType]:
        """Predict error types for given exceptions."""
        ...

    def predict_proba(self, X: List[Exception]) -> List[Dict[ErrorType, float]]:
        """Predict class probabilities for given exceptions."""
        ...

    def score(self, X: List[Exception], y: List[ErrorType]) -> float:
        """Return the mean accuracy on the given test data and labels."""
        ...


class BaseErrorClassifierImpl(ABC):
    """Abstract base class for error classification algorithms."""

    def __init__(self, strategy: ClassificationStrategy) -> None:
        self.strategy = strategy
        self.logger = logging.getLogger(self.__class__.__name__)
        self.is_fitted = False

    @abstractmethod
    def _classify_error(self, error: Exception) -> ClassificationResult:
        """Classify a single error."""
        pass

    def fit(self, X: List[Exception], y: List[ErrorType]) -> "BaseErrorClassifierImpl":
        """Fit the classifier to training data."""
        self.logger.info(
            f"Fitting {self.strategy.value} classifier with {len(X)} samples"
        )
        # Most classifiers don't need explicit training, but this provides the interface
        self.is_fitted = True
        return self

    def predict(self, X: List[Exception]) -> List[ErrorType]:
        """Predict error types for given exceptions."""
        if not self.is_fitted:
            self.logger.warning("Classifier not fitted, using default behavior")

        results = []
        for error in X:
            result = self._classify_error(error)
            results.append(result.error_type)

        return results

    def predict_proba(self, X: List[Exception]) -> List[Dict[ErrorType, float]]:
        """Predict class probabilities for given exceptions."""
        if not self.is_fitted:
            self.logger.warning("Classifier not fitted, using default behavior")

        results = []
        for error in X:
            result = self._classify_error(error)
            # Convert confidence to probability distribution
            prob_dict = {result.error_type: result.confidence}
            # Add small probabilities for other error types
            for error_type in ErrorType:
                if error_type != result.error_type:
                    prob_dict[error_type] = (1.0 - result.confidence) / (
                        len(ErrorType) - 1
                    )
            results.append(prob_dict)

        return results

    def score(self, X: List[Exception], y: List[ErrorType]) -> float:
        """Return the mean accuracy on the given test data and labels."""
        predictions = self.predict(X)
        correct = sum(
            1 for pred, actual in zip(predictions, y, strict=True) if pred == actual
        )
        return correct / len(X) if X else 0.0


class RuleBasedClassifier(BaseErrorClassifierImpl):
    """Rule-based error classifier using predefined classification rules."""

    def __init__(self) -> None:
        super().__init__(ClassificationStrategy.RULE_BASED)
        self.classification_rules = self._initialize_rules()

    def _initialize_rules(self) -> List[Any]:
        """Initialize classification rules in order of specificity."""
        return [
            self._classify_provider_errors,
            self._classify_network_errors,
            self._classify_timeout_errors,
            self._classify_rate_limit_errors,
            self._classify_http_errors,
            self._classify_authentication_errors,
            self._classify_validation_errors,
            self._classify_file_system_errors,
            self._classify_security_errors,
            self._classify_api_errors,
        ]

    def _classify_error(self, error: Exception) -> ClassificationResult:
        """Classify an error using rule-based approach."""
        for rule in self.classification_rules:
            result = rule(error)
            if result:
                return result

        # Default classification for unknown errors
        metadata = _get_metadata_or_fallback(ErrorType.UNKNOWN_ERROR)
        return ClassificationResult(
            error_type=ErrorType.UNKNOWN_ERROR,
            confidence=0.1,
            metadata=metadata,
            classification_strategy=self.strategy,
            details={"error": str(error), "type": type(error).__name__},
        )

    def _classify_network_errors(
        self, error: Exception
    ) -> Optional[ClassificationResult]:
        """Classify network-related errors."""
        if isinstance(error, (ConnectionError, OSError)):
            metadata = _get_metadata_or_fallback(ErrorType.NETWORK_ERROR)
            return ClassificationResult(
                error_type=ErrorType.NETWORK_ERROR,
                confidence=0.9,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error)},
            )
        return None

    def _classify_timeout_errors(
        self, error: Exception
    ) -> Optional[ClassificationResult]:
        """Classify timeout errors."""
        if isinstance(error, (TimeoutError,)):
            metadata = _get_metadata_or_fallback(ErrorType.TIMEOUT_ERROR)
            return ClassificationResult(
                error_type=ErrorType.TIMEOUT_ERROR,
                confidence=0.9,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error)},
            )
        return None

    def _classify_rate_limit_errors(
        self, error: Exception
    ) -> Optional[ClassificationResult]:
        """Classify rate limit errors."""
        error_str = str(error).lower()
        if any(
            term in error_str for term in ["rate limit", "too many requests", "429"]
        ):
            metadata = _get_metadata_or_fallback(ErrorType.RATE_LIMIT_ERROR)
            return ClassificationResult(
                error_type=ErrorType.RATE_LIMIT_ERROR,
                confidence=0.8,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error)},
            )
        return None

    def _classify_http_errors(self, error: Exception) -> Optional[ClassificationResult]:
        """Classify HTTP status code errors."""
        if hasattr(error, "status"):
            status = getattr(error, "status", None)
            if status is not None:
                if 500 <= status < 600:
                    metadata = _get_metadata_or_fallback(ErrorType.SERVER_ERROR)
                    return ClassificationResult(
                        error_type=ErrorType.SERVER_ERROR,
                        confidence=0.9,
                        metadata=metadata,
                        classification_strategy=self.strategy,
                        details={"error": str(error), "status": status},
                    )
                elif status == 404:
                    metadata = _get_metadata_or_fallback(ErrorType.NOT_FOUND_ERROR)
                    return ClassificationResult(
                        error_type=ErrorType.NOT_FOUND_ERROR,
                        confidence=0.9,
                        metadata=metadata,
                        classification_strategy=self.strategy,
                        details={"error": str(error), "status": status},
                    )
                elif status in [401, 403]:
                    error_type = (
                        ErrorType.AUTHENTICATION_ERROR
                        if status == 401
                        else ErrorType.AUTHORIZATION_ERROR
                    )
                    metadata = _get_metadata_or_fallback(error_type)
                    return ClassificationResult(
                        error_type=error_type,
                        confidence=0.9,
                        metadata=metadata,
                        classification_strategy=self.strategy,
                        details={"error": str(error), "status": status},
                    )
        return None

    def _classify_authentication_errors(
        self, error: Exception
    ) -> Optional[ClassificationResult]:
        """Classify authentication errors."""
        error_str = str(error).lower()
        if any(
            term in error_str
            for term in ["unauthorized", "authentication", "invalid token", "401"]
        ):
            metadata = _get_metadata_or_fallback(ErrorType.AUTHENTICATION_ERROR)
            return ClassificationResult(
                error_type=ErrorType.AUTHENTICATION_ERROR,
                confidence=0.8,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error)},
            )
        return None

    def _classify_validation_errors(
        self, error: Exception
    ) -> Optional[ClassificationResult]:
        """Classify validation errors."""
        if isinstance(error, (ValueError, TypeError)):
            metadata = _get_metadata_or_fallback(ErrorType.VALIDATION_ERROR)
            return ClassificationResult(
                error_type=ErrorType.VALIDATION_ERROR,
                confidence=0.9,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error)},
            )
        return None

    def _classify_provider_errors(
        self, error: Exception
    ) -> Optional[ClassificationResult]:
        """Classify provider-specific errors."""
        error_str = str(error).lower()
        error_type_name = type(error).__name__.lower()

        # GitHub-specific errors
        if "github" in error_str or "pygithub" in error_type_name:
            return self._classify_github_errors(error, error_str)

        # GitLab-specific errors
        elif "gitlab" in error_str or "gitlab" in error_type_name:
            return self._classify_gitlab_errors(error, error_str)

        # Local Git errors
        elif "git" in error_str or "gitpython" in error_type_name:
            return self._classify_local_git_errors(error, error_str)

        return None

    def _classify_github_errors(
        self, error: Exception, error_str: str
    ) -> Optional[ClassificationResult]:
        """Classify GitHub-specific errors."""
        # Rate limiting
        if any(
            term in error_str for term in ["rate limit", "403", "too many requests"]
        ):
            metadata = _get_metadata_or_fallback(ErrorType.GITHUB_RATE_LIMIT_ERROR)
            return ClassificationResult(
                error_type=ErrorType.GITHUB_RATE_LIMIT_ERROR,
                confidence=0.9,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error), "provider": "github"},
            )

        # 2FA required
        elif any(term in error_str for term in ["2fa", "two-factor", "otp", "mfa"]):
            metadata = _get_metadata_or_fallback(ErrorType.GITHUB_2FA_ERROR)
            return ClassificationResult(
                error_type=ErrorType.GITHUB_2FA_ERROR,
                confidence=0.9,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error), "provider": "github"},
            )

        # SSH errors
        elif any(term in error_str for term in ["ssh", "key", "fingerprint"]):
            metadata = _get_metadata_or_fallback(ErrorType.GITHUB_SSH_ERROR)
            return ClassificationResult(
                error_type=ErrorType.GITHUB_SSH_ERROR,
                confidence=0.8,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error), "provider": "github"},
            )

        # General GitHub API errors
        else:
            metadata = _get_metadata_or_fallback(ErrorType.GITHUB_API_ERROR)
            return ClassificationResult(
                error_type=ErrorType.GITHUB_API_ERROR,
                confidence=0.7,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error), "provider": "github"},
            )

    def _classify_gitlab_errors(
        self, error: Exception, error_str: str
    ) -> Optional[ClassificationResult]:
        """Classify GitLab-specific errors."""
        # Rate limiting
        if any(
            term in error_str for term in ["rate limit", "429", "too many requests"]
        ):
            metadata = _get_metadata_or_fallback(ErrorType.GITLAB_RATE_LIMIT_ERROR)
            return ClassificationResult(
                error_type=ErrorType.GITLAB_RATE_LIMIT_ERROR,
                confidence=0.9,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error), "provider": "gitlab"},
            )

        # General GitLab API errors
        else:
            metadata = _get_metadata_or_fallback(ErrorType.GITLAB_API_ERROR)
            return ClassificationResult(
                error_type=ErrorType.GITLAB_API_ERROR,
                confidence=0.7,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error), "provider": "gitlab"},
            )

    def _classify_local_git_errors(
        self, error: Exception, error_str: str
    ) -> Optional[ClassificationResult]:
        """Classify local Git errors."""
        # Repository not found
        if any(
            term in error_str
            for term in ["not a git repository", "no such file", "repository"]
        ):
            metadata = _get_metadata_or_fallback(ErrorType.LOCAL_REPOSITORY_NOT_FOUND)
            return ClassificationResult(
                error_type=ErrorType.LOCAL_REPOSITORY_NOT_FOUND,
                confidence=0.9,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error), "provider": "local"},
            )

        # General local Git errors
        else:
            metadata = _get_metadata_or_fallback(ErrorType.LOCAL_GIT_ERROR)
            return ClassificationResult(
                error_type=ErrorType.LOCAL_GIT_ERROR,
                confidence=0.7,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error), "provider": "local"},
            )

    def _classify_file_system_errors(
        self, error: Exception
    ) -> Optional[ClassificationResult]:
        """Classify file system errors."""
        error_str = str(error).lower()

        # File not found
        if any(
            term in error_str for term in ["file not found", "no such file", "enoent"]
        ):
            metadata = _get_metadata_or_fallback(ErrorType.FILE_NOT_FOUND_ERROR)
            return ClassificationResult(
                error_type=ErrorType.FILE_NOT_FOUND_ERROR,
                confidence=0.9,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error)},
            )

        # Permission denied
        elif any(
            term in error_str
            for term in ["permission denied", "access denied", "eacces"]
        ):
            metadata = _get_metadata_or_fallback(ErrorType.PERMISSION_DENIED_ERROR)
            return ClassificationResult(
                error_type=ErrorType.PERMISSION_DENIED_ERROR,
                confidence=0.9,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error)},
            )

        return None

    def _classify_security_errors(
        self, error: Exception
    ) -> Optional[ClassificationResult]:
        """Classify security-related errors."""
        error_str = str(error).lower()

        # SSL/TLS errors
        if any(
            term in error_str for term in ["ssl", "tls", "certificate", "handshake"]
        ):
            metadata = _get_metadata_or_fallback(ErrorType.SSL_ERROR)
            return ClassificationResult(
                error_type=ErrorType.SSL_ERROR,
                confidence=0.8,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error)},
            )

        return None

    def _classify_api_errors(self, error: Exception) -> Optional[ClassificationResult]:
        """Classify API and service errors."""
        error_str = str(error).lower()

        # Service unavailable
        if any(
            term in error_str for term in ["service unavailable", "503", "unavailable"]
        ):
            metadata = _get_metadata_or_fallback(
                ErrorType.API_SERVICE_UNAVAILABLE_ERROR
            )
            return ClassificationResult(
                error_type=ErrorType.API_SERVICE_UNAVAILABLE_ERROR,
                confidence=0.8,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error)},
            )

        return None


class PatternBasedClassifier(BaseErrorClassifierImpl):
    """Pattern-based error classifier using keyword and regex matching."""

    def __init__(self) -> None:
        super().__init__(ClassificationStrategy.PATTERN_BASED)
        self.pattern_matchers = self._initialize_pattern_matchers()

    def _initialize_pattern_matchers(self) -> Dict[ErrorType, List[str]]:
        """Initialize pattern matchers for each error type."""
        matchers = {}
        for error_type in ErrorType:
            metadata = _get_metadata_or_fallback(error_type)
            if metadata:
                matchers[error_type] = metadata.patterns
        return matchers

    def _classify_error(self, error: Exception) -> ClassificationResult:
        """Classify an error using pattern matching."""
        error_str = str(error).lower()
        best_match = None
        best_confidence = 0.0

        matched_patterns = []
        for error_type, patterns in self.pattern_matchers.items():
            confidence = self._calculate_pattern_confidence(error_str, patterns)
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = error_type
                matched_patterns = patterns

        if best_match and best_confidence > 0.5:
            metadata = _get_metadata_or_fallback(best_match)
            return ClassificationResult(
                error_type=best_match,
                confidence=best_confidence,
                metadata=metadata,
                classification_strategy=self.strategy,
                details={"error": str(error), "matched_patterns": matched_patterns},
            )

        # Default to unknown error
        metadata = _get_metadata_or_fallback(ErrorType.UNKNOWN_ERROR)
        return ClassificationResult(
            error_type=ErrorType.UNKNOWN_ERROR,
            confidence=0.1,
            metadata=metadata,
            classification_strategy=self.strategy,
            details={"error": str(error)},
        )

    def _calculate_pattern_confidence(
        self, error_str: str, patterns: List[str]
    ) -> float:
        """Calculate confidence based on pattern matching."""
        if not patterns:
            return 0.0

        matches = 0
        for pattern in patterns:
            if pattern in error_str:
                matches += 1

        return matches / len(patterns) if patterns else 0.0


class HybridClassifier(BaseErrorClassifierImpl):
    """Hybrid classifier combining rule-based and pattern-based approaches."""

    def __init__(self) -> None:
        super().__init__(ClassificationStrategy.HYBRID)
        self.rule_classifier = RuleBasedClassifier()
        self.pattern_classifier = PatternBasedClassifier()
        self.weights = {"rule": 0.7, "pattern": 0.3}

    def _classify_error(self, error: Exception) -> ClassificationResult:
        """Classify an error using hybrid approach."""
        # Get results from both classifiers
        rule_result = self.rule_classifier._classify_error(error)
        pattern_result = self.pattern_classifier._classify_error(error)

        # Weighted combination
        if rule_result.error_type == pattern_result.error_type:
            # Both classifiers agree
            combined_confidence = min(
                1.0,
                rule_result.confidence * self.weights["rule"]
                + pattern_result.confidence * self.weights["pattern"],
            )
            return ClassificationResult(
                error_type=rule_result.error_type,
                confidence=combined_confidence,
                metadata=rule_result.metadata,
                classification_strategy=self.strategy,
                details={
                    "rule_confidence": rule_result.confidence,
                    "pattern_confidence": pattern_result.confidence,
                    "combined_confidence": combined_confidence,
                },
            )
        else:
            # Classifiers disagree, use rule-based result with lower confidence
            return ClassificationResult(
                error_type=rule_result.error_type,
                confidence=rule_result.confidence
                * 0.8,  # Reduce confidence due to disagreement
                metadata=rule_result.metadata,
                classification_strategy=self.strategy,
                details={
                    "rule_confidence": rule_result.confidence,
                    "pattern_confidence": pattern_result.confidence,
                    "disagreement": True,
                },
            )


class ClassificationAlgorithmFactory:
    """Factory for creating classification algorithms."""

    @staticmethod
    def create_classifier(strategy: ClassificationStrategy) -> BaseErrorClassifierImpl:
        """Create a classifier based on the specified strategy."""
        if strategy == ClassificationStrategy.RULE_BASED:
            return RuleBasedClassifier()
        elif strategy == ClassificationStrategy.PATTERN_BASED:
            return PatternBasedClassifier()
        elif strategy == ClassificationStrategy.HYBRID:
            return HybridClassifier()
        else:
            raise ValueError(f"Unsupported classification strategy: {strategy}")

    @staticmethod
    def create_all_classifiers() -> (
        Dict[ClassificationStrategy, BaseErrorClassifierImpl]
    ):
        """Create all available classifiers."""
        return {
            strategy: ClassificationAlgorithmFactory.create_classifier(strategy)
            for strategy in ClassificationStrategy
        }


def create_error_classification(
    error: Exception, strategy: ClassificationStrategy = ClassificationStrategy.HYBRID
) -> ErrorClassification:
    """Convenience function to create ErrorClassification from Exception."""
    classifier = ClassificationAlgorithmFactory.create_classifier(strategy)
    result = classifier._classify_error(error)

    return ErrorClassification(
        error_type=result.error_type,
        is_retryable=result.metadata.is_retryable,
        retry_delay=result.metadata.retry_delay,
        max_retries=result.metadata.max_retries,
        should_open_circuit=result.metadata.should_open_circuit,
        details=result.details,
    )
