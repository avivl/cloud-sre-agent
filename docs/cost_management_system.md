# Dynamic Cost Management System

## Overview

The Dynamic Cost Management System provides comprehensive cost tracking, optimization, and budget management for multi-provider LLM operations. It enables real-time cost monitoring, intelligent provider selection, budget enforcement, and detailed analytics.

## Key Features

- **Dynamic Pricing**: Real-time pricing data with automatic refresh and caching
- **Cost Optimization**: Intelligent provider and model selection based on cost, performance, and quality
- **Budget Management**: Flexible budget tracking with alerts and enforcement policies
- **Analytics & Reporting**: Comprehensive cost analytics, trends, and optimization recommendations
- **Multi-Provider Support**: Unified interface for managing costs across all LLM providers

## Architecture

The system consists of four main components:

1. **DynamicCostManager**: Manages real-time pricing data and cost estimation
2. **CostOptimizer**: Provides intelligent provider and model selection
3. **BudgetManager**: Tracks spending, enforces budgets, and manages alerts
4. **CostAnalytics**: Generates insights, trends, and optimization recommendations

## Quick Start

### Basic Usage

```python
from gemini_sre_agent.llm.cost_management_integration import create_default_cost_manager

# Create a cost manager with default settings
cost_manager = create_default_cost_manager(
    budget_limit=100.0,
    budget_period="monthly"
)

# Estimate request cost
cost = await cost_manager.estimate_request_cost("openai", "gpt-4", 1000, 500)

# Check if request is within budget
can_make, message = await cost_manager.can_make_request("openai", "gpt-4", 1000, 500)

# Get optimal provider for a request
provider, model, score = await cost_manager.get_optimal_provider("text", 1000, 500)

# Record a completed request
cost_manager.record_request(
    "openai", "gpt-4", 1000, 500, 0.06, True, 1500
)
```

### Advanced Configuration

```python
from gemini_sre_agent.llm.cost_management import CostManagementConfig, BudgetPeriod, EnforcementPolicy
from gemini_sre_agent.llm.budget_manager import BudgetConfig
from gemini_sre_agent.llm.cost_optimizer import OptimizationConfig
from gemini_sre_agent.llm.cost_analytics import AnalyticsConfig
from gemini_sre_agent.llm.cost_management_integration import IntegratedCostManager

# Configure cost management
cost_config = CostManagementConfig(
    cache_duration_minutes=60,
    refresh_interval_minutes=30,
    enable_auto_refresh=True,
    fallback_pricing=True
)

# Configure budget management
budget_config = BudgetConfig(
    budget_limit=500.0,
    budget_period=BudgetPeriod.WEEKLY,
    alert_thresholds=[0.5, 0.8, 0.9, 1.0],
    enforcement_policy=EnforcementPolicy.SOFT_LIMIT,
    auto_reset=True,
    rollover_unused=True,
    max_rollover=100.0
)

# Configure optimization
optimization_config = OptimizationConfig(
    enable_optimization=True,
    cost_weight=0.4,
    performance_weight=0.3,
    quality_weight=0.3,
    min_confidence_threshold=0.7
)

# Configure analytics
analytics_config = AnalyticsConfig(
    retention_days=90,
    aggregation_intervals=["hourly", "daily", "weekly", "monthly"],
    cost_optimization_threshold=0.1
)

# Create integrated manager
cost_manager = IntegratedCostManager(
    cost_config=cost_config,
    budget_config=budget_config,
    optimization_config=optimization_config,
    analytics_config=analytics_config
)
```

## Components

### DynamicCostManager

Manages real-time pricing data and provides cost estimation.

#### Key Features

- **Real-time Pricing**: Fetches and caches current pricing from all providers
- **Automatic Refresh**: Periodically updates pricing data
- **Fallback Pricing**: Uses default pricing when real-time data is unavailable
- **Cost Estimation**: Calculates request costs based on token usage

#### Usage

```python
from gemini_sre_agent.llm.cost_management import DynamicCostManager, CostManagementConfig

config = CostManagementConfig(
    cache_duration_minutes=60,
    refresh_interval_minutes=30,
    enable_auto_refresh=True
)

cost_manager = DynamicCostManager(config)

# Estimate cost
cost = await cost_manager.estimate_cost("openai", "gpt-4", 1000, 500)

# Get pricing info
pricing = cost_manager.get_pricing_info("openai", "gpt-4")

# Refresh pricing data
await cost_manager.refresh_pricing_data()
```

