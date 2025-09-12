# Comprehensive Logging Framework

A unified, enterprise-grade logging system for the Gemini SRE Agent that provides structured logging, flow tracking, performance monitoring, and alerting capabilities.

## Features

### Core Logging

- **Structured Logging**: JSON and text formatters with consistent data structures
- **Multiple Handlers**: Console, file, rotating file, syslog, HTTP, database, and queue handlers
- **Advanced Filtering**: Level, regex, tag, context, sampling, and rate limiting filters
- **Context Management**: Thread-safe context storage and retrieval
- **Flow Tracking**: Operation tracking with unique identifiers and hierarchical relationships

### Performance Monitoring

- **Metrics Collection**: Timing, counter, and gauge metrics
- **Statistical Analysis**: Min, max, average, and percentile calculations
- **Sampling Support**: Configurable sampling rates for high-volume scenarios
- **Export Formats**: Multiple export formats (dict, list, stats)

### Alerting System

- **Rule-based Alerts**: Configurable alert rules with conditions
- **Severity Levels**: Low, medium, high, and critical alert severities
- **Alert Management**: Acknowledge, resolve, and suppress alerts
- **Cooldown Periods**: Prevent alert spam with configurable cooldowns

### Integration

- **Dependency Injection**: Seamless integration with DI container
- **Configuration Validation**: Validated configuration with comprehensive error reporting
- **Thread Safety**: All operations are thread-safe
- **Resource Management**: Proper cleanup and resource management

## Quick Start

### Basic Usage

```python
from gemini_sre_agent.core.logging import get_logger

# Get a logger
logger = get_logger()

# Basic logging
logger.info("Application started")
logger.error("An error occurred", extra={"error_code": "E001"})

# Logging with tags
logger.info("User action", tags=["user", "action"], extra={"action": "login"})
```

### Flow Tracking

```python
# Start a flow
with logger.flow("user_registration") as flow_id:
    logger.info("Starting registration", flow_id=flow_id)

    # Do work
    process_registration()

    logger.info("Registration completed", flow_id=flow_id)
```

### Performance Monitoring

```python
# Record metrics
logger.record_metric("api_requests", 1, tags={"endpoint": "/users"})

# Timing operations
with logger.timing("database_query", tags={"table": "users"}):
    execute_query()

# Get performance stats
stats = logger.get_performance_stats("api_requests")
```

### Context Management

```python
# Add context
logger.add_context("user_id", "12345")
logger.add_context("session_id", "sess_abc123")

# Log with context
logger.info("Processing request")  # Includes user_id and session_id

# Clear context
logger.clear_context()
```

## Configuration

### Basic Configuration

```python
from gemini_sre_agent.core.logging import LoggingConfig, get_logger

config = LoggingConfig(
    name="my_app",
    level=20,  # INFO level
    handlers=[
        {
            "type": "console",
            "level": 20,
            "formatter": "json"
        },
        {
            "type": "file",
            "filename": "app.log",
            "level": 10,
            "formatter": "text"
        }
    ],
    formatters={
        "json": {
            "type": "json",
            "include_extra": True,
            "include_context": True
        },
        "text": {
            "type": "text",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    }
)

logger = get_logger(config)
```

### Advanced Configuration

```python
config = LoggingConfig(
    name="production_app",
    level=20,
    handlers=[
        {
            "type": "console",
            "level": 30,  # WARNING and above
            "formatter": "json"
        },
        {
            "type": "rotating_file",
            "filename": "app.log",
            "max_bytes": 10485760,  # 10MB
            "backup_count": 5,
            "level": 10,
            "formatter": "detailed"
        },
        {
            "type": "syslog",
            "address": ("localhost", 514),
            "facility": "local0",
            "level": 40,  # ERROR and above
            "formatter": "syslog"
        }
    ],
    formatters={
        "json": {
            "type": "json",
            "include_extra": True,
            "include_context": True,
            "include_flow": True
        },
        "detailed": {
            "type": "text",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(extra)s"
        },
        "syslog": {
            "type": "text",
            "format": "%(name)s[%(process)d]: %(levelname)s - %(message)s"
        }
    },
    filters=[
        {
            "type": "level",
            "level": 20
        },
        {
            "type": "regex",
            "pattern": r"^(?!.*password).*$",
            "exclude": True
        }
    ],
    context={
        "enabled": True,
        "max_size": 100,
        "include_flow": True
    },
    performance_monitoring={
        "enabled": True,
        "sampling_rate": 1.0,
        "max_metrics_per_name": 1000
    },
    alerting=[
        {
            "name": "high_error_rate",
            "condition": "lambda data: data.get('level', 0) >= 40",
            "severity": "high",
            "message_template": "High error rate: {level_name} - {message}",
            "cooldown_seconds": 300
        }
    ]
)
```

