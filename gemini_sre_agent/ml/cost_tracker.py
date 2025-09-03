# gemini_sre_agent/ml/cost_tracker.py

"""
Cost tracker for monitoring API usage and budget management.

This module implements cost tracking functionality to monitor API usage costs,
manage budgets, and provide cost-related insights and alerts.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .cost_config import BudgetConfig, BudgetStatus, CostSummary, UsageRecord


class CostTracker:
    """
    Tracks API usage costs and manages budget constraints.

    This class provides comprehensive cost tracking, budget management,
    and cost-related analytics for API usage monitoring.
    """

    def __init__(
        self, budget_config: Optional[BudgetConfig] = None, max_records: int = 10000
    ):
        """
        Initialize the cost tracker.

        Args:
            budget_config: Budget configuration for cost tracking
            max_records: Maximum number of usage records to keep
        """
        self.budget_config = budget_config or BudgetConfig()
        self.config = self.budget_config  # Alias for compatibility
        self.max_records = max_records
        self.logger = logging.getLogger(__name__)

        # Usage records storage
        self.usage_records: List[UsageRecord] = []

        # Daily and monthly tracking
        self.daily_usage = 0.0
        self.daily_cost = 0.0  # Alias for compatibility
        self.monthly_usage = 0.0
        self.monthly_cost = 0.0  # Alias for compatibility
        self.last_daily_reset = datetime.now(timezone.utc).date()
        self.last_monthly_reset = datetime.now(timezone.utc).replace(day=1).date()

        # Cost tracking by model and operation
        self.cost_by_model: Dict[str, float] = {}
        self.cost_by_operation: Dict[str, float] = {}

        # Current date for testing
        self.current_date: Optional[date] = None
        self.current_month: Optional[tuple] = None

        # Model pricing (simplified)
        self.model_pricing = {
            "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
            "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
            "default": {"input": 0.00125, "output": 0.005},
        }

        # Stats manager (simplified)
        self._stats_manager = self._StatsManager()

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for a given model and token usage.

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        pricing = self.model_pricing.get(model, self.model_pricing["default"])
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        return input_cost + output_cost

    async def record_actual_cost(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        request_id: str = "",
        operation_type: str = "unknown",
    ) -> float:
        """Record actual cost with detailed parameters."""
        # Calculate cost
        cost_usd = self.estimate_cost(model_name, input_tokens, output_tokens)

        # Record usage
        await self.record_usage(
            operation=operation_type,
            model=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            success=True,
            metadata={"request_id": request_id} if request_id else None,
        )

        return cost_usd

    async def record_usage(
        self,
        operation: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UsageRecord:
        """
        Record API usage and associated costs.

        Args:
            operation: Type of operation performed
            model: Model used for the operation
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost_usd: Cost in USD
            success: Whether the operation was successful
            error_message: Error message if operation failed
            metadata: Additional metadata

        Returns:
            Created usage record
        """
        # Create usage record
        record = UsageRecord(
            timestamp=datetime.now(timezone.utc),
            operation=operation,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            success=success,
            error_message=error_message,
            metadata=metadata or {},
        )

        # Add to records
        self.usage_records.append(record)

        # Update cost tracking
        await self._update_cost_tracking(record)

        # Check for budget alerts
        await self._check_budget_alerts()

        self.logger.debug(
            f"Recorded usage: {operation} using {model}, cost: ${cost_usd:.4f}"
        )

        return record

    async def check_budget(self, estimated_cost: float) -> bool:
        """
        Check if estimated cost would exceed budget limits.

        Args:
            estimated_cost: Estimated cost of the operation

        Returns:
            True if operation is within budget, False otherwise
        """
        # Check daily budget
        if self.daily_cost + estimated_cost > self.budget_config.daily_budget_usd:
            self.logger.warning(
                f"Operation would exceed daily budget: "
                f"${self.daily_cost + estimated_cost:.2f} > ${self.budget_config.daily_budget_usd:.2f}"
            )
            return False

        # Check monthly budget
        if self.monthly_cost + estimated_cost > self.budget_config.monthly_budget_usd:
            self.logger.warning(
                f"Operation would exceed monthly budget: "
                f"${self.monthly_cost + estimated_cost:.2f} > ${self.budget_config.monthly_budget_usd:.2f}"
            )
            return False

        return True

    async def get_budget_status(self) -> BudgetStatus:
        """
        Get current budget status.

        Returns:
            Current budget status information
        """
        # Reset daily/monthly costs if needed
        await self._reset_periodic_costs()

        daily_usage_percent = (
            self.daily_cost / self.budget_config.daily_budget_usd
        ) * 100
        monthly_usage_percent = (
            self.monthly_cost / self.budget_config.monthly_budget_usd
        ) * 100

        is_over_budget = (
            self.daily_cost > self.budget_config.daily_budget_usd
            or self.monthly_cost > self.budget_config.monthly_budget_usd
        )

        is_near_limit = (
            daily_usage_percent >= self.budget_config.warn_threshold_percent
            or monthly_usage_percent >= self.budget_config.warn_threshold_percent
        )

        return BudgetStatus(
            daily_used_usd=self.daily_cost,
            daily_budget_usd=self.budget_config.daily_budget_usd,
            monthly_used_usd=self.monthly_cost,
            monthly_budget_usd=self.budget_config.monthly_budget_usd,
            daily_usage_percent=daily_usage_percent,
            monthly_usage_percent=monthly_usage_percent,
            is_over_budget=is_over_budget,
            is_near_limit=is_near_limit,
        )

    async def get_cost_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> CostSummary:
        """
        Get cost summary for a specific time period.

        Args:
            start_date: Start date for summary (default: beginning of current month)
            end_date: End date for summary (default: now)

        Returns:
            Cost summary for the specified period
        """
        if start_date is None:
            start_date = datetime.now(timezone.utc).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        if end_date is None:
            end_date = datetime.now(timezone.utc)

        # Filter records by date range
        period_records = [
            record
            for record in self.usage_records
            if start_date <= record.timestamp <= end_date
        ]

        # Calculate summary
        total_cost = sum(record.cost_usd for record in period_records)
        total_requests = len(period_records)
        successful_requests = sum(1 for record in period_records if record.success)
        failed_requests = total_requests - successful_requests
        total_input_tokens = sum(record.input_tokens for record in period_records)
        total_output_tokens = sum(record.output_tokens for record in period_records)

        # Cost by model
        cost_by_model = {}
        for record in period_records:
            cost_by_model[record.model] = (
                cost_by_model.get(record.model, 0.0) + record.cost_usd
            )

        # Cost by operation
        cost_by_operation = {}
        for record in period_records:
            cost_by_operation[record.operation] = (
                cost_by_operation.get(record.operation, 0.0) + record.cost_usd
            )

        return CostSummary(
            period_start=start_date,
            period_end=end_date,
            total_cost_usd=total_cost,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            cost_by_model=cost_by_model,
            cost_by_operation=cost_by_operation,
        )

    async def get_usage_records(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[UsageRecord]:
        """
        Get usage records for a specific time period.

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            limit: Maximum number of records to return

        Returns:
            List of usage records
        """
        records = self.usage_records

        # Filter by date range
        if start_date:
            records = [r for r in records if r.timestamp >= start_date]
        if end_date:
            records = [r for r in records if r.timestamp <= end_date]

        # Sort by timestamp (newest first)
        records.sort(key=lambda r: r.timestamp, reverse=True)

        # Apply limit
        if limit:
            records = records[:limit]

        return records

    async def reset_usage(
        self, reset_daily: bool = True, reset_monthly: bool = True
    ) -> None:
        """Reset usage tracking with specific options."""
        if reset_daily and reset_monthly:
            await self.reset_budget("all")
        elif reset_daily:
            await self.reset_budget("daily")
        elif reset_monthly:
            await self.reset_budget("monthly")

    async def reset_budget(self, reset_type: str = "daily"):
        """
        Reset budget tracking.

        Args:
            reset_type: Type of reset ("daily", "monthly", or "all")
        """
        if reset_type in ["daily", "all"]:
            self.daily_usage = 0.0
            self.daily_cost = 0.0
            self.last_daily_reset = datetime.now(timezone.utc).date()
            self.logger.info("Daily budget reset")

        if reset_type in ["monthly", "all"]:
            self.monthly_usage = 0.0
            self.monthly_cost = 0.0
            self.last_monthly_reset = datetime.now(timezone.utc).replace(day=1).date()
            self.logger.info("Monthly budget reset")

        if reset_type == "all":
            self.cost_by_model.clear()
            self.cost_by_operation.clear()
            self.logger.info("All budget tracking reset")

    async def _update_cost_tracking(self, record: UsageRecord):
        """Update internal cost tracking with new record."""
        # Update daily and monthly costs
        self.daily_usage += record.cost_usd
        self.daily_cost += record.cost_usd
        self.monthly_usage += record.cost_usd
        self.monthly_cost += record.cost_usd

        # Update cost by model
        self.cost_by_model[record.model] = (
            self.cost_by_model.get(record.model, 0.0) + record.cost_usd
        )

        # Update cost by operation
        self.cost_by_operation[record.operation] = (
            self.cost_by_operation.get(record.operation, 0.0) + record.cost_usd
        )

    async def _reset_usage_if_needed(self):
        """Reset usage if needed (alias for _reset_periodic_costs)."""
        await self._reset_periodic_costs()

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "daily_usage": self.daily_usage,
            "monthly_usage": self.monthly_usage,
            "daily_cost": self.daily_cost,
            "monthly_cost": self.monthly_cost,
            "total_records": len(self.usage_records),
            "cost_by_model": self.cost_by_model.copy(),
            "cost_by_operation": self.cost_by_operation.copy(),
        }

    def get_cost_breakdown(self, days: Optional[int] = None) -> Dict[str, Any]:
        """Get cost breakdown by category."""
        result = {
            "by_model": self.cost_by_model.copy(),
            "by_operation": self.cost_by_operation.copy(),
            "daily_total": self.daily_cost,
            "monthly_total": self.monthly_cost,
        }

        if days is not None:
            # Filter records by days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            period_records = [
                r for r in self.usage_records if r.timestamp >= cutoff_date
            ]

            # Calculate period totals
            total_cost = sum(r.cost_usd for r in period_records)
            result.update(
                {
                    "period_days": days,
                    "total_records": len(period_records),
                    "total_cost_usd": total_cost,
                }
            )

        return result

    async def _reset_periodic_costs(self):
        """Reset daily/monthly costs if needed."""
        current_date = datetime.now(timezone.utc).date()

        # Reset daily cost if needed
        if (
            self.budget_config.enable_daily_reset
            and current_date > self.last_daily_reset
        ):
            self.daily_usage = 0.0
            self.daily_cost = 0.0
            self.last_daily_reset = current_date

        # Reset monthly cost if needed
        current_month = current_date.replace(day=1)
        if (
            self.budget_config.enable_monthly_reset
            and current_month > self.last_monthly_reset
        ):
            self.monthly_usage = 0.0
            self.monthly_cost = 0.0
            self.last_monthly_reset = current_month

    async def _check_budget_alerts(self):
        """Check for budget alerts and log warnings."""
        budget_status = await self.get_budget_status()

        # Check for over budget
        if budget_status.is_over_budget:
            self.logger.error(
                f"Budget exceeded! Daily: {budget_status.daily_usage_percent:.1f}%, "
                f"Monthly: {budget_status.monthly_usage_percent:.1f}%"
            )

        # Check for near limit
        elif budget_status.is_near_limit:
            self.logger.warning(
                f"Approaching budget limit! Daily: {budget_status.daily_usage_percent:.1f}%, "
                f"Monthly: {budget_status.monthly_usage_percent:.1f}%"
            )

    class _StatsManager:
        """Simplified stats manager for cost tracking."""

        def __init__(self):
            self.budget_violations = 0
            self.total_requests = 0
            self.successful_requests = 0

        def get_base_stats(self) -> Dict[str, Any]:
            """Get base statistics."""
            return {
                "budget_violations": self.budget_violations,
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
            }
