# Migration Guide: Enhanced Multi-Provider LLM System

## Overview

This guide helps you migrate from the original Gemini-only SRE Agent to the enhanced multi-provider LLM system while maintaining full backward compatibility.

## Migration Strategies

### 1. Zero-Code Migration (Recommended for Quick Start)

Use legacy adapters to migrate without changing any existing code:

```python
# Before (Original)
from gemini_sre_agent.triage_agent import TriageAgent
from gemini_sre_agent.analysis_agent import AnalysisAgent
from gemini_sre_agent.remediation_agent import RemediationAgent

triage_agent = TriageAgent(project_id, location, model)
analysis_agent = AnalysisAgent(project_id, location, model)
remediation_agent = RemediationAgent(github_token, repo_name)

# After (Enhanced with Legacy Adapters)
from gemini_sre_agent.agents.legacy_adapter import (
    create_enhanced_triage_agent,
    create_enhanced_analysis_agent,
    create_enhanced_remediation_agent,
)
from gemini_sre_agent.llm.config_manager import ConfigManager

# Load enhanced configuration
config_manager = ConfigManager("config/llm_config.yaml")
llm_config = config_manager.get_config()

# Drop-in replacements
triage_agent = create_enhanced_triage_agent(project_id, location, model, llm_config)
analysis_agent = create_enhanced_analysis_agent(project_id, location, model, llm_config)
remediation_agent = create_enhanced_remediation_agent(github_token, repo_name, llm_config)

# All existing code works unchanged!
```

### 2. Gradual Migration (Recommended for Production)

Migrate one agent at a time to enhanced versions:

```python
# Step 1: Migrate Triage Agent
from gemini_sre_agent.agents.enhanced_triage_agent import EnhancedTriageAgent

triage_agent = EnhancedTriageAgent(
    llm_config=llm_config,
    primary_model="llama3.2:3b",
    fallback_model="llama3.2:1b",
    optimization_goal=OptimizationGoal.COST_EFFECTIVE,
    max_cost=0.01,
    min_quality=0.7,
)

# Step 2: Migrate Analysis Agent
from gemini_sre_agent.agents.enhanced_analysis_agent import EnhancedAnalysisAgent

analysis_agent = EnhancedAnalysisAgent(
    llm_config=llm_config,
    optimization_goal=OptimizationGoal.QUALITY,
    max_cost=0.02,
    min_quality=0.8,
)

# Step 3: Migrate Remediation Agent
from gemini_sre_agent.agents.enhanced_remediation_agent import EnhancedRemediationAgent

remediation_agent = EnhancedRemediationAgent(
    llm_config=llm_config,
    optimization_goal=OptimizationGoal.HYBRID,
    max_cost=0.03,
    min_quality=0.9,
)
```

### 3. Full Migration (Recommended for New Projects)

Use the complete enhanced system with all features:

```python
from gemini_sre_agent.agents.enhanced_specialized import (
    EnhancedTriageAgent,
    EnhancedAnalysisAgent,
    EnhancedRemediationAgentV2,
)

# Create agents with full enhanced capabilities
agents = {
    "triage": EnhancedTriageAgent(
        llm_config=llm_config,
        primary_model="llama3.2:3b",
        fallback_model="llama3.2:1b",
        optimization_goal=OptimizationGoal.COST_EFFECTIVE,
        collect_stats=True,
    ),
    "analysis": EnhancedAnalysisAgent(
        llm_config=llm_config,
        optimization_goal=OptimizationGoal.QUALITY,
        collect_stats=True,
    ),
    "remediation": EnhancedRemediationAgentV2(
        llm_config=llm_config,
        optimization_goal=OptimizationGoal.HYBRID,
        collect_stats=True,
    ),
}
```

## Configuration Setup

### 1. Create LLM Configuration

Create `config/llm_config.yaml`:

