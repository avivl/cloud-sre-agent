# Multi-Provider LLM Configuration Guide

This guide covers the comprehensive multi-provider LLM configuration system that enables the Gemini SRE Agent to work with multiple LLM providers simultaneously, including Google Gemini, OpenAI, Anthropic, xAI (Grok), Amazon Bedrock, and Ollama.

## Overview

The multi-provider LLM configuration system provides:

- **Multi-provider support** with unified configuration interface
- **Semantic model naming** for consistent model selection across providers
- **Cost management** with per-provider and per-model cost tracking
- **Resilience patterns** including circuit breakers, retries, and fallbacks
- **Hot-reloading** configuration updates without service restart
- **Type-safe validation** using Pydantic v2.0+ models
- **Environment variable integration** for secure credential management

## Configuration Architecture

```mermaid
graph TD
    subgraph "Multi-Provider LLM Configuration"
        ROOT[LLMConfig]

        ROOT --> PROVIDERS[providers: Dict[str, LLMProviderConfig]]
        ROOT --> AGENTS[agents: Dict[str, AgentLLMConfig]]
        ROOT --> DEFAULTS[default_provider: str]
        ROOT --> MODEL_TYPE[default_model_type: ModelType]
        ROOT --> FALLBACK[enable_fallback: bool]
        ROOT --> MONITORING[enable_monitoring: bool]
        ROOT --> COST[cost_config: CostConfig]
        ROOT --> RESILIENCE[resilience_config: ResilienceConfig]

        PROVIDERS --> P1[Google Gemini Provider]
        PROVIDERS --> P2[OpenAI Provider]
        PROVIDERS --> P3[Anthropic Provider]
        PROVIDERS --> P4[Grok Provider]
        PROVIDERS --> P5[Bedrock Provider]
        PROVIDERS --> P6[Ollama Provider]

        P1 --> M1[Gemini Models]
        P2 --> M2[OpenAI Models]
        P3 --> M3[Anthropic Models]
        P4 --> M4[Grok Models]
        P5 --> M5[Bedrock Models]
        P6 --> M6[Ollama Models]

        M1 --> MODEL_CONFIG[ModelConfig]
        M2 --> MODEL_CONFIG
        M3 --> MODEL_CONFIG
        M4 --> MODEL_CONFIG
        M5 --> MODEL_CONFIG
        M6 --> MODEL_CONFIG

        MODEL_CONFIG --> NAME[name: str]
        MODEL_CONFIG --> TYPE[model_type: ModelType]
        MODEL_CONFIG --> COST[cost_per_1k_tokens: float]
        MODEL_CONFIG --> TOKENS[max_tokens: int]
        MODEL_CONFIG --> STREAMING[supports_streaming: bool]
        MODEL_CONFIG --> TOOLS[supports_tools: bool]
        MODEL_CONFIG --> CAPABILITIES[capabilities: List[str]]

        AGENTS --> A1[Analysis Agent]
        AGENTS --> A2[Triage Agent]
        AGENTS --> A3[Remediation Agent]

        A1 --> AGENT_CONFIG[AgentLLMConfig]
        A2 --> AGENT_CONFIG
        A3 --> AGENT_CONFIG

        AGENT_CONFIG --> PRIMARY[primary_provider: str]
        AGENT_CONFIG --> FALLBACK_PROVIDERS[fallback_providers: List[str]]
        AGENT_CONFIG --> MODEL_SELECTION[model_selection_strategy: str]
    end

    classDef required fill:#ffebee,stroke:#d32f2f,stroke-width:2px
    classDef optional fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef config fill:#e1f5fe,stroke:#01579b,stroke-width:2px

    class ROOT,PROVIDERS,AGENTS,DEFAULTS required
    class MODEL_TYPE,FALLBACK,MONITORING,COST,RESILIENCE optional
    class P1,P2,P3,P4,P5,P6,M1,M2,M3,M4,M5,M6,A1,A2,A3 config
```

## Configuration Structure

### Main Configuration (LLMConfig)

The root configuration class that orchestrates all LLM providers and agents:

