# Log Ingestion System

A pluggable architecture for ingesting logs from multiple sources with unified processing, error handling, and monitoring capabilities.

## Features

- **Multi-Source Support**: GCP Pub/Sub, GCP Logging, File System, and more
- **Unified Interface**: Consistent API across all log sources
- **Resilience Patterns**: Circuit breakers, retries, backpressure handling
- **Memory Buffering**: Configurable memory queues for high-throughput scenarios
- **PII Detection**: Automatic detection and masking of sensitive information
- **Flow Tracking**: Built-in flow ID generation and tracking
- **Health Monitoring**: Comprehensive health checks and metrics
- **Configuration Management**: YAML/JSON configuration with validation

## Quick Start

### 1. Basic Usage

```python
import asyncio
from gemini_sre_agent.ingestion import LogManager
from gemini_sre_agent.ingestion.adapters import FileSystemAdapter, FileSystemConfig

async def log_callback(log_entry):
    print(f"Received: {log_entry.message}")

async def main():
    # Create file system source
    config = FileSystemConfig(
        name="my-logs",
        file_path="/var/log/applications",
        file_pattern="*.log"
    )

    adapter = FileSystemAdapter(config)

    # Create and start manager
    manager = LogManager(callback=log_callback)
    await manager.add_source(adapter)
    await manager.start()

    # Run for a while
    await asyncio.sleep(60)

    # Stop
    await manager.stop()

asyncio.run(main())
```

### 2. Configuration-Based Setup

```python
from gemini_sre_agent.config.ingestion_config import IngestionConfigManager

# Load configuration
config_manager = IngestionConfigManager()
config = config_manager.load_config("config.json")

# Validate
errors = config_manager.validate_config()
if errors:
    print(f"Configuration errors: {errors}")
```

### 3. Multiple Sources

```python
from gemini_sre_agent.ingestion.adapters import (
    GCPPubSubAdapter, GCPPubSubConfig,
    FileSystemAdapter, FileSystemConfig
)

async def setup_sources():
    manager = LogManager(callback=log_callback)

    # Add GCP Pub/Sub source
    gcp_config = GCPPubSubConfig(
        name="gcp-logs",
        project_id="my-project",
        subscription_id="log-subscription"
    )
    await manager.add_source(GCPPubSubAdapter(gcp_config))

    # Add file system source
    fs_config = FileSystemConfig(
        name="file-logs",
        file_path="/var/log/apps"
    )
    await manager.add_source(FileSystemAdapter(fs_config))

    return manager
```

## Configuration

### Basic Configuration

```json
{
  "sources": [
    {
      "name": "gcp-pubsub-logs",
      "type": "gcp_pubsub",
      "enabled": true,
      "priority": 10,
      "config": {
        "project_id": "my-gcp-project",
        "subscription_id": "log-ingestion-sub",
        "credentials_path": "/path/to/service-account.json"
      },
      "max_retries": 3,
      "retry_delay": 1.0,
      "timeout": 30.0,
      "circuit_breaker_enabled": true,
      "rate_limit_per_second": 100
    }
  ],
  "global_max_throughput": 500,
  "global_error_threshold": 0.05,
  "enable_metrics": true,
  "enable_health_checks": true,
  "health_check_interval": 30,
  "max_message_length": 10000,
  "enable_pii_detection": true,
  "enable_flow_tracking": true,
  "default_buffer_size": 1000,
  "max_memory_mb": 500,
  "backpressure_threshold": 0.8,
  "drop_oldest_on_full": true
}
```

### Source Types

#### GCP Pub/Sub

```json
{
  "name": "gcp-pubsub",
  "type": "gcp_pubsub",
  "config": {
    "project_id": "my-project",
    "subscription_id": "my-subscription",
    "credentials_path": "/path/to/credentials.json"
  }
}
```

#### GCP Logging

```json
{
  "name": "gcp-logging",
  "type": "gcp_logging",
  "config": {
    "project_id": "my-project",
    "log_filter": "severity>=ERROR",
    "credentials_path": "/path/to/credentials.json",
    "poll_interval": 30
  }
}
```

#### File System

```json
{
  "name": "file-system",
  "type": "file_system",
  "config": {
    "file_path": "/var/log/applications",
    "file_pattern": "*.log",
    "watch_mode": true,
    "encoding": "utf-8",
    "buffer_size": 1000,
    "max_memory_mb": 100
  }
}
```

## Memory Queue and Buffering

The system supports different buffering strategies:

### 1. Direct Processing (No Queue)

- Single consumer
- Low to medium log volume (< 100 logs/second)
- Simple deployment

### 2. Memory Queue/Buffer (Recommended)

- High-volume log processing (100-1000 logs/second)
- Backpressure handling
- Resilience against transient failures
- Configurable buffer size and memory limits

### 3. External Message Broker

- Very high-volume processing (> 1000 logs/second)
- Distributed systems
- Persistent storage requirements

## Error Handling

The system includes comprehensive error handling:

- **Circuit Breakers**: Prevent cascading failures
- **Retry Logic**: Exponential backoff with configurable limits
- **Backpressure**: Automatic throttling when downstream systems are slow
- **Health Monitoring**: Continuous health checks with metrics

## Monitoring and Metrics

### Health Checks

```python
health = await manager.get_health_status()
for source_name, health_status in health.items():
    print(f"{source_name}: {'Healthy' if health_status.is_healthy else 'Unhealthy'}")
```

### Metrics

```python
metrics = await manager.get_metrics()
print(f"Total sources: {metrics['manager']['total_sources']}")
print(f"Backpressure stats: {metrics['backpressure']}")
```

## Examples

See the `examples/` directory for:

- `ingestion_example.py`: Basic usage example
- `ingestion_configs/`: Configuration examples
- `basic_config.json`: Simple multi-source configuration
- `gcp_only_config.yaml`: GCP-focused configuration
- `file_system_config.yaml`: File system focused configuration

## Migration from Legacy System

The new system is designed to be backward compatible. To migrate:

1. **Update imports**:

   ```python
   # Old
   from gemini_sre_agent.log_subscriber import LogSubscriber

   # New
   from gemini_sre_agent.ingestion import LogManager
   from gemini_sre_agent.ingestion.adapters import GCPPubSubAdapter
   ```

2. **Update configuration**:
   - Convert existing GCP Pub/Sub settings to new config format
   - Add new features like health monitoring and buffering

3. **Update callbacks**:
   - New system uses `LogEntry` objects instead of raw messages
   - Enhanced metadata and flow tracking available

## Performance Considerations

- **Memory Usage**: Configure buffer sizes based on available memory
- **Throughput**: Set appropriate rate limits to prevent overwhelming downstream systems
- **Latency**: Use memory buffering for high-throughput scenarios
- **Reliability**: Enable circuit breakers and health monitoring for production use

## Security

- **PII Detection**: Automatic detection and masking of sensitive information
- **Credential Management**: Secure handling of service account credentials
- **Access Control**: Configurable permissions for different log sources
- **Data Sanitization**: Built-in sanitization of log content
