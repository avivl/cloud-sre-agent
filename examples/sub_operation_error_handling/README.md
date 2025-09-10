# Sub-Operation Error Handling Examples

This directory contains comprehensive examples demonstrating how to use the sub-operation error handling system in the Gemini SRE Agent. The examples cover basic usage, advanced scenarios, and provider integration patterns.

## Overview

The sub-operation error handling system provides:

- **Circuit Breaker Pattern**: Prevents cascading failures by opening the circuit when failure rates exceed thresholds
- **Retry Strategies**: Configurable retry logic with exponential backoff
- **Error Classification**: Categorizes errors for appropriate handling
- **Metrics Collection**: Tracks performance and error metrics
- **Health Checks**: Monitors system health and enables recovery
- **Configuration Management**: Flexible configuration for different providers and operations

## Examples

### 1. Basic Usage Example (`basic_usage_example.py`)

Demonstrates the fundamental usage of sub-operation error handling:

- **Local File Operations**: Shows how to use error handling with local file operations
- **Error Scenarios**: Demonstrates various error conditions and how they're handled
- **Configuration Management**: Shows how to manage configurations for different providers

**Key Features:**

- Basic file operations (create, read, update, delete)
- Error handling with circuit breaker and retry logic
- Configuration setup and management
- Performance tracking and health checks

**Usage:**

```bash
python basic_usage_example.py
```

### 2. Advanced Error Handling Example (`advanced_error_handling_example.py`)

Demonstrates advanced error handling scenarios:

- **Circuit Breaker Patterns**: Shows how circuit breakers prevent cascading failures
- **Retry Strategies**: Demonstrates different retry configurations and their effects
- **Metrics Collection**: Shows how to collect and monitor performance metrics
- **Health Checks**: Demonstrates health monitoring and recovery

**Key Features:**

- Circuit breaker with failure simulation
- Multiple retry strategies (aggressive, conservative, no retry)
- Metrics collection and monitoring
- Health checks and configuration updates

**Usage:**

```bash
python advanced_error_handling_example.py
```

### 3. Provider Integration Example (`provider_integration_example.py`)

Demonstrates how to integrate error handling with different source control providers:

- **Multi-Provider Support**: Shows how to manage multiple providers (GitHub, GitLab, Local)
- **Provider-Specific Configuration**: Demonstrates different configurations for different providers
- **Unified Interface**: Shows how to use a unified interface across providers

**Key Features:**

- Provider manager for multiple source control systems
- Provider-specific error handling configurations
- Unified operation interface
- Health monitoring across providers

**Usage:**

```bash
python provider_integration_example.py
```

## Configuration

### Sub-Operation Configuration

Each sub-operation can be configured with:

```python
from gemini_sre_agent.source_control.providers.sub_operation_config import SubOperationConfig
from gemini_sre_agent.source_control.error_handling.core import CircuitBreakerConfig, RetryConfig

config = SubOperationConfig(
    operation_name="file_operations",
    provider_type="github",
    error_handling_enabled=True,
    circuit_breaker=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
        timeout=30.0,
    ),
    retry=RetryConfig(
        max_retries=5,
        base_delay=2.0,
        max_delay=30.0,
        backoff_factor=2.0,
    ),
    log_operations=True,
    log_errors=True,
    log_performance=True,
    enable_metrics=True,
)
```

### Provider-Specific Configurations

Different providers can have different configurations:

- **GitHub**: More aggressive retry for API rate limits
- **GitLab**: Moderate retry for API stability
- **Local**: Minimal retry for local operations

## Error Handling Components

### Circuit Breaker

The circuit breaker prevents cascading failures by:

1. **Closed State**: Normal operation, requests pass through
2. **Open State**: Circuit is open, requests fail immediately
3. **Half-Open State**: Testing if the service has recovered

### Retry Strategy

The retry strategy handles transient failures with:

- **Exponential Backoff**: Delays increase exponentially between retries
- **Maximum Retries**: Configurable maximum number of retry attempts
- **Timeout Handling**: Each retry attempt has a configurable timeout

### Error Classification

Errors are classified into categories:

- **TEMPORARY_ERROR**: Transient errors that may succeed on retry
- **PERMANENT_ERROR**: Errors that won't succeed on retry
- **TIMEOUT_ERROR**: Operations that exceed timeout limits
- **UNKNOWN_ERROR**: Unclassified errors

## Metrics and Monitoring

### Performance Metrics

The system tracks:

- **Operation Duration**: Time taken for each operation
- **Success Rate**: Percentage of successful operations
- **Error Rate**: Percentage of failed operations
- **Retry Count**: Number of retry attempts
- **Circuit Breaker State**: Current state of circuit breakers

### Health Checks

Health checks verify:

- **Basic Operations**: Test fundamental operations
- **Configuration Validity**: Verify configuration settings
- **Dependencies**: Check external dependencies
- **Performance**: Monitor performance metrics

## Best Practices

### 1. Configuration Management

- Use provider-specific configurations
- Set appropriate timeouts and retry limits
- Enable metrics for production environments
- Use circuit breakers for external services

### 2. Error Handling

- Classify errors appropriately
- Use retry strategies for transient errors
- Implement circuit breakers for external services
- Monitor error rates and patterns

### 3. Performance

- Enable performance logging for debugging
- Use metrics collection for monitoring
- Set appropriate timeouts
- Monitor circuit breaker states

### 4. Health Monitoring

- Implement health checks for all providers
- Monitor health status regularly
- Set up alerts for unhealthy providers
- Implement recovery procedures

## Troubleshooting

### Common Issues

1. **Circuit Breaker Always Open**
   - Check failure thresholds
   - Verify error classification
   - Review retry configuration

2. **High Retry Counts**
   - Check timeout settings
   - Verify error handling logic
   - Review retry configuration

3. **Performance Issues**
   - Check timeout settings
   - Review retry configuration
   - Monitor metrics

### Debugging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check performance statistics:

```python
stats = file_ops.get_performance_stats()
print(f"Performance stats: {stats}")
```

Monitor health status:

```python
health = await file_ops.health_check()
print(f"Health status: {health}")
```

## Dependencies

The examples require the following packages:

- `asyncio`: For asynchronous operations
- `pathlib`: For file path handling
- `logging`: For logging
- `time`: For timing operations

## Running the Examples

1. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Run Basic Example**:

   ```bash
   python basic_usage_example.py
   ```

3. **Run Advanced Example**:

   ```bash
   python advanced_error_handling_example.py
   ```

4. **Run Provider Integration Example**:
   ```bash
   python provider_integration_example.py
   ```

## Contributing

When adding new examples:

1. Follow the existing code structure
2. Include comprehensive error handling
3. Add detailed logging
4. Include cleanup procedures
5. Document any new features or patterns

## License

This code is part of the Gemini SRE Agent project and follows the same license terms.
