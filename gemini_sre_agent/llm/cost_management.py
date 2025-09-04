"""
Dynamic Cost Management System for Multi-Provider LLM Operations.

This module provides comprehensive cost management including dynamic pricing,
optimization strategies, budget enforcement, and usage analytics.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from .base import ProviderType

logger = logging.getLogger(__name__)


class BudgetPeriod(str, Enum):
    """Budget period types."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class EnforcementPolicy(str, Enum):
    """Budget enforcement policies."""
    WARN = "warn"
    SOFT_LIMIT = "soft_limit"
    HARD_LIMIT = "hard_limit"


class OptimizationStrategy(str, Enum):
    """Cost optimization strategies."""
    BUDGET = "budget"
    PERFORMANCE = "performance"
    BALANCED = "balanced"


@dataclass
class PricingInfo:
    """Pricing information for a model."""
    model_name: str
    provider: ProviderType
    input_cost_per_1k: float
    output_cost_per_1k: float
    last_updated: datetime
    ttl_seconds: int = 3600  # 1 hour default TTL


@dataclass
class UsageRecord:
    """Record of model usage and cost."""
    timestamp: datetime
    provider: ProviderType
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    request_id: str
    operation_type: str = "unknown"


@dataclass
class BudgetAlert:
    """Budget alert information."""
    timestamp: datetime
    budget_period: BudgetPeriod
    current_spend: float
    budget_limit: float
    threshold_percentage: float
    alert_type: str


class CostManagementConfig(BaseModel):
    """Configuration for cost management system."""
    
    budget_limit: float = Field(100.0, gt=0, description="Budget limit in USD")
    budget_period: BudgetPeriod = BudgetPeriod.MONTHLY
    alert_thresholds: List[float] = Field(
        default=[0.5, 0.8, 0.9, 1.0],
        description="Alert thresholds as percentages"
    )
    enforcement_policy: EnforcementPolicy = EnforcementPolicy.WARN
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.BALANCED
    refresh_interval: int = Field(3600, gt=0, description="Pricing refresh interval in seconds")
    max_records: int = Field(10000, gt=0, description="Maximum usage records to keep")


