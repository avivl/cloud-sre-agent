# LLM Configuration Examples

This directory contains comprehensive examples and tools for configuring the multi-provider LLM system in the Gemini SRE Agent.

## Configuration Files

### Multi-Provider Configuration

- **`multi_provider_config.yaml`** - Comprehensive setup with all supported providers (OpenAI, Anthropic, xAI, Bedrock, Ollama)
- **`cost_optimized_config.yaml`** - Budget-conscious configuration prioritizing cost efficiency
- **`development_config.yaml`** - Local development setup with Ollama as primary provider
- **`production_config.yaml`** - Production-grade configuration with high reliability and monitoring

## Tools

### Configuration Validation

- **`validate_config.py`** - CLI tool for validating configuration files and testing provider connections

```bash
# Basic validation
python validate_config.py multi_provider_config.yaml

# Test provider connections
python validate_config.py multi_provider_config.yaml --test-providers

# Verbose output
python validate_config.py multi_provider_config.yaml --verbose

# Save results to file
python validate_config.py multi_provider_config.yaml --output results.json
```

## Quick Start

### 1. Choose Your Configuration

Select the configuration that best fits your needs:

- **Development**: Use `development_config.yaml` for local development with Ollama
- **Production**: Use `production_config.yaml` for production deployments
- **Cost-Conscious**: Use `cost_optimized_config.yaml` for budget-limited environments
- **Full-Featured**: Use `multi_provider_config.yaml` for comprehensive multi-provider setup

### 2. Set Up Environment Variables

Create a `.env` file with your API keys:

```bash
# Required API keys
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
XAI_API_KEY=xai-...
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# Optional: Organization/Project IDs
GEMINI_PROJECT_ID=your-gemini-project
OPENAI_ORG_ID=org-...
OPENAI_PROJECT_ID=proj-...
```

### 3. Validate Your Configuration

```bash
# Validate the configuration
python validate_config.py your_config.yaml --test-providers
```

### 4. Use in Your Application

```python
from gemini_sre_agent.llm.config_manager import get_config_manager
from gemini_sre_agent.analysis_agent import AnalysisAgent

# Load configuration
config_manager = get_config_manager("your_config.yaml")
config = config_manager.get_config()

# Create agent
agent = AnalysisAgent(config=config)

# Use agent
result = agent.analyze_logs(log_entries)
```

## Configuration Scenarios

### Single Provider Setup

For simple setups with a single provider:

```yaml
default_provider: "gemini"
providers:
  gemini:
    provider: "gemini"
    api_key: "${GEMINI_API_KEY}"
    models:
      gemini-1.5-flash:
        name: "gemini-1.5-flash"
        model_type: "FAST"
        cost_per_1k_tokens: 0.000075
        max_tokens: 8192
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation", "analysis"]
```

### Multi-Provider with Fallbacks

For high-reliability setups:

```yaml
default_provider: "gemini"
providers:
  gemini:
    # ... Gemini configuration
  openai:
    # ... OpenAI configuration
  anthropic:
    # ... Anthropic configuration
  grok:
    # ... Grok configuration

agents:
  analysis_agent:
    primary_provider: "gemini"
    fallback_providers: ["openai", "anthropic", "grok"]
    model_selection_strategy: "quality_optimized"
```

### Local Development

For development with local models:

```yaml
default_provider: "gemini"
providers:
  gemini:
    provider: "gemini"
    api_key: "${GEMINI_API_KEY}"
    models:
      gemini-1.5-flash:
        name: "gemini-1.5-flash"
        model_type: "FAST"
        cost_per_1k_tokens: 0.000075
        max_tokens: 8192
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation", "analysis"]
  ollama:
    provider: "ollama"
    base_url: "http://localhost:11434"
    models:
      llama3.1:8b:
        name: "llama3.1:8b"
        model_type: "FAST"
        cost_per_1k_tokens: 0.0
        max_tokens: 8192
        supports_streaming: true
        supports_tools: false
        capabilities: ["reasoning", "code_generation"]
```

## Best Practices

### Security

- Never hardcode API keys in configuration files
- Use environment variables for all sensitive data
- Implement proper access controls and monitoring
- Rotate API keys regularly

### Performance

- Choose appropriate models for each task type
- Implement caching where appropriate
- Use fallback providers for reliability
- Monitor costs and usage patterns

### Reliability

- Test all provider connections before deployment
- Implement circuit breakers and retry logic
- Set up comprehensive monitoring and alerting
- Plan for provider outages

## Troubleshooting

### Common Issues

1. **Invalid API Keys**: Verify API keys are correct and have proper permissions
2. **Provider Connection Failures**: Check network connectivity and API endpoints
3. **Configuration Validation Errors**: Use the validation tool to identify issues
4. **Model Not Found**: Ensure model names match provider specifications

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
export LLM_LOG_LEVEL=DEBUG
python validate_config.py your_config.yaml --verbose
```

### Getting Help

1. Check the [Multi-Provider LLM Configuration Guide](../../docs/MULTI_PROVIDER_LLM_CONFIGURATION.md)
2. Review the [Migration Guide](../../docs/MIGRATION_GUIDE_SINGLE_TO_MULTI_PROVIDER.md)
3. Consult the [Secure Credential Management Guide](../../docs/SECURE_CREDENTIAL_MANAGEMENT.md)
4. Use the validation tools to identify configuration issues

## Examples by Use Case

### Cost Optimization

- Use `cost_optimized_config.yaml` as a starting point
- Prioritize fast, low-cost models for routine tasks
- Use local models (Ollama) for development
- Implement cost monitoring and alerts

### High Availability

- Use `production_config.yaml` as a starting point
- Configure multiple providers with fallbacks
- Implement circuit breakers and health checks
- Set up comprehensive monitoring

### Development

- Use `development_config.yaml` as a starting point
- Use local models to reduce costs
- Enable debug logging and verbose output
- Test with multiple providers

### Enterprise

- Use `multi_provider_config.yaml` as a starting point
- Implement proper secret management
- Set up audit logging and compliance monitoring
- Configure role-based access controls

This comprehensive set of examples and tools provides everything needed to configure and manage the multi-provider LLM system effectively.
