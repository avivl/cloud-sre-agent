"""
Pattern classification logic.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from ..logger import setup_logging
from .confidence_scorer import ConfidenceScorer
from .models import (
    LogEntry,
    PatternMatch,
    PatternType,
    ThresholdResult,
    ThresholdType,
    TimeWindow,
)


class PatternClassifier:
    """Classifies threshold evaluation results into actionable patterns."""

    # Common suggested actions
    SCALE_UP_ACTION = "Scale up affected services"

    def __init__(self, confidence_scorer: Optional[ConfidenceScorer] = None):
        self.logger = setup_logging()
        self.classification_rules = self._load_classification_rules()
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()
        self.logger.info("[PATTERN_DETECTION] PatternClassifier initialized")

    def classify_patterns(
        self, window: TimeWindow, threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        patterns = []
        triggered_results = [r for r in threshold_results if r.triggered]
        if not triggered_results:
            self.logger.debug(
                f"[PATTERN_DETECTION] No triggered thresholds to classify: window={window.start_time}"
            )
            return patterns

        self.logger.info(
            f"[PATTERN_DETECTION] Classifying patterns: window={window.start_time}, "
            f"triggered_thresholds={len(triggered_results)}"
        )

        # Detect all pattern types
        patterns.extend(self._detect_cascade_failure(window, triggered_results))
        patterns.extend(self._detect_service_degradation(window, triggered_results))
        patterns.extend(self._detect_traffic_spike(window, triggered_results))
        patterns.extend(self._detect_configuration_issue(window, triggered_results))
        patterns.extend(self._detect_dependency_failure(window, triggered_results))
        patterns.extend(self._detect_resource_exhaustion(window, triggered_results))

        if not patterns:
            patterns.extend(self._detect_sporadic_errors(window, triggered_results))

        patterns.sort(key=lambda p: p.confidence_score, reverse=True)
        self.logger.info(
            f"[PATTERN_DETECTION] Pattern classification complete: "
            f"patterns_detected={len(patterns)}, window={window.start_time}"
        )
        return patterns

    def _load_classification_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load pattern classification rules and thresholds."""
        return {
            "cascade_failure": {
                "min_services": 2,
                "min_confidence": 0.3,  # Lowered for conservative confidence scoring
                "error_correlation_window_seconds": 300,  # 5 minutes
                "severity_threshold": ["ERROR", "CRITICAL"],
            },
            "service_degradation": {
                "min_error_rate": 0.05,  # 5% error rate
                "min_confidence": 0.3,  # Lowered for conservative confidence scoring
                "single_service_threshold": 0.8,  # 80% of errors from one service
            },
            "traffic_spike": {
                "volume_increase_threshold": 2.0,  # 2x normal volume
                "min_confidence": 0.2,  # Lowered for conservative confidence scoring
                "concurrent_error_threshold": 10,
            },
            "configuration_issue": {
                "config_keywords": [
                    "config",
                    "configuration",
                    "settings",
                    "invalid",
                    "missing",
                ],
                "min_confidence": 0.3,  # Lowered for conservative confidence scoring
                "rapid_onset_threshold_seconds": 60,  # Errors start quickly
            },
            "dependency_failure": {
                "dependency_keywords": [
                    "timeout",
                    "connection",
                    "unavailable",
                    "refused",
                    "dns",
                    "network",
                ],
                "min_confidence": 0.3,  # Lowered for conservative confidence scoring
                "external_service_indicators": ["api", "external", "third-party"],
            },
            "resource_exhaustion": {
                "resource_keywords": [
                    "memory",
                    "cpu",
                    "disk",
                    "space",
                    "limit",
                    "quota",
                    "throttle",
                ],
                "min_confidence": 0.3,  # Lowered for conservative confidence scoring
                "gradual_onset_indicators": ["slow", "degraded", "performance"],
            },
        }

    def _detect_cascade_failure(
        self, window: TimeWindow, threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        patterns = []
        rules = self.classification_rules["cascade_failure"]

        cascade_triggers = [
            r
            for r in threshold_results
            if r.threshold_type == ThresholdType.CASCADE_FAILURE and r.triggered
        ]

        service_impact_triggers = [
            r
            for r in threshold_results
            if r.threshold_type == ThresholdType.SERVICE_IMPACT and r.triggered
        ]

        if cascade_triggers or (
            service_impact_triggers
            and any(
                len(r.affected_services) >= rules["min_services"]
                for r in service_impact_triggers
            )
        ):

            all_affected_services = set()
            all_triggering_logs = []

            for result in threshold_results:
                if result.triggered:
                    all_affected_services.update(result.affected_services)
                    all_triggering_logs.extend(result.triggering_logs)

            confidence_score = self.confidence_scorer.calculate_confidence(
                pattern_type=PatternType.CASCADE_FAILURE,
                window=window,
                logs=all_triggering_logs,
                additional_context={
                    "affected_services": list(all_affected_services),
                    "service_count": len(all_affected_services),
                    "rules": rules,
                },
            )

            if confidence_score.overall_score >= rules["min_confidence"]:
                severity = self._determine_severity_level(all_triggering_logs)
                primary_service = self._identify_primary_service(all_triggering_logs)

                patterns.append(
                    PatternMatch(
                        pattern_type=PatternType.CASCADE_FAILURE,
                        confidence_score=confidence_score.overall_score,
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
                            self.SCALE_UP_ACTION,
                        ],
                    )
                )

        return patterns

    def _detect_service_degradation(
        self, window: TimeWindow, threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        patterns = []
        rules = self.classification_rules["service_degradation"]

        service_errors = self._group_service_errors(threshold_results)

        for service_name, error_logs in service_errors.items():
            if self._should_create_service_pattern(error_logs, service_errors, rules):
                pattern = self._create_service_degradation_pattern(
                    service_name,
                    error_logs,
                    len(error_logs)
                    / sum(len(logs) for logs in service_errors.values()),
                    sum(len(logs) for logs in service_errors.values()),
                    window,
                    rules,
                )
                if pattern:
                    patterns.append(pattern)

        return patterns

    def _group_service_errors(
        self, threshold_results: List[ThresholdResult]
    ) -> Dict[str, List[LogEntry]]:
        """Group error logs by service name."""
        service_errors = defaultdict(list)
        for result in threshold_results:
            if result.triggered:
                for log in result.triggering_logs:
                    if log.service_name:
                        service_errors[log.service_name].append(log)
        return service_errors

    def _should_create_service_pattern(
        self,
        error_logs: List[LogEntry],
        service_errors: Dict[str, List[LogEntry]],
        rules: Dict[str, Any],
    ) -> bool:
        """Check if a service degradation pattern should be created."""
        total_errors = sum(len(logs) for logs in service_errors.values())
        if total_errors == 0:
            return False
        service_error_ratio = len(error_logs) / total_errors
        return service_error_ratio >= rules["single_service_threshold"]

    def _create_service_degradation_pattern(
        self,
        service_name: str,
        error_logs: List[LogEntry],
        service_error_ratio: float,
        total_errors: int,
        window: TimeWindow,
        rules: Dict[str, Any],
    ) -> Optional[PatternMatch]:
        """Create a service degradation pattern if confidence threshold is met."""
        confidence_score = self.confidence_scorer.calculate_confidence(
            pattern_type=PatternType.SERVICE_DEGRADATION,
            window=window,
            logs=error_logs,
            additional_context={
                "service_name": service_name,
                "service_error_ratio": service_error_ratio,
                "total_errors": total_errors,
                "rules": rules,
            },
        )

        if confidence_score.overall_score >= rules["min_confidence"]:
            severity = self._determine_severity_level(error_logs)
            return PatternMatch(
                pattern_type=PatternType.SERVICE_DEGRADATION,
                confidence_score=confidence_score.overall_score,
                primary_service=service_name,
                affected_services=[service_name],
                severity_level=severity,
                evidence={
                    "error_concentration": service_error_ratio,
                    "error_count": len(error_logs),
                    "service_dominance": "high",
                },
                remediation_priority=(
                    "HIGH" if severity in ["HIGH", "CRITICAL"] else "MEDIUM"
                ),
                suggested_actions=[
                    f"Investigate {service_name} service health",
                    "Check service logs and metrics",
                    "Verify service dependencies",
                    "Consider service restart or rollback",
                ],
            )
        return None

    def _detect_traffic_spike(
        self, window: TimeWindow, threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        patterns = []
        rules = self.classification_rules["traffic_spike"]

        frequency_triggers = [
            r
            for r in threshold_results
            if (
                r.threshold_type == ThresholdType.ERROR_FREQUENCY
                and r.triggered
                and r.score >= rules["concurrent_error_threshold"]
            )
        ]

        if frequency_triggers:
            all_logs = []
            affected_services = set()

            for result in frequency_triggers:
                all_logs.extend(result.triggering_logs)
                affected_services.update(result.affected_services)

            time_concentration = self.confidence_scorer._calculate_time_concentration(
                all_logs, window
            )

            confidence_score = self.confidence_scorer.calculate_confidence(
                pattern_type=PatternType.TRAFFIC_SPIKE,
                window=window,
                logs=all_logs,
                additional_context={
                    "time_concentration": time_concentration,
                    "affected_services": list(affected_services),
                    "concurrent_error_count": len(all_logs),
                    "rules": rules,
                },
            )

            if confidence_score.overall_score >= rules["min_confidence"]:
                severity = self._determine_severity_level(all_logs)
                primary_service = self._identify_primary_service(all_logs)

                patterns.append(
                    PatternMatch(
                        pattern_type=PatternType.TRAFFIC_SPIKE,
                        confidence_score=confidence_score.overall_score,
                        primary_service=primary_service,
                        affected_services=list(affected_services),
                        severity_level=severity,
                        evidence={
                            "concurrent_errors": len(all_logs),
                            "time_concentration": time_concentration,
                            "spike_intensity": "high",
                        },
                        remediation_priority="HIGH",
                        suggested_actions=[
                            self.SCALE_UP_ACTION,
                            "Implement rate limiting",
                            "Check load balancer configuration",
                            "Monitor traffic patterns",
                        ],
                    )
                )

        return patterns

    def _detect_configuration_issue(
        self, window: TimeWindow, threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        patterns = []
        rules = self.classification_rules["configuration_issue"]

        config_logs, affected_services = self._filter_config_logs(
            threshold_results, rules
        )

        if config_logs:
            pattern = self._create_configuration_issue_pattern(
                config_logs, affected_services, window, threshold_results, rules
            )
            if pattern:
                patterns.append(pattern)

        return patterns

    def _filter_config_logs(
        self, threshold_results: List[ThresholdResult], rules: Dict[str, Any]
    ) -> tuple[List[LogEntry], set]:
        """Filter logs for configuration issue patterns."""
        config_logs = []
        affected_services = set()

        for result in threshold_results:
            if result.triggered:
                self._process_config_logs(
                    result.triggering_logs, rules, config_logs, affected_services
                )

        return config_logs, affected_services

    def _process_config_logs(
        self,
        logs: List[LogEntry],
        rules: Dict[str, Any],
        config_logs: List[LogEntry],
        affected_services: set,
    ) -> None:
        """Process individual logs for configuration keywords."""
        for log in logs:
            if self._is_config_error(log, rules):
                config_logs.append(log)
                if log.service_name:
                    affected_services.add(log.service_name)

    def _is_config_error(self, log: LogEntry, rules: Dict[str, Any]) -> bool:
        """Check if a log entry indicates a configuration issue."""
        if not log.error_message:
            return False
        return any(
            keyword in log.error_message.lower() for keyword in rules["config_keywords"]
        )

    def _create_configuration_issue_pattern(
        self,
        config_logs: List[LogEntry],
        affected_services: set,
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
        rules: Dict[str, Any],
    ) -> Optional[PatternMatch]:
        """Create a configuration issue pattern if confidence threshold is met."""
        rapid_onset = self.confidence_scorer._check_rapid_onset(
            config_logs, rules["rapid_onset_threshold_seconds"]
        )

        keyword_density = len(config_logs) / len(window.logs) if window.logs else 0

        confidence_score = self.confidence_scorer.calculate_confidence(
            pattern_type=PatternType.CONFIGURATION_ISSUE,
            window=window,
            logs=config_logs,
            additional_context={
                "keyword_density": keyword_density,
                "rapid_onset": rapid_onset,
                "affected_services": list(affected_services),
                "config_error_count": len(config_logs),
                "rules": rules,
            },
        )

        if confidence_score.overall_score >= rules["min_confidence"]:
            severity = self._determine_severity_level(config_logs)
            primary_service = self._identify_primary_service(config_logs)

            return PatternMatch(
                pattern_type=PatternType.CONFIGURATION_ISSUE,
                confidence_score=confidence_score.overall_score,
                primary_service=primary_service,
                affected_services=list(affected_services),
                severity_level=severity,
                evidence={
                    "config_error_count": len(config_logs),
                    "rapid_onset": rapid_onset,
                    "keyword_matches": rules["config_keywords"],
                },
                remediation_priority="HIGH",
                suggested_actions=[
                    "Review recent configuration changes",
                    "Validate configuration files",
                    "Check environment variables",
                    "Rollback recent config deployments",
                ],
            )
        return None

    def _detect_dependency_failure(
        self, window: TimeWindow, threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        patterns = []
        rules = self.classification_rules["dependency_failure"]

        dependency_logs, affected_services = self._filter_dependency_logs(
            threshold_results, rules
        )

        if dependency_logs:
            pattern = self._create_dependency_failure_pattern(
                dependency_logs, affected_services, window, threshold_results, rules
            )
            if pattern:
                patterns.append(pattern)

        return patterns

    def _filter_dependency_logs(
        self, threshold_results: List[ThresholdResult], rules: Dict[str, Any]
    ) -> tuple[List[LogEntry], set]:
        """Filter logs for dependency failure patterns."""
        dependency_logs = []
        affected_services = set()

        for result in threshold_results:
            if result.triggered:
                self._process_triggered_logs(
                    result.triggering_logs, rules, dependency_logs, affected_services
                )

        return dependency_logs, affected_services

    def _process_triggered_logs(
        self,
        logs: List[LogEntry],
        rules: Dict[str, Any],
        dependency_logs: List[LogEntry],
        affected_services: set,
    ) -> None:
        """Process individual logs for dependency keywords."""
        for log in logs:
            if self._is_dependency_error(log, rules):
                dependency_logs.append(log)
                if log.service_name:
                    affected_services.add(log.service_name)

    def _create_dependency_failure_pattern(
        self,
        dependency_logs: List[LogEntry],
        affected_services: set,
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
        rules: Dict[str, Any],
    ) -> Optional[PatternMatch]:
        """Create a dependency failure pattern if confidence threshold is met."""
        external_indicators = any(
            indicator in log.error_message.lower()
            for log in dependency_logs
            for indicator in rules["external_service_indicators"]
            if log.error_message
        )

        keyword_density = len(dependency_logs) / len(window.logs) if window.logs else 0

        confidence_score = self.confidence_scorer.calculate_confidence(
            pattern_type=PatternType.DEPENDENCY_FAILURE,
            window=window,
            logs=dependency_logs,
            additional_context={
                "keyword_density": keyword_density,
                "external_indicators": external_indicators,
                "affected_services": list(affected_services),
                "dependency_error_count": len(dependency_logs),
                "rules": rules,
            },
        )

        if confidence_score.overall_score >= rules["min_confidence"]:
            severity = self._determine_severity_level(dependency_logs)
            primary_service = self._identify_primary_service(dependency_logs)

            return PatternMatch(
                pattern_type=PatternType.DEPENDENCY_FAILURE,
                confidence_score=confidence_score.overall_score,
                primary_service=primary_service,
                affected_services=list(affected_services),
                severity_level=severity,
                evidence={
                    "dependency_error_count": len(dependency_logs),
                    "external_service": external_indicators,
                    "keyword_matches": rules["dependency_keywords"],
                },
                remediation_priority="HIGH",
                suggested_actions=[
                    "Check external service status",
                    "Verify network connectivity",
                    "Implement fallback mechanisms",
                    "Review timeout configurations",
                ],
            )
        return None

    def _detect_resource_exhaustion(
        self, window: TimeWindow, threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        patterns = []
        rules = self.classification_rules["resource_exhaustion"]

        resource_logs, affected_services = self._filter_resource_logs(
            threshold_results, rules
        )

        if resource_logs:
            pattern = self._create_resource_exhaustion_pattern(
                resource_logs, affected_services, window, threshold_results, rules
            )
            if pattern:
                patterns.append(pattern)

        return patterns

    def _filter_resource_logs(
        self, threshold_results: List[ThresholdResult], rules: Dict[str, Any]
    ) -> tuple[List[LogEntry], set]:
        """Filter logs for resource exhaustion patterns."""
        resource_logs = []
        affected_services = set()

        for result in threshold_results:
            if result.triggered:
                self._process_resource_logs(
                    result.triggering_logs, rules, resource_logs, affected_services
                )

        return resource_logs, affected_services

    def _process_resource_logs(
        self,
        logs: List[LogEntry],
        rules: Dict[str, Any],
        resource_logs: List[LogEntry],
        affected_services: set,
    ) -> None:
        """Process individual logs for resource keywords."""
        for log in logs:
            if self._is_resource_error(log, rules):
                resource_logs.append(log)
                if log.service_name:
                    affected_services.add(log.service_name)

    def _is_resource_error(self, log: LogEntry, rules: Dict[str, Any]) -> bool:
        """Check if a log entry indicates a resource exhaustion issue."""
        if not log.error_message:
            return False
        return any(
            keyword in log.error_message.lower()
            for keyword in rules["resource_keywords"]
        )

    def _create_resource_exhaustion_pattern(
        self,
        resource_logs: List[LogEntry],
        affected_services: set,
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
        rules: Dict[str, Any],
    ) -> Optional[PatternMatch]:
        """Create a resource exhaustion pattern if confidence threshold is met."""
        gradual_onset = self.confidence_scorer._check_gradual_onset(resource_logs)
        keyword_density = len(resource_logs) / len(window.logs) if window.logs else 0

        confidence_score = self.confidence_scorer.calculate_confidence(
            pattern_type=PatternType.RESOURCE_EXHAUSTION,
            window=window,
            logs=resource_logs,
            additional_context={
                "keyword_density": keyword_density,
                "gradual_onset": gradual_onset,
                "affected_services": list(affected_services),
                "resource_error_count": len(resource_logs),
                "rules": rules,
            },
        )

        if confidence_score.overall_score >= rules["min_confidence"]:
            severity = self._determine_severity_level(resource_logs)
            primary_service = self._identify_primary_service(resource_logs)

            return PatternMatch(
                pattern_type=PatternType.RESOURCE_EXHAUSTION,
                confidence_score=confidence_score.overall_score,
                primary_service=primary_service,
                affected_services=list(affected_services),
                severity_level=severity,
                evidence={
                    "resource_error_count": len(resource_logs),
                    "gradual_onset": gradual_onset,
                    "resource_types": rules["resource_keywords"],
                },
                remediation_priority="MEDIUM",
                suggested_actions=[
                    "Check resource utilization",
                    self.SCALE_UP_ACTION,
                    "Optimize resource usage",
                    "Review resource limits",
                ],
            )
        return None

    def _detect_sporadic_errors(
        self, window: TimeWindow, threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        patterns = []

        triggered_results = [r for r in threshold_results if r.triggered]
        if not triggered_results:
            return patterns

        all_logs = []
        affected_services = set()

        for result in triggered_results:
            all_logs.extend(result.triggering_logs)
            affected_services.update(result.affected_services)

        service_distribution = len(affected_services) / max(1, len(all_logs))
        time_distribution = self.confidence_scorer._calculate_time_concentration(
            all_logs, window
        )

        if service_distribution > 0.3 and time_distribution < 0.6:
            confidence_score = self.confidence_scorer.calculate_confidence(
                pattern_type=PatternType.SPORADIC_ERRORS,
                window=window,
                logs=all_logs,
                additional_context={
                    "service_distribution": service_distribution,
                    "time_distribution": time_distribution,
                    "affected_services": list(affected_services),
                    "error_count": len(all_logs),
                    "is_fallback_pattern": True,
                },
            )

            severity = self._determine_severity_level(all_logs)
            primary_service = self._identify_primary_service(all_logs)

            patterns.append(
                PatternMatch(
                    pattern_type=PatternType.SPORADIC_ERRORS,
                    confidence_score=confidence_score.overall_score,
                    primary_service=primary_service,
                    affected_services=list(affected_services),
                    severity_level=severity,
                    evidence={
                        "error_distribution": "dispersed",
                        "service_spread": len(affected_services),
                        "time_spread": 1 - time_distribution,
                    },
                    remediation_priority=(
                        "LOW" if severity in ["LOW", "MEDIUM"] else "MEDIUM"
                    ),
                    suggested_actions=[
                        "Monitor error trends",
                        "Investigate common root causes",
                        "Improve error handling",
                        "Check system stability",
                    ],
                )
            )

        return patterns

    def _identify_primary_service(self, logs: List[LogEntry]) -> Optional[str]:
        """Identifies the service with the most errors."""
        if not logs:
            return None
        service_counts = defaultdict(int)
        for log in logs:
            if log.service_name:
                service_counts[log.service_name] += 1
        if not service_counts:
            return None
        return max(service_counts.keys(), key=lambda x: service_counts[x])

    def _determine_severity_level(self, logs: List[LogEntry]) -> str:
        """Determines the overall severity level from a list of logs."""
        if not logs:
            return "LOW"
        severities = [log.severity for log in logs]
        if "CRITICAL" in severities:
            return "CRITICAL"
        if "ERROR" in severities:
            return "HIGH"
        if "WARNING" in severities:
            return "MEDIUM"
        return "LOW"

    def _is_dependency_error(self, log: LogEntry, rules: Dict[str, Any]) -> bool:
        """Check if a log entry indicates a dependency failure."""
        if not log.error_message:
            return False
        return any(
            keyword in log.error_message.lower()
            for keyword in rules["dependency_keywords"]
        )
