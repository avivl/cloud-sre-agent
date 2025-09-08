"""
Configuration management for capability definitions.

This module provides functionality to load and manage capability definitions
from configuration files, allowing for easy customization and extension of
the capability discovery system.
"""

import logging
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .models import ModelCapability

logger = logging.getLogger(__name__)


class CapabilityConfig:
    """Manages capability definitions loaded from configuration files."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the capability configuration.
        
        Args:
            config_path: Path to the capability definitions YAML file.
                        If None, uses default path.
        """
        if config_path is None:
            # Default to config/capability_definitions.yaml relative to project root
            project_root = Path(__file__).parent.parent.parent.parent
            config_path = str(project_root / "config" / "capability_definitions.yaml")
        
        self.config_path = Path(config_path)
        self._config_data: Dict[str, Any] = {}
        self._capabilities: Dict[str, ModelCapability] = {}
        self._provider_mappings: Dict[str, Dict[str, Any]] = {}
        self._task_requirements: Dict[str, Dict[str, List[str]]] = {}
        
        self._load_config()
    
    def _load_config(self) -> None:
        """Load capability definitions from the configuration file."""
        try:
            if not self.config_path.exists():
                logger.warning(f"Capability config file not found: {self.config_path}")
                self._load_default_capabilities()
                return
            
            with open(self.config_path, 'r') as f:
                self._config_data = yaml.safe_load(f)
            
            self._parse_capabilities()
            self._parse_provider_mappings()
            self._parse_task_requirements()
            
            logger.info(f"Loaded capability configuration from {self.config_path}")
            logger.info(f"Loaded {len(self._capabilities)} capability definitions")
            
        except Exception as e:
            logger.error(f"Failed to load capability configuration: {e}")
            self._load_default_capabilities()
    
    def _load_default_capabilities(self) -> None:
        """Load default capability definitions if config file is not available."""
        logger.info("Loading default capability definitions")
        
        # Basic text generation capability
        self._capabilities["text_generation"] = ModelCapability(
            name="text_generation",
            description="Generates human-like text based on a given prompt",
            parameters={
                "max_tokens": {"type": "integer", "default": 1000},
                "temperature": {"type": "float", "default": 0.7}
            },
            performance_score=0.8,
            cost_efficiency=0.7
        )
        
        # Code generation capability
        self._capabilities["code_generation"] = ModelCapability(
            name="code_generation",
            description="Generates programming code in various languages",
            parameters={
                "language": {"type": "string"},
                "framework": {"type": "string", "optional": True}
            },
            performance_score=0.9,
            cost_efficiency=0.6
        )
    
    def _parse_capabilities(self) -> None:
        """Parse capability definitions from config data."""
        capabilities_data = self._config_data.get("capabilities", {})
        
        for cap_name, cap_data in capabilities_data.items():
            try:
                capability = ModelCapability(
                    name=cap_data["name"],
                    description=cap_data["description"],
                    parameters=cap_data.get("parameters", {}),
                    performance_score=cap_data.get("performance_score", 0.5),
                    cost_efficiency=cap_data.get("cost_efficiency", 0.5)
                )
                self._capabilities[cap_name] = capability
                
            except Exception as e:
                logger.error(f"Failed to parse capability '{cap_name}': {e}")
    
    def _parse_provider_mappings(self) -> None:
        """Parse provider-specific capability mappings."""
        self._provider_mappings = self._config_data.get("provider_mappings", {})
    
    def _parse_task_requirements(self) -> None:
        """Parse task-specific capability requirements."""
        self._task_requirements = self._config_data.get("task_requirements", {})
    
    def get_capability(self, name: str) -> Optional[ModelCapability]:
        """
        Get a capability definition by name.
        
        Args:
            name: The name of the capability.
            
        Returns:
            ModelCapability object if found, None otherwise.
        """
        return self._capabilities.get(name)
    
    def get_all_capabilities(self) -> Dict[str, ModelCapability]:
        """
        Get all capability definitions.
        
        Returns:
            Dictionary mapping capability names to ModelCapability objects.
        """
        return self._capabilities.copy()
    
    def get_capability_names(self) -> List[str]:
        """
        Get list of all capability names.
        
        Returns:
            List of capability names.
        """
        return list(self._capabilities.keys())
    
    def get_provider_capabilities(self, provider_name: str, model_name: Optional[str] = None) -> List[str]:
        """
        Get capabilities for a specific provider and optionally a specific model.
        
        Args:
            provider_name: Name of the provider (e.g., "openai", "anthropic").
            model_name: Optional specific model name.
            
        Returns:
            List of capability names supported by the provider/model.
        """
        capabilities = []
        
        # Get provider-specific capabilities
        provider_data = self._provider_mappings.get(provider_name, {})
        default_caps = provider_data.get("default_capabilities", [])
        capabilities.extend(default_caps)
        
        # Add model-specific capabilities if model is specified
        if model_name:
            model_specific = provider_data.get("model_specific", {})
            model_caps = model_specific.get(model_name, {}).get("additional_capabilities", [])
            capabilities.extend(model_caps)
        
        return list(set(capabilities))  # Remove duplicates
    
    def get_task_requirements(self, task_type: str) -> Dict[str, List[str]]:
        """
        Get capability requirements for a specific task type.
        
        Args:
            task_type: Type of task (e.g., "text_completion", "code_generation").
            
        Returns:
            Dictionary with 'required_capabilities' and 'optional_capabilities' lists.
        """
        return self._task_requirements.get(task_type, {
            "required_capabilities": [],
            "optional_capabilities": []
        })
    
    def get_required_capabilities(self, task_type: str) -> List[str]:
        """
        Get required capabilities for a task type.
        
        Args:
            task_type: Type of task.
            
        Returns:
            List of required capability names.
        """
        requirements = self.get_task_requirements(task_type)
        return requirements.get("required_capabilities", [])
    
    def get_optional_capabilities(self, task_type: str) -> List[str]:
        """
        Get optional capabilities for a task type.
        
        Args:
            task_type: Type of task.
            
        Returns:
            List of optional capability names.
        """
        requirements = self.get_task_requirements(task_type)
        return requirements.get("optional_capabilities", [])
    
    def validate_capability_requirements(self, task_type: str, available_capabilities: List[str]) -> Dict[str, Any]:
        """
        Validate if available capabilities meet task requirements.
        
        Args:
            task_type: Type of task to validate for.
            available_capabilities: List of available capability names.
            
        Returns:
            Dictionary with validation results including:
            - 'meets_requirements': Boolean indicating if requirements are met
            - 'missing_required': List of missing required capabilities
            - 'available_optional': List of available optional capabilities
            - 'missing_optional': List of missing optional capabilities
        """
        required = set(self.get_required_capabilities(task_type))
        optional = set(self.get_optional_capabilities(task_type))
        available = set(available_capabilities)
        
        missing_required = required - available
        available_optional = optional & available
        missing_optional = optional - available
        
        meets_requirements = len(missing_required) == 0
        
        return {
            "meets_requirements": meets_requirements,
            "missing_required": list(missing_required),
            "available_optional": list(available_optional),
            "missing_optional": list(missing_optional),
            "coverage_score": len(available_optional) / len(optional) if optional else 1.0
        }
    
    def get_performance_thresholds(self) -> Dict[str, float]:
        """Get performance thresholds for capability scoring."""
        return self._config_data.get("performance_thresholds", {
            "excellent": 0.9,
            "good": 0.7,
            "fair": 0.5,
            "poor": 0.3
        })
    
    def get_cost_thresholds(self) -> Dict[str, float]:
        """Get cost efficiency thresholds."""
        return self._config_data.get("cost_thresholds", {
            "very_efficient": 0.8,
            "efficient": 0.6,
            "moderate": 0.4,
            "expensive": 0.2
        })
    
    def reload_config(self) -> None:
        """Reload configuration from file."""
        logger.info("Reloading capability configuration")
        self._load_config()
    
    def add_capability(self, capability: ModelCapability) -> None:
        """
        Add a new capability definition.
        
        Args:
            capability: ModelCapability object to add.
        """
        self._capabilities[capability.name] = capability
        logger.info(f"Added capability: {capability.name}")
    
    def remove_capability(self, name: str) -> bool:
        """
        Remove a capability definition.
        
        Args:
            name: Name of the capability to remove.
            
        Returns:
            True if capability was removed, False if not found.
        """
        if name in self._capabilities:
            del self._capabilities[name]
            logger.info(f"Removed capability: {name}")
            return True
        return False


# Global instance for easy access
_capability_config: Optional[CapabilityConfig] = None


def get_capability_config() -> CapabilityConfig:
    """
    Get the global capability configuration instance.
    
    Returns:
        CapabilityConfig instance.
    """
    global _capability_config
    if _capability_config is None:
        _capability_config = CapabilityConfig()
    return _capability_config


def reload_capability_config() -> None:
    """Reload the global capability configuration."""
    global _capability_config
    if _capability_config is not None:
        _capability_config.reload_config()
    else:
        _capability_config = CapabilityConfig()
