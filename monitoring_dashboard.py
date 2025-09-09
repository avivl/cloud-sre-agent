#!/usr/bin/env python3
"""
Monitoring Dashboard for Enhanced Multi-Provider LLM System

This script creates a comprehensive monitoring dashboard using the metrics collector.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

from gemini_sre_agent.llm.monitoring.llm_metrics import get_llm_metrics_collector
from gemini_sre_agent.llm.config import LLMConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MonitoringDashboard:
    """Comprehensive monitoring dashboard for the enhanced LLM system."""
    
    def __init__(self):
        self.metrics_collector = get_llm_metrics_collector()
        self.start_time = datetime.now()
        
    def generate_dashboard_data(self) -> Dict[str, Any]:
        """Generate comprehensive dashboard data."""
        current_time = datetime.now()
        uptime = current_time - self.start_time
        
        # Get metrics summary
        metrics_summary = self.metrics_collector.get_metrics_summary()
        provider_metrics = self.metrics_collector.get_all_provider_metrics()
        model_metrics = self.metrics_collector.get_all_model_metrics()
        
        # Calculate additional metrics
        total_requests = metrics_summary.get('total_requests', 0)
        total_cost = metrics_summary.get('total_cost', 0.0)
        success_rate = metrics_summary.get('overall_success_rate', 0.0)
        avg_latency = metrics_summary.get('average_latency_ms', 0.0)
        
        # Calculate rates
        uptime_hours = uptime.total_seconds() / 3600
        requests_per_hour = total_requests / max(uptime_hours, 0.01)
        cost_per_hour = total_cost / max(uptime_hours, 0.01)
        
        return {
            "dashboard": {
                "title": "Enhanced Multi-Provider LLM System Dashboard",
                "last_updated": current_time.isoformat(),
                "uptime_hours": round(uptime_hours, 2),
                "status": "OPERATIONAL"
            },
            "overview": {
                "total_requests": total_requests,
                "total_cost": round(total_cost, 4),
                "success_rate": round(success_rate * 100, 2),
                "average_latency_ms": round(avg_latency, 2),
                "requests_per_hour": round(requests_per_hour, 2),
                "cost_per_hour": round(cost_per_hour, 4),
                "provider_count": len(provider_metrics),
                "model_count": len(model_metrics)
            },
            "providers": {
                provider: {
                    "total_requests": pm.total_requests,
                    "success_rate": round(pm.success_rate * 100, 2),
                    "total_cost": round(pm.total_cost, 4),
                    "avg_latency_ms": round(pm.avg_latency_ms, 2),
                    "p95_latency_ms": round(pm.p95_latency_ms, 2),
                    "p99_latency_ms": round(pm.p99_latency_ms, 2),
                    "circuit_breaker_trips": pm.circuit_breaker_trips,
                    "rate_limit_hits": pm.rate_limit_hits,
                    "last_updated": pm.last_updated.isoformat()
                }
                for provider, pm in provider_metrics.items()
            },
            "models": {
                model_key: {
                    "provider": mm.provider,
                    "model": mm.model,
                    "model_type": mm.model_type,
                    "total_requests": mm.total_requests,
                    "success_rate": round(mm.success_rate * 100, 2),
                    "total_cost": round(mm.total_cost, 4),
                    "avg_latency_ms": round(mm.avg_latency_ms, 2),
                    "quality_score": round(mm.quality_score, 2),
                    "last_updated": mm.last_updated.isoformat()
                }
                for model_key, mm in model_metrics.items()
            },
            "alerts": self._generate_alerts(metrics_summary, provider_metrics),
            "recommendations": self._generate_recommendations(metrics_summary, provider_metrics)
        }
    
    def _generate_alerts(self, metrics_summary: Dict, provider_metrics: Dict) -> List[Dict]:
        """Generate alerts based on metrics."""
        alerts = []
        
        # Check success rate
        success_rate = metrics_summary.get('overall_success_rate', 0.0)
        if success_rate < 0.95:
            alerts.append({
                "level": "WARNING",
                "message": f"Low success rate: {success_rate:.2%}",
                "recommendation": "Check provider health and error logs"
            })
        
        # Check latency
        avg_latency = metrics_summary.get('average_latency_ms', 0.0)
        if avg_latency > 5000:  # 5 seconds
            alerts.append({
                "level": "WARNING", 
                "message": f"High average latency: {avg_latency:.2f}ms",
                "recommendation": "Consider switching to faster models or providers"
            })
        
        # Check circuit breaker trips
        for provider, pm in provider_metrics.items():
            if pm.circuit_breaker_trips > 0:
                alerts.append({
                    "level": "ERROR",
                    "message": f"Circuit breaker tripped {pm.circuit_breaker_trips} times for {provider}",
                    "recommendation": "Check provider status and consider fallback options"
                })
        
        # Check rate limits
        for provider, pm in provider_metrics.items():
            if pm.rate_limit_hits > 0:
                alerts.append({
                    "level": "WARNING",
                    "message": f"Rate limit hit {pm.rate_limit_hits} times for {provider}",
                    "recommendation": "Consider implementing request queuing or using multiple API keys"
                })
        
        return alerts
    
    def _generate_recommendations(self, metrics_summary: Dict, provider_metrics: Dict) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Cost optimization
        total_cost = metrics_summary.get('total_cost', 0.0)
        if total_cost > 10.0:  # $10
            recommendations.append("Consider implementing cost optimization strategies")
        
        # Performance optimization
        avg_latency = metrics_summary.get('average_latency_ms', 0.0)
        if avg_latency > 2000:  # 2 seconds
            recommendations.append("Consider using faster models for better performance")
        
        # Provider diversity
        if len(provider_metrics) < 2:
            recommendations.append("Consider adding more providers for better reliability")
        
        # Success rate optimization
        success_rate = metrics_summary.get('overall_success_rate', 0.0)
        if success_rate < 0.98:
            recommendations.append("Investigate and improve error handling")
        
        return recommendations
    
    def export_dashboard_json(self, filename: str = None) -> str:
        """Export dashboard data to JSON file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dashboard_{timestamp}.json"
        
        dashboard_data = self.generate_dashboard_data()
        
        with open(filename, 'w') as f:
            json.dump(dashboard_data, f, indent=2)
        
        return filename
    
    def print_dashboard(self):
        """Print a formatted dashboard to console."""
        dashboard_data = self.generate_dashboard_data()
        
        print("=" * 80)
        print(f"🚀 {dashboard_data['dashboard']['title']}")
        print("=" * 80)
        print(f"📊 Last Updated: {dashboard_data['dashboard']['last_updated']}")
        print(f"⏱️  Uptime: {dashboard_data['dashboard']['uptime_hours']} hours")
        print(f"🟢 Status: {dashboard_data['dashboard']['status']}")
        print()
        
        # Overview
        overview = dashboard_data['overview']
        print("📈 OVERVIEW")
        print("-" * 40)
        print(f"Total Requests: {overview['total_requests']:,}")
        print(f"Total Cost: ${overview['total_cost']:.4f}")
        print(f"Success Rate: {overview['success_rate']:.2f}%")
        print(f"Avg Latency: {overview['average_latency_ms']:.2f}ms")
        print(f"Requests/Hour: {overview['requests_per_hour']:.2f}")
        print(f"Cost/Hour: ${overview['cost_per_hour']:.4f}")
        print(f"Providers: {overview['provider_count']}")
        print(f"Models: {overview['model_count']}")
        print()
        
        # Providers
        if dashboard_data['providers']:
            print("🔌 PROVIDERS")
            print("-" * 40)
            for provider, data in dashboard_data['providers'].items():
                print(f"{provider.upper()}:")
                print(f"  Requests: {data['total_requests']:,}")
                print(f"  Success Rate: {data['success_rate']:.2f}%")
                print(f"  Cost: ${data['total_cost']:.4f}")
                print(f"  Avg Latency: {data['avg_latency_ms']:.2f}ms")
                if data['circuit_breaker_trips'] > 0:
                    print(f"  ⚠️  Circuit Breaker Trips: {data['circuit_breaker_trips']}")
                if data['rate_limit_hits'] > 0:
                    print(f"  ⚠️  Rate Limit Hits: {data['rate_limit_hits']}")
                print()
        
        # Models
        if dashboard_data['models']:
            print("🤖 MODELS")
            print("-" * 40)
            for model_key, data in dashboard_data['models'].items():
                print(f"{data['model']} ({data['provider']}):")
                print(f"  Type: {data['model_type']}")
                print(f"  Requests: {data['total_requests']:,}")
                print(f"  Success Rate: {data['success_rate']:.2f}%")
                print(f"  Cost: ${data['total_cost']:.4f}")
                print(f"  Avg Latency: {data['avg_latency_ms']:.2f}ms")
                print(f"  Quality Score: {data['quality_score']:.2f}")
                print()
        
        # Alerts
        if dashboard_data['alerts']:
            print("🚨 ALERTS")
            print("-" * 40)
            for alert in dashboard_data['alerts']:
                level_icon = "🔴" if alert['level'] == 'ERROR' else "🟡"
                print(f"{level_icon} {alert['level']}: {alert['message']}")
                print(f"   💡 {alert['recommendation']}")
                print()
        
        # Recommendations
        if dashboard_data['recommendations']:
            print("💡 RECOMMENDATIONS")
            print("-" * 40)
            for i, rec in enumerate(dashboard_data['recommendations'], 1):
                print(f"{i}. {rec}")
            print()
        
        print("=" * 80)

