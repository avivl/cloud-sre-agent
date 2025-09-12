# gemini_sre_agent/pattern_detector/threshold_evaluator.py

"""
Threshold evaluation logic.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from .baseline_tracker import BaselineTracker
from .models import (
    LogEntry,
    ThresholdConfig,
    ThresholdResult,
    ThresholdType,
    TimeWindow,
)

logger = logging.getLogger(__name__)


class ThresholdEvaluator:
    """Evaluates time windows against configured smart thresholds."""

    def __init__(
        self,
        threshold_configs: List[ThresholdConfig],
        baseline_tracker: Optional[BaselineTracker] = None,
    ):
        self.threshold_configs = threshold_configs
        self.baseline_tracker = baseline_tracker or BaselineTracker()
        logger.info(
            f"[PATTERN_DETECTION] ThresholdEvaluator initialized with {len(threshold_configs)} thresholds"
        )

    def evaluate_window(self, window: TimeWindow) -> List[ThresholdResult]:
        """
        Evaluate Window.

        Args:
            window: TimeWindow: Description of window: TimeWindow.

        Returns:
            List[ThresholdResult]: Description of return value.

        """
        results = []
        for config in self.threshold_configs:
            try:
                result = self._evaluate_single_threshold(window, config)
                results.append(result)
                if result.triggered:
                    logger.info(
                        f"[PATTERN_DETECTION] Threshold triggered: type={result.threshold_type}, "
                        f"score={result.score:.2f}, services={len(result.affected_services)}, "
                        f"window={window.start_time}"
                    )
            except Exception as e:
                logger.error(
                    f"[ERROR_HANDLING] Error evaluating threshold {config.threshold_type}: {e}"
                )
        if self.baseline_tracker:
            self.baseline_tracker.update_baseline(window)
        return results

    def _evaluate_single_threshold(
        self, window: TimeWindow, config: ThresholdConfig
    ) -> ThresholdResult:
        if config.threshold_type == ThresholdType.ERROR_FREQUENCY:
            return self._evaluate_error_frequency(window, config)
        elif config.threshold_type == ThresholdType.ERROR_RATE:
            return self._evaluate_error_rate(window, config)
        elif config.threshold_type == ThresholdType.SERVICE_IMPACT:
            return self._evaluate_service_impact(window, config)
        elif config.threshold_type == ThresholdType.SEVERITY_WEIGHTED:
            return self._evaluate_severity_weighted(window, config)
        elif config.threshold_type == ThresholdType.CASCADE_FAILURE:
            return self._evaluate_cascade_failure(window, config)
        else:
            raise ValueError(f"Unknown threshold type: {config.threshold_type}")

    def _evaluate_error_frequency(
        self, window: TimeWindow, config: ThresholdConfig
    ) -> ThresholdResult:
        error_logs = window.get_error_logs()
        error_count = len(error_logs)
        triggered = error_count >= config.min_error_count
        service_groups = window.get_service_groups()
        affected_services = [
            service
            for service, logs in service_groups.items()
            if len(
                [
                    log
                    for log in logs
                    if log.severity in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]
                ]
            )
            > 0
        ]
        return ThresholdResult(
            threshold_type=config.threshold_type,
            triggered=triggered,
            score=float(error_count),
            details={
                "error_count": error_count,
                "total_logs": len(window.logs),
                "threshold": config.min_error_count,
            },
            triggering_logs=error_logs,
            affected_services=affected_services,
        )

    def _evaluate_error_rate(
        self, window: TimeWindow, config: ThresholdConfig
    ) -> ThresholdResult:
        error_logs = window.get_error_logs()
        total_logs = len(window.logs)
        current_rate = (len(error_logs) / total_logs * 100) if total_logs > 0 else 0.0
        baseline_rate = self.baseline_tracker.get_global_baseline(
            config.baseline_window_count
        )
        rate_increase = (
            current_rate - baseline_rate if baseline_rate > 0 else current_rate
        )
        rate_increase_percentage = (
            (rate_increase / baseline_rate * 100)
            if baseline_rate > 0
            else float("inf") if current_rate > 0 else 0.0
        )
        triggered = (
            rate_increase_percentage >= config.min_rate_increase and current_rate > 0
        )
        service_groups = window.get_service_groups()
        affected_services = [
            service
            for service, logs in service_groups.items()
            if len(
                [
                    log
                    for log in logs
                    if log.severity in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]
                ]
            )
            > 0
        ]
        return ThresholdResult(
            threshold_type=config.threshold_type,
            triggered=triggered,
            score=rate_increase_percentage,
            details={
                "current_rate": current_rate,
                "baseline_rate": baseline_rate,
                "rate_increase": rate_increase,
                "rate_increase_percentage": rate_increase_percentage,
                "threshold": config.min_rate_increase,
            },
            triggering_logs=error_logs,
            affected_services=affected_services,
        )

    def _evaluate_service_impact(
        self, window: TimeWindow, config: ThresholdConfig
    ) -> ThresholdResult:
        service_groups = window.get_service_groups()
        affected_services = []
        all_error_logs = []
        for service, logs in service_groups.items():
            service_errors = [
                log
                for log in logs
                if log.severity in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]
            ]
            if service_errors:
                affected_services.append(service)
                all_error_logs.extend(service_errors)
        triggered = len(affected_services) >= config.min_affected_services
        return ThresholdResult(
            threshold_type=config.threshold_type,
            triggered=triggered,
            score=float(len(affected_services)),
            details={
                "affected_services": len(affected_services),
                "total_services": len(service_groups),
                "threshold": config.min_affected_services,
            },
            triggering_logs=all_error_logs,
            affected_services=affected_services,
        )

    def _evaluate_severity_weighted(
        self, window: TimeWindow, config: ThresholdConfig
    ) -> ThresholdResult:
        weighted_score = 0.0
        triggering_logs = []
        for log in window.logs:
            weight = config.severity_weights.get(log.severity, 1.0)
            weighted_score += weight
            if weight >= 5.0:
                triggering_logs.append(log)
        triggered = weighted_score >= config.min_value
        service_groups = window.get_service_groups()
        affected_services = [
            service
            for service, logs in service_groups.items()
            if any(
                config.severity_weights.get(log.severity, 1.0) >= 5.0 for log in logs
            )
        ]
        return ThresholdResult(
            threshold_type=config.threshold_type,
            triggered=triggered,
            score=weighted_score,
            details={
                "weighted_score": weighted_score,
                "threshold": config.min_value,
                "severity_breakdown": self._get_severity_breakdown(
                    window.logs, config.severity_weights
                ),
            },
            triggering_logs=triggering_logs,
            affected_services=affected_services,
        )

    def _evaluate_cascade_failure(
        self, window: TimeWindow, config: ThresholdConfig
    ) -> ThresholdResult:
        service_groups = window.get_service_groups()
        services_with_errors = []
        all_error_logs = []
        for service, logs in service_groups.items():
            service_errors = [
                log
                for log in logs
                if log.severity in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]
            ]
            if service_errors:
                services_with_errors.append(service)
                all_error_logs.extend(service_errors)
        triggered = len(services_with_errors) >= config.cascade_min_services
        return ThresholdResult(
            threshold_type=config.threshold_type,
            triggered=triggered,
            score=float(len(services_with_errors)),
            details={
                "services_with_errors": len(services_with_errors),
                "total_services": len(service_groups),
                "threshold": config.cascade_min_services,
                "time_window_minutes": config.cascade_time_window_minutes,
            },
            triggering_logs=all_error_logs,
            affected_services=services_with_errors,
        )

    def _get_severity_breakdown(
        self, logs: List[LogEntry], severity_weights: Dict[str, float]
    ) -> Dict[str, int]:
        breakdown: Dict[str, int] = defaultdict(int)
        for log in logs:
            breakdown[log.severity] += 1
        return dict(breakdown)