## Components

### Loggers

- **Logger**: Main logger class that integrates all components
- **StructuredLogger**: Enhanced logger with structured output
- **LoggingManager**: Central logging orchestrator

### Formatters

- **JSONFormatter**: JSON output with structured data
- **TextFormatter**: Human-readable text output
- **StructuredFormatter**: Custom structured format
- **FlowFormatter**: Flow-aware formatting

### Handlers

- **ConsoleHandler**: Console output
- **FileHandler**: File output
- **RotatingFileHandler**: Rotating file output
- **SyslogHandler**: Syslog output
- **HTTPHandler**: HTTP endpoint output
- **DatabaseHandler**: Database storage
- **QueueHandler**: Queue-based output

### Filters

- **LevelFilter**: Level-based filtering
- **RegexFilter**: Regex pattern filtering
- **TagFilter**: Tag-based filtering
- **ContextFilter**: Context-based filtering
- **SamplingFilter**: Sampling-based filtering
- **RateLimitFilter**: Rate limiting

### Flow Tracking

- **FlowTracker**: Tracks operations across the system
- **FlowContext**: Context for individual flows

### Performance Monitoring

- **PerformanceMonitor**: Collects and analyzes performance metrics
- **PerformanceMetric**: Individual metric measurement
- **PerformanceStats**: Statistical analysis of metrics

### Alerting

- **AlertManager**: Manages alerts and alert rules
- **AlertRule**: Defines alert conditions
- **Alert**: Individual alert instance

## Examples

See `examples.py` for comprehensive usage examples including:

- Basic logging operations
- Flow tracking workflows
- Performance monitoring
- Alert configuration and management
- Context management
- Complete integration examples

## Thread Safety

All components are thread-safe and can be used in multi-threaded environments. The logging framework uses appropriate locking mechanisms to ensure data consistency.

## Performance Considerations

- **Sampling**: Use sampling filters for high-volume logging scenarios
- **Async Handlers**: Use queue handlers for non-blocking log processing
- **Metric Limits**: Configure appropriate limits for performance metrics
- **Context Size**: Limit context data size to prevent memory issues

## Integration with Monitoring Systems

The logging framework integrates with various monitoring systems through:

- **HTTP Handlers**: Send logs to external monitoring services
- **Database Handlers**: Store logs in databases for analysis
- **Queue Handlers**: Integrate with message queues for async processing
- **Custom Handlers**: Implement custom handlers for specific requirements

## Error Handling

The framework includes comprehensive error handling:

- **Graceful Degradation**: Continues operation even if components fail
- **Fallback Logging**: Falls back to basic logging if advanced features fail
- **Error Reporting**: Reports errors through the logging system itself
- **Resource Cleanup**: Properly cleans up resources on shutdown

## Best Practices

1. **Use Structured Logging**: Prefer structured data over free-form messages
2. **Include Context**: Add relevant context to log messages
3. **Use Appropriate Levels**: Use appropriate log levels for different scenarios
4. **Monitor Performance**: Use performance monitoring to track system health
5. **Configure Alerts**: Set up appropriate alerts for critical conditions
6. **Test Logging**: Include logging in your tests to verify behavior
7. **Document Patterns**: Document logging patterns for your team

## Troubleshooting

### Common Issues

1. **Missing Logs**: Check log levels and filter configurations
2. **Performance Issues**: Review sampling rates and handler configurations
3. **Memory Usage**: Monitor context size and metric limits
4. **Alert Spam**: Adjust cooldown periods and alert conditions

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
config = LoggingConfig(
    level=10,  # DEBUG level
    handlers=[{
        "type": "console",
        "level": 10,
        "formatter": "detailed"
    }]
)
```

## Contributing

When contributing to the logging framework:

1. Follow the existing code style and patterns
2. Add comprehensive tests for new features
3. Update documentation for new functionality
4. Consider performance implications of changes
5. Ensure thread safety for all new components