### CostOptimizer

Provides intelligent provider and model selection based on cost, performance, and quality.

#### Key Features

- **Multi-factor Optimization**: Considers cost, performance, and quality
- **Provider Comparison**: Evaluates all available providers
- **Confidence Scoring**: Provides confidence levels for recommendations
- **Customizable Weights**: Adjustable importance of different factors

#### Usage

```python
from gemini_sre_agent.llm.cost_optimizer import CostOptimizer, OptimizationConfig

config = OptimizationConfig(
    enable_optimization=True,
    cost_weight=0.4,
    performance_weight=0.3,
    quality_weight=0.3
)

optimizer = CostOptimizer(config)

# Get optimal provider
provider, model, score = await optimizer.get_optimal_provider(
    "text", 1000, 500, {"max_response_time": 2000}
)

# Get optimization recommendations
recommendations = optimizer.get_optimization_recommendations(usage_data)
```

### BudgetManager

Tracks spending, enforces budgets, and manages alerts.

#### Key Features

- **Flexible Periods**: Daily, weekly, or monthly budget periods
- **Alert Thresholds**: Configurable spending alerts
- **Enforcement Policies**: Hard limits, soft limits, or warnings
- **Rollover Support**: Optional budget rollover between periods
- **Detailed Tracking**: Comprehensive spending breakdowns

#### Usage

```python
from gemini_sre_agent.llm.budget_manager import BudgetManager, BudgetConfig, BudgetPeriod, EnforcementPolicy

config = BudgetConfig(
    budget_limit=100.0,
    budget_period=BudgetPeriod.MONTHLY,
    alert_thresholds=[0.5, 0.8, 0.9, 1.0],
    enforcement_policy=EnforcementPolicy.WARN,
    auto_reset=True
)

budget_manager = BudgetManager(config)

# Check if request is within budget
can_make, message = budget_manager.can_make_request(10.0)

# Get budget status
status = budget_manager.get_budget_status()

# Get spending breakdown
breakdown = budget_manager.get_spending_breakdown()

# Get budget forecast
forecast = budget_manager.get_budget_forecast(30)
```

### CostAnalytics

Generates insights, trends, and optimization recommendations.

#### Key Features

- **Cost Trends**: Historical cost analysis with multiple time intervals
- **Provider Comparison**: Detailed provider performance analysis
- **Optimization Recommendations**: AI-powered cost optimization suggestions
- **Usage Patterns**: Analysis of usage patterns and peak times
- **Export Capabilities**: Data export in multiple formats

#### Usage

```python
from gemini_sre_agent.llm.cost_analytics import CostAnalytics, AnalyticsConfig

config = AnalyticsConfig(
    retention_days=90,
    cost_optimization_threshold=0.1
)

analytics = CostAnalytics(config)

# Get cost trends
trends = analytics.get_cost_trends(
    start_date, end_date, "daily"
)

# Get provider comparison
comparisons = analytics.get_provider_comparison()

# Get optimization recommendations
recommendations = analytics.get_optimization_recommendations(30)

# Get cost summary
summary = analytics.get_cost_summary()
```

## Budget Management

### Budget Periods

- **Daily**: Budget resets every 24 hours
- **Weekly**: Budget resets every Monday
- **Monthly**: Budget resets on the 1st of each month

### Alert Thresholds

Configure multiple alert thresholds as percentages (0.0 to 1.0):

```python
alert_thresholds = [0.5, 0.8, 0.9, 1.0]  # 50%, 80%, 90%, 100%
```

### Enforcement Policies

- **WARN**: Only send alerts, no request blocking
- **SOFT_LIMIT**: Send warnings but allow requests
- **HARD_LIMIT**: Block requests when budget is exceeded

### Budget Rollover

Enable rollover to carry unused budget to the next period:

```python
budget_config = BudgetConfig(
    rollover_unused=True,
    max_rollover=50.0  # Maximum rollover amount
)
```

## Cost Optimization

### Optimization Factors

The system considers three factors when optimizing:

