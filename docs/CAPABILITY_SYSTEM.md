# Model Capability Discovery System

## Overview

The Model Capability Discovery System is a comprehensive framework for discovering, cataloging, and managing the capabilities of Large Language Models (LLMs) across different providers. It enables intelligent model selection based on task requirements and provides caching, metrics, and configuration management.

## Architecture

### Core Components

1. **CapabilityDiscovery**: Main orchestrator for discovering and managing model capabilities
2. **CapabilityConfig**: Configuration management for capability definitions
3. **ModelCapability**: Data model representing individual capabilities
4. **ModelCapabilities**: Container for a model's complete capability set
5. **CapabilityDatabase**: Storage and query interface for capabilities
6. **CapabilityComparer**: Comparison utilities for model capabilities
7. **CapabilityTester**: Testing framework for validating capabilities

### Key Features

- **Automatic Discovery**: Automatically discovers capabilities from provider configurations
- **Caching**: Intelligent caching with TTL to avoid repeated provider queries
- **Metrics & Monitoring**: Comprehensive metrics and health monitoring
- **Configuration Management**: YAML-based capability definitions
- **Task-Based Selection**: Find models based on task requirements
- **Performance Optimization**: Async operations and batch processing

## Usage Examples

### Basic Usage

```python
from gemini_sre_agent.llm.capabilities.discovery import CapabilityDiscovery
from gemini_sre_agent.llm.factory import LLMProviderFactory

# Initialize providers
providers = LLMProviderFactory.create_providers_from_config(llm_config)

# Create capability discovery instance
discovery = CapabilityDiscovery(providers, cache_ttl=3600)

# Discover capabilities for all models
capabilities = await discovery.discover_capabilities()

# Get capabilities for a specific model
model_caps = discovery.get_model_capabilities("openai/gpt-4")
if model_caps:
    print(f"Model supports: {[cap.name for cap in model_caps.capabilities]}")
```

### Task-Based Model Selection

```python
# Find models suitable for code generation
suitable_models = discovery.find_models_for_task("code_generation", min_coverage=0.8)

for model_info in suitable_models:
    print(f"Model: {model_info['model_id']}")
    print(f"Coverage: {model_info['coverage_score']:.2f}")
    print(f"Capabilities: {model_info['capabilities']}")
    print("---")
```

### Validation and Requirements

```python
# Validate if a model meets task requirements
validation_result = discovery.validate_task_requirements("text_completion", "openai/gpt-4")

if validation_result["meets_requirements"]:
    print("Model meets all requirements!")
else:
    print(f"Missing required capabilities: {validation_result['missing_required']}")
    print(f"Available optional capabilities: {validation_result['available_optional']}")
```

### Metrics and Health Monitoring

```python
# Get system metrics
metrics = discovery.get_metrics()
print(f"Discovery attempts: {metrics['discovery_attempts']}")
print(f"Success rate: {metrics['discovery_successes'] / metrics['discovery_attempts']:.2f}")
print(f"Cache hit rate: {metrics['cache_hits'] / (metrics['cache_hits'] + metrics['cache_misses']):.2f}")

# Get health status
health = discovery.get_health_status()
print(f"System status: {health['status']}")
print(f"Total models: {health['total_models']}")
print(f"Average discovery time: {health['average_discovery_time']:.2f}s")
```

### Configuration Management

```python
from gemini_sre_agent.llm.capabilities.config import get_capability_config

# Get capability configuration
config = get_capability_config()

# Get all available capabilities
all_capabilities = config.get_all_capabilities()
print(f"Available capabilities: {list(all_capabilities.keys())}")

# Get provider-specific capabilities
openai_caps = config.get_provider_capabilities("openai", "gpt-4")
print(f"OpenAI GPT-4 capabilities: {openai_caps}")

# Get task requirements
requirements = config.get_task_requirements("code_generation")
print(f"Required: {requirements['required_capabilities']}")
print(f"Optional: {requirements['optional_capabilities']}")
```

## Configuration

### Capability Definitions

Capabilities are defined in `config/capability_definitions.yaml`:

```yaml
capabilities:
  text_generation:
    name: "text_generation"
    description: "Generates human-like text based on a given prompt"
    parameters:
      max_tokens:
        type: "integer"
        description: "Maximum number of tokens to generate"
        default: 1000
      temperature:
        type: "float"
        description: "Controls randomness in generation"
        default: 0.7
    performance_score: 0.8
    cost_efficiency: 0.7

  code_generation:
    name: "code_generation"
    description: "Generates programming code in various languages"
    parameters:
      language:
        type: "string"
        description: "Programming language for code generation"
        options: ["python", "javascript", "typescript", "java"]
    performance_score: 0.9
    cost_efficiency: 0.6
```

### Provider Mappings

Define which capabilities each provider supports:

```yaml
provider_mappings:
  openai:
    default_capabilities: ["text_generation", "streaming", "tool_calling"]
    model_specific:
      gpt-4:
        additional_capabilities: ["reasoning", "multimodal"]
      gpt-3.5-turbo:
        additional_capabilities: ["reasoning"]
```

### Task Requirements

Define capability requirements for different task types:

```yaml
task_requirements:
  text_completion:
    required_capabilities: ["text_generation"]
    optional_capabilities: ["streaming", "memory"]
  
  code_generation:
    required_capabilities: ["code_generation"]
    optional_capabilities: ["reasoning", "tool_calling"]
```

