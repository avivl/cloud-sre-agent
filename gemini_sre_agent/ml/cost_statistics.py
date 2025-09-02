"""
Cost tracking statistics and usage analysis for Gemini API.

This module provides statistics tracking, usage analytics, and reporting
capabilities for cost monitoring and optimization.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

from .cost_config import CostAnalytics, UsageRecord


class CostStatisticsManager:
    """Manages cost statistics, analytics, and usage reporting."""

    def __init__(self):
        self._stats = {
            "total_requests": 0,
            "total_tokens_input": 0,
            "total_tokens_output": 0,
            "budget_violations": 0,
            "warnings_issued": 0,
        }

    def update_request_stats(self, input_tokens: int, output_tokens: int) -> None:
        """Update statistics after a request."""
        self._stats["total_requests"] += 1
        self._stats["total_tokens_input"] += input_tokens
        self._stats["total_tokens_output"] += output_tokens

    def record_budget_violation(self) -> None:
        """Record a budget violation occurrence."""
        self._stats["budget_violations"] += 1

    def record_warning_issued(self) -> None:
        """Record a budget warning occurrence."""
        self._stats["warnings_issued"] += 1

    def get_base_stats(self) -> Dict[str, int]:
        """Get basic statistics dictionary."""
        return self._stats.copy()

    def analyze_recent_usage(self, usage_records: list[UsageRecord]) -> Dict[str, Any]:
        """Analyze usage patterns from the last 24 hours."""
        cutoff_time = datetime.now() - timedelta(hours=24)
        recent_records = [
            record for record in usage_records if record.timestamp >= cutoff_time
        ]

        if not recent_records:
            return {
                "request_count": 0,
                "total_cost": 0.0,
                "avg_cost_per_request": 0.0,
                "top_model": "none",
            }

        total_cost = sum(record.cost_usd for record in recent_records)
        top_model = CostAnalytics.find_top_model(recent_records)

        return {
            "request_count": len(recent_records),
            "total_cost": total_cost,
            "avg_cost_per_request": total_cost / len(recent_records),
            "top_model": top_model,
        }

    def build_usage_stats(
        self,
        daily_usage: float,
        monthly_usage: float,
        daily_budget: float,
        monthly_budget: float,
        current_date: str,
        current_month: str,
        warn_threshold: float,
        recent_usage: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build comprehensive usage statistics dictionary."""
        daily_pct = (daily_usage / daily_budget) * 100
        monthly_pct = (monthly_usage / monthly_budget) * 100

        return {
            # Current usage
            "daily_usage_usd": round(daily_usage, 6),
            "daily_budget_usd": daily_budget,
            "daily_remaining_usd": max(0, daily_budget - daily_usage),
            "daily_utilization_pct": round(daily_pct, 2),
            "monthly_usage_usd": round(monthly_usage, 6),
            "monthly_budget_usd": monthly_budget,
            "monthly_remaining_usd": max(0, monthly_budget - monthly_usage),
            "monthly_utilization_pct": round(monthly_pct, 2),
            # Statistics
            **self._stats,
            # Recent analysis
            "recent_24h_requests": recent_usage["request_count"],
            "recent_24h_cost_usd": round(recent_usage["total_cost"], 6),
            "average_cost_per_request": round(recent_usage["avg_cost_per_request"], 6),
            "most_used_model": recent_usage["top_model"],
            # Status
            "within_budget": (daily_pct < 100 and monthly_pct < 100),
            "approaching_limit": (
                daily_pct > warn_threshold or monthly_pct > warn_threshold
            ),
            "current_date": current_date,
            "current_month": current_month,
        }

    def get_cost_breakdown(
        self, usage_records: list[UsageRecord], days: int = 7
    ) -> Dict[str, Any]:
        """Get detailed cost breakdown for analysis and optimization."""
        cutoff_time = datetime.now() - timedelta(days=days)
        recent_records = [
            record for record in usage_records if record.timestamp >= cutoff_time
        ]

        if not recent_records:
            return {"period_days": days, "total_records": 0}

        model_breakdown = CostAnalytics.calculate_model_breakdown(recent_records)
        operation_breakdown = CostAnalytics.calculate_operation_breakdown(
            recent_records
        )
        total_cost = sum(record.cost_usd for record in recent_records)

        return {
            "period_days": days,
            "total_records": len(recent_records),
            "total_cost_usd": round(total_cost, 6),
            "avg_daily_cost": round(total_cost / days, 6),
            "model_breakdown": model_breakdown,
            "operation_breakdown": operation_breakdown,
        }