1. **Cost** (default weight: 0.4): Lower cost is better
2. **Performance** (default weight: 0.3): Faster response times are better
3. **Quality** (default weight: 0.3): Higher success rates are better

### Customizing Weights

```python
optimization_config = OptimizationConfig(
    cost_weight=0.5,      # Prioritize cost
    performance_weight=0.2,  # Less emphasis on performance
    quality_weight=0.3    # Standard quality emphasis
)
```

### Optimization Recommendations

The system provides several types of recommendations:

- **Provider Switch**: Switch to a cheaper provider with similar quality
- **Model Switch**: Use a more cost-effective model
- **Usage Pattern**: Optimize usage patterns (e.g., off-peak scheduling)
- **Budget Adjustment**: Adjust budget limits based on usage patterns

## Analytics and Reporting

### Cost Trends

Analyze cost trends over time with multiple aggregation intervals:

```python
# Daily trends
trends = analytics.get_cost_trends(start_date, end_date, "daily")

# Weekly trends
trends = analytics.get_cost_trends(start_date, end_date, "weekly")
```

### Provider Comparison

Compare providers across multiple metrics:

```python
comparisons = analytics.get_provider_comparison()

for comp in comparisons:
    print(f"Provider: {comp.provider}")
    print(f"Total Cost: ${comp.total_cost:.2f}")
    print(f"Avg Cost/Request: ${comp.avg_cost_per_request:.4f}")
    print(f"Success Rate: {comp.success_rate:.1f}%")
    print(f"Efficiency Score: {comp.cost_efficiency_score:.3f}")
```

### Spending Breakdown

Get detailed spending breakdowns:

```python
breakdown = cost_manager.get_spending_breakdown()

print(f"Total Spend: ${breakdown['total_spend']:.2f}")
print("By Provider:")
for provider, data in breakdown['by_provider'].items():
    print(f"  {provider}: ${data['cost']:.2f} ({data['requests']} requests)")
```

### Budget Forecast

Predict future spending based on current patterns:

```python
forecast = cost_manager.get_budget_forecast(30)  # Next 30 days

print(f"Current Daily Rate: ${forecast['daily_rate']:.2f}")
print(f"Days Until Budget Exhausted: {forecast['days_until_budget_exhausted']}")
```

## Integration Examples

### With LLM Provider Factory

```python
from gemini_sre_agent.llm.provider_factory import LLMProviderFactory
from gemini_sre_agent.llm.cost_management_integration import create_default_cost_manager

# Create cost manager
cost_manager = create_default_cost_manager(budget_limit=200.0)

# Create provider factory
provider_factory = LLMProviderFactory()

# Get optimal provider for request
provider_name, model, score = await cost_manager.get_optimal_provider(
    "text", 1000, 500
)

# Create provider instance
provider = provider_factory.get_provider(provider_name)

# Make request
response = await provider.generate(request)

# Record usage
cost_manager.record_request(
    provider_name, model,
    request.input_tokens, response.output_tokens,
    response.cost_usd, response.success,
    response.response_time_ms
)
```

### With Strategy Manager

```python
from gemini_sre_agent.llm.strategy_manager import StrategyManager
from gemini_sre_agent.llm.cost_management_integration import create_default_cost_manager

# Create cost manager
cost_manager = create_default_cost_manager()

# Create strategy manager
strategy_manager = StrategyManager()

# Get cost-optimized strategy
strategy = strategy_manager.get_strategy("cost_optimized")

# Enhance strategy with cost manager
strategy.cost_manager = cost_manager

# Use strategy for model selection
selected_model = strategy.select_model(request, available_models)
```

## Monitoring and Alerts

### System Health

Monitor overall system health:

```python
health = cost_manager.get_system_health()

print(f"Status: {health['status']}")
print(f"Budget Status: {health['budget_status']}")
print(f"Issues: {health['issues']}")
print(f"Recommendations: {health['recommendations_count']}")
```

### Recent Alerts

Get recent budget alerts:

```python
alerts = cost_manager.get_recent_alerts(24)  # Last 24 hours

for alert in alerts:
    print(f"Alert: {alert['alert_type']}")
    print(f"Threshold: {alert['threshold_percentage']*100}%")
    print(f"Current Spend: ${alert['current_spend']:.2f}")
    print(f"Budget Limit: ${alert['budget_limit']:.2f}")
```

