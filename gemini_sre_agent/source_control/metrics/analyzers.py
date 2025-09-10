"""
Metrics analysis and insights.

This module provides analysis capabilities for metrics data including
performance trends, anomaly detection, and recommendations.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from .collectors import MetricsCollector


class MetricsAnalyzer:
    """Analyzes metrics to provide insights and recommendations."""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.logger = logging.getLogger("MetricsAnalyzer")

    async def analyze_performance_trends(
        self, provider_name: str, window_minutes: int = 60
    ) -> Dict[str, Any]:
        """Analyze performance trends for a provider."""
        analysis = {
            "provider": provider_name,
            "window_minutes": window_minutes,
            "timestamp": datetime.now().isoformat(),
            "trends": {},
        }

        # Analyze operation duration trends
        duration_stats = await self.collector.get_metric_statistics(
            "operation_duration", {"provider": provider_name}, window_minutes
        )

        if duration_stats["count"] > 0:
            analysis["trends"]["operation_duration"] = {
                "current_avg_ms": duration_stats["mean"],
                "p95_ms": duration_stats["p95"],
                "p99_ms": duration_stats["p99"],
                "total_operations": duration_stats["count"],
            }

        # Analyze success rate trends
        success_rate = await self.collector.get_metric_value(
            "operation_success_rate", {"provider": provider_name}
        )
        if success_rate is not None:
            analysis["trends"]["success_rate"] = {
                "current_rate": success_rate,
                "status": (
                    "healthy"
                    if success_rate > 0.95
                    else "degraded" if success_rate > 0.8 else "unhealthy"
                ),
            }

        return analysis

    async def detect_anomalies(
        self, provider_name: str, window_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in provider metrics."""
        anomalies = []

        # Check for high error rates
        error_stats = await self.collector.get_metric_statistics(
            "operation_errors", {"provider": provider_name}, window_minutes
        )
        total_ops = await self.collector.get_metric_statistics(
            "operation_complete", {"provider": provider_name}, window_minutes
        )

        if total_ops["count"] > 0 and error_stats["count"] / total_ops["count"] > 0.1:
            anomalies.append(
                {
                    "type": "high_error_rate",
                    "severity": "warning",
                    "message": f"High error rate: {error_stats['count']}/{total_ops['count']} operations failed",
                    "value": error_stats["count"] / total_ops["count"],
                    "threshold": 0.1,
                }
            )

        # Check for slow operations
        duration_stats = await self.collector.get_metric_statistics(
            "operation_duration", {"provider": provider_name}, window_minutes
        )

        if duration_stats["count"] > 0 and duration_stats["p95"] > 5000:
            anomalies.append(
                {
                    "type": "slow_operations",
                    "severity": "warning",
                    "message": f"Slow operations detected: P95 duration is {duration_stats['p95']:.0f}ms",
                    "value": duration_stats["p95"],
                    "threshold": 5000,
                }
            )

        return anomalies

    async def generate_recommendations(
        self, provider_name: str, window_minutes: int = 60
    ) -> List[str]:
        """Generate recommendations based on metrics analysis."""
        recommendations = []

        # Analyze performance
        trends = await self.analyze_performance_trends(provider_name, window_minutes)

        if "operation_duration" in trends["trends"]:
            avg_duration = trends["trends"]["operation_duration"]["current_avg_ms"]
            if avg_duration > 2000:
                recommendations.append(
                    f"Consider optimizing operations - average duration is {avg_duration:.0f}ms"
                )

        if "success_rate" in trends["trends"]:
            success_rate = trends["trends"]["success_rate"]["current_rate"]
            if success_rate < 0.9:
                recommendations.append(
                    f"Investigate error causes - success rate is {success_rate:.1%}"
                )

        # Check for anomalies
        anomalies = await self.detect_anomalies(provider_name, window_minutes)
        for anomaly in anomalies:
            if anomaly["type"] == "high_error_rate":
                recommendations.append(
                    "Review error logs and consider implementing retry logic"
                )
            elif anomaly["type"] == "slow_operations":
                recommendations.append(
                    "Consider implementing caching or optimizing slow operations"
                )

        return recommendations