async def run_monitoring_demo():
    """Run monitoring dashboard demo."""
    print("🚀 Starting Monitoring Dashboard Demo")
    print("=" * 60)
    
    # Create dashboard
    dashboard = MonitoringDashboard()
    
    # Simulate some activity
    print("📊 Simulating system activity...")
    
    # Add some sample metrics
    for i in range(20):
        dashboard.metrics_collector.record_request(
            provider='gemini',
            model='gemini-1.5-flash',
            model_type='fast',
            request=None,
            response=None,
            duration_ms=150 + i * 5,
            cost=0.001 + i * 0.0001
        )
        
        # Simulate some failures
        if i % 10 == 0:
            dashboard.metrics_collector.record_request(
                provider='openai',
                model='gpt-4o-mini',
                model_type='smart',
                request=None,
                response=None,
                error=Exception("Rate limit exceeded"),
                duration_ms=5000,
                cost=0.0
            )
    
    # Add some circuit breaker trips
    dashboard.metrics_collector.record_circuit_breaker_trip('openai')
    dashboard.metrics_collector.record_rate_limit_hit('gemini')
    
    print("✅ Activity simulation complete")
    print()
    
    # Display dashboard
    dashboard.print_dashboard()
    
    # Export to JSON
    filename = dashboard.export_dashboard_json()
    print(f"📁 Dashboard exported to: {filename}")
    
    return dashboard

if __name__ == "__main__":
    asyncio.run(run_monitoring_demo())
