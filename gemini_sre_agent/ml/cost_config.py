# gemini_sre_agent/ml/cost_config.py

"""
Cost tracking configuration and models.

This module defines the configuration classes and data models used by the
cost tracker for managing API usage costs and budget constraints.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class BudgetConfig:
    """
    Configuration for budget management and cost tracking.

    This class defines budget limits and thresholds for cost monitoring.
    """

    daily_budget_usd: float = 10.0
    monthly_budget_usd: float = 100.0
    warn_threshold_percent: float = 80.0
    alert_threshold_percent: float = 95.0
    enable_daily_reset: bool = True
    enable_monthly_reset: bool = True
    currency: str = "USD"

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "daily_budget_usd": self.daily_budget_usd,
            "monthly_budget_usd": self.monthly_budget_usd,
            "warn_threshold_percent": self.warn_threshold_percent,
            "alert_threshold_percent": self.alert_threshold_percent,
            "enable_daily_reset": self.enable_daily_reset,
            "enable_monthly_reset": self.enable_monthly_reset,
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "BudgetConfig":
        """Create configuration from dictionary."""
        return cls(**config_dict)

    def validate(self) -> bool:
        """Validate configuration parameters."""
        if self.daily_budget_usd <= 0:
            return False
        if self.monthly_budget_usd <= 0:
            return False
        if not 0 <= self.warn_threshold_percent <= 100:
            return False
        if not 0 <= self.alert_threshold_percent <= 100:
            return False
        if self.warn_threshold_percent >= self.alert_threshold_percent:
            return False
        return True


@dataclass
class UsageRecord:
    """
    Record of API usage and associated costs.

    This class represents a single usage record with timing and cost information.
    """

    timestamp: datetime
    operation: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert usage record to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "success": self.success,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, record_dict: Dict[str, Any]) -> "UsageRecord":
        """Create usage record from dictionary."""
        # Parse timestamp
        timestamp = record_dict["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif isinstance(timestamp, datetime):
            pass  # Already a datetime
        else:
            raise ValueError(f"Invalid timestamp format: {timestamp}")

        return cls(
            timestamp=timestamp,
            operation=record_dict["operation"],
            model=record_dict["model"],
            input_tokens=record_dict["input_tokens"],
            output_tokens=record_dict["output_tokens"],
            cost_usd=record_dict["cost_usd"],
            success=record_dict.get("success", True),
            error_message=record_dict.get("error_message"),
            metadata=record_dict.get("metadata", {}),
        )


@dataclass
class CostSummary:
    """
    Summary of costs for a specific time period.

    This class provides aggregated cost information for monitoring and reporting.
    """

    period_start: datetime
    period_end: datetime
    total_cost_usd: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_input_tokens: int
    total_output_tokens: int
    cost_by_model: Dict[str, float] = field(default_factory=dict)
    cost_by_operation: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert cost summary to dictionary."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_cost_usd": self.total_cost_usd,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "cost_by_model": self.cost_by_model,
            "cost_by_operation": self.cost_by_operation,
        }

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def average_cost_per_request(self) -> float:
        """Calculate average cost per request."""
        if self.total_requests == 0:
            return 0.0
        return self.total_cost_usd / self.total_requests


@dataclass
class BudgetStatus:
    """
    Current status of budget usage and limits.

    This class provides real-time budget status information.
    """

    daily_used_usd: float
    daily_budget_usd: float
    monthly_used_usd: float
    monthly_budget_usd: float
    daily_usage_percent: float
    monthly_usage_percent: float
    is_over_budget: bool
    is_near_limit: bool
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert budget status to dictionary."""
        return {
            "daily_used_usd": self.daily_used_usd,
            "daily_budget_usd": self.daily_budget_usd,
            "monthly_used_usd": self.monthly_used_usd,
            "monthly_budget_usd": self.monthly_budget_usd,
            "daily_usage_percent": self.daily_usage_percent,
            "monthly_usage_percent": self.monthly_usage_percent,
            "is_over_budget": self.is_over_budget,
            "is_near_limit": self.is_near_limit,
            "last_updated": self.last_updated.isoformat(),
        }

    @property
    def daily_remaining_usd(self) -> float:
        """Calculate remaining daily budget."""
        return max(0.0, self.daily_budget_usd - self.daily_used_usd)

    @property
    def monthly_remaining_usd(self) -> float:
        """Calculate remaining monthly budget."""
        return max(0.0, self.monthly_budget_usd - self.monthly_used_usd)
