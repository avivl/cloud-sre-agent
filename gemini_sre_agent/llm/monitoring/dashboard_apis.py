"""
Dashboard APIs for LLM Monitoring.

This module provides REST API endpoints for monitoring dashboards,
including metrics, health status, performance data, and cost analytics.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..cost_management_integration import IntegratedCostManager
from ..monitoring.health_checks import LLMHealthChecker
from ..monitoring.llm_metrics import get_llm_metrics_collector

logger = logging.getLogger(__name__)


class LLMDashboardAPI:
    """Dashboard API for LLM monitoring and observability."""

    def __init__(
        self,
        health_checker: LLMHealthChecker,
        cost_manager: Optional[IntegratedCostManager] = None,
    ):
        """Initialize the dashboard API."""
        self.health_checker = health_checker
        self.cost_manager = cost_manager
        self.metrics_collector = get_llm_metrics_collector()

        logger.info("LLMDashboardAPI initialized")

    def get_overview(self) -> Dict[str, Any]:
        """Get system overview for dashboard."""
        health_summary = self.health_checker.get_health_summary()
        metrics_summary = self.metrics_collector.get_metrics_summary()

        # Get cost summary if available
        cost_summary = {}
        if self.cost_manager:
            try:
                cost_summary = self.cost_manager.get_cost_analytics()
            except Exception as e:
                logger.warning(f"Failed to get cost summary: {e}")
                cost_summary = {"error": "Cost data unavailable"}

        return {
            "timestamp": datetime.now().isoformat(),
            "health": health_summary,
            "metrics": metrics_summary,
            "cost": cost_summary,
            "status": (
                "operational"
                if health_summary.get("overall_status") == "healthy"
                else "degraded"
            ),
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get detailed health status for all providers."""
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": self.health_checker.get_health_summary(),
            "providers": {
                provider: {
                    "status": health.status.value,
                    "last_check": health.last_check.isoformat(),
                    "check_count": health.check_count,
                    "success_count": health.success_count,
                    "failure_count": health.failure_count,
                    "success_rate": (
                        health.success_count / health.check_count
                        if health.check_count > 0
                        else 0
                    ),
                    "avg_response_time_ms": health.avg_response_time_ms,
                    "issues": health.issues,
                    "models": {
                        model: {
                            "status": result.status.value,
                            "message": result.message,
                            "duration_ms": result.duration_ms,
                            "timestamp": result.timestamp.isoformat(),
                            "error": result.error,
                        }
                        for model, result in health.models.items()
                    },
                }
                for provider, health in self.health_checker.get_all_provider_health().items()
            },
        }

    def get_metrics(
        self, provider: Optional[str] = None, model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get metrics data for dashboard."""
        if provider and model:
            # Get specific model metrics
            model_metrics = self.metrics_collector.get_model_metrics(provider, model)
            if not model_metrics:
                return {"error": f"No metrics found for {provider}:{model}"}

            return {
                "timestamp": datetime.now().isoformat(),
                "provider": provider,
                "model": model,
                "metrics": {
                    "total_requests": model_metrics.total_requests,
                    "successful_requests": model_metrics.successful_requests,
                    "failed_requests": model_metrics.failed_requests,
                    "success_rate": model_metrics.success_rate,
                    "total_cost": model_metrics.total_cost,
                    "total_tokens": model_metrics.total_tokens,
                    "avg_latency_ms": model_metrics.avg_latency_ms,
                    "quality_score": model_metrics.quality_score,
                    "last_updated": model_metrics.last_updated.isoformat(),
                },
            }
        elif provider:
            # Get provider metrics
            provider_metrics = self.metrics_collector.get_provider_metrics(provider)
            if not provider_metrics:
                return {"error": f"No metrics found for provider {provider}"}

            return {
                "timestamp": datetime.now().isoformat(),
                "provider": provider,
                "metrics": {
                    "total_requests": provider_metrics.total_requests,
                    "successful_requests": provider_metrics.successful_requests,
                    "failed_requests": provider_metrics.failed_requests,
                    "success_rate": provider_metrics.success_rate,
                    "error_rate": provider_metrics.error_rate,
                    "total_cost": provider_metrics.total_cost,
                    "total_tokens": provider_metrics.total_tokens,
                    "avg_latency_ms": provider_metrics.avg_latency_ms,
                    "p95_latency_ms": provider_metrics.p95_latency_ms,
                    "p99_latency_ms": provider_metrics.p99_latency_ms,
                    "circuit_breaker_trips": provider_metrics.circuit_breaker_trips,
                    "rate_limit_hits": provider_metrics.rate_limit_hits,
                    "last_updated": provider_metrics.last_updated.isoformat(),
                },
            }
        else:
            # Get all metrics
            return {
                "timestamp": datetime.now().isoformat(),
                "summary": self.metrics_collector.get_metrics_summary(),
                "providers": {
                    provider: {
                        "total_requests": pm.total_requests,
                        "success_rate": pm.success_rate,
                        "total_cost": pm.total_cost,
                        "avg_latency_ms": pm.avg_latency_ms,
                        "p95_latency_ms": pm.p95_latency_ms,
                        "p99_latency_ms": pm.p99_latency_ms,
                        "circuit_breaker_trips": pm.circuit_breaker_trips,
                        "rate_limit_hits": pm.rate_limit_hits,
                        "last_updated": pm.last_updated.isoformat(),
                    }
                    for provider, pm in self.metrics_collector.get_all_provider_metrics().items()
                },
                "models": {
                    model_key: {
                        "provider": mm.provider,
                        "model": mm.model,
                        "model_type": mm.model_type,
                        "total_requests": mm.total_requests,
                        "success_rate": mm.success_rate,
                        "total_cost": mm.total_cost,
                        "avg_latency_ms": mm.avg_latency_ms,
                        "quality_score": mm.quality_score,
                        "last_updated": mm.last_updated.isoformat(),
                    }
                    for model_key, mm in self.metrics_collector.get_all_model_metrics().items()
                },
            }

    def get_performance_data(
        self, provider: Optional[str] = None, hours: int = 24
    ) -> Dict[str, Any]:
        """Get performance data for charts and graphs."""
        # This would typically query time-series data
        # For now, we'll return current metrics with some mock historical data

        if provider:
            provider_metrics = self.metrics_collector.get_provider_metrics(provider)
            if not provider_metrics:
                return {"error": f"No performance data found for provider {provider}"}

            # Get throughput metrics
            throughput = self.metrics_collector.get_throughput_metrics(
                provider, window_minutes=60
            )

            return {
                "timestamp": datetime.now().isoformat(),
                "provider": provider,
                "time_range_hours": hours,
                "current_metrics": {
                    "avg_latency_ms": provider_metrics.avg_latency_ms,
                    "p95_latency_ms": provider_metrics.p95_latency_ms,
                    "p99_latency_ms": provider_metrics.p99_latency_ms,
                    "success_rate": provider_metrics.success_rate,
                    "requests_per_minute": throughput.get("requests_per_minute", 0),
                    "requests_per_second": throughput.get("requests_per_second", 0),
                },
                "historical_data": self._generate_mock_historical_data(provider, hours),
            }
        else:
            # Get performance data for all providers
            all_providers = self.metrics_collector.get_all_provider_metrics()
            performance_data = {}

            for provider_name in all_providers.keys():
                throughput = self.metrics_collector.get_throughput_metrics(
                    provider_name, window_minutes=60
                )
                performance_data[provider_name] = {
                    "current_metrics": {
                        "avg_latency_ms": all_providers[provider_name].avg_latency_ms,
                        "p95_latency_ms": all_providers[provider_name].p95_latency_ms,
                        "p99_latency_ms": all_providers[provider_name].p99_latency_ms,
                        "success_rate": all_providers[provider_name].success_rate,
                        "requests_per_minute": throughput.get("requests_per_minute", 0),
                        "requests_per_second": throughput.get("requests_per_second", 0),
                    },
                    "historical_data": self._generate_mock_historical_data(
                        provider_name, hours
                    ),
                }

            return {
                "timestamp": datetime.now().isoformat(),
                "time_range_hours": hours,
                "providers": performance_data,
            }

    def get_cost_analytics(
        self, provider: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """Get cost analytics data."""
        if not self.cost_manager:
            return {"error": "Cost management not available"}

        try:
            if provider:
                # Get cost data for specific provider
                # This would typically query cost data by provider
                return {
                    "timestamp": datetime.now().isoformat(),
                    "provider": provider,
                    "time_range_days": days,
                    "cost_data": self._get_provider_cost_data(provider, days),
                }
            else:
                # Get overall cost analytics
                analytics = self.cost_manager.get_cost_analytics()
                return {
                    "timestamp": datetime.now().isoformat(),
                    "time_range_days": days,
                    "analytics": analytics,
                }
        except Exception as e:
            logger.error(f"Error getting cost analytics: {e}")
            return {"error": f"Failed to get cost analytics: {str(e)}"}

    def get_alerts(self) -> Dict[str, Any]:
        """Get current alerts and issues."""
        alerts = []

        # Check for unhealthy providers
        unhealthy_providers = self.health_checker.get_unhealthy_providers()
        for provider in unhealthy_providers:
            issues = self.health_checker.get_provider_issues(provider)
            alerts.append(
                {
                    "type": "health",
                    "severity": "critical",
                    "provider": provider,
                    "message": f"Provider {provider} is unhealthy",
                    "details": issues,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Check for degraded providers
        degraded_providers = self.health_checker.get_degraded_providers()
        for provider in degraded_providers:
            issues = self.health_checker.get_provider_issues(provider)
            alerts.append(
                {
                    "type": "health",
                    "severity": "warning",
                    "provider": provider,
                    "message": f"Provider {provider} is degraded",
                    "details": issues,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Check for high error rates
        for (
            provider,
            metrics,
        ) in self.metrics_collector.get_all_provider_metrics().items():
            if metrics.error_rate > 0.1:  # 10% error rate threshold
                alerts.append(
                    {
                        "type": "performance",
                        "severity": "warning",
                        "provider": provider,
                        "message": f"High error rate: {metrics.error_rate:.1%}",
                        "details": {"error_rate": metrics.error_rate},
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # Check for circuit breaker trips
            if metrics.circuit_breaker_trips > 0:
                alerts.append(
                    {
                        "type": "reliability",
                        "severity": "critical",
                        "provider": provider,
                        "message": f"Circuit breaker tripped {metrics.circuit_breaker_trips} times",
                        "details": {"trips": metrics.circuit_breaker_trips},
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        return {
            "timestamp": datetime.now().isoformat(),
            "total_alerts": len(alerts),
            "critical_alerts": len([a for a in alerts if a["severity"] == "critical"]),
            "warning_alerts": len([a for a in alerts if a["severity"] == "warning"]),
            "alerts": alerts,
        }

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        health_summary = self.health_checker.get_health_summary()
        metrics_summary = self.metrics_collector.get_metrics_summary()
        alerts = self.get_alerts()

        # Determine overall system status
        if (
            health_summary.get("overall_status") == "healthy"
            and alerts["critical_alerts"] == 0
        ):
            system_status = "operational"
        elif (
            health_summary.get("overall_status") == "degraded"
            or alerts["critical_alerts"] > 0
        ):
            system_status = "degraded"
        else:
            system_status = "unhealthy"

        return {
            "timestamp": datetime.now().isoformat(),
            "status": system_status,
            "health": health_summary,
            "metrics": {
                "total_requests": metrics_summary.get("total_requests", 0),
                "overall_success_rate": metrics_summary.get("overall_success_rate", 0),
                "average_latency_ms": metrics_summary.get("average_latency_ms", 0),
                "total_cost": metrics_summary.get("total_cost", 0),
            },
            "alerts": {
                "total": alerts["total_alerts"],
                "critical": alerts["critical_alerts"],
                "warnings": alerts["warning_alerts"],
            },
        }

    def _generate_mock_historical_data(
        self, provider: str, hours: int
    ) -> List[Dict[str, Any]]:
        """Generate mock historical data for charts."""
        # In a real implementation, this would query time-series data
        data_points = []
        current_time = datetime.now()

        for i in range(hours):
            timestamp = current_time - timedelta(hours=i)
            data_points.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "requests_per_minute": 10 + (i % 5) * 2,  # Mock data
                    "avg_latency_ms": 100 + (i % 3) * 50,
                    "success_rate": 0.95 + (i % 2) * 0.03,
                    "error_rate": 0.02 + (i % 2) * 0.01,
                }
            )

        return list(reversed(data_points))  # Return in chronological order

    def _get_provider_cost_data(self, provider: str, days: int) -> Dict[str, Any]:
        """Get cost data for a specific provider."""
        # In a real implementation, this would query cost data
        return {
            "total_cost": 150.75,
            "daily_average": 5.02,
            "cost_trend": "stable",
            "breakdown": {"input_tokens": 120.50, "output_tokens": 30.25},
        }
