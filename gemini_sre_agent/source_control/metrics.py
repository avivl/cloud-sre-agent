"""
Backward-compatible module for metrics.

This module ensures that existing imports of metrics classes continue to work
after the refactoring into a subpackage.
"""

from .metrics.core import MetricType, MetricPoint, MetricSeries
from .metrics.collectors import MetricsCollector, OperationMetrics
from .metrics.analyzers import MetricsAnalyzer

__all__ = [
    "MetricType",
    "MetricPoint",
    "MetricSeries",
    "MetricsCollector",
    "OperationMetrics",
    "MetricsAnalyzer",
]
