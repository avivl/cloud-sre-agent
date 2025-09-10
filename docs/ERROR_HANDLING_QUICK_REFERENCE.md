# Error Handling Quick Reference

This is a quick reference guide for using the error handling system in the Gemini SRE Agent.

## Quick Start

```python
from gemini_sre_agent.source_control.error_handling import ResilientOperations

# Create resilient operations manager
resilient_ops = ResilientOperations()

# Execute any operation with automatic error handling
result = await resilient_ops.execute_resilient_operation(
    "file_operations",  # Operation type
    your_function,      # Function to execute
    *args,             # Function arguments
    **kwargs           # Function keyword arguments
)
```

## Common Patterns

### 1. Basic Error Handling

```python
from gemini_sre_agent.source_control.error_handling import ResilientOperations

resilient_ops = ResilientOperations()

# File operations
result = await resilient_ops.execute_resilient_operation(
    "file_operations",
    github_provider.create_file,
    "path/to/file",
    "content"
)

# Branch operations
result = await resilient_ops.execute_resilient_operation(
    "branch_operations",
    github_provider.create_branch,
    "feature-branch",
    "main"
)
```

### 2. Custom Error Classification

```python
from gemini_sre_agent.source_control.error_handling import ErrorClassifier, ErrorType

classifier = ErrorClassifier()

try:
    # Your operation
    result = await some_operation()
except Exception as e:
    classification = classifier.classify_error(e)

    if classification.error_type == ErrorType.NETWORK_ERROR:
        # Handle network error
        pass
    elif classification.is_retryable:
        # Retry the operation
        pass
    else:
        # Handle non-retryable error
        raise
```

### 3. Circuit Breaker Usage

```python
from gemini_sre_agent.source_control.error_handling import CircuitBreaker, CircuitBreakerConfig

# Configure circuit breaker
config = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60.0
)

# Create circuit breaker
circuit_breaker = CircuitBreaker("github_operations", config)

# Use as decorator
@circuit_breaker
async def github_operation():
    # Your GitHub API call
    pass

# Or use directly
async def operation():
    async with circuit_breaker:
        # Your operation
        pass
```

### 4. Retry with Custom Configuration

```python
from gemini_sre_agent.source_control.error_handling import RetryManager, RetryConfig

# Configure retry
config = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True
)

# Create retry manager
retry_manager = RetryManager(config)

# Use as decorator
@retry_manager.retry
async def operation_with_retry():
    # Your operation
    pass

# Or use directly
result = await retry_manager.execute_with_retry(operation_func, *args)
```

### 5. Graceful Degradation

```python
from gemini_sre_agent.source_control.error_handling import GracefulDegradationManager

# Create degradation manager
degradation_manager = GracefulDegradationManager(resilient_manager)

# Execute with fallback strategies
result = await degradation_manager.execute_with_graceful_degradation(
    "file_operations",
    primary_operation,
    *args,
    **kwargs
)
```

### 6. Health Monitoring

```python
from gemini_sre_agent.source_control.error_handling import HealthCheckManager

health_manager = HealthCheckManager()

# Check specific provider
github_health = await health_manager.check_provider_health("github")
print(f"GitHub health: {github_health['status']}")

# Check operation type
file_ops_health = await health_manager.get_operation_type_health("file_operations")
print(f"File operations health: {file_ops_health['status']}")

# Get overall system health
overall_health = await health_manager.get_overall_health()
print(f"Overall health: {overall_health['status']}")
```

### 7. Metrics Collection

```python
from gemini_sre_agent.source_control.error_handling import ErrorHandlingMetrics

metrics = ErrorHandlingMetrics()

# Record error
await metrics.record_error(
    error_type=ErrorType.NETWORK_ERROR,
    operation_name="file_operations",
    provider="github",
    is_retryable=True
)

# Record operation success
await metrics.record_operation_success(
    operation_name="file_operations",
    provider="github",
    duration_seconds=2.5
)

# Record circuit breaker state change
await metrics.record_circuit_breaker_state_change(
    circuit_name="github_operations",
    old_state=CircuitState.CLOSED,
    new_state=CircuitState.OPEN,
    operation_type="file_operations"
)
```

## Error Types Reference