```yaml
# Main LLM configuration
default_provider: "openai" # Default provider name
default_model_type: "SMART" # Default model type
enable_fallback: true # Enable fallback mechanisms
enable_monitoring: true # Enable monitoring and metrics

# Provider configurations
providers:
  openai:
    provider: "openai"
    api_key: "${OPENAI_API_KEY}" # Environment variable
    base_url: "https://api.openai.com/v1"
    timeout: 30
    max_retries: 3
    rate_limit: 60
    models:
      gpt-4o:
        name: "gpt-4o"
        model_type: "SMART"
        cost_per_1k_tokens: 0.005
        max_tokens: 128000
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation", "analysis"]
      gpt-4o-mini:
        name: "gpt-4o-mini"
        model_type: "FAST"
        cost_per_1k_tokens: 0.00015
        max_tokens: 128000
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation"]

# Agent configurations
agents:
  analysis_agent:
    primary_provider: "openai"
    fallback_providers: ["anthropic", "grok"]
    model_selection_strategy: "cost_optimized"
    max_tokens: 32000
    temperature: 0.3
    timeout: 60
  triage_agent:
    primary_provider: "openai"
    fallback_providers: ["anthropic"]
    model_selection_strategy: "speed_optimized"
    max_tokens: 8000
    temperature: 0.1
    timeout: 30

# Cost management
cost_config:
  monthly_budget: 1000.0
  alert_threshold: 0.8
  enable_tracking: true
  cost_optimization: true

# Resilience configuration
resilience_config:
  circuit_breaker_threshold: 5
  circuit_breaker_timeout: 60
  retry_attempts: 3
  retry_delay: 1.0
  retry_backoff: 2.0
  fallback_enabled: true
```

## Provider Configurations

### Google Gemini Provider

```yaml
providers:
  gemini:
    provider: "gemini"
    api_key: "${GEMINI_API_KEY}"
    base_url: "https://generativelanguage.googleapis.com/v1"
    timeout: 30
    max_retries: 3
    rate_limit: 60
    models:
      gemini-1.5-flash:
        name: "gemini-1.5-flash"
        model_type: "FAST"
        cost_per_1k_tokens: 0.000075
        max_tokens: 8192
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation", "analysis"]
      gemini-1.5-pro:
        name: "gemini-1.5-pro"
        model_type: "SMART"
        cost_per_1k_tokens: 0.0005
        max_tokens: 32768
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation", "analysis", "vision"]
      gemini-1.5-flash-lite:
        name: "gemini-1.5-flash-lite"
        model_type: "FAST"
        cost_per_1k_tokens: 0.0000375
        max_tokens: 4096
        supports_streaming: true
        supports_tools: false
        capabilities: ["reasoning", "code_generation"]
    provider_specific:
      project_id: "${GEMINI_PROJECT_ID}"
```

**Security Considerations:**

- Use project-specific API keys when possible
- Set usage limits and alerts
- Monitor usage patterns for anomalies
- Rotate keys regularly (every 90 days)

### OpenAI Provider

```yaml
providers:
  openai:
    provider: "openai"
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
    timeout: 30
    max_retries: 3
    rate_limit: 60
    models:
      gpt-4o:
        name: "gpt-4o"
        model_type: "SMART"
        cost_per_1k_tokens: 0.005
        max_tokens: 128000
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation", "analysis", "vision"]
      gpt-4o-mini:
        name: "gpt-4o-mini"
        model_type: "FAST"
        cost_per_1k_tokens: 0.00015
        max_tokens: 128000
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation"]
      gpt-3.5-turbo:
        name: "gpt-3.5-turbo"
        model_type: "FAST"
        cost_per_1k_tokens: 0.0005
        max_tokens: 16384
        supports_streaming: true
        supports_tools: false
        capabilities: ["reasoning", "code_generation"]
    provider_specific:
      organization: "${OPENAI_ORG_ID}" # Optional
      project: "${OPENAI_PROJECT_ID}" # Optional
```

### Anthropic Provider

