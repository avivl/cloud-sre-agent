"""
Historical pattern analysis for incident detection.

This module provides historical context analysis including baseline comparison,
trend analysis, and similar incident detection.
"""

from typing import Any, Dict, List

import numpy as np

from ..pattern_detector.models import TimeWindow


class HistoricalAnalyzer:
    """Analyze historical context and patterns."""

    async def analyze_historical_context(
        self, window: TimeWindow, historical_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze historical context and patterns."""
        return {
            "baseline_comparison": self._compare_to_baseline(window, historical_data),
            "trend_analysis": self._analyze_trends(historical_data),
            "similar_incidents": self._find_similar_incidents(window, historical_data),
            "recent_changes": self._extract_recent_changes(historical_data),
        }

    def _compare_to_baseline(
        self, window: TimeWindow, historical_data: Dict[str, Any]
    ) -> str:
        """Compare current window to historical baseline."""
        baseline_error_rate = historical_data.get("baseline_error_rate", 0)
        current_error_rate = len(window.logs) / max(window.duration_minutes, 1)

        if baseline_error_rate == 0:
            return "No baseline available"

        ratio = current_error_rate / baseline_error_rate

        if ratio > 5.0:
            return "Extreme deviation (>5x baseline)"
        if ratio > 2.0:
            return "High deviation (>2x baseline)"
        if ratio > 1.5:
            return "Moderate deviation (>1.5x baseline)"
        if ratio < 0.5:
            return "Below baseline activity"

        return "Within normal baseline range"

    def _analyze_trends(self, historical_data: Dict[str, Any]) -> str:
        """Analyze recent trend patterns."""
        trend_data = historical_data.get("recent_trend", [])

        if len(trend_data) < 3:
            return "Insufficient trend data"

        # Simple trend analysis
        recent_avg = np.mean(trend_data[-3:])
        older_avg = np.mean(trend_data[:-3]) if len(trend_data) > 3 else recent_avg

        if recent_avg > older_avg * 1.5:
            return "Increasing trend"
        if recent_avg < older_avg * 0.7:
            return "Decreasing trend"

        return "Stable trend"

    def _find_similar_incidents(
        self, window: TimeWindow, historical_data: Dict[str, Any]
    ) -> List[str]:
        """Find similar historical incidents."""
        # Simplified implementation - in production would use more sophisticated matching
        similar_incidents = historical_data.get("similar_incidents", [])
        return similar_incidents[:3]  # Return top 3 matches

    def _extract_recent_changes(self, historical_data: Dict[str, Any]) -> List[str]:
        """Extract recent system changes."""
        return historical_data.get("recent_changes", [])
