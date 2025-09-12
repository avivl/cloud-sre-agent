# gemini_sre_agent/pattern_detector/detection_algorithms.py

"""
Core pattern detection algorithms for log analysis.

This module provides specialized detection algorithms for identifying
various patterns in system logs using Protocol-based interfaces and
Generic typing for extensibility.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, Optional, Protocol, Set, TypeVar

from .models import LogEntry, PatternMatch, PatternType, ThresholdResult, TimeWindow

logger = logging.getLogger(__name__)

# Type variables for Generic typing
T = TypeVar("T", bound=PatternMatch)
AlgorithmConfig = TypeVar("AlgorithmConfig")


@dataclass
class DetectionAlgorithmConfig:
    """Base configuration for detection algorithms."""

    min_confidence: float = 0.3
    enabled: bool = True
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CascadeFailureConfig(DetectionAlgorithmConfig):
    """Configuration for cascade failure detection."""

    min_services: int = 2
    error_correlation_window_seconds: int = 300
    severity_threshold: List[str] = field(default_factory=lambda: ["ERROR", "CRITICAL"])


@dataclass
class ServiceDegradationConfig(DetectionAlgorithmConfig):
    """Configuration for service degradation detection."""

    min_error_rate: float = 0.05
    single_service_threshold: float = 0.8


@dataclass
class TrafficSpikeConfig(DetectionAlgorithmConfig):
    """Configuration for traffic spike detection."""

    volume_increase_threshold: float = 2.0
    concurrent_error_threshold: int = 10


@dataclass
class ConfigurationIssueConfig(DetectionAlgorithmConfig):
    """Configuration for configuration issue detection."""

    config_keywords: List[str] = field(
        default_factory=lambda: [
            "config",
            "configuration",
            "settings",
            "invalid",
            "missing",
        ]
    )
    rapid_onset_threshold_seconds: int = 60


@dataclass
class DependencyFailureConfig(DetectionAlgorithmConfig):
    """Configuration for dependency failure detection."""

    dependency_keywords: List[str] = field(
        default_factory=lambda: [
            "timeout",
            "connection",
            "unavailable",
            "refused",
            "dns",
            "network",
        ]
    )
    external_service_indicators: List[str] = field(
        default_factory=lambda: ["api", "external", "third-party"]
    )


@dataclass
class ResourceExhaustionConfig(DetectionAlgorithmConfig):
    """Configuration for resource exhaustion detection."""

    resource_keywords: List[str] = field(
        default_factory=lambda: [
            "memory",
            "cpu",
            "disk",
            "space",
            "limit",
            "quota",
            "throttle",
        ]
    )
    gradual_onset_indicators: List[str] = field(
        default_factory=lambda: ["slow", "degraded", "performance"]
    )


class DetectionAlgorithm(Protocol[T]):
    """Protocol for detection algorithms."""

    def detect(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
        logs: List[LogEntry],
    ) -> List[T]:
        """Detect patterns in the given data."""
        ...


class BaseDetectionAlgorithm(ABC, Generic[T]):
    """Base class for detection algorithms."""

    def __init__(self, config: DetectionAlgorithmConfig):
        """Initialize the detection algorithm."""
        self.config = config
        self.logger = logging.getLogger(f"DetectionAlgorithm.{self.__class__.__name__}")

    @abstractmethod
    def detect(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
        logs: List[LogEntry],
    ) -> List[T]:
        """Detect patterns in the given data."""
        pass

    def is_enabled(self) -> bool:
        """Check if the algorithm is enabled."""
        return self.config.enabled

    def get_weight(self) -> float:
        """Get the algorithm weight for ensemble methods."""
        return self.config.weight


class CascadeFailureDetector(BaseDetectionAlgorithm[PatternMatch]):
    """Detects cascade failure patterns in system logs."""

    def __init__(self, config: Optional[CascadeFailureConfig] = None):
        """Initialize the cascade failure detector."""
        super().__init__(config or CascadeFailureConfig())
        self.cascade_config: CascadeFailureConfig = self.config  # type: ignore

    def detect(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
        logs: List[LogEntry],
    ) -> List[PatternMatch]:
        """Detect cascade failure patterns."""
        if not self.is_enabled():
            return []

        patterns = []

        # Find cascade failure triggers
        cascade_triggers = [
            r
            for r in threshold_results
            if r.threshold_type == "cascade_failure" and r.triggered
        ]

        # Find service impact triggers
        service_impact_triggers = [
            r
            for r in threshold_results
            if r.threshold_type == "service_impact" and r.triggered
        ]

        # Check if we have cascade failure indicators
        has_cascade_failure = cascade_triggers or (
            service_impact_triggers
            and any(
                len(r.affected_services) >= self.cascade_config.min_services
                for r in service_impact_triggers
            )
        )

        if not has_cascade_failure:
            return patterns

        # Collect all affected services and triggering logs
        all_affected_services = set()
        all_triggering_logs = []

        for result in threshold_results:
            if result.triggered:
                all_affected_services.update(result.affected_services)
                all_triggering_logs.extend(result.triggering_logs)

        # Calculate confidence score
        confidence_score = self._calculate_confidence(
            window, all_triggering_logs, all_affected_services
        )

        if confidence_score >= self.cascade_config.min_confidence:
            severity = self._determine_severity_level(all_triggering_logs)
            primary_service = self._identify_primary_service(all_triggering_logs)

            patterns.append(
                PatternMatch(
                    pattern_type=PatternType.CASCADE_FAILURE,
                    confidence_score=confidence_score,
                    primary_service=primary_service,
                    affected_services=list(all_affected_services),
                    severity_level=severity,
                    evidence={
                        "service_count": len(all_affected_services),
                        "error_correlation": "high",
                        "failure_chain": list(all_affected_services),
                    },
                    remediation_priority="IMMEDIATE",
                    suggested_actions=[
                        "Investigate primary failure service",
                        "Check service dependencies",
                        "Implement circuit breakers",
                        "Scale up affected services",
                    ],
                )
            )

        return patterns

    def _calculate_confidence(
        self,
        window: TimeWindow,
        logs: List[LogEntry],
        affected_services: Set[str],
    ) -> float:
        """Calculate confidence score for cascade failure detection."""
        if not logs or not affected_services:
            return 0.0

        # Base confidence on service count and error correlation
        service_count_factor = min(len(affected_services) / 5.0, 1.0)
        error_density_factor = min(len(logs) / 100.0, 1.0)

        # Time correlation factor
        time_span = (window.end_time - window.start_time).total_seconds()
        time_correlation_factor = min(time_span / 300.0, 1.0)  # 5 minutes max

        confidence = (
            service_count_factor * 0.4
            + error_density_factor * 0.3
            + time_correlation_factor * 0.3
        )

        return min(confidence, 1.0)

    def _determine_severity_level(self, logs: List[LogEntry]) -> str:
        """Determine severity level based on log entries."""
        if not logs:
            return "LOW"

        error_counts = {}
        for log in logs:
            level = log.severity.upper()
            error_counts[level] = error_counts.get(level, 0) + 1

        total_logs = len(logs)
        critical_ratio = error_counts.get("CRITICAL", 0) / total_logs
        error_ratio = error_counts.get("ERROR", 0) / total_logs

        if critical_ratio > 0.5:
            return "CRITICAL"
        elif critical_ratio > 0.2 or error_ratio > 0.7:
            return "HIGH"
        elif error_ratio > 0.3:
            return "MEDIUM"
        else:
            return "LOW"

    def _identify_primary_service(self, logs: List[LogEntry]) -> Optional[str]:
        """Identify the primary service causing the cascade failure."""
        if not logs:
            return None

        service_counts = {}
        for log in logs:
            service = log.service_name or "unknown"
            service_counts[service] = service_counts.get(service, 0) + 1

        return (
            max(service_counts.items(), key=lambda x: x[1])[0]
            if service_counts
            else None
        )


class ServiceDegradationDetector(BaseDetectionAlgorithm[PatternMatch]):
    """Detects service degradation patterns in system logs."""

    def __init__(self, config: Optional[ServiceDegradationConfig] = None):
        """Initialize the service degradation detector."""
        super().__init__(config or ServiceDegradationConfig())
        self.degradation_config: ServiceDegradationConfig = self.config  # type: ignore

    def detect(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
        logs: List[LogEntry],
    ) -> List[PatternMatch]:
        """Detect service degradation patterns."""
        if not self.is_enabled():
            return []

        patterns = []

        # Find service degradation triggers
        degradation_triggers = [
            r
            for r in threshold_results
            if r.threshold_type == "service_degradation" and r.triggered
        ]

        if not degradation_triggers:
            return patterns

        for trigger in degradation_triggers:
            if not trigger.affected_services:
                continue

            # Calculate error rate
            total_logs = len(
                [log for log in logs if log.service_name in trigger.affected_services]
            )
            error_logs = len(
                [
                    log
                    for log in logs
                    if log.service_name in trigger.affected_services
                    and log.severity.upper() in ["ERROR", "CRITICAL"]
                ]
            )

            if total_logs == 0:
                continue

            error_rate = error_logs / total_logs

            if error_rate >= self.degradation_config.min_error_rate:
                confidence_score = self._calculate_confidence(
                    window, trigger.triggering_logs, error_rate
                )

                if confidence_score >= self.degradation_config.min_confidence:
                    primary_service = self._identify_primary_service(
                        trigger.triggering_logs
                    )
                    severity = self._determine_severity_level(trigger.triggering_logs)

                    patterns.append(
                        PatternMatch(
                            pattern_type=PatternType.SERVICE_DEGRADATION,
                            confidence_score=confidence_score,
                            primary_service=primary_service,
                            affected_services=trigger.affected_services,
                            severity_level=severity,
                            evidence={
                                "error_rate": error_rate,
                                "total_logs": total_logs,
                                "error_logs": error_logs,
                            },
                            remediation_priority="HIGH",
                            suggested_actions=[
                                "Investigate service performance",
                                "Check resource utilization",
                                "Review recent deployments",
                                "Scale up affected services",
                            ],
                        )
                    )

        return patterns

    def _calculate_confidence(
        self,
        window: TimeWindow,
        logs: List[LogEntry],
        error_rate: float,
    ) -> float:
        """Calculate confidence score for service degradation detection."""
        if not logs:
            return 0.0

        # Base confidence on error rate
        error_rate_factor = min(error_rate * 2, 1.0)

        # Log volume factor
        log_volume_factor = min(len(logs) / 50.0, 1.0)

        # Time window factor
        time_span = (window.end_time - window.start_time).total_seconds()
        time_factor = min(time_span / 1800.0, 1.0)  # 30 minutes max

        confidence = (
            error_rate_factor * 0.5 + log_volume_factor * 0.3 + time_factor * 0.2
        )

        return min(confidence, 1.0)

    def _determine_severity_level(self, logs: List[LogEntry]) -> str:
        """Determine severity level based on log entries."""
        if not logs:
            return "LOW"

        error_counts = {}
        for log in logs:
            level = log.severity.upper()
            error_counts[level] = error_counts.get(level, 0) + 1

        total_logs = len(logs)
        critical_ratio = error_counts.get("CRITICAL", 0) / total_logs
        error_ratio = error_counts.get("ERROR", 0) / total_logs

        if critical_ratio > 0.3:
            return "CRITICAL"
        elif critical_ratio > 0.1 or error_ratio > 0.5:
            return "HIGH"
        elif error_ratio > 0.2:
            return "MEDIUM"
        else:
            return "LOW"

    def _identify_primary_service(self, logs: List[LogEntry]) -> Optional[str]:
        """Identify the primary service experiencing degradation."""
        if not logs:
            return None

        service_counts = {}
        for log in logs:
            service = log.service_name or "unknown"
            service_counts[service] = service_counts.get(service, 0) + 1

        return (
            max(service_counts.items(), key=lambda x: x[1])[0]
            if service_counts
            else None
        )


class TrafficSpikeDetector(BaseDetectionAlgorithm[PatternMatch]):
    """Detects traffic spike patterns in system logs."""

    def __init__(self, config: Optional[TrafficSpikeConfig] = None):
        """Initialize the traffic spike detector."""
        super().__init__(config or TrafficSpikeConfig())
        self.spike_config = self.config

    def detect(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
        logs: List[LogEntry],
    ) -> List[PatternMatch]:
        """Detect traffic spike patterns."""
        if not self.is_enabled():
            return []

        patterns = []

        # Find traffic spike triggers
        spike_triggers = [
            r
            for r in threshold_results
            if r.threshold_type == "traffic_spike" and r.triggered
        ]

        if not spike_triggers:
            return patterns

        for trigger in spike_triggers:
            confidence_score = self._calculate_confidence(
                window, trigger.triggering_logs
            )

            if confidence_score >= self.spike_config.min_confidence:
                primary_service = self._identify_primary_service(
                    trigger.triggering_logs
                )
                severity = self._determine_severity_level(trigger.triggering_logs)

                # Calculate volume increase
                volume_increase = self._calculate_volume_increase(
                    window, trigger.triggering_logs
                )

                patterns.append(
                    PatternMatch(
                        pattern_type=PatternType.TRAFFIC_SPIKE,
                        confidence_score=confidence_score,
                        primary_service=primary_service,
                        affected_services=trigger.affected_services,
                        severity_level=severity,
                        evidence={
                            "volume_increase": volume_increase,
                            "log_count": len(trigger.triggering_logs),
                            "time_window_seconds": (
                                window.end_time - window.start_time
                            ).total_seconds(),
                        },
                        remediation_priority="MEDIUM",
                        suggested_actions=[
                            "Monitor resource utilization",
                            "Check for DDoS attacks",
                            "Scale up infrastructure",
                            "Review traffic patterns",
                        ],
                    )
                )

        return patterns

    def _calculate_confidence(
        self,
        window: TimeWindow,
        logs: List[LogEntry],
    ) -> float:
        """Calculate confidence score for traffic spike detection."""
        if not logs:
            return 0.0

        # Base confidence on log volume
        log_volume_factor = min(len(logs) / 200.0, 1.0)

        # Time concentration factor
        time_span = (window.end_time - window.start_time).total_seconds()
        time_concentration_factor = min(
            300.0 / time_span, 1.0
        )  # Prefer shorter time windows

        confidence = log_volume_factor * 0.6 + time_concentration_factor * 0.4

        return min(confidence, 1.0)

    def _calculate_volume_increase(
        self,
        window: TimeWindow,
        logs: List[LogEntry],
    ) -> float:
        """Calculate the volume increase factor."""
        # This is a simplified calculation
        # In a real implementation, you'd compare with historical data
        time_span_hours = (window.end_time - window.start_time).total_seconds() / 3600
        logs_per_hour = len(logs) / time_span_hours if time_span_hours > 0 else 0

        # Assume normal rate is 100 logs per hour
        normal_rate = 100
        return logs_per_hour / normal_rate if normal_rate > 0 else 1.0

    def _determine_severity_level(self, logs: List[LogEntry]) -> str:
        """Determine severity level based on log entries."""
        if not logs:
            return "LOW"

        log_count = len(logs)

        if log_count > 1000:
            return "CRITICAL"
        elif log_count > 500:
            return "HIGH"
        elif log_count > 200:
            return "MEDIUM"
        else:
            return "LOW"

    def _identify_primary_service(self, logs: List[LogEntry]) -> Optional[str]:
        """Identify the primary service experiencing traffic spike."""
        if not logs:
            return None

        service_counts = {}
        for log in logs:
            service = log.service_name or "unknown"
            service_counts[service] = service_counts.get(service, 0) + 1

        return (
            max(service_counts.items(), key=lambda x: x[1])[0]
            if service_counts
            else None
        )


class ConfigurationIssueDetector(BaseDetectionAlgorithm[PatternMatch]):
    """Detects configuration issue patterns in system logs."""

    def __init__(self, config: Optional[ConfigurationIssueConfig] = None):
        """Initialize the configuration issue detector."""
        super().__init__(config or ConfigurationIssueConfig())
        self.config_issue_config: ConfigurationIssueConfig = self.config  # type: ignore

    def detect(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
        logs: List[LogEntry],
    ) -> List[PatternMatch]:
        """Detect configuration issue patterns."""
        if not self.is_enabled():
            return []

        patterns = []

        # Filter logs for configuration-related errors
        config_logs = self._filter_config_logs(logs)

        if not config_logs:
            return patterns

        confidence_score = self._calculate_confidence(window, config_logs)

        if confidence_score >= self.config_issue_config.min_confidence:
            primary_service = self._identify_primary_service(config_logs)
            severity = self._determine_severity_level(config_logs)

            patterns.append(
                PatternMatch(
                    pattern_type=PatternType.CONFIGURATION_ISSUE,
                    confidence_score=confidence_score,
                    primary_service=primary_service,
                    affected_services=list(
                        set(log.service_name or "unknown" for log in config_logs)
                    ),
                    severity_level=severity,
                    evidence={
                        "config_error_count": len(config_logs),
                        "keywords_found": self._extract_keywords(config_logs),
                        "rapid_onset": self._check_rapid_onset(config_logs, window),
                    },
                    remediation_priority="HIGH",
                    suggested_actions=[
                        "Review configuration files",
                        "Check environment variables",
                        "Validate configuration syntax",
                        "Rollback recent configuration changes",
                    ],
                )
            )

        return patterns

    def _filter_config_logs(self, logs: List[LogEntry]) -> List[LogEntry]:
        """Filter logs for configuration-related errors."""
        config_logs = []

        for log in logs:
            log_message = (log.error_message or "").lower()
            if any(
                keyword in log_message
                for keyword in self.config_issue_config.config_keywords
            ):
                config_logs.append(log)

        return config_logs

    def _calculate_confidence(
        self,
        window: TimeWindow,
        logs: List[LogEntry],
    ) -> float:
        """Calculate confidence score for configuration issue detection."""
        if not logs:
            return 0.0

        # Base confidence on log count
        log_count_factor = min(len(logs) / 20.0, 1.0)

        # Keyword diversity factor
        unique_keywords = len(
            set(
                keyword
                for log in logs
                for keyword in self.config_issue_config.config_keywords
                if keyword in (log.error_message or "").lower()
            )
        )
        keyword_diversity_factor = min(unique_keywords / 3.0, 1.0)

        # Time concentration factor
        time_span = (window.end_time - window.start_time).total_seconds()
        time_concentration_factor = min(300.0 / time_span, 1.0)

        confidence = (
            log_count_factor * 0.4
            + keyword_diversity_factor * 0.3
            + time_concentration_factor * 0.3
        )

        return min(confidence, 1.0)

    def _extract_keywords(self, logs: List[LogEntry]) -> List[str]:
        """Extract configuration keywords found in logs."""
        found_keywords = set()

        for log in logs:
            log_message = (log.error_message or "").lower()
            for keyword in self.config_issue_config.config_keywords:
                if keyword in log_message:
                    found_keywords.add(keyword)

        return list(found_keywords)

    def _check_rapid_onset(self, logs: List[LogEntry], window: TimeWindow) -> bool:
        """Check if configuration errors started rapidly."""
        if not logs:
            return False

        # Sort logs by timestamp
        sorted_logs = sorted(logs, key=lambda log: log.timestamp)

        # Check if errors started within the rapid onset threshold
        first_error_time = sorted_logs[0].timestamp
        time_since_start = (first_error_time - window.start_time).total_seconds()

        return (
            time_since_start <= self.config_issue_config.rapid_onset_threshold_seconds
        )

    def _determine_severity_level(self, logs: List[LogEntry]) -> str:
        """Determine severity level based on log entries."""
        if not logs:
            return "LOW"

        error_counts = {}
        for log in logs:
            level = log.severity.upper()
            error_counts[level] = error_counts.get(level, 0) + 1

        total_logs = len(logs)
        critical_ratio = error_counts.get("CRITICAL", 0) / total_logs
        error_ratio = error_counts.get("ERROR", 0) / total_logs

        if critical_ratio > 0.4:
            return "CRITICAL"
        elif critical_ratio > 0.2 or error_ratio > 0.6:
            return "HIGH"
        elif error_ratio > 0.3:
            return "MEDIUM"
        else:
            return "LOW"

    def _identify_primary_service(self, logs: List[LogEntry]) -> Optional[str]:
        """Identify the primary service with configuration issues."""
        if not logs:
            return None

        service_counts = {}
        for log in logs:
            service = log.service_name or "unknown"
            service_counts[service] = service_counts.get(service, 0) + 1

        return (
            max(service_counts.items(), key=lambda x: x[1])[0]
            if service_counts
            else None
        )


class DependencyFailureDetector(BaseDetectionAlgorithm[PatternMatch]):
    """Detects dependency failure patterns in system logs."""

    def __init__(self, config: Optional[DependencyFailureConfig] = None):
        """Initialize the dependency failure detector."""
        super().__init__(config or DependencyFailureConfig())
        self.dependency_config: DependencyFailureConfig = self.config  # type: ignore

    def detect(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
        logs: List[LogEntry],
    ) -> List[PatternMatch]:
        """Detect dependency failure patterns."""
        if not self.is_enabled():
            return []

        patterns = []

        # Filter logs for dependency-related errors
        dependency_logs = self._filter_dependency_logs(logs)

        if not dependency_logs:
            return patterns

        confidence_score = self._calculate_confidence(window, dependency_logs)

        if confidence_score >= self.dependency_config.min_confidence:
            primary_service = self._identify_primary_service(dependency_logs)
            severity = self._determine_severity_level(dependency_logs)

            patterns.append(
                PatternMatch(
                    pattern_type=PatternType.DEPENDENCY_FAILURE,
                    confidence_score=confidence_score,
                    primary_service=primary_service,
                    affected_services=list(
                        set(log.service_name or "unknown" for log in dependency_logs)
                    ),
                    severity_level=severity,
                    evidence={
                        "dependency_error_count": len(dependency_logs),
                        "keywords_found": self._extract_keywords(dependency_logs),
                        "external_services": self._identify_external_services(
                            dependency_logs
                        ),
                    },
                    remediation_priority="HIGH",
                    suggested_actions=[
                        "Check external service status",
                        "Implement retry mechanisms",
                        "Add circuit breakers",
                        "Review dependency configurations",
                    ],
                )
            )

        return patterns

    def _filter_dependency_logs(self, logs: List[LogEntry]) -> List[LogEntry]:
        """Filter logs for dependency-related errors."""
        dependency_logs = []

        for log in logs:
            log_message = (log.error_message or "").lower()
            if any(
                keyword in log_message
                for keyword in self.dependency_config.dependency_keywords
            ):
                dependency_logs.append(log)

        return dependency_logs

    def _calculate_confidence(
        self,
        window: TimeWindow,
        logs: List[LogEntry],
    ) -> float:
        """Calculate confidence score for dependency failure detection."""
        if not logs:
            return 0.0

        # Base confidence on log count
        log_count_factor = min(len(logs) / 15.0, 1.0)

        # Keyword diversity factor
        unique_keywords = len(
            set(
                keyword
                for log in logs
                for keyword in self.dependency_config.dependency_keywords
                if keyword in (log.error_message or "").lower()
            )
        )
        keyword_diversity_factor = min(unique_keywords / 2.0, 1.0)

        # External service factor
        external_service_factor = 1.0 if self._has_external_services(logs) else 0.5

        confidence = (
            log_count_factor * 0.4
            + keyword_diversity_factor * 0.3
            + external_service_factor * 0.3
        )

        return min(confidence, 1.0)

    def _extract_keywords(self, logs: List[LogEntry]) -> List[str]:
        """Extract dependency keywords found in logs."""
        found_keywords = set()

        for log in logs:
            log_message = (log.error_message or "").lower()
            for keyword in self.dependency_config.dependency_keywords:
                if keyword in log_message:
                    found_keywords.add(keyword)

        return list(found_keywords)

    def _has_external_services(self, logs: List[LogEntry]) -> bool:
        """Check if logs mention external services."""
        for log in logs:
            log_message = (log.error_message or "").lower()
            if any(
                indicator in log_message
                for indicator in self.dependency_config.external_service_indicators
            ):
                return True
        return False

    def _identify_external_services(self, logs: List[LogEntry]) -> List[str]:
        """Identify external services mentioned in logs."""
        external_services = set()

        for log in logs:
            log_message = (log.error_message or "").lower()
            for indicator in self.dependency_config.external_service_indicators:
                if indicator in log_message:
                    external_services.add(indicator)

        return list(external_services)

    def _determine_severity_level(self, logs: List[LogEntry]) -> str:
        """Determine severity level based on log entries."""
        if not logs:
            return "LOW"

        error_counts = {}
        for log in logs:
            level = log.severity.upper()
            error_counts[level] = error_counts.get(level, 0) + 1

        total_logs = len(logs)
        critical_ratio = error_counts.get("CRITICAL", 0) / total_logs
        error_ratio = error_counts.get("ERROR", 0) / total_logs

        if critical_ratio > 0.3:
            return "CRITICAL"
        elif critical_ratio > 0.1 or error_ratio > 0.5:
            return "HIGH"
        elif error_ratio > 0.2:
            return "MEDIUM"
        else:
            return "LOW"

    def _identify_primary_service(self, logs: List[LogEntry]) -> Optional[str]:
        """Identify the primary service experiencing dependency failures."""
        if not logs:
            return None

        service_counts = {}
        for log in logs:
            service = log.service_name or "unknown"
            service_counts[service] = service_counts.get(service, 0) + 1

        return (
            max(service_counts.items(), key=lambda x: x[1])[0]
            if service_counts
            else None
        )


class ResourceExhaustionDetector(BaseDetectionAlgorithm[PatternMatch]):
    """Detects resource exhaustion patterns in system logs."""

    def __init__(self, config: Optional[ResourceExhaustionConfig] = None):
        """Initialize the resource exhaustion detector."""
        super().__init__(config or ResourceExhaustionConfig())
        self.resource_config: ResourceExhaustionConfig = self.config  # type: ignore

    def detect(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
        logs: List[LogEntry],
    ) -> List[PatternMatch]:
        """Detect resource exhaustion patterns."""
        if not self.is_enabled():
            return []

        patterns = []

        # Filter logs for resource-related errors
        resource_logs = self._filter_resource_logs(logs)

        if not resource_logs:
            return patterns

        confidence_score = self._calculate_confidence(window, resource_logs)

        if confidence_score >= self.resource_config.min_confidence:
            primary_service = self._identify_primary_service(resource_logs)
            severity = self._determine_severity_level(resource_logs)

            patterns.append(
                PatternMatch(
                    pattern_type=PatternType.RESOURCE_EXHAUSTION,
                    confidence_score=confidence_score,
                    primary_service=primary_service,
                    affected_services=list(
                        set(log.service_name or "unknown" for log in resource_logs)
                    ),
                    severity_level=severity,
                    evidence={
                        "resource_error_count": len(resource_logs),
                        "keywords_found": self._extract_keywords(resource_logs),
                        "gradual_onset": self._check_gradual_onset(
                            resource_logs, window
                        ),
                    },
                    remediation_priority="HIGH",
                    suggested_actions=[
                        "Check resource utilization",
                        "Scale up infrastructure",
                        "Optimize resource usage",
                        "Review resource limits",
                    ],
                )
            )

        return patterns

    def _filter_resource_logs(self, logs: List[LogEntry]) -> List[LogEntry]:
        """Filter logs for resource-related errors."""
        resource_logs = []

        for log in logs:
            log_message = (log.error_message or "").lower()
            if any(
                keyword in log_message
                for keyword in self.resource_config.resource_keywords
            ):
                resource_logs.append(log)

        return resource_logs

    def _calculate_confidence(
        self,
        window: TimeWindow,
        logs: List[LogEntry],
    ) -> float:
        """Calculate confidence score for resource exhaustion detection."""
        if not logs:
            return 0.0

        # Base confidence on log count
        log_count_factor = min(len(logs) / 10.0, 1.0)

        # Keyword diversity factor
        unique_keywords = len(
            set(
                keyword
                for log in logs
                for keyword in self.resource_config.resource_keywords
                if keyword in (log.error_message or "").lower()
            )
        )
        keyword_diversity_factor = min(unique_keywords / 2.0, 1.0)

        # Gradual onset factor
        gradual_onset_factor = 1.0 if self._check_gradual_onset(logs, window) else 0.7

        confidence = (
            log_count_factor * 0.4
            + keyword_diversity_factor * 0.3
            + gradual_onset_factor * 0.3
        )

        return min(confidence, 1.0)

    def _extract_keywords(self, logs: List[LogEntry]) -> List[str]:
        """Extract resource keywords found in logs."""
        found_keywords = set()

        for log in logs:
            log_message = (log.error_message or "").lower()
            for keyword in self.resource_config.resource_keywords:
                if keyword in log_message:
                    found_keywords.add(keyword)

        return list(found_keywords)

    def _check_gradual_onset(self, logs: List[LogEntry], window: TimeWindow) -> bool:
        """Check if resource errors started gradually."""
        if not logs:
            return False

        # Sort logs by timestamp
        sorted_logs = sorted(logs, key=lambda log: log.timestamp)

        # Check if errors started gradually over time
        time_span = (window.end_time - window.start_time).total_seconds()
        if time_span < 300:  # Less than 5 minutes
            return False

        # Check for gradual increase in error frequency
        quarters = [
            sorted_logs[i : i + len(sorted_logs) // 4]
            for i in range(0, len(sorted_logs), len(sorted_logs) // 4)
        ]

        if len(quarters) < 2:
            return False

        # Check if error count increases over quarters
        quarter_counts = [len(quarter) for quarter in quarters]
        return quarter_counts[-1] > quarter_counts[0]

    def _determine_severity_level(self, logs: List[LogEntry]) -> str:
        """Determine severity level based on log entries."""
        if not logs:
            return "LOW"

        error_counts = {}
        for log in logs:
            level = log.severity.upper()
            error_counts[level] = error_counts.get(level, 0) + 1

        total_logs = len(logs)
        critical_ratio = error_counts.get("CRITICAL", 0) / total_logs
        error_ratio = error_counts.get("ERROR", 0) / total_logs

        if critical_ratio > 0.4:
            return "CRITICAL"
        elif critical_ratio > 0.2 or error_ratio > 0.6:
            return "HIGH"
        elif error_ratio > 0.3:
            return "MEDIUM"
        else:
            return "LOW"

    def _identify_primary_service(self, logs: List[LogEntry]) -> Optional[str]:
        """Identify the primary service experiencing resource exhaustion."""
        if not logs:
            return None

        service_counts = {}
        for log in logs:
            service = log.service_name or "unknown"
            service_counts[service] = service_counts.get(service, 0) + 1

        return (
            max(service_counts.items(), key=lambda x: x[1])[0]
            if service_counts
            else None
        )


class DetectionAlgorithmFactory:
    """Factory for creating detection algorithms."""

    @staticmethod
    def create_algorithm(
        algorithm_type: str, config: Optional[DetectionAlgorithmConfig] = None
    ) -> BaseDetectionAlgorithm[PatternMatch]:
        """Create a detection algorithm instance."""
        algorithm_map = {
            "cascade_failure": CascadeFailureDetector,
            "service_degradation": ServiceDegradationDetector,
            "traffic_spike": TrafficSpikeDetector,
            "configuration_issue": ConfigurationIssueDetector,
            "dependency_failure": DependencyFailureDetector,
            "resource_exhaustion": ResourceExhaustionDetector,
        }

        if algorithm_type not in algorithm_map:
            raise ValueError(f"Unknown algorithm type: {algorithm_type}")

        algorithm_class = algorithm_map[algorithm_type]

        if config is None:
            # Use default config for the algorithm type
            config_map = {
                "cascade_failure": CascadeFailureConfig(),
                "service_degradation": ServiceDegradationConfig(),
                "traffic_spike": TrafficSpikeConfig(),
                "configuration_issue": ConfigurationIssueConfig(),
                "dependency_failure": DependencyFailureConfig(),
                "resource_exhaustion": ResourceExhaustionConfig(),
            }
            config = config_map[algorithm_type]

        return algorithm_class(config)

    @staticmethod
    def get_available_algorithms() -> List[str]:
        """Get list of available algorithm types."""
        return [
            "cascade_failure",
            "service_degradation",
            "traffic_spike",
            "configuration_issue",
            "dependency_failure",
            "resource_exhaustion",
        ]
