"""
Pattern matching logic for the pattern detection system.

This module provides specialized pattern matchers for different types of
log patterns and error conditions. Each matcher is responsible for
identifying specific patterns within log data and generating appropriate
PatternMatch objects.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Set

from ..logger import setup_logging
from .models import (
    LogEntry,
    PatternMatch,
    PatternType,
    ThresholdResult,
    TimeWindow,
)


@dataclass
class PatternMatcherConfig:
    """Configuration for pattern matchers."""
    
    min_confidence: float = 0.3
    keywords: Optional[List[str]] = None
    min_services: int = 2
    min_error_rate: float = 0.05
    single_service_threshold: float = 0.8
    volume_increase_threshold: float = 2.0
    concurrent_error_threshold: int = 10
    rapid_onset_threshold_seconds: int = 60
    external_service_indicators: Optional[List[str]] = None
    gradual_onset_indicators: Optional[List[str]] = None
    
    def __post_init__(self):
        """Set default values for optional fields."""
        if self.keywords is None:
            self.keywords = []
        if self.external_service_indicators is None:
            self.external_service_indicators = []
        if self.gradual_onset_indicators is None:
            self.gradual_onset_indicators = []


class PatternMatcher(Protocol):
    """Protocol for pattern matchers."""
    
    def match_patterns(
        self, 
        window: TimeWindow, 
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Match patterns in the given time window and threshold results."""
        ...


class BasePatternMatcher(ABC):
    """Base class for pattern matchers."""
    
    def __init__(self, config: PatternMatcherConfig, confidence_scorer=None):
        self.config = config
        self.confidence_scorer = confidence_scorer
        self.logger = setup_logging()
    
    @abstractmethod
    def match_patterns(
        self, 
        window: TimeWindow, 
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Match patterns in the given time window and threshold results."""
        pass
    
    def _determine_severity_level(self, logs: List[LogEntry]) -> str:
        """Determine the overall severity level from a list of logs."""
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
    
    def _identify_primary_service(self, logs: List[LogEntry]) -> Optional[str]:
        """Identify the service with the most errors."""
        if not logs:
            return None
        service_counts = defaultdict(int)
        for log in logs:
            if log.service_name:
                service_counts[log.service_name] += 1
        if not service_counts:
            return None
        return max(service_counts.keys(), key=lambda x: service_counts[x])
    
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


class CascadeFailureMatcher(BasePatternMatcher):
    """Pattern matcher for cascade failure detection."""
    
    def match_patterns(
        self, 
        window: TimeWindow, 
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect cascade failure patterns."""
        patterns = []
        
        cascade_triggers = [
            r for r in threshold_results
            if r.threshold_type == "cascade_failure" and r.triggered
        ]
        
        service_impact_triggers = [
            r for r in threshold_results
            if r.threshold_type == "service_impact" and r.triggered
        ]
        
        if cascade_triggers or (
            service_impact_triggers
            and any(
                len(r.affected_services) >= self.config.min_services
                for r in service_impact_triggers
            )
        ):
            all_affected_services = set()
            all_triggering_logs = []
            
            for result in threshold_results:
                if result.triggered:
                    all_affected_services.update(result.affected_services)
                    all_triggering_logs.extend(result.triggering_logs)
            
            if self.confidence_scorer:
                confidence_score = self.confidence_scorer.calculate_confidence(
                    pattern_type=PatternType.CASCADE_FAILURE,
                    window=window,
                    logs=all_triggering_logs,
                    additional_context={
                        "affected_services": list(all_affected_services),
                        "service_count": len(all_affected_services),
                        "rules": self.config.__dict__,
                    },
                )
                
                if confidence_score.overall_score >= self.config.min_confidence:
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
                                "Scale up affected services",
                            ],
                        )
                    )
        
        return patterns


