# gemini_sre_agent/source_control/error_handling/monitoring_dashboard.py

"""
Monitoring dashboard for error handling metrics and health status.

This module provides a comprehensive monitoring interface for tracking
error handling performance, circuit breaker states, and system health.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .advanced_circuit_breaker import AdvancedCircuitBreaker
from .custom_fallback_strategies import CustomFallbackManager
from .error_recovery_automation import SelfHealingManager
from .metrics_integration import ErrorHandlingMetrics


class MonitoringDashboard:
    """Comprehensive monitoring dashboard for error handling system."""

    def __init__(self, metrics: Optional[ErrorHandlingMetrics] = None):
        self.metrics = metrics
        self.logger = logging.getLogger("MonitoringDashboard")
        self.circuit_breakers: Dict[str, AdvancedCircuitBreaker] = {}
        self.fallback_manager: Optional[CustomFallbackManager] = None
        self.self_healing_manager: Optional[SelfHealingManager] = None
        self.dashboard_data: Dict[str, Any] = {}
        self.last_update: Optional[datetime] = None

    def register_circuit_breaker(
        self, name: str, circuit_breaker: AdvancedCircuitBreaker
    ) -> None:
        """Register a circuit breaker for monitoring."""
        self.circuit_breakers[name] = circuit_breaker
        self.logger.info(f"Registered circuit breaker: {name}")

    def register_fallback_manager(
        self, fallback_manager: CustomFallbackManager
    ) -> None:
        """Register fallback manager for monitoring."""
        self.fallback_manager = fallback_manager
        self.logger.info("Registered fallback manager")

    def register_self_healing_manager(
        self, self_healing_manager: SelfHealingManager
    ) -> None:
        """Register self-healing manager for monitoring."""
        self.self_healing_manager = self_healing_manager
        self.logger.info("Registered self-healing manager")

    async def refresh_dashboard_data(self) -> None:
        """Refresh all dashboard data."""
        self.logger.info("Refreshing dashboard data")

        # Circuit breaker data
        circuit_breaker_data = {}
        for name, cb in self.circuit_breakers.items():
            circuit_breaker_data[name] = {
                "stats": cb.get_advanced_stats(),
                "health": cb.get_health_status(),
            }

        # Fallback manager data
        fallback_data = {}
        if self.fallback_manager:
            fallback_data = self.fallback_manager.get_strategy_stats()

        # Self-healing data
        self_healing_data = {}
        if self.self_healing_manager:
            self_healing_data = {
                "stats": self.self_healing_manager.get_recovery_stats(),
                "health": self.self_healing_manager.get_health_status(),
            }

        # Overall system health
        system_health = await self._calculate_system_health(
            circuit_breaker_data, fallback_data, self_healing_data
        )

        # Metrics data
        metrics_data = {}
        if self.metrics:
            metrics_data = await self._get_metrics_summary()

        self.dashboard_data = {
            "timestamp": datetime.now().isoformat(),
            "system_health": system_health,
            "circuit_breakers": circuit_breaker_data,
            "fallback_strategies": fallback_data,
            "self_healing": self_healing_data,
            "metrics": metrics_data,
        }

        self.last_update = datetime.now()
        self.logger.info("Dashboard data refreshed successfully")

    async def _calculate_system_health(
        self,
        circuit_breaker_data: Dict[str, Any],
        fallback_data: Dict[str, Any],
        self_healing_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate overall system health score."""
        health_scores = []
        issues = []
        recommendations = []

        # Circuit breaker health
        for name, data in circuit_breaker_data.items():
            health = data["health"]
            health_scores.append(health["health_score"])
            issues.extend([f"{name}: {issue}" for issue in health.get("issues", [])])
            recommendations.extend(health.get("recommendations", []))

        # Self-healing health
        if self_healing_data and "health" in self_healing_data:
            health = self_healing_data["health"]
            health_scores.append(health["health_score"])
            issues.extend(health.get("issues", []))

        # Calculate overall health score
        if health_scores:
            overall_score = sum(health_scores) / len(health_scores)
        else:
            overall_score = 100

        # Determine status
        if overall_score > 80:
            status = "healthy"
        elif overall_score > 50:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "overall_score": overall_score,
            "status": status,
            "issues": issues,
            "recommendations": recommendations,
            "component_count": len(circuit_breaker_data),
        }

    async def _get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of metrics data."""
        if not self.metrics:
            return {}

        # This would typically query the metrics system
        # For now, return a placeholder structure
        return {
            "total_operations": 0,
            "success_rate": 0.0,
            "average_response_time": 0.0,
            "error_rate": 0.0,
            "circuit_breaker_opens": 0,
            "fallback_executions": 0,
        }

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get a summary of the current dashboard state."""
        if not self.dashboard_data:
            return {"status": "no_data", "message": "Dashboard data not available"}

        system_health = self.dashboard_data.get("system_health", {})

        return {
            "status": system_health.get("status", "unknown"),
            "health_score": system_health.get("overall_score", 0),
            "issues_count": len(system_health.get("issues", [])),
            "recommendations_count": len(system_health.get("recommendations", [])),
            "circuit_breakers": len(self.dashboard_data.get("circuit_breakers", {})),
            "last_update": self.dashboard_data.get("timestamp"),
        }

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get status of all circuit breakers."""
        if not self.dashboard_data:
            return {}

        circuit_breakers = self.dashboard_data.get("circuit_breakers", {})
        status = {}

        for name, data in circuit_breakers.items():
            stats = data.get("stats", {})
            health = data.get("health", {})

            status[name] = {
                "state": stats.get("state", "unknown"),
                "health_score": health.get("health_score", 0),
                "failure_rate": stats.get("failure_rate", 0),
                "total_requests": stats.get("total_requests", 0),
                "issues": health.get("issues", []),
            }

        return status

    def get_fallback_strategy_status(self) -> Dict[str, Any]:
        """Get status of fallback strategies."""
        if not self.dashboard_data:
            return {}

        return self.dashboard_data.get("fallback_strategies", {})

    def get_self_healing_status(self) -> Dict[str, Any]:
        """Get status of self-healing system."""
        if not self.dashboard_data:
            return {}

        return self.dashboard_data.get("self_healing", {})

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        if not self.dashboard_data:
            return {}

        return self.dashboard_data.get("metrics", {})

    def get_alerts(self) -> List[Dict[str, Any]]:
        """Get current alerts based on dashboard data."""
        alerts = []

        if not self.dashboard_data:
            return alerts

        # System health alerts
        system_health = self.dashboard_data.get("system_health", {})
        if system_health.get("status") == "unhealthy":
            alerts.append(
                {
                    "type": "critical",
                    "message": "System health is critical",
                    "component": "system",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Circuit breaker alerts
        circuit_breakers = self.dashboard_data.get("circuit_breakers", {})
        for name, data in circuit_breakers.items():
            stats = data.get("stats", {})
            health = data.get("health", {})

            if stats.get("state") == "open":
                alerts.append(
                    {
                        "type": "warning",
                        "message": f"Circuit breaker {name} is open",
                        "component": f"circuit_breaker.{name}",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            if health.get("health_score", 0) < 50:
                alerts.append(
                    {
                        "type": "warning",
                        "message": f"Circuit breaker {name} health is degraded",
                        "component": f"circuit_breaker.{name}",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        # Self-healing alerts
        self_healing = self.dashboard_data.get("self_healing", {})
        if self_healing:
            health = self_healing.get("health", {})
            if health.get("health_score", 0) < 50:
                alerts.append(
                    {
                        "type": "info",
                        "message": "Self-healing system health is degraded",
                        "component": "self_healing",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        return alerts

    def export_dashboard_data(self, format: str = "json") -> str:
        """Export dashboard data in specified format."""
        if format == "json":
            return json.dumps(self.dashboard_data, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def get_health_trend(self, hours: int = 24) -> Dict[str, Any]:
        """Get health trend over specified hours."""
        # This would typically query historical data
        # For now, return a placeholder structure
        return {
            "time_range": f"last_{hours}_hours",
            "data_points": [],
            "trend": "stable",
            "message": "Historical data not available",
        }

    async def start_monitoring(self, refresh_interval: int = 30) -> None:
        """Start continuous monitoring with specified refresh interval."""
        self.logger.info(
            f"Starting monitoring with {refresh_interval}s refresh interval"
        )

        while True:
            try:
                await self.refresh_dashboard_data()
                await asyncio.sleep(refresh_interval)
            except asyncio.CancelledError:
                self.logger.info("Monitoring stopped")
                break
            except Exception as e:
                self.logger.error(f"Error during monitoring: {e}")
                await asyncio.sleep(refresh_interval)

    def get_dashboard_html(self) -> str:
        """Generate HTML dashboard for web interface."""
        if not self.dashboard_data:
            return "<html><body><h1>Dashboard data not available</h1></body></html>"

        system_health = self.dashboard_data.get("system_health", {})
        circuit_breakers = self.dashboard_data.get("circuit_breakers", {})
        alerts = self.get_alerts()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error Handling Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .status {{ font-size: 24px; font-weight: bold; }}
                .healthy {{ color: green; }}
                .degraded {{ color: orange; }}
                .unhealthy {{ color: red; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .alert {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; margin: 5px 0; border-radius: 3px; }}
                .critical {{ background: #f8d7da; border-color: #f5c6cb; }}
                .warning {{ background: #fff3cd; border-color: #ffeaa7; }}
                .info {{ background: #d1ecf1; border-color: #bee5eb; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Error Handling Dashboard</h1>
                <div class="status {system_health.get('status', 'unknown')}">
                    Status: {system_health.get('status', 'unknown').upper()}
                    (Score: {system_health.get('overall_score', 0):.1f})
                </div>
                <p>Last Updated: {self.dashboard_data.get('timestamp', 'Never')}</p>
            </div>

            <div class="section">
                <h2>Alerts</h2>
                {self._generate_alerts_html(alerts)}
            </div>

            <div class="section">
                <h2>Circuit Breakers</h2>
                {self._generate_circuit_breakers_html(circuit_breakers)}
            </div>

            <div class="section">
                <h2>System Health</h2>
                <p>Overall Score: {system_health.get('overall_score', 0):.1f}/100</p>
                <p>Issues: {len(system_health.get('issues', []))}</p>
                <p>Recommendations: {len(system_health.get('recommendations', []))}</p>
            </div>
        </body>
        </html>
        """
        return html

    def _generate_alerts_html(self, alerts: List[Dict[str, Any]]) -> str:
        """Generate HTML for alerts section."""
        if not alerts:
            return "<p>No alerts</p>"

        html = ""
        for alert in alerts:
            alert_type = alert.get("type", "info")
            html += f"""
            <div class="alert {alert_type}">
                <strong>{alert.get('type', 'info').upper()}</strong>: {alert.get('message', '')}
                <br><small>Component: {alert.get('component', 'unknown')} | {alert.get('timestamp', '')}</small>
            </div>
            """
        return html

    def _generate_circuit_breakers_html(self, circuit_breakers: Dict[str, Any]) -> str:
        """Generate HTML for circuit breakers section."""
        if not circuit_breakers:
            return "<p>No circuit breakers registered</p>"

        html = "<table border='1' style='border-collapse: collapse; width: 100%;'>"
        html += "<tr><th>Name</th><th>State</th><th>Health Score</th><th>Failure Rate</th><th>Requests</th></tr>"

        for name, data in circuit_breakers.items():
            stats = data.get("stats", {})
            health = data.get("health", {})

            html += f"""
            <tr>
                <td>{name}</td>
                <td>{stats.get('state', 'unknown')}</td>
                <td>{health.get('health_score', 0):.1f}</td>
                <td>{stats.get('failure_rate', 0):.2%}</td>
                <td>{stats.get('total_requests', 0)}</td>
            </tr>
            """

        html += "</table>"
        return html
