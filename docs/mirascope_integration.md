# Mirascope Prompt Management Integration

This document describes the comprehensive Mirascope integration for advanced prompt management in the Gemini SRE Agent system.

## Overview

The Mirascope integration provides enterprise-grade prompt management capabilities including:

- **Version Control**: Track and manage multiple versions of prompts
- **Testing Framework**: Comprehensive testing and validation of prompts
- **Performance Analytics**: Detailed metrics and performance tracking
- **Environment Management**: Deploy different prompt versions across environments
- **Team Collaboration**: Review and approval workflows
- **Optimization**: AI-powered prompt optimization
- **Structured Output**: Integration with Pydantic response models

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Mirascope Integration                    │
├─────────────────────────────────────────────────────────────┤
│  PromptManager  │  PromptEnvironment  │  CollaborationMgr  │
│  - Versioning   │  - Environment      │  - Reviews         │
│  - Testing      │  - Deployment       │  - Approvals       │
│  - Metrics      │  - Fallback         │  - Workflow        │
├─────────────────────────────────────────────────────────────┤
│  PromptOptimizer  │  LLMPromptService  │  IntegratedLLM    │
│  - AI Optimization│  - Execution       │  - Unified API    │
│  - A/B Testing   │  - Metrics          │  - Environment    │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. PromptManager

The central component for managing prompts with full version control.

```python
from gemini_sre_agent.llm.mirascope_integration import PromptManager

# Initialize prompt manager
manager = PromptManager(storage_path="./prompts")

# Create a new prompt
prompt_id = manager.create_prompt(
    name="SRE Analysis",
    template="Analyze this log: {{log_data}}",
    description="Analyzes SRE logs for issues"
)

# Create a new version
version = manager.create_version(
    prompt_id,
    "Analyze this log for errors: {{log_data}}"
)

# Get a prompt (returns Mirascope Prompt object)
prompt = manager.get_prompt(prompt_id, version)
```

### 2. PromptEnvironment

Environment-specific prompt deployment and management.

```python
from gemini_sre_agent.llm.mirascope_integration import PromptEnvironment

# Create environments
prod_env = PromptEnvironment("production", manager)
dev_env = PromptEnvironment("development", manager)

# Deploy specific versions to environments
prod_env.deploy_prompt(prompt_id, "1.0.0")  # Stable version
dev_env.deploy_prompt(prompt_id, "1.1.0")  # Latest version

# Get environment-specific prompts
prod_prompt = prod_env.get_prompt(prompt_id)
dev_prompt = dev_env.get_prompt(prompt_id)
```

### 3. LLMPromptService

Service for executing managed prompts with full tracking.

```python
from gemini_sre_agent.llm.prompt_service import LLMPromptService
from gemini_sre_agent.agents.agent_models import TriageResult

# Initialize service
prompt_service = LLMPromptService(llm_service, manager)

# Execute prompt with structured output
result = await prompt_service.execute_prompt(
    prompt_id="sre_analysis",
    inputs={"log_data": "Error: Connection timeout"},
    response_model=TriageResult
)

# Execute prompt with text output
text_result = await prompt_service.execute_prompt_text(
    prompt_id="sre_analysis",
    inputs={"log_data": "Error: Connection timeout"}
)
```

### 4. PromptCollaborationManager

Team collaboration and review workflows.

```python
from gemini_sre_agent.llm.mirascope_integration import PromptCollaborationManager

# Initialize collaboration manager
collab_manager = PromptCollaborationManager(manager)

# Create a review
review_id = collab_manager.create_review(
    prompt_id="sre_analysis",
    version="1.1.0",
    reviewer="senior@company.com",
    comments="This looks good but needs more context"
)

# Approve or reject reviews
collab_manager.approve_review(review_id)
# or
collab_manager.reject_review(review_id, "Needs more examples")
```

### 5. PromptOptimizer

AI-powered prompt optimization.

```python
from gemini_sre_agent.llm.mirascope_integration import PromptOptimizer

# Initialize optimizer
optimizer = PromptOptimizer(manager, llm_service)

# Optimize prompt based on goals and test cases
test_cases = [
    {"inputs": {"log_data": "Error: timeout"}, "expected": "timeout issue"},
    {"inputs": {"log_data": "Warning: memory"}, "expected": "memory warning"}
]

new_version = await optimizer.optimize_prompt(
    prompt_id="sre_analysis",
    optimization_goals=["clarity", "accuracy", "conciseness"],
    test_cases=test_cases
)
```

