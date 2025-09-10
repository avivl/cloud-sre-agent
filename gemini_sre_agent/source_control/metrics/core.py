"""
Core metrics data structures and types.

This module defines the fundamental data structures for metrics collection,
including metric types, points, and series.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class MetricType(Enum):
    """Types of metrics that can be collected."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"


@dataclass
class MetricPoint:
    """A single metric measurement point."""

    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    unit: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """A series of metric points over time."""

    name: str
    metric_type: MetricType
    points: deque = field(default_factory=lambda: deque(maxlen=1000))
    tags: Dict[str, str] = field(default_factory=dict)
    unit: Optional[str] = None

    def add_point(
        self,
        value: float,
        timestamp: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Add a point to the series."""
        point = MetricPoint(
            name=self.name,
            value=value,
            metric_type=self.metric_type,
            timestamp=timestamp,
            tags=self.tags.copy(),
            unit=self.unit,
            metadata=metadata or {},
        )
        self.points.append(point)

    def get_latest(self) -> Optional[MetricPoint]:
        """Get the latest point in the series."""
        return self.points[-1] if self.points else None

    def get_range(self, start_time: datetime, end_time: datetime) -> List[MetricPoint]:
        """Get points within a time range."""
        return [
            point for point in self.points if start_time <= point.timestamp <= end_time
        ]

    def get_statistics(self, window_minutes: int = 60) -> Dict[str, float]:
        """Get statistics for the series over a time window."""
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_points = [p for p in self.points if p.timestamp >= cutoff_time]

        if not recent_points:
            return {"count": 0, "min": 0, "max": 0, "mean": 0, "sum": 0}

        values = [p.value for p in recent_points]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "sum": sum(values),
            "std_dev": self._calculate_std_dev(values),
            "p50": self._percentile(values, 50),
            "p95": self._percentile(values, 95),
            "p99": self._percentile(values, 99),
        }

    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance**0.5

    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]
