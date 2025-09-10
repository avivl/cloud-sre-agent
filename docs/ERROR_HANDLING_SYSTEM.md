# Error Handling System

This document describes the comprehensive error handling system implemented in the Gemini SRE Agent for source control operations. The system provides robust error classification, circuit breakers, retry mechanisms, graceful degradation, health checks, and metrics integration.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Core Components](#core-components)
- [Error Classification](#error-classification)
- [Circuit Breaker Pattern](#circuit-breaker-pattern)
- [Retry Mechanisms](#retry-mechanisms)
- [Graceful Degradation](#graceful-degradation)
- [Health Checks](#health-checks)
- [Metrics Integration](#metrics-integration)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

The error handling system is designed to make source control operations resilient to various failure modes including network issues, API rate limits, authentication failures, and service outages. It provides multiple layers of protection:

1. **Error Classification**: Intelligent categorization of errors for appropriate handling
2. **Circuit Breakers**: Prevent cascade failures by temporarily disabling failing services
3. **Retry Mechanisms**: Automatic retry with exponential backoff for transient failures
4. **Graceful Degradation**: Fallback strategies when primary operations fail
5. **Health Checks**: Continuous monitoring of service availability
6. **Metrics Integration**: Comprehensive observability and monitoring

## Architecture

The error handling system is organized into several modules:

```text
gemini_sre_agent/source_control/error_handling/
├── core.py                    # Core types and configurations
├── error_classification.py    # Error classification logic
├── circuit_breaker.py         # Circuit breaker implementation
├── retry_manager.py           # Retry mechanisms
├── graceful_degradation.py    # Graceful degradation strategies
├── health_checks.py           # Health check management
├── metrics_integration.py     # Metrics collection
└── resilient_operations.py    # High-level resilient operations
```

## Core Components

### Error Types

The system defines comprehensive error types in `core.py`:

```python
class ErrorType(Enum):
    # Network-related errors
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"

    # Provider-specific errors
    GITHUB_RATE_LIMIT_ERROR = "github_rate_limit_error"
    GITHUB_API_ERROR = "github_api_error"
    GITLAB_RATE_LIMIT_ERROR = "gitlab_rate_limit_error"
    GITLAB_API_ERROR = "gitlab_api_error"
    LOCAL_GIT_ERROR = "local_git_error"

    # HTTP errors
    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"

    # Authentication and authorization
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"

    # Validation errors
    VALIDATION_ERROR = "validation_error"

    # File system errors
    FILE_SYSTEM_ERROR = "file_system_error"

    # Security errors
    SECURITY_ERROR = "security_error"

    # General API errors
    API_ERROR = "api_error"
    UNKNOWN_ERROR = "unknown_error"
```

### Circuit States

Circuit breakers operate in three states:

```python
class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, requests fail fast
    HALF_OPEN = "half_open" # Testing if service has recovered
```

### Error Classification Structure

The `ErrorClassification` dataclass provides detailed information about errors:

```python
@dataclass
class ErrorClassification:
    error_type: ErrorType
    is_retryable: bool
    retry_delay: float
    max_retries: int
    should_open_circuit: bool
    details: Dict[str, Any] = field(default_factory=dict)
```

## Error Classification

The `ErrorClassifier` analyzes exceptions and determines appropriate handling strategies:

### Classification Rules

The classifier uses a comprehensive set of rules to identify error types:

- **Network Errors**: Connection failures, DNS resolution issues
- **Timeout Errors**: Operation timeouts, request timeouts
- **Rate Limit Errors**: Provider-specific rate limiting (GitHub, GitLab)
- **HTTP Errors**: 4xx and 5xx status codes
- **Authentication Errors**: Invalid credentials, expired tokens
- **Validation Errors**: Invalid input parameters, malformed requests

### Usage

```python
from gemini_sre_agent.source_control.error_handling import ErrorClassifier

classifier = ErrorClassifier()
classification = classifier.classify_error(exception)

print(f"Error Type: {classification.error_type}")
print(f"Retryable: {classification.is_retryable}")
print(f"Max Retries: {classification.max_retries}")
```

## Circuit Breaker Pattern

The circuit breaker prevents cascade failures by monitoring error rates and temporarily disabling failing services.

### Features

- **Configurable thresholds**: Failure count and time window
- **State transitions**: Automatic state changes based on error patterns
- **Recovery testing**: Half-open state for gradual recovery
- **Operation-specific**: Different circuits for different operation types

### Circuit Breaker Configuration

```python
from gemini_sre_agent.source_control.error_handling import CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exception=Exception
)

circuit_breaker = CircuitBreaker("github_operations", config)
```

### Circuit Breaker Usage

```python
@circuit_breaker
async def github_operation():
    # Your GitHub API call here
    pass
```

## Retry Mechanisms

The retry system provides intelligent retry logic with exponential backoff and jitter.

### Retry Features

- **Exponential backoff**: Increasing delays between retries
- **Jitter**: Randomization to prevent thundering herd
- **Max retry limits**: Configurable retry attempts
- **Retryable error detection**: Only retry appropriate errors

### Retry Configuration

```python
from gemini_sre_agent.source_handling.error_handling import RetryConfig

config = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True
)

retry_manager = RetryManager(config)
```

### Retry Usage

```python
@retry_manager.retry
async def operation_with_retry():
    # Your operation here
    pass
```

## Graceful Degradation

The graceful degradation system provides fallback strategies when primary operations fail.

### Degradation Strategies

- **Reduced Timeout**: Lower timeout for faster failure detection
- **Cached Data**: Use previously cached results
- **Simplified Operations**: Fall back to basic operations
- **Local Operations**: Switch to local Git when remote fails
- **Read-Only Mode**: Disable write operations during outages

### Graceful Degradation Usage

```python
from gemini_sre_agent.source_control.error_handling import GracefulDegradationManager

degradation_manager = GracefulDegradationManager(resilient_manager)

result = await degradation_manager.execute_with_graceful_degradation(
    "file_operations",
    operation_func,
    *args,
    **kwargs
)
```

## Health Checks

The health check system monitors service availability and operational status.

### Health Check Features

- **Provider-specific checks**: Different checks for GitHub, GitLab, local Git
- **Operation type monitoring**: Track health by operation type
- **Overall health assessment**: System-wide health status
- **Configurable intervals**: Customizable check frequencies

### Health Check Usage

```python
from gemini_sre_agent.source_control.error_handling import HealthCheckManager

health_manager = HealthCheckManager()

# Check specific provider
github_health = await health_manager.check_provider_health("github")

# Check operation type
file_ops_health = await health_manager.get_operation_type_health("file_operations")

# Get overall health
overall_health = await health_manager.get_overall_health()
```

## Metrics Integration

The metrics system provides comprehensive observability for error handling operations.

### Metrics Collected

- **Error counts**: By type, provider, and operation
- **Circuit breaker state changes**: State transitions and timing
- **Retry attempts**: Retry counts and delays
- **Operation success/failure**: Success rates and durations
- **Health check results**: Provider availability and response times

### Metrics Usage

```python
from gemini_sre_agent.source_control.error_handling import ErrorHandlingMetrics

metrics = ErrorHandlingMetrics()

# Record an error
await metrics.record_error(
    error_type=ErrorType.NETWORK_ERROR,
    operation_name="file_operations",
    provider="github",
    is_retryable=True
)

# Record circuit breaker state change
await metrics.record_circuit_breaker_state_change(
    circuit_name="github_operations",
    old_state=CircuitState.CLOSED,
    new_state=CircuitState.OPEN,
    operation_type="file_operations"
)
```

## Configuration

The error handling system can be configured through the main configuration file:

```yaml
error_handling:
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout: 60.0
    expected_exception: "Exception"

  retry:
    max_attempts: 3
    base_delay: 1.0
    max_delay: 60.0
    exponential_base: 2.0
    jitter: true

  graceful_degradation:
    enabled: true
    fallback_timeout: 30.0

  health_checks:
    enabled: true
    check_interval: 300.0
    timeout: 10.0

  metrics:
    enabled: true
    collection_interval: 60.0
```

## Usage Examples

### Basic Error Handling

```python
from gemini_sre_agent.source_control.error_handling import ResilientOperations

resilient_ops = ResilientOperations()

# Execute with automatic error handling
result = await resilient_ops.execute_resilient_operation(
    "file_operations",
    github_provider.create_file,
    "path/to/file",
    "content"
)
```

### Custom Error Handling

```python
from gemini_sre_agent.source_control.error_handling import (
    ErrorClassifier, CircuitBreaker, RetryManager
)

# Create custom error classifier
classifier = ErrorClassifier()

# Create circuit breaker for specific operations
circuit_breaker = CircuitBreaker("github_api", config)

# Create retry manager
retry_manager = RetryManager(retry_config)

# Combine them for custom error handling
@circuit_breaker
@retry_manager.retry
async def custom_operation():
    try:
        # Your operation here
        pass
    except Exception as e:
        classification = classifier.classify_error(e)
        if not classification.is_retryable:
            raise
        # Handle retryable error
        raise
```

### Health Monitoring

```python
from gemini_sre_agent.source_control.error_handling import HealthCheckManager

health_manager = HealthCheckManager()

# Monitor health continuously
async def monitor_health():
    while True:
        health = await health_manager.get_overall_health()
        if health['status'] != 'healthy':
            logger.warning(f"System health degraded: {health}")
        await asyncio.sleep(60)
```

## Best Practices

### 1. Error Classification Best Practices

- Always classify errors before handling them
- Use appropriate error types for better monitoring
- Include relevant details in error classifications

### 2. Circuit Breakers

- Use operation-specific circuit breakers
- Set appropriate failure thresholds
- Monitor circuit breaker state changes

### 3. Retry Logic

- Only retry retryable errors
- Use exponential backoff with jitter
- Set reasonable retry limits

### 4. Graceful Degradation

- Provide meaningful fallback operations
- Log degradation events for monitoring
- Test fallback scenarios regularly

### 5. Health Checks

- Monitor all critical providers
- Set up alerts for health degradation
- Use health checks for load balancing

### 6. Metrics

- Collect comprehensive metrics
- Set up dashboards for monitoring
- Use metrics for capacity planning

## Troubleshooting

### Common Issues

#### Circuit Breaker Stuck Open

**Symptoms**: Operations fail immediately without retry attempts

**Solutions**:

- Check circuit breaker configuration
- Verify error thresholds are appropriate
- Manually reset circuit breaker if needed

#### High Retry Rates

**Symptoms**: Many operations are being retried

**Solutions**:

- Review error classification rules
- Check for transient issues
- Adjust retry configuration

#### Health Check Failures

**Symptoms**: Health checks report unhealthy status

**Solutions**:

- Verify provider connectivity
- Check authentication credentials
- Review health check configuration

#### Metrics Not Collected

**Symptoms**: No metrics appearing in monitoring

**Solutions**:

- Verify metrics collector configuration
- Check metrics collection intervals
- Ensure proper error handling in metrics code

### Debugging

Enable debug logging for error handling:

```python
import logging

logging.getLogger("gemini_sre_agent.source_control.error_handling").setLevel(logging.DEBUG)
```

### Monitoring

Set up monitoring for key metrics:

- Error rates by provider and operation type
- Circuit breaker state changes
- Retry attempt counts
- Health check results
- Operation success/failure rates

## Conclusion

The error handling system provides comprehensive resilience for source control operations. By combining error classification, circuit breakers, retry mechanisms, graceful degradation, health checks, and metrics, it ensures reliable operation even under adverse conditions.

For more information about specific components, refer to the individual module documentation and test files.