```yaml
providers:
  ollama:
    provider_type: "ollama"
    base_url: "http://localhost:11434"
    models:
      - "llama3.2:3b"
      - "llama3.2:1b"
    default_model: "llama3.2:3b"
    
  openai:
    provider_type: "openai"
    api_key: "${OPENAI_API_KEY}"
    models:
      - "gpt-4o-mini"
      - "gpt-3.5-turbo"
    default_model: "gpt-4o-mini"

strategy:
  default_optimization_goal: "hybrid"
  cost_thresholds:
    low: 0.001
    medium: 0.01
    high: 0.1
  quality_thresholds:
    minimum: 0.7
    good: 0.8
    excellent: 0.9
```

### 2. Environment Variables

```bash
# Required for enhanced features
LLM_CONFIG_PATH=config/llm_config.yaml

# Optional provider API keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key

# Existing variables (still supported)
GITHUB_TOKEN=your_github_token
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
```

## Testing Your Migration

### 1. Run the Demo

```bash
python examples/enhanced_system_demo.py
```

### 2. Test Legacy Compatibility

```bash
python examples/legacy_compatibility_test.py
```

### 3. Validate Configuration

```bash
python -c "
from gemini_sre_agent.llm.config_manager import ConfigManager
config = ConfigManager('config/llm_config.yaml').get_config()
print(f'Loaded {len(config.providers)} providers')
"
```

## Common Issues and Solutions

### Issue 1: Configuration Not Found

**Error**: `FileNotFoundError: config/llm_config.yaml`

**Solution**: 
```bash
# Copy example configuration
cp examples/llm_configs/multi_provider_config.yaml config/llm_config.yaml
# Edit with your settings
```

### Issue 2: Provider Connection Failed

**Error**: `ConnectionError: Could not connect to provider`

**Solution**:
```bash
# For Ollama
ollama serve
ollama pull llama3.2:3b

# For OpenAI
export OPENAI_API_KEY=your_key
```

### Issue 3: Legacy Interface Changes

**Error**: `TypeError: analyze_issue() missing 1 required positional argument`

**Solution**: Use legacy adapters for zero-code migration:
```python
from gemini_sre_agent.agents.legacy_adapter import create_enhanced_analysis_agent
```

## Performance Optimization

### 1. Model Selection

- **Triage**: Use fast, cost-effective models (llama3.2:1b, gpt-4o-mini)
- **Analysis**: Use balanced models (llama3.2:3b, gpt-4o)
- **Remediation**: Use high-quality models (gpt-4, claude-3-sonnet)

### 2. Cost Management

```python
# Set cost limits per agent
triage_agent = EnhancedTriageAgent(
    max_cost=0.005,  # $0.005 per 1k tokens
    optimization_goal=OptimizationGoal.COST_EFFECTIVE,
)
```

### 3. Quality Assurance

```python
# Set quality thresholds
analysis_agent = EnhancedAnalysisAgent(
    min_quality=0.8,  # Minimum 80% quality score
    optimization_goal=OptimizationGoal.QUALITY,
)
```

## Monitoring and Metrics

### 1. Enable Metrics Collection

```python
from gemini_sre_agent.llm.monitoring.llm_metrics import get_llm_metrics_collector

metrics_collector = get_llm_metrics_collector()
summary = metrics_collector.get_metrics_summary()
print(f"Total requests: {summary['total_requests']}")
print(f"Total cost: ${summary['total_cost']:.4f}")
```

### 2. Health Monitoring

```python
# Check provider health
for provider_name, provider in providers.items():
    health = await provider.health_check()
    print(f"{provider_name}: {'✓' if health.is_healthy else '✗'}")
```

## Next Steps

1. **Start with Zero-Code Migration**: Use legacy adapters for immediate benefits
2. **Gradually Enhance**: Move to enhanced agents one by one
3. **Optimize Configuration**: Tune models and costs for your use case
4. **Monitor Performance**: Use built-in metrics and monitoring
5. **Explore Advanced Features**: Try model mixing, A/B testing, and prompt optimization

## Support

- **Documentation**: See `docs/` directory for detailed guides
- **Examples**: Check `examples/` for working code samples
- **Issues**: Report problems via GitHub issues
- **Community**: Join discussions in GitHub Discussions