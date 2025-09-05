"""
Cost Analytics and Reporting System for Multi-Provider LLM Operations.

This module provides comprehensive analytics, reporting, and insights
for cost management across different providers and time periods.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .cost_management import ProviderType, UsageRecord

logger = logging.getLogger(__name__)


class AnalyticsConfig(BaseModel):
    """Configuration for cost analytics."""

    retention_days: int = Field(90, gt=0, description="Days to retain usage data")
    aggregation_intervals: List[str] = Field(
        default=["hourly", "daily", "weekly", "monthly"],
        description="Available aggregation intervals",
    )
    cost_optimization_threshold: float = Field(
        0.1,
        gt=0,
        description="Cost difference threshold for optimization recommendations",
    )
    performance_weight: float = Field(
        0.3, ge=0, le=1, description="Weight for performance in cost optimization"
    )
    quality_weight: float = Field(
        0.4, ge=0, le=1, description="Weight for quality in cost optimization"
    )
    cost_weight: float = Field(
        0.3, ge=0, le=1, description="Weight for cost in optimization"
    )


@dataclass
class CostTrend:
    """Cost trend analysis data."""

    period: str
    start_date: datetime
    end_date: datetime
    total_cost: float
    request_count: int
    avg_cost_per_request: float
    cost_change_percent: float
    request_change_percent: float


@dataclass
class ProviderComparison:
    """Provider comparison data."""

    provider: ProviderType
    total_cost: float
    request_count: int
    avg_cost_per_request: float
    avg_response_time: float
    success_rate: float
    cost_efficiency_score: float


@dataclass
class OptimizationRecommendation:
    """Cost optimization recommendation."""

    type: str  # "provider_switch", "model_switch", "usage_pattern", "budget_adjustment"
    priority: str  # "high", "medium", "low"
    potential_savings: float
    confidence: float
    description: str
    implementation_effort: str  # "low", "medium", "high"
    details: Dict[str, Any]


class CostAnalytics:
    """Comprehensive cost analytics and reporting system."""

    def __init__(self, config: AnalyticsConfig):
        self.config = config
        self.usage_records: List[UsageRecord] = []

    def add_usage_record(self, record: UsageRecord) -> None:
        """Add a usage record for analytics."""
        self.usage_records.append(record)
        self._cleanup_old_records()

    def _cleanup_old_records(self) -> None:
        """Remove old usage records based on retention policy."""
        cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
        self.usage_records = [
            record for record in self.usage_records if record.timestamp >= cutoff_date
        ]

    def get_cost_trends(
        self, start_date: datetime, end_date: datetime, interval: str = "daily"
    ) -> List[CostTrend]:
        """Get cost trends for a specific period and interval."""
        # Filter records by date range
        filtered_records = [
            record
            for record in self.usage_records
            if start_date <= record.timestamp <= end_date
        ]

        if not filtered_records:
            return []

        # Group records by interval
        grouped_records = self._group_records_by_interval(filtered_records, interval)

        trends = []
        previous_period_cost = None
        previous_period_request_count = None

        for period, records in grouped_records.items():
            total_cost = sum(record.cost_usd for record in records)
            request_count = len(records)
            avg_cost_per_request = (
                total_cost / request_count if request_count > 0 else 0
            )

            # Calculate change from previous period
            cost_change_percent = 0.0
            request_change_percent = 0.0

            if previous_period_cost is not None:
                cost_change_percent = (
                    (total_cost - previous_period_cost) / previous_period_cost
                ) * 100
                
            if previous_period_request_count is not None and previous_period_request_count > 0:
                request_change_percent = (
                    (request_count - previous_period_request_count)
                    / previous_period_request_count
                ) * 100

            trends.append(
                CostTrend(
                    period=period,
                    start_date=records[0].timestamp if records else start_date,
                    end_date=records[-1].timestamp if records else end_date,
                    total_cost=total_cost,
                    request_count=request_count,
                    avg_cost_per_request=avg_cost_per_request,
                    cost_change_percent=cost_change_percent,
                    request_change_percent=request_change_percent,
                )
            )

            # Update previous period values for next iteration
            previous_period_cost = total_cost
            previous_period_request_count = request_count

        return trends

    def _group_records_by_interval(
        self, records: List[UsageRecord], interval: str
    ) -> Dict[str, List[UsageRecord]]:
        """Group records by time interval."""
        grouped = {}

        for record in records:
            if interval == "hourly":
                key = record.timestamp.strftime("%Y-%m-%d %H:00")
            elif interval == "daily":
                key = record.timestamp.strftime("%Y-%m-%d")
            elif interval == "weekly":
                # Get Monday of the week
                monday = record.timestamp - timedelta(days=record.timestamp.weekday())
                key = monday.strftime("%Y-%m-%d")
            elif interval == "monthly":
                key = record.timestamp.strftime("%Y-%m")
            else:
                key = record.timestamp.strftime("%Y-%m-%d")

            if key not in grouped:
                grouped[key] = []
            grouped[key].append(record)

        return dict(sorted(grouped.items()))

    def get_provider_comparison(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[ProviderComparison]:
        """Get comprehensive provider comparison."""
        # Filter records by date range if provided
        if start_date and end_date:
            filtered_records = [
                record
                for record in self.usage_records
                if start_date <= record.timestamp <= end_date
            ]
        else:
            filtered_records = self.usage_records

        # Group by provider
        provider_records = {}
        for record in filtered_records:
            provider = record.provider
            if provider not in provider_records:
                provider_records[provider] = []
            provider_records[provider].append(record)

        comparisons = []
        for provider, records in provider_records.items():
            total_cost = sum(record.cost_usd for record in records)
            request_count = len(records)
            avg_cost_per_request = (
                total_cost / request_count if request_count > 0 else 0
            )

            # Calculate average response time (not available in current UsageRecord)
            avg_response_time = 0.0  # Default to 0

            # Calculate success rate (assume all requests are successful for now)
            # In a real implementation, this would be tracked in the UsageRecord
            success_rate = 100.0  # Default to 100% success rate

            # Calculate cost efficiency score (lower cost + higher success rate = better score)
            cost_efficiency_score = (success_rate / 100) / (
                avg_cost_per_request + 0.001
            )  # Avoid division by zero

            comparisons.append(
                ProviderComparison(
                    provider=provider,
                    total_cost=total_cost,
                    request_count=request_count,
                    avg_cost_per_request=avg_cost_per_request,
                    avg_response_time=avg_response_time,
                    success_rate=success_rate,
                    cost_efficiency_score=cost_efficiency_score,
                )
            )

        return sorted(comparisons, key=lambda x: x.cost_efficiency_score, reverse=True)

    def get_optimization_recommendations(
        self, lookback_days: int = 30
    ) -> List[OptimizationRecommendation]:
        """Get cost optimization recommendations."""
        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        recent_records = [
            record for record in self.usage_records if record.timestamp >= cutoff_date
        ]

        if not recent_records:
            return []

        recommendations = []

        # Provider switch recommendations
        provider_recs = self._analyze_provider_switches(recent_records)
        recommendations.extend(provider_recs)

        # Model optimization recommendations
        model_recs = self._analyze_model_optimization(recent_records)
        recommendations.extend(model_recs)

        # Usage pattern recommendations
        usage_recs = self._analyze_usage_patterns(recent_records)
        recommendations.extend(usage_recs)

        # Sort by potential savings
        return sorted(recommendations, key=lambda x: x.potential_savings, reverse=True)

    def _analyze_provider_switches(
        self, records: List[UsageRecord]
    ) -> List[OptimizationRecommendation]:
        """Analyze potential provider switches for cost optimization."""
        recommendations = []

        # Group by model type and analyze provider performance
        model_groups = {}
        for record in records:
            model_type = getattr(record, "model_type", "unknown")
            if model_type not in model_groups:
                model_groups[model_type] = {}
            if record.provider not in model_groups[model_type]:
                model_groups[model_type][record.provider] = []
            model_groups[model_type][record.provider].append(record)

        for model_type, provider_records in model_groups.items():
            if len(provider_records) < 2:  # Need at least 2 providers to compare
                continue

            # Calculate average cost per provider for this model type
            provider_costs = {}
            for provider, provider_recs in provider_records.items():
                total_cost = sum(record.cost_usd for record in provider_recs)
                avg_cost = total_cost / len(provider_recs)
                success_rate = sum(1 for r in provider_recs if r.success) / len(
                    provider_recs
                )
                provider_costs[provider] = {
                    "avg_cost": avg_cost,
                    "success_rate": success_rate,
                    "request_count": len(provider_recs),
                }

            # Find the most expensive provider with significant usage
            expensive_provider = max(
                provider_costs.items(),
                key=lambda x: x[1]["avg_cost"] * x[1]["request_count"],
            )

            # Find cheaper alternatives with good success rates
            alternatives = [
                (provider, data)
                for provider, data in provider_costs.items()
                if (
                    provider != expensive_provider[0]
                    and data["avg_cost"]
                    < expensive_provider[1]["avg_cost"] * 0.8  # 20% cheaper
                    and data["success_rate"]
                    >= expensive_provider[1]["success_rate"] * 0.95
                )  # Similar success rate
            ]

            if alternatives:
                best_alternative = min(alternatives, key=lambda x: x[1]["avg_cost"])
                potential_savings = (
                    expensive_provider[1]["avg_cost"] - best_alternative[1]["avg_cost"]
                ) * expensive_provider[1]["request_count"]

                if potential_savings > self.config.cost_optimization_threshold:
                    recommendations.append(
                        OptimizationRecommendation(
                            type="provider_switch",
                            priority="high" if potential_savings > 10 else "medium",
                            potential_savings=potential_savings,
                            confidence=0.8,
                            description=f"Switch from {expensive_provider[0].value} to {best_alternative[0].value} for {model_type} models",
                            implementation_effort="low",
                            details={
                                "current_provider": expensive_provider[0].value,
                                "recommended_provider": best_alternative[0].value,
                                "model_type": model_type,
                                "current_avg_cost": expensive_provider[1]["avg_cost"],
                                "recommended_avg_cost": best_alternative[1]["avg_cost"],
                                "request_count": expensive_provider[1]["request_count"],
                            },
                        )
                    )

        return recommendations

    def _analyze_model_optimization(
        self, records: List[UsageRecord]
    ) -> List[OptimizationRecommendation]:
        """Analyze model usage for optimization opportunities."""
        recommendations = []

        # Group by provider and analyze model usage patterns
        provider_groups = {}
        for record in records:
            if record.provider not in provider_groups:
                provider_groups[record.provider] = {}
            model = record.model
            if model not in provider_groups[record.provider]:
                provider_groups[record.provider][model] = []
            provider_groups[record.provider][model].append(record)

        for provider, model_records in provider_groups.items():
            if len(model_records) < 2:  # Need at least 2 models to compare
                continue

            # Analyze model performance vs cost
            model_analysis = {}
            for model, model_recs in model_records.items():
                total_cost = sum(record.cost_usd for record in model_recs)
                avg_cost = total_cost / len(model_recs)
                success_rate = sum(1 for r in model_recs if r.success) / len(model_recs)
                avg_response_time = sum(
                    r.response_time_ms for r in model_recs if r.response_time_ms
                ) / len([r for r in model_recs if r.response_time_ms])

                model_analysis[model] = {
                    "avg_cost": avg_cost,
                    "success_rate": success_rate,
                    "avg_response_time": avg_response_time,
                    "request_count": len(model_recs),
                }

            # Find overused expensive models
            for model, data in model_analysis.items():
                if data["request_count"] < 10:  # Skip models with low usage
                    continue

                # Find cheaper alternatives with similar performance
                alternatives = [
                    (alt_model, alt_data)
                    for alt_model, alt_data in model_analysis.items()
                    if (
                        alt_model != model
                        and alt_data["avg_cost"] < data["avg_cost"] * 0.7  # 30% cheaper
                        and alt_data["success_rate"] >= data["success_rate"] * 0.9
                    )  # Similar success rate
                ]

                if alternatives:
                    best_alternative = min(alternatives, key=lambda x: x[1]["avg_cost"])
                    potential_savings = (
                        data["avg_cost"] - best_alternative[1]["avg_cost"]
                    ) * data["request_count"]

                    if potential_savings > self.config.cost_optimization_threshold:
                        recommendations.append(
                            OptimizationRecommendation(
                                type="model_switch",
                                priority="medium",
                                potential_savings=potential_savings,
                                confidence=0.7,
                                description=f"Consider using {best_alternative[0]} instead of {model} for {provider.value}",
                                implementation_effort="low",
                                details={
                                    "current_model": model,
                                    "recommended_model": best_alternative[0],
                                    "provider": provider.value,
                                    "current_avg_cost": data["avg_cost"],
                                    "recommended_avg_cost": best_alternative[1][
                                        "avg_cost"
                                    ],
                                    "request_count": data["request_count"],
                                },
                            )
                        )

        return recommendations

    def _analyze_usage_patterns(
        self, records: List[UsageRecord]
    ) -> List[OptimizationRecommendation]:
        """Analyze usage patterns for optimization opportunities."""
        recommendations = []

        # Analyze peak usage times
        hourly_usage = {}
        for record in records:
            hour = record.timestamp.hour
            if hour not in hourly_usage:
                hourly_usage[hour] = {"cost": 0, "requests": 0}
            hourly_usage[hour]["cost"] += record.cost_usd
            hourly_usage[hour]["requests"] += 1

        if hourly_usage:
            # Find peak hours
            peak_hours = sorted(
                hourly_usage.items(), key=lambda x: x[1]["cost"], reverse=True
            )[:3]
            off_peak_hours = sorted(hourly_usage.items(), key=lambda x: x[1]["cost"])[
                :3
            ]

            peak_cost = sum(data["cost"] for _, data in peak_hours)
            off_peak_cost = sum(data["cost"] for _, data in off_peak_hours)

            if peak_cost > off_peak_cost * 2:  # Significant peak usage
                recommendations.append(
                    OptimizationRecommendation(
                        type="usage_pattern",
                        priority="low",
                        potential_savings=peak_cost
                        * 0.1,  # Estimate 10% savings from load balancing
                        confidence=0.6,
                        description="Consider load balancing requests to off-peak hours",
                        implementation_effort="medium",
                        details={
                            "peak_hours": [hour for hour, _ in peak_hours],
                            "off_peak_hours": [hour for hour, _ in off_peak_hours],
                            "peak_cost": peak_cost,
                            "off_peak_cost": off_peak_cost,
                        },
                    )
                )

        return recommendations

    def get_cost_summary(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get comprehensive cost summary."""
        if start_date and end_date:
            filtered_records = [
                record
                for record in self.usage_records
                if start_date <= record.timestamp <= end_date
            ]
        else:
            filtered_records = self.usage_records

        if not filtered_records:
            return {"error": "No data available for the specified period"}

        total_cost = sum(record.cost_usd for record in filtered_records)
        total_requests = len(filtered_records)
        successful_requests = len(
            filtered_records
        )  # Assume all requests are successful

        # Provider breakdown
        provider_breakdown = {}
        for record in filtered_records:
            provider = record.provider.value
            if provider not in provider_breakdown:
                provider_breakdown[provider] = {
                    "cost": 0,
                    "requests": 0,
                    "successful": 0,
                }
            provider_breakdown[provider]["cost"] += record.cost_usd
            provider_breakdown[provider]["requests"] += 1
            # Assume all requests are successful
            provider_breakdown[provider]["successful"] += 1

        # Model breakdown
        model_breakdown = {}
        for record in filtered_records:
            model = record.model
            if model not in model_breakdown:
                model_breakdown[model] = {"cost": 0, "requests": 0, "successful": 0}
            model_breakdown[model]["cost"] += record.cost_usd
            model_breakdown[model]["requests"] += 1
            # Assume all requests are successful
            model_breakdown[model]["successful"] += 1

        return {
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            "summary": {
                "total_cost": total_cost,
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "success_rate": (
                    (successful_requests / total_requests) * 100
                    if total_requests > 0
                    else 0
                ),
                "avg_cost_per_request": (
                    total_cost / total_requests if total_requests > 0 else 0
                ),
            },
            "provider_breakdown": provider_breakdown,
            "model_breakdown": model_breakdown,
        }

    def export_data(self, format: str = "json") -> str:
        """Export usage data in specified format."""
        if format == "json":
            import json

            data = {
                "usage_records": [
                    {
                        "timestamp": record.timestamp.isoformat(),
                        "provider": record.provider.value,
                        "model": record.model,
                        "cost_usd": record.cost_usd,
                        "success": True,  # Assume all requests are successful
                        "response_time_ms": None,  # Not available in current UsageRecord
                        "tokens_used": record.input_tokens + record.output_tokens,
                    }
                    for record in self.usage_records
                ]
            }
            return json.dumps(data, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")
