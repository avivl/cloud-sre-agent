# gemini_sre_agent/llm/service_manager.py

"""
Service Manager Module

This module provides the main service management and coordination functionality,
including service discovery, health monitoring, and load balancing.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from ..core.exceptions import ServiceError
from .service_base import BaseService, ServiceConfig, ServiceHealth, ServiceStatus
from .service_implementations import (
    CacheService,
    ContextService,
    MetricsService,
    ModelService,
    ValidationService,
)


class ServiceType(Enum):
    """Enumeration of available service types."""

    MODEL = "model"
    CONTEXT = "context"
    VALIDATION = "validation"
    METRICS = "metrics"
    CACHE = "cache"


class LoadBalancingStrategy(Enum):
    """Load balancing strategies for service selection."""

    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"
    RANDOM = "random"
    HEALTH_BASED = "health_based"


@dataclass
class ServiceMetrics:
    """Metrics for service performance monitoring."""

    service_id: str
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_response_time: float = 0.0
    last_request_time: Optional[datetime] = None
    health_score: float = 1.0
    uptime_percentage: float = 100.0
    error_rate: float = 0.0

    def update_metrics(self, success: bool, response_time: float) -> None:
        """Update service metrics with new request data."""
        self.request_count += 1
        if success:
            self.success_count += 1
        else:
            self.error_count += 1

        # Update average response time
        if self.request_count == 1:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (
                self.avg_response_time * (self.request_count - 1) + response_time
            ) / self.request_count

        self.last_request_time = datetime.now()
        self.error_rate = (
            self.error_count / self.request_count if self.request_count > 0 else 0.0
        )
        self.health_score = max(
            0.0, 1.0 - self.error_rate - (self.avg_response_time / 1000.0)
        )


@dataclass
class ServiceRegistry:
    """Registry for managing service instances and their configurations."""

    services: Dict[str, BaseService] = field(default_factory=dict)
    service_configs: Dict[str, ServiceConfig] = field(default_factory=dict)
    service_metrics: Dict[str, ServiceMetrics] = field(default_factory=dict)
    service_types: Dict[str, ServiceType] = field(default_factory=dict)

    def register_service(
        self,
        service_id: str,
        service: BaseService,
        config: ServiceConfig,
        service_type: ServiceType,
    ) -> None:
        """Register a new service in the registry."""
        self.services[service_id] = service
        self.service_configs[service_id] = config
        self.service_metrics[service_id] = ServiceMetrics(service_id=service_id)
        self.service_types[service_id] = service_type

    def get_service(self, service_id: str) -> Optional[BaseService]:
        """Get a service by ID."""
        return self.services.get(service_id)

    def get_services_by_type(self, service_type: ServiceType) -> List[BaseService]:
        """Get all services of a specific type."""
        return [
            service
            for service_id, service in self.services.items()
            if self.service_types.get(service_id) == service_type
        ]

    def unregister_service(self, service_id: str) -> bool:
        """Unregister a service from the registry."""
        if service_id in self.services:
            del self.services[service_id]
            del self.service_configs[service_id]
            del self.service_metrics[service_id]
            del self.service_types[service_id]
            return True
        return False


class ServiceHealthChecker:
    """Health checker for monitoring service status."""

    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.health_checks: Dict[str, asyncio.Task] = {}
        self.logger = logging.getLogger(__name__)

    async def start_health_monitoring(self, registry: ServiceRegistry) -> None:
        """Start health monitoring for all registered services."""
        for service_id in registry.services:
            task = asyncio.create_task(
                self._monitor_service_health(service_id, registry)
            )
            self.health_checks[service_id] = task

    async def stop_health_monitoring(self) -> None:
        """Stop all health monitoring tasks."""
        for task in self.health_checks.values():
            task.cancel()
        await asyncio.gather(*self.health_checks.values(), return_exceptions=True)
        self.health_checks.clear()

    async def _monitor_service_health(
        self, service_id: str, registry: ServiceRegistry
    ) -> None:
        """Monitor health of a specific service."""
        while True:
            try:
                service = registry.get_service(service_id)
                if service:
                    health = await service.check_health()
                    registry.service_metrics[service_id].health_score = health.score

                    if health.status != ServiceStatus.HEALTHY:
                        self.logger.warning(
                            f"Service {service_id} is unhealthy: {health.status}"
                        )
                else:
                    self.logger.error(f"Service {service_id} not found in registry")

                await asyncio.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Health check failed for {service_id}: {e}")
                await asyncio.sleep(self.check_interval)


class LoadBalancer:
    """Load balancer for distributing requests across services."""

    def __init__(
        self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    ):
        self.strategy = strategy
        self.current_index = 0
        self.logger = logging.getLogger(__name__)

    def select_service(
        self, services: List[BaseService], registry: ServiceRegistry
    ) -> Optional[BaseService]:
        """Select a service based on the load balancing strategy."""
        if not services:
            return None

        healthy_services = [
            service
            for service in services
            if registry.service_metrics.get(
                service.service_id, ServiceMetrics(service_id="")
            ).health_score
            > 0.5
        ]

        if not healthy_services:
            self.logger.warning("No healthy services available")
            return services[0]  # Fallback to first available service

        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._round_robin_selection(healthy_services)
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._least_connections_selection(healthy_services, registry)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED:
            return self._weighted_selection(healthy_services, registry)
        elif self.strategy == LoadBalancingStrategy.RANDOM:
            return self._random_selection(healthy_services)
        elif self.strategy == LoadBalancingStrategy.HEALTH_BASED:
            return self._health_based_selection(healthy_services, registry)
        else:
            return healthy_services[0]

    def _round_robin_selection(self, services: List[BaseService]) -> BaseService:
        """Select service using round-robin strategy."""
        service = services[self.current_index % len(services)]
        self.current_index += 1
        return service

    def _least_connections_selection(
        self, services: List[BaseService], registry: ServiceRegistry
    ) -> BaseService:
        """Select service with least active connections."""
        return min(
            services,
            key=lambda s: registry.service_metrics.get(
                s.service_id, ServiceMetrics(service_id="")
            ).request_count,
        )

    def _weighted_selection(
        self, services: List[BaseService], registry: ServiceRegistry
    ) -> BaseService:
        """Select service based on weighted health score."""
        weights = [
            registry.service_metrics.get(
                s.service_id, ServiceMetrics(service_id="")
            ).health_score
            for s in services
        ]
        total_weight = sum(weights)
        if total_weight == 0:
            return services[0]

        # Simple weighted selection
        import random

        rand = random.uniform(0, total_weight)
        cumulative = 0
        for i, weight in enumerate(weights):
            cumulative += weight
            if rand <= cumulative:
                return services[i]
        return services[-1]

    def _random_selection(self, services: List[BaseService]) -> BaseService:
        """Select service randomly."""
        import random

        return random.choice(services)

    def _health_based_selection(
        self, services: List[BaseService], registry: ServiceRegistry
    ) -> BaseService:
        """Select service with highest health score."""
        return max(
            services,
            key=lambda s: registry.service_metrics.get(
                s.service_id, ServiceMetrics(service_id="")
            ).health_score,
        )


class ServiceManager:
    """Main service manager for orchestrating all service operations."""

    def __init__(
        self,
        load_balancing_strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
        health_check_interval: int = 30,
    ):
        self.registry = ServiceRegistry()
        self.load_balancer = LoadBalancer(load_balancing_strategy)
        self.health_checker = ServiceHealthChecker(health_check_interval)
        self.logger = logging.getLogger(__name__)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the service manager and start health monitoring."""
        if self._initialized:
            return

        try:
            # Register default services
            await self._register_default_services()

            # Start health monitoring
            await self.health_checker.start_health_monitoring(self.registry)

            self._initialized = True
            self.logger.info("Service manager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize service manager: {e}")
            raise ServiceError(f"Service manager initialization failed: {e}")

    async def shutdown(self) -> None:
        """Shutdown the service manager and all services."""
        try:
            # Stop health monitoring
            await self.health_checker.stop_health_monitoring()

            # Shutdown all services
            for service in self.registry.services.values():
                await service.shutdown()

            self.registry = ServiceRegistry()
            self._initialized = False
            self.logger.info("Service manager shutdown completed")
        except Exception as e:
            self.logger.error(f"Error during service manager shutdown: {e}")

    async def _register_default_services(self) -> None:
        """Register default service implementations."""
        # Model Service
        model_config = ServiceConfig(
            service_id="model_service",
            max_connections=100,
            timeout_seconds=30,
            retry_attempts=3,
        )
        model_service = ModelService(model_config)
        await model_service.initialize()
        self.registry.register_service(
            "model_service", model_service, model_config, ServiceType.MODEL
        )

        # Context Service
        context_config = ServiceConfig(
            service_id="context_service",
            max_connections=50,
            timeout_seconds=15,
            retry_attempts=2,
        )
        context_service = ContextService(context_config)
        await context_service.initialize()
        self.registry.register_service(
            "context_service", context_service, context_config, ServiceType.CONTEXT
        )

        # Validation Service
        validation_config = ServiceConfig(
            service_id="validation_service",
            max_connections=75,
            timeout_seconds=20,
            retry_attempts=2,
        )
        validation_service = ValidationService(validation_config)
        await validation_service.initialize()
        self.registry.register_service(
            "validation_service",
            validation_service,
            validation_config,
            ServiceType.VALIDATION,
        )

        # Metrics Service
        metrics_config = ServiceConfig(
            service_id="metrics_service",
            max_connections=25,
            timeout_seconds=10,
            retry_attempts=1,
        )
        metrics_service = MetricsService(metrics_config)
        await metrics_service.initialize()
        self.registry.register_service(
            "metrics_service", metrics_service, metrics_config, ServiceType.METRICS
        )

        # Cache Service
        cache_config = ServiceConfig(
            service_id="cache_service",
            max_connections=200,
            timeout_seconds=5,
            retry_attempts=1,
        )
        cache_service = CacheService(cache_config)
        await cache_service.initialize()
        self.registry.register_service(
            "cache_service", cache_service, cache_config, ServiceType.CACHE
        )

    async def get_service(
        self, service_type: ServiceType, service_id: Optional[str] = None
    ) -> Optional[BaseService]:
        """Get a service by type and optionally by ID."""
        if service_id:
            service = self.registry.get_service(service_id)
            if service and self.registry.service_types.get(service_id) == service_type:
                return service
            return None

        services = self.registry.get_services_by_type(service_type)
        if not services:
            return None

        return self.load_balancer.select_service(services, self.registry)

    async def register_custom_service(
        self,
        service_id: str,
        service: BaseService,
        config: ServiceConfig,
        service_type: ServiceType,
    ) -> None:
        """Register a custom service."""
        await service.initialize()
        self.registry.register_service(service_id, service, config, service_type)
        self.logger.info(f"Registered custom service: {service_id}")

    async def unregister_service(self, service_id: str) -> bool:
        """Unregister a service."""
        service = self.registry.get_service(service_id)
        if service:
            await service.shutdown()

        success = self.registry.unregister_service(service_id)
        if success:
            self.logger.info(f"Unregistered service: {service_id}")
        return success

    def get_service_metrics(self, service_id: str) -> Optional[ServiceMetrics]:
        """Get metrics for a specific service."""
        return self.registry.service_metrics.get(service_id)

    def get_all_metrics(self) -> Dict[str, ServiceMetrics]:
        """Get metrics for all services."""
        return self.registry.service_metrics.copy()

    def get_service_health(self, service_id: str) -> Optional[ServiceHealth]:
        """Get health status for a specific service."""
        service = self.registry.get_service(service_id)
        if not service:
            return None

        metrics = self.registry.service_metrics.get(service_id)
        if not metrics:
            return ServiceHealth(
                status=ServiceStatus.UNKNOWN, score=0.0, message="No metrics available"
            )

        if metrics.health_score > 0.8:
            status = ServiceStatus.HEALTHY
        elif metrics.health_score > 0.5:
            status = ServiceStatus.DEGRADED
        else:
            status = ServiceStatus.UNHEALTHY

        return ServiceHealth(
            status=status,
            score=metrics.health_score,
            message=f"Health score: {metrics.health_score:.2f}",
        )

    async def execute_service_request(
        self,
        service_type: ServiceType,
        request_data: Dict[str, Any],
        service_id: Optional[str] = None,
    ) -> Any:
        """Execute a request through the appropriate service."""
        service = await self.get_service(service_type, service_id)
        if not service:
            raise ServiceError(f"No available service of type {service_type}")

        start_time = datetime.now()
        success = False

        try:
            result = await service.process_request(request_data)
            success = True
            return result
        except Exception as e:
            self.logger.error(f"Service request failed: {e}")
            raise
        finally:
            # Update metrics
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            metrics = self.registry.service_metrics.get(service.service_id)
            if metrics:
                metrics.update_metrics(success, response_time)


# Factory function for creating service manager instances
def create_service_manager(
    load_balancing_strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
    health_check_interval: int = 30,
) -> ServiceManager:
    """Create a new service manager instance."""
    return ServiceManager(load_balancing_strategy, health_check_interval)
