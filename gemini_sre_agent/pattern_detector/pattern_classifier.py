# gemini_sre_agent/pattern_detector/pattern_classifier.py

"""
Lightweight pattern classification orchestrator.

This module provides a lightweight orchestrator that coordinates the modular
pattern detection components including pattern matchers, confidence calculators,
and ensemble methods for comprehensive pattern classification.
"""


from ..logger import setup_logging
from .classifier_ensemble import EnsembleConfig, PatternEnsemble
from .confidence_scorer import ConfidenceScorer
from .models import (
    PatternMatch,
    ThresholdResult,
    TimeWindow,
)


class PatternClassifier:
    """Lightweight orchestrator for pattern classification using modular components."""

    def __init__(
        self,
        confidence_scorer: ConfidenceScorer | None = None,
        ensemble_config: EnsembleConfig | None = None,
    ):
        self.logger = setup_logging()
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()
        self.ensemble_config = ensemble_config or EnsembleConfig()

        # Initialize the pattern ensemble
        self.pattern_ensemble = PatternEnsemble(
            config=self.ensemble_config, confidence_scorer=self.confidence_scorer
        )

        self.logger.info(
            "[PATTERN_DETECTION] PatternClassifier initialized with ensemble"
        )

    def classify_patterns(
        self, window: TimeWindow, threshold_results: list[ThresholdResult]
    ) -> list[PatternMatch]:
        """Classify patterns using the ensemble approach."""
        triggered_results = [r for r in threshold_results if r.triggered]
        if not triggered_results:
            self.logger.debug(
                f"[PATTERN_DETECTION] No triggered thresholds to classify: window={window.start_time}"
            )
            return []

        self.logger.info(
            f"[PATTERN_DETECTION] Classifying patterns: window={window.start_time}, "
            f"triggered_thresholds={len(triggered_results)}"
        )

        # Use the pattern ensemble for classification
        patterns = self.pattern_ensemble.classify_patterns(window, threshold_results)

        self.logger.info(
            f"[PATTERN_DETECTION] Pattern classification complete: "
            f"patterns_detected={len(patterns)}, window={window.start_time}"
        )
        return patterns

    def get_ensemble_metrics(self) -> dict:
        """Get metrics about the ensemble performance."""
        return self.pattern_ensemble.get_ensemble_metrics()

    def update_ensemble_config(self, config: EnsembleConfig) -> None:
        """Update the ensemble configuration."""
        self.ensemble_config = config
        self.pattern_ensemble = PatternEnsemble(
            config=config, confidence_scorer=self.confidence_scorer
        )
        self.logger.info("[PATTERN_DETECTION] Ensemble configuration updated")
