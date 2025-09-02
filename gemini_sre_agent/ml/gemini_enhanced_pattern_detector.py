"""
Gemini-enhanced pattern detection system with ensemble capabilities.

Combines Gemini AI pattern classification with traditional rule-based methods
for comprehensive incident pattern analysis with fallback protection.
"""

import logging
from typing import Any, Dict, List, Optional

from ..pattern_detector.models import PatternMatch, ThresholdResult, TimeWindow
from ..pattern_detector.pattern_classifier import PatternClassifier
from .gemini_pattern_classifier import GeminiPatternClassifier


class GeminiEnhancedPatternDetector:
    """Pattern detector enhanced with Gemini AI capabilities."""

    def __init__(
        self,
        gemini_api_key: str,
        config: Optional[Dict[str, Any]] = None,
        cost_tracker: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
    ):
        """Initialize the enhanced pattern detector.

        Args:
            gemini_api_key: Gemini API key for AI classification
            config: Optional configuration parameters
            cost_tracker: Optional cost tracking component
            rate_limiter: Optional rate limiting component
        """
        self.config = config or self._get_default_config()
        self.gemini_classifier = GeminiPatternClassifier(
            api_key=gemini_api_key,
            config=self.config.get("gemini", {}),
            cost_tracker=cost_tracker,
            rate_limiter=rate_limiter,
        )
        self.rule_based_classifier = PatternClassifier()  # Fallback

        # Optional source code analysis
        self.code_context_extractor = None
        if config and config.get("code_analysis", {}).get("enabled", False):
            try:
                # Note: Code analysis integration is optional
                # from ..code_analysis.code_context_extractor import (
                #     CodeAnalysisConfig,
                #     CodeContextExtractor,
                # )

                # Code analysis integration disabled for now
                self.code_context_extractor = None
            except ImportError:
                logging.getLogger(__name__).warning(
                    "Code analysis disabled - CodeContextExtractor not available"
                )

        self.ensemble_mode = self.config.get("ensemble_mode", "gemini_primary")
        self.confidence_threshold = self.config.get("gemini_confidence_threshold", 0.6)
        self.fallback_enabled = self.config.get("fallback_enabled", True)

        self.logger = logging.getLogger(__name__)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "ensemble_mode": "gemini_primary",  # "gemini_primary", "ensemble", "rules_only"
            "gemini_confidence_threshold": 0.6,
            "fallback_enabled": True,
            "gemini": {
                "classification_model": "gemini-1.5-pro",
                "fast_classification_model": "gemini-1.5-flash",
                "confidence_model": "gemini-1.5-pro",
            },
        }

    async def classify_patterns(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
        historical_context: Optional[Dict] = None,
    ) -> List[PatternMatch]:
        """Enhanced pattern classification using Gemini AI.

        Args:
            window: Time window with log data to analyze
            threshold_results: Results from threshold-based detection
            historical_context: Optional historical analysis data

        Returns:
            List of pattern matches with confidence scores
        """
        if self.ensemble_mode == "rules_only":
            return self.rule_based_classifier.classify_patterns(
                window, threshold_results
            )

        try:
            # Get Gemini classification
            gemini_patterns = []
            if self.ensemble_mode in ["gemini_primary", "ensemble"]:
                # Convert ThresholdResult objects to dictionaries
                threshold_dicts = [
                    {
                        "type": result.threshold_type,
                        "triggered": result.triggered,
                        "score": result.score,
                        "details": result.details,
                    }
                    for result in threshold_results
                ]

                gemini_patterns = await self.gemini_classifier.classify_patterns(
                    window, threshold_dicts, historical_context
                )

            # Get rule-based classification if needed
            rule_patterns = []
            if (
                self.ensemble_mode == "ensemble"
                or (self.fallback_enabled and not gemini_patterns)
                or (self.ensemble_mode == "gemini_primary" and self.fallback_enabled)
            ):
                rule_patterns = self.rule_based_classifier.classify_patterns(
                    window, threshold_results
                )

            # Combine results based on mode
            if self.ensemble_mode == "gemini_primary":
                return self._handle_gemini_primary(
                    gemini_patterns, rule_patterns, window
                )

            elif self.ensemble_mode == "ensemble":
                return self._handle_ensemble(gemini_patterns, rule_patterns, window)

            else:
                return rule_patterns

        except Exception as e:
            self.logger.error(f"Error in classification: {e}")

            # Fallback to rules if enabled
            if self.fallback_enabled:
                self.logger.info("Falling back to rule-based classification")
                return self.rule_based_classifier.classify_patterns(
                    window, threshold_results
                )
            else:
                return []

    def _handle_gemini_primary(
        self,
        gemini_patterns: List[PatternMatch],
        rule_patterns: List[PatternMatch],
        window: TimeWindow,
    ) -> List[PatternMatch]:
        """Handle Gemini-primary mode with rule-based fallback."""
        if not gemini_patterns and self.fallback_enabled:
            self.logger.info("No Gemini patterns, using rule-based fallback")
            return rule_patterns

        # Filter Gemini patterns by confidence
        high_confidence_patterns = [
            p
            for p in gemini_patterns
            if p.confidence_score >= self.confidence_threshold
        ]

        if high_confidence_patterns:
            # Enhance with rule-based insights
            enhanced_patterns = self._enhance_gemini_patterns(
                high_confidence_patterns, rule_patterns
            )
            return enhanced_patterns

        elif self.fallback_enabled and rule_patterns:
            self.logger.info(
                "Low confidence Gemini patterns, using rule-based fallback"
            )
            return rule_patterns

        else:
            # Return low confidence Gemini patterns with warning
            for pattern in gemini_patterns:
                pattern.evidence["low_confidence_warning"] = True
            return gemini_patterns

    def _handle_ensemble(
        self,
        gemini_patterns: List[PatternMatch],
        rule_patterns: List[PatternMatch],
        window: TimeWindow,
    ) -> List[PatternMatch]:
        """Handle ensemble mode combining both approaches."""
        if not gemini_patterns and not rule_patterns:
            return []

        if not gemini_patterns:
            return rule_patterns

        if not rule_patterns:
            return gemini_patterns

        # Combine patterns using weighted approach
        combined_patterns = []

        # Match patterns by type
        gemini_by_type = {p.pattern_type: p for p in gemini_patterns}
        rule_by_type = {p.pattern_type: p for p in rule_patterns}

        all_types = set(gemini_by_type.keys()) | set(rule_by_type.keys())

        for pattern_type in all_types:
            gemini_pattern = gemini_by_type.get(pattern_type)
            rule_pattern = rule_by_type.get(pattern_type)

            if gemini_pattern and rule_pattern:
                # Combine both patterns
                combined_pattern = self._merge_patterns(gemini_pattern, rule_pattern)
                combined_patterns.append(combined_pattern)

            elif (
                gemini_pattern
                and gemini_pattern.confidence_score >= self.confidence_threshold
            ):
                # Use high-confidence Gemini pattern
                combined_patterns.append(gemini_pattern)

            elif rule_pattern:
                # Use rule-based pattern
                combined_patterns.append(rule_pattern)

        # Sort by confidence
        combined_patterns.sort(key=lambda x: x.confidence_score, reverse=True)

        return combined_patterns

    def _enhance_gemini_patterns(
        self,
        gemini_patterns: List[PatternMatch],
        rule_patterns: List[PatternMatch],
    ) -> List[PatternMatch]:
        """Enhance Gemini patterns with rule-based insights."""
        enhanced_patterns = []

        for gemini_pattern in gemini_patterns:
            # Find matching rule pattern
            matching_rule = None
            for rule_pattern in rule_patterns:
                if rule_pattern.pattern_type == gemini_pattern.pattern_type:
                    matching_rule = rule_pattern
                    break

            if matching_rule:
                # Merge evidence from both approaches
                enhanced_evidence = {
                    **gemini_pattern.evidence,
                    "rule_based_confidence": matching_rule.confidence_score,
                    "rule_based_evidence": matching_rule.evidence,
                    "approaches_agree": True,
                }

                # Boost confidence when both approaches agree
                boosted_confidence = min(1.0, gemini_pattern.confidence_score * 1.1)

                enhanced_pattern = PatternMatch(
                    pattern_type=gemini_pattern.pattern_type,
                    confidence_score=boosted_confidence,
                    primary_service=gemini_pattern.primary_service,
                    affected_services=gemini_pattern.affected_services,
                    severity_level=gemini_pattern.severity_level,
                    evidence=enhanced_evidence,
                    remediation_priority=gemini_pattern.remediation_priority,
                    suggested_actions=list(
                        set(
                            gemini_pattern.suggested_actions
                            + matching_rule.suggested_actions
                        )
                    ),
                )

                enhanced_patterns.append(enhanced_pattern)

            else:
                # No rule-based match, keep Gemini pattern as-is
                enhanced_patterns.append(gemini_pattern)

        return enhanced_patterns

    def _merge_patterns(
        self, gemini_pattern: PatternMatch, rule_pattern: PatternMatch
    ) -> PatternMatch:
        """Merge Gemini and rule-based patterns of the same type."""
        # Weighted confidence combination
        gemini_weight = (
            0.7 if gemini_pattern.confidence_score >= self.confidence_threshold else 0.4
        )
        rule_weight = 1.0 - gemini_weight

        combined_confidence = (
            gemini_pattern.confidence_score * gemini_weight
            + rule_pattern.confidence_score * rule_weight
        )

        # Take highest severity
        severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        severity_levels = [gemini_pattern.severity_level, rule_pattern.severity_level]
        combined_severity = min(
            severity_levels,
            key=lambda x: severity_order.index(x) if x in severity_order else 999,
        )

        # Merge evidence
        combined_evidence = {
            **gemini_pattern.evidence,
            "rule_based_confidence": rule_pattern.confidence_score,
            "rule_based_evidence": rule_pattern.evidence,
            "ensemble_method": "weighted_combination",
            "gemini_weight": gemini_weight,
            "rule_weight": rule_weight,
        }

        # Combine suggested actions
        combined_actions = list(
            set(gemini_pattern.suggested_actions + rule_pattern.suggested_actions)
        )

        return PatternMatch(
            pattern_type=gemini_pattern.pattern_type,
            confidence_score=combined_confidence,
            primary_service=gemini_pattern.primary_service
            or rule_pattern.primary_service,
            affected_services=list(
                set(gemini_pattern.affected_services + rule_pattern.affected_services)
            ),
            severity_level=combined_severity,
            evidence=combined_evidence,
            remediation_priority=gemini_pattern.remediation_priority,
            suggested_actions=combined_actions,
        )

    async def process_feedback(
        self,
        window_id: str,
        predicted_pattern: str,
        actual_pattern: str,
        user_id: str,
        notes: Optional[str] = None,
    ) -> None:
        """Process human feedback for continuous learning.

        Args:
            window_id: Unique identifier for the time window
            predicted_pattern: Pattern that was predicted
            actual_pattern: Actual pattern that occurred
            user_id: ID of the user providing feedback
            notes: Optional additional notes
        """
        try:
            # TODO: Implement feedback processing when available in GeminiPatternClassifier
            self.logger.info(
                f"Feedback received for {window_id}: {predicted_pattern} -> {actual_pattern}"
            )

            # For now, just log the feedback for future implementation
            feedback_data = {
                "window_id": window_id,
                "predicted_pattern": predicted_pattern,
                "actual_pattern": actual_pattern,
                "user_id": user_id,
                "notes": notes,
            }
            self.logger.debug(f"Feedback data: {feedback_data}")

        except Exception as e:
            self.logger.error(f"Error processing feedback: {e}")

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics from the detector.

        Returns:
            Dictionary containing performance metrics
        """
        gemini_stats = self.gemini_classifier.get_performance_stats()

        return {
            "ensemble_mode": self.ensemble_mode,
            "confidence_threshold": self.confidence_threshold,
            "fallback_enabled": self.fallback_enabled,
            "gemini_stats": gemini_stats,
        }
