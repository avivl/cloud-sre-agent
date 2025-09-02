"""
Advanced confidence scoring system.
"""

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..logger import setup_logging
from .models import (
    ConfidenceFactors,
    ConfidenceRule,
    ConfidenceScore,
    LogEntry,
    PatternType,
    TimeWindow,
)


class ConfidenceScorer:
    """Advanced confidence scoring engine for pattern detection."""

    def __init__(
        self, confidence_rules: Optional[Dict[str, List[ConfidenceRule]]] = None
    ):
        self.logger = setup_logging()
        self.confidence_rules = confidence_rules or self._get_default_confidence_rules()
        self.logger.info("[CONFIDENCE_SCORING] ConfidenceScorer initialized")

    def calculate_confidence(
        self,
        pattern_type: str,
        window: TimeWindow,
        logs: List[LogEntry],
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceScore:
        context = additional_context or {}
        rules = self.confidence_rules.get(pattern_type, [])
        raw_factors = self._calculate_raw_factors(window, logs, context)
        factor_scores = {}
        weighted_sum = 0.0
        total_weight = 0.0

        for rule in rules:
            if rule.factor_type in raw_factors:
                raw_value = raw_factors[rule.factor_type]
                if rule.threshold is not None and raw_value < rule.threshold:
                    factor_scores[rule.factor_type] = 0.0
                    continue
                processed_value = self._apply_decay_function(raw_value, rule)
                capped_value = min(processed_value, rule.max_contribution)
                weighted_contribution = capped_value * rule.weight
                factor_scores[rule.factor_type] = weighted_contribution
                weighted_sum += weighted_contribution
                total_weight += rule.weight

        overall_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0
        overall_score = max(0.0, min(1.0, overall_score))
        confidence_level = self._determine_confidence_level(overall_score)
        explanation = self._generate_explanation(
            pattern_type, factor_scores, raw_factors
        )

        return ConfidenceScore(
            overall_score=overall_score,
            factor_scores=factor_scores,
            raw_factors=raw_factors,
            confidence_level=confidence_level,
            explanation=explanation,
        )

    def _calculate_raw_factors(
        self,
        window: TimeWindow,
        logs: List[LogEntry],
        context: Dict[str, Any],
    ) -> Dict[str, float]:
        factors = {}
        factors[ConfidenceFactors.TIME_CONCENTRATION] = (
            self._calculate_time_concentration(logs, window)
        )
        factors[ConfidenceFactors.TIME_CORRELATION] = self._calculate_time_correlation(
            logs
        )
        factors[ConfidenceFactors.RAPID_ONSET] = (
            1.0 if self._check_rapid_onset(logs, 60) else 0.0
        )
        factors[ConfidenceFactors.GRADUAL_ONSET] = (
            1.0 if self._check_gradual_onset(logs) else 0.0
        )
        services = list({log.service_name for log in logs if log.service_name})
        factors[ConfidenceFactors.SERVICE_COUNT] = min(1.0, len(services) / 5.0)
        factors[ConfidenceFactors.SERVICE_DISTRIBUTION] = (
            self._calculate_service_distribution(logs)
        )
        factors[ConfidenceFactors.CROSS_SERVICE_CORRELATION] = (
            self._calculate_cross_service_correlation(logs)
        )
        factors[ConfidenceFactors.ERROR_FREQUENCY] = min(1.0, len(logs) / 20.0)
        factors[ConfidenceFactors.ERROR_SEVERITY] = self._calculate_severity_factor(
            logs
        )
        factors[ConfidenceFactors.ERROR_TYPE_CONSISTENCY] = (
            self._calculate_error_consistency(logs)
        )
        factors[ConfidenceFactors.MESSAGE_SIMILARITY] = (
            self._calculate_message_similarity(logs)
        )
        factors[ConfidenceFactors.BASELINE_DEVIATION] = context.get(
            "baseline_deviation", 0.5
        )
        factors[ConfidenceFactors.TREND_ANALYSIS] = context.get("trend_score", 0.5)
        factors[ConfidenceFactors.SEASONAL_PATTERN] = context.get("seasonal_score", 0.5)
        factors[ConfidenceFactors.DEPENDENCY_STATUS] = context.get(
            "dependency_health", 0.8
        )
        factors[ConfidenceFactors.RESOURCE_UTILIZATION] = context.get(
            "resource_pressure", 0.3
        )
        factors[ConfidenceFactors.DEPLOYMENT_CORRELATION] = context.get(
            "recent_deployment", 0.0
        )
        return factors

    def _calculate_time_concentration(
        self, logs: List[LogEntry], window: TimeWindow
    ) -> float:
        if not logs or len(logs) < 2:
            return 0.0
        timestamps = sorted([log.timestamp for log in logs])
        error_span = (timestamps[-1] - timestamps[0]).total_seconds()
        window_span = window.duration_minutes * 60
        return 1.0 - (error_span / window_span) if window_span > 0 else 1.0

    def _calculate_time_correlation(self, logs: List[LogEntry]) -> float:
        if len(logs) < 2:
            return 0.0
        timestamps = sorted([log.timestamp for log in logs])
        total_span = (timestamps[-1] - timestamps[0]).total_seconds()
        if total_span == 0:
            return 1.0
        return max(0.0, 1.0 - (total_span / 120.0))

    def _calculate_service_distribution(self, logs: List[LogEntry]) -> float:
        if not logs:
            return 0.0
        service_counts = {}
        for log in logs:
            if log.service_name:
                service_counts[log.service_name] = (
                    service_counts.get(log.service_name, 0) + 1
                )
        if len(service_counts) <= 1:
            return 0.0
        counts = list(service_counts.values())
        mean_count = sum(counts) / len(counts)
        if mean_count == 0:
            return 0.0
        variance = sum((count - mean_count) ** 2 for count in counts) / len(counts)
        cv = (variance**0.5) / mean_count
        return max(0.0, 1.0 - cv)

    def _calculate_cross_service_correlation(self, logs: List[LogEntry]) -> float:
        if not logs:
            return 0.0
        service_timestamps = self._group_logs_by_service(logs)
        if len(service_timestamps) < 2:
            return 0.0

        return self._calculate_service_correlations(service_timestamps)

    def _group_logs_by_service(self, logs: List[LogEntry]) -> Dict[str, List[datetime]]:
        """Group log timestamps by service name."""
        service_timestamps = {}
        for log in logs:
            if log.service_name:
                if log.service_name not in service_timestamps:
                    service_timestamps[log.service_name] = []
                service_timestamps[log.service_name].append(log.timestamp)
        return service_timestamps

    def _calculate_service_correlations(
        self, service_timestamps: Dict[str, List[datetime]]
    ) -> float:
        """Calculate cross-service correlation scores."""
        services = list(service_timestamps.keys())
        total_correlations = 0
        correlation_sum = 0.0

        for i in range(len(services)):
            for j in range(i + 1, len(services)):
                correlation = self._calculate_pair_correlation(
                    service_timestamps[services[i]], service_timestamps[services[j]]
                )
                correlation_sum += correlation
                total_correlations += 1

        return correlation_sum / total_correlations if total_correlations > 0 else 0.0

    def _calculate_pair_correlation(
        self, times_a: List[datetime], times_b: List[datetime]
    ) -> float:
        """Calculate correlation between two service timestamp lists."""
        correlation = 0.0
        for time_a in times_a:
            for time_b in times_b:
                if abs((time_a - time_b).total_seconds()) <= 30:
                    correlation += 1

        if times_a and times_b:
            return correlation / (len(times_a) * len(times_b))
        return 0.0

    def _calculate_severity_factor(self, logs: List[LogEntry]) -> float:
        if not logs:
            return 0.0
        severity_weights = {
            "CRITICAL": 1.0,
            "ERROR": 0.8,
            "WARNING": 0.4,
            "INFO": 0.1,
            "DEBUG": 0.05,
        }
        total_weight = 0.0
        for log in logs:
            severity = log.severity.upper() if log.severity else "INFO"
            total_weight += severity_weights.get(severity, 0.5)
        return min(1.0, total_weight / len(logs))

    def _calculate_error_consistency(self, logs: List[LogEntry]) -> float:
        if not logs:
            return 0.0
        severities = [log.severity for log in logs if log.severity]
        if not severities:
            return 0.0
        severity_counts = {}
        for severity in severities:
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        most_common_count = max(severity_counts.values())
        return most_common_count / len(severities)

    def _calculate_message_similarity(self, logs: List[LogEntry]) -> float:
        if not logs:
            return 0.0
        messages = [log.error_message for log in logs if log.error_message]
        if len(messages) < 2:
            return 0.0
        all_words = set()
        message_words = []
        for message in messages:
            words = set(message.lower().split())
            message_words.append(words)
            all_words.update(words)
        if not all_words:
            return 0.0
        similarities = []
        for i in range(len(message_words)):
            for j in range(i + 1, len(message_words)):
                intersection = len(message_words[i] & message_words[j])
                union = len(message_words[i] | message_words[j])
                if union > 0:
                    similarities.append(intersection / union)
        return sum(similarities) / len(similarities) if similarities else 0.0

    def _check_rapid_onset(self, logs: List[LogEntry], threshold_seconds: int) -> bool:
        if not logs:
            return False
        timestamps = sorted([log.timestamp for log in logs])
        time_span = (timestamps[-1] - timestamps[0]).total_seconds()
        return time_span <= threshold_seconds

    def _check_gradual_onset(self, logs: List[LogEntry]) -> bool:
        if len(logs) < 3:
            return False
        sorted_logs = sorted(logs, key=lambda x: x.timestamp)
        total_time = (
            sorted_logs[-1].timestamp - sorted_logs[0].timestamp
        ).total_seconds()
        if total_time < 60:
            return False
        bucket_size = total_time / 3
        buckets = [0, 0, 0]
        for log in sorted_logs:
            elapsed = (log.timestamp - sorted_logs[0].timestamp).total_seconds()
            bucket_idx = min(2, int(elapsed / bucket_size))
            buckets[bucket_idx] += 1
        return buckets[2] > buckets[1] and buckets[1] >= buckets[0]

    def _apply_decay_function(self, value: float, rule: ConfidenceRule) -> float:
        if not rule.decay_function:
            return value
        if rule.decay_function == "linear":
            slope = rule.parameters.get("slope", 1.0)
            return max(0.0, value * slope)
        elif rule.decay_function == "exponential":
            decay_rate = rule.parameters.get("decay_rate", 1.0)
            return value * math.exp(-decay_rate * (1.0 - value))
        elif rule.decay_function == "logarithmic":
            base = rule.parameters.get("base", math.e)
            return math.log(1 + value) / math.log(1 + base)
        return value

    def _determine_confidence_level(self, score: float) -> str:
        if score >= 0.9:
            return "VERY_HIGH"
        elif score >= 0.75:
            return "HIGH"
        elif score >= 0.5:
            return "MEDIUM"
        elif score >= 0.25:
            return "LOW"
        else:
            return "VERY_LOW"

    def _generate_explanation(
        self,
        pattern_type: str,
        factor_scores: Dict[str, float],
        raw_factors: Dict[str, float],
    ) -> List[str]:
        explanations = []
        sorted_factors = sorted(factor_scores.items(), key=lambda x: x[1], reverse=True)
        explanations.append(f"Confidence assessment for {pattern_type} pattern:")
        top_factors = sorted_factors[:3]
        for factor_type, score in top_factors:
            if score > 0.1:
                raw_value = raw_factors.get(factor_type, 0.0)
                explanations.append(
                    f"- {factor_type}: {score:.2f} (raw: {raw_value:.2f})"
                )
        if factor_scores.get(ConfidenceFactors.RAPID_ONSET, 0) > 0:
            explanations.append("- Rapid error onset detected (high confidence)")
        if factor_scores.get(ConfidenceFactors.CROSS_SERVICE_CORRELATION, 0) > 0.5:
            explanations.append("- Strong cross-service error correlation")
        if factor_scores.get(ConfidenceFactors.MESSAGE_SIMILARITY, 0) > 0.7:
            explanations.append("- High similarity in error messages")
        return explanations

    def _get_default_confidence_rules(self) -> Dict[str, List[ConfidenceRule]]:
        return {
            PatternType.CASCADE_FAILURE: [
                ConfidenceRule(ConfidenceFactors.SERVICE_COUNT, 0.3, threshold=2.0),
                ConfidenceRule(ConfidenceFactors.CROSS_SERVICE_CORRELATION, 0.25),
                ConfidenceRule(ConfidenceFactors.TIME_CONCENTRATION, 0.2),
                ConfidenceRule(ConfidenceFactors.RAPID_ONSET, 0.15),
                ConfidenceRule(ConfidenceFactors.ERROR_SEVERITY, 0.1),
            ],
            PatternType.SERVICE_DEGRADATION: [
                ConfidenceRule(ConfidenceFactors.ERROR_FREQUENCY, 0.3),
                ConfidenceRule(ConfidenceFactors.BASELINE_DEVIATION, 0.25),
                ConfidenceRule(ConfidenceFactors.TREND_ANALYSIS, 0.2),
                ConfidenceRule(ConfidenceFactors.ERROR_TYPE_CONSISTENCY, 0.15),
                ConfidenceRule(ConfidenceFactors.GRADUAL_ONSET, 0.1),
            ],
            PatternType.TRAFFIC_SPIKE: [
                ConfidenceRule(ConfidenceFactors.ERROR_FREQUENCY, 0.35),
                ConfidenceRule(ConfidenceFactors.TIME_CONCENTRATION, 0.25),
                ConfidenceRule(ConfidenceFactors.RAPID_ONSET, 0.2),
                ConfidenceRule(ConfidenceFactors.RESOURCE_UTILIZATION, 0.2),
            ],
            PatternType.CONFIGURATION_ISSUE: [
                ConfidenceRule(ConfidenceFactors.MESSAGE_SIMILARITY, 0.3),
                ConfidenceRule(ConfidenceFactors.DEPLOYMENT_CORRELATION, 0.25),
                ConfidenceRule(ConfidenceFactors.ERROR_TYPE_CONSISTENCY, 0.2),
                ConfidenceRule(ConfidenceFactors.RAPID_ONSET, 0.15),
                ConfidenceRule(ConfidenceFactors.SERVICE_DISTRIBUTION, 0.1),
            ],
            PatternType.DEPENDENCY_FAILURE: [
                ConfidenceRule(ConfidenceFactors.DEPENDENCY_STATUS, 0.3),
                ConfidenceRule(ConfidenceFactors.MESSAGE_SIMILARITY, 0.25),
                ConfidenceRule(ConfidenceFactors.CROSS_SERVICE_CORRELATION, 0.2),
                ConfidenceRule(ConfidenceFactors.ERROR_TYPE_CONSISTENCY, 0.15),
                ConfidenceRule(ConfidenceFactors.RAPID_ONSET, 0.1),
            ],
            PatternType.RESOURCE_EXHAUSTION: [
                ConfidenceRule(ConfidenceFactors.RESOURCE_UTILIZATION, 0.35),
                ConfidenceRule(ConfidenceFactors.GRADUAL_ONSET, 0.25),
                ConfidenceRule(ConfidenceFactors.ERROR_FREQUENCY, 0.2),
                ConfidenceRule(ConfidenceFactors.MESSAGE_SIMILARITY, 0.2),
            ],
            PatternType.SPORADIC_ERRORS: [
                ConfidenceRule(ConfidenceFactors.SERVICE_DISTRIBUTION, 0.3),
                ConfidenceRule(
                    ConfidenceFactors.TIME_CORRELATION, 0.25, decay_function="linear"
                ),
                ConfidenceRule(
                    ConfidenceFactors.ERROR_TYPE_CONSISTENCY,
                    0.2,
                    decay_function="linear",
                ),
                ConfidenceRule(
                    ConfidenceFactors.MESSAGE_SIMILARITY, 0.15, decay_function="linear"
                ),
                ConfidenceRule(ConfidenceFactors.BASELINE_DEVIATION, 0.1),
            ],
        }
