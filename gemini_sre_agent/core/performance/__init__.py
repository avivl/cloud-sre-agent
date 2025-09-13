"""Performance monitoring system for the Gemini SRE Agent.

This module provides comprehensive performance tracking and optimization including:
- Core performance metrics collection
- Asyncio profiling and async operation monitoring
- Performance alerting and threshold management
- Performance dashboards and visualization
- Performance optimization recommendations

The main components are:
- MetricsCollector: Core metrics collection and aggregation
- PerformanceProfiler: Asyncio and async operation profiling
- PerformanceAlerts: Alerting and threshold management
- PerformanceDashboard: Visualization and reporting
- OptimizationEngine: Performance optimization recommendations

Example usage:
    from gemini_sre_agent.core.performance import MetricsCollector, PerformanceProfiler

    # Create metrics collector
    collector = MetricsCollector()
    
    # Track performance
    with collector.track_operation("api_call"):
        result = await api_call()
    
    # Profile async operations
    profiler = PerformanceProfiler()
    with profiler.profile_async_operation("data_processing"):
        await process_data()
"""

from .alerts import AlertConfig, AlertRule, AlertSeverity, AlertThreshold, PerformanceAlerts
from .dashboard import (
    DashboardConfig,
    DashboardWidget,
    PerformanceDashboard,
    PerformanceVisualization,
)
from .metrics import (
    MetricAggregation,
    MetricsCollector,
    MetricsConfig,
    MetricType,
    MetricValue,
    PerformanceMetrics,
)
from .optimization import (
    OptimizationConfig,
    OptimizationEngine,
    OptimizationRecommendation,
    PerformanceAnalyzer,
)
from .profiler import (
    AsyncProfiler,
    OperationProfile,
    PerformanceProfiler,
    ProfilerConfig,
    ProfilerResult,
)

__all__ = [
    # Metrics
    "MetricsCollector",
    "MetricType",
    "MetricValue",
    "MetricAggregation",
    "PerformanceMetrics",
    "MetricsConfig",

    # Profiler
    "PerformanceProfiler",
    "AsyncProfiler",
    "ProfilerConfig",
    "ProfilerResult",
    "OperationProfile",

    # Alerts
    "PerformanceAlerts",
    "AlertThreshold",
    "AlertRule",
    "AlertSeverity",
    "AlertConfig",

    # Dashboard
    "PerformanceDashboard",
    "DashboardConfig",
    "DashboardWidget",
    "PerformanceVisualization",

    # Optimization
    "OptimizationEngine",
    "OptimizationRecommendation",
    "PerformanceAnalyzer",
    "OptimizationConfig",
]
