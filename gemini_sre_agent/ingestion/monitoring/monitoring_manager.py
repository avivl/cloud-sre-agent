"""
Monitoring Manager - Centralized monitoring and observability system.

This module provides a unified interface for all monitoring capabilities:
- Metrics collection and reporting
- Health checking and status monitoring
- Performance monitoring and bottleneck detection
- Alerting and notification management
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

from .metrics import MetricsCollector, get_global_metrics
from .health import HealthChecker, get_global_health_checker
from .performance import PerformanceMonitor, get_global_performance_monitor
from .alerts import AlertManager, get_global_alert_manager, AlertLevel

logger = logging.getLogger(__name__)


@dataclass
class MonitoringConfig:
    """Configuration for the monitoring system."""
    enable_metrics: bool = True
    enable_health_checks: bool = True
    enable_performance_monitoring: bool = True
    enable_alerting: bool = True
    
    # Metrics configuration
    metrics_retention_hours: int = 24
    metrics_export_interval_seconds: int = 60
    
    # Health check configuration
    health_check_interval_seconds: int = 30
    
    # Performance monitoring configuration
    performance_window_size: int = 1000
    performance_update_interval_seconds: int = 10
    
    # Alerting configuration
    alert_evaluation_interval_seconds: int = 30
    alert_cleanup_interval_hours: int = 1


class MonitoringManager:
    """
    Centralized monitoring and observability manager.
    
    Orchestrates all monitoring components:
    - Metrics collection and aggregation
    - Health checking and status reporting
    - Performance monitoring and analysis
    - Alerting and notification management
    """
    
    def __init__(self, config: Optional[MonitoringConfig] = None):
        """
        Initialize the monitoring manager.
        
        Args:
            config: Monitoring configuration
        """
        self.config = config or MonitoringConfig()
        
        # Initialize monitoring components
        self.metrics_collector: Optional[MetricsCollector] = None
        self.health_checker: Optional[HealthChecker] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None
        self.alert_manager: Optional[AlertManager] = None
        
        self._running = False
        self._startup_task: Optional[asyncio.Task] = None
        
        logger.info("MonitoringManager initialized")
    
    async def start(self) -> None:
        """Start all monitoring components."""
        if self._running:
            return
        
        self._running = True
        self._startup_task = asyncio.create_task(self._startup_components())
        
        try:
            await self._startup_task
        except Exception as e:
            logger.error(f"Failed to start monitoring components: {e}")
            await self.stop()
            raise
        
        logger.info("MonitoringManager started")
    
    async def stop(self) -> None:
        """Stop all monitoring components."""
        self._running = False
        
        if self._startup_task:
            self._startup_task.cancel()
            try:
                await self._startup_task
            except asyncio.CancelledError:
                pass
        
        # Stop all components
        stop_tasks = []
        
        if self.metrics_collector:
            stop_tasks.append(self.metrics_collector.stop())
        if self.health_checker:
            stop_tasks.append(self.health_checker.stop())
        if self.performance_monitor:
            stop_tasks.append(self.performance_monitor.stop())
        if self.alert_manager:
            stop_tasks.append(self.alert_manager.stop())
        
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        logger.info("MonitoringManager stopped")
    
    async def _startup_components(self) -> None:
        """Startup all monitoring components."""
        startup_tasks = []
        
        # Initialize and start metrics collector
        if self.config.enable_metrics:
            self.metrics_collector = MetricsCollector()
            set_global_metrics(self.metrics_collector)
            startup_tasks.append(self.metrics_collector.start())
        
        # Initialize and start health checker
        if self.config.enable_health_checks:
            self.health_checker = HealthChecker()
            set_global_health_checker(self.health_checker)
            startup_tasks.append(self.health_checker.start())
        
        # Initialize and start performance monitor
        if self.config.enable_performance_monitoring:
            self.performance_monitor = PerformanceMonitor()
            set_global_performance_monitor(self.performance_monitor)
            startup_tasks.append(self.performance_monitor.start())
        
        # Initialize and start alert manager
        if self.config.enable_alerting:
            self.alert_manager = AlertManager()
            set_global_alert_manager(self.alert_manager)
            startup_tasks.append(self.alert_manager.start())
        
        # Start all components concurrently
        if startup_tasks:
            await asyncio.gather(*startup_tasks)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        if not self.metrics_collector:
            return {"error": "Metrics collection not enabled"}
        
        return self.metrics_collector.get_metrics_summary()
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary."""
        if not self.health_checker:
            return {"error": "Health checking not enabled"}
        
        return self.health_checker.get_health_summary()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        if not self.performance_monitor:
            return {"error": "Performance monitoring not enabled"}
        
        return self.performance_monitor.get_performance_summary()
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get comprehensive alert summary."""
        if not self.alert_manager:
            return {"error": "Alerting not enabled"}
        
        return self.alert_manager.get_alert_summary()
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status including all monitoring data.
        
        Returns:
            Dictionary with complete system status
        """
        status = {
            "timestamp": datetime.now().isoformat(),
            "monitoring_enabled": self._running,
            "config": {
                "metrics_enabled": self.config.enable_metrics,
                "health_checks_enabled": self.config.enable_health_checks,
                "performance_monitoring_enabled": self.config.enable_performance_monitoring,
                "alerting_enabled": self.config.enable_alerting
            }
        }
        
        # Add component summaries
        if self.config.enable_metrics:
            status["metrics"] = self.get_metrics_summary()
        
        if self.config.enable_health_checks:
            status["health"] = self.get_health_summary()
        
        if self.config.enable_performance_monitoring:
            status["performance"] = self.get_performance_summary()
        
        if self.config.enable_alerting:
            status["alerts"] = self.get_alert_summary()
        
        return status
    
    async def register_component_health_check(self, name: str, check_func) -> None:
        """Register a health check for a component."""
        if self.health_checker:
            await self.health_checker.register_health_check(name, check_func)
        else:
            logger.warning("Health checking not enabled, cannot register health check")
    
    def record_operation_metrics(
        self,
        component: str,
        operation: str,
        duration_ms: float,
        success: bool = True,
        bytes_processed: int = 0
    ) -> None:
        """Record operation metrics."""
        if self.performance_monitor:
            self.performance_monitor.record_operation(
                component=component,
                operation=operation,
                duration_ms=duration_ms,
                success=success,
                bytes_processed=bytes_processed
            )
        
        # Also record in metrics collector
        if self.metrics_collector:
            if success:
                self.metrics_collector.increment_counter(
                    f"{component}_{operation}_success_total"
                )
            else:
                self.metrics_collector.increment_counter(
                    f"{component}_{operation}_failure_total"
                )
            
            self.metrics_collector.record_histogram(
                f"{component}_{operation}_duration_seconds",
                value=duration_ms / 1000.0,
                labels={"component": component, "operation": operation}
            )
    
    async def create_alert(
        self,
        title: str,
        message: str,
        level: AlertLevel,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """Create an alert."""
        if self.alert_manager:
            return await self.alert_manager.create_alert(
                title=title,
                message=message,
                level=level,
                source=source,
                metadata=metadata
            )
        else:
            logger.warning("Alerting not enabled, cannot create alert")
            return None
    
    def get_bottlenecks(self, threshold_ms: float = 1000.0) -> List[Dict[str, Any]]:
        """Get performance bottlenecks."""
        if self.performance_monitor:
            return self.performance_monitor.get_bottlenecks(threshold_ms)
        return []
    
    def get_active_alerts(self) -> List[Any]:
        """Get active alerts."""
        if self.alert_manager:
            return self.alert_manager.get_active_alerts()
        return []


# Global monitoring manager instance
_global_monitoring_manager: Optional[MonitoringManager] = None


def get_global_monitoring_manager() -> MonitoringManager:
    """Get the global monitoring manager instance."""
    global _global_monitoring_manager
    if _global_monitoring_manager is None:
        _global_monitoring_manager = MonitoringManager()
    return _global_monitoring_manager


def set_global_monitoring_manager(manager: MonitoringManager) -> None:
    """Set the global monitoring manager instance."""
    global _global_monitoring_manager
    _global_monitoring_manager = manager


# Convenience functions for common monitoring operations
async def start_monitoring(config: Optional[MonitoringConfig] = None) -> MonitoringManager:
    """Start the global monitoring system."""
    manager = MonitoringManager(config)
    set_global_monitoring_manager(manager)
    await manager.start()
    return manager


async def stop_monitoring() -> None:
    """Stop the global monitoring system."""
    manager = get_global_monitoring_manager()
    if manager:
        await manager.stop()


def get_system_status() -> Dict[str, Any]:
    """Get comprehensive system status."""
    manager = get_global_monitoring_manager()
    if manager:
        return manager.get_comprehensive_status()
    return {"error": "Monitoring not initialized"}


async def record_component_operation(
    component: str,
    operation: str,
    duration_ms: float,
    success: bool = True,
    bytes_processed: int = 0
) -> None:
    """Record a component operation."""
    manager = get_global_monitoring_manager()
    if manager:
        manager.record_operation_metrics(
            component=component,
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            bytes_processed=bytes_processed
        )


async def create_system_alert(
    title: str,
    message: str,
    level: AlertLevel = AlertLevel.WARNING,
    source: str = "system"
) -> Optional[Any]:
    """Create a system alert."""
    manager = get_global_monitoring_manager()
    if manager:
        return await manager.create_alert(
            title=title,
            message=message,
            level=level,
            source=source
        )
    return None
