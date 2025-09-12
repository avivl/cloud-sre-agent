# gemini_sre_agent/source_control/error_handling/error_patterns.py

"""
Error pattern detection and matching for source control operations.

This module provides specialized pattern matching classes for error detection
using regex, keyword, and semantic pattern matching algorithms.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

from .core import ErrorType

logger = logging.getLogger(__name__)


@dataclass
class PatternMatch:
    """Result of pattern matching operation."""

    pattern: str
    error_type: ErrorType
    confidence: float
    matched_text: str
    start_pos: int
    end_pos: int
    groups: Dict[str, str]
    metadata: Dict[str, Any]


@dataclass
class PatternConfig:
    """Configuration for pattern matching."""

    case_sensitive: bool = False
    multiline: bool = False
    dotall: bool = False
    verbose: bool = False
    max_matches: int = 10
    timeout: float = 1.0


class PatternMatcher(Protocol):
    """Protocol for pattern matching implementations."""

    def match(
        self, text: str, context: Optional[Dict[str, Any]] = None
    ) -> List[PatternMatch]:
        """Match patterns against text."""
        ...

    def compile_patterns(self) -> None:
        """Compile patterns for performance."""
        ...

    def add_pattern(
        self, pattern: Any, error_type: ErrorType, confidence: float = 1.0
    ) -> None:
        """Add a new pattern to the matcher."""
        ...

    def remove_pattern(self, pattern: Any) -> None:
        """Remove a pattern from the matcher."""
        ...

    def get_patterns(self) -> List[Tuple[str, ErrorType, float]]:
        """Get all patterns in the matcher."""
        ...


class RegexPatternMatcher:
    """Regex-based pattern matcher for error detection."""

    def __init__(
        self, name: str = "regex_matcher", config: Optional[PatternConfig] = None
    ):
        """Initialize the regex pattern matcher."""
        self.name = name
        self.config = config or PatternConfig()
        self.logger = logging.getLogger(f"RegexPatternMatcher.{name}")
        self.patterns: List[Tuple[str, ErrorType, float, re.Pattern]] = []
        self.is_compiled = False

    def add_pattern(
        self, pattern: str, error_type: ErrorType, confidence: float = 1.0
    ) -> None:
        """Add a new regex pattern to the matcher."""
        try:
            flags = 0
            if not self.config.case_sensitive:
                flags |= re.IGNORECASE
            if self.config.multiline:
                flags |= re.MULTILINE
            if self.config.dotall:
                flags |= re.DOTALL
            if self.config.verbose:
                flags |= re.VERBOSE

            compiled_pattern = re.compile(pattern, flags)
            self.patterns.append((pattern, error_type, confidence, compiled_pattern))
            self.logger.debug(f"Added pattern: {pattern} -> {error_type}")
        except re.error as e:
            self.logger.error(f"Failed to compile pattern '{pattern}': {e}")

    def remove_pattern(self, pattern: str) -> None:
        """Remove a pattern from the matcher."""
        self.patterns = [
            (p, et, conf, comp) for p, et, conf, comp in self.patterns if p != pattern
        ]
        self.logger.debug(f"Removed pattern: {pattern}")

    def get_patterns(self) -> List[Tuple[str, ErrorType, float]]:
        """Get all patterns in the matcher."""
        return [
            (pattern, error_type, confidence)
            for pattern, error_type, confidence, _ in self.patterns
        ]

    def compile_patterns(self) -> None:
        """Compile all patterns for performance."""
        self.is_compiled = True
        self.logger.info(f"Compiled {len(self.patterns)} patterns")

    def match(
        self, text: str, context: Optional[Dict[str, Any]] = None
    ) -> List[PatternMatch]:
        """Match patterns against text."""
        if not self.is_compiled:
            self.compile_patterns()

        matches = []
        context = context or {}

        for pattern, error_type, confidence, compiled_pattern in self.patterns:
            try:
                for match in compiled_pattern.finditer(text):
                    if len(matches) >= self.config.max_matches:
                        break

                    groups = match.groupdict() if match.groupdict() else {}
                    matched_text = match.group(0)

                    # Calculate confidence based on match quality
                    match_confidence = self._calculate_match_confidence(
                        pattern, matched_text, confidence, context
                    )

                    pattern_match = PatternMatch(
                        pattern=pattern,
                        error_type=error_type,
                        confidence=match_confidence,
                        matched_text=matched_text,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        groups=groups,
                        metadata={
                            "matcher": self.name,
                            "pattern_type": "regex",
                            "context": context,
                        },
                    )

                    matches.append(pattern_match)

            except re.error as e:
                self.logger.warning(f"Error matching pattern '{pattern}': {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error matching pattern '{pattern}': {e}")

        # Sort matches by confidence (highest first)
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches

    def _calculate_match_confidence(
        self,
        pattern: str,
        matched_text: str,
        base_confidence: float,
        context: Dict[str, Any],
    ) -> float:
        """Calculate confidence score for a match."""
        confidence = base_confidence

        # Boost confidence for longer matches
        if len(matched_text) > 10:
            confidence *= 1.1

        # Boost confidence for exact word matches
        if re.search(r"\b" + re.escape(matched_text) + r"\b", pattern):
            confidence *= 1.2

        # Boost confidence based on context
        if context.get("error_context") == "network":
            if "network" in pattern.lower() or "connection" in pattern.lower():
                confidence *= 1.1

        return min(confidence, 1.0)


class KeywordPatternMatcher:
    """Keyword-based pattern matcher for error detection."""

    def __init__(
        self, name: str = "keyword_matcher", config: Optional[PatternConfig] = None
    ):
        """Initialize the keyword pattern matcher."""
        self.name = name
        self.config = config or PatternConfig()
        self.logger = logging.getLogger(f"KeywordPatternMatcher.{name}")
        self.keyword_patterns: List[Tuple[List[str], ErrorType, float]] = []
        self.is_compiled = False

    def add_pattern(
        self, pattern: Any, error_type: ErrorType, confidence: float = 1.0
    ) -> None:
        """Add a new keyword pattern to the matcher."""
        if isinstance(pattern, list):
            keywords = pattern
        else:
            keywords = [pattern]
        self.keyword_patterns.append((keywords, error_type, confidence))
        self.logger.debug(f"Added keyword pattern: {keywords} -> {error_type}")

    def remove_pattern(self, pattern: Any) -> None:
        """Remove a keyword pattern from the matcher."""
        if isinstance(pattern, list):
            keywords = pattern
        else:
            keywords = [pattern]
        self.keyword_patterns = [
            (kw, et, conf) for kw, et, conf in self.keyword_patterns if kw != keywords
        ]
        self.logger.debug(f"Removed keyword pattern: {keywords}")

    def get_patterns(self) -> List[Tuple[str, ErrorType, float]]:
        """Get all patterns in the matcher."""
        return [
            (" ".join(keywords), error_type, confidence)
            for keywords, error_type, confidence in self.keyword_patterns
        ]

    def compile_patterns(self) -> None:
        """Compile keyword patterns for performance."""
        self.is_compiled = True
        self.logger.info(f"Compiled {len(self.keyword_patterns)} keyword patterns")

    def match(
        self, text: str, context: Optional[Dict[str, Any]] = None
    ) -> List[PatternMatch]:
        """Match keyword patterns against text."""
        if not self.is_compiled:
            self.compile_patterns()

        matches = []
        context = context or {}
        text_lower = text.lower() if not self.config.case_sensitive else text

        for keywords, error_type, confidence in self.keyword_patterns:
            try:
                # Check if all keywords are present
                keyword_matches = []
                for keyword in keywords:
                    keyword_lower = (
                        keyword.lower() if not self.config.case_sensitive else keyword
                    )
                    if keyword_lower in text_lower:
                        # Find the position of the keyword
                        start_pos = text_lower.find(keyword_lower)
                        end_pos = start_pos + len(keyword)
                        keyword_matches.append((keyword, start_pos, end_pos))

                if len(keyword_matches) == len(keywords):
                    # All keywords found, create a match
                    if len(matches) >= self.config.max_matches:
                        break

                    # Calculate confidence based on keyword proximity and context
                    match_confidence = self._calculate_keyword_confidence(
                        keywords, keyword_matches, confidence, context
                    )

                    # Find the best position for the match
                    start_pos = min(pos for _, pos, _ in keyword_matches)
                    end_pos = max(pos + len for _, pos, len in keyword_matches)

                    pattern_match = PatternMatch(
                        pattern=" ".join(keywords),
                        error_type=error_type,
                        confidence=match_confidence,
                        matched_text=text[start_pos:end_pos],
                        start_pos=start_pos,
                        end_pos=end_pos,
                        groups={},
                        metadata={
                            "matcher": self.name,
                            "pattern_type": "keyword",
                            "keywords": keywords,
                            "context": context,
                        },
                    )

                    matches.append(pattern_match)

            except Exception as e:
                self.logger.error(f"Error matching keyword pattern {keywords}: {e}")

        # Sort matches by confidence (highest first)
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches

    def _calculate_keyword_confidence(
        self,
        keywords: List[str],
        matches: List[Tuple[str, int, int]],
        base_confidence: float,
        context: Dict[str, Any],
    ) -> float:
        """Calculate confidence score for keyword matches."""
        confidence = base_confidence

        # Boost confidence for more keywords
        confidence *= 1 + len(keywords) * 0.1

        # Boost confidence for keyword proximity
        if len(matches) > 1:
            positions = [pos for _, pos, _ in matches]
            max_distance = max(positions) - min(positions)
            if max_distance < 100:  # Keywords close together
                confidence *= 1.2

        # Boost confidence based on context
        if context.get("error_context") == "network":
            if any(
                "network" in kw.lower() or "connection" in kw.lower() for kw in keywords
            ):
                confidence *= 1.1

        return min(confidence, 1.0)


class SemanticPatternMatcher:
    """Semantic pattern matcher using fuzzy matching and similarity."""

    def __init__(
        self, name: str = "semantic_matcher", config: Optional[PatternConfig] = None
    ):
        """Initialize the semantic pattern matcher."""
        self.name = name
        self.config = config or PatternConfig()
        self.logger = logging.getLogger(f"SemanticPatternMatcher.{name}")
        self.semantic_patterns: List[Tuple[str, ErrorType, float, List[str]]] = []
        self.is_compiled = False

    def add_pattern(
        self,
        pattern: str,
        error_type: ErrorType,
        confidence: float = 1.0,
        synonyms: Optional[List[str]] = None,
    ) -> None:
        """Add a new semantic pattern to the matcher."""
        synonyms = synonyms or []
        self.semantic_patterns.append((pattern, error_type, confidence, synonyms))
        self.logger.debug(f"Added semantic pattern: {pattern} -> {error_type}")

    def remove_pattern(self, pattern: str) -> None:
        """Remove a semantic pattern from the matcher."""
        self.semantic_patterns = [
            (p, et, conf, syn)
            for p, et, conf, syn in self.semantic_patterns
            if p != pattern
        ]
        self.logger.debug(f"Removed semantic pattern: {pattern}")

    def get_patterns(self) -> List[Tuple[str, ErrorType, float]]:
        """Get all patterns in the matcher."""
        return [
            (pattern, error_type, confidence)
            for pattern, error_type, confidence, _ in self.semantic_patterns
        ]

    def compile_patterns(self) -> None:
        """Compile semantic patterns for performance."""
        self.is_compiled = True
        self.logger.info(f"Compiled {len(self.semantic_patterns)} semantic patterns")

    def match(
        self, text: str, context: Optional[Dict[str, Any]] = None
    ) -> List[PatternMatch]:
        """Match semantic patterns against text."""
        if not self.is_compiled:
            self.compile_patterns()

        matches = []
        context = context or {}

        for pattern, error_type, confidence, synonyms in self.semantic_patterns:
            try:
                # Calculate semantic similarity
                similarity = self._calculate_semantic_similarity(
                    pattern, text, synonyms
                )

                if similarity > 0.3:  # Minimum similarity threshold
                    if len(matches) >= self.config.max_matches:
                        break

                    # Find the best matching substring
                    best_match = self._find_best_substring_match(
                        pattern, text, synonyms
                    )

                    if best_match:
                        match_confidence = confidence * similarity

                        pattern_match = PatternMatch(
                            pattern=pattern,
                            error_type=error_type,
                            confidence=match_confidence,
                            matched_text=best_match["text"],
                            start_pos=best_match["start"],
                            end_pos=best_match["end"],
                            groups={},
                            metadata={
                                "matcher": self.name,
                                "pattern_type": "semantic",
                                "similarity": similarity,
                                "synonyms": synonyms,
                                "context": context,
                            },
                        )

                        matches.append(pattern_match)

            except Exception as e:
                self.logger.error(f"Error matching semantic pattern '{pattern}': {e}")

        # Sort matches by confidence (highest first)
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches

    def _calculate_semantic_similarity(
        self, pattern: str, text: str, synonyms: List[str]
    ) -> float:
        """Calculate semantic similarity between pattern and text."""
        # Simple word-based similarity
        pattern_words = set(pattern.lower().split())
        text_words = set(text.lower().split())
        synonyms_words = set()
        for synonym in synonyms:
            synonyms_words.update(synonym.lower().split())

        # Calculate Jaccard similarity
        intersection = pattern_words.intersection(text_words)
        union = pattern_words.union(text_words)

        base_similarity = len(intersection) / len(union) if union else 0.0

        # Boost similarity for synonym matches
        synonym_intersection = synonyms_words.intersection(text_words)
        if synonym_intersection:
            base_similarity += len(synonym_intersection) * 0.1

        return min(base_similarity, 1.0)

    def _find_best_substring_match(
        self, pattern: str, text: str, synonyms: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Find the best matching substring in the text."""
        pattern_words = pattern.lower().split()
        text_lower = text.lower()

        best_match = None
        best_score = 0.0

        # Try to find the pattern words in sequence
        for i in range(len(text_lower)):
            for j in range(i + len(pattern), len(text_lower) + 1):
                substring = text_lower[i:j]
                score = self._calculate_substring_score(
                    pattern_words, substring, synonyms
                )

                if score > best_score:
                    best_score = score
                    best_match = {
                        "text": text[i:j],
                        "start": i,
                        "end": j,
                        "score": score,
                    }

        return best_match

    def _calculate_substring_score(
        self, pattern_words: List[str], substring: str, synonyms: List[str]
    ) -> float:
        """Calculate score for a substring match."""
        substring_words = substring.split()
        score = 0.0

        for pattern_word in pattern_words:
            if pattern_word in substring_words:
                score += 1.0
            else:
                # Check synonyms
                for synonym in synonyms:
                    if synonym.lower() in substring_words:
                        score += 0.5
                        break

        return score / len(pattern_words) if pattern_words else 0.0


