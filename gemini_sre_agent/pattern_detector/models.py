# gemini_sre_agent/pattern_detector/models.py

"""
Data models for the pattern detection system.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class LogEntry(BaseModel):
    """Structured representation of a log entry for pattern analysis."""

    insert_id: str
    timestamp: datetime
    severity: str
    service_name: Optional[str] = None
    error_message: Optional[str] = None
    raw_data: Dict[str, Any]

    def __init__(self, **data):
        data = self._process_timestamp(data)
        data = self._process_severity(data)
        data = self._process_service_name(data)
        data = self._process_error_message(data)
        super().__init__(**data)

    def _process_timestamp(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and process timestamp from raw data."""
        if "timestamp" not in data and "raw_data" in data:
            raw_timestamp = data["raw_data"].get("timestamp")
            if raw_timestamp:
                try:
                    data["timestamp"] = datetime.fromisoformat(
                        raw_timestamp.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    data["timestamp"] = datetime.now(timezone.utc)
            else:
                data["timestamp"] = datetime.now(timezone.utc)
        return data

    def _process_severity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract severity from raw data."""
        if "severity" not in data and "raw_data" in data:
            data["severity"] = data["raw_data"].get("severity", "INFO")
        return data

    def _process_service_name(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract service name from resource labels."""
        if "service_name" not in data and "raw_data" in data:
            resource = data["raw_data"].get("resource", {})
            labels = resource.get("labels", {})
            data["service_name"] = labels.get("service_name") or labels.get(
                "function_name"
            )
        return data

    def _process_error_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract error message from raw data."""
        if "error_message" not in data and "raw_data" in data:
            data["error_message"] = data["raw_data"].get("textPayload") or data[
                "raw_data"
            ].get("message")
        return data


@dataclass
class TimeWindow:
    """Represents a time window for log accumulation."""

    start_time: datetime
    duration_minutes: int
    logs: List[LogEntry] = field(default_factory=list)

    @property
    def end_time(self) -> datetime:
        """Calculate the end time of this window."""
        return self.start_time + timedelta(minutes=self.duration_minutes)

    def is_active(self, current_time: datetime) -> bool:
        """Check if this window is still active for log collection."""
        return current_time < self.end_time

    def is_expired(self, current_time: datetime) -> bool:
        """Check if this window has expired and should be processed."""
        return current_time >= self.end_time

    def accepts_log(self, log_entry: LogEntry) -> bool:
        """Check if this window should accept the given log entry."""
        return self.start_time <= log_entry.timestamp < self.end_time

    def add_log(self, log_entry: LogEntry) -> bool:
        """Add a log entry to this window if it belongs here."""
        if self.accepts_log(log_entry):
            self.logs.append(log_entry)
            return True
        return False

    def get_error_logs(self) -> List[LogEntry]:
        """Get only error-level logs from this window."""
        return [
            log
            for log in self.logs
            if log.severity in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]
        ]

    def get_service_groups(self) -> Dict[str, List[LogEntry]]:
        """Group logs by service name."""
        groups: Dict[str, List[LogEntry]] = defaultdict(list)
        for log in self.logs:
            service = log.service_name or "unknown"
            groups[service].append(log)
        return dict(groups)


class ThresholdType:
    """Enumeration of threshold types for pattern detection."""

    ERROR_FREQUENCY = "error_frequency"  # Count of errors in window
    ERROR_RATE = "error_rate"  # Percentage increase from baseline
    SERVICE_IMPACT = "service_impact"  # Number of affected services
    SEVERITY_WEIGHTED = "severity_weighted"  # Weighted score by severity
    CASCADE_FAILURE = "cascade_failure"  # Multi-service correlation


@dataclass
class ThresholdConfig:
    """Configuration for smart thresholds."""

    threshold_type: str
    min_value: float
    max_value: Optional[float] = None

    # Error frequency thresholds
    min_error_count: int = 3

    # Error rate thresholds (percentage)
    min_rate_increase: float = 10.0  # 10% increase from baseline
    baseline_window_count: int = 12  # Windows to use for baseline

    # Service impact thresholds
    min_affected_services: int = 2

    # Severity weights for scoring
    severity_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "CRITICAL": 10.0,
            "ERROR": 5.0,
            "WARNING": 2.0,
            "INFO": 1.0,
        }
    )

    # Cascade failure detection
    cascade_time_window_minutes: int = 10
    cascade_min_services: int = 2


@dataclass
class ThresholdResult:
    """Result of threshold evaluation."""

    threshold_type: str
    triggered: bool
    score: float
    details: Dict[str, Any]
    triggering_logs: List[LogEntry]
    affected_services: List[str]


class PatternType:
    """Enumeration of detectable issue patterns."""

    SPORADIC_ERRORS = "sporadic_errors"  # Random errors across services
    SERVICE_DEGRADATION = "service_degradation"  # Single service having issues
    CASCADE_FAILURE = "cascade_failure"  # Multi-service failure chain
    TRAFFIC_SPIKE = "traffic_spike"  # High volume causing errors
    CONFIGURATION_ISSUE = "configuration_issue"  # Config-related problems
    DEPENDENCY_FAILURE = "dependency_failure"  # External dependency issues
    RESOURCE_EXHAUSTION = "resource_exhaustion"  # Memory/CPU/disk issues


@dataclass
class PatternMatch:
    """Result of pattern classification."""

    pattern_type: str
    confidence_score: float  # 0.0 to 1.0
    primary_service: Optional[str]
    affected_services: List[str]
    severity_level: str  # LOW, MEDIUM, HIGH, CRITICAL

    # Evidence supporting the pattern classification
    evidence: Dict[str, Any]

    # Recommended remediation approach
    remediation_priority: str  # IMMEDIATE, HIGH, MEDIUM, LOW
    suggested_actions: List[str]


class ConfidenceFactors:
    """Enumeration of confidence scoring factors."""

    # Temporal factors
    TIME_CONCENTRATION = "time_concentration"
    TIME_CORRELATION = "time_correlation"
    RAPID_ONSET = "rapid_onset"
    GRADUAL_ONSET = "gradual_onset"

    # Service impact factors
    SERVICE_COUNT = "service_count"
    SERVICE_DISTRIBUTION = "service_distribution"
    CROSS_SERVICE_CORRELATION = "cross_service_correlation"

    # Error pattern factors
    ERROR_FREQUENCY = "error_frequency"
    ERROR_SEVERITY = "error_severity"
    ERROR_TYPE_CONSISTENCY = "error_type_consistency"
    MESSAGE_SIMILARITY = "message_similarity"

    # Historical factors
    BASELINE_DEVIATION = "baseline_deviation"
    TREND_ANALYSIS = "trend_analysis"
    SEASONAL_PATTERN = "seasonal_pattern"

    # External factors
    DEPENDENCY_STATUS = "dependency_status"
    RESOURCE_UTILIZATION = "resource_utilization"
    DEPLOYMENT_CORRELATION = "deployment_correlation"


@dataclass
class ConfidenceRule:
    """Configuration for confidence factor calculation."""

    factor_type: str
    weight: float  # 0.0 to 1.0
    threshold: Optional[float] = None
    max_contribution: float = 1.0
    decay_function: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfidenceScore:
    """Detailed confidence score with factor breakdown."""

    overall_score: float
    factor_scores: Dict[str, float]
    raw_factors: Dict[str, float]
    confidence_level: str
    explanation: List[str]
