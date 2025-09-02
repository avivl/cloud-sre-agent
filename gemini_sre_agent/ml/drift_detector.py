"""
Drift detection logic for model performance monitoring.

This module provides specialized drift detection algorithms and alerting
for accuracy, confidence, and latency metrics.
"""

import logging
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Optional

from .performance_config import DriftAlert, PerformanceConfig


class DriftDetector:
    """Specialized drift detection for model performance metrics."""

    def __init__(self, config: PerformanceConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

    async def check_accuracy_drift(
        self,
        current_accuracy: float,
        baseline_accuracy: Optional[float],
        drift_alerts: List[DriftAlert],
    ) -> None:
        """Check for accuracy drift and create alert if needed."""
        if baseline_accuracy is None:
            return

        accuracy_drift = abs(current_accuracy - baseline_accuracy)

        if accuracy_drift > self.config.accuracy_drift_threshold:
            severity = self._determine_drift_severity(
                accuracy_drift, self.config.high_drift_threshold
            )

            alert = DriftAlert(
                drift_type="accuracy_drift",
                severity=severity,
                baseline_value=baseline_accuracy,
                current_value=current_accuracy,
                drift_amount=accuracy_drift,
                timestamp=datetime.now(),
            )

            drift_alerts.append(alert)
            self.logger.warning("[DRIFT_DETECTOR] Accuracy drift detected: %s", alert)

    async def check_confidence_drift(
        self,
        current_confidence: float,
        baseline_confidence: Optional[float],
        drift_alerts: List[DriftAlert],
    ) -> None:
        """Check for confidence calibration drift."""
        if baseline_confidence is None:
            return

        confidence_drift = abs(current_confidence - baseline_confidence)

        if confidence_drift > self.config.confidence_drift_threshold:
            alert = DriftAlert(
                drift_type="confidence_drift",
                severity="MEDIUM",
                baseline_value=baseline_confidence,
                current_value=current_confidence,
                drift_amount=confidence_drift,
                timestamp=datetime.now(),
            )

            drift_alerts.append(alert)
            self.logger.warning("[DRIFT_DETECTOR] Confidence drift detected: %s", alert)

    async def check_latency_drift(
        self,
        current_latency: float,
        baseline_latency: Optional[float],
        drift_alerts: List[DriftAlert],
    ) -> None:
        """Check for latency performance degradation."""
        if baseline_latency is None:
            return

        # Check for significant latency increase (performance degradation)
        latency_multiplier = current_latency / baseline_latency

        if latency_multiplier > self.config.latency_drift_multiplier:
            drift_pct = (latency_multiplier - 1.0) * 100

            alert = DriftAlert(
                drift_type="latency_drift",
                severity="MEDIUM",
                baseline_value=baseline_latency,
                current_value=current_latency,
                drift_amount=drift_pct,
                timestamp=datetime.now(),
            )

            drift_alerts.append(alert)
            self.logger.warning("[DRIFT_DETECTOR] Latency drift detected: %s", alert)

    def _determine_drift_severity(
        self, drift_amount: float, high_threshold: float
    ) -> str:
        """Determine drift severity based on amount and thresholds."""
        if drift_amount > high_threshold:
            return "HIGH"
        elif drift_amount > high_threshold * 0.5:
            return "MEDIUM"
        else:
            return "LOW"


class MetricsCalculator:
    """Helper class for performance metrics calculations."""

    @staticmethod
    def calculate_recent_metrics(history: List[float], recent_size: int) -> float:
        """Calculate recent metrics from history with window size."""
        if not history:
            return 0.0

        actual_size = min(recent_size, len(history))
        return mean(list(history)[-actual_size:])

    @staticmethod
    def calculate_pattern_accuracy(accuracies: List[float], window_size: int) -> dict:
        """Calculate pattern-specific accuracy metrics."""
        if not accuracies:
            return {"accuracy": 0.0, "sample_count": 0, "recent_samples": 0}

        recent_samples = min(window_size, len(accuracies))
        recent_accuracy = mean(accuracies[-recent_samples:])

        return {
            "accuracy": recent_accuracy,
            "sample_count": len(accuracies),
            "recent_samples": recent_samples,
        }

    @staticmethod
    def trim_history(history: List[float], max_size: int) -> List[float]:
        """Trim history list to prevent unlimited growth."""
        if len(history) > max_size:
            return history[-max_size:]
        return history

    @staticmethod
    def analyze_drift_alerts(drift_alerts: List[DriftAlert]) -> Dict[str, Any]:
        """Analyze drift alerts and return summary."""
        if not drift_alerts:
            return {
                "has_drift": False,
                "total_alerts": 0,
                "recent_alerts": [],
                "severity_counts": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
            }

        # Count alerts by severity
        severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for alert in drift_alerts:
            severity_counts[alert.severity] += 1

        # Get recent high-severity alerts
        recent_high_severity = [
            alert
            for alert in drift_alerts[-10:]
            if alert.severity in ["HIGH", "MEDIUM"]
        ]

        return {
            "has_drift": len(recent_high_severity) > 0,
            "total_alerts": len(drift_alerts),
            "recent_alerts": drift_alerts[-5:],
            "severity_counts": severity_counts,
            "high_severity_recent": len(recent_high_severity),
        }
