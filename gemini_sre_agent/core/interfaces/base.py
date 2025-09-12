# gemini_sre_agent/core/interfaces/base.py

"""
Base interfaces for the Gemini SRE Agent system.

This module defines abstract base classes that form the foundation
for all major components in the system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic

import time
from ..types import (
    AgentId,
    ConfigDict,
    Content,
    JsonDict,
    LogContext,
    Priority,
    RequestId,
    ResponseId,
    Timestamp,
    UserId,
)

# Generic type variables
T = TypeVar('T')
R = TypeVar('R')


class BaseComponent(ABC):
    """
    Abstract base class for all system components.
    
    This class provides common functionality and interface requirements
    for all components in the system.
    """
    
    def __init__(self, component_id: str, name: str) -> None:
        """
        Initialize the base component.
        
        Args:
            component_id: Unique identifier for the component
            name: Human-readable name for the component
        """
        self._component_id = component_id
        self._name = name
        self._created_at = time.time()
        self._status = "initialized"
    
    @property
    def component_id(self) -> str:
        """Get the component's unique identifier."""
        return self._component_id
    
    @property
    def name(self) -> str:
        """Get the component's name."""
        return self._name
    
    @property
    def created_at(self) -> Timestamp:
        """Get the component's creation timestamp."""
        return self._created_at
    
    @property
    def status(self) -> str:
        """Get the component's current status."""
        return self._status
    
    def set_status(self, status: str) -> None:
        """
        Set the component's status.
        
        Args:
            status: New status value
        """
        self._status = status
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the component."""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the component."""
        pass
    
    @abstractmethod
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get the component's health status.
        
        Returns:
            Dictionary containing health status information
        """
        pass
    
    def get_log_context(self) -> LogContext:
        """
        Get logging context for the component.
        
        Returns:
            Dictionary containing logging context
        """
        return {
            "component_id": self._component_id,
            "component_name": self._name,
            "status": self._status,
            "created_at": self._created_at
        }


class ConfigurableComponent(BaseComponent):
    """
    Abstract base class for configurable components.
    
    This class extends BaseComponent with configuration management
    capabilities.
    """
    
    def __init__(self, component_id: str, name: str, config: Optional[ConfigDict] = None) -> None:
        """
        Initialize the configurable component.
        
        Args:
            component_id: Unique identifier for the component
            name: Human-readable name for the component
            config: Optional initial configuration
        """
        super().__init__(component_id, name)
        self._config = config or {}
        self._config_validated = False
    
    @property
    def config(self) -> ConfigDict:
        """Get the current configuration."""
        return self._config.copy()
    
    @abstractmethod
    def configure(self, config: ConfigDict) -> None:
        """
        Configure the component with new settings.
        
        Args:
            config: Configuration dictionary
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: ConfigDict) -> bool:
        """
        Validate a configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if configuration is valid, False otherwise
        """
        pass
    
    def update_config(self, updates: ConfigDict) -> None:
        """
        Update configuration with new values.
        
        Args:
            updates: Configuration updates to apply
        """
        if not self.validate_config({**self._config, **updates}):
            raise ValueError("Invalid configuration updates")
        
        self._config.update(updates)
        self.configure(self._config)


class StatefulComponent(ConfigurableComponent):
    """
    Abstract base class for stateful components.
    
    This class extends ConfigurableComponent with state management
    capabilities.
    """
    
    def __init__(self, component_id: str, name: str, config: Optional[ConfigDict] = None) -> None:
        """
        Initialize the stateful component.
        
        Args:
            component_id: Unique identifier for the component
            name: Human-readable name for the component
            config: Optional initial configuration
        """
        super().__init__(component_id, name, config)
        self._state = {}
        self._state_history = []
    
    @property
    def state(self) -> Dict[str, Any]:
        """Get the current state."""
        return self._state.copy()
    
    @abstractmethod
    def set_state(self, key: str, value: Any) -> None:
        """
        Set a state value.
        
        Args:
            key: State key
            value: State value
        """
        pass
    
    @abstractmethod
    def get_state(self, key: str, default: Any = None) -> Any:
        """
        Get a state value.
        
        Args:
            key: State key
            default: Default value if key not found
            
        Returns:
            State value or default
        """
        pass
    
    @abstractmethod
    def clear_state(self, key: Optional[str] = None) -> None:
        """
        Clear state values.
        
        Args:
            key: Specific key to clear, or None to clear all
        """
        pass
    
    def get_state_snapshot(self) -> Dict[str, Any]:
        """
        Get a complete state snapshot.
        
        Returns:
            Complete state dictionary
        """
        return self._state.copy()
    
    def save_state_history(self) -> None:
        """Save current state to history."""
        self._state_history.append({
            "timestamp": time.time(),
            "state": self._state.copy()
        })


