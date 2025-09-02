"""
Log quality validation for ensuring reliable input data for AI processing.

This module provides comprehensive validation of log quality including
completeness, noise detection, consistency checking, and duplicate analysis.
"""

import logging
import re
from collections import defaultdict
from statistics import mean
from typing import Dict, List, Optional

from .validation_config import (
    LogEntry,
    QualityThresholds,
    TimeWindow,
    ValidationMetrics,
)


class LogQualityValidator:
    """
    Validate log quality before AI processing to ensure good input data.

    Analyzes logs for completeness, noise ratio, format consistency,
    and duplicate detection to determine overall quality score.
    """

    def __init__(self, thresholds: Optional[QualityThresholds] = None):
        """Initialize validator with quality thresholds."""
        self.thresholds = thresholds or QualityThresholds()
        self.logger = logging.getLogger(__name__)

        self.logger.info(
            "[LOG_QUALITY] Initialized with thresholds - "
            "completeness: %.2f, max_noise: %.2f, consistency: %.2f, max_duplicates: %.2f",
            self.thresholds.min_completeness,
            self.thresholds.max_noise_ratio,
            self.thresholds.min_consistency,
            self.thresholds.max_duplicate_ratio,
        )

    def assess_log_quality(self, window: TimeWindow) -> Dict[str, float]:
        """
        Assess quality of logs in time window.

        Args:
            window: Time window containing logs to analyze

        Returns:
            Dictionary containing quality metrics and overall assessment
        """
        logs = window.logs
        if not logs:
            return ValidationMetrics.empty_metrics()

        # Calculate individual quality metrics
        completeness = self._calculate_completeness(logs)
        noise_ratio = self._calculate_noise_ratio(logs)
        consistency = self._calculate_consistency(logs)
        duplicate_ratio = self._calculate_duplicate_ratio(logs)

        # Calculate overall quality score
        quality_factors = {
            "completeness": max(0.0, completeness),
            "low_noise": max(0.0, 1.0 - noise_ratio),
            "consistency": max(0.0, consistency),
            "low_duplicates": max(0.0, 1.0 - duplicate_ratio),
        }

        overall_quality = mean(quality_factors.values())

        quality_assessment = {
            "overall_quality": overall_quality,
            "completeness": completeness,
            "noise_ratio": noise_ratio,
            "consistency": consistency,
            "duplicate_ratio": duplicate_ratio,
            "passes_threshold": self._passes_quality_threshold(overall_quality),
            "quality_factors": quality_factors,
            "total_logs_analyzed": len(logs),
        }

        self.logger.debug(
            "[LOG_QUALITY] Assessment - Overall: %.3f, Complete: %.3f, "
            "Noise: %.3f, Consistent: %.3f, Duplicates: %.3f",
            overall_quality,
            completeness,
            noise_ratio,
            consistency,
            duplicate_ratio,
        )

        return quality_assessment

    def validate_for_processing(self, window: TimeWindow) -> bool:
        """
        Determine if logs meet minimum quality for AI processing.

        Args:
            window: Time window containing logs to validate

        Returns:
            True if logs meet quality thresholds, False otherwise
        """
        quality_metrics = self.assess_log_quality(window)

        # Check individual thresholds
        passes_completeness = (
            quality_metrics["completeness"] >= self.thresholds.min_completeness
        )
        passes_noise = quality_metrics["noise_ratio"] <= self.thresholds.max_noise_ratio
        passes_consistency = (
            quality_metrics["consistency"] >= self.thresholds.min_consistency
        )
        passes_duplicates = (
            quality_metrics["duplicate_ratio"] <= self.thresholds.max_duplicate_ratio
        )

        # Must pass all individual thresholds and overall quality
        validation_result = bool(
            passes_completeness
            and passes_noise
            and passes_consistency
            and passes_duplicates
            and quality_metrics["passes_threshold"]
        )

        if not validation_result:
            self.logger.warning(
                "[LOG_QUALITY] Validation failed - "
                "Completeness: %s (%.3f >= %.2f), "
                "Noise: %s (%.3f <= %.2f), "
                "Consistency: %s (%.3f >= %.2f), "
                "Duplicates: %s (%.3f <= %.2f), "
                "Overall: %s (%.3f)",
                "PASS" if passes_completeness else "FAIL",
                quality_metrics["completeness"],
                self.thresholds.min_completeness,
                "PASS" if passes_noise else "FAIL",
                quality_metrics["noise_ratio"],
                self.thresholds.max_noise_ratio,
                "PASS" if passes_consistency else "FAIL",
                quality_metrics["consistency"],
                self.thresholds.min_consistency,
                "PASS" if passes_duplicates else "FAIL",
                quality_metrics["duplicate_ratio"],
                self.thresholds.max_duplicate_ratio,
                "PASS" if quality_metrics["passes_threshold"] else "FAIL",
                quality_metrics["overall_quality"],
            )
        else:
            self.logger.info(
                "[LOG_QUALITY] Validation passed with quality score: %.3f",
                quality_metrics["overall_quality"],
            )

        return validation_result

    def get_quality_recommendations(
        self, quality_metrics: Dict[str, float]
    ) -> List[str]:
        """
        Generate recommendations to improve log quality.

        Args:
            quality_metrics: Quality assessment results

        Returns:
            List of actionable recommendations
        """
        recommendations = []

        if quality_metrics["completeness"] < self.thresholds.min_completeness:
            recommendations.append(
                f"Improve log completeness (current: {quality_metrics['completeness']:.2f}, "
                f"required: {self.thresholds.min_completeness:.2f}) - "
                "ensure service_name, error_message, and severity fields are populated"
            )

        if quality_metrics["noise_ratio"] > self.thresholds.max_noise_ratio:
            recommendations.append(
                f"Reduce noise ratio (current: {quality_metrics['noise_ratio']:.2f}, "
                f"max allowed: {self.thresholds.max_noise_ratio:.2f}) - "
                "filter out DEBUG/TRACE logs and very short messages"
            )

        if quality_metrics["consistency"] < self.thresholds.min_consistency:
            recommendations.append(
                f"Improve log consistency (current: {quality_metrics['consistency']:.2f}, "
                f"required: {self.thresholds.min_consistency:.2f}) - "
                "standardize log formats and message patterns"
            )

        if quality_metrics["duplicate_ratio"] > self.thresholds.max_duplicate_ratio:
            recommendations.append(
                f"Reduce duplicate messages (current: {quality_metrics['duplicate_ratio']:.2f}, "
                f"max allowed: {self.thresholds.max_duplicate_ratio:.2f}) - "
                "implement log deduplication or rate limiting"
            )

        if not recommendations:
            recommendations.append(
                "Log quality meets all thresholds - good for AI processing"
            )

        return recommendations

    def _calculate_completeness(self, logs: List[LogEntry]) -> float:
        """Calculate completeness score based on essential fields."""
        if not logs:
            return 0.0

        complete_logs = sum(
            1 for log in logs if log.service_name and log.error_message and log.severity
        )

        return complete_logs / len(logs)

    def _calculate_noise_ratio(self, logs: List[LogEntry]) -> float:
        """Calculate noise ratio from low-value logs."""
        if not logs:
            return 1.0

        noisy_logs = sum(1 for log in logs if self._is_noisy_log(log))

        return noisy_logs / len(logs)

    def _calculate_consistency(self, logs: List[LogEntry]) -> float:
        """Calculate consistency score based on message patterns."""
        if not logs:
            return 0.0

        message_patterns = defaultdict(int)

        for log in logs:
            if log.error_message:
                pattern = self._extract_message_pattern(log.error_message)
                message_patterns[pattern] += 1

        if not message_patterns:
            return 0.0

        # Consistency is based on pattern distribution
        max_pattern_count = max(message_patterns.values())
        return max_pattern_count / len(logs)

    def _calculate_duplicate_ratio(self, logs: List[LogEntry]) -> float:
        """Calculate ratio of duplicate messages."""
        if not logs:
            return 0.0

        message_counts = defaultdict(int)

        for log in logs:
            if log.error_message:
                message_counts[log.error_message] += 1

        # Count duplicate occurrences (beyond first occurrence)
        duplicate_messages = sum(
            count - 1 for count in message_counts.values() if count > 1
        )

        return duplicate_messages / len(logs) if len(logs) > 0 else 0.0

    def _is_noisy_log(self, log: LogEntry) -> bool:
        """Determine if a log entry is considered noisy."""
        # Very short messages
        if log.error_message and len(log.error_message.strip()) < 10:
            return True

        # Debug/trace level logs
        if log.severity and log.severity.upper() in ["DEBUG", "TRACE"]:
            return True

        # Empty or minimal content
        if not log.error_message or not log.error_message.strip():
            return True

        return False

    def _extract_message_pattern(self, message: str) -> str:
        """Extract pattern from log message by normalizing variables."""
        if not message:
            return ""

        # Replace UUIDs and hashes with placeholder (do this before numbers)
        pattern = re.sub(r"[a-f0-9]{8,}", "ID", message)

        # Replace numbers with placeholder
        pattern = re.sub(r"\d+", "N", pattern)

        # Replace IP addresses with placeholder
        pattern = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "IP", pattern)

        # Replace timestamps with placeholder
        pattern = re.sub(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", "TIMESTAMP", pattern
        )

        # Return first 50 characters as pattern key
        return pattern[:50].strip()

    def _passes_quality_threshold(self, overall_quality: float) -> bool:
        """Check if overall quality meets minimum threshold."""
        return overall_quality >= self.thresholds.overall_quality_threshold
