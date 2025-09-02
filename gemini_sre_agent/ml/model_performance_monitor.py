"""
Model performance monitoring and drift detection for Gemini AI classification.

This module provides comprehensive monitoring of classification accuracy,
confidence calibration, and latency metrics with automated drift detection.
"""

import logging
from collections import defaultdict, deque
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Optional

from .drift_detector import DriftDetector, MetricsCalculator
from .performance_config import DriftAlert, PerformanceConfig, PerformanceMetrics


class ModelPerformanceMonitor:
    """
    Monitor classification accuracy and detect model drift over time.

    Tracks prediction accuracy, confidence calibration, and latency metrics
    with automated drift detection and baseline establishment.
    """

    def __init__(self, config: Optional[PerformanceConfig] = None):
        self.config = config or PerformanceConfig()

        # Performance tracking with sliding windows
        self.accuracy_history: deque = deque(maxlen=self.config.window_size)
        self.confidence_history: deque = deque(maxlen=self.config.window_size)
        self.latency_history: deque = deque(maxlen=self.config.window_size)
        self.pattern_type_accuracy: Dict[str, List[float]] = defaultdict(list)

        # Baseline metrics for drift detection
        self.baseline_accuracy: Optional[float] = None
        self.baseline_confidence: Optional[float] = None
        self.baseline_latency: Optional[float] = None

        # Drift detection components
        self.drift_detector = DriftDetector(self.config)
        self.last_drift_check = datetime.now()
        self.drift_alerts: List[DriftAlert] = []

        self.logger = logging.getLogger(__name__)
        self.logger.info(
            "[PERFORMANCE_MONITOR] Initialized with window_size=%d, drift_threshold=%.3f",
            self.config.window_size,
            self.config.accuracy_drift_threshold,
        )

    async def track_prediction_accuracy(
        self,
        prediction: str,
        actual_outcome: str,
        confidence_score: float,
        latency_ms: float,
    ) -> None:
        """
        Track prediction accuracy against actual incident outcomes.

        Args:
            prediction: The model's predicted pattern type
            actual_outcome: The confirmed actual pattern type
            confidence_score: Model confidence (0.0-1.0)
            latency_ms: Prediction latency in milliseconds
        """
        # Calculate accuracy (1.0 for correct, 0.0 for incorrect)
        is_correct = 1.0 if prediction == actual_outcome else 0.0

        # Update tracking histories
        self.accuracy_history.append(is_correct)
        self.confidence_history.append(confidence_score)
        self.latency_history.append(latency_ms)

        # Track pattern-specific accuracy
        self.pattern_type_accuracy[prediction].append(is_correct)
        self._trim_pattern_history(prediction)

        # Set baseline metrics if we have enough data
        if (
            self.baseline_accuracy is None
            and len(self.accuracy_history) >= self.config.baseline_establishment_size
        ):
            self._set_baseline_metrics()

        # Check for drift periodically
        if self._should_check_drift():
            await self._check_for_drift()

        self.logger.debug(
            "[PERFORMANCE_MONITOR] Tracked prediction: %s -> %s, "
            "Correct: %s, Confidence: %.3f, Latency: %.1fms",
            prediction,
            actual_outcome,
            bool(is_correct),
            confidence_score,
            latency_ms,
        )

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics and drift status.

        Returns:
            Dictionary containing accuracy, confidence, latency metrics
        """
        if not self.accuracy_history:
            return PerformanceMetrics.empty_metrics()

        # Calculate recent metrics using MetricsCalculator
        recent_accuracy = MetricsCalculator.calculate_recent_metrics(
            list(self.accuracy_history), self.config.recent_window_size
        )
        recent_confidence = MetricsCalculator.calculate_recent_metrics(
            list(self.confidence_history), self.config.recent_window_size
        )
        recent_latency = MetricsCalculator.calculate_recent_metrics(
            list(self.latency_history), self.config.recent_window_size
        )

        # Pattern-specific accuracy analysis
        pattern_accuracy = self._calculate_pattern_accuracy()

        return {
            "overall_accuracy": mean(self.accuracy_history),
            "recent_accuracy": recent_accuracy,
            "baseline_accuracy": self.baseline_accuracy,
            "overall_confidence": mean(self.confidence_history),
            "recent_confidence": recent_confidence,
            "baseline_confidence": self.baseline_confidence,
            "overall_latency_ms": mean(self.latency_history),
            "recent_latency_ms": recent_latency,
            "baseline_latency_ms": self.baseline_latency,
            "pattern_accuracy": pattern_accuracy,
            "total_predictions": len(self.accuracy_history),
            "drift_alerts_count": len(self.drift_alerts),
            "recent_drift_alerts": self.drift_alerts[-5:] if self.drift_alerts else [],
            "baseline_established": self.baseline_accuracy is not None,
            "drift_check_enabled": self._can_check_drift(),
        }

    def get_drift_summary(self) -> Dict[str, Any]:
        """Get summary of drift alerts and current status."""
        summary = MetricsCalculator.analyze_drift_alerts(self.drift_alerts)
        summary["last_check"] = self.last_drift_check.isoformat()
        return summary

    def reset_drift_alerts(self) -> int:
        """Reset drift alerts and return count of cleared alerts."""
        alert_count = len(self.drift_alerts)
        self.drift_alerts.clear()

        self.logger.info("[PERFORMANCE_MONITOR] Cleared %d drift alerts", alert_count)
        return alert_count

    def _set_baseline_metrics(self) -> None:
        """Establish baseline performance metrics from current history."""
        self.baseline_accuracy = mean(self.accuracy_history)
        self.baseline_confidence = mean(self.confidence_history)
        self.baseline_latency = mean(self.latency_history)

        self.logger.info(
            "[PERFORMANCE_MONITOR] Baseline established - "
            "Accuracy: %.3f, Confidence: %.3f, Latency: %.1fms",
            self.baseline_accuracy,
            self.baseline_confidence,
            self.baseline_latency,
        )

    def _should_check_drift(self) -> bool:
        """Determine if drift check should be performed."""
        return (
            len(self.accuracy_history) >= self.config.min_samples_for_drift_check
            and (datetime.now() - self.last_drift_check).total_seconds()
            >= self.config.drift_check_interval_seconds
        )

    def _can_check_drift(self) -> bool:
        """Check if drift detection is possible with current data."""
        return (
            len(self.accuracy_history) >= self.config.min_samples_for_drift_check
            and self.baseline_accuracy is not None
        )

    async def _check_for_drift(self) -> None:
        """Check for significant performance drift in all metrics."""
        if not self._can_check_drift():
            return

        # Calculate current metrics using MetricsCalculator
        current_accuracy = MetricsCalculator.calculate_recent_metrics(
            list(self.accuracy_history), self.config.recent_window_size
        )
        current_confidence = MetricsCalculator.calculate_recent_metrics(
            list(self.confidence_history), self.config.recent_window_size
        )
        current_latency = MetricsCalculator.calculate_recent_metrics(
            list(self.latency_history), self.config.recent_window_size
        )

        # Delegate drift checking to DriftDetector
        await self.drift_detector.check_accuracy_drift(
            current_accuracy, self.baseline_accuracy, self.drift_alerts
        )
        await self.drift_detector.check_confidence_drift(
            current_confidence, self.baseline_confidence, self.drift_alerts
        )
        await self.drift_detector.check_latency_drift(
            current_latency, self.baseline_latency, self.drift_alerts
        )

        self.last_drift_check = datetime.now()

    def _calculate_pattern_accuracy(self) -> Dict[str, Dict[str, Any]]:
        """Calculate accuracy metrics for each pattern type."""
        pattern_accuracy = {}

        for pattern, accuracies in self.pattern_type_accuracy.items():
            if accuracies:
                pattern_accuracy[pattern] = (
                    MetricsCalculator.calculate_pattern_accuracy(
                        accuracies, self.config.pattern_accuracy_window
                    )
                )

        return pattern_accuracy

    def _trim_pattern_history(self, pattern: str) -> None:
        """Trim pattern history to prevent unlimited growth."""
        self.pattern_type_accuracy[pattern] = MetricsCalculator.trim_history(
            self.pattern_type_accuracy[pattern], self.config.max_pattern_history
        )
