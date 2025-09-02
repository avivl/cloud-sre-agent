"""
Cost tracking configuration and data models for Gemini API usage.

This module provides configuration classes and data structures for
tracking and managing Gemini API costs and usage patterns.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class BudgetConfig:
    """Configuration for budget limits and cost tracking."""

    daily_budget_usd: float = 100.0
    monthly_budget_usd: float = 2000.0
    warn_threshold_percent: float = 80.0  # Warn at 80% of budget

    # Cost per model (USD per 1K tokens) - Based on Gemini pricing
    model_costs: Dict[str, Dict[str, float]] = field(
        default_factory=lambda: {
            "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
            "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
            "gemini-1.5-flash-8b": {"input": 0.0000375, "output": 0.00015},
            "gemini-2.0-flash": {"input": 0.000075, "output": 0.0003},
            "gemini-2.5-pro": {"input": 0.00125, "output": 0.005},
            "gemini-2.5-flash": {"input": 0.000075, "output": 0.0003},
        }
    )

    # Default to most expensive model for unknown models (safety)
    default_model_costs: Dict[str, float] = field(
        default_factory=lambda: {"input": 0.00125, "output": 0.005}
    )


@dataclass
class UsageRecord:
    """Record of a single API usage for tracking and analysis."""

    timestamp: datetime
    model_name: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    request_id: Optional[str] = None
    operation_type: Optional[str] = None  # e.g., "pattern_classification"


class CostAnalytics:
    """Helper class for cost analysis and statistics calculations."""

    @staticmethod
    def calculate_model_breakdown(records: list[UsageRecord]) -> Dict[str, Any]:
        """Calculate cost breakdown by model."""
        model_breakdown = {}

        for record in records:
            if record.model_name not in model_breakdown:
                model_breakdown[record.model_name] = {
                    "requests": 0,
                    "total_cost": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }

            model_data = model_breakdown[record.model_name]
            model_data["requests"] += 1
            model_data["total_cost"] += record.cost_usd
            model_data["input_tokens"] += record.input_tokens
            model_data["output_tokens"] += record.output_tokens

        # Calculate averages
        for model_data in model_breakdown.values():
            if model_data["requests"] > 0:
                model_data["avg_cost_per_request"] = (
                    model_data["total_cost"] / model_data["requests"]
                )

        return model_breakdown

    @staticmethod
    def calculate_operation_breakdown(records: list[UsageRecord]) -> Dict[str, Any]:
        """Calculate cost breakdown by operation type."""
        operation_breakdown = {}

        for record in records:
            op_type = record.operation_type or "unknown"
            if op_type not in operation_breakdown:
                operation_breakdown[op_type] = {"requests": 0, "total_cost": 0.0}

            operation_breakdown[op_type]["requests"] += 1
            operation_breakdown[op_type]["total_cost"] += record.cost_usd

        return operation_breakdown

    @staticmethod
    def find_top_model(records: list[UsageRecord]) -> str:
        """Find the most frequently used model."""
        if not records:
            return "none"

        model_usage = {}
        for record in records:
            if record.model_name not in model_usage:
                model_usage[record.model_name] = 0
            model_usage[record.model_name] += 1

        return max(model_usage.items(), key=lambda x: x[1])[0]


class CostCalculator:
    """Helper class for cost calculations and estimations."""

    @staticmethod
    def calculate_request_cost(
        model_name: str, input_tokens: int, output_tokens: int, config: BudgetConfig
    ) -> float:
        """Calculate cost for a specific request."""
        # Get model costs or use default
        if model_name in config.model_costs:
            costs = config.model_costs[model_name]
        else:
            costs = config.default_model_costs

        # Calculate costs per 1K tokens
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]

        return input_cost + output_cost

    @staticmethod
    def estimate_output_tokens(input_tokens: int, multiplier: float = 0.5) -> int:
        """Estimate output tokens based on input tokens."""
        return max(500, int(input_tokens * multiplier))
