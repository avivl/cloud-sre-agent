"""
Configuration management system for multi-LLM provider support.

This module provides a comprehensive configuration system that supports
multiple LLM providers, models, resilience patterns, and cost management.
"""

import os
import yaml
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

from .config import (
    LLMProviderConfig,
    AgentLLMConfig,
    LLMConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class ConfigSource:
    """Represents a configuration source with metadata."""
    source_type: str  # 'env', 'file', 'programmatic'
    path: Optional[str] = None
    priority: int = 0  # Higher number = higher priority
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConfigManager:
    """
    Central configuration manager for multi-LLM provider support.
    
    Handles loading, validation, access, and hot-reloading of configuration
    from multiple sources with proper precedence rules.
    """
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Optional path to configuration file
        """
        self.config_path = Path(config_path) if config_path else None
        self._config: Optional[LLMConfig] = None
        self._sources: List[ConfigSource] = []
        self._watchers: List[Any] = []  # File watchers for hot-reload
        self._callbacks: List[Any] = []
        
        # Load initial configuration
        self._load_configuration()
    
    def _load_configuration(self) -> None:
        """Load configuration from all available sources."""
        try:
            # Start with default configuration
            config_data = {}
            
            # Load from file if specified
            if self.config_path and self.config_path.exists():
                file_data = self._load_from_file(self.config_path)
                config_data.update(file_data)
                self._sources.append(ConfigSource(
                    source_type='file',
                    path=str(self.config_path),
                    priority=1
                ))
            
            # Load from environment variables
            env_data = self._load_from_environment()
            config_data.update(env_data)
            self._sources.append(ConfigSource(
                source_type='env',
                priority=2
            ))
            
            # Ensure required fields are present
            if 'providers' not in config_data:
                config_data['providers'] = {}
            if 'agents' not in config_data:
                config_data['agents'] = {}
            
            # Validate and create configuration
            self._config = LLMConfig(**config_data)
            
            logger.info(f"Configuration loaded successfully from {len(self._sources)} sources")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            # Fall back to default configuration
            self._config = LLMConfig(
                providers={},
                agents={}
            )
    
    def _load_from_file(self, path: Path) -> Dict[str, Any]:
        """Load configuration from a file (YAML or JSON)."""
        try:
            with open(path, 'r') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    return yaml.safe_load(f) or {}
                elif path.suffix.lower() == '.json':
                    return json.load(f) or {}
                else:
                    logger.warning(f"Unsupported file format: {path.suffix}")
                    return {}
        except Exception as e:
            logger.error(f"Failed to load configuration from {path}: {e}")
            return {}
    
    def _load_from_environment(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config_data = {}
        
        # Map environment variables to configuration keys
        env_mappings = {
            'LLM_DEFAULT_PROVIDER': 'default_provider',
            'LLM_DEFAULT_MODEL_TYPE': 'default_model_type',
            'LLM_COST_BUDGET': 'cost.budget',
            'LLM_COST_ALERT_THRESHOLD': 'cost.alert_threshold',
            'LLM_RESILIENCE_MAX_RETRIES': 'resilience.max_retries',
            'LLM_RESILIENCE_TIMEOUT': 'resilience.timeout',
        }
        
        for env_var, config_key in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Handle nested keys
                keys = config_key.split('.')
                current = config_data
                for key in keys[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[keys[-1]] = value
        
        # Load provider-specific environment variables
        for provider in ['openai', 'anthropic', 'xai', 'ollama', 'bedrock']:
            provider_key = f"{provider.upper()}_API_KEY"
            api_key = os.environ.get(provider_key)
            if api_key:
                if 'providers' not in config_data:
                    config_data['providers'] = {}
                if provider not in config_data['providers']:
                    config_data['providers'][provider] = {
                        'provider': provider,
                        'models': {}
                    }
                config_data['providers'][provider]['api_key'] = api_key
        
        return config_data
    
    def get_config(self) -> LLMConfig:
        """Get the current configuration."""
        if self._config is None:
            self._load_configuration()
        assert self._config is not None
        return self._config
    
    def get_provider_config(self, provider_name: str) -> Optional[LLMProviderConfig]:
        """Get configuration for a specific provider."""
        config = self.get_config()
        return config.providers.get(provider_name)
    
    def get_agent_config(self, agent_name: str) -> Optional[AgentLLMConfig]:
        """Get configuration for a specific agent."""
        config = self.get_config()
        return config.agents.get(agent_name)
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration programmatically."""
        try:
            current_config = self.get_config()
            current_dict = current_config.model_dump()
            
            # Deep merge updates
            self._deep_merge(current_dict, updates)
            
            # Validate updated configuration
            new_config = LLMConfig(**current_dict)
            self._config = new_config
            
            # Notify callbacks
            self._notify_callbacks()
            
            logger.info("Configuration updated successfully")
            
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")
            raise
    
    def _deep_merge(self, base: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """Deep merge updates into base dictionary."""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def reload_config(self) -> None:
        """Reload configuration from sources."""
        self._load_configuration()
        self._notify_callbacks()
    
    def add_callback(self, callback: Any) -> None:
        """Add a callback to be notified of configuration changes."""
        self._callbacks.append(callback)
    
    def _notify_callbacks(self) -> None:
        """Notify all registered callbacks of configuration changes."""
        for callback in self._callbacks:
            try:
                callback(self._config)
            except Exception as e:
                logger.error(f"Error in configuration change callback: {e}")
    
    def validate_config(self) -> List[str]:
        """Validate the current configuration and return any errors."""
        errors = []
        
        try:
            config = self.get_config()
            
            # Validate provider configurations
            for provider_name, provider_config in config.providers.items():
                try:
                    # Check if provider has required API key
                    if provider_name != 'ollama' and not provider_config.api_key:
                        errors.append(f"Provider {provider_name} missing API key")
                    
                    # Validate model configurations
                    for model_name, model_config in provider_config.models.items():
                        if model_config.max_tokens <= 0:
                            errors.append(f"Model {model_name} has invalid max_tokens: {model_config.max_tokens}")
                        
                        # Note: temperature validation would be added if ModelConfig had temperature field
                
                except Exception as e:
                    errors.append(f"Error validating provider {provider_name}: {e}")
            
            # Validate agent configurations
            for agent_name, agent_config in config.agents.items():
                try:
                    # Check if primary model type is valid (basic validation)
                    if not hasattr(agent_config.primary_model_type, 'value'):
                        errors.append(f"Agent {agent_name} has invalid primary model type: {agent_config.primary_model_type}")
                    
                    # Check if fallback model type is valid (if specified)
                    if agent_config.fallback_model_type and not hasattr(agent_config.fallback_model_type, 'value'):
                        errors.append(f"Agent {agent_name} has invalid fallback model type: {agent_config.fallback_model_type}")
                
                except Exception as e:
                    errors.append(f"Error validating agent {agent_name}: {e}")
        
        except Exception as e:
            errors.append(f"Configuration validation failed: {e}")
        
        return errors
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the current configuration."""
        config = self.get_config()
        
        return {
            'default_provider': config.default_provider,
            'default_model_type': config.default_model_type,
            'providers': list(config.providers.keys()),
            'agents': list(config.agents.keys()),
            'cost_budget': config.cost_config.monthly_budget,
            'resilience_max_retries': config.resilience_config.retry_attempts,
            'sources': [
                {
                    'type': source.source_type,
                    'path': source.path,
                    'priority': source.priority
                }
                for source in self._sources
            ]
        }
    
    def export_config(self, path: Union[str, Path], format: str = 'yaml') -> None:
        """Export current configuration to a file."""
        config = self.get_config()
        config_dict = config.model_dump()
        
        path = Path(path)
        
        try:
            with open(path, 'w') as f:
                if format.lower() == 'yaml':
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
                elif format.lower() == 'json':
                    json.dump(config_dict, f, indent=2)
                else:
                    raise ValueError(f"Unsupported format: {format}")
            
            logger.info(f"Configuration exported to {path}")
            
        except Exception as e:
            logger.error(f"Failed to export configuration to {path}: {e}")
            raise


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def initialize_config(config_path: Optional[Union[str, Path]] = None) -> ConfigManager:
    """Initialize the global configuration manager."""
    global _config_manager
    _config_manager = ConfigManager(config_path)
    return _config_manager