## Best Practices

### 1. Set Appropriate Budget Limits

- Start with conservative limits and adjust based on usage patterns
- Use rollover for predictable workloads
- Set multiple alert thresholds for early warning

### 2. Monitor Cost Trends

- Regularly review cost trends to identify patterns
- Use provider comparison to optimize spending
- Implement optimization recommendations

### 3. Use Optimization Features

- Enable cost optimization for automatic provider selection
- Review optimization recommendations regularly
- Adjust optimization weights based on your priorities

### 4. Implement Proper Error Handling

```python
try:
    can_make, message = await cost_manager.can_make_request("openai", "gpt-4", 1000, 500)
    if not can_make:
        logger.warning(f"Request blocked: {message}")
        # Handle budget exceeded
        return
except Exception as e:
    logger.error(f"Cost check failed: {e}")
    # Fallback to default behavior
```

### 5. Regular Maintenance

- Refresh pricing data regularly
- Clean up old analytics data
- Review and update budget configurations
- Monitor system health

## Troubleshooting

### Common Issues

1. **Pricing Data Not Available**
   - Check network connectivity
   - Verify provider API keys
   - Enable fallback pricing

2. **Budget Alerts Not Working**
   - Verify alert thresholds are set correctly
   - Check that usage records are being recorded
   - Ensure budget period is configured properly

3. **Optimization Recommendations Empty**
   - Ensure sufficient usage data is available
   - Check optimization thresholds
   - Verify provider comparison data

### Debug Mode

Enable debug logging for detailed information:

```python
import logging

logging.getLogger("gemini_sre_agent.llm.cost_management").setLevel(logging.DEBUG)
```

## API Reference

### IntegratedCostManager

#### Methods

- `estimate_request_cost(provider, model, input_tokens, output_tokens)`: Estimate request cost
- `can_make_request(provider, model, input_tokens, output_tokens)`: Check budget constraints
- `get_optimal_provider(model_type, input_tokens, output_tokens, requirements)`: Get optimal provider
- `record_request(provider, model, input_tokens, output_tokens, cost, success, response_time)`: Record request
- `get_budget_status()`: Get current budget status
- `get_cost_analytics(start_date, end_date)`: Get cost analytics
- `get_optimization_recommendations(lookback_days)`: Get optimization recommendations
- `get_provider_comparison(start_date, end_date)`: Get provider comparison
- `get_cost_trends(start_date, end_date, interval)`: Get cost trends
- `get_spending_breakdown()`: Get spending breakdown
- `get_budget_forecast(days_ahead)`: Get budget forecast
- `get_recent_alerts(hours)`: Get recent alerts
- `refresh_pricing_data()`: Refresh pricing data
- `get_system_health()`: Get system health status
- `export_analytics_data(format)`: Export analytics data

### Configuration Classes

- `CostManagementConfig`: Cost management configuration
- `BudgetConfig`: Budget management configuration
- `OptimizationConfig`: Cost optimization configuration
- `AnalyticsConfig`: Analytics configuration

### Data Classes

- `UsageRecord`: Individual usage record
- `ModelPricing`: Model pricing information
- `BudgetAlert`: Budget alert information
- `BudgetStatus`: Current budget status
- `CostTrend`: Cost trend data
- `ProviderComparison`: Provider comparison data
- `OptimizationRecommendation`: Optimization recommendation

## Performance Considerations

### Caching

- Pricing data is cached to reduce API calls
- Cache duration is configurable (default: 60 minutes)
- Automatic refresh prevents stale data

### Memory Usage

- Usage records are retained based on retention policy
- Old records are automatically cleaned up
- Analytics data is aggregated to reduce memory usage

### Network Efficiency

- Batch pricing updates when possible
- Use fallback pricing to avoid blocking requests
- Implement retry logic for failed pricing updates

## Security Considerations

### API Keys

- Store provider API keys securely
- Use environment variables or secure key management
- Rotate keys regularly

### Data Privacy

- Usage data may contain sensitive information
- Implement appropriate data retention policies
- Consider data anonymization for analytics

### Access Control

- Implement proper access controls for cost management features
- Restrict budget configuration changes to authorized users
- Monitor and audit cost management operations
