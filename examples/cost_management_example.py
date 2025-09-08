#!/usr/bin/env python3
"""
Cost Management System Example

This example demonstrates how to use the comprehensive cost management system
for tracking, optimizing, and managing costs across multiple LLM providers.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from gemini_sre_agent.llm.config import CostConfig
from gemini_sre_agent.llm.cost_management_integration import (
    create_cost_manager_from_config,
    create_default_cost_manager,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def basic_cost_management_example():
    """Basic cost management example with default settings."""
    logger.info("=== Basic Cost Management Example ===")

    # Create a default cost manager
    cost_manager = create_default_cost_manager(
        budget_limit=50.0, budget_period="monthly"
    )

    # Estimate request cost
    cost = await cost_manager.estimate_request_cost("openai", "gpt-4", 1000, 500)
    logger.info(f"Estimated cost for GPT-4 request: ${cost:.4f}")

    # Check if request is within budget
    can_make, message = await cost_manager.can_make_request(
        "openai", "gpt-4", 1000, 500
    )
    logger.info(f"Can make request: {can_make} - {message}")

    # Get optimal provider
    provider, model, estimated_cost = await cost_manager.get_optimal_provider(
        "text", 1000, 500
    )
    logger.info(f"Optimal provider: {provider}/{model} (${estimated_cost:.4f})")

    # Record a completed request
    cost_manager.record_request(
        provider="openai",
        model="gpt-4",
        input_tokens=1000,
        output_tokens=500,
        cost_usd=0.06,
        success=True,
        response_time_ms=1500,
    )

    # Get budget status
    budget_status = cost_manager.get_budget_status()
    logger.info(
        f"Budget status: {budget_status['status']} - ${budget_status['current_spend']:.2f}/${budget_status['budget_limit']:.2f}"
    )

    # Get cost analytics
    analytics = cost_manager.get_cost_analytics()
    if "error" in analytics:
        logger.info(f"Analytics: {analytics['error']}")
    else:
        logger.info(f"Total requests: {analytics['summary']['total_requests']}")
        logger.info(f"Total cost: ${analytics['summary']['total_cost']:.2f}")


async def advanced_cost_management_example():
    """Advanced cost management example with custom configuration."""
    logger.info("\n=== Advanced Cost Management Example ===")

    # Create custom cost configuration
    cost_config = CostConfig(
        # Budget settings
        monthly_budget=100.0,
        budget_period="monthly",
        enforcement_policy="soft_limit",
        enable_cost_tracking=True,
        auto_reset=True,
        rollover_unused=True,
        max_rollover=25.0,
        cost_alerts=[50, 75, 90, 100],
        # Optimization settings
        enable_optimization=True,
        optimization_strategy="balanced",
        cost_weight=0.4,
        performance_weight=0.3,
        quality_weight=0.3,
        # Analytics settings
        enable_analytics=True,
        retention_days=180,
        cost_optimization_threshold=0.05,
        # Pricing settings
        refresh_interval=1800,  # 30 minutes
        max_records=50000,
    )

    # Create cost manager from config
    cost_manager = create_cost_manager_from_config(cost_config)

    # Simulate multiple requests
    requests = [
        ("openai", "gpt-4", 2000, 1000, 0.12),
        ("openai", "gpt-3.5-turbo", 1500, 800, 0.004),
        ("claude", "claude-3-sonnet", 1800, 900, 0.008),
        ("gemini", "gemini-1.5-pro", 1200, 600, 0.003),
    ]

    for provider, model, input_tokens, output_tokens, cost in requests:
        # Check if request is allowed
        can_make, message = await cost_manager.can_make_request(
            provider, model, input_tokens, output_tokens
        )

        if can_make:
            # Record the request
            cost_manager.record_request(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                success=True,
                response_time_ms=1200,
            )
            logger.info(f"Recorded request: {provider}/{model} - ${cost:.4f}")
        else:
            logger.warning(f"Request blocked: {provider}/{model} - {message}")

    # Get comprehensive analytics
    logger.info("\n--- Cost Analytics ---")
    analytics = cost_manager.get_cost_analytics()
    if "error" in analytics:
        logger.info(f"Analytics: {analytics['error']}")
    else:
        logger.info(f"Total cost: ${analytics['summary']['total_cost']:.2f}")
        logger.info(f"Total requests: {analytics['summary']['total_requests']}")
        logger.info(
            f"Average cost per request: ${analytics['summary']['avg_cost_per_request']:.4f}"
        )

        # Provider breakdown
        logger.info("\n--- Provider Breakdown ---")
        for provider, data in analytics["provider_breakdown"].items():
            logger.info(
                f"{provider}: ${data['cost']:.2f} ({data['requests']} requests)"
            )

    # Get optimization recommendations
    logger.info("\n--- Optimization Recommendations ---")
    recommendations = cost_manager.get_optimization_recommendations(lookback_days=7)
    for rec in recommendations[:3]:  # Show top 3
        logger.info(
            f"{rec['type']}: {rec['description']} (Potential savings: ${rec['potential_savings']:.2f})"
        )

    # Get budget forecast
    logger.info("\n--- Budget Forecast ---")
    forecast = cost_manager.get_budget_forecast(days_ahead=30)
    if "error" not in forecast:
        logger.info(f"Current daily rate: ${forecast['daily_rate']:.2f}")
        logger.info(
            f"Projected spend in 30 days: ${forecast['forecast'][-1]['projected_spend']:.2f}"
        )
        if forecast["days_until_budget_exhausted"]:
            logger.info(
                f"Budget will be exhausted in {forecast['days_until_budget_exhausted']} days"
            )

    # Get system health
    logger.info("\n--- System Health ---")
    health = cost_manager.get_system_health()
    logger.info(f"Status: {health['status']}")
    logger.info(f"Budget status: {health['budget_status']}")
    if health["issues"]:
        logger.warning(f"Issues: {', '.join(health['issues'])}")


async def cost_optimization_example():
    """Example demonstrating cost optimization features."""
    logger.info("\n=== Cost Optimization Example ===")

    cost_manager = create_default_cost_manager(budget_limit=25.0)

    # Simulate usage patterns that would trigger optimization recommendations
    usage_patterns = [
        # Expensive model usage
        ("openai", "gpt-4", 1000, 500, 0.06),
        ("openai", "gpt-4", 1200, 600, 0.072),
        ("openai", "gpt-4", 800, 400, 0.048),
        # Cheaper alternative usage
        ("openai", "gpt-3.5-turbo", 1000, 500, 0.002),
        ("openai", "gpt-3.5-turbo", 1200, 600, 0.0024),
        # Mixed provider usage
        ("claude", "claude-3-sonnet", 1000, 500, 0.008),
        ("gemini", "gemini-1.5-pro", 1000, 500, 0.003),
    ]

    for provider, model, input_tokens, output_tokens, cost in usage_patterns:
        cost_manager.record_request(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            success=True,
        )

    # Get provider comparison
    logger.info("--- Provider Comparison ---")
    comparison = cost_manager.get_provider_comparison()
    for comp in comparison:
        logger.info(
            f"{comp['provider']}: ${comp['avg_cost_per_request']:.4f}/request, "
            f"{comp['request_count']} requests, efficiency: {comp['cost_efficiency_score']:.2f}"
        )

    # Get cost trends
    logger.info("\n--- Cost Trends ---")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    trends = cost_manager.get_cost_trends(start_date, end_date, "daily")

    for trend in trends[-3:]:  # Show last 3 days
        logger.info(
            f"{trend['period']}: ${trend['total_cost']:.2f} "
            f"({trend['request_count']} requests, "
            f"{trend['cost_change_percent']:+.1f}% change)"
        )


async def main():
    """Run all cost management examples."""
    try:
        await basic_cost_management_example()
        await advanced_cost_management_example()
        await cost_optimization_example()

        logger.info("\n=== All Examples Completed Successfully ===")

    except Exception as e:
        logger.error(f"Error running examples: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