class ServiceDegradationMatcher(BasePatternMatcher):
    """Pattern matcher for service degradation detection."""
    
    def match_patterns(
        self, 
        window: TimeWindow, 
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect service degradation patterns."""
        patterns = []
        service_errors = self._group_service_errors(threshold_results)
        
        for service_name, error_logs in service_errors.items():
            if self._should_create_service_pattern(error_logs, service_errors):
                pattern = self._create_service_degradation_pattern(
                    service_name, error_logs, window, service_errors
                )
                if pattern:
                    patterns.append(pattern)
        
        return patterns
    
    def _should_create_service_pattern(
        self,
        error_logs: List[LogEntry],
        service_errors: Dict[str, List[LogEntry]],
    ) -> bool:
        """Check if a service degradation pattern should be created."""
        total_errors = sum(len(logs) for logs in service_errors.values())
        if total_errors == 0:
            return False
        service_error_ratio = len(error_logs) / total_errors
        return service_error_ratio >= self.config.single_service_threshold
    
    def _create_service_degradation_pattern(
        self,
        service_name: str,
        error_logs: List[LogEntry],
        window: TimeWindow,
        service_errors: Dict[str, List[LogEntry]],
    ) -> Optional[PatternMatch]:
        """Create a service degradation pattern if confidence threshold is met."""
        total_errors = sum(len(logs) for logs in service_errors.values())
        service_error_ratio = len(error_logs) / total_errors if total_errors > 0 else 0
        
        if self.confidence_scorer:
            confidence_score = self.confidence_scorer.calculate_confidence(
                pattern_type=PatternType.SERVICE_DEGRADATION,
                window=window,
                logs=error_logs,
                additional_context={
                    "service_name": service_name,
                    "service_error_ratio": service_error_ratio,
                    "total_errors": total_errors,
                    "rules": self.config.__dict__,
                },
            )
            
            if confidence_score.overall_score >= self.config.min_confidence:
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


class TrafficSpikeMatcher(BasePatternMatcher):
    """Pattern matcher for traffic spike detection."""
    
    def match_patterns(
        self, 
        window: TimeWindow, 
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect traffic spike patterns."""
        patterns = []
        
        frequency_triggers = [
            r for r in threshold_results
            if (
                r.threshold_type == "error_frequency"
                and r.triggered
                and r.score >= self.config.concurrent_error_threshold
            )
        ]
        
        if frequency_triggers:
            all_logs = []
            affected_services = set()
            
            for result in frequency_triggers:
                all_logs.extend(result.triggering_logs)
                affected_services.update(result.affected_services)
            
            if self.confidence_scorer:
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
                        "rules": self.config.__dict__,
                    },
                )
                
                if confidence_score.overall_score >= self.config.min_confidence:
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
                                "Scale up affected services",
                                "Implement rate limiting",
                                "Check load balancer configuration",
                                "Monitor traffic patterns",
                            ],
                        )
                    )
        
        return patterns


class ConfigurationIssueMatcher(BasePatternMatcher):
    """Pattern matcher for configuration issue detection."""
    
    def match_patterns(
        self, 
        window: TimeWindow, 
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect configuration issue patterns."""
        patterns = []
        config_logs, affected_services = self._filter_config_logs(threshold_results)
        
        if config_logs:
            pattern = self._create_configuration_issue_pattern(
                config_logs, affected_services, window, threshold_results
            )
            if pattern:
                patterns.append(pattern)
        
        return patterns
    
    def _filter_config_logs(
        self, threshold_results: List[ThresholdResult]
    ) -> tuple[List[LogEntry], Set[str]]:
        """Filter logs for configuration issue patterns."""
        config_logs = []
        affected_services = set()
        
        for result in threshold_results:
            if result.triggered:
                self._process_config_logs(
                    result.triggering_logs, config_logs, affected_services
                )
        
        return config_logs, affected_services
    
    def _process_config_logs(
        self,
        logs: List[LogEntry],
        config_logs: List[LogEntry],
        affected_services: Set[str],
    ) -> None:
        """Process individual logs for configuration keywords."""
        for log in logs:
            if self._is_config_error(log):
                config_logs.append(log)
                if log.service_name:
                    affected_services.add(log.service_name)
    
    def _is_config_error(self, log: LogEntry) -> bool:
        """Check if a log entry indicates a configuration issue."""
        if not log.error_message or not self.config.keywords:
            return False
        return any(
            keyword in log.error_message.lower() 
            for keyword in self.config.keywords
        )
    
    def _create_configuration_issue_pattern(
        self,
        config_logs: List[LogEntry],
        affected_services: Set[str],
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
    ) -> Optional[PatternMatch]:
        """Create a configuration issue pattern if confidence threshold is met."""
        if self.confidence_scorer:
            rapid_onset = self.confidence_scorer._check_rapid_onset(
                config_logs, self.config.rapid_onset_threshold_seconds
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
                    "rules": self.config.__dict__,
                },
            )
            
            if confidence_score.overall_score >= self.config.min_confidence:
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
                        "keyword_matches": self.config.keywords,
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


class DependencyFailureMatcher(BasePatternMatcher):
    """Pattern matcher for dependency failure detection."""
    
    def match_patterns(
        self, 
        window: TimeWindow, 
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect dependency failure patterns."""
        patterns = []
        dependency_logs, affected_services = self._filter_dependency_logs(threshold_results)
        
        if dependency_logs:
            pattern = self._create_dependency_failure_pattern(
                dependency_logs, affected_services, window, threshold_results
            )
            if pattern:
                patterns.append(pattern)
        
        return patterns
    
    def _filter_dependency_logs(
        self, threshold_results: List[ThresholdResult]
    ) -> tuple[List[LogEntry], Set[str]]:
        """Filter logs for dependency failure patterns."""
        dependency_logs = []
        affected_services = set()
        
        for result in threshold_results:
            if result.triggered:
                self._process_dependency_logs(
                    result.triggering_logs, dependency_logs, affected_services
                )
        
        return dependency_logs, affected_services
    
    def _process_dependency_logs(
        self,
        logs: List[LogEntry],
        dependency_logs: List[LogEntry],
        affected_services: Set[str],
    ) -> None:
        """Process individual logs for dependency keywords."""
        for log in logs:
            if self._is_dependency_error(log):
                dependency_logs.append(log)
                if log.service_name:
                    affected_services.add(log.service_name)
    
    def _is_dependency_error(self, log: LogEntry) -> bool:
        """Check if a log entry indicates a dependency failure."""
        if not log.error_message or not self.config.keywords:
            return False
        return any(
            keyword in log.error_message.lower()
            for keyword in self.config.keywords
        )
    
    def _create_dependency_failure_pattern(
        self,
        dependency_logs: List[LogEntry],
        affected_services: Set[str],
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
    ) -> Optional[PatternMatch]:
        """Create a dependency failure pattern if confidence threshold is met."""
        if self.confidence_scorer:
            external_indicators = any(
                indicator in log.error_message.lower()
                for log in dependency_logs
                for indicator in (self.config.external_service_indicators or [])
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
                    "rules": self.config.__dict__,
                },
            )
            
            if confidence_score.overall_score >= self.config.min_confidence:
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
                        "keyword_matches": self.config.keywords,
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


