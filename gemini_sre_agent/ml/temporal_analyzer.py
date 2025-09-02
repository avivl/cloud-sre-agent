"""
Temporal pattern analysis for incident detection.

This module provides temporal analysis capabilities for error patterns,
including burst detection, acceleration analysis, and timing correlation.
"""

from datetime import datetime
from typing import Any, Dict, List

import numpy as np

from ..pattern_detector.models import TimeWindow


class TemporalAnalyzer:
    """Analyze temporal patterns in log data."""

    async def analyze_temporal_patterns(self, window: TimeWindow) -> Dict[str, Any]:
        """Analyze temporal characteristics of errors."""
        if not window.logs:
            return {"burst_pattern": "No errors", "distribution": "Empty window"}

        timestamps = sorted([log.timestamp for log in window.logs])

        # Calculate time differences
        intervals = []
        if len(timestamps) > 1:
            intervals = [
                (timestamps[i + 1] - timestamps[i]).total_seconds()
                for i in range(len(timestamps) - 1)
            ]

            # Analyze burst pattern
            burst_pattern = self._classify_burst_pattern(intervals, timestamps, window)

            # Analyze distribution
            distribution = self._analyze_time_distribution(timestamps, window)
        else:
            burst_pattern = "Single error event"
            distribution = "Point occurrence"

        return {
            "burst_pattern": burst_pattern,
            "distribution": distribution,
            "error_frequency": len(window.logs),
            "avg_interval": float(np.mean(intervals)) if len(timestamps) > 1 else 0.0,
        }

    def _classify_burst_pattern(
        self, intervals: List[float], timestamps: List[datetime], window: TimeWindow
    ) -> str:
        """Classify the burst pattern of errors."""
        if len(intervals) == 0:
            return "Single event"

        avg_interval = np.mean(intervals)
        std_interval = np.std(intervals)
        total_span = (timestamps[-1] - timestamps[0]).total_seconds()
        window_span = window.duration_minutes * 60

        # High frequency, short intervals
        if avg_interval < 10 and len(intervals) > 5:
            return "Rapid burst (high-frequency errors in tight clusters)"

        # Errors concentrated in small portion of window
        if total_span < (window_span * 0.3):
            return "Concentrated burst (errors clustered in time)"

        # Regular intervals
        if std_interval < (avg_interval * 0.3):
            return "Periodic pattern (regular interval errors)"

        # Increasing frequency over time
        if self._check_acceleration(intervals):
            return "Accelerating pattern (increasing error frequency)"

        # Scattered throughout window
        return "Distributed pattern (errors spread across time window)"

    def _check_acceleration(self, intervals: List[float]) -> bool:
        """Check if error intervals are decreasing (acceleration)."""
        if len(intervals) < 4:
            return False

        # Split into first half and second half
        mid = len(intervals) // 2
        first_half_avg = np.mean(intervals[:mid])
        second_half_avg = np.mean(intervals[mid:])

        # Acceleration means decreasing intervals (increasing frequency)
        return bool(second_half_avg < (first_half_avg * 0.7))

    def _analyze_time_distribution(
        self, timestamps: List[datetime], window: TimeWindow
    ) -> str:
        """Analyze the distribution of errors across the time window."""
        if len(timestamps) <= 1:
            return "Single event"

        window_span = window.duration_minutes * 60
        bucket_size = window_span / 4  # Divide into 4 quarters
        buckets = [0, 0, 0, 0]

        for ts in timestamps:
            elapsed = (ts - window.start_time).total_seconds()
            bucket_idx = min(int(elapsed / bucket_size), 3)
            buckets[bucket_idx] += 1

        # Analyze distribution pattern
        non_empty_buckets = sum(1 for count in buckets if count > 0)
        max_bucket_count = max(buckets)
        total_errors = sum(buckets)

        if non_empty_buckets == 1:
            return "Concentrated in single quarter"
        if max_bucket_count / total_errors > 0.7:
            return "Heavy concentration in one period"
        if non_empty_buckets >= 3:
            return "Distributed across multiple periods"

        return "Moderate distribution"

    def analyze_cross_service_timing(self, window: TimeWindow) -> Dict[str, Any]:
        """Analyze timing patterns across services."""
        service_timestamps = {}
        for log in window.logs:
            service = log.service_name or "unknown"
            if service not in service_timestamps:
                service_timestamps[service] = []
            service_timestamps[service].append(log.timestamp)

        if len(service_timestamps) <= 1:
            return {"pattern": "single_service", "correlation": 0.0}

        # Analyze temporal correlation between services
        services = list(service_timestamps.keys())
        if len(services) >= 2:
            # Simple correlation analysis between first two services
            service1_times = sorted(service_timestamps[services[0]])
            service2_times = sorted(service_timestamps[services[1]])

            # Calculate time proximity score
            correlation = self._calculate_timing_correlation(
                service1_times, service2_times
            )
            return {"pattern": "multi_service", "correlation": correlation}

        return {"pattern": "unknown", "correlation": 0.0}

    def _calculate_timing_correlation(
        self, times1: List[datetime], times2: List[datetime]
    ) -> float:
        """Calculate timing correlation between two service error sequences."""
        if not times1 or not times2:
            return 0.0

        # Find closest pairs and measure average distance
        total_distance = 0.0
        pairs = 0

        for t1 in times1:
            closest_distance = min(abs((t2 - t1).total_seconds()) for t2 in times2)
            if closest_distance <= 60:  # Within 1 minute considered correlated
                total_distance += closest_distance
                pairs += 1

        if pairs == 0:
            return 0.0

        avg_distance = total_distance / pairs
        # Convert to correlation score (closer = higher correlation)
        return max(0.0, 1.0 - (avg_distance / 60.0))
