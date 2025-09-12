"""Health checker implementation for fault tolerance."""

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .exceptions import HealthCheckError, UnhealthyError


class HealthStatus(Enum):
    """Health status levels."""
    
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check definition.
    
    Attributes:
        name: Name of the health check
        check_func: Function to perform the health check
        timeout: Timeout for the health check
        interval: Interval between health checks
        enabled: Whether the health check is enabled
        critical: Whether the health check is critical
        metadata: Additional metadata for the health check
    """
    
    name: str
    check_func: Callable[[], bool]
    timeout: float = 30.0
    interval: float = 60.0
    enabled: bool = True
    critical: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """Health checker implementation for fault tolerance.
    
    Monitors system health through various health checks
    and provides health status information.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the health checker.
        
        Args:
            config: Health checker configuration
        """
        self._config = config or {}
        self._lock = threading.RLock()
        self._health_checks: Dict[str, HealthCheck] = {}
        self._health_status: Dict[str, HealthStatus] = {}
        self._last_check_time: Dict[str, float] = {}
        self._check_results: Dict[str, Dict[str, Any]] = {}
        self._health_history: list[Dict[str, Any]] = []
        self._max_history = 1000
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
    
    def add_health_check(self, health_check: HealthCheck) -> None:
        """Add a health check.
        
        Args:
            health_check: Health check to add
        """
        with self._lock:
            self._health_checks[health_check.name] = health_check
            self._health_status[health_check.name] = HealthStatus.UNKNOWN
            self._last_check_time[health_check.name] = 0.0
            self._check_results[health_check.name] = {}
    
    def remove_health_check(self, name: str) -> None:
        """Remove a health check.
        
        Args:
            name: Name of the health check to remove
        """
        with self._lock:
            self._health_checks.pop(name, None)
            self._health_status.pop(name, None)
            self._last_check_time.pop(name, None)
            self._check_results.pop(name, None)
    
    def check_health(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Check health of specific check or all checks.
        
        Args:
            name: Name of specific health check, or None for all
            
        Returns:
            Health check results
        """
        if name:
            return self._check_single_health(name)
        else:
            return self._check_all_health()
    
    def _check_single_health(self, name: str) -> Dict[str, Any]:
        """Check health of a single health check.
        
        Args:
            name: Name of the health check
            
        Returns:
            Health check result
        """
        if name not in self._health_checks:
            return {
                "name": name,
                "status": HealthStatus.UNKNOWN.value,
                "error": "Health check not found",
                "timestamp": time.time()
            }
        
        health_check = self._health_checks[name]
        
        if not health_check.enabled:
            return {
                "name": name,
                "status": HealthStatus.UNKNOWN.value,
                "error": "Health check disabled",
                "timestamp": time.time()
            }
        
        try:
            # Perform health check with timeout
            start_time = time.time()
            result = self._execute_health_check(health_check)
            duration = time.time() - start_time
            
            # Update status
            with self._lock:
                self._health_status[name] = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                self._last_check_time[name] = time.time()
                self._check_results[name] = {
                    "result": result,
                    "duration": duration,
                    "timestamp": time.time(),
                    "error": None
                }
            
            # Record in history
            self._record_health_check(name, result, duration, None)
            
            return {
                "name": name,
                "status": self._health_status[name].value,
                "result": result,
                "duration": duration,
                "timestamp": time.time(),
                "metadata": health_check.metadata
            }
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Update status
            with self._lock:
                self._health_status[name] = HealthStatus.UNHEALTHY
                self._last_check_time[name] = time.time()
                self._check_results[name] = {
                    "result": False,
                    "duration": duration,
                    "timestamp": time.time(),
                    "error": str(e)
                }
            
            # Record in history
            self._record_health_check(name, False, duration, str(e))
            
            return {
                "name": name,
                "status": HealthStatus.UNHEALTHY.value,
                "result": False,
                "duration": duration,
                "timestamp": time.time(),
                "error": str(e),
                "metadata": health_check.metadata
            }
    
    def _check_all_health(self) -> Dict[str, Any]:
        """Check health of all health checks.
        
        Returns:
            Overall health status and individual check results
        """
        overall_status = HealthStatus.HEALTHY
        check_results = {}
        critical_failures = 0
        
        for name in self._health_checks:
            result = self._check_single_health(name)
            check_results[name] = result
            
            if result["status"] == HealthStatus.UNHEALTHY.value:
                if self._health_checks[name].critical:
                    critical_failures += 1
                    overall_status = HealthStatus.UNHEALTHY
                elif overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
        
        return {
            "overall_status": overall_status.value,
            "critical_failures": critical_failures,
            "total_checks": len(self._health_checks),
            "check_results": check_results,
            "timestamp": time.time()
        }
    
    def _execute_health_check(self, health_check: HealthCheck) -> bool:
        """Execute a health check with timeout.
        
        Args:
            health_check: Health check to execute
            
        Returns:
            Health check result
        """
        # Simple timeout implementation
        # In production, use proper timeout mechanism
        try:
            return health_check.check_func()
        except Exception:
            return False
    
    def _record_health_check(
        self,
        name: str,
        result: bool,
        duration: float,
        error: Optional[str]
    ) -> None:
        """Record a health check result.
        
        Args:
            name: Name of the health check
            result: Health check result
            duration: Duration of the check
            error: Error message if check failed
        """
        with self._lock:
            health_record = {
                "name": name,
                "result": result,
                "duration": duration,
                "error": error,
                "timestamp": time.time(),
                "status": self._health_status[name].value
            }
            
            self._health_history.append(health_record)
            
            # Trim history if needed
            if len(self._health_history) > self._max_history:
                self._health_history = self._health_history[-self._max_history:]
    
    def start_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return
        
        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self._monitoring_thread.daemon = True
        self._monitoring_thread.start()
    
    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._stop_monitoring.set()
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5.0)
    
    def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                # Check all health checks
                for name, health_check in self._health_checks.items():
                    if not health_check.enabled:
                        continue
                    
                    # Check if it's time for this health check
                    current_time = time.time()
                    last_check = self._last_check_time.get(name, 0.0)
                    
                    if current_time - last_check >= health_check.interval:
                        self._check_single_health(name)
                
                # Sleep for a short interval
                time.sleep(1.0)
                
            except Exception:
                # Continue monitoring even if individual checks fail
                pass
    
    def get_health_status(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Get current health status.
        
        Args:
            name: Name of specific health check, or None for all
            
        Returns:
            Health status information
        """
        if name:
            return {
                "name": name,
                "status": self._health_status.get(name, HealthStatus.UNKNOWN).value,
                "last_check": self._last_check_time.get(name, 0.0),
                "result": self._check_results.get(name, {})
            }
        else:
            return {
                "overall_status": self._get_overall_status().value,
                "health_checks": {
                    name: {
                        "status": status.value,
                        "last_check": self._last_check_time.get(name, 0.0),
                        "result": self._check_results.get(name, {})
                    }
                    for name, status in self._health_status.items()
                }
            }
    
    def _get_overall_status(self) -> HealthStatus:
        """Get overall health status.
        
        Returns:
            Overall health status
        """
        if not self._health_status:
            return HealthStatus.UNKNOWN
        
        critical_failures = 0
        for name, status in self._health_status.items():
            if status == HealthStatus.UNHEALTHY and self._health_checks[name].critical:
                critical_failures += 1
        
        if critical_failures > 0:
            return HealthStatus.UNHEALTHY
        
        unhealthy_count = sum(1 for status in self._health_status.values() if status == HealthStatus.UNHEALTHY)
        if unhealthy_count > 0:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY
    
    def get_health_history(self, limit: Optional[int] = None) -> list[Dict[str, Any]]:
        """Get health check history.
        
        Args:
            limit: Optional limit on number of records to return
            
        Returns:
            List of health check records
        """
        with self._lock:
            if limit is None:
                return self._health_history.copy()
            return self._health_history[-limit:]
    
    def is_healthy(self, name: Optional[str] = None) -> bool:
        """Check if system is healthy.
        
        Args:
            name: Name of specific health check, or None for overall
            
        Returns:
            True if healthy, False otherwise
        """
        if name:
            return self._health_status.get(name, HealthStatus.UNKNOWN) == HealthStatus.HEALTHY
        else:
            return self._get_overall_status() == HealthStatus.HEALTHY
    
    def reset(self) -> None:
        """Reset the health checker.
        
        Clears all history and resets status.
        """
        with self._lock:
            self._health_status.clear()
            self._last_check_time.clear()
            self._check_results.clear()
            self._health_history.clear()
    
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
        self.stop_monitoring()