```yaml
providers:
  anthropic:
    provider: "anthropic"
    api_key: "${ANTHROPIC_API_KEY}"
    base_url: "https://api.anthropic.com"
    timeout: 30
    max_retries: 3
    rate_limit: 50
    models:
      claude-3-5-sonnet-20241022:
        name: "claude-3-5-sonnet-20241022"
        model_type: "SMART"
        cost_per_1k_tokens: 0.003
        max_tokens: 200000
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation", "analysis", "vision"]
      claude-3-5-haiku-20241022:
        name: "claude-3-5-haiku-20241022"
        model_type: "FAST"
        cost_per_1k_tokens: 0.00025
        max_tokens: 200000
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation"]
      claude-3-opus-20240229:
        name: "claude-3-opus-20240229"
        model_type: "SMART"
        cost_per_1k_tokens: 0.015
        max_tokens: 200000
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation", "analysis", "vision"]
    provider_specific:
      version: "2023-06-01"
```

### xAI (Grok) Provider

```yaml
providers:
  grok:
    provider: "grok"
    api_key: "${XAI_API_KEY}"
    base_url: "https://api.x.ai/v1"
    timeout: 30
    max_retries: 3
    rate_limit: 60
    models:
      grok-beta:
        name: "grok-beta"
        model_type: "SMART"
        cost_per_1k_tokens: 0.002
        max_tokens: 32768
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation", "analysis"]
      grok-2-1212:
        name: "grok-2-1212"
        model_type: "SMART"
        cost_per_1k_tokens: 0.002
        max_tokens: 32768
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation", "analysis"]
    provider_specific:
      version: "2024-12-12"
```

### Amazon Bedrock Provider

```yaml
providers:
  bedrock:
    provider: "bedrock"
    api_key: "${AWS_ACCESS_KEY_ID}" # AWS Access Key
    base_url: "https://bedrock-runtime.us-east-1.amazonaws.com"
    region: "us-east-1" # Required for Bedrock
    timeout: 30
    max_retries: 3
    rate_limit: 30
    models:
      anthropic.claude-3-5-sonnet-20241022-v2:0:
        name: "anthropic.claude-3-5-sonnet-20241022-v2:0"
        model_type: "SMART"
        cost_per_1k_tokens: 0.003
        max_tokens: 200000
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation", "analysis"]
      anthropic.claude-3-5-haiku-20241022-v1:0:
        name: "anthropic.claude-3-5-haiku-20241022-v1:0"
        model_type: "FAST"
        cost_per_1k_tokens: 0.00025
        max_tokens: 200000
        supports_streaming: true
        supports_tools: true
        capabilities: ["reasoning", "code_generation"]
      meta.llama-3-1-405b-instruct-v1:0:
        name: "meta.llama-3-1-405b-instruct-v1:0"
        model_type: "SMART"
        cost_per_1k_tokens: 0.00265
        max_tokens: 8192
        supports_streaming: true
        supports_tools: false
        capabilities: ["reasoning", "code_generation"]
    provider_specific:
      aws_region: "us-east-1"
      aws_profile: "default" # Optional
```

### Ollama Provider (Local)

```yaml
providers:
  ollama:
    provider: "ollama"
    # No API key required for local Ollama
    base_url: "http://localhost:11434"
    timeout: 120 # Longer timeout for local models
    max_retries: 2
    rate_limit: null # No rate limit for local
    models:
      llama3.1:8b:
        name: "llama3.1:8b"
        model_type: "FAST"
        cost_per_1k_tokens: 0.0 # Free for local
        max_tokens: 8192
        supports_streaming: true
        supports_tools: false
        capabilities: ["reasoning", "code_generation"]
      llama3.1:70b:
        name: "llama3.1:70b"
        model_type: "SMART"
        cost_per_1k_tokens: 0.0 # Free for local
        max_tokens: 8192
        supports_streaming: true
        supports_tools: false
        capabilities: ["reasoning", "code_generation", "analysis"]
      codellama:7b:
        name: "codellama:7b"
        model_type: "FAST"
        cost_per_1k_tokens: 0.0 # Free for local
        max_tokens: 16384
        supports_streaming: true
        supports_tools: false
        capabilities: ["code_generation", "code_analysis"]
    provider_specific:
      host: "localhost"
      port: 11434
      tls: false
```

## Agent Configurations

### Analysis Agent

```yaml
agents:
  analysis_agent:
    primary_provider: "openai"
    fallback_providers: ["anthropic", "grok"]
    model_selection_strategy: "cost_optimized" # cost_optimized, speed_optimized, quality_optimized
    max_tokens: 32000
    temperature: 0.3
    timeout: 60
    retry_attempts: 3
    enable_streaming: true
    enable_tools: true
    model_preferences:
      - "gpt-4o"
      - "claude-3-5-sonnet-20241022"
      - "grok-beta"
```