class ResourceExhaustionMatcher(BasePatternMatcher):
    """Pattern matcher for resource exhaustion detection."""
    
    def match_patterns(
        self, 
        window: TimeWindow, 
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect resource exhaustion patterns."""
        patterns = []
        resource_logs, affected_services = self._filter_resource_logs(threshold_results)
        
        if resource_logs:
            pattern = self._create_resource_exhaustion_pattern(
                resource_logs, affected_services, window, threshold_results
            )
            if pattern:
                patterns.append(pattern)
        
        return patterns
    
    def _filter_resource_logs(
        self, threshold_results: List[ThresholdResult]
    ) -> tuple[List[LogEntry], Set[str]]:
        """Filter logs for resource exhaustion patterns."""
        resource_logs = []
        affected_services = set()
        
        for result in threshold_results:
            if result.triggered:
                self._process_resource_logs(
                    result.triggering_logs, resource_logs, affected_services
                )
        
        return resource_logs, affected_services
    
    def _process_resource_logs(
        self,
        logs: List[LogEntry],
        resource_logs: List[LogEntry],
        affected_services: Set[str],
    ) -> None:
        """Process individual logs for resource keywords."""
        for log in logs:
            if self._is_resource_error(log):
                resource_logs.append(log)
                if log.service_name:
                    affected_services.add(log.service_name)
    
    def _is_resource_error(self, log: LogEntry) -> bool:
        """Check if a log entry indicates a resource exhaustion issue."""
        if not log.error_message or not self.config.keywords:
            return False
        return any(
            keyword in log.error_message.lower()
            for keyword in self.config.keywords
        )
    
    def _create_resource_exhaustion_pattern(
        self,
        resource_logs: List[LogEntry],
        affected_services: Set[str],
        window: TimeWindow,
        threshold_results: List[ThresholdResult],
    ) -> Optional[PatternMatch]:
        """Create a resource exhaustion pattern if confidence threshold is met."""
        if self.confidence_scorer:
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
                    "rules": self.config.__dict__,
                },
            )
            
            if confidence_score.overall_score >= self.config.min_confidence:
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
                        "resource_types": self.config.keywords,
                    },
                    remediation_priority="MEDIUM",
                    suggested_actions=[
                        "Check resource utilization",
                        "Scale up affected services",
                        "Optimize resource usage",
                        "Review resource limits",
                    ],
                )
        return None


class SporadicErrorsMatcher(BasePatternMatcher):
    """Pattern matcher for sporadic error detection."""
    
    def match_patterns(
        self, 
        window: TimeWindow, 
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect sporadic error patterns."""
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
        
        if self.confidence_scorer:
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


class PatternMatcherFactory:
    """Factory for creating pattern matchers."""
    
    @staticmethod
    def create_matcher(
        pattern_type: str, 
        config: PatternMatcherConfig, 
        confidence_scorer=None
    ) -> PatternMatcher:
        """Create a pattern matcher for the specified pattern type."""
        matchers = {
            "cascade_failure": CascadeFailureMatcher,
            "service_degradation": ServiceDegradationMatcher,
            "traffic_spike": TrafficSpikeMatcher,
            "configuration_issue": ConfigurationIssueMatcher,
            "dependency_failure": DependencyFailureMatcher,
            "resource_exhaustion": ResourceExhaustionMatcher,
            "sporadic_errors": SporadicErrorsMatcher,
        }
        
        matcher_class = matchers.get(pattern_type)
        if not matcher_class:
            raise ValueError(f"Unknown pattern type: {pattern_type}")
        
        return matcher_class(config, confidence_scorer)
    
    @staticmethod
    def create_all_matchers(
        configs: Dict[str, PatternMatcherConfig], 
        confidence_scorer=None
    ) -> Dict[str, PatternMatcher]:
        """Create all pattern matchers with their respective configurations."""
        matchers = {}
        for pattern_type, config in configs.items():
            matchers[pattern_type] = PatternMatcherFactory.create_matcher(
                pattern_type, config, confidence_scorer
            )
        return matchers
