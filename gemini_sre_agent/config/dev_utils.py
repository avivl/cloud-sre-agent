# gemini_sre_agent/config/dev_utils.py

"""
Development utilities for configuration management.
"""

from datetime import datetime
from typing import Any, Dict, List, Type, TypeVar

from .base import BaseConfig

T = TypeVar("T", bound=BaseConfig)


class ConfigDevUtils:
    """Development utilities for configuration."""

    @staticmethod
    def generate_config_template(
        config_class: Type, environment: str = "production"
    ) -> str:
        """Generate configuration template from Pydantic model."""
        template = f"""# Gemini SRE Agent Configuration Template
# Generated for environment: {environment}
# Generated on: {datetime.now().isoformat()}
# Schema version: 1.0.0

# Base application configuration
app:
  name: "gemini-sre-agent"
  version: "0.1.0"
  environment: "{environment}"
  debug: false

# Schema metadata
schema_version: "1.0.0"
last_validated: null
validation_checksum: null

# Logging configuration
logging:
  level: "INFO"
  format: "json"
  file: null
  max_size_mb: 100
  backup_count: 5

# ML Configuration
ml:
  models:
    triage:
      name: "gemini-1.5-flash-001"
      max_tokens: 4096
      temperature: 0.3
      timeout_seconds: 15
      retry_attempts: 3
      cost_per_1k_tokens: 0.0
    analysis:
      name: "gemini-1.5-pro-001"
      max_tokens: 8192
      temperature: 0.7
      timeout_seconds: 30
      retry_attempts: 3
      cost_per_1k_tokens: 0.0
    classification:
      name: "gemini-2.5-flash-lite"
      max_tokens: 2048
      temperature: 0.5
      timeout_seconds: 10
      retry_attempts: 3
      cost_per_1k_tokens: 0.0

  code_generation:
    enable_validation: true
    enable_specialized_generators: true
    max_iterations: 3
    quality_threshold: 8.0
    human_review_threshold: 7.0
    enable_learning: true

  adaptive_prompt:
    enable_adaptive_strategy: true
    cache_ttl_seconds: 3600
    max_cache_size: 1000
    enable_fallback: true
    strategy_switch_threshold: 0.7

  cost_tracking:
    daily_budget_usd: 10.0
    monthly_budget_usd: 100.0
    warn_threshold_percent: 80.0
    alert_threshold_percent: 95.0
    enable_daily_reset: true
    enable_monthly_reset: true
    currency: "USD"
    model_costs: {{}}

  rate_limiting:
    max_requests_per_minute: 60
    max_requests_per_hour: 1000
    max_concurrent_requests: 10
    enable_circuit_breaker: true
    circuit_breaker_threshold: 5
    circuit_breaker_timeout_seconds: 60

  performance:
    enable_caching: true
    cache_ttl_seconds: 3600
    max_cache_size_mb: 100
    enable_parallel_processing: true
    max_workers: 4

# Performance settings
performance:
  cache_max_size_mb: 100
  cache_ttl_seconds: 3600
  max_concurrent_requests: 10
  request_timeout_seconds: 30

# Services to monitor
services:
  - name: "example-service"
    project_id: "your-gcp-project"
    location: "us-central1"
    subscription_id: "example-logs-subscription"

# GitHub configuration
github:
  repository: "owner/repo"
  base_branch: "main"
  token: null  # Set via environment variable GITHUB_TOKEN

# Security configuration
security:
  enable_secrets_validation: true
  secrets_rotation_interval_days: 90
  enable_audit_logging: true
  max_failed_attempts: 5
  lockout_duration_minutes: 30

# Monitoring configuration
monitoring:
  enable_metrics: true
  metrics_endpoint: null
  enable_health_checks: true
  health_check_interval_seconds: 60
  enable_alerting: true
  alert_webhook_url: null
"""

        return template

    @staticmethod
    def validate_config_file(file_path: str, config_class: Type[T]) -> bool:
        """Validate configuration file against schema."""
        try:
            from .manager import ConfigManager

            manager = ConfigManager()
            manager.loader.load_config(config_class, config_file=file_path)
            return True
        except Exception:
            return False

    @staticmethod
    def migrate_old_config(old_config: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate old configuration format to new format."""
        new_config = {}

        # Extract base configuration
        if "gemini_cloud_log_monitor" in old_config:
            old_monitor_config = old_config["gemini_cloud_log_monitor"]

            # Migrate app configuration
            new_config["app"] = {
                "name": "gemini-sre-agent",
                "version": "0.1.0",
                "environment": "development",
                "debug": False,
            }

            # Migrate ML configuration
            if "default_model_selection" in old_monitor_config:
                model_selection = old_monitor_config["default_model_selection"]
                new_config["ml"] = {
                    "models": {
                        "triage": {
                            "name": model_selection.get(
                                "triage_model", "gemini-1.5-flash-001"
                            ),
                            "max_tokens": 4096,
                            "temperature": 0.3,
                            "timeout_seconds": 15,
                            "retry_attempts": 3,
                            "cost_per_1k_tokens": 0.0,
                        },
                        "analysis": {
                            "name": model_selection.get(
                                "analysis_model", "gemini-1.5-pro-001"
                            ),
                            "max_tokens": 8192,
                            "temperature": 0.7,
                            "timeout_seconds": 30,
                            "retry_attempts": 3,
                            "cost_per_1k_tokens": 0.0,
                        },
                        "classification": {
                            "name": model_selection.get(
                                "classification_model", "gemini-2.5-flash-lite"
                            ),
                            "max_tokens": 2048,
                            "temperature": 0.5,
                            "timeout_seconds": 10,
                            "retry_attempts": 3,
                            "cost_per_1k_tokens": 0.0,
                        },
                    },
                    "code_generation": {
                        "enable_validation": True,
                        "enable_specialized_generators": True,
                        "max_iterations": 3,
                        "quality_threshold": 8.0,
                        "human_review_threshold": 7.0,
                        "enable_learning": True,
                    },
                }

            # Migrate services
            if "services" in old_monitor_config:
                new_config["services"] = old_monitor_config["services"]

            # Migrate GitHub configuration
            if "default_github_config" in old_monitor_config:
                github_config = old_monitor_config["default_github_config"]
                new_config["github"] = {
                    "repository": github_config.get("repository", "owner/repo"),
                    "base_branch": github_config.get("base_branch", "main"),
                    "token": None,
                }

            # Migrate logging configuration
            if "logging" in old_monitor_config:
                logging_config = old_monitor_config["logging"]
                new_config["logging"] = {
                    "level": logging_config.get("log_level", "INFO"),
                    "format": (
                        "json" if logging_config.get("json_format", False) else "text"
                    ),
                    "file": logging_config.get("log_file"),
                    "max_size_mb": 100,
                    "backup_count": 5,
                }

        # Add schema metadata
        new_config["schema_version"] = "1.0.0"
        new_config["last_validated"] = None
        new_config["validation_checksum"] = None

        return new_config

    @staticmethod
    def export_config_to_env(config: BaseConfig) -> Dict[str, str]:
        """Export configuration as environment variables."""
        env_vars = {}

        def flatten_dict(d: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
            """Flatten nested dictionary for environment variables."""
            result = {}
            for key, value in d.items():
                new_key = f"{prefix}_{key}".upper() if prefix else key.upper()

                if isinstance(value, dict):
                    result.update(flatten_dict(value, new_key))
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            result.update(flatten_dict(item, f"{new_key}_{i}"))
                        else:
                            result[f"{new_key}_{i}"] = str(item)
                else:
                    result[new_key] = str(value)

            return result

        config_dict = config.model_dump()
        env_vars = flatten_dict(config_dict, "GEMINI_SRE_AGENT")

        return env_vars

    @staticmethod
    def diff_configs(
        config1: Dict[str, Any], config2: Dict[str, Any], output_format: str = "yaml"
    ) -> str:
        """Compare two configurations and return differences."""

        def find_differences(
            d1: Dict[str, Any], d2: Dict[str, Any], path: str = ""
        ) -> List[str]:
            """Find differences between two dictionaries."""
            differences = []

            all_keys = set(d1.keys()) | set(d2.keys())

            for key in all_keys:
                current_path = f"{path}.{key}" if path else key

                if key not in d1:
                    differences.append(f"+ {current_path}: {d2[key]} (added)")
                elif key not in d2:
                    differences.append(f"- {current_path}: {d1[key]} (removed)")
                elif isinstance(d1[key], dict) and isinstance(d2[key], dict):
                    differences.extend(find_differences(d1[key], d2[key], current_path))
                elif d1[key] != d2[key]:
                    differences.append(
                        f"~ {current_path}: {d1[key]} → {d2[key]} (changed)"
                    )

            return differences

        differences = find_differences(config1, config2)

        if not differences:
            return "No differences found between configurations."

        result = ["Configuration differences found:"]
        result.extend(differences)

        return "\n".join(result)