### Triage Agent

```yaml
agents:
  triage_agent:
    primary_provider: "openai"
    fallback_providers: ["anthropic"]
    model_selection_strategy: "speed_optimized"
    max_tokens: 8000
    temperature: 0.1
    timeout: 30
    retry_attempts: 2
    enable_streaming: false
    enable_tools: false
    model_preferences:
      - "gpt-4o-mini"
      - "claude-3-5-haiku-20241022"
```

### Remediation Agent

```yaml
agents:
  remediation_agent:
    primary_provider: "anthropic"
    fallback_providers: ["openai", "grok"]
    model_selection_strategy: "quality_optimized"
    max_tokens: 64000
    temperature: 0.2
    timeout: 90
    retry_attempts: 3
    enable_streaming: true
    enable_tools: true
    model_preferences:
      - "claude-3-5-sonnet-20241022"
      - "gpt-4o"
      - "grok-beta"
```

## Cost Management

### Cost Configuration

```yaml
cost_config:
  monthly_budget: 1000.0 # USD
  alert_threshold: 0.8 # Alert at 80% of budget
  enable_tracking: true
  cost_optimization: true
  optimization_strategy: "balanced" # balanced, aggressive, conservative
  cost_breakdown:
    by_provider: true
    by_model: true
    by_agent: true
  alerts:
    email: "admin@company.com"
    webhook: "https://hooks.slack.com/services/..."
    threshold_percentages: [50, 75, 90, 100]
```

## Resilience Configuration

### Resilience Patterns

```yaml
resilience_config:
  circuit_breaker_threshold: 5 # Failures before opening circuit
  circuit_breaker_timeout: 60 # Seconds before trying again
  retry_attempts: 3
  retry_delay: 1.0 # Initial delay in seconds
  retry_backoff: 2.0 # Exponential backoff multiplier
  fallback_enabled: true
  health_check_interval: 30 # Seconds between health checks
  timeout_multiplier: 1.5 # Timeout multiplier for retries
  jitter_enabled: true # Add random jitter to retries
  max_concurrent_requests: 10
  rate_limiting:
    enabled: true
    requests_per_minute: 60
    burst_size: 10
```

## Model Types and Capabilities

### Model Types

The system supports three semantic model types:

- **`FAST`**: Optimized for speed and low cost (e.g., GPT-4o-mini, Claude Haiku)
- **`SMART`**: Balanced performance and capability (e.g., GPT-4o, Claude Sonnet)
- **`POWERFUL`**: Maximum capability for complex tasks (e.g., GPT-4, Claude Opus)

### Capabilities

Models can be tagged with capabilities:

- **`reasoning`**: Complex logical reasoning
- **`code_generation`**: Code writing and modification
- **`code_analysis`**: Code review and analysis
- **`analysis`**: Data analysis and interpretation
- **`vision`**: Image and visual content processing
- **`tool_use`**: Function calling and tool usage
- **`streaming`**: Real-time response streaming
- **`long_context`**: Large context window support

## Environment Variables

### Required Environment Variables

```bash
# Google Gemini
export GEMINI_API_KEY="AIza..."

# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# xAI (Grok)
export XAI_API_KEY="xai-..."

# AWS Bedrock
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="us-east-1"

# Optional: Organization/Project IDs
export GEMINI_PROJECT_ID="your-gemini-project"
export OPENAI_ORG_ID="org-..."
export OPENAI_PROJECT_ID="proj-..."
```

### Configuration Override Variables

```bash
# Override default provider
export LLM_DEFAULT_PROVIDER="anthropic"

# Override default model type
export LLM_DEFAULT_MODEL_TYPE="SMART"

# Enable/disable features
export LLM_ENABLE_FALLBACK="true"
export LLM_ENABLE_MONITORING="true"

# Cost management
export LLM_MONTHLY_BUDGET="500.0"
export LLM_ALERT_THRESHOLD="0.8"
```

## Usage Examples

### Basic Usage