## Usage Examples

### Basic Prompt Management

```python
# 1. Create and manage prompts
manager = PromptManager()

# Create initial prompt
prompt_id = manager.create_prompt(
    name="Log Analysis",
    template="Analyze this log entry: {{log_entry}}",
    description="Analyzes log entries for issues"
)

# Create improved version
manager.create_version(
    prompt_id,
    "Analyze this log entry for errors and warnings: {{log_entry}}"
)

# Test the prompt
test_cases = [
    {"inputs": {"log_entry": "ERROR: Database connection failed"}, "expected": "error"},
    {"inputs": {"log_entry": "INFO: User logged in"}, "expected": "info"}
]

results = manager.test_prompt(prompt_id, test_cases)
print(f"Test success rate: {results['success_rate']:.2%}")
```

### Environment-Specific Deployment

```python
# 2. Environment management
prod_env = PromptEnvironment("production", manager)
staging_env = PromptEnvironment("staging", manager)

# Deploy stable version to production
prod_env.deploy_prompt(prompt_id, "1.0.0")

# Deploy latest version to staging for testing
staging_env.deploy_prompt(prompt_id, "1.1.0")

# Use environment-specific prompts
prod_prompt = prod_env.get_prompt(prompt_id)
staging_prompt = staging_env.get_prompt(prompt_id)
```

### Structured Output Integration

```python
# 3. Structured output with Pydantic models
from gemini_sre_agent.agents.agent_models import TriageResult

prompt_service = LLMPromptService(llm_service, manager)

# Execute with structured output
result = await prompt_service.execute_prompt(
    prompt_id="log_analysis",
    inputs={"log_entry": "ERROR: Database timeout after 30s"},
    response_model=TriageResult
)

print(f"Issue type: {result.issue_type}")
print(f"Severity: {result.severity}")
print(f"Confidence: {result.confidence}")
```

### Performance Monitoring

```python
# 4. Performance monitoring and metrics
# Metrics are automatically recorded when executing prompts
result = await prompt_service.execute_prompt(
    prompt_id="log_analysis",
    inputs={"log_entry": "WARNING: High memory usage"},
    response_model=TriageResult,
    record_metrics=True
)

# View metrics for a prompt version
prompt_data = manager.prompts[prompt_id]
version_data = prompt_data.versions[prompt_data.current_version]
print(f"Average duration: {version_data.metrics.get('duration_seconds', 0):.2f}s")
print(f"Success rate: {version_data.metrics.get('success', 0):.2%}")
```

### Team Collaboration

```python
# 5. Team collaboration workflow
collab_manager = PromptCollaborationManager(manager)

# Create a review for a new version
review_id = collab_manager.create_review(
    prompt_id="log_analysis",
    version="1.2.0",
    reviewer="team-lead@company.com",
    comments="This version looks good but could be more specific about error types"
)

# Approve after review
collab_manager.approve_review(review_id)

# Deploy approved version to production
prod_env.deploy_prompt(prompt_id, "1.2.0")
```

## Advanced Features

### A/B Testing

```python
# A/B test different prompt versions
def run_ab_test(prompt_id, version_a, version_b, test_cases):
    # Test version A
    results_a = manager.test_prompt(prompt_id, test_cases, version_a)

    # Test version B
    results_b = manager.test_prompt(prompt_id, test_cases, version_b)

    # Compare results
    if results_a['success_rate'] > results_b['success_rate']:
        return version_a
    else:
        return version_b

# Run A/B test
winner = run_ab_test("log_analysis", "1.0.0", "1.1.0", test_cases)
print(f"Winner: {winner}")
```

### Prompt Analytics

```python
# Analyze prompt performance over time
def analyze_prompt_performance(prompt_id):
    prompt_data = manager.prompts[prompt_id]

    for version, version_data in prompt_data.versions.items():
        print(f"\nVersion {version}:")
        print(f"  Tests: {len(version_data.tests)}")
        print(f"  Metrics: {version_data.metrics}")

        # Analyze metrics history
        if version_data.metrics_history:
            durations = [m['data'].get('duration_seconds', 0) for m in version_data.metrics_history]
            avg_duration = sum(durations) / len(durations)
            print(f"  Average duration: {avg_duration:.2f}s")

analyze_prompt_performance("log_analysis")
```

