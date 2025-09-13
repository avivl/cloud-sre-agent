"""Timeout manager implementation for fault tolerance."""

from collections.abc import Callable
from dataclasses import dataclass
import signal
import threading
import time
from typing import Any

from .exceptions import OperationTimeoutError


@dataclass
class TimeoutConfig:
    """Configuration for timeout manager.
    
    Attributes:
        default_timeout: Default timeout in seconds
        max_timeout: Maximum allowed timeout in seconds
        min_timeout: Minimum allowed timeout in seconds
        timeout_handler: Function to call when timeout occurs
        name: Name of the timeout manager
    """

    default_timeout: float = 30.0
    max_timeout: float = 300.0
    min_timeout: float = 0.1
    timeout_handler: Callable[[str, float], None] | None = None
    name: str = "default"


class TimeoutManager:
    """Timeout manager implementation for fault tolerance.
    
    Provides timeout handling for operations with configurable
    timeout values and handlers.
    """

    def __init__(self, config: TimeoutConfig | None = None):
        """Initialize the timeout manager.
        
        Args:
            config: Timeout configuration
        """
        self._config = config or TimeoutConfig()
        self._lock = threading.RLock()
        self._active_timeouts: dict[str, dict[str, Any]] = {}
        self._timeout_history: list[dict[str, Any]] = []
        self._max_history = 100

    def execute_with_timeout(
        self,
        func: Callable[..., Any],
        timeout: float | None = None,
        operation_name: str | None = None,
        *args,
        **kwargs
    ) -> Any:
        """Execute a function with timeout.
        
        Args:
            func: Function to execute
            timeout: Timeout in seconds (uses default if None)
            operation_name: Name of the operation for logging
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            OperationTimeoutError: If operation times out
            Exception: If the function raises an exception
        """
        if timeout is None:
            timeout = self._config.default_timeout

        # Validate timeout
        timeout = max(self._config.min_timeout, min(timeout, self._config.max_timeout))

        operation_name = operation_name or f"operation_{id(func)}"

        with self._lock:
            # Record timeout start
            timeout_id = f"{operation_name}_{int(time.time() * 1000)}"
            self._active_timeouts[timeout_id] = {
                "operation_name": operation_name,
                "timeout": timeout,
                "start_time": time.time(),
                "thread_id": threading.get_ident()
            }

        try:
            # Execute with timeout
            result = self._execute_with_signal_timeout(
                func, timeout, operation_name, *args, **kwargs
            )

            # Record successful completion
            self._record_timeout(timeout_id, True, None)
            return result

        except OperationTimeoutError as e:
            # Record timeout
            self._record_timeout(timeout_id, False, str(e))
            raise

        except Exception as e:
            # Record failure
            self._record_timeout(timeout_id, False, str(e))
            raise

        finally:
            # Clean up active timeout
            with self._lock:
                self._active_timeouts.pop(timeout_id, None)

    def _execute_with_signal_timeout(
        self,
        func: Callable[..., Any],
        timeout: float,
        operation_name: str,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with signal-based timeout.
        
        Args:
            func: Function to execute
            timeout: Timeout in seconds
            operation_name: Name of the operation
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            OperationTimeoutError: If operation times out
        """
        # Set up timeout handler
        def timeout_handler(signum, frame):
            raise OperationTimeoutError(operation_name, timeout)

        # Store original handler
        original_handler = signal.signal(signal.SIGALRM, timeout_handler)

        try:
            # Set alarm
            signal.alarm(int(timeout))

            # Execute function
            result = func(*args, **kwargs)

            # Cancel alarm
            signal.alarm(0)

            return result

        finally:
            # Restore original handler
            signal.signal(signal.SIGALRM, original_handler)

    def _record_timeout(
        self,
        timeout_id: str,
        success: bool,
        error: str | None
    ) -> None:
        """Record a timeout operation.
        
        Args:
            timeout_id: Unique timeout identifier
            success: Whether the operation succeeded
            error: Error message if operation failed
        """
        with self._lock:
            timeout_info = self._active_timeouts.get(timeout_id, {})

            timeout_record = {
                "timeout_id": timeout_id,
                "operation_name": timeout_info.get("operation_name", "unknown"),
                "timeout": timeout_info.get("timeout", 0.0),
                "start_time": timeout_info.get("start_time", time.time()),
                "end_time": time.time(),
                "duration": time.time() - timeout_info.get("start_time", time.time()),
                "success": success,
                "error": error,
                "thread_id": timeout_info.get("thread_id", threading.get_ident())
            }

            self._timeout_history.append(timeout_record)

            # Trim history if needed
            if len(self._timeout_history) > self._max_history:
                self._timeout_history = self._timeout_history[-self._max_history:]

    def get_stats(self) -> dict[str, Any]:
        """Get timeout manager statistics.
        
        Returns:
            Dictionary containing timeout manager statistics
        """
        with self._lock:
            total_operations = len(self._timeout_history)
            successful_operations = sum(1 for op in self._timeout_history if op["success"])
            failed_operations = total_operations - successful_operations

            success_rate = (
                (successful_operations / total_operations * 100) 
                if total_operations > 0 else 0.0
            )

            # Calculate average duration
            durations = [op["duration"] for op in self._timeout_history]
            avg_duration = sum(durations) / len(durations) if durations else 0.0

            # Calculate timeout rate
            timeout_operations = sum(
                1 for op in self._timeout_history 
                if not op["success"] and "timeout" in (op["error"] or "").lower()
            )
            timeout_rate = (
                (timeout_operations / total_operations * 100) 
                if total_operations > 0 else 0.0
            )

            return {
                "name": self._config.name,
                "total_operations": total_operations,
                "successful_operations": successful_operations,
                "failed_operations": failed_operations,
                "timeout_operations": timeout_operations,
                "success_rate": success_rate,
                "timeout_rate": timeout_rate,
                "average_duration": avg_duration,
                "active_timeouts": len(self._active_timeouts),
                "config": {
                    "default_timeout": self._config.default_timeout,
                    "max_timeout": self._config.max_timeout,
                    "min_timeout": self._config.min_timeout
                }
            }

    def get_timeout_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get timeout history.
        
        Args:
            limit: Optional limit on number of records to return
            
        Returns:
            List of timeout operation records
        """
        with self._lock:
            if limit is None:
                return self._timeout_history.copy()
            return self._timeout_history[-limit:]

    def get_active_timeouts(self) -> dict[str, dict[str, Any]]:
        """Get currently active timeouts.
        
        Returns:
            Dictionary of active timeout information
        """
        with self._lock:
            return self._active_timeouts.copy()

    def cancel_timeout(self, timeout_id: str) -> bool:
        """Cancel an active timeout.
        
        Args:
            timeout_id: Timeout identifier to cancel
            
        Returns:
            True if timeout was cancelled, False if not found
        """
        with self._lock:
            if timeout_id in self._active_timeouts:
                del self._active_timeouts[timeout_id]
                return True
            return False

    def reset(self) -> None:
        """Reset the timeout manager.
        
        Clears all history and active timeouts.
        """
        with self._lock:
            self._active_timeouts.clear()
            self._timeout_history.clear()

    def __call__(self, timeout: float | None = None, operation_name: str | None = None):
        """Make timeout manager callable as a decorator.
        
        Args:
            timeout: Timeout in seconds
            operation_name: Name of the operation
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            def wrapper(*args, **kwargs):
                return self.execute_with_timeout(
                    func, timeout, operation_name, *args, **kwargs
                )
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