```python
from gemini_sre_agent.llm.config_manager import get_config_manager

# Get configuration manager
config_manager = get_config_manager()

# Get configuration
config = config_manager.get_config()

# Get specific provider configuration
openai_config = config_manager.get_provider_config("openai")

# Get agent configuration
analysis_config = config_manager.get_agent_config("analysis_agent")
```

### Provider Factory Usage

```python
from gemini_sre_agent.llm.factory import LLMProviderFactory
from gemini_sre_agent.llm.config_manager import get_config_manager

# Get configuration
config_manager = get_config_manager()
config = config_manager.get_config()

# Create provider factory
factory = LLMProviderFactory(config)

# Create provider instance
openai_provider = factory.create_provider("openai")

# Use provider
response = openai_provider.generate_response(
    prompt="Analyze this log entry...",
    model="gpt-4o",
    max_tokens=1000
)
```

### Agent Usage

```python
from gemini_sre_agent.analysis_agent import AnalysisAgent
from gemini_sre_agent.llm.config_manager import get_config_manager

# Get configuration
config_manager = get_config_manager()
config = config_manager.get_config()

# Create agent with configuration
agent = AnalysisAgent(config=config)

# Use agent
result = agent.analyze_logs(log_entries)
```

## Configuration Validation

### CLI Validation

```bash
# Validate configuration file
python -m gemini_sre_agent.llm.config_manager validate config/llm_config.yaml

# Validate with detailed output
python -m gemini_sre_agent.llm.config_manager validate config/llm_config.yaml --verbose

# Test provider connections
python -m gemini_sre_agent.llm.config_manager test-providers config/llm_config.yaml
```

### Programmatic Validation

```python
from gemini_sre_agent.llm.config_manager import ConfigManager
from gemini_sre_agent.llm.config import LLMConfig

# Validate configuration
try:
    config_manager = ConfigManager("config/llm_config.yaml")
    config = config_manager.get_config()
    print("Configuration is valid!")
except Exception as e:
    print(f"Configuration error: {e}")

# Validate specific provider
try:
    provider_config = config_manager.get_provider_config("openai")
    print("OpenAI configuration is valid!")
except Exception as e:
    print(f"OpenAI configuration error: {e}")
```

## Best Practices

### Security

1. **Use Environment Variables**: Never hardcode API keys in configuration files
2. **Rotate Keys Regularly**: Implement key rotation policies
3. **Use Least Privilege**: Only grant necessary permissions to API keys
4. **Monitor Usage**: Track API key usage and costs
5. **Secure Storage**: Use secure secret management systems

### Performance

1. **Optimize Model Selection**: Choose appropriate models for each task
2. **Use Caching**: Enable response caching where appropriate
3. **Implement Rate Limiting**: Prevent API quota exhaustion
4. **Monitor Costs**: Set up cost alerts and budgets
5. **Use Fallbacks**: Implement fallback providers for reliability

### Reliability

1. **Test Configurations**: Validate configurations before deployment
2. **Use Circuit Breakers**: Implement circuit breakers for failing providers
3. **Monitor Health**: Set up health checks for all providers
4. **Implement Retries**: Use exponential backoff for retries
5. **Plan for Failures**: Design for provider outages

### Cost Optimization

1. **Use Cost-Effective Models**: Choose models based on task requirements
2. **Implement Cost Tracking**: Monitor costs by provider, model, and agent
3. **Set Budgets**: Establish monthly budgets and alerts
4. **Optimize Token Usage**: Minimize token consumption where possible
5. **Use Local Models**: Consider Ollama for development and testing

## Troubleshooting

### Common Issues

1. **Invalid API Keys**: Verify API keys are correct and have proper permissions
2. **Rate Limiting**: Check rate limits and implement backoff strategies
3. **Model Not Found**: Ensure model names match provider specifications
4. **Configuration Errors**: Validate configuration files using CLI tools
5. **Provider Outages**: Implement fallback providers and circuit breakers

### Debug Mode

Enable debug logging for detailed troubleshooting:

```yaml
# In your configuration
logging:
  level: "DEBUG"
  format: "json"
  file_path: "/var/log/llm-config.log"
```

```bash
# Set environment variable
export LLM_LOG_LEVEL="DEBUG"
```

This comprehensive configuration system provides the foundation for robust, cost-effective, and reliable multi-provider LLM operations in the Gemini SRE Agent.
