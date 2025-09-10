# Advanced Error Handling System

This directory contains a comprehensive error handling system for source control operations, providing resilience, self-healing capabilities, and intelligent fallback mechanisms.

## Overview

The error handling system is designed to provide robust error management for source control operations across different providers (GitHub, GitLab, Local). It includes:

- **Advanced Circuit Breakers** - Prevent cascading failures and provide graceful degradation
- **Custom Fallback Strategies** - Intelligent fallback mechanisms for different operation types
- **Error Recovery Automation** - Self-healing capabilities with pattern recognition
- **Monitoring Dashboard** - Real-time monitoring and alerting
- **Comprehensive Metrics** - Detailed performance and health metrics

## Architecture

```text
error_handling/
├── core.py                          # Core types, enums, and exceptions
├── circuit_breaker.py               # Basic circuit breaker implementation
├── advanced_circuit_breaker.py      # Advanced circuit breaker with health checks
├── custom_fallback_strategies.py    # Custom fallback strategies
├── error_recovery_automation.py     # Self-healing and recovery automation
├── monitoring_dashboard.py          # Monitoring and alerting dashboard
├── metrics_integration.py           # Metrics collection and reporting
├── factory.py                       # Factory for creating error handling components
└── examples/
    └── advanced_usage_examples.py   # Comprehensive usage examples
```

## Core Components

### 1. Circuit Breakers

Circuit breakers prevent cascading failures by monitoring operation success rates and temporarily stopping calls to failing services.

#### Basic Circuit Breaker

- Simple open/closed/half-open states
- Configurable failure thresholds
- Timeout handling

#### Advanced Circuit Breaker

- Health monitoring and scoring
- Adaptive timeout adjustment
- Slow request detection
- Comprehensive statistics

### 2. Fallback Strategies

Intelligent fallback mechanisms that provide alternative approaches when primary operations fail.

#### Built-in Strategies

- **Cached Response Strategy** - Use cached data when operations fail
- **Provider-Specific Fallbacks** - GitHub, GitLab, and Local-specific fallbacks
- **Generic Retry Strategy** - Exponential backoff with jitter

#### Custom Strategies

- Easy to implement custom fallback logic
- Priority-based execution
- Context-aware decision making

### 3. Error Recovery Automation

Self-healing capabilities that automatically detect and recover from common failure patterns.

#### Features

- Pattern recognition for common error types
- Automated recovery actions
- Health scoring and recommendations
- Recovery statistics and monitoring

#### Recovery Actions

- **Retry with Backoff** - Exponential backoff retry
- **Credential Refresh** - Refresh authentication tokens
- **Connection Reset** - Reset network connections
- **Circuit Breaker Reset** - Reset circuit breaker states
- **Configuration Update** - Update configuration based on error patterns

### 4. Monitoring Dashboard

Real-time monitoring and alerting for the error handling system.

#### Dashboard Features

- System health scoring
- Circuit breaker status monitoring
- Alert generation and management
- HTML dashboard generation
- Data export capabilities

## Usage Examples

### Basic Circuit Breaker Usage

```python
from gemini_sre_agent.source_control.error_handling.advanced_circuit_breaker import (
    AdvancedCircuitBreaker,
    AdvancedCircuitBreakerConfig,
)

# Configure circuit breaker
config = AdvancedCircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=30.0,
    success_threshold=3,
    timeout=15.0,
)

# Create circuit breaker
circuit_breaker = AdvancedCircuitBreaker(config, "github_api")

# Use with operations
async def github_operation():
    # Your GitHub API call here
    pass

try:
    result = await circuit_breaker.call(github_operation)
except Exception as e:
    # Handle circuit breaker errors
    pass
```

### Custom Fallback Strategy

```python
from gemini_sre_agent.source_control.error_handling.custom_fallback_strategies import (
    CustomFallbackManager,
    FallbackStrategy,
    FallbackStrategyConfig,
)

# Create fallback manager
config = FallbackStrategyConfig(max_retries=3, retry_delay=1.0)
fallback_manager = CustomFallbackManager(config)

# Define custom strategy
def custom_fallback_action(error_type, error_message, context):
    # Your fallback logic here
    return {"status": "fallback_success", "data": "cached_data"}

strategy = FallbackStrategy(
    name="custom_fallback",
    condition=lambda error_type, error_message, context: True,
    action=custom_fallback_action,
    priority=1,
)

# Register and use
fallback_manager.add_strategy(strategy)
result = await fallback_manager.execute_fallback(
    "operation_type", ErrorType.TIMEOUT_ERROR, original_func, context
)
```

### Self-Healing System

```python
from gemini_sre_agent.source_control.error_handling.error_recovery_automation import (
    SelfHealingManager,
)

# Create self-healing manager
self_healing_manager = SelfHealingManager()

# Handle errors with automatic recovery
success, message = await self_healing_manager.handle_error_with_recovery(
    ErrorType.TIMEOUT_ERROR, "Request timeout", context
)

if success:
    print(f"Recovery successful: {message}")
else:
    print(f"Recovery failed: {message}")
```

