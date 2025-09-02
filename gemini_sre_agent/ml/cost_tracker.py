"""
Cost tracking and budget management for Gemini API usage.

This module provides comprehensive cost tracking capabilities to monitor
and control Gemini API usage within daily and monthly budget constraints.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, Optional

from .cost_config import BudgetConfig, CostCalculator, UsageRecord
from .cost_statistics import CostStatisticsManager


class CostTracker:
    """
    Track and limit Gemini API costs with comprehensive budget controls.

    Provides real-time cost tracking, budget validation, and usage analytics
    with daily and monthly budget limits. Includes detailed logging and
    statistics for cost optimization.
    """

    def __init__(self, config: Optional[BudgetConfig] = None):
        self.config = config or BudgetConfig()
        self.logger = logging.getLogger(__name__)

        # Current usage tracking
        self.daily_usage = 0.0
        self.monthly_usage = 0.0
        self.current_date = date.today()
        self.current_month = (date.today().year, date.today().month)

        # Usage records for analytics
        self.usage_records: list[UsageRecord] = []
        self.max_records = 10000  # Keep last 10k records

        # Statistics manager
        self._stats_manager = CostStatisticsManager()

        self.logger.info(
            f"[COST_TRACKER] Initialized with daily budget: ${self.config.daily_budget_usd}, "
            f"monthly budget: ${self.config.monthly_budget_usd}"
        )

    async def check_budget(self, estimated_cost_usd: float) -> bool:
        """
        Check if request fits within budget constraints.

        Args:
            estimated_cost_usd: Estimated cost of the API request

        Returns:
            True if request is within budget limits, False otherwise
        """
        self._reset_usage_if_needed()

        # Check daily budget
        new_daily_total = self.daily_usage + estimated_cost_usd
        if new_daily_total > self.config.daily_budget_usd:
            self._stats_manager.record_budget_violation()
            self.logger.warning(
                f"[COST_TRACKER] Daily budget exceeded: "
                f"${new_daily_total:.6f} > ${self.config.daily_budget_usd}"
            )
            return False

        # Check monthly budget
        new_monthly_total = self.monthly_usage + estimated_cost_usd
        if new_monthly_total > self.config.monthly_budget_usd:
            self._stats_manager.record_budget_violation()
            self.logger.warning(
                f"[COST_TRACKER] Monthly budget exceeded: "
                f"${new_monthly_total:.6f} > ${self.config.monthly_budget_usd}"
            )
            return False

        # Check warning thresholds
        await self._check_warning_thresholds(new_daily_total, new_monthly_total)

        return True

    def estimate_cost(
        self, model_name: str, input_tokens: int, estimated_output_tokens: int = 500
    ) -> float:
        """
        Estimate cost for a Gemini API request.

        Args:
            model_name: Name of the Gemini model
            input_tokens: Number of input tokens
            estimated_output_tokens: Estimated output tokens (default: 500)

        Returns:
            Estimated cost in USD
        """
        total_cost = CostCalculator.calculate_request_cost(
            model_name, input_tokens, estimated_output_tokens, self.config
        )

        self.logger.debug(
            f"[COST_TRACKER] Cost estimate for {model_name}: "
            f"${total_cost:.6f} ({input_tokens}+{estimated_output_tokens} tokens)"
        )

        return total_cost

    async def record_actual_cost(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        request_id: Optional[str] = None,
        operation_type: Optional[str] = None,
    ) -> float:
        """
        Record actual cost after API call completion.

        Args:
            model_name: Name of the Gemini model used
            input_tokens: Actual input tokens consumed
            output_tokens: Actual output tokens generated
            request_id: Optional request identifier for tracking
            operation_type: Type of operation (e.g., "pattern_classification")

        Returns:
            Actual cost in USD
        """
        actual_cost = CostCalculator.calculate_request_cost(
            model_name, input_tokens, output_tokens, self.config
        )

        # Update usage counters
        self.daily_usage += actual_cost
        self.monthly_usage += actual_cost

        # Update statistics
        self._stats_manager.update_request_stats(input_tokens, output_tokens)

        # Create usage record
        usage_record = UsageRecord(
            timestamp=datetime.now(),
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=actual_cost,
            request_id=request_id,
            operation_type=operation_type,
        )

        # Add to records (with size limit)
        self.usage_records.append(usage_record)
        if len(self.usage_records) > self.max_records:
            self.usage_records = self.usage_records[-self.max_records :]

        self.logger.info(
            f"[COST_TRACKER] Recorded cost: ${actual_cost:.6f} "
            f"({model_name}, {input_tokens}+{output_tokens} tokens), "
            f"Daily: ${self.daily_usage:.4f}, Monthly: ${self.monthly_usage:.4f}"
        )

        return actual_cost

    def _reset_usage_if_needed(self) -> None:
        """Reset daily and monthly usage counters if period changed."""
        today = date.today()
        current_month = (today.year, today.month)

        # Reset daily usage if new day
        if today > self.current_date:
            self.daily_usage = 0.0
            self.current_date = today
            self.logger.info(f"[COST_TRACKER] Reset daily usage for {today}")

        # Reset monthly usage if new month
        if current_month != self.current_month:
            self.monthly_usage = 0.0
            self.current_month = current_month
            self.logger.info(
                f"[COST_TRACKER] Reset monthly usage for {current_month[0]}-{current_month[1]:02d}"
            )

    async def _check_warning_thresholds(
        self, new_daily_total: float, new_monthly_total: float
    ) -> None:
        """Check if usage crosses warning thresholds."""
        warn_threshold = self.config.warn_threshold_percent / 100.0

        # Daily warning
        daily_threshold = self.config.daily_budget_usd * warn_threshold
        if self.daily_usage < daily_threshold <= new_daily_total:
            self._stats_manager.record_warning_issued()
            self.logger.warning(
                f"[COST_TRACKER] Daily budget warning: "
                f"${new_daily_total:.4f} / ${self.config.daily_budget_usd} "
                f"({(new_daily_total/self.config.daily_budget_usd)*100:.1f}%)"
            )

        # Monthly warning
        monthly_threshold = self.config.monthly_budget_usd * warn_threshold
        if self.monthly_usage < monthly_threshold <= new_monthly_total:
            self._stats_manager.record_warning_issued()
            self.logger.warning(
                f"[COST_TRACKER] Monthly budget warning: "
                f"${new_monthly_total:.4f} / ${self.config.monthly_budget_usd} "
                f"({(new_monthly_total/self.config.monthly_budget_usd)*100:.1f}%)"
            )

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics and budget status."""
        self._reset_usage_if_needed()

        # Recent usage analysis (last 24 hours)
        recent_usage = self._stats_manager.analyze_recent_usage(self.usage_records)

        return self._stats_manager.build_usage_stats(
            self.daily_usage,
            self.monthly_usage,
            self.config.daily_budget_usd,
            self.config.monthly_budget_usd,
            self.current_date.isoformat(),
            f"{self.current_month[0]}-{self.current_month[1]:02d}",
            self.config.warn_threshold_percent,
            recent_usage,
        )

    def reset_usage(
        self, reset_daily: bool = True, reset_monthly: bool = False
    ) -> None:
        """Reset usage counters manually (for testing or admin purposes)."""
        if reset_daily:
            self.daily_usage = 0.0
            self.logger.info("[COST_TRACKER] Manually reset daily usage")

        if reset_monthly:
            self.monthly_usage = 0.0
            self.logger.info("[COST_TRACKER] Manually reset monthly usage")

    def get_cost_breakdown(self, days: int = 7) -> Dict[str, Any]:
        """Get detailed cost breakdown for analysis and optimization."""
        return self._stats_manager.get_cost_breakdown(self.usage_records, days)
