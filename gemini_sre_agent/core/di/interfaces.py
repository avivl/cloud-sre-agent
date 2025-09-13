"""Interfaces for the dependency injection system."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from typing import Generic, TypeVar

T = TypeVar("T")


class ServiceLifetime(Enum):
    """Service lifetime enumeration."""

    TRANSIENT = "transient"
    SINGLETON = "singleton"
    SCOPED = "scoped"


class ServiceProvider(ABC, Generic[T]):
    """Abstract base class for service providers."""

    @abstractmethod
    def get_service(self) -> T:
        """Get the service instance."""
        pass

    @abstractmethod
    def get_lifetime(self) -> ServiceLifetime:
        """Get the service lifetime."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the service is available."""
        pass


class FactoryProvider(ServiceProvider[T]):
    """Factory-based service provider."""

    def __init__(
        self,
        factory: Callable[[], T],
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ):
        """Initialize the factory provider.

        Args:
            factory: Factory function to create service instances
            lifetime: Service lifetime
        """
        self._factory = factory
        self._lifetime = lifetime
        self._instance: T | None = None

    def get_service(self) -> T:
        """Get the service instance."""
        if self._lifetime == ServiceLifetime.TRANSIENT:
            return self._factory()

        if self._instance is None:
            self._instance = self._factory()

        return self._instance

    def get_lifetime(self) -> ServiceLifetime:
        """Get the service lifetime."""
        return self._lifetime

    def is_available(self) -> bool:
        """Check if the service is available."""
        try:
            self._factory()
            return True
        except Exception:
            return False


class InstanceProvider(ServiceProvider[T]):
    """Instance-based service provider."""

    def __init__(self, instance: T):
        """Initialize the instance provider.

        Args:
            instance: The service instance
        """
        self._instance = instance

    def get_service(self) -> T:
        """Get the service instance."""
        return self._instance

    def get_lifetime(self) -> ServiceLifetime:
        """Get the service lifetime."""
        return ServiceLifetime.SINGLETON

    def is_available(self) -> bool:
        """Check if the service is available."""
        return self._instance is not None


class TypeProvider(ServiceProvider[T]):
    """Type-based service provider."""

    def __init__(
        self,
        service_type: type[T],
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ):
        """Initialize the type provider.

        Args:
            service_type: The service type to instantiate
            lifetime: Service lifetime
        """
        self._service_type = service_type
        self._lifetime = lifetime
        self._instance: T | None = None

    def get_service(self) -> T:
        """Get the service instance."""
        if self._lifetime == ServiceLifetime.TRANSIENT:
            return self._service_type()

        if self._instance is None:
            self._instance = self._service_type()

        return self._instance

    def get_lifetime(self) -> ServiceLifetime:
        """Get the service lifetime."""
        return self._lifetime

    def is_available(self) -> bool:
        """Check if the service is available."""
        try:
            self._service_type()
            return True
        except Exception:
            return False


class ServiceScope(ABC):
    """Abstract base class for service scopes."""

    @abstractmethod
    def get_service(self, service_type: type[T]) -> T:
        """Get a service from the scope."""
        pass

    @abstractmethod
    def dispose(self) -> None:
        """Dispose of the scope and its services."""
        pass


class ServiceRegistry(ABC):
    """Abstract base class for service registries."""

    @abstractmethod
    def register(
        self,
        service_type: type[T],
        implementation: type[T] | Callable[[], T] | T,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ) -> None:
        """Register a service."""
        pass

    @abstractmethod
    def register_singleton(
        self, service_type: type[T], implementation: type[T] | Callable[[], T] | T
    ) -> None:
        """Register a singleton service."""
        pass

    @abstractmethod
    def register_transient(
        self, service_type: type[T], implementation: type[T] | Callable[[], T] | T
    ) -> None:
        """Register a transient service."""
        pass

    @abstractmethod
    def register_scoped(
        self, service_type: type[T], implementation: type[T] | Callable[[], T] | T
    ) -> None:
        """Register a scoped service."""
        pass

    @abstractmethod
    def is_registered(self, service_type: type[T]) -> bool:
        """Check if a service is registered."""
        pass

    @abstractmethod
    def get_provider(self, service_type: type[T]) -> ServiceProvider[T]:
        """Get the service provider for a type."""
        pass
