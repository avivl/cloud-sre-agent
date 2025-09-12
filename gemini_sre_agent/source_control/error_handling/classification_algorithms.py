# gemini_sre_agent/source_control/error_handling/classification_algorithms.py

"""
Classification algorithms for error classification with sklearn-style interfaces.

This module provides various classification algorithms implementing Protocol-based
interfaces similar to scikit-learn for error classification tasks.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

from .core import ErrorClassification, ErrorType
from .error_types import (
    ErrorCategory,
    ErrorTypeMetadata,
    get_error_metadata,
)


logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result from error classification."""

    error_type: ErrorType
    confidence: float
    metadata: Dict[str, Any]
    classification_path: List[str]
    matched_patterns: List[str]
    suggested_actions: List[str]


@dataclass
class TrainingData:
    """Training data for classification algorithms."""

    error_messages: List[str]
    error_types: List[ErrorType]
    contexts: List[Dict[str, Any]]
    labels: List[str]


class BaseErrorClassifier(Protocol):
    """Base protocol for error classification algorithms."""

    def fit(self, training_data: TrainingData) -> None:
        """Fit the classifier to training data."""
        ...

    def predict(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        """Predict error type for a given error message."""
        ...

    def predict_proba(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[ErrorType, float]:
        """Predict error type probabilities."""
        ...

    def score(self, test_data: TrainingData) -> float:
        """Calculate classification accuracy score."""
        ...


class RuleBasedClassifier:
    """Rule-based classifier using pattern matching and heuristics."""

    def __init__(self, name: str = "rule_based_classifier"):
        """Initialize the rule-based classifier."""
        self.name = name
        self.logger = logging.getLogger(f"RuleBasedClassifier.{name}")
        self.rules: List[Tuple[str, ErrorType, float, List[str]]] = []
        self.compiled_patterns: Dict[str, re.Pattern] = {}
        self.is_fitted = False

    def fit(self, training_data: TrainingData) -> None:
        """Fit the classifier by building rules from training data."""
        self.logger.info(f"Fitting {self.name} with {len(training_data.error_messages)} samples")
        
        # Build rules from training data
        self._build_rules_from_data(training_data)
        
        # Compile patterns for performance
        self._compile_patterns()
        
        self.is_fitted = True
        self.logger.info(f"Fitted {self.name} with {len(self.rules)} rules")

    def _build_rules_from_data(self, training_data: TrainingData) -> None:
        """Build classification rules from training data."""
        # Group by error type
        type_groups: Dict[ErrorType, List[str]] = {}
        for error_msg, error_type in zip(training_data.error_messages, training_data.error_types, strict=True):
            if error_type not in type_groups:
                type_groups[error_type] = []
            type_groups[error_type].append(error_msg)

        # Create rules for each error type
        for error_type, messages in type_groups.items():
            patterns = self._extract_patterns(messages)
            for pattern in patterns:
                confidence = self._calculate_pattern_confidence(pattern, messages)
                keywords = self._extract_keywords(pattern)
                self.rules.append((pattern, error_type, confidence, keywords))

        # Sort rules by confidence (highest first)
        self.rules.sort(key=lambda x: x[2], reverse=True)

    def _extract_patterns(self, messages: List[str]) -> List[str]:
        """Extract regex patterns from error messages."""
        patterns = []
        
        # Common patterns for different error types
        common_patterns = [
            r"timeout|timed out|deadline exceeded",
            r"connection.*reset|reset by peer",
            r"network.*error|connection.*failed",
            r"dns.*error|name resolution",
            r"ssl.*error|tls.*error|certificate.*error",
            r"auth.*failed|invalid.*credentials|unauthorized",
            r"forbidden|access.*denied|permission.*denied",
            r"not.*found|404|missing.*resource",
            r"validation.*error|invalid.*input|bad.*request",
            r"config.*error|configuration.*error",
            r"file.*not.*found|no.*such.*file",
            r"disk.*space|no.*space|device.*full",
            r"rate.*limit|quota.*exceeded|throttle",
            r"server.*error|500|internal.*error",
            r"merge.*conflict|conflict.*github|conflict.*gitlab",
            r"git.*error|local.*git",
            r"ssh.*error|key.*error",
        ]
        
        # Test which patterns match the messages
        for pattern in common_patterns:
            if self._pattern_matches_messages(pattern, messages):
                patterns.append(pattern)
        
        return patterns

    def _pattern_matches_messages(self, pattern: str, messages: List[str]) -> bool:
        """Check if a pattern matches a significant portion of messages."""
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            matches = sum(1 for msg in messages if compiled.search(msg))
            return matches >= len(messages) * 0.3  # At least 30% match
        except re.error:
            return False

    def _calculate_pattern_confidence(self, pattern: str, messages: List[str]) -> float:
        """Calculate confidence score for a pattern."""
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            matches = sum(1 for msg in messages if compiled.search(msg))
            return matches / len(messages) if messages else 0.0
        except re.error:
            return 0.0

    def _extract_keywords(self, pattern: str) -> List[str]:
        """Extract keywords from a pattern."""
        # Simple keyword extraction
        keywords = []
        words = re.findall(r'\b\w+\b', pattern.lower())
        for word in words:
            if len(word) > 3 and word not in ['error', 'failed', 'invalid']:
                keywords.append(word)
        return keywords

    def _compile_patterns(self) -> None:
        """Compile regex patterns for performance."""
        for pattern, _, _, _ in self.rules:
            try:
                self.compiled_patterns[pattern] = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                self.logger.warning(f"Failed to compile pattern '{pattern}': {e}")

    def predict(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        """Predict error type for a given error message."""
        if not self.is_fitted:
            raise ValueError("Classifier must be fitted before prediction")

        best_match = None
        best_confidence = 0.0
        matched_patterns = []
        classification_path = []

        # Try each rule in order of confidence
        for pattern, error_type, confidence, _ in self.rules:
            if pattern in self.compiled_patterns:
                compiled_pattern = self.compiled_patterns[pattern]
                if compiled_pattern.search(error_message):
                    if confidence > best_confidence:
                        best_match = error_type
                        best_confidence = confidence
                        matched_patterns = [pattern]
                        classification_path = [f"matched_pattern:{pattern}"]
                    elif confidence == best_confidence:
                        matched_patterns.append(pattern)
                        classification_path.append(f"matched_pattern:{pattern}")

        # Fallback to keyword matching
        if not best_match:
            best_match, best_confidence, matched_patterns, classification_path = self._keyword_classification(
                error_message, context
            )

        # Get metadata for the predicted error type
        metadata = get_error_metadata(best_match.value) if best_match else None
        
        # Generate suggested actions
        suggested_actions = self._generate_suggested_actions(best_match, metadata, context)

        return ClassificationResult(
            error_type=best_match or ErrorType.UNKNOWN_ERROR,
            confidence=best_confidence,
            metadata=metadata.__dict__ if metadata else {},
            classification_path=classification_path,
            matched_patterns=matched_patterns,
            suggested_actions=suggested_actions,
        )

    def _keyword_classification(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> Tuple[Optional[ErrorType], float, List[str], List[str]]:
        """Fallback classification using keyword matching."""
        error_lower = error_message.lower()
        
        # Keyword to error type mapping
        keyword_mappings = {
            'timeout': ErrorType.TIMEOUT_ERROR,
            'network': ErrorType.NETWORK_ERROR,
            'connection': ErrorType.NETWORK_ERROR,
            'auth': ErrorType.AUTHENTICATION_ERROR,
            'unauthorized': ErrorType.AUTHENTICATION_ERROR,
            'forbidden': ErrorType.AUTHORIZATION_ERROR,
            'permission': ErrorType.PERMISSION_DENIED_ERROR,
            'not found': ErrorType.NOT_FOUND_ERROR,
            'validation': ErrorType.VALIDATION_ERROR,
            'invalid': ErrorType.INVALID_INPUT_ERROR,
            'config': ErrorType.CONFIGURATION_ERROR,
            'file': ErrorType.FILE_NOT_FOUND_ERROR,
            'disk': ErrorType.DISK_SPACE_ERROR,
            'rate': ErrorType.RATE_LIMIT_ERROR,
            'server': ErrorType.SERVER_ERROR,
            'merge': ErrorType.GITHUB_MERGE_CONFLICT,
            'git': ErrorType.LOCAL_GIT_ERROR,
            'ssh': ErrorType.GITHUB_SSH_ERROR,
        }

        matched_keywords = []
        for keyword, error_type in keyword_mappings.items():
            if keyword in error_lower:
                matched_keywords.append(keyword)
                return error_type, 0.5, [keyword], [f"keyword_match:{keyword}"]

        return None, 0.0, [], []

    def _generate_suggested_actions(self, error_type: Optional[ErrorType], metadata: Optional[ErrorTypeMetadata], context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Generate suggested actions based on error type and metadata."""
        if not error_type or not metadata:
            return ["Investigate error details", "Check logs for more information"]

        actions = []
        
        if metadata.is_retryable:
            actions.append(f"Retry after {metadata.retry_delay} seconds")
            actions.append(f"Maximum retries: {metadata.max_retries}")
        else:
            actions.append("Do not retry - fix underlying issue")

        if metadata.category == ErrorCategory.NETWORK:
            actions.append("Check network connectivity")
            actions.append("Verify DNS resolution")
        elif metadata.category == ErrorCategory.AUTHENTICATION:
            actions.append("Verify credentials")
            actions.append("Check token validity")
        elif metadata.category == ErrorCategory.AUTHORIZATION:
            actions.append("Check permissions")
            actions.append("Verify access rights")
        elif metadata.category == ErrorCategory.VALIDATION:
            actions.append("Validate input parameters")
            actions.append("Check request format")
        elif metadata.category == ErrorCategory.CONFIGURATION:
            actions.append("Check configuration settings")
            actions.append("Verify environment variables")
        elif metadata.category == ErrorCategory.FILE_SYSTEM:
            actions.append("Check file permissions")
            actions.append("Verify disk space")
        elif metadata.category == ErrorCategory.API:
            actions.append("Check API status")
            actions.append("Verify rate limits")

        return actions

    def predict_proba(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[ErrorType, float]:
        """Predict error type probabilities."""
        result = self.predict(error_message, context)
        probabilities = {result.error_type: result.confidence}
        
        # Add probabilities for other potential matches
        for pattern, error_type, confidence, _ in self.rules:
            if pattern in self.compiled_patterns:
                compiled_pattern = self.compiled_patterns[pattern]
                if compiled_pattern.search(error_message):
                    if error_type not in probabilities or confidence > probabilities[error_type]:
                        probabilities[error_type] = confidence

        return probabilities

    def score(self, test_data: TrainingData) -> float:
        """Calculate classification accuracy score."""
        if not self.is_fitted:
            raise ValueError("Classifier must be fitted before scoring")

        correct_predictions = 0
        total_predictions = len(test_data.error_messages)

        for error_msg, true_type in zip(test_data.error_messages, test_data.error_types, strict=True):
            predicted_result = self.predict(error_msg)
            if predicted_result.error_type == true_type:
                correct_predictions += 1

        return correct_predictions / total_predictions if total_predictions > 0 else 0.0


class PatternBasedClassifier:
    """Pattern-based classifier using advanced pattern matching."""

    def __init__(self, name: str = "pattern_based_classifier"):
        """Initialize the pattern-based classifier."""
        self.name = name
        self.logger = logging.getLogger(f"PatternBasedClassifier.{name}")
        self.patterns: Dict[ErrorType, List[Tuple[str, float, List[str]]]] = {}
        self.compiled_patterns: Dict[ErrorType, List[re.Pattern]] = {}
        self.is_fitted = False

    def fit(self, training_data: TrainingData) -> None:
        """Fit the classifier by learning patterns from training data."""
        self.logger.info(f"Fitting {self.name} with {len(training_data.error_messages)} samples")
        
        # Group by error type
        type_groups: Dict[ErrorType, List[str]] = {}
        for error_msg, error_type in zip(training_data.error_messages, training_data.error_types, strict=True):
            if error_type not in type_groups:
                type_groups[error_type] = []
            type_groups[error_type].append(error_msg)

        # Learn patterns for each error type
        for error_type, messages in type_groups.items():
            self.patterns[error_type] = self._learn_patterns(messages)
            self._compile_patterns_for_type(error_type)

        self.is_fitted = True
        self.logger.info(f"Fitted {self.name} with patterns for {len(self.patterns)} error types")

    def _learn_patterns(self, messages: List[str]) -> List[Tuple[str, float, List[str]]]:
        """Learn patterns from error messages."""
        patterns = []
        
        # Extract common substrings
        common_substrings = self._extract_common_substrings(messages)
        for substring, frequency in common_substrings.items():
            if frequency >= len(messages) * 0.3:  # At least 30% frequency
                pattern = re.escape(substring)
                confidence = frequency / len(messages)
                keywords = self._extract_keywords_from_substring(substring)
                patterns.append((pattern, confidence, keywords))

        # Extract regex patterns
        regex_patterns = self._extract_regex_patterns(messages)
        for pattern, confidence in regex_patterns.items():
            keywords = self._extract_keywords_from_pattern(pattern)
            patterns.append((pattern, confidence, keywords))

        return patterns

    def _extract_common_substrings(self, messages: List[str]) -> Dict[str, int]:
        """Extract common substrings from messages."""
        substring_counts = {}
        
        for message in messages:
            words = message.lower().split()
            for i in range(len(words)):
                for j in range(i + 1, min(i + 4, len(words) + 1)):  # 2-4 word phrases
                    phrase = ' '.join(words[i:j])
                    if len(phrase) > 5:  # Minimum phrase length
                        substring_counts[phrase] = substring_counts.get(phrase, 0) + 1

        return substring_counts

    def _extract_regex_patterns(self, messages: List[str]) -> Dict[str, float]:
        """Extract regex patterns from messages."""
        patterns = {}
        
        # Common error patterns
        common_patterns = [
            (r'\d{3}', 0.1),  # HTTP status codes
            (r'error|failed|exception', 0.2),  # Error keywords
            (r'timeout|timed out', 0.3),  # Timeout patterns
            (r'connection.*reset', 0.4),  # Connection patterns
            (r'permission.*denied', 0.5),  # Permission patterns
            (r'not.*found', 0.4),  # Not found patterns
            (r'invalid.*input', 0.3),  # Validation patterns
        ]
        
        for pattern, base_confidence in common_patterns:
            matches = sum(1 for msg in messages if re.search(pattern, msg, re.IGNORECASE))
            if matches > 0:
                confidence = (matches / len(messages)) * base_confidence
                patterns[pattern] = confidence

        return patterns

    def _extract_keywords_from_substring(self, substring: str) -> List[str]:
        """Extract keywords from a substring."""
        words = re.findall(r'\b\w+\b', substring.lower())
        return [word for word in words if len(word) > 3 and word not in ['error', 'failed']]

    def _extract_keywords_from_pattern(self, pattern: str) -> List[str]:
        """Extract keywords from a regex pattern."""
        # Extract word characters from the pattern
        words = re.findall(r'\b\w+\b', pattern.lower())
        return [word for word in words if len(word) > 3 and word not in ['error', 'failed']]

    def _compile_patterns_for_type(self, error_type: ErrorType) -> None:
        """Compile patterns for a specific error type."""
        self.compiled_patterns[error_type] = []
        for pattern, _, _ in self.patterns.get(error_type, []):
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self.compiled_patterns[error_type].append(compiled)
            except re.error as e:
                self.logger.warning(f"Failed to compile pattern '{pattern}' for {error_type}: {e}")

    def predict(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        """Predict error type for a given error message."""
        if not self.is_fitted:
            raise ValueError("Classifier must be fitted before prediction")

        best_error_type = None
        best_confidence = 0.0
        matched_patterns = []
        classification_path = []

        # Test patterns for each error type
        for error_type, patterns in self.patterns.items():
            type_confidence = 0.0
            type_matches = []
            
            for pattern, confidence, _ in patterns:
                if error_type in self.compiled_patterns:
                    for compiled_pattern in self.compiled_patterns[error_type]:
                        if compiled_pattern.search(error_message):
                            type_confidence += confidence
                            type_matches.append(pattern)
                            break

            if type_confidence > best_confidence:
                best_error_type = error_type
                best_confidence = type_confidence
                matched_patterns = type_matches
                classification_path = [f"pattern_match:{p}" for p in type_matches]

        # Fallback to unknown if no patterns match
        if not best_error_type:
            best_error_type = ErrorType.UNKNOWN_ERROR
            best_confidence = 0.0

        # Get metadata for the predicted error type
        metadata = get_error_metadata(best_error_type.value) if best_error_type else None
        
        # Generate suggested actions
        suggested_actions = self._generate_suggested_actions(best_error_type, metadata, context)

        return ClassificationResult(
            error_type=best_error_type,
            confidence=min(best_confidence, 1.0),  # Cap at 1.0
            metadata=metadata.__dict__ if metadata else {},
            classification_path=classification_path,
            matched_patterns=matched_patterns,
            suggested_actions=suggested_actions,
        )

    def _generate_suggested_actions(self, error_type: ErrorType, metadata: Optional[ErrorTypeMetadata], context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Generate suggested actions based on error type and metadata."""
        if not metadata:
            return ["Investigate error details", "Check logs for more information"]

        actions = []
        
        if metadata.is_retryable:
            actions.append(f"Retry after {metadata.retry_delay} seconds")
            actions.append(f"Maximum retries: {metadata.max_retries}")
        else:
            actions.append("Do not retry - fix underlying issue")

        # Add category-specific actions
        if metadata.category == ErrorCategory.NETWORK:
            actions.append("Check network connectivity")
            actions.append("Verify DNS resolution")
        elif metadata.category == ErrorCategory.AUTHENTICATION:
            actions.append("Verify credentials")
            actions.append("Check token validity")
        elif metadata.category == ErrorCategory.AUTHORIZATION:
            actions.append("Check permissions")
            actions.append("Verify access rights")

        return actions

    def predict_proba(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[ErrorType, float]:
        """Predict error type probabilities."""
        probabilities = {}
        
        for error_type, patterns in self.patterns.items():
            confidence = 0.0
            for _, pattern_confidence, _ in patterns:
                if error_type in self.compiled_patterns:
                    for compiled_pattern in self.compiled_patterns[error_type]:
                        if compiled_pattern.search(error_message):
                            confidence += pattern_confidence
                            break
            
            if confidence > 0:
                probabilities[error_type] = min(confidence, 1.0)

        return probabilities

    def score(self, test_data: TrainingData) -> float:
        """Calculate classification accuracy score."""
        if not self.is_fitted:
            raise ValueError("Classifier must be fitted before scoring")

        correct_predictions = 0
        total_predictions = len(test_data.error_messages)

        for error_msg, true_type in zip(test_data.error_messages, test_data.error_types, strict=True):
            predicted_result = self.predict(error_msg)
            if predicted_result.error_type == true_type:
                correct_predictions += 1

        return correct_predictions / total_predictions if total_predictions > 0 else 0.0


class HybridClassifier:
    """Hybrid classifier combining multiple classification approaches."""

    def __init__(self, name: str = "hybrid_classifier"):
        """Initialize the hybrid classifier."""
        self.name = name
        self.logger = logging.getLogger(f"HybridClassifier.{name}")
        self.rule_classifier = RuleBasedClassifier(f"{name}_rule")
        self.pattern_classifier = PatternBasedClassifier(f"{name}_pattern")
        self.weights = {"rule": 0.4, "pattern": 0.6}  # Weighted combination
        self.is_fitted = False

    def fit(self, training_data: TrainingData) -> None:
        """Fit both classifiers."""
        self.logger.info(f"Fitting {self.name} with {len(training_data.error_messages)} samples")
        
        self.rule_classifier.fit(training_data)
        self.pattern_classifier.fit(training_data)
        
        self.is_fitted = True
        self.logger.info(f"Fitted {self.name} with hybrid approach")

    def predict(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        """Predict using hybrid approach."""
        if not self.is_fitted:
            raise ValueError("Classifier must be fitted before prediction")

        # Get predictions from both classifiers
        rule_result = self.rule_classifier.predict(error_message, context)
        pattern_result = self.pattern_classifier.predict(error_message, context)

        # Combine results using weighted voting
        combined_confidence = (
            rule_result.confidence * self.weights["rule"] +
            pattern_result.confidence * self.weights["pattern"]
        )

        # Choose the result with higher confidence
        if rule_result.confidence > pattern_result.confidence:
            best_result = rule_result
            best_result.confidence = combined_confidence
        else:
            best_result = pattern_result
            best_result.confidence = combined_confidence

        # Combine metadata and suggestions
        best_result.metadata.update(pattern_result.metadata)
        best_result.classification_path.extend(pattern_result.classification_path)
        best_result.matched_patterns.extend(pattern_result.matched_patterns)
        best_result.suggested_actions.extend(pattern_result.suggested_actions)

        return best_result

    def predict_proba(self, error_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[ErrorType, float]:
        """Predict probabilities using hybrid approach."""
        rule_proba = self.rule_classifier.predict_proba(error_message, context)
        pattern_proba = self.pattern_classifier.predict_proba(error_message, context)

        # Combine probabilities
        combined_proba = {}
        all_types = set(rule_proba.keys()) | set(pattern_proba.keys())
        
        for error_type in all_types:
            rule_conf = rule_proba.get(error_type, 0.0)
            pattern_conf = pattern_proba.get(error_type, 0.0)
            combined_proba[error_type] = (
                rule_conf * self.weights["rule"] +
                pattern_conf * self.weights["pattern"]
            )

        return combined_proba

    def score(self, test_data: TrainingData) -> float:
        """Calculate hybrid classification accuracy score."""
        if not self.is_fitted:
            raise ValueError("Classifier must be fitted before scoring")

        correct_predictions = 0
        total_predictions = len(test_data.error_messages)

        for error_msg, true_type in zip(test_data.error_messages, test_data.error_types, strict=True):
            predicted_result = self.predict(error_msg)
            if predicted_result.error_type == true_type:
                correct_predictions += 1

        return correct_predictions / total_predictions if total_predictions > 0 else 0.0


class ClassifierFactory:
    """Factory for creating classification algorithms."""

    @staticmethod
    def create_classifier(algorithm: str, **kwargs) -> BaseErrorClassifier:
        """Create a classifier instance."""
        if algorithm == "rule_based":
            return RuleBasedClassifier(**kwargs)
        elif algorithm == "pattern_based":
            return PatternBasedClassifier(**kwargs)
        elif algorithm == "hybrid":
            return HybridClassifier(**kwargs)
        else:
            raise ValueError(f"Unknown classifier algorithm: {algorithm}")

    @staticmethod
    def get_available_algorithms() -> List[str]:
        """Get list of available classifier algorithms."""
        return ["rule_based", "pattern_based", "hybrid"]


def create_error_classification(result: ClassificationResult) -> ErrorClassification:
    """Convert ClassificationResult to ErrorClassification."""
    metadata = result.metadata
    return ErrorClassification(
        error_type=result.error_type,
        is_retryable=metadata.get("is_retryable", False),
        retry_delay=metadata.get("retry_delay", 0.0),
        max_retries=metadata.get("max_retries", 0),
        should_open_circuit=metadata.get("should_open_circuit", False),
        details={
            "classification_path": result.classification_path,
            "matched_patterns": result.matched_patterns,
            "suggested_actions": result.suggested_actions,
            "confidence": result.confidence,
        },
    )