class ProcessableComponent(StatefulComponent, Generic[T, R]):
    """
    Abstract base class for components that process data.
    
    This class extends StatefulComponent with data processing
    capabilities.
    """
    
    def __init__(self, component_id: str, name: str, config: Optional[ConfigDict] = None) -> None:
        """
        Initialize the processable component.
        
        Args:
            component_id: Unique identifier for the component
            name: Human-readable name for the component
            config: Optional initial configuration
        """
        super().__init__(component_id, name, config)
        self._processing_count = 0
        self._last_processed_at: Optional[Timestamp] = None
    
    @property
    def processing_count(self) -> int:
        """Get the number of items processed."""
        return self._processing_count
    
    @property
    def last_processed_at(self) -> Optional[Timestamp]:
        """Get the timestamp of the last processed item."""
        return self._last_processed_at
    
    @abstractmethod
    def process(self, input_data: T) -> R:
        """
        Process input data and return result.
        
        Args:
            input_data: Input data to process
            
        Returns:
            Processing result
        """
        pass
    
    def process_with_metrics(self, input_data: T) -> R:
        """
        Process input data with metrics tracking.
        
        Args:
            input_data: Input data to process
            
        Returns:
            Processing result
        """
        self._processing_count += 1
        self._last_processed_at = time.time()
        
        try:
            result = self.process(input_data)
            self.set_state("last_processing_status", "success")
            return result
        except Exception as e:
            self.set_state("last_processing_status", "error")
            self.set_state("last_processing_error", str(e))
            raise


class MonitorableComponent(ProcessableComponent[T, R]):
    """
    Abstract base class for monitorable components.
    
    This class extends ProcessableComponent with monitoring
    capabilities.
    """
    
    def __init__(self, component_id: str, name: str, config: Optional[ConfigDict] = None) -> None:
        """
        Initialize the monitorable component.
        
        Args:
            component_id: Unique identifier for the component
            name: Human-readable name for the component
            config: Optional initial configuration
        """
        super().__init__(component_id, name, config)
        self._metrics = {}
        self._alerts = []
    
    @property
    def metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return self._metrics.copy()
    
    @property
    def alerts(self) -> List[Dict[str, Any]]:
        """Get current alerts."""
        return self._alerts.copy()
    
    @abstractmethod
    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect component metrics.
        
        Returns:
            Dictionary containing metrics
        """
        pass
    
    @abstractmethod
    def check_health(self) -> bool:
        """
        Check component health.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def update_metrics(self) -> None:
        """Update component metrics."""
        self._metrics = self.collect_metrics()
    
    def add_alert(self, alert_type: str, message: str, severity: str = "warning") -> None:
        """
        Add an alert.
        
        Args:
            alert_type: Type of alert
            message: Alert message
            severity: Alert severity level
        """
        alert = {
            "timestamp": time.time(),
            "type": alert_type,
            "message": message,
            "severity": severity,
            "component_id": self._component_id
        }
        self._alerts.append(alert)
    
    def clear_alerts(self) -> None:
        """Clear all alerts."""
        self._alerts.clear()
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status.
        
        Returns:
            Dictionary containing health status information
        """
        is_healthy = self.check_health()
        self.update_metrics()
        
        return {
            "component_id": self._component_id,
            "name": self._name,
            "status": self._status,
            "healthy": is_healthy,
            "metrics": self._metrics,
            "alerts": self._alerts,
            "processing_count": self._processing_count,
            "last_processed_at": self._last_processed_at
        }
