"""Fault tolerance implementation for resilience patterns."""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from .exceptions import (
    CircuitBreakerError,
    RetryExhaustedError,
    TimeoutError,
    BulkheadError,
    RateLimitError,
    HealthCheckError
)
from .circuit_breaker import CircuitBreaker, CircuitState
from .retry_handler import RetryHandler, RetryConfig
from .timeout_manager import TimeoutManager, TimeoutConfig
from .bulkhead_isolator import BulkheadIsolator, BulkheadConfig
from .rate_limiter import RateLimiter, RateLimitConfig
from .health_checker import HealthChecker, HealthCheck, HealthStatus

T = TypeVar("T")


class FaultToleranceStrategy(Enum):
    """Fault tolerance strategies."""
    
    NONE = "none"
    RETRY_ONLY = "retry_only"
    CIRCUIT_BREAKER_ONLY = "circuit_breaker_only"
    TIMEOUT_ONLY = "timeout_only"
    BULKHEAD_ONLY = "bulkhead_only"
    RATE_LIMIT_ONLY = "rate_limit_only"
    HEALTH_CHECK_ONLY = "health_check_only"
    FULL_PROTECTION = "full_protection"
    CUSTOM = "custom"


@dataclass
class FaultToleranceConfig:
    """Fault tolerance configuration.
    
    Attributes:
        strategy: Fault tolerance strategy to use
        retry_config: Retry configuration
        circuit_breaker_config: Circuit breaker configuration
        timeout_config: Timeout configuration
        bulkhead_config: Bulkhead configuration
        rate_limit_config: Rate limit configuration
        health_checks: Health check configurations
        fallback_func: Fallback function for failures
        enable_metrics: Whether to enable metrics collection
        enable_logging: Whether to enable logging
    """
    
    strategy: FaultToleranceStrategy = FaultToleranceStrategy.FULL_PROTECTION
    retry_config: Optional[RetryConfig] = None
    circuit_breaker_config: Optional[Dict[str, Any]] = None
    timeout_config: Optional[TimeoutConfig] = None
    bulkhead_config: Optional[BulkheadConfig] = None
    rate_limit_config: Optional[RateLimitConfig] = None
    health_checks: List[Dict[str, Any]] = field(default_factory=list)
    fallback_func: Optional[Callable[[], T]] = None
    enable_metrics: bool = True
    enable_logging: bool = True