| Error Type                | Description                 | Retryable | Circuit Breaker |
| ------------------------- | --------------------------- | --------- | --------------- |
| `NETWORK_ERROR`           | Network connectivity issues | Yes       | Yes             |
| `TIMEOUT_ERROR`           | Operation timeouts          | Yes       | Yes             |
| `GITHUB_RATE_LIMIT_ERROR` | GitHub API rate limiting    | Yes       | Yes             |
| `GITHUB_API_ERROR`        | GitHub API errors           | Depends   | Yes             |
| `GITLAB_RATE_LIMIT_ERROR` | GitLab API rate limiting    | Yes       | Yes             |
| `GITLAB_API_ERROR`        | GitLab API errors           | Depends   | Yes             |
| `LOCAL_GIT_ERROR`         | Local Git operations        | Yes       | No              |
| `CLIENT_ERROR`            | 4xx HTTP errors             | No        | No              |
| `SERVER_ERROR`            | 5xx HTTP errors             | Yes       | Yes             |
| `AUTHENTICATION_ERROR`    | Invalid credentials         | No        | No              |
| `AUTHORIZATION_ERROR`     | Insufficient permissions    | No        | No              |
| `VALIDATION_ERROR`        | Invalid input               | No        | No              |
| `FILE_SYSTEM_ERROR`       | File system issues          | Yes       | No              |
| `SECURITY_ERROR`          | Security violations         | No        | No              |
| `API_ERROR`               | General API errors          | Depends   | Yes             |
| `UNKNOWN_ERROR`           | Unclassified errors         | No        | Yes             |

## Circuit Breaker States

| State       | Description      | Behavior                  |
| ----------- | ---------------- | ------------------------- |
| `CLOSED`    | Normal operation | All requests pass through |
| `OPEN`      | Circuit is open  | All requests fail fast    |
| `HALF_OPEN` | Testing recovery | Limited requests allowed  |

## Configuration Examples

### Basic Configuration

```yaml
error_handling:
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout: 60.0

  retry:
    max_attempts: 3
    base_delay: 1.0
    max_delay: 60.0

  graceful_degradation:
    enabled: true

  health_checks:
    enabled: true
    check_interval: 300.0

  metrics:
    enabled: true
```

### Production Configuration

```yaml
error_handling:
  circuit_breaker:
    failure_threshold: 10
    recovery_timeout: 120.0
    expected_exception: "Exception"

  retry:
    max_attempts: 5
    base_delay: 2.0
    max_delay: 120.0
    exponential_base: 2.0
    jitter: true

  graceful_degradation:
    enabled: true
    fallback_timeout: 30.0

  health_checks:
    enabled: true
    check_interval: 60.0
    timeout: 10.0

  metrics:
    enabled: true
    collection_interval: 30.0
```

## Common Issues and Solutions

### Issue: Circuit Breaker Stuck Open

**Solution**: Check error thresholds and manually reset if needed

```python
# Reset circuit breaker
circuit_breaker.reset()
```

### Issue: Too Many Retries

**Solution**: Adjust retry configuration

```python
config = RetryConfig(
    max_attempts=2,  # Reduce retry attempts
    base_delay=5.0   # Increase base delay
)
```

### Issue: Health Checks Failing

**Solution**: Verify provider connectivity and credentials

```python
# Check specific provider
health = await health_manager.check_provider_health("github")
print(f"Health details: {health}")
```

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from gemini_sre_agent.source_control.error_handling import ErrorClassifier

def test_error_classification():
    classifier = ErrorClassifier()
    error = Exception("Network connection failed")
    classification = classifier.classify_error(error)
    assert classification.error_type == ErrorType.NETWORK_ERROR
    assert classification.is_retryable == True
```

### Integration Tests

```python
import pytest
from gemini_sre_agent.source_control.error_handling import ResilientOperations

@pytest.mark.asyncio
async def test_resilient_operation():
    resilient_ops = ResilientOperations()

    # Mock a failing operation
    mock_func = AsyncMock(side_effect=Exception("Network error"))

    # Should handle error gracefully
    result = await resilient_ops.execute_resilient_operation(
        "file_operations",
        mock_func
    )

    # Verify error was handled
    assert result is not None
```

## Monitoring and Alerting

### Key Metrics to Monitor

- Error rates by provider and operation type
- Circuit breaker state changes
- Retry attempt counts
- Health check results
- Operation success/failure rates

### Example Alert Rules

```yaml
# High error rate alert
- alert: HighErrorRate
  expr: rate(source_control_errors_total[5m]) > 0.1
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "High error rate detected"

# Circuit breaker open alert
- alert: CircuitBreakerOpen
  expr: source_control_circuit_breaker_state == 1
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Circuit breaker is open"
```

## Best Practices

1. **Always use resilient operations** for external API calls
2. **Monitor circuit breaker states** and set up alerts
3. **Configure appropriate retry limits** to avoid cascading failures
4. **Test fallback scenarios** regularly
5. **Use health checks** for load balancing and monitoring
6. **Collect comprehensive metrics** for observability
7. **Log error details** for debugging and analysis
8. **Set up proper alerting** for critical failures
