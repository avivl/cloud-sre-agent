"""Rate limiter implementation for fault tolerance."""

from collections.abc import Callable
from dataclasses import dataclass
import threading
import time
from typing import Any

from .exceptions import RateLimitExceededError


@dataclass
class RateLimitConfig:
    """Configuration for rate limiter.
    
    Attributes:
        limit: Maximum number of requests allowed
        window_seconds: Time window in seconds
        name: Name of the rate limiter
    """

    limit: int = 100
    window_seconds: int = 60
    name: str = "default"


class RateLimiter:
    """Rate limiter implementation for fault tolerance.
    
    Implements rate limiting to prevent overwhelming services
    and maintain system stability.
    """

    def __init__(self, config: RateLimitConfig | None = None):
        """Initialize the rate limiter.
        
        Args:
            config: Rate limit configuration
        """
        self._config = config or RateLimitConfig()
        self._lock = threading.RLock()
        self._requests: list[float] = []
        self._request_history: list[dict[str, Any]] = []
        self._max_history = 1000

    def execute(
        self,
        func: Callable[..., Any],
        operation_name: str | None = None,
        *args,
        **kwargs
    ) -> Any:
        """Execute a function with rate limiting.
        
        Args:
            func: Function to execute
            operation_name: Name of the operation
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            RateLimitExceededError: If rate limit is exceeded
            Exception: If the function raises an exception
        """
        operation_name = operation_name or f"operation_{id(func)}"

        # Check rate limit
        if not self._check_rate_limit():
            raise RateLimitExceededError(
                self._config.name,
                self._config.limit,
                self._config.window_seconds,
                len(self._requests)
            )

        # Record request
        request_time = time.time()
        self._record_request(request_time, operation_name)

        try:
            # Execute function
            result = func(*args, **kwargs)

            # Record successful completion
            self._record_completion(request_time, True, None)
            return result

        except Exception as e:
            # Record failure
            self._record_completion(request_time, False, str(e))
            raise

    def _check_rate_limit(self) -> bool:
        """Check if request is within rate limit.
        
        Returns:
            True if request is allowed, False otherwise
        """
        current_time = time.time()
        window_start = current_time - self._config.window_seconds

        with self._lock:
            # Remove old requests outside the window
            self._requests = [req_time for req_time in self._requests if req_time > window_start]

            # Check if we're within the limit
            if len(self._requests) >= self._config.limit:
                return False

            # Add current request
            self._requests.append(current_time)
            return True

    def _record_request(self, request_time: float, operation_name: str) -> None:
        """Record a request.
        
        Args:
            request_time: Time when request was made
            operation_name: Name of the operation
        """
        with self._lock:
            request_record = {
                "timestamp": request_time,
                "operation_name": operation_name,
                "success": None,  # Will be updated when operation completes
                "error": None,
                "thread_id": threading.get_ident()
            }

            self._request_history.append(request_record)

            # Trim history if needed
            if len(self._request_history) > self._max_history:
                self._request_history = self._request_history[-self._max_history:]

    def _record_completion(
        self,
        request_time: float,
        success: bool,
        error: str | None
    ) -> None:
        """Record operation completion.
        
        Args:
            request_time: Time when request was made
            success: Whether the operation succeeded
            error: Error message if operation failed
        """
        with self._lock:
            # Find the matching request record
            for record in reversed(self._request_history):
                if record["timestamp"] == request_time and record["success"] is None:
                    record["success"] = success
                    record["error"] = error
                    break

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics.
        
        Returns:
            Dictionary containing rate limiter statistics
        """
        with self._lock:
            current_time = time.time()
            window_start = current_time - self._config.window_seconds

            # Count requests in current window
            current_requests = len([req for req in self._requests if req > window_start])

            # Count total requests in history
            total_requests = len(self._request_history)
            successful_requests = sum(1 for req in self._request_history if req["success"] is True)
            failed_requests = sum(1 for req in self._request_history if req["success"] is False)

            success_rate = (
                (successful_requests / total_requests * 100) 
                if total_requests > 0 else 0.0
            )

            # Calculate requests per second
            requests_per_second = (
                current_requests / self._config.window_seconds 
                if self._config.window_seconds > 0 else 0.0
            )

            return {
                "name": self._config.name,
                "current_requests": current_requests,
                "limit": self._config.limit,
                "window_seconds": self._config.window_seconds,
                "requests_per_second": requests_per_second,
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "success_rate": success_rate,
                "utilization_rate": (
                    (current_requests / self._config.limit * 100) 
                    if self._config.limit > 0 else 0.0
                ),
                "config": {
                    "limit": self._config.limit,
                    "window_seconds": self._config.window_seconds
                }
            }

    def get_request_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get request history.
        
        Args:
            limit: Optional limit on number of records to return
            
        Returns:
            List of request records
        """
        with self._lock:
            if limit is None:
                return self._request_history.copy()
            return self._request_history[-limit:]

    def get_current_requests(self) -> int:
        """Get current number of requests in the window.
        
        Returns:
            Number of requests in current window
        """
        current_time = time.time()
        window_start = current_time - self._config.window_seconds

        with self._lock:
            return len([req for req in self._requests if req > window_start])

    def is_available(self) -> bool:
        """Check if rate limit allows new requests.
        
        Returns:
            True if requests are allowed, False otherwise
        """
        return self.get_current_requests() < self._config.limit

    def reset(self) -> None:
        """Reset the rate limiter.
        
        Clears all history and requests.
        """
        with self._lock:
            self._requests.clear()
            self._request_history.clear()

    def __call__(self, operation_name: str | None = None):
        """Make rate limiter callable as a decorator.
        
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