class DynamicCostManager:
    """Manages dynamic pricing and cost tracking across providers."""
    
    def __init__(
        self,
        config: CostManagementConfig
    ):
        self.config = config
        # Simplified for now - these would be passed in a real implementation
        self.provider_factory = None
        self.model_registry = None
        
        # Pricing cache: provider -> model -> PricingInfo
        self.pricing_cache: Dict[ProviderType, Dict[str, PricingInfo]] = {}
        self.usage_records: List[UsageRecord] = []
        self.budget_alerts: List[BudgetAlert] = []
        
        # Background task for pricing updates
        self._refresh_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Initialize with default pricing
        self._initialize_default_pricing()
    
    def _initialize_default_pricing(self) -> None:
        """Initialize with default pricing for known providers."""
        default_pricing = {
            ProviderType.OPENAI: {
                "gpt-4": PricingInfo("gpt-4", ProviderType.OPENAI, 0.03, 0.06, datetime.now()),
                "gpt-3.5-turbo": PricingInfo("gpt-3.5-turbo", ProviderType.OPENAI, 0.0015, 0.002, datetime.now()),
            },
            ProviderType.CLAUDE: {
                "claude-3-opus": PricingInfo("claude-3-opus", ProviderType.CLAUDE, 0.015, 0.075, datetime.now()),
                "claude-3-sonnet": PricingInfo("claude-3-sonnet", ProviderType.CLAUDE, 0.003, 0.015, datetime.now()),
            },
            ProviderType.GEMINI: {
                "gemini-1.5-pro": PricingInfo("gemini-1.5-pro", ProviderType.GEMINI, 0.00125, 0.005, datetime.now()),
                "gemini-1.5-flash": PricingInfo("gemini-1.5-flash", ProviderType.GEMINI, 0.000075, 0.0003, datetime.now()),
            },
        }
        
        for provider, models in default_pricing.items():
            self.pricing_cache[provider] = models
    
    async def start(self) -> None:
        """Start the cost management system."""
        if self._running:
            return
        
        self._running = True
        self._refresh_task = asyncio.create_task(self._refresh_pricing_loop())
        logger.info("Dynamic cost management system started")
    
    async def stop(self) -> None:
        """Stop the cost management system."""
        self._running = False
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        logger.info("Dynamic cost management system stopped")
    
    async def _refresh_pricing_loop(self) -> None:
        """Background task to refresh pricing data."""
        while self._running:
            try:
                await self._refresh_pricing()
                await asyncio.sleep(self.config.refresh_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error refreshing pricing: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def _refresh_pricing(self) -> None:
        """Refresh pricing data from providers."""
        for provider_type in ProviderType:
            try:
                # Simplified for now - in real implementation would get pricing from provider
                # provider = self.provider_factory.get_provider(provider_type)
                # if provider:
                #     await self._update_provider_pricing(provider_type, provider)
                pass  # Placeholder for now
            except Exception as e:
                logger.warning(f"Failed to refresh pricing for {provider_type}: {e}")
    
    async def _update_provider_pricing(self, provider_type: ProviderType, provider) -> None:
        """Update pricing for a specific provider."""
        # This would integrate with provider-specific pricing APIs
        # For now, we'll use the provider's cost_estimate method as a reference
        logger.debug(f"Updating pricing for {provider_type}")
        
        # In a real implementation, this would call provider-specific pricing APIs
        # For now, we'll keep the default pricing and just update timestamps
        if provider_type in self.pricing_cache:
            for _, pricing_info in self.pricing_cache[provider_type].items():
                pricing_info.last_updated = datetime.now()
    
    def get_pricing(self, provider: ProviderType, model: str) -> Optional[PricingInfo]:
        """Get current pricing for a model."""
        if provider not in self.pricing_cache:
            return None
        
        pricing_info = self.pricing_cache[provider].get(model)
        if not pricing_info:
            return None
        
        # Check if pricing is still valid
        if datetime.now() - pricing_info.last_updated > timedelta(seconds=pricing_info.ttl_seconds):
            logger.warning(f"Pricing for {provider}:{model} is stale")
        
        return pricing_info
    
    def estimate_cost(self, provider: ProviderType, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a request."""
        pricing = self.get_pricing(provider, model)
        if not pricing:
            logger.warning(f"No pricing data for {provider}:{model}, using default estimate")
            return (input_tokens + output_tokens) * 0.001  # Default $1 per 1k tokens
        
        input_cost = (input_tokens / 1000) * pricing.input_cost_per_1k
        output_cost = (output_tokens / 1000) * pricing.output_cost_per_1k
        return input_cost + output_cost
    
    def record_usage(self, usage: UsageRecord) -> None:
        """Record usage and cost."""
        self.usage_records.append(usage)
        
        # Keep only recent records
        if len(self.usage_records) > self.config.max_records:
            self.usage_records = self.usage_records[-self.config.max_records:]
        
        # Check budget thresholds
        self._check_budget_thresholds()
    
    def _check_budget_thresholds(self) -> None:
        """Check if budget thresholds have been exceeded."""
        current_spend = self.get_current_spend()
        budget_limit = self.config.budget_limit
        
        for threshold in self.config.alert_thresholds:
            threshold_amount = budget_limit * threshold
            
            if current_spend >= threshold_amount:
                # Check if we've already sent an alert for this threshold
                recent_alerts = [
                    alert for alert in self.budget_alerts
                    if alert.threshold_percentage == threshold
                    and (datetime.now() - alert.timestamp).total_seconds() < 3600  # 1 hour
                ]
                
                if not recent_alerts:
                    alert = BudgetAlert(
                        timestamp=datetime.now(),
                        budget_period=self.config.budget_period,
                        current_spend=current_spend,
                        budget_limit=budget_limit,
                        threshold_percentage=threshold,
                        alert_type="budget_threshold"
                    )
                    self.budget_alerts.append(alert)
                    logger.warning(f"Budget alert: {threshold*100}% threshold exceeded (${current_spend:.2f}/${budget_limit:.2f})")
    
    def get_current_spend(self) -> float:
        """Get current spending for the budget period."""
        now = datetime.now()
        
        if self.config.budget_period == BudgetPeriod.DAILY:
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.config.budget_period == BudgetPeriod.WEEKLY:
            start_time = now - timedelta(days=7)
        else:  # MONTHLY
            start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        recent_usage = [
            record for record in self.usage_records
            if record.timestamp >= start_time
        ]
        
        return sum(record.cost_usd for record in recent_usage)
    
    def get_usage_analytics(self) -> Dict[str, Any]:
        """Get usage analytics and trends."""
        if not self.usage_records:
            return {"total_requests": 0, "total_cost": 0.0, "cost_by_provider": {}}
        
        total_cost = sum(record.cost_usd for record in self.usage_records)
        cost_by_provider = {}
        
        for record in self.usage_records:
            provider = record.provider.value
            if provider not in cost_by_provider:
                cost_by_provider[provider] = {"cost": 0.0, "requests": 0}
            cost_by_provider[provider]["cost"] += record.cost_usd
            cost_by_provider[provider]["requests"] += 1
        
        return {
            "total_requests": len(self.usage_records),
            "total_cost": total_cost,
            "cost_by_provider": cost_by_provider,
            "average_cost_per_request": total_cost / len(self.usage_records) if self.usage_records else 0.0,
            "current_budget_usage": self.get_current_spend() / self.config.budget_limit,
        }
    
    def can_make_request(self, estimated_cost: float) -> Tuple[bool, str]:
        """Check if a request can be made within budget constraints."""
        current_spend = self.get_current_spend()
        total_after_request = current_spend + estimated_cost
        
        if total_after_request > self.config.budget_limit:
            if self.config.enforcement_policy == EnforcementPolicy.HARD_LIMIT:
                return False, f"Request would exceed budget limit (${total_after_request:.2f} > ${self.config.budget_limit:.2f})"
            elif self.config.enforcement_policy == EnforcementPolicy.SOFT_LIMIT:
                return True, f"Warning: Request would exceed budget limit (${total_after_request:.2f} > ${self.config.budget_limit:.2f})"
        
        return True, "Request within budget"
