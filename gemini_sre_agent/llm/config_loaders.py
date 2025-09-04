"""
Configuration loaders for multi-LLM provider support.

This module provides specialized loaders for different configuration sources
including environment variables, files, and programmatic sources.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Union

import yaml

logger = logging.getLogger(__name__)


@dataclass
class LoaderResult:
    """Result from a configuration loader."""

    data: Dict[str, Any]
    source: str
    metadata: Dict[str, Any]
    errors: List[str]


class BaseConfigLoader:
    """Base class for configuration loaders."""

    def __init__(self, source: str, priority: int = 0):
        """
        Initialize the loader.

        Args:
            source: Source identifier
            priority: Loader priority (higher = more important)
        """
        self.source = source
        self.priority = priority
        self._validators: List[Callable[[Dict[str, Any]], List[str]]] = []

    def add_validator(self, validator: Callable[[Dict[str, Any]], List[str]]) -> None:
        """Add a validation function."""
        self._validators.append(validator)

    def validate(self, data: Dict[str, Any]) -> List[str]:
        """Validate configuration data."""
        errors = []
        for validator in self._validators:
            try:
                errors.extend(validator(data))
            except Exception as e:
                errors.append(f"Validation error: {e}")
        return errors

    def load(self) -> LoaderResult:
        """Load configuration data."""
        raise NotImplementedError


class EnvironmentConfigLoader(BaseConfigLoader):
    """Loader for environment variable configuration."""

    def __init__(self, prefix: str = "LLM_", priority: int = 2):
        """
        Initialize environment loader.

        Args:
            prefix: Environment variable prefix
            priority: Loader priority
        """
        super().__init__("environment", priority)
        self.prefix = prefix
        self._mappings = {
            "LLM_DEFAULT_PROVIDER": "default_provider",
            "LLM_DEFAULT_MODEL_TYPE": "default_model_type",
            "LLM_ENABLE_FALLBACK": "enable_fallback",
            "LLM_ENABLE_MONITORING": "enable_monitoring",
            "LLM_COST_BUDGET": "cost_config.monthly_budget",
            "LLM_COST_ALERT_THRESHOLD": "cost_config.cost_alerts",
            "LLM_RESILIENCE_MAX_RETRIES": "resilience_config.retry_attempts",
            "LLM_RESILIENCE_TIMEOUT": "resilience_config.timeout",
            "LLM_RESILIENCE_CIRCUIT_BREAKER_ENABLED": "resilience_config.circuit_breaker_enabled",
        }

    def load(self) -> LoaderResult:
        """Load configuration from environment variables."""
        data = {}
        errors = []

        try:
            # Load mapped environment variables
            for env_var, config_key in self._mappings.items():
                value = os.environ.get(env_var)
                if value is not None:
                    self._set_nested_value(data, config_key, value)

            # Load provider-specific environment variables
            provider_data = self._load_provider_env_vars()
            if provider_data:
                data["providers"] = provider_data

            # Load agent-specific environment variables
            agent_data = self._load_agent_env_vars()
            if agent_data:
                data["agents"] = agent_data

            # Validate loaded data
            validation_errors = self.validate(data)
            errors.extend(validation_errors)

            return LoaderResult(
                data=data,
                source=self.source,
                metadata={"prefix": self.prefix, "mappings": len(self._mappings)},
                errors=errors,
            )

        except Exception as e:
            errors.append(f"Failed to load environment configuration: {e}")
            return LoaderResult(
                data={},
                source=self.source,
                metadata={"prefix": self.prefix},
                errors=errors,
            )

    def _set_nested_value(
        self, data: Dict[str, Any], key_path: str, value: Any
    ) -> None:
        """Set a nested value in the data dictionary."""
        keys = key_path.split(".")
        current = data

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Convert string values to appropriate types
        if (
            key_path.endswith("_enabled")
            or key_path.endswith("_fallback")
            or key_path.endswith("_monitoring")
        ):
            current[keys[-1]] = value.lower() in ("true", "1", "yes", "on")
        elif (
            key_path.endswith("_budget")
            or key_path.endswith("_threshold")
            or key_path.endswith("_timeout")
        ):
            try:
                current[keys[-1]] = float(value)
            except ValueError:
                current[keys[-1]] = value
        elif key_path.endswith("_retries") or key_path.endswith("_attempts"):
            try:
                current[keys[-1]] = int(value)
            except ValueError:
                current[keys[-1]] = value
        elif key_path.endswith("_alerts"):
            # Handle comma-separated list
            current[keys[-1]] = [
                float(x.strip()) for x in value.split(",") if x.strip()
            ]
        else:
            current[keys[-1]] = value

    def _load_provider_env_vars(self) -> Dict[str, Any]:
        """Load provider-specific environment variables."""
        providers = {}

        for provider in [
            "openai",
            "anthropic",
            "xai",
            "ollama",
            "bedrock",
            "gemini",
            "claude",
            "grok",
        ]:
            provider_key = f"{provider.upper()}_API_KEY"
            api_key = os.environ.get(provider_key)

            if api_key:
                providers[provider] = {
                    "provider": provider,
                    "api_key": api_key,
                    "models": {},
                }

                # Load provider-specific configuration
                base_url_key = f"{provider.upper()}_BASE_URL"
                base_url = os.environ.get(base_url_key)
                if base_url:
                    providers[provider]["base_url"] = base_url

                timeout_key = f"{provider.upper()}_TIMEOUT"
                timeout = os.environ.get(timeout_key)
                if timeout:
                    try:
                        providers[provider]["timeout"] = int(timeout)
                    except ValueError:
                        pass

                max_retries_key = f"{provider.upper()}_MAX_RETRIES"
                max_retries = os.environ.get(max_retries_key)
                if max_retries:
                    try:
                        providers[provider]["max_retries"] = int(max_retries)
                    except ValueError:
                        pass

        return providers

    def _load_agent_env_vars(self) -> Dict[str, Any]:
        """Load agent-specific environment variables."""
        agents = {}

        # Look for agent-specific environment variables
        for key, value in os.environ.items():
            if key.startswith("LLM_AGENT_") and key.endswith("_PROVIDER"):
                agent_name = key[10:-9].lower()  # Remove 'LLM_AGENT_' and '_PROVIDER'
                agents[agent_name] = {
                    "primary_provider": value,
                    "primary_model_type": "smart",  # Default
                }

                # Look for model type
                model_type_key = f"LLM_AGENT_{agent_name.upper()}_MODEL_TYPE"
                model_type = os.environ.get(model_type_key)
                if model_type:
                    agents[agent_name]["primary_model_type"] = model_type

                # Look for fallback provider
                fallback_key = f"LLM_AGENT_{agent_name.upper()}_FALLBACK_PROVIDER"
                fallback_provider = os.environ.get(fallback_key)
                if fallback_provider:
                    agents[agent_name]["fallback_provider"] = fallback_provider

        return agents


class FileConfigLoader(BaseConfigLoader):
    """Loader for file-based configuration (YAML/JSON)."""

    def __init__(self, file_path: Union[str, Path], priority: int = 1):
        """
        Initialize file loader.

        Args:
            file_path: Path to configuration file
            priority: Loader priority
        """
        super().__init__(f"file:{file_path}", priority)
        self.file_path = Path(file_path)

    def load(self) -> LoaderResult:
        """Load configuration from file."""
        data = {}
        errors = []

        try:
            if not self.file_path.exists():
                errors.append(f"Configuration file not found: {self.file_path}")
                return LoaderResult(
                    data=data,
                    source=self.source,
                    metadata={"path": str(self.file_path)},
                    errors=errors,
                )

            with open(self.file_path, "r") as f:
                if self.file_path.suffix.lower() in [".yaml", ".yml"]:
                    data = yaml.safe_load(f) or {}
                elif self.file_path.suffix.lower() == ".json":
                    data = json.load(f) or {}
                else:
                    errors.append(f"Unsupported file format: {self.file_path.suffix}")
                    return LoaderResult(
                        data=data,
                        source=self.source,
                        metadata={"path": str(self.file_path)},
                        errors=errors,
                    )

            # Validate loaded data
            validation_errors = self.validate(data)
            errors.extend(validation_errors)

            return LoaderResult(
                data=data,
                source=self.source,
                metadata={
                    "path": str(self.file_path),
                    "size": self.file_path.stat().st_size,
                    "format": self.file_path.suffix,
                },
                errors=errors,
            )

        except yaml.YAMLError as e:
            errors.append(f"YAML parsing error: {e}")
        except json.JSONDecodeError as e:
            errors.append(f"JSON parsing error: {e}")
        except Exception as e:
            errors.append(f"Failed to load file configuration: {e}")

        return LoaderResult(
            data=data,
            source=self.source,
            metadata={"path": str(self.file_path)},
            errors=errors,
        )


class ProgrammaticConfigLoader(BaseConfigLoader):
    """Loader for programmatically provided configuration."""

    def __init__(self, config_data: Dict[str, Any], priority: int = 3):
        """
        Initialize programmatic loader.

        Args:
            config_data: Configuration data
            priority: Loader priority
        """
        super().__init__("programmatic", priority)
        self.config_data = config_data

    def load(self) -> LoaderResult:
        """Load programmatic configuration."""
        errors = []

        try:
            # Validate loaded data
            validation_errors = self.validate(self.config_data)
            errors.extend(validation_errors)

            return LoaderResult(
                data=self.config_data.copy(),
                source=self.source,
                metadata={"size": len(str(self.config_data))},
                errors=errors,
            )

        except Exception as e:
            errors.append(f"Failed to load programmatic configuration: {e}")
            return LoaderResult(data={}, source=self.source, metadata={}, errors=errors)


class ConfigLoaderManager:
    """Manager for multiple configuration loaders."""

    def __init__(self):
        """Initialize the loader manager."""
        self.loaders: List[BaseConfigLoader] = []
        self._results: List[LoaderResult] = []

    def add_loader(self, loader: BaseConfigLoader) -> None:
        """Add a configuration loader."""
        self.loaders.append(loader)

    def load_all(self) -> Dict[str, Any]:
        """Load configuration from all loaders and merge results."""
        self._results = []
        merged_data = {}

        # Sort loaders by priority (higher priority first)
        sorted_loaders = sorted(self.loaders, key=lambda x: x.priority, reverse=True)

        for loader in sorted_loaders:
            try:
                result = loader.load()
                self._results.append(result)

                if result.errors:
                    logger.warning(
                        f"Loader {loader.source} had errors: {result.errors}"
                    )

                # Merge data (higher priority overwrites lower priority)
                merged_data = self._merge_config_data(merged_data, result.data)

            except Exception as e:
                logger.error(f"Failed to load from {loader.source}: {e}")
                self._results.append(
                    LoaderResult(
                        data={}, source=loader.source, metadata={}, errors=[str(e)]
                    )
                )

        return merged_data

    def _merge_config_data(
        self, base: Dict[str, Any], updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deep merge configuration data."""
        result = base.copy()

        for key, value in updates.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_config_data(result[key], value)
            else:
                result[key] = value

        return result

    def get_loader_results(self) -> List[LoaderResult]:
        """Get results from all loaders."""
        return self._results.copy()

    def get_all_errors(self) -> List[str]:
        """Get all errors from all loaders."""
        errors = []
        for result in self._results:
            errors.extend(result.errors)
        return errors

    def get_loader_summary(self) -> Dict[str, Any]:
        """Get a summary of loader results."""
        return {
            "total_loaders": len(self.loaders),
            "successful_loads": len([r for r in self._results if not r.errors]),
            "failed_loads": len([r for r in self._results if r.errors]),
            "total_errors": len(self.get_all_errors()),
            "loaders": [
                {
                    "source": result.source,
                    "errors": len(result.errors),
                    "metadata": result.metadata,
                }
                for result in self._results
            ],
        }
