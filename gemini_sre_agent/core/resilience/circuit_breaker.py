"""Circuit breaker implementation for fault tolerance."""

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from .exceptions import CircuitBreakerError, CircuitOpenError, CircuitHalfOpenError


class CircuitState(Enum):
    """Circuit breaker states."""
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker.
    
    Attributes:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time in seconds before attempting recovery
        success_threshold: Number of successes needed to close circuit from half-open
        expected_exception: Exception types that count as failures
        ignored_exception: Exception types that should be ignored
        name: Name of the circuit breaker
        timeout: Timeout for individual operations
    """
    
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    expected_exception: Union[Type[Exception], tuple[Type[Exception], ...]] = Exception
    ignored_exception: Union[Type[Exception], tuple[Type[Exception], ...]] = ()
    name: str = "default"
    timeout: Optional[float] = None


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance.
    
    The circuit breaker pattern prevents cascading failures by temporarily
    blocking calls to a failing service. It has three states:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Circuit is open, calls fail immediately
    - HALF_OPEN: Testing if service has recovered
    """
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        """Initialize the circuit breaker.
        
        Args:
            config: Circuit breaker configuration
        """
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._lock = threading.RLock()
        self._call_count = 0
        self._call_history: List[Dict[str, Any]] = []
        self._max_history = 100
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state.
        
        Returns:
            Current circuit state
        """
        return self._state
    
    @property
    def failure_count(self) -> int:
        """Get current failure count.
        
        Returns:
            Current failure count
        """
        return self._failure_count
    
    @property
    def success_count(self) -> int:
        """Get current success count.
        
        Returns:
            Current success count
        """
        return self._success_count
    
    @property
    def call_count(self) -> int:
        """Get total call count.
        
        Returns:
            Total number of calls made
        """
        return self._call_count
    
    def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitOpenError: If circuit is open
            CircuitHalfOpenError: If circuit is half-open and call fails
            Exception: If the function raises an exception
        """
        with self._lock:
            self._call_count += 1
            
            # Check if circuit should be opened
            if self._state == CircuitState.CLOSED:
                if self._failure_count >= self._config.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._last_failure_time = time.time()
            
            # Check if circuit should be half-opened
            elif self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self._config.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
            
            # Handle different states
            if self._state == CircuitState.OPEN:
                raise CircuitOpenError(
                    self._config.name,
                    self._failure_count,
                    self._config.failure_threshold
                )
            
            # Execute the function
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
                
            except Exception as e:
                self._on_failure(e)
                raise
    
    def _on_success(self) -> None:
        """Handle successful call.
        
        Updates circuit state based on success.
        """
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0
            
            # Record success in history
            self._record_call(True, None)
    
    def _on_failure(self, exception: Exception) -> None:
        """Handle failed call.
        
        Args:
            exception: Exception that occurred
        """
        with self._lock:
            # Check if exception should be ignored
            if isinstance(exception, self._config.ignored_exception):
                return
            
            # Check if exception is expected
            if not isinstance(exception, self._config.expected_exception):
                return
            
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            # If in half-open state, open the circuit on failure
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._success_count = 0
            
            # Record failure in history
            self._record_call(False, str(exception))
    
    def _record_call(self, success: bool, error: Optional[str]) -> None:
        """Record a call in the history.
        
        Args:
            success: Whether the call was successful
            error: Error message if call failed
        """
        call_record = {
            "timestamp": time.time(),
            "success": success,
            "error": error,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count
        }
        
        self._call_history.append(call_record)
        
        # Trim history if needed
        if len(self._call_history) > self._max_history:
            self._call_history = self._call_history[-self._max_history:]
    
    def reset(self) -> None:
        """Reset the circuit breaker to closed state.
        
        Clears all counters and resets state.
        """
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = 0.0
            self._call_history.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics.
        
        Returns:
            Dictionary containing circuit breaker statistics
        """
        with self._lock:
            total_calls = len(self._call_history)
            successful_calls = sum(1 for call in self._call_history if call["success"])
            failed_calls = total_calls - successful_calls
            
            success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0.0
            
            return {
                "name": self._config.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "total_calls": total_calls,
                "successful_calls": successful_calls,
                "failed_calls": failed_calls,
                "success_rate": success_rate,
                "last_failure_time": self._last_failure_time,
                "config": {
                    "failure_threshold": self._config.failure_threshold,
                    "recovery_timeout": self._config.recovery_timeout,
                    "success_threshold": self._config.success_threshold,
                    "timeout": self._config.timeout
                }
            }
    
    def get_call_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get call history.
        
        Args:
            limit: Optional limit on number of records to return
            
        Returns:
            List of call records
        """
        with self._lock:
            if limit is None:
                return self._call_history.copy()
            return self._call_history[-limit:]
    
    def is_available(self) -> bool:
        """Check if circuit breaker is available for calls.
        
        Returns:
            True if circuit is closed or half-open, False if open
        """
        return self._state != CircuitState.OPEN
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get detailed state information.
        
        Returns:
            Dictionary containing detailed state information
        """
        with self._lock:
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
                "time_since_last_failure": time.time() - self._last_failure_time,
                "is_available": self.is_available(),
                "config": {
                    "failure_threshold": self._config.failure_threshold,
                    "recovery_timeout": self._config.recovery_timeout,
                    "success_threshold": self._config.success_threshold,
                    "timeout": self._config.timeout
                }
            }
    
    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Make circuit breaker callable as a decorator.
        
        Args:
            func: Function to wrap
            
        Returns:
            Wrapped function
        """
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        
        return wrapper
    
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
