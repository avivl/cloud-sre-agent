# gemini_sre_agent/config/loader.py

"""
Configuration loader with support for multiple sources and complete implementations.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar, Union

import yaml

from .base import BaseConfig
from .errors import ConfigFileError

T = TypeVar("T", bound=BaseConfig)


class ConfigLoader:
    """Configuration loader with support for multiple sources."""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._cache: Dict[str, Any] = {}

    def load_config(
        self,
        config_class: Type[T],
        environment: Optional[str] = None,
        config_file: Optional[str] = None,
    ) -> T:
        """
        Load configuration with environment-specific overrides.

        Args:
            config_class: Pydantic configuration class
            environment: Environment name (dev/staging/prod)
            config_file: Specific config file to load

        Returns:
            Loaded configuration instance
        """
        try:
            # Determine environment
            env = environment or os.getenv("ENVIRONMENT", "development")

            # Load base configuration
            base_config = self._load_yaml_config(config_file or "config.yaml")

            # Load environment-specific overrides
            env_config = self._load_yaml_config(f"config.{env}.yaml")

            # Merge configurations
            merged_config = self._merge_configs(base_config, env_config)

            # Load from environment variables
            env_vars = self._extract_env_vars(config_class)

            # Final merge
            final_config = self._merge_configs(merged_config, env_vars)

            # Validate and return
            return config_class(**final_config)

        except yaml.YAMLError as e:
            raise ConfigFileError(
                f"Invalid YAML configuration: {e}", config_file, e
            ) from e
        except Exception as e:
            raise ConfigFileError(
                f"Configuration loading failed: {e}", config_file, e
            ) from e

    def _load_yaml_config(self, filename: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config_path = self.config_dir / filename
        if not config_path.exists():
            return {}

        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise ConfigFileError(
                f"Failed to load YAML file {filename}: {e}", str(config_path), e
            ) from e

    def _extract_env_vars(self, config_class: Type[T]) -> Dict[str, Any]:
        """Extract configuration from environment variables."""
        env_vars = {}

        # Get all field names from the config class
        if hasattr(config_class, "model_fields"):
            for field_name, field_info in config_class.model_fields.items():
                # Convert field name to environment variable name
                env_var_name = f"{config_class.__name__.upper()}_{field_name.upper()}"
                env_value = os.getenv(env_var_name)

                if env_value is not None:
                    # Handle nested configuration with double underscore
                    nested_env_vars = self._extract_nested_env_vars(
                        field_name, config_class
                    )
                    if nested_env_vars:
                        env_vars[field_name] = nested_env_vars
                    else:
                        # Convert string values to appropriate types
                        env_vars[field_name] = self._convert_env_value(
                            env_value, field_info
                        )

        return env_vars

    def _extract_nested_env_vars(
        self, prefix: str, config_class: Type[T]
    ) -> Dict[str, Any]:
        """Extract nested environment variables for complex configurations."""
        nested_vars = {}
        prefix_upper = f"{config_class.__name__.upper()}_{prefix.upper()}"

        # Look for environment variables with the prefix
        for env_name, env_value in os.environ.items():
            if env_name.startswith(prefix_upper + "__"):
                # Extract the nested path
                nested_path = env_name[len(prefix_upper) + 2 :].lower()
                nested_keys = nested_path.split("__")

                # Build nested dictionary
                current = nested_vars
                for key in nested_keys[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]

                # Set the final value
                current[nested_keys[-1]] = self._convert_string_value(env_value)

        return nested_vars

    def _convert_env_value(self, value: str, field_info) -> Any:
        """Convert environment variable string to appropriate type."""
        # Handle different field types
        if hasattr(field_info, "annotation"):
            field_type = field_info.annotation

            # Handle Optional types
            if hasattr(field_type, "__origin__") and field_type.__origin__ is Union:
                # Extract the non-None type from Optional
                non_none_types = [t for t in field_type.__args__ if t is not type(None)]
                if non_none_types:
                    field_type = non_none_types[0]

            if field_type is not None:
                return self._convert_string_value(value, field_type)
            else:
                return self._convert_string_value(value)

        return self._convert_string_value(value)

    def _convert_string_value(
        self, value: str, target_type: Optional[Type] = None
    ) -> Any:
        """Convert string value to target type."""
        if target_type is None:
            # Try to infer type from value
            if value.lower() in ("true", "false"):
                return value.lower() == "true"
            elif value.isdigit():
                return int(value)
            elif value.replace(".", "").isdigit():
                return float(value)
            elif value.lower() == "null":
                return None
            else:
                return value

        # Convert to specific type
        if target_type is bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif target_type is int:
            return int(value)
        elif target_type is float:
            return float(value)
        elif target_type is str:
            return value
        else:
            return value

    def _merge_configs(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deep merge configuration dictionaries."""
        if not override:
            return base.copy()

        if not base:
            return override.copy()

        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Recursively merge nested dictionaries
                result[key] = self._merge_configs(result[key], value)
            else:
                # Override the value
                result[key] = value

        return result
