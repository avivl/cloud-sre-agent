"""
Error pattern analysis for incident detection.

This module provides error analysis capabilities including error type
classification, message similarity analysis, and severity distribution.
"""

from typing import Any, Dict, List

import numpy as np

from ..pattern_detector.models import LogEntry, TimeWindow


class ErrorAnalyzer:
    """Analyze error patterns in log data."""

    async def analyze_error_patterns(self, window: TimeWindow) -> Dict[str, Any]:
        """Analyze error types and patterns."""
        error_types = {}
        severity_counts = {}
        messages = []

        for log in window.logs:
            # Extract error type
            error_type = self._extract_error_type(log)
            error_types[error_type] = error_types.get(error_type, 0) + 1

            # Extract severity
            severity = log.severity.lower() if log.severity else "unknown"
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            # Collect message samples
            if len(messages) < 5:
                messages.append(log.error_message or "")

        return {
            "error_types": error_types,
            "severity_distribution": severity_counts,
            "message_samples": messages,
            "similarity_score": self._calculate_message_similarity(messages),
        }

    def _extract_error_type(self, log: LogEntry) -> str:
        """Extract error type from log entry."""
        message = (log.error_message or "").lower()

        if "timeout" in message:
            return "timeout_error"
        if "connection" in message and ("refused" in message or "failed" in message):
            return "connection_error"
        if "500" in message or "internal server error" in message:
            return "internal_server_error"
        if "404" in message or "not found" in message:
            return "not_found_error"
        if "authentication" in message or "unauthorized" in message:
            return "auth_error"
        if "memory" in message or "out of memory" in message:
            return "memory_error"
        if "database" in message or "sql" in message:
            return "database_error"

        return "generic_error"

    def _calculate_message_similarity(self, messages: List[str]) -> float:
        """Calculate similarity score between error messages."""
        if len(messages) <= 1:
            return 1.0

        # Simple similarity based on common words
        word_sets = [set(msg.lower().split()) for msg in messages if msg]

        if not word_sets:
            return 0.0

        # Calculate average pairwise similarity
        similarities = []
        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                intersection = len(word_sets[i] & word_sets[j])
                union = len(word_sets[i] | word_sets[j])
                if union > 0:
                    similarities.append(intersection / union)

        return float(np.mean(similarities)) if similarities else 0.0