class FaultToleranceManager:
    """Fault tolerance manager for resilience patterns.
    
    Provides a unified interface for applying multiple
    resilience patterns to operations.
    """
    
    def __init__(self, config: FaultToleranceConfig):
        """Initialize the fault tolerance manager.
        
        Args:
            config: Fault tolerance configuration
        """
        self._config = config
        self._circuit_breaker: Optional[CircuitBreaker] = None
        self._retry_handler: Optional[RetryHandler] = None
        self._timeout_manager: Optional[TimeoutManager] = None
        self._bulkhead_isolator: Optional[BulkheadIsolator] = None
        self._rate_limiter: Optional[RateLimiter] = None
        self._health_checker: Optional[HealthChecker] = None
        self._metrics: Dict[str, Any] = {}
        self._setup_resilience_patterns()
    
    def _setup_resilience_patterns(self) -> None:
        """Setup resilience patterns based on configuration."""
        if self._config.strategy == FaultToleranceStrategy.NONE:
            return
        
        # Setup retry handler
        if (self._config.strategy in [
            FaultToleranceStrategy.RETRY_ONLY,
            FaultToleranceStrategy.FULL_PROTECTION,
            FaultToleranceStrategy.CUSTOM
        ] and self._config.retry_config):
            self._retry_handler = RetryHandler(self._config.retry_config)
        
        # Setup circuit breaker
        if (self._config.strategy in [
            FaultToleranceStrategy.CIRCUIT_BREAKER_ONLY,
            FaultToleranceStrategy.FULL_PROTECTION,
            FaultToleranceStrategy.CUSTOM
        ] and self._config.circuit_breaker_config):
            self._circuit_breaker = CircuitBreaker(**self._config.circuit_breaker_config)
        
        # Setup timeout manager
        if (self._config.strategy in [
            FaultToleranceStrategy.TIMEOUT_ONLY,
            FaultToleranceStrategy.FULL_PROTECTION,
            FaultToleranceStrategy.CUSTOM
        ] and self._config.timeout_config):
            self._timeout_manager = TimeoutManager(self._config.timeout_config)
        
        # Setup bulkhead isolator
        if (self._config.strategy in [
            FaultToleranceStrategy.BULKHEAD_ONLY,
            FaultToleranceStrategy.FULL_PROTECTION,
            FaultToleranceStrategy.CUSTOM
        ] and self._config.bulkhead_config):
            self._bulkhead_isolator = BulkheadIsolator(self._config.bulkhead_config)
        
        # Setup rate limiter
        if (self._config.strategy in [
            FaultToleranceStrategy.RATE_LIMIT_ONLY,
            FaultToleranceStrategy.FULL_PROTECTION,
            FaultToleranceStrategy.CUSTOM
        ] and self._config.rate_limit_config):
            self._rate_limiter = RateLimiter(self._config.rate_limit_config)
        
        # Setup health checker
        if (self._config.strategy in [
            FaultToleranceStrategy.HEALTH_CHECK_ONLY,
            FaultToleranceStrategy.FULL_PROTECTION,
            FaultToleranceStrategy.CUSTOM
        ] and self._config.health_checks):
            self._health_checker = HealthChecker()
            for health_check_config in self._config.health_checks:
                health_check = HealthCheck(**health_check_config)
                self._health_checker.add_health_check(health_check)
    
    async def execute_with_fault_tolerance(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Execute a function with fault tolerance.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerError: If circuit breaker is open
            RetryExhaustedError: If retries are exhausted
            TimeoutError: If operation times out
            BulkheadError: If bulkhead is full
            RateLimitError: If rate limit is exceeded
            HealthCheckError: If health checks fail
        """
        # Check health first
        if self._health_checker and not self._health_checker.is_healthy():
            if self._config.fallback_func:
                return self._config.fallback_func()
            raise HealthCheckError("System is unhealthy")
        
        # Apply rate limiting
        if self._rate_limiter:
            await self._rate_limiter.acquire()
        
        # Apply bulkhead isolation
        if self._bulkhead_isolator:
            await self._bulkhead_isolator.acquire()
        
        try:
            # Apply timeout
            if self._timeout_manager:
                result = await self._timeout_manager.execute_with_timeout(
                    self._execute_with_retry_and_circuit_breaker,
                    func,
                    *args,
                    **kwargs
                )
            else:
                result = await self._execute_with_retry_and_circuit_breaker(
                    func,
                    *args,
                    **kwargs
                )
            
            # Update metrics
            if self._config.enable_metrics:
                self._update_metrics("success", 1)
            
            return result
            
        except Exception as e:
            # Update metrics
            if self._config.enable_metrics:
                self._update_metrics("failure", 1)
                self._update_metrics(f"failure_{type(e).__name__}", 1)
            
            # Use fallback if available
            if self._config.fallback_func:
                return self._config.fallback_func()
            
            raise
        
        finally:
            # Release bulkhead
            if self._bulkhead_isolator:
                self._bulkhead_isolator.release()
    
    async def _execute_with_retry_and_circuit_breaker(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Execute function with retry and circuit breaker.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        # Check circuit breaker
        if self._circuit_breaker and self._circuit_breaker.state == CircuitState.OPEN:
            raise CircuitBreakerError("Circuit breaker is open")
        
        # Execute with retry if configured
        if self._retry_handler:
            return await self._retry_handler.execute_with_retry(
                self._execute_with_circuit_breaker,
                func,
                *args,
                **kwargs
            )
        else:
            return await self._execute_with_circuit_breaker(func, *args, **kwargs)
    
    async def _execute_with_circuit_breaker(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Execute function with circuit breaker.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        if self._circuit_breaker:
            return await self._circuit_breaker.execute(func, *args, **kwargs)
        else:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
    
    def _update_metrics(self, metric_name: str, value: Union[int, float]) -> None:
        """Update metrics.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
        """
        if metric_name not in self._metrics:
            self._metrics[metric_name] = 0
        self._metrics[metric_name] += value
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics.
        
        Returns:
            Current metrics
        """
        return self._metrics.copy()
    
    def reset_metrics(self) -> None:
        """Reset metrics."""
        self._metrics.clear()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status.
        
        Returns:
            Health status information
        """
        if self._health_checker:
            return self._health_checker.get_health_status()
        return {"status": "unknown", "message": "Health checker not configured"}
    
    def is_healthy(self) -> bool:
        """Check if system is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        if self._health_checker:
            return self._health_checker.is_healthy()
        return True


def fault_tolerance(
    config: FaultToleranceConfig
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for applying fault tolerance to functions.
    
    Args:
        config: Fault tolerance configuration
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        manager = FaultToleranceManager(config)
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs) -> T:
                return await manager.execute_with_fault_tolerance(func, *args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs) -> T:
                # For sync functions, we need to run in event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If we're in an async context, we can't use run_until_complete
                        # This is a limitation of the current implementation
                        raise RuntimeError("Cannot use fault tolerance decorator on sync functions in async context")
                    return loop.run_until_complete(
                        manager.execute_with_fault_tolerance(func, *args, **kwargs)
                    )
                except RuntimeError:
                    # No event loop, create one
                    return asyncio.run(
                        manager.execute_with_fault_tolerance(func, *args, **kwargs)
                    )
            return sync_wrapper
    
    return decorator


# Convenience functions for common patterns
def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for applying retry logic to functions.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff_multiplier: Backoff multiplier for delay
        max_delay: Maximum delay between retries
        jitter: Whether to add jitter to delays
        
    Returns:
        Decorated function
    """
    config = FaultToleranceConfig(
        strategy=FaultToleranceStrategy.RETRY_ONLY,
        retry_config=RetryConfig(
            max_attempts=max_attempts,
            delay=delay,
            backoff_multiplier=backoff_multiplier,
            max_delay=max_delay,
            jitter=jitter
        )
    )
    return fault_tolerance(config)


def with_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: type = Exception
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for applying circuit breaker to functions.
    
    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time to wait before attempting recovery
        expected_exception: Exception type to count as failures
        
    Returns:
        Decorated function
    """
    config = FaultToleranceConfig(
        strategy=FaultToleranceStrategy.CIRCUIT_BREAKER_ONLY,
        circuit_breaker_config={
            "failure_threshold": failure_threshold,
            "recovery_timeout": recovery_timeout,
            "expected_exception": expected_exception
        }
    )
    return fault_tolerance(config)


def with_timeout(timeout: float) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for applying timeout to functions.
    
    Args:
        timeout: Timeout in seconds
        
    Returns:
        Decorated function
    """
    config = FaultToleranceConfig(
        strategy=FaultToleranceStrategy.TIMEOUT_ONLY,
        timeout_config=TimeoutConfig(timeout=timeout)
    )
    return fault_tolerance(config)