## API Reference

### CapabilityDiscovery

#### Methods

- `discover_capabilities(force_refresh=False)`: Discover capabilities for all models
- `get_model_capabilities(model_id, auto_refresh=True)`: Get capabilities for a specific model
- `find_models_by_capability(capability_name)`: Find models supporting a capability
- `find_models_by_capabilities(capability_names, require_all=False)`: Find models supporting multiple capabilities
- `find_models_for_task(task_type, min_coverage=0.8)`: Find models suitable for a task
- `validate_task_requirements(task_type, model_id)`: Validate model against task requirements
- `get_capability_summary()`: Get summary of capability distribution
- `get_metrics()`: Get system performance metrics
- `get_health_status()`: Get system health information
- `clear_cache()`: Clear all cached data
- `reset_metrics()`: Reset performance metrics

#### Properties

- `model_capabilities`: Dictionary of discovered model capabilities
- `cache_ttl`: Cache time-to-live in seconds
- `capability_config`: Capability configuration instance

### CapabilityConfig

#### Methods

- `get_capability(name)`: Get capability definition by name
- `get_all_capabilities()`: Get all capability definitions
- `get_provider_capabilities(provider_name, model_name=None)`: Get provider capabilities
- `get_task_requirements(task_type)`: Get task capability requirements
- `validate_capability_requirements(task_type, available_capabilities)`: Validate requirements
- `reload_config()`: Reload configuration from file

### ModelCapability

#### Properties

- `name`: Capability name
- `description`: Human-readable description
- `parameters`: Parameter definitions
- `performance_score`: Performance rating (0.0 to 1.0)
- `cost_efficiency`: Cost efficiency rating (0.0 to 1.0)

## Performance Optimization

### Caching

The system implements intelligent caching with the following features:

- **TTL-based expiration**: Configurable cache time-to-live
- **Cache hit/miss tracking**: Metrics for cache performance
- **Force refresh option**: Bypass cache when needed
- **Concurrent access protection**: Prevents duplicate discovery

### Async Operations

All discovery operations are fully async:

```python
# Async capability discovery
capabilities = await discovery.discover_capabilities()

# Async capability testing
tester = CapabilityTester(providers)
results = await tester.test_capabilities(["text_generation", "code_generation"])
```

### Batch Operations

Support for batch capability queries:

```python
# Find models supporting multiple capabilities
models = discovery.find_models_by_capabilities(
    ["text_generation", "streaming", "tool_calling"],
    require_all=True
)
```

## Monitoring and Observability

### Metrics

The system tracks comprehensive metrics:

- **Discovery Performance**: Attempts, successes, failures, timing
- **Cache Performance**: Hit/miss rates, efficiency
- **System Health**: Success rates, model counts, performance

### Health Checks

Health status includes:

- **Overall Status**: healthy/degraded/unhealthy
- **Success Rate**: Percentage of successful discoveries
- **Cache Hit Rate**: Cache efficiency
- **Model Count**: Total discovered models
- **Performance**: Average discovery time

### Logging

Comprehensive logging at multiple levels:

- **DEBUG**: Detailed discovery process
- **INFO**: High-level operations and status
- **WARNING**: Non-critical issues
- **ERROR**: Critical failures

## Integration

### Main System Integration

The capability discovery system is integrated into the main application:

```python
# In main.py
capability_discovery = CapabilityDiscovery(all_providers)
await capability_discovery.discover_capabilities()
logger.info(f"Discovered capabilities for {len(capability_discovery.model_capabilities)} models")
```

### Model Selection Integration

Use with the model selection system:

```python
from gemini_sre_agent.llm.model_selector import ModelSelector

# Create model selector with capability discovery
model_selector = ModelSelector(model_registry, capability_discovery, model_scorer)

# Select model based on task requirements
selected_model = model_selector.select_model(task_context)
```

## Troubleshooting

### Common Issues

1. **Configuration Not Found**
   - Ensure `config/capability_definitions.yaml` exists
   - Check file permissions and YAML syntax

2. **Provider Capabilities Not Discovered**
   - Verify provider configuration
   - Check provider-specific capability mappings

3. **Cache Issues**
   - Clear cache with `discovery.clear_cache()`
   - Check cache TTL settings

4. **Performance Issues**
   - Monitor metrics for bottlenecks
   - Adjust cache TTL for your use case
   - Consider batch operations for multiple queries

### Debug Mode

Enable debug logging for detailed information:

```python
import logging
logging.getLogger("gemini_sre_agent.llm.capabilities").setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features

1. **Real-time Capability Updates**: Dynamic capability discovery
2. **Advanced Caching**: Redis-based distributed caching
3. **Machine Learning**: ML-based capability prediction
4. **API Endpoints**: REST API for capability queries
5. **Dashboard**: Web-based monitoring interface

### Extension Points

The system is designed for easy extension:

- **Custom Capabilities**: Add new capability types
- **Provider Plugins**: Support for new providers
- **Validation Rules**: Custom requirement validation
- **Scoring Algorithms**: Custom performance scoring

## Contributing

When contributing to the capability system:

1. **Follow the existing patterns** for capability definitions
2. **Add comprehensive tests** for new functionality
3. **Update documentation** for new features
4. **Consider backward compatibility** when making changes
5. **Add appropriate logging** for debugging

## License

This capability discovery system is part of the Gemini SRE Agent project and follows the same licensing terms.
