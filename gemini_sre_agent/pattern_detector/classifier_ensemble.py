# gemini_sre_agent/pattern_detector/classifier_ensemble.py

"""
Ensemble pattern classification system.

This module provides ensemble methods for pattern classification that combine
multiple pattern matchers and confidence calculators to improve accuracy and
robustness of pattern detection.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from ..logger import setup_logging
from .confidence_calculators import ConfidenceRuleFactory, ConfidenceScoreProcessor
from .models import (
    PatternMatch,
    ThresholdResult,
    TimeWindow,
)
from .pattern_matchers import (
    PatternMatcherConfig,
    PatternMatcherFactory,
)


@dataclass
class EnsembleConfig:
    """Configuration for ensemble pattern classification."""

    # Voting strategy
    voting_strategy: str = "weighted"  # "majority", "weighted", "consensus"

    # Confidence thresholds
    min_ensemble_confidence: float = 0.4
    min_individual_confidence: float = 0.2

    # Weighting factors
    confidence_weight: float = 0.6
    frequency_weight: float = 0.3
    recency_weight: float = 0.1

    # Ensemble size limits
    max_patterns_per_ensemble: int = 5
    min_agreement_threshold: float = 0.3

    # Pattern-specific configurations
    pattern_configs: Optional[Dict[str, PatternMatcherConfig]] = None

    def __post_init__(self) -> None:
        """Set default pattern configurations."""
        if self.pattern_configs is None:
            self.pattern_configs = self._get_default_pattern_configs()

    def _get_default_pattern_configs(self) -> Dict[str, PatternMatcherConfig]:
        """Get default pattern matcher configurations."""
        return {
            "cascade_failure": PatternMatcherConfig(
                min_confidence=0.3,
                min_services=2,
            ),
            "service_degradation": PatternMatcherConfig(
                min_confidence=0.3,
                single_service_threshold=0.8,
            ),
            "traffic_spike": PatternMatcherConfig(
                min_confidence=0.2,
                concurrent_error_threshold=10,
            ),
            "configuration_issue": PatternMatcherConfig(
                min_confidence=0.3,
                keywords=["config", "configuration", "settings", "invalid", "missing"],
                rapid_onset_threshold_seconds=60,
            ),
            "dependency_failure": PatternMatcherConfig(
                min_confidence=0.3,
                keywords=[
                    "timeout",
                    "connection",
                    "unavailable",
                    "refused",
                    "dns",
                    "network",
                ],
                external_service_indicators=["api", "external", "third-party"],
            ),
            "resource_exhaustion": PatternMatcherConfig(
                min_confidence=0.3,
                keywords=[
                    "memory",
                    "cpu",
                    "disk",
                    "space",
                    "limit",
                    "quota",
                    "throttle",
                ],
                gradual_onset_indicators=["slow", "degraded", "performance"],
            ),
            "sporadic_errors": PatternMatcherConfig(
                min_confidence=0.2,
            ),
        }


class EnsembleStrategy(Protocol):
    """Protocol for ensemble voting strategies."""

    def combine_patterns(
        self, patterns: List[PatternMatch], config: EnsembleConfig
    ) -> List[PatternMatch]:
        """Combine patterns using the ensemble strategy."""
        ...


class MajorityVotingStrategy:
    """Majority voting ensemble strategy."""

    def combine_patterns(
        self, patterns: List[PatternMatch], config: EnsembleConfig
    ) -> List[PatternMatch]:
        """Combine patterns using majority voting."""
        if not patterns:
            return []

        # Group patterns by type
        pattern_groups = {}
        for pattern in patterns:
            pattern_type = pattern.pattern_type
            if pattern_type not in pattern_groups:
                pattern_groups[pattern_type] = []
            pattern_groups[pattern_type].append(pattern)

        # Select patterns with majority support
        ensemble_patterns = []
        for group_patterns in pattern_groups.values():
            if len(group_patterns) >= 2:  # Majority threshold
                # Select the pattern with highest confidence
                best_pattern = max(group_patterns, key=lambda p: p.confidence_score)
                ensemble_patterns.append(best_pattern)

        return ensemble_patterns


class WeightedVotingStrategy:
    """Weighted voting ensemble strategy."""

    def combine_patterns(
        self, patterns: List[PatternMatch], config: EnsembleConfig
    ) -> List[PatternMatch]:
        """Combine patterns using weighted voting."""
        if not patterns:
            return []

        # Group patterns by type
        pattern_groups = {}
        for pattern in patterns:
            pattern_type = pattern.pattern_type
            if pattern_type not in pattern_groups:
                pattern_groups[pattern_type] = []
            pattern_groups[pattern_type].append(pattern)

        ensemble_patterns = []
        for group_patterns in pattern_groups.values():
            if len(group_patterns) == 1:
                # Single pattern, use as-is if confidence is sufficient
                pattern = group_patterns[0]
                if pattern.confidence_score >= config.min_individual_confidence:
                    ensemble_patterns.append(pattern)
            else:
                # Multiple patterns, combine using weighted average
                combined_pattern = self._combine_group_patterns(group_patterns, config)
                if (
                    combined_pattern
                    and combined_pattern.confidence_score
                    >= config.min_ensemble_confidence
                ):
                    ensemble_patterns.append(combined_pattern)

        return ensemble_patterns

    def _combine_group_patterns(
        self, patterns: List[PatternMatch], config: EnsembleConfig
    ) -> Optional[PatternMatch]:
        """Combine multiple patterns of the same type."""
        if not patterns:
            return None

        # Calculate weighted confidence
        total_weight = 0.0
        weighted_confidence = 0.0

        for pattern in patterns:
            weight = self._calculate_pattern_weight(pattern, config)
            weighted_confidence += pattern.confidence_score * weight
            total_weight += weight

        if total_weight == 0:
            return None

        combined_confidence = weighted_confidence / total_weight

        # Combine affected services
        all_affected_services = set()
        for pattern in patterns:
            all_affected_services.update(pattern.affected_services)

        # Select primary service from highest confidence pattern
        primary_pattern = max(patterns, key=lambda p: p.confidence_score)

        # Combine evidence
        combined_evidence = self._combine_evidence(patterns)

        # Combine suggested actions
        combined_actions = self._combine_suggested_actions(patterns)

        # Determine severity level
        severity_levels = [p.severity_level for p in patterns]
        combined_severity = self._determine_combined_severity(severity_levels)

        # Determine remediation priority
        priorities = [p.remediation_priority for p in patterns]
        combined_priority = self._determine_combined_priority(priorities)

        return PatternMatch(
            pattern_type=patterns[0].pattern_type,
            confidence_score=combined_confidence,
            primary_service=primary_pattern.primary_service,
            affected_services=list(all_affected_services),
            severity_level=combined_severity,
            evidence=combined_evidence,
            remediation_priority=combined_priority,
            suggested_actions=combined_actions,
        )

    def _calculate_pattern_weight(
        self, pattern: PatternMatch, config: EnsembleConfig
    ) -> float:
        """Calculate weight for a pattern in ensemble voting."""
        # Base weight from confidence
        confidence_weight = pattern.confidence_score * config.confidence_weight

        # Frequency weight (number of affected services)
        frequency_weight = (
            min(1.0, len(pattern.affected_services) / 5.0) * config.frequency_weight
        )

        # Recency weight (assume all patterns are recent for now)
        recency_weight = config.recency_weight

        return confidence_weight + frequency_weight + recency_weight

    def _combine_evidence(self, patterns: List[PatternMatch]) -> Dict[str, Any]:
        """Combine evidence from multiple patterns."""
        combined_evidence = {}

        # Collect all evidence keys
        all_keys = set()
        for pattern in patterns:
            all_keys.update(pattern.evidence.keys())

        # Combine evidence values
        for key in all_keys:
            values = [p.evidence.get(key) for p in patterns if key in p.evidence]
            if values:
                # Filter out None values for numeric operations
                numeric_values = [v for v in values if isinstance(v, (int, float))]
                if numeric_values:
                    # Numeric values - use average
                    combined_evidence[key] = sum(numeric_values) / len(numeric_values)
                elif isinstance(values[0], list):
                    # List values - combine and deduplicate
                    combined_list = []
                    for value in values:
                        if isinstance(value, list):
                            combined_list.extend(value)
                    combined_evidence[key] = list(set(combined_list))
                else:
                    # Other values - use most common
                    from collections import Counter

                    counter = Counter(values)
                    combined_evidence[key] = counter.most_common(1)[0][0]

        return combined_evidence

    def _combine_suggested_actions(self, patterns: List[PatternMatch]) -> List[str]:
        """Combine suggested actions from multiple patterns."""
        all_actions = []
        for pattern in patterns:
            all_actions.extend(pattern.suggested_actions)

        # Remove duplicates while preserving order
        seen = set()
        unique_actions = []
        for action in all_actions:
            if action not in seen:
                seen.add(action)
                unique_actions.append(action)

        return unique_actions

    def _determine_combined_severity(self, severity_levels: List[str]) -> str:
        """Determine combined severity level from multiple patterns."""
        severity_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        max_severity = "LOW"

        for severity in severity_levels:
            if severity in severity_order:
                current_index = severity_order.index(severity)
                max_index = severity_order.index(max_severity)
                if current_index > max_index:
                    max_severity = severity

        return max_severity

    def _determine_combined_priority(self, priorities: List[str]) -> str:
        """Determine combined remediation priority from multiple patterns."""
        priority_order = ["LOW", "MEDIUM", "HIGH", "IMMEDIATE"]
        max_priority = "LOW"

        for priority in priorities:
            if priority in priority_order:
                current_index = priority_order.index(priority)
                max_index = priority_order.index(max_priority)
                if current_index > max_index:
                    max_priority = priority

        return max_priority


class ConsensusVotingStrategy:
    """Consensus voting ensemble strategy."""

    def combine_patterns(
        self, patterns: List[PatternMatch], config: EnsembleConfig
    ) -> List[PatternMatch]:
        """Combine patterns using consensus voting."""
        if not patterns:
            return []

        # Group patterns by type
        pattern_groups = {}
        for pattern in patterns:
            pattern_type = pattern.pattern_type
            if pattern_type not in pattern_groups:
                pattern_groups[pattern_type] = []
            pattern_groups[pattern_type].append(pattern)

        ensemble_patterns = []
        for group_patterns in pattern_groups.values():
            if len(group_patterns) >= 2:
                # Check for consensus
                consensus_pattern = self._find_consensus_pattern(group_patterns, config)
                if consensus_pattern:
                    ensemble_patterns.append(consensus_pattern)
            else:
                # Single pattern, use if confidence is sufficient
                pattern = group_patterns[0]
                if pattern.confidence_score >= config.min_individual_confidence:
                    ensemble_patterns.append(pattern)

        return ensemble_patterns

    def _find_consensus_pattern(
        self, patterns: List[PatternMatch], config: EnsembleConfig
    ) -> Optional[PatternMatch]:
        """Find consensus pattern from multiple patterns."""
        if len(patterns) < 2:
            return patterns[0] if patterns else None

        # Calculate agreement scores
        agreement_scores = []
        for i, pattern_a in enumerate(patterns):
            for j, pattern_b in enumerate(patterns[i + 1 :], i + 1):
                agreement = self._calculate_agreement(pattern_a, pattern_b)
                agreement_scores.append((i, j, agreement))

        # Find patterns with high agreement
        high_agreement_pairs = [
            (i, j, score)
            for i, j, score in agreement_scores
            if score >= config.min_agreement_threshold
        ]

        if not high_agreement_pairs:
            return None

        # Select the pattern with highest average agreement
        pattern_agreement_scores = {}
        for i, j, score in high_agreement_pairs:
            pattern_agreement_scores[i] = pattern_agreement_scores.get(i, 0) + score
            pattern_agreement_scores[j] = pattern_agreement_scores.get(j, 0) + score

        best_pattern_index = max(
            pattern_agreement_scores.keys(), key=lambda k: pattern_agreement_scores[k]
        )

        return patterns[best_pattern_index]

    def _calculate_agreement(
        self, pattern_a: PatternMatch, pattern_b: PatternMatch
    ) -> float:
        """Calculate agreement score between two patterns."""
        # Service overlap
        services_a = set(pattern_a.affected_services)
        services_b = set(pattern_b.affected_services)
        service_overlap = len(services_a & services_b) / max(
            len(services_a | services_b), 1
        )

        # Confidence similarity
        confidence_diff = abs(pattern_a.confidence_score - pattern_b.confidence_score)
        confidence_similarity = 1.0 - confidence_diff

        # Severity similarity
        severity_similarity = (
            1.0 if pattern_a.severity_level == pattern_b.severity_level else 0.5
        )

        # Weighted average
        return (
            service_overlap * 0.5
            + confidence_similarity * 0.3
            + severity_similarity * 0.2
        )


class PatternEnsemble:
    """Ensemble pattern classifier that combines multiple pattern matchers."""

    def __init__(self, config: Optional[EnsembleConfig] = None, confidence_scorer: Optional[str] = None) -> None:
        self.config = config or EnsembleConfig()
        self.confidence_scorer = confidence_scorer
        self.logger = setup_logging()

        # Initialize pattern matchers
        self.pattern_matchers = PatternMatcherFactory.create_all_matchers(
            self.config.pattern_configs or {}, confidence_scorer
        )

        # Initialize ensemble strategy
        self.ensemble_strategy = self._create_ensemble_strategy()

        # Initialize confidence processor
        self.confidence_processor = ConfidenceScoreProcessor()
        self.confidence_rules = ConfidenceRuleFactory.get_default_confidence_rules()

        self.logger.info("[PATTERN_ENSEMBLE] PatternEnsemble initialized")

    def classify_patterns(
        self, window: TimeWindow, threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Classify patterns using ensemble methods."""
        self.logger.info(
            f"[PATTERN_ENSEMBLE] Starting ensemble classification: "
            f"window={window.start_time}, threshold_results={len(threshold_results)}"
        )

        # Get patterns from all matchers
        all_patterns = []
        for matcher_name, matcher in self.pattern_matchers.items():
            try:
                patterns = matcher.match_patterns(window, threshold_results)
                all_patterns.extend(patterns)
                self.logger.debug(
                    f"[PATTERN_ENSEMBLE] {matcher_name} found {len(patterns)} patterns"
                )
            except Exception as e:
                self.logger.error(f"[PATTERN_ENSEMBLE] Error in {matcher_name}: {e}")

        if not all_patterns:
            self.logger.info("[PATTERN_ENSEMBLE] No patterns found by any matcher")
            return []

        # Apply ensemble strategy
        ensemble_patterns = self.ensemble_strategy.combine_patterns(
            all_patterns, self.config
        )

        # Sort by confidence score
        ensemble_patterns.sort(key=lambda p: p.confidence_score, reverse=True)

        # Limit to max patterns per ensemble
        if len(ensemble_patterns) > self.config.max_patterns_per_ensemble:
            ensemble_patterns = ensemble_patterns[
                : self.config.max_patterns_per_ensemble
            ]

        self.logger.info(
            f"[PATTERN_ENSEMBLE] Ensemble classification complete: "
            f"total_patterns={len(all_patterns)}, ensemble_patterns={len(ensemble_patterns)}"
        )

        return ensemble_patterns

    def _create_ensemble_strategy(self) -> EnsembleStrategy:
        """Create ensemble strategy based on configuration."""
        strategy_name = self.config.voting_strategy.lower()

        if strategy_name == "majority":
            return MajorityVotingStrategy()
        elif strategy_name == "weighted":
            return WeightedVotingStrategy()
        elif strategy_name == "consensus":
            return ConsensusVotingStrategy()
        else:
            self.logger.warning(
                f"[PATTERN_ENSEMBLE] Unknown voting strategy: {strategy_name}, "
                "defaulting to weighted"
            )
            return WeightedVotingStrategy()

    def get_ensemble_metrics(self) -> Dict[str, Any]:
        """Get metrics about the ensemble performance."""
        return {
            "voting_strategy": self.config.voting_strategy,
            "num_matchers": len(self.pattern_matchers),
            "matcher_names": list(self.pattern_matchers.keys()),
            "min_ensemble_confidence": self.config.min_ensemble_confidence,
            "min_individual_confidence": self.config.min_individual_confidence,
        }
