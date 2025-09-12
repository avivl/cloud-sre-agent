"""Retry handler implementation for fault tolerance."""

import random
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from .exceptions import RetryError, MaxRetriesExceededError


class RetryStrategy(Enum):
    """Retry strategies."""
    
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CUSTOM = "custom"


@dataclass
class RetryConfig:
    """Configuration for retry handler.
    
    Attributes:
        max_attempts: Maximum number of retry attempts
        backoff_strategy: Strategy for calculating backoff delay
        base_delay: Base delay in seconds for backoff calculation
        max_delay: Maximum delay in seconds
        jitter: Whether to add random jitter to delays
        jitter_range: Range for jitter (0.0 to 1.0)
        exponential_base: Base for exponential backoff
        linear_increment: Increment for linear backoff
        custom_delays: Custom delay sequence
        expected_exception: Exception types that should trigger retry
        ignored_exception: Exception types that should not trigger retry
        name: Name of the retry handler
    """
    
    max_attempts: int = 3
    backoff_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    jitter_range: float = 0.1
    exponential_base: float = 2.0
    linear_increment: float = 1.0
    custom_delays: List[float] = field(default_factory=list)
    expected_exception: Union[Type[Exception], tuple[Type[Exception], ...]] = Exception
    ignored_exception: Union[Type[Exception], tuple[Type[Exception], ...]] = ()
    name: str = "default"


class RetryHandler:
    """Retry handler implementation for fault tolerance.
    
    Provides configurable retry logic with various backoff strategies
    and exception handling.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """Initialize the retry handler.
        
        Args:
            config: Retry configuration
        """
        self._config = config or RetryConfig()
        self._lock = threading.RLock()
        self._attempt_count = 0
        self._retry_history: List[Dict[str, Any]] = []
        self._max_history = 100
    
    def execute(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            MaxRetriesExceededError: If maximum retries are exceeded
            Exception: If the function raises an exception after all retries
        """
        with self._lock:
            self._attempt_count = 0
            last_exception = None
            
            while self._attempt_count < self._config.max_attempts:
                self._attempt_count += 1
                
                try:
                    result = func(*args, **kwargs)
                    self._record_attempt(True, None)
                    return result
                    
                except Exception as e:
                    last_exception = e
                    self._record_attempt(False, str(e))
                    
                    # Check if exception should be ignored
                    if isinstance(e, self._config.ignored_exception):
                        raise
                    
                    # Check if exception is expected for retry
                    if not isinstance(e, self._config.expected_exception):
                        raise
                    
                    # If this was the last attempt, raise the exception
                    if self._attempt_count >= self._config.max_attempts:
                        break
                    
                    # Calculate delay and wait
                    delay = self._calculate_delay()
                    if delay > 0:
                        time.sleep(delay)
            
            # All retries exhausted
            raise MaxRetriesExceededError(
                self._config.max_attempts,
                last_exception,
                {"attempts": self._attempt_count}
            )
    
    def _calculate_delay(self) -> float:
        """Calculate delay for next retry attempt.
        
        Returns:
            Delay in seconds
        """
        if self._config.backoff_strategy == RetryStrategy.FIXED:
            delay = self._config.base_delay
            
        elif self._config.backoff_strategy == RetryStrategy.EXPONENTIAL:
            delay = self._config.base_delay * (
                self._config.exponential_base ** (self._attempt_count - 1)
            )
            
        elif self._config.backoff_strategy == RetryStrategy.LINEAR:
            delay = self._config.base_delay + (
                self._config.linear_increment * (self._attempt_count - 1)
            )
            
        elif self._config.backoff_strategy == RetryStrategy.CUSTOM:
            if self._attempt_count - 1 < len(self._config.custom_delays):
                delay = self._config.custom_delays[self._attempt_count - 1]
            else:
                delay = self._config.base_delay
        else:
            delay = self._config.base_delay
        
        # Apply maximum delay limit
        delay = min(delay, self._config.max_delay)
        
        # Apply jitter if enabled
        if self._config.jitter and delay > 0:
            jitter_amount = delay * self._config.jitter_range
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay + jitter)
        
        return delay
    
    def _record_attempt(self, success: bool, error: Optional[str]) -> None:
        """Record a retry attempt in the history.
        
        Args:
            success: Whether the attempt was successful
            error: Error message if attempt failed
        """
        attempt_record = {
            "timestamp": time.time(),
            "attempt": self._attempt_count,
            "success": success,
            "error": error,
            "delay": self._calculate_delay() if not success and self._attempt_count < self._config.max_attempts else 0.0
        }
        
        self._retry_history.append(attempt_record)
        
        # Trim history if needed
        if len(self._retry_history) > self._max_history:
            self._retry_history = self._retry_history[-self._max_history:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retry handler statistics.
        
        Returns:
            Dictionary containing retry handler statistics
        """
        with self._lock:
            total_attempts = len(self._retry_history)
            successful_attempts = sum(1 for attempt in self._retry_history if attempt["success"])
            failed_attempts = total_attempts - successful_attempts
            
            success_rate = (successful_attempts / total_attempts * 100) if total_attempts > 0 else 0.0
            
            # Calculate average delay
            delays = [attempt["delay"] for attempt in self._retry_history if attempt["delay"] > 0]
            avg_delay = sum(delays) / len(delays) if delays else 0.0
            
            return {
                "name": self._config.name,
                "total_attempts": total_attempts,
                "successful_attempts": successful_attempts,
                "failed_attempts": failed_attempts,
                "success_rate": success_rate,
                "average_delay": avg_delay,
                "config": {
                    "max_attempts": self._config.max_attempts,
                    "backoff_strategy": self._config.backoff_strategy.value,
                    "base_delay": self._config.base_delay,
                    "max_delay": self._config.max_delay,
                    "jitter": self._config.jitter
                }
            }
    
    def get_retry_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get retry history.
        
        Args:
            limit: Optional limit on number of records to return
            
        Returns:
            List of retry attempt records
        """
        with self._lock:
            if limit is None:
                return self._retry_history.copy()
            return self._retry_history[-limit:]
    
    def reset(self) -> None:
        """Reset the retry handler.
        
        Clears all counters and history.
        """
        with self._lock:
            self._attempt_count = 0
            self._retry_history.clear()
    
    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Make retry handler callable as a decorator.
        
        Args:
            func: Function to wrap
            
        Returns:
            Wrapped function
        """
        def wrapper(*args, **kwargs):
            return self.execute(func, *args, **kwargs)
        
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
