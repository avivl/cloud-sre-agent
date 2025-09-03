# Configuration System Migration Guide

This guide helps you migrate from the legacy configuration system to the new enhanced configuration management system introduced in the Gemini SRE Agent.

## Overview

The new configuration system provides:

- **Type-safe configuration** with Pydantic models
- **Environment variable integration** with `pydantic-settings`
- **Multiple format support** (YAML, TOML, JSON)
- **Enhanced validation** with detailed error messages
- **Hot reloading** capabilities
- **CLI tools** for validation, migration, and management
- **Comprehensive monitoring** and audit logging

## Migration Steps

### 1. Backup Your Current Configuration

Before starting the migration, backup your existing configuration:

```bash
cp config/config.yaml config/config.yaml.backup
```

### 2. Install New Dependencies

The new configuration system requires additional dependencies:

```bash
uv sync
```

This will install `pydantic-settings` and `click` for the enhanced configuration system.

### 3. Update Configuration Structure

The new configuration system uses a different structure. Here's how to migrate:

#### Legacy Structure (Old)

```yaml
gemini_cloud_log_monitor:
  default_model_selection:
    triage_model: "gemini-flash"
    analysis_model: "gemini-pro"
    classification_model: "gemini-flash-lite"

  default_github_config:
    repository: "owner/repo"
    base_branch: "main"

  logging:
    log_level: "INFO"
    json_format: false
    log_file: null

  services:
    - service_name: "billing-service"
      project_id: "your-gcp-project"
      location: "us-central1"
      subscription_id: "billing-logs-subscription"
```

#### New Structure (Enhanced)

```yaml
schema_version: "1.0.0"
environment: "development"
debug: false
log_level: "INFO"
app_name: "Gemini SRE Agent"
app_version: "0.1.0"

services:
  - name: "billing-service"
    project_id: "your-gcp-project"
    location: "us-central1"
    subscription_id: "billing-logs-subscription"
    github:
      repository: "owner/repo"
      base_branch: "main"
    model_selection:
      triage_model: "gemini-flash"
      analysis_model: "gemini-pro"
      classification_model: "gemini-flash-lite"

ml:
  models:
    triage:
      name: "gemini-flash"
      max_tokens: 8192
      temperature: 0.1
      cost_per_1k_tokens: 0.000075
      type: "FLASH"
    analysis:
      name: "gemini-pro"
      max_tokens: 32768
      temperature: 0.3
      cost_per_1k_tokens: 0.0005
      type: "PRO"
    classification:
      name: "gemini-flash-lite"
      max_tokens: 4096
      temperature: 0.1
      cost_per_1k_tokens: 0.0000375
      type: "FLASH_LITE"

performance:
  max_concurrent_requests: 10
  request_timeout_seconds: 30
  retry_attempts: 3
  cache_ttl_seconds: 3600

security:
  enable_pii_sanitization: true
  enable_audit_logging: true
  max_log_size_mb: 10

monitoring:
  enable_metrics: true
  metrics_retention_days: 30
  alert_thresholds:
    error_rate_percent: 5.0
    response_time_ms: 5000

github:
  repository: "owner/repo"
  base_branch: "main"
  auto_merge: false
  require_reviews: 1

logging:
  level: "INFO"
  format: "json"
  file_path: null
  max_file_size_mb: 100
  backup_count: 5
```

### 4. Use the Migration Tool

The new system includes a CLI tool to help with migration:

```bash
# Validate your new configuration
python -m gemini_sre_agent.config.cli_tools validate config/config.yaml

# Generate a template for the new structure
python -m gemini_sre_agent.config.cli_tools generate_template --output config/config_new.yaml

# Migrate from old format (if you have the old config)
python -m gemini_sre_agent.config.cli_tools migrate --input config/config.yaml.backup --output config/config.yaml
```

### 5. Environment Variable Integration

The new system supports environment variables for sensitive configuration:

```bash
# Set environment variables
export GEMINI_API_KEY="your-gemini-api-key"
export GITHUB_TOKEN="your-github-token"
export GCP_SERVICE_ACCOUNT_KEY="path/to/service-account.json"

# Or use a .env file
echo "GEMINI_API_KEY=your-gemini-api-key" > .env
echo "GITHUB_TOKEN=your-github-token" >> .env
echo "GCP_SERVICE_ACCOUNT_KEY=path/to/service-account.json" >> .env
```

### 6. Update Your Code

If you have custom code that uses the old configuration system, update it to use the new system:

#### Old Usage

```python
from gemini_sre_agent.config import load_config

config = load_config()
services = config.gemini_cloud_log_monitor.services
```

#### New Usage

```python
from gemini_sre_agent.config import ConfigManager

# Initialize the configuration manager
config_manager = ConfigManager()

# Load configuration
config = config_manager.reload_config()

# Access configuration
services = config.services
ml_config = config.ml
```

### 7. Validate Your Migration

After migration, validate your configuration:

```bash
# Run the validation tool
python -m gemini_sre_agent.config.cli_tools validate config/config.yaml

# Run tests to ensure everything works
uv run pytest tests/test_config_system.py

# Test the example usage
python examples/config_usage_example.py
```

## Key Changes

### Configuration Structure Changes

1. **Schema Versioning**: All configurations now include a `schema_version` field
2. **Environment Support**: Added `environment` field for environment-specific settings
3. **Flattened Structure**: Services are now at the top level instead of nested under `gemini_cloud_log_monitor`
4. **Enhanced ML Configuration**: ML settings are now consolidated under the `ml` section
5. **Performance Settings**: Added dedicated `performance` section for optimization settings
6. **Security Settings**: Added `security` section for security-related configuration
7. **Monitoring Settings**: Added `monitoring` section for observability configuration

### New Features

1. **Type Safety**: All configuration is now validated using Pydantic models
2. **Environment Variables**: Support for loading configuration from environment variables
3. **Hot Reloading**: Configuration can be reloaded without restarting the application
4. **CLI Tools**: Command-line tools for validation, migration, and management
5. **Comprehensive Validation**: Detailed error messages for configuration issues
6. **Audit Logging**: Track configuration changes and validation events

### Breaking Changes

1. **Configuration File Structure**: The YAML structure has changed significantly
2. **Import Paths**: Configuration loading functions have moved to `ConfigManager`
3. **Field Names**: Some field names have changed (e.g., `log_level` instead of `logging.log_level`)
4. **Required Fields**: Some fields that were optional are now required

## Troubleshooting

### Common Migration Issues

1. **Schema Version Mismatch**: Ensure you're using `schema_version: "1.0.0"`
2. **Missing Required Fields**: Check that all required fields are present
3. **Invalid Field Types**: Ensure field types match the expected types (e.g., `max_tokens` should be an integer)
4. **Environment Variable Issues**: Verify environment variables are set correctly

### Getting Help

If you encounter issues during migration:

1. **Check the logs**: The new system provides detailed error messages
2. **Use the CLI tools**: Run `python -m gemini_sre_agent.config.cli_tools validate` to check your configuration
3. **Review the examples**: Check `examples/config_example.yaml` and `examples/config_usage_example.py`
4. **Run tests**: Execute the test suite to verify your setup

## Rollback Plan

If you need to rollback to the old configuration system:

1. **Restore backup**: `cp config/config.yaml.backup config/config.yaml`
2. **Revert dependencies**: Remove `pydantic-settings` and `click` from `pyproject.toml`
3. **Update imports**: Revert any code changes to use the old configuration system

## Next Steps

After successful migration:

1. **Explore CLI tools**: Try the various CLI commands for configuration management
2. **Set up monitoring**: Configure the monitoring and metrics collection
3. **Customize settings**: Adjust performance, security, and monitoring settings for your environment
4. **Test thoroughly**: Run comprehensive tests to ensure everything works as expected

For more information, refer to:

- [Configuration Guide](CONFIGURATION.md) - Updated for the new system
- [Development Guide](DEVELOPMENT.md) - Information on using the new configuration system
- [Examples](../examples/) - Working examples of the new configuration system
