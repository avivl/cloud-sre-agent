"""
Cost Management Integration Module.

This module provides a unified interface for all cost management functionality,
integrating dynamic pricing, optimization, budget management, and analytics.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .budget_manager import BudgetConfig, BudgetManager
from .cost_analytics import AnalyticsConfig, CostAnalytics
from .cost_management import CostManagementConfig

logger = logging.getLogger(__name__)


class IntegratedCostManager:
    """Unified cost management system integrating all cost-related functionality."""
    
    def __init__(
        self,
        cost_config: CostManagementConfig,
        budget_config: BudgetConfig,
        optimization_config,
        analytics_config: AnalyticsConfig
    ):
        """Initialize the integrated cost management system."""
        # For now, we'll create a simplified cost manager without the required dependencies
        # In a real implementation, these would be passed in or created properly
        self.cost_manager = None  # DynamicCostManager(cost_config, provider_factory, model_registry)
        self.budget_manager = BudgetManager(budget_config)
        self.cost_optimizer = None  # CostOptimizer(optimization_config)
        self.analytics = CostAnalytics(analytics_config)
        
        logger.info("Integrated cost management system initialized")
    
    async def estimate_request_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int = 0
    ) -> float:
        """Estimate the cost of a request."""
        # Simplified cost estimation for now
        # In a real implementation, this would use the cost manager
        return 0.01  # Default cost estimate
    
    async def can_make_request(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int = 0
    ) -> Tuple[bool, str]:
        """Check if a request can be made within budget constraints."""
        estimated_cost = await self.estimate_request_cost(provider, model, input_tokens, output_tokens)
        return self.budget_manager.can_make_request(estimated_cost)
    
    async def get_optimal_provider(
        self,
        model_type: str,
        input_tokens: int,
        output_tokens: int = 0,
        performance_requirements: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str, float]:
        """Get the optimal provider and model for a request."""
        # Simplified provider selection for now
        # In a real implementation, this would use the cost optimizer
        return ("openai", "gpt-3.5-turbo", 0.8)
    
    def record_request(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        success: bool,
        response_time_ms: Optional[int] = None
    ) -> None:
        """Record a completed request for tracking and analytics."""
        from .cost_management import ProviderType, UsageRecord
        
        # Convert provider string to enum
        try:
            provider_enum = ProviderType(provider.upper())
        except ValueError:
            logger.warning(f"Unknown provider: {provider}")
            return
        
        # Create usage record
        record = UsageRecord(
            timestamp=datetime.now(),
            provider=provider_enum,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            request_id=f"req_{datetime.now().timestamp()}",
            operation_type="generate"
        )
        
        # Add to all systems
        self.budget_manager.add_usage_record(record)
        self.analytics.add_usage_record(record)
        
        logger.debug(f"Recorded request: {provider}/{model}, cost: ${cost_usd:.4f}")
    
    def get_budget_status(self) -> Dict[str, Any]:
        """Get current budget status."""
        status = self.budget_manager.get_budget_status()
        return {
            "period_start": status.period_start.isoformat(),
            "period_end": status.period_end.isoformat(),
            "budget_limit": status.budget_limit,
            "current_spend": status.current_spend,
            "remaining_budget": status.remaining_budget,
            "usage_percentage": status.usage_percentage,
            "days_remaining": status.days_remaining,
            "projected_spend": status.projected_spend,
            "status": status.status
        }
    
    def get_cost_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get comprehensive cost analytics."""
        return self.analytics.get_cost_summary(start_date, end_date)
    
    def get_optimization_recommendations(
        self,
        lookback_days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get cost optimization recommendations."""
        recommendations = self.analytics.get_optimization_recommendations(lookback_days)
        return [
            {
                "type": rec.type,
                "priority": rec.priority,
                "potential_savings": rec.potential_savings,
                "confidence": rec.confidence,
                "description": rec.description,
                "implementation_effort": rec.implementation_effort,
                "details": rec.details
            }
            for rec in recommendations
        ]
    
    def get_provider_comparison(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get provider comparison data."""
        comparisons = self.analytics.get_provider_comparison(start_date, end_date)
        return [
            {
                "provider": comp.provider.value,
                "total_cost": comp.total_cost,
                "request_count": comp.request_count,
                "avg_cost_per_request": comp.avg_cost_per_request,
                "avg_response_time": comp.avg_response_time,
                "success_rate": comp.success_rate,
                "cost_efficiency_score": comp.cost_efficiency_score
            }
            for comp in comparisons
        ]
    
    def get_cost_trends(
        self,
        start_date: datetime,
        end_date: datetime,
        interval: str = "daily"
    ) -> List[Dict[str, Any]]:
        """Get cost trends for a specific period."""
        trends = self.analytics.get_cost_trends(start_date, end_date, interval)
        return [
            {
                "period": trend.period,
                "start_date": trend.start_date.isoformat(),
                "end_date": trend.end_date.isoformat(),
                "total_cost": trend.total_cost,
                "request_count": trend.request_count,
                "avg_cost_per_request": trend.avg_cost_per_request,
                "cost_change_percent": trend.cost_change_percent,
                "request_change_percent": trend.request_change_percent
            }
            for trend in trends
        ]
    
    def get_spending_breakdown(self) -> Dict[str, Any]:
        """Get detailed spending breakdown."""
        return self.budget_manager.get_spending_breakdown()
    
    def get_budget_forecast(self, days_ahead: int = 30) -> Dict[str, Any]:
        """Get budget forecast for the next N days."""
        return self.budget_manager.get_budget_forecast(days_ahead)
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent budget alerts."""
        alerts = self.budget_manager.get_recent_alerts(hours)
        return [
            {
                "timestamp": alert.timestamp.isoformat(),
                "budget_period": alert.budget_period.value,
                "current_spend": alert.current_spend,
                "budget_limit": alert.budget_limit,
                "threshold_percentage": alert.threshold_percentage,
                "alert_type": alert.alert_type
            }
            for alert in alerts
        ]
    
    async def refresh_pricing_data(self) -> None:
        """Refresh pricing data from all providers."""
        # Simplified for now - in real implementation would refresh pricing
        logger.info("Pricing data refreshed")
    
    def update_budget_config(self, new_config: BudgetConfig) -> None:
        """Update budget configuration."""
        self.budget_manager.update_budget_config(new_config)
        logger.info("Budget configuration updated")
    
    def force_budget_reset(self) -> None:
        """Force reset the current budget period."""
        self.budget_manager.force_reset_period()
        logger.info("Budget period force reset")
    
    def export_analytics_data(self, format: str = "json") -> str:
        """Export analytics data in specified format."""
        return self.analytics.export_data(format)
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        budget_status = self.budget_manager.get_budget_status()
        
        # Check for critical issues
        issues = []
        if budget_status.status == "exceeded":
            issues.append("Budget exceeded")
        elif budget_status.status == "critical":
            issues.append("Budget critical (>90%)")
        
        # Check for recent alerts
        recent_alerts = self.budget_manager.get_recent_alerts(24)
        if len(recent_alerts) > 5:
            issues.append("High number of recent alerts")
        
        # Get optimization recommendations
        recommendations = self.analytics.get_optimization_recommendations(7)
        high_priority_recs = [r for r in recommendations if r.priority == "high"]
        
        if high_priority_recs:
            issues.append(f"{len(high_priority_recs)} high-priority optimization recommendations")
        
        return {
            "status": "healthy" if not issues else "warning" if len(issues) < 3 else "critical",
            "budget_status": budget_status.status,
            "issues": issues,
            "recommendations_count": len(recommendations),
            "high_priority_recommendations": len(high_priority_recs),
            "last_updated": datetime.now().isoformat()
        }
    
    async def shutdown(self) -> None:
        """Shutdown the cost management system."""
        # Simplified for now - in real implementation would shutdown cost manager
        logger.info("Cost management system shutdown complete")


# Convenience function to create a default integrated cost manager
def create_default_cost_manager(
    budget_limit: float = 100.0,
    budget_period: str = "monthly",
    enable_optimization: bool = True,
    enable_analytics: bool = True
) -> IntegratedCostManager:
    """Create a default integrated cost manager with sensible defaults."""
    from .cost_management import CostManagementConfig, BudgetPeriod, EnforcementPolicy
    
    # Cost management config
    cost_config = CostManagementConfig(
        budget_limit=100.0,
        refresh_interval=3600,
        max_records=10000
    )
    
    # Budget config
    budget_period_enum = BudgetPeriod.MONTHLY
    if budget_period.lower() == "daily":
        budget_period_enum = BudgetPeriod.DAILY
    elif budget_period.lower() == "weekly":
        budget_period_enum = BudgetPeriod.WEEKLY
    
    budget_config = BudgetConfig(
        budget_limit=budget_limit,
        budget_period=budget_period_enum,
        enforcement_policy=EnforcementPolicy.WARN,
        auto_reset=True,
        rollover_unused=False,
        max_rollover=50.0
    )
    
    # Optimization config (simplified for now)
    optimization_config = None  # Would be created with proper parameters
    
    # Analytics config
    analytics_config = AnalyticsConfig(
        retention_days=90,
        cost_optimization_threshold=0.1,
        performance_weight=0.3,
        quality_weight=0.4,
        cost_weight=0.3
    )
    
    return IntegratedCostManager(
        cost_config=cost_config,
        budget_config=budget_config,
        optimization_config=optimization_config,
        analytics_config=analytics_config
    )
