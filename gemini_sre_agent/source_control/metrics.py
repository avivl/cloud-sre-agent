# gemini_sre_agent/source_control/metrics.py

"""
Backward-compatible module for metrics.

This module ensures that existing imports of metrics classes continue to work
after the refactoring into a subpackage.
"""

from .metrics.analyzers import MetricsAnalyzer
from .metrics.collectors import MetricsCollector, OperationMetrics
from .metrics.core import MetricPoint, MetricSeries, MetricType

__all__ = [
    "MetricPoint",
    "MetricSeries",
    "MetricType",
    "MetricsAnalyzer",
    "MetricsCollector",
    "OperationMetrics",
]