class PatternMatcherFactory:
    """Factory for creating pattern matchers."""

    @staticmethod
    def create_matcher(
        matcher_type: str,
        name: Optional[str] = None,
        config: Optional[PatternConfig] = None,
    ) -> PatternMatcher:
        """Create a pattern matcher instance."""
        if matcher_type == "regex":
            return RegexPatternMatcher(name or "regex_matcher", config)
        elif matcher_type == "keyword":
            return KeywordPatternMatcher(name or "keyword_matcher", config)
        elif matcher_type == "semantic":
            return SemanticPatternMatcher(name or "semantic_matcher", config)
        else:
            raise ValueError(f"Unknown matcher type: {matcher_type}")

    @staticmethod
    def get_available_matchers() -> List[str]:
        """Get list of available matcher types."""
        return ["regex", "keyword", "semantic"]


class PatternRegistry:
    """Registry for managing error patterns and matchers."""

    def __init__(self) -> None:
        """Initialize the pattern registry."""
        self.matchers: Dict[str, PatternMatcher] = {}
        self.pattern_cache: Dict[str, List[PatternMatch]] = {}
        self.logger = logging.getLogger("PatternRegistry")

    def add_matcher(self, name: str, matcher: PatternMatcher) -> None:
        """Add a pattern matcher to the registry."""
        self.matchers[name] = matcher
        self.logger.info(f"Added matcher: {name}")

    def remove_matcher(self, name: str) -> None:
        """Remove a pattern matcher from the registry."""
        if name in self.matchers:
            del self.matchers[name]
            self.logger.info(f"Removed matcher: {name}")

    def match_all(
        self, text: str, context: Optional[Dict[str, Any]] = None
    ) -> List[PatternMatch]:
        """Match text against all registered matchers."""
        all_matches = []
        context = context or {}

        for name, matcher in self.matchers.items():
            try:
                matches = matcher.match(text, context)
                all_matches.extend(matches)
            except Exception as e:
                self.logger.error(f"Error in matcher {name}: {e}")

        # Sort all matches by confidence
        all_matches.sort(key=lambda x: x.confidence, reverse=True)
        return all_matches

    def get_best_match(
        self, text: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[PatternMatch]:
        """Get the best pattern match for text."""
        matches = self.match_all(text, context)
        return matches[0] if matches else None

    def get_matches_by_type(
        self, text: str, error_type: ErrorType, context: Optional[Dict[str, Any]] = None
    ) -> List[PatternMatch]:
        """Get all matches for a specific error type."""
        all_matches = self.match_all(text, context)
        return [match for match in all_matches if match.error_type == error_type]

    def clear_cache(self) -> None:
        """Clear the pattern match cache."""
        self.pattern_cache.clear()
        self.logger.info("Cleared pattern match cache")

    def get_matcher_names(self) -> List[str]:
        """Get names of all registered matchers."""
        return list(self.matchers.keys())

    def get_matcher(self, name: str) -> Optional[PatternMatcher]:
        """Get a specific matcher by name."""
        return self.matchers.get(name)


# Global pattern registry
pattern_registry = PatternRegistry()


def initialize_default_patterns() -> None:
    """Initialize default error patterns for common error types."""
    # Create regex matcher
    regex_matcher = PatternMatcherFactory.create_matcher("regex", "default_regex")

    # Add common error patterns
    regex_matcher.add_pattern(
        r"timeout|timed out|deadline exceeded", ErrorType.TIMEOUT_ERROR, 0.9
    )
    regex_matcher.add_pattern(
        r"connection.*reset|reset by peer", ErrorType.CONNECTION_RESET_ERROR, 0.9
    )
    regex_matcher.add_pattern(
        r"network.*error|connection.*failed", ErrorType.NETWORK_ERROR, 0.8
    )
    regex_matcher.add_pattern(r"dns.*error|name resolution", ErrorType.DNS_ERROR, 0.9)
    regex_matcher.add_pattern(
        r"ssl.*error|tls.*error|certificate.*error", ErrorType.SSL_ERROR, 0.9
    )
    regex_matcher.add_pattern(
        r"auth.*failed|invalid.*credentials|unauthorized",
        ErrorType.AUTHENTICATION_ERROR,
        0.9,
    )
    regex_matcher.add_pattern(
        r"forbidden|access.*denied|permission.*denied",
        ErrorType.AUTHORIZATION_ERROR,
        0.9,
    )
    regex_matcher.add_pattern(
        r"not.*found|404|missing.*resource", ErrorType.NOT_FOUND_ERROR, 0.8
    )
    regex_matcher.add_pattern(
        r"validation.*error|invalid.*input|bad.*request",
        ErrorType.VALIDATION_ERROR,
        0.8,
    )
    regex_matcher.add_pattern(
        r"config.*error|configuration.*error", ErrorType.CONFIGURATION_ERROR, 0.8
    )
    regex_matcher.add_pattern(
        r"file.*not.*found|no.*such.*file", ErrorType.FILE_NOT_FOUND_ERROR, 0.8
    )
    regex_matcher.add_pattern(
        r"disk.*space|no.*space|device.*full", ErrorType.DISK_SPACE_ERROR, 0.9
    )
    regex_matcher.add_pattern(
        r"rate.*limit|quota.*exceeded|throttle", ErrorType.RATE_LIMIT_ERROR, 0.9
    )
    regex_matcher.add_pattern(
        r"server.*error|500|internal.*error", ErrorType.SERVER_ERROR, 0.8
    )
    regex_matcher.add_pattern(
        r"merge.*conflict|conflict.*github|conflict.*gitlab",
        ErrorType.GITHUB_MERGE_CONFLICT,
        0.9,
    )
    regex_matcher.add_pattern(r"git.*error|local.*git", ErrorType.LOCAL_GIT_ERROR, 0.8)
    regex_matcher.add_pattern(r"ssh.*error|key.*error", ErrorType.GITHUB_SSH_ERROR, 0.9)

    # Create keyword matcher
    keyword_matcher = PatternMatcherFactory.create_matcher("keyword", "default_keyword")

    # Add keyword patterns
    keyword_matcher.add_pattern(
        ["timeout", "timed", "out"], ErrorType.TIMEOUT_ERROR, 0.8
    )
    keyword_matcher.add_pattern(
        ["connection", "reset"], ErrorType.CONNECTION_RESET_ERROR, 0.8
    )
    keyword_matcher.add_pattern(["network", "error"], ErrorType.NETWORK_ERROR, 0.7)
    keyword_matcher.add_pattern(["dns", "resolution"], ErrorType.DNS_ERROR, 0.8)
    keyword_matcher.add_pattern(["ssl", "tls", "certificate"], ErrorType.SSL_ERROR, 0.8)
    keyword_matcher.add_pattern(
        ["auth", "failed", "unauthorized"], ErrorType.AUTHENTICATION_ERROR, 0.8
    )
    keyword_matcher.add_pattern(
        ["forbidden", "access", "denied"], ErrorType.AUTHORIZATION_ERROR, 0.8
    )
    keyword_matcher.add_pattern(["not", "found", "404"], ErrorType.NOT_FOUND_ERROR, 0.7)
    keyword_matcher.add_pattern(
        ["validation", "invalid", "input"], ErrorType.VALIDATION_ERROR, 0.7
    )
    keyword_matcher.add_pattern(
        ["config", "configuration"], ErrorType.CONFIGURATION_ERROR, 0.7
    )
    keyword_matcher.add_pattern(
        ["file", "not", "found"], ErrorType.FILE_NOT_FOUND_ERROR, 0.7
    )
    keyword_matcher.add_pattern(
        ["disk", "space", "full"], ErrorType.DISK_SPACE_ERROR, 0.8
    )
    keyword_matcher.add_pattern(
        ["rate", "limit", "quota"], ErrorType.RATE_LIMIT_ERROR, 0.8
    )
    keyword_matcher.add_pattern(["server", "error", "500"], ErrorType.SERVER_ERROR, 0.7)
    keyword_matcher.add_pattern(
        ["merge", "conflict"], ErrorType.GITHUB_MERGE_CONFLICT, 0.8
    )
    keyword_matcher.add_pattern(["git", "error"], ErrorType.LOCAL_GIT_ERROR, 0.7)
    keyword_matcher.add_pattern(
        ["ssh", "key", "error"], ErrorType.GITHUB_SSH_ERROR, 0.8
    )

    # Create semantic matcher
    semantic_matcher = SemanticPatternMatcher("default_semantic")

    # Add semantic patterns
    semantic_matcher.add_pattern(
        "connection timeout", ErrorType.TIMEOUT_ERROR, 0.8, ["timeout", "timed out"]
    )
    semantic_matcher.add_pattern(
        "network connectivity issue",
        ErrorType.NETWORK_ERROR,
        0.8,
        ["network", "connection"],
    )
    semantic_matcher.add_pattern(
        "authentication failure",
        ErrorType.AUTHENTICATION_ERROR,
        0.8,
        ["auth", "login", "credentials"],
    )
    semantic_matcher.add_pattern(
        "permission denied",
        ErrorType.AUTHORIZATION_ERROR,
        0.8,
        ["forbidden", "access denied"],
    )
    semantic_matcher.add_pattern(
        "resource not found", ErrorType.NOT_FOUND_ERROR, 0.8, ["missing", "not found"]
    )
    semantic_matcher.add_pattern(
        "input validation error",
        ErrorType.VALIDATION_ERROR,
        0.8,
        ["invalid", "bad request"],
    )
    semantic_matcher.add_pattern(
        "configuration problem", ErrorType.CONFIGURATION_ERROR, 0.8, ["config", "setup"]
    )
    semantic_matcher.add_pattern(
        "file system error", ErrorType.FILE_NOT_FOUND_ERROR, 0.8, ["file", "disk"]
    )
    semantic_matcher.add_pattern(
        "rate limit exceeded", ErrorType.RATE_LIMIT_ERROR, 0.8, ["quota", "throttle"]
    )
    semantic_matcher.add_pattern(
        "server internal error", ErrorType.SERVER_ERROR, 0.8, ["server", "internal"]
    )
    semantic_matcher.add_pattern(
        "merge conflict", ErrorType.GITHUB_MERGE_CONFLICT, 0.8, ["conflict", "merge"]
    )
    semantic_matcher.add_pattern(
        "git operation failed", ErrorType.LOCAL_GIT_ERROR, 0.8, ["git", "command"]
    )
    semantic_matcher.add_pattern(
        "ssh authentication failed", ErrorType.GITHUB_SSH_ERROR, 0.8, ["ssh", "key"]
    )

    # Register matchers
    pattern_registry.add_matcher("regex", regex_matcher)
    pattern_registry.add_matcher("keyword", keyword_matcher)
    pattern_registry.add_matcher("semantic", semantic_matcher)

    # Compile all patterns
    for matcher in pattern_registry.matchers.values():
        matcher.compile_patterns()

    logger.info("Initialized default error patterns")


def match_error_patterns(
    text: str, context: Optional[Dict[str, Any]] = None
) -> List[PatternMatch]:
    """Match error patterns against text using the global registry."""
    return pattern_registry.match_all(text, context)


def get_best_error_match(
    text: str, context: Optional[Dict[str, Any]] = None
) -> Optional[PatternMatch]:
    """Get the best error pattern match for text."""
    return pattern_registry.get_best_match(text, context)


def get_error_matches_by_type(
    text: str, error_type: ErrorType, context: Optional[Dict[str, Any]] = None
) -> List[PatternMatch]:
    """Get all error pattern matches for a specific error type."""
    return pattern_registry.get_matches_by_type(text, error_type, context)
