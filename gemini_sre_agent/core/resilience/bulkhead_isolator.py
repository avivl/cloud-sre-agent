"""Bulkhead isolator implementation for fault tolerance."""

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from .exceptions import BulkheadError, ResourceExhaustedError


@dataclass
class BulkheadConfig:
    """Configuration for bulkhead isolator.
    
    Attributes:
        max_concurrency: Maximum number of concurrent operations
        queue_size: Maximum queue size for waiting operations
        timeout: Timeout for acquiring resources
        name: Name of the bulkhead
    """
    
    max_concurrency: int = 10
    queue_size: int = 100
    timeout: float = 30.0
    name: str = "default"


class BulkheadIsolator:
    """Bulkhead isolator implementation for fault tolerance.
    
    Implements the bulkhead pattern to isolate resources and prevent
    cascading failures by limiting concurrency.
    """
    
    def __init__(self, config: Optional[BulkheadConfig] = None):
        """Initialize the bulkhead isolator.
        
        Args:
            config: Bulkhead configuration
        """
        self._config = config or BulkheadConfig()
        self._lock = threading.RLock()
        self._semaphore = threading.Semaphore(self._config.max_concurrency)
        self._queue = []
        self._active_operations: Dict[str, Dict[str, Any]] = {}
        self._operation_history: list[Dict[str, Any]] = []
        self._max_history = 100
        self._operation_counter = 0
    
    def execute(
        self,
        func: Callable[..., Any],
        operation_name: Optional[str] = None,
        *args,
        **kwargs
    ) -> Any:
        """Execute a function with bulkhead isolation.
        
        Args:
            func: Function to execute
            operation_name: Name of the operation
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            ResourceExhaustedError: If resources are exhausted
            Exception: If the function raises an exception
        """
        operation_name = operation_name or f"operation_{id(func)}"
        
        # Acquire semaphore with timeout
        if not self._semaphore.acquire(timeout=self._config.timeout):
            raise ResourceExhaustedError(
                self._config.name,
                self._config.max_concurrency,
                self._config.max_concurrency
            )
        
        operation_id = f"{operation_name}_{self._operation_counter}"
        self._operation_counter += 1
        
        with self._lock:
            self._active_operations[operation_id] = {
                "operation_name": operation_name,
                "start_time": time.time(),
                "thread_id": threading.get_ident()
            }
        
        try:
            # Execute function
            result = func(*args, **kwargs)
            
            # Record successful completion
            self._record_operation(operation_id, True, None)
            return result
            
        except Exception as e:
            # Record failure
            self._record_operation(operation_id, False, str(e))
            raise
            
        finally:
            # Release semaphore
            self._semaphore.release()
            
            # Clean up active operation
            with self._lock:
                self._active_operations.pop(operation_id, None)
    
    def _record_operation(
        self,
        operation_id: str,
        success: bool,
        error: Optional[str]
    ) -> None:
        """Record an operation.
        
        Args:
            operation_id: Unique operation identifier
            success: Whether the operation succeeded
            error: Error message if operation failed
        """
        with self._lock:
            operation_info = self._active_operations.get(operation_id, {})
            
            operation_record = {
                "operation_id": operation_id,
                "operation_name": operation_info.get("operation_name", "unknown"),
                "start_time": operation_info.get("start_time", time.time()),
                "end_time": time.time(),
                "duration": time.time() - operation_info.get("start_time", time.time()),
                "success": success,
                "error": error,
                "thread_id": operation_info.get("thread_id", threading.get_ident())
            }
            
            self._operation_history.append(operation_record)
            
            # Trim history if needed
            if len(self._operation_history) > self._max_history:
                self._operation_history = self._operation_history[-self._max_history:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bulkhead isolator statistics.
        
        Returns:
            Dictionary containing bulkhead isolator statistics
        """
        with self._lock:
            total_operations = len(self._operation_history)
            successful_operations = sum(1 for op in self._operation_history if op["success"])
            failed_operations = total_operations - successful_operations
            
            success_rate = (successful_operations / total_operations * 100) if total_operations > 0 else 0.0
            
            # Calculate average duration
            durations = [op["duration"] for op in self._operation_history]
            avg_duration = sum(durations) / len(durations) if durations else 0.0
            
            # Calculate current utilization
            current_usage = len(self._active_operations)
            utilization_rate = (current_usage / self._config.max_concurrency * 100) if self._config.max_concurrency > 0 else 0.0
            
            return {
                "name": self._config.name,
                "total_operations": total_operations,
                "successful_operations": successful_operations,
                "failed_operations": failed_operations,
                "success_rate": success_rate,
                "average_duration": avg_duration,
                "current_usage": current_usage,
                "max_concurrency": self._config.max_concurrency,
                "utilization_rate": utilization_rate,
                "queue_size": len(self._queue),
                "config": {
                    "max_concurrency": self._config.max_concurrency,
                    "queue_size": self._config.queue_size,
                    "timeout": self._config.timeout
                }
            }
    
    def get_operation_history(self, limit: Optional[int] = None) -> list[Dict[str, Any]]:
        """Get operation history.
        
        Args:
            limit: Optional limit on number of records to return
            
        Returns:
            List of operation records
        """
        with self._lock:
            if limit is None:
                return self._operation_history.copy()
            return self._operation_history[-limit:]
    
    def get_active_operations(self) -> Dict[str, Dict[str, Any]]:
        """Get currently active operations.
        
        Returns:
            Dictionary of active operation information
        """
        with self._lock:
            return self._active_operations.copy()
    
    def get_available_capacity(self) -> int:
        """Get available capacity.
        
        Returns:
            Number of available slots
        """
        return self._semaphore._value
    
    def is_available(self) -> bool:
        """Check if bulkhead has available capacity.
        
        Returns:
            True if capacity is available, False otherwise
        """
        return self.get_available_capacity() > 0
    
    def reset(self) -> None:
        """Reset the bulkhead isolator.
        
        Clears all history and active operations.
        """
        with self._lock:
            self._active_operations.clear()
            self._operation_history.clear()
            self._queue.clear()
    
    def __call__(self, operation_name: Optional[str] = None):
        """Make bulkhead isolator callable as a decorator.
        
        Args:
            operation_name: Name of the operation
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            def wrapper(*args, **kwargs):
                return self.execute(func, operation_name, *args, **kwargs)
            return wrapper
        return decorator
    
    def __enter__(self):
        """Context manager entry.
        
        Returns:
            Self
        """
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit.
        
        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        pass
