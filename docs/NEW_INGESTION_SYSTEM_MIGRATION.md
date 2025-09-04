# New Log Ingestion System Migration Guide

## Overview

The Gemini SRE Agent has been enhanced with a new, comprehensive log ingestion system that provides improved monitoring, reliability, and extensibility while maintaining full backward compatibility with the existing system.

## New Features

### 🚀 Enhanced Architecture
- **Pluggable Adapters**: Support for multiple log sources (GCP Pub/Sub, Kubernetes, File System, AWS CloudWatch, etc.)
- **Comprehensive Monitoring**: Built-in metrics collection, health checks, performance monitoring, and alerting
- **Resilience Patterns**: Circuit breakers, backpressure management, automatic retries, and failover
- **Production Ready**: Enterprise-grade observability and error handling

### 📊 Monitoring System
- **MetricsCollector**: Real-time metrics with counters, gauges, histograms, and custom metrics
- **HealthChecker**: Component health monitoring with automated status checks
- **PerformanceMonitor**: Processing time tracking, throughput analysis, and resource utilization
- **AlertManager**: Configurable alerts with multiple notification channels and escalation

### 🔧 Configuration Management
- **Unified Configuration**: Single configuration system for all ingestion sources
- **Runtime Updates**: Dynamic configuration changes without restarts
- **Validation**: Comprehensive configuration validation and error reporting

## Migration Options

### Option 1: Feature Flag Rollout (Recommended)

Enable the new system gradually using environment variables:

```bash
# Enable new ingestion system for specific services
export USE_NEW_INGESTION_SYSTEM=true

# Enable comprehensive monitoring
export ENABLE_MONITORING=true

# Keep legacy fallback enabled during transition
export ENABLE_LEGACY_FALLBACK=true
```

### Option 2: Direct Migration

Update your startup configuration to use the new system by default.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_NEW_INGESTION_SYSTEM` | `false` | Enable the new log ingestion system |
| `ENABLE_MONITORING` | `true` | Enable comprehensive monitoring features |
| `ENABLE_LEGACY_FALLBACK` | `true` | Fall back to legacy system if new system fails |

## Key Benefits

### 🛡️ Improved Reliability
- **Circuit Breakers**: Prevent cascade failures
- **Backpressure Management**: Handle high-volume log streams
- **Automatic Retries**: Resilient error handling
- **Health Monitoring**: Proactive issue detection

### 📈 Enhanced Observability
- **Real-time Metrics**: Processing rates, error counts, latencies
- **Performance Tracking**: Resource utilization and bottleneck identification
- **Alert Management**: Configurable alerting with escalation policies
- **Health Dashboards**: Component status and system health overview

### 🔌 Extensibility
- **Multiple Sources**: Easy addition of new log sources
- **Adapter Pattern**: Clean separation of concerns
- **Configuration Driven**: No code changes for new sources
- **Plugin Architecture**: Modular and maintainable design

## Configuration Examples

### Basic GCP Pub/Sub Configuration

```python
from gemini_sre_agent.config.ingestion_config import GCPPubSubConfig, SourceType

config = GCPPubSubConfig(
    name="my_service_logs",
    type=SourceType.GCP_PUBSUB,
    project_id="my-gcp-project",
    subscription_id="my-log-subscription",
    enabled=True,
    max_messages=100,
    ack_deadline_seconds=60,
)
```

### Monitoring Configuration

```python
from gemini_sre_agent.ingestion.monitoring.monitoring_manager import MonitoringManager

# Initialize comprehensive monitoring
monitoring_manager = MonitoringManager()
await monitoring_manager.start()

# Register health checks
await monitoring_manager.register_component_health_check(
    "log_processor",
    lambda: check_log_processor_health()
)

# Record metrics
monitoring_manager.record_operation_metrics(
    component="log_processor",
    operation="process_log",
    duration_ms=45.2,
    success=True,
    bytes_processed=1024
)
```

## Rollback Strategy

If issues occur during migration:

1. **Immediate Rollback**: Set `USE_NEW_INGESTION_SYSTEM=false`
2. **Graceful Degradation**: The legacy fallback system will automatically engage
3. **Monitoring**: Review logs and monitoring data to identify issues
4. **Iterative Fix**: Address issues and re-enable with feature flags

## Testing Recommendations

### 1. Development Environment
- Test with `USE_NEW_INGESTION_SYSTEM=true`
- Verify all log sources are properly ingested
- Confirm monitoring metrics are collected
- Test failure scenarios and recovery

### 2. Staging Environment
- Run both systems in parallel with feature flags
- Compare processing results and performance
- Validate monitoring and alerting functionality
- Test configuration changes and updates

### 3. Production Rollout
- Start with non-critical services
- Monitor health metrics and error rates
- Gradually expand to more services
- Keep legacy fallback enabled initially

## Monitoring During Migration

### Key Metrics to Watch
- **Log Processing Rate**: Ensure consistent throughput
- **Error Rates**: Monitor for increased failures
- **Latency**: Check processing times remain acceptable
- **Memory Usage**: Watch for resource consumption changes
- **Health Status**: Monitor all component health checks

### Alert Configurations
```python
# Example alert for high error rate
await monitoring_manager.create_alert(
    title="High Log Processing Error Rate",
    message="Error rate exceeded 5% threshold",
    level=AlertLevel.WARNING,
    source="log_ingestion_system",
    metadata={"threshold": "5%", "current_rate": "8%"}
)
```

## Support and Troubleshooting

### Common Issues

1. **Configuration Errors**
   - Check configuration validation logs
   - Verify required parameters are provided
   - Ensure proper environment variable setup

2. **Connection Issues**
   - Verify GCP credentials and permissions
   - Check network connectivity to log sources
   - Validate subscription and topic configurations

3. **Performance Issues**
   - Monitor resource utilization metrics
   - Check for backpressure indicators
   - Review processing latency trends

### Getting Help

1. **Logs**: Check application logs for detailed error information
2. **Monitoring**: Review health check and metric data
3. **Configuration**: Validate configuration against examples
4. **Fallback**: Enable legacy system if immediate resolution needed

## Best Practices

### 1. Gradual Migration
- Start with low-volume services
- Use feature flags for controlled rollout
- Monitor metrics during transition
- Keep fallback options available

### 2. Monitoring Setup
- Configure comprehensive health checks
- Set up appropriate alert thresholds
- Monitor both technical and business metrics
- Create operational dashboards

### 3. Configuration Management
- Use version control for configurations
- Test configuration changes in staging
- Implement configuration validation
- Document configuration changes

### 4. Operational Readiness
- Train team on new monitoring tools
- Update runbooks and procedures
- Establish escalation procedures
- Plan for rollback scenarios

## Next Steps

After successful migration:
1. **Performance Optimization**: Tune configuration based on monitoring data
2. **Additional Sources**: Add new log sources as needed
3. **Advanced Features**: Implement custom adapters or processors
4. **Legacy Removal**: Remove legacy system after confidence period

---

For additional support or questions about the migration, please refer to the system architecture documentation or contact the development team.