### Monitoring Dashboard

```python
from gemini_sre_agent.source_control.error_handling.monitoring_dashboard import (
    MonitoringDashboard,
)

# Create dashboard
dashboard = MonitoringDashboard()

# Register components
dashboard.register_circuit_breaker("github_api", circuit_breaker)
dashboard.register_fallback_manager(fallback_manager)
dashboard.register_self_healing_manager(self_healing_manager)

# Refresh and get status
await dashboard.refresh_dashboard_data()
summary = dashboard.get_dashboard_summary()
alerts = dashboard.get_alerts()

# Generate HTML dashboard
html_dashboard = dashboard.get_dashboard_html()
```

## Configuration

### Circuit Breaker Configuration

```python
config = AdvancedCircuitBreakerConfig(
    failure_threshold=5,                    # Failures before opening
    recovery_timeout=30.0,                  # Seconds before half-open
    success_threshold=3,                    # Successes to close
    timeout=15.0,                          # Operation timeout
    max_requests_half_open=10,             # Max requests in half-open
    slow_request_threshold=5.0,            # Slow request threshold
    slow_request_percentage_threshold=30.0, # Slow request percentage
    health_check_interval=60.0,            # Health check interval
    adaptive_timeout=True,                 # Enable adaptive timeout
    adaptive_timeout_percentile=95.0,      # Timeout percentile
    adaptive_timeout_multiplier=1.2,       # Timeout multiplier
)
```

### Fallback Strategy Configuration

```python
config = FallbackStrategyConfig(
    max_retries=3,              # Maximum retry attempts
    retry_delay=1.0,            # Base retry delay
    exponential_backoff=True,   # Enable exponential backoff
    jitter=True,                # Add jitter to delays
    fallback_timeout=30.0,      # Fallback operation timeout
)
```

## Error Types

The system supports comprehensive error type classification:

### Retryable Errors

- `NETWORK_ERROR` - Network connectivity issues
- `TIMEOUT_ERROR` - Request timeouts
- `RATE_LIMIT_ERROR` - API rate limiting
- `TEMPORARY_ERROR` - Temporary service issues
- `SERVER_ERROR` - Server-side errors
- `CONNECTION_RESET_ERROR` - Connection resets
- `DNS_ERROR` - DNS resolution issues
- `SSL_ERROR` - SSL/TLS issues

### Non-Retryable Errors

- `AUTHENTICATION_ERROR` - Authentication failures
- `AUTHORIZATION_ERROR` - Authorization failures
- `NOT_FOUND_ERROR` - Resource not found
- `VALIDATION_ERROR` - Input validation errors
- `CONFIGURATION_ERROR` - Configuration issues
- `INVALID_INPUT_ERROR` - Invalid input data
- `PERMISSION_DENIED_ERROR` - Permission denied

### Provider-Specific Errors

- `GITHUB_API_ERROR` - GitHub API errors
- `GITHUB_RATE_LIMIT_ERROR` - GitHub rate limiting
- `GITHUB_REPOSITORY_NOT_FOUND` - Repository not found
- `GITHUB_BRANCH_NOT_FOUND` - Branch not found
- `GITHUB_MERGE_CONFLICT` - Merge conflicts

## Health Monitoring

The system provides comprehensive health monitoring:

### Health Scores

- **100-80**: Healthy - System operating normally
- **79-50**: Degraded - Some issues detected
- **49-0**: Unhealthy - Critical issues present

### Health Factors

- Circuit breaker states
- Error rates and patterns
- Recovery success rates
- Response times
- Resource utilization

### Alerts

- **Critical**: System health is critical
- **Warning**: Circuit breakers open or degraded
- **Info**: Self-healing system issues

## Best Practices

### 1. Circuit Breaker Configuration

- Set appropriate failure thresholds based on your service characteristics
- Use adaptive timeouts for dynamic environments
- Monitor health scores and adjust configurations accordingly

### 2. Fallback Strategy Best Practices

- Implement provider-specific fallbacks for better reliability
- Use cached responses when possible
- Consider data consistency when using fallbacks

### 3. Error Recovery

- Monitor recovery success rates
- Adjust patterns and actions based on observed behavior
- Use health scores to guide configuration changes

### 4. Monitoring

- Set up regular dashboard refreshes
- Monitor alerts and respond to critical issues
- Export data for long-term analysis

## Testing

The system includes comprehensive tests covering:

- Circuit breaker state transitions
- Fallback strategy execution
- Error recovery automation
- Monitoring dashboard functionality
- Integration scenarios

Run tests with:

```bash
pytest tests/source_control/test_advanced_error_handling.py -v
```

## Examples

See `examples/advanced_usage_examples.py` for comprehensive usage examples demonstrating all system components.

## Contributing

When adding new error handling components:

1. Follow the existing patterns and interfaces
2. Add comprehensive tests
3. Update documentation
4. Consider backward compatibility
5. Add monitoring and metrics support

## License

This error handling system is part of the Gemini SRE Agent project and follows the same license terms.
