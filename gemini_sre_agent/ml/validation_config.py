"""
Configuration and data models for log quality validation.

This module provides data structures and thresholds for validating
log quality before AI processing including completeness, noise detection,
consistency checking, and duplicate analysis.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class LogEntry:
    """Represents a single log entry for quality validation."""

    timestamp: datetime
    service_name: Optional[str] = None
    error_message: Optional[str] = None
    severity: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}


@dataclass
class QualityThresholds:
    """Configuration thresholds for log quality validation."""

    # Completeness requirements (0.0-1.0)
    min_completeness: float = 0.80  # 80% of logs must have essential fields

    # Noise ratio limits (0.0-1.0)
    max_noise_ratio: float = 0.20  # Max 20% noisy/low-value logs

    # Consistency requirements (0.0-1.0)
    min_consistency: float = 0.70  # 70% pattern consistency required

    # Duplicate limits (0.0-1.0)
    max_duplicate_ratio: float = 0.30  # Max 30% duplicate messages

    # Overall quality threshold (0.0-1.0)
    overall_quality_threshold: float = 0.75  # 75% overall quality required


@dataclass
class TimeWindow:
    """Represents a time window containing logs for analysis."""

    start_time: datetime
    end_time: datetime
    logs: List[LogEntry]
    window_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate time window configuration."""
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")

        if self.window_id is None:
            self.window_id = (
                f"{self.start_time.isoformat()}_{self.end_time.isoformat()}"
            )

    @property
    def duration_seconds(self) -> float:
        """Get window duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()

    @property
    def log_count(self) -> int:
        """Get number of logs in window."""
        return len(self.logs)


class ValidationMetrics:
    """Helper class for validation metrics calculations and formatting."""

    @staticmethod
    def empty_metrics() -> Dict[str, Any]:
        """Return empty metrics structure when no logs are available."""
        return {
            "overall_quality": 0.0,
            "completeness": 0.0,
            "noise_ratio": 1.0,  # 100% noise when no valid logs
            "consistency": 0.0,
            "duplicate_ratio": 0.0,
            "passes_threshold": False,
            "quality_factors": {
                "completeness": 0.0,
                "low_noise": 0.0,
                "consistency": 0.0,
                "low_duplicates": 1.0,
            },
            "total_logs_analyzed": 0,
        }

    @staticmethod
    def format_quality_score(score: float) -> str:
        """Format quality score as percentage string."""
        return f"{score * 100:.1f}%"

    @staticmethod
    def categorize_quality_level(overall_quality: float) -> str:
        """Categorize overall quality into descriptive levels."""
        if overall_quality >= 0.90:
            return "EXCELLENT"
        elif overall_quality >= 0.80:
            return "GOOD"
        elif overall_quality >= 0.70:
            return "FAIR"
        elif overall_quality >= 0.50:
            return "POOR"
        else:
            return "CRITICAL"

    @staticmethod
    def calculate_quality_improvement(current: float, target: float) -> float:
        """Calculate quality improvement needed to reach target."""
        return max(0.0, target - current)

    @staticmethod
    def estimate_logs_needed_for_quality(
        current_logs: int, current_quality: float, target_quality: float
    ) -> int:
        """Estimate additional logs needed to reach target quality."""
        if current_quality >= target_quality:
            return 0

        # Simplified estimation: assume linear relationship
        improvement_ratio = (
            target_quality / current_quality if current_quality > 0 else 2.0
        )
        additional_logs_ratio = improvement_ratio - 1.0
        return int(current_logs * additional_logs_ratio)


class ValidationRules:
    """Validation rules and criteria for log quality assessment."""

    # Essential fields required for completeness
    ESSENTIAL_FIELDS = {"service_name", "error_message", "severity"}

    # Severity levels considered noisy
    NOISY_SEVERITY_LEVELS = {"DEBUG", "TRACE"}

    # Minimum message length to avoid noise
    MIN_MESSAGE_LENGTH = 10

    # Pattern normalization rules for consistency analysis
    NORMALIZATION_PATTERNS = {
        "numbers": r"\d+",
        "uuids": r"[a-f0-9-]{8,}",
        "ips": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        "timestamps": r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
        "urls": r"https?://[^\s]+",
        "file_paths": r"(?:/[^/\s]+)+",
    }

    @classmethod
    def is_essential_field_complete(cls, log_entry: LogEntry) -> bool:
        """Check if log entry has all essential fields populated."""
        return all(
            getattr(log_entry, field) and str(getattr(log_entry, field)).strip()
            for field in cls.ESSENTIAL_FIELDS
        )

    @classmethod
    def is_noisy_severity(cls, severity: Optional[str]) -> bool:
        """Check if severity level is considered noisy."""
        return bool(severity and severity.upper() in cls.NOISY_SEVERITY_LEVELS)

    @classmethod
    def is_message_too_short(cls, message: Optional[str]) -> bool:
        """Check if message is too short to be meaningful."""
        return not message or len(message.strip()) < cls.MIN_MESSAGE_LENGTH
