"""
Budget Management System for Multi-Provider LLM Operations.

This module provides comprehensive budget tracking, enforcement, and alerting
capabilities for managing costs across different providers and time periods.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .cost_management import BudgetAlert, BudgetPeriod, EnforcementPolicy, UsageRecord

logger = logging.getLogger(__name__)


class BudgetConfig(BaseModel):
    """Configuration for budget management."""

    budget_limit: float = Field(100.0, gt=0, description="Budget limit in USD")
    budget_period: BudgetPeriod = BudgetPeriod.MONTHLY
    alert_thresholds: List[float] = Field(
        default=[0.5, 0.8, 0.9, 1.0],
        description="Alert thresholds as percentages (0.0 to 1.0)",
    )
    enforcement_policy: EnforcementPolicy = EnforcementPolicy.WARN
    auto_reset: bool = Field(
        True, description="Automatically reset budget at period end"
    )
    rollover_unused: bool = Field(
        False, description="Roll over unused budget to next period"
    )
    max_rollover: float = Field(
        50.0, gt=0, description="Maximum rollover amount in USD"
    )


@dataclass
class BudgetStatus:
    """Current budget status information."""

    period_start: datetime
    period_end: datetime
    budget_limit: float
    current_spend: float
    remaining_budget: float
    usage_percentage: float
    days_remaining: int
    projected_spend: float
    status: str  # "healthy", "warning", "critical", "exceeded"


class BudgetManager:
    """Manages budget tracking, enforcement, and alerts."""

    def __init__(self, config: BudgetConfig):
        self.config = config
        self.usage_records: List[UsageRecord] = []
        self.budget_alerts: List[BudgetAlert] = []
        self.period_start: Optional[datetime] = None
        self.period_end: Optional[datetime] = None
        self.rollover_amount: float = 0.0

        # Initialize current period
        self._initialize_period()

    def _initialize_period(self) -> None:
        """Initialize the current budget period."""
        now = datetime.now()

        if self.config.budget_period == BudgetPeriod.DAILY:
            self.period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self.period_end = self.period_start + timedelta(days=1)
        elif self.config.budget_period == BudgetPeriod.WEEKLY:
            # Start from Monday
            days_since_monday = now.weekday()
            self.period_start = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            self.period_end = self.period_start + timedelta(weeks=1)
        else:  # MONTHLY
            self.period_start = now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            # Calculate next month
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            self.period_end = next_month

        logger.info(
            f"Initialized budget period: {self.period_start} to {self.period_end}"
        )

    def add_usage_record(self, record: UsageRecord) -> None:
        """Add a usage record and check budget constraints."""
        # Check if we need to reset the period
        if self._should_reset_period():
            self._reset_period()

        # Add the record
        self.usage_records.append(record)

        # Check budget thresholds
        self._check_budget_thresholds()

        # Check if we need to enforce budget limits
        self._enforce_budget_limits()

    def _should_reset_period(self) -> bool:
        """Check if the budget period should be reset."""
        if not self.config.auto_reset:
            return False

        now = datetime.now()
        return self.period_end is not None and now >= self.period_end

    def _reset_period(self) -> None:
        """Reset the budget period."""
        if self.config.rollover_unused:
            current_spend = self.get_current_spend()
            unused_budget = max(0, self.config.budget_limit - current_spend)
            self.rollover_amount = min(unused_budget, self.config.max_rollover)
            logger.info(f"Rolling over ${self.rollover_amount:.2f} unused budget")
        else:
            self.rollover_amount = 0.0

        # Clear usage records for the new period
        self.usage_records = []
        self.budget_alerts = []

        # Initialize new period
        self._initialize_period()

        logger.info(
            f"Budget period reset. New period: {self.period_start} to {self.period_end}"
        )

    def _check_budget_thresholds(self) -> None:
        """Check if budget thresholds have been exceeded."""
        current_spend = self.get_current_spend()
        effective_budget = self.get_effective_budget()

        for threshold in self.config.alert_thresholds:
            threshold_amount = effective_budget * threshold

            if current_spend >= threshold_amount:
                # Check if we've already sent an alert for this threshold recently
                recent_alerts = [
                    alert
                    for alert in self.budget_alerts
                    if alert.threshold_percentage == threshold
                    and (datetime.now() - alert.timestamp).total_seconds()
                    < 3600  # 1 hour
                ]

                if not recent_alerts:
                    alert = BudgetAlert(
                        timestamp=datetime.now(),
                        budget_period=self.config.budget_period,
                        current_spend=current_spend,
                        budget_limit=effective_budget,
                        threshold_percentage=threshold,
                        alert_type="budget_threshold",
                    )
                    self.budget_alerts.append(alert)

                    severity = "WARNING" if threshold < 1.0 else "CRITICAL"
                    logger.warning(
                        f"Budget {severity}: {threshold*100}% threshold exceeded "
                        f"(${current_spend:.2f}/${effective_budget:.2f})"
                    )

    def _enforce_budget_limits(self) -> None:
        """Enforce budget limits based on policy."""
        current_spend = self.get_current_spend()
        effective_budget = self.get_effective_budget()

        if current_spend > effective_budget:
            if self.config.enforcement_policy == EnforcementPolicy.HARD_LIMIT:
                logger.error(
                    f"Budget exceeded! Current spend: ${current_spend:.2f}, Limit: ${effective_budget:.2f}"
                )
                # In a real implementation, this might trigger request blocking
            elif self.config.enforcement_policy == EnforcementPolicy.SOFT_LIMIT:
                logger.warning(
                    f"Budget exceeded (soft limit). Current spend: ${current_spend:.2f}, Limit: ${effective_budget:.2f}"
                )

    def get_current_spend(self) -> float:
        """Get current spending for the current period."""
        if not self.period_start:
            return 0.0

        current_period_records = [
            record
            for record in self.usage_records
            if record.timestamp >= self.period_start
        ]

        return sum(record.cost_usd for record in current_period_records)

    def get_effective_budget(self) -> float:
        """Get the effective budget limit including rollover."""
        return self.config.budget_limit + self.rollover_amount

    def get_budget_status(self) -> BudgetStatus:
        """Get current budget status."""
        current_spend = self.get_current_spend()
        effective_budget = self.get_effective_budget()
        remaining_budget = max(0, effective_budget - current_spend)
        usage_percentage = (
            (current_spend / effective_budget) * 100 if effective_budget > 0 else 0
        )

        # Calculate days remaining
        now = datetime.now()
        if self.period_end:
            days_remaining = max(0, (self.period_end - now).days)
        else:
            days_remaining = 0

        # Project spending based on current rate
        if self.period_start and days_remaining > 0:
            days_elapsed = (now - self.period_start).days
            if days_elapsed > 0:
                daily_rate = current_spend / days_elapsed
                projected_spend = current_spend + (daily_rate * days_remaining)
            else:
                projected_spend = current_spend
        else:
            projected_spend = current_spend

        # Determine status
        if usage_percentage >= 100:
            status = "exceeded"
        elif usage_percentage >= 90:
            status = "critical"
        elif usage_percentage >= 80:
            status = "warning"
        else:
            status = "healthy"

        return BudgetStatus(
            period_start=self.period_start or now,
            period_end=self.period_end or now,
            budget_limit=effective_budget,
            current_spend=current_spend,
            remaining_budget=remaining_budget,
            usage_percentage=usage_percentage,
            days_remaining=days_remaining,
            projected_spend=projected_spend,
            status=status,
        )

    def can_make_request(self, estimated_cost: float) -> tuple[bool, str]:
        """Check if a request can be made within budget constraints."""
        current_spend = self.get_current_spend()
        effective_budget = self.get_effective_budget()
        total_after_request = current_spend + estimated_cost

        if total_after_request > effective_budget:
            if self.config.enforcement_policy == EnforcementPolicy.HARD_LIMIT:
                return (
                    False,
                    f"Request would exceed budget limit (${total_after_request:.2f} > ${effective_budget:.2f})",
                )
            elif self.config.enforcement_policy == EnforcementPolicy.SOFT_LIMIT:
                return (
                    True,
                    f"Warning: Request would exceed budget limit (${total_after_request:.2f} > ${effective_budget:.2f})",
                )

        return True, "Request within budget"

    def get_spending_breakdown(self) -> Dict[str, Any]:
        """Get detailed spending breakdown."""
        if not self.usage_records:
            return {"total_spend": 0.0, "by_provider": {}, "by_model": {}, "by_day": {}}

        current_period_records = [
            record
            for record in self.usage_records
            if self.period_start and record.timestamp >= self.period_start
        ]

        total_spend = sum(record.cost_usd for record in current_period_records)

        # Breakdown by provider
        by_provider = {}
        for record in current_period_records:
            provider = record.provider.value
            if provider not in by_provider:
                by_provider[provider] = {"cost": 0.0, "requests": 0}
            by_provider[provider]["cost"] += record.cost_usd
            by_provider[provider]["requests"] += 1

        # Breakdown by model
        by_model = {}
        for record in current_period_records:
            model = record.model
            if model not in by_model:
                by_model[model] = {"cost": 0.0, "requests": 0}
            by_model[model]["cost"] += record.cost_usd
            by_model[model]["requests"] += 1

        # Breakdown by day
        by_day = {}
        for record in current_period_records:
            day = record.timestamp.date().isoformat()
            if day not in by_day:
                by_day[day] = {"cost": 0.0, "requests": 0}
            by_day[day]["cost"] += record.cost_usd
            by_day[day]["requests"] += 1

        return {
            "total_spend": total_spend,
            "by_provider": by_provider,
            "by_model": by_model,
            "by_day": by_day,
            "period_start": (
                self.period_start.isoformat() if self.period_start else None
            ),
            "period_end": self.period_end.isoformat() if self.period_end else None,
        }

    def get_recent_alerts(self, hours: int = 24) -> List[BudgetAlert]:
        """Get recent budget alerts."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [alert for alert in self.budget_alerts if alert.timestamp >= cutoff_time]

    def update_budget_config(self, new_config: BudgetConfig) -> None:
        """Update budget configuration."""
        self.config = new_config
        logger.info("Budget configuration updated")

    def force_reset_period(self) -> None:
        """Force reset the current budget period."""
        self._reset_period()
        logger.info("Budget period force reset")

    def get_budget_forecast(self, days_ahead: int = 30) -> Dict[str, Any]:
        """Get budget forecast for the next N days."""
        current_spend = self.get_current_spend()

        if not self.period_start:
            return {"error": "No period initialized"}

        now = datetime.now()
        days_elapsed = (now - self.period_start).days

        if days_elapsed <= 0:
            return {"error": "Period just started, insufficient data for forecast"}

        # Calculate daily spending rate
        daily_rate = current_spend / days_elapsed

        # Project future spending
        forecast = []
        for day in range(1, days_ahead + 1):
            projected_spend = current_spend + (daily_rate * day)
            forecast.append(
                {
                    "day": day,
                    "projected_spend": projected_spend,
                    "budget_remaining": max(
                        0, self.get_effective_budget() - projected_spend
                    ),
                }
            )

        return {
            "current_spend": current_spend,
            "daily_rate": daily_rate,
            "effective_budget": self.get_effective_budget(),
            "forecast": forecast,
            "days_until_budget_exhausted": (
                int(self.get_effective_budget() / daily_rate)
                if daily_rate > 0
                else None
            ),
        }
