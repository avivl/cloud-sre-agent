"""
Configuration and data models for model performance monitoring.

This module provides configuration classes and data structures for
tracking model performance, drift detection, and metrics analysis.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


@dataclass
class PerformanceConfig:
    """Configuration for model performance monitoring."""

    # Window sizes for tracking
    window_size: int = 100  # Main sliding window size
    recent_window_size: int = 25  # Recent samples for drift comparison
    pattern_accuracy_window: int = 10  # Pattern-specific accuracy window
    max_pattern_history: int = 200  # Max samples per pattern type

    # Baseline establishment
    baseline_establishment_size: int = 20  # Min samples to set baseline

    # Drift detection thresholds
    accuracy_drift_threshold: float = 0.15  # 15% accuracy drift
    confidence_drift_threshold: float = 0.20  # 20% confidence drift
    latency_drift_multiplier: float = 2.0  # 100% latency increase
    high_drift_threshold: float = 0.30  # Threshold for HIGH severity

    # Drift checking configuration
    drift_check_interval_seconds: int = 3600  # Check every hour
    min_samples_for_drift_check: int = 50  # Minimum samples before checking


@dataclass
class DriftAlert:
    """Data structure for drift detection alerts."""

    drift_type: str  # "accuracy_drift", "confidence_drift", "latency_drift"
    severity: str  # "HIGH", "MEDIUM", "LOW"
    baseline_value: float
    current_value: float
    drift_amount: float
    timestamp: datetime

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"{self.drift_type.upper()}({self.severity}): "
            f"baseline={self.baseline_value:.3f}, "
            f"current={self.current_value:.3f}, "
            f"drift={self.drift_amount:.3f}"
        )


class PerformanceMetrics:
    """Helper class for performance metrics calculations."""

    @staticmethod
    def empty_metrics() -> Dict[str, Any]:
        """Return empty metrics structure when no data is available."""
        return {
            "overall_accuracy": 0.0,
            "recent_accuracy": 0.0,
            "baseline_accuracy": None,
            "overall_confidence": 0.0,
            "recent_confidence": 0.0,
            "baseline_confidence": None,
            "overall_latency_ms": 0.0,
            "recent_latency_ms": 0.0,
            "baseline_latency_ms": None,
            "pattern_accuracy": {},
            "total_predictions": 0,
            "drift_alerts_count": 0,
            "recent_drift_alerts": [],
            "baseline_established": False,
            "drift_check_enabled": False,
        }

    @staticmethod
    def calculate_drift_percentage(baseline: float, current: float) -> float:
        """Calculate percentage drift from baseline."""
        if baseline == 0:
            return 0.0
        return ((current - baseline) / baseline) * 100

    @staticmethod
    def is_significant_drift(baseline: float, current: float, threshold: float) -> bool:
        """Check if drift is significant based on threshold."""
        return abs(current - baseline) > threshold

    @staticmethod
    def categorize_drift_severity(drift_amount: float, high_threshold: float) -> str:
        """Categorize drift severity based on amount."""
        if drift_amount > high_threshold:
            return "HIGH"
        elif drift_amount > high_threshold * 0.5:
            return "MEDIUM"
        else:
            return "LOW"