### Custom Prompt Types

```python
# Create custom prompt types
class CustomPromptType:
    def __init__(self, template):
        self.template = template

    def format(self, **kwargs):
        return self.template.format(**kwargs)

# Register custom prompt type
manager.create_prompt(
    name="Custom Analysis",
    template="Custom analysis: {{data}}",
    prompt_type="custom"
)
```

## Configuration

### Storage Configuration

```python
# Configure storage location
manager = PromptManager(storage_path="/path/to/prompts")

# The storage directory will contain:
# - prompts.json: Main prompt data
# - versions/: Individual version files
# - metrics/: Performance metrics
# - tests/: Test results
```

### Environment Variables

```bash
# Optional environment variables
export MIRASCOPE_STORAGE_PATH="/path/to/prompts"
export MIRASCOPE_ENVIRONMENT="production"
export MIRASCOPE_ENABLE_ANALYTICS="true"
```

## Integration with Existing LLM Service

The Mirascope integration seamlessly integrates with the existing LLM service:

```python
from gemini_sre_agent.llm.prompt_service import MirascopeIntegratedLLMService

# Create integrated service
integrated_service = MirascopeIntegratedLLMService(
    llm_service=existing_llm_service,
    prompt_manager=prompt_manager
)

# Use the integrated service
result = await integrated_service.execute_managed_prompt(
    prompt_id="sre_analysis",
    inputs={"log_data": "Error: Connection failed"},
    response_model=TriageResult
)
```

## Best Practices

### 1. Version Management

- Use semantic versioning (major.minor.patch)
- Always test new versions before deployment
- Keep detailed changelogs for each version

### 2. Testing

- Create comprehensive test cases for each prompt
- Test with realistic data and edge cases
- Monitor test success rates over time

### 3. Performance Monitoring

- Record metrics for all prompt executions
- Set up alerts for performance degradation
- Regularly review and optimize slow prompts

### 4. Team Collaboration

- Use reviews for all production deployments
- Document changes and reasoning
- Maintain clear approval workflows

### 5. Environment Management

- Use separate environments for development, staging, and production
- Deploy stable versions to production
- Test new versions in staging first

## Troubleshooting

### Common Issues

1. **Prompt not found**: Ensure the prompt ID exists and is correctly spelled
2. **Version not found**: Check that the version exists for the prompt
3. **Test failures**: Review test cases and expected outputs
4. **Performance issues**: Check metrics and consider optimization

### Debug Mode

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Debug prompt execution
result = await prompt_service.execute_prompt(
    prompt_id="debug_prompt",
    inputs={"test": "data"},
    response_model=TestModel
)
```

## API Reference

### PromptManager

- `create_prompt(name, template, description=None, prompt_type="chat")` → str
- `get_prompt(prompt_id, version=None)` → Prompt
- `create_version(prompt_id, template, version=None)` → str
- `test_prompt(prompt_id, test_cases, version=None)` → Dict
- `record_metrics(prompt_id, metrics, version=None)` → None
- `list_prompts()` → List[Dict]
- `get_prompt_versions(prompt_id)` → List[str]

### PromptEnvironment

- `deploy_prompt(prompt_id, version)` → None
- `get_prompt(prompt_id)` → Prompt

### LLMPromptService

- `execute_prompt(prompt_id, inputs, response_model, record_metrics=True)` → BaseModel
- `execute_prompt_text(prompt_id, inputs, record_metrics=True)` → str

### PromptCollaborationManager

- `create_review(prompt_id, version, reviewer, comments)` → str
- `approve_review(review_id)` → None
- `reject_review(review_id, reason)` → None

### PromptOptimizer

- `optimize_prompt(prompt_id, optimization_goals, test_cases)` → str

## Conclusion

The Mirascope integration provides a comprehensive solution for prompt management in the Gemini SRE Agent system. It enables version control, testing, optimization, and team collaboration while maintaining seamless integration with existing LLM services.

For more information, see the unit tests in `tests/llm/test_mirascope_integration.py` and the implementation in `gemini_sre_agent/llm/mirascope_integration.py`.
