"""Main dependency injection container implementation."""

import inspect
import threading
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union

from .exceptions import (
    CircularDependencyError,
    ServiceNotFoundError,
    ServiceRegistrationError,
    ServiceResolutionError,
)
from .interfaces import (
    FactoryProvider,
    InstanceProvider,
    ServiceLifetime,
    ServiceProvider,
    ServiceRegistry,
    ServiceScope,
    TypeProvider,
)

T = TypeVar("T")


class DIContainer(ServiceRegistry):
    """Main dependency injection container."""

    def __init__(self):
        """Initialize the container."""
        self._services: Dict[Type, ServiceProvider] = {}
        self._singletons: Dict[Type, Any] = {}
        self._scopes: Dict[threading.Thread, ServiceScope] = {}
        self._lock = threading.RLock()

    def register(
        self,
        service_type: Type[T],
        implementation: Union[Type[T], Callable[[], T], T],
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ) -> None:
        """Register a service.

        Args:
            service_type: The service type to register
            implementation: The implementation (type, factory, or instance)
            lifetime: The service lifetime
        """
        with self._lock:
            try:
                if isinstance(implementation, type):
                    provider = TypeProvider(implementation, lifetime)
                elif callable(implementation):
                    provider = FactoryProvider(implementation, lifetime)
                else:
                    provider = InstanceProvider(implementation)

                self._services[service_type] = provider
            except Exception as e:
                raise ServiceRegistrationError(
                    service_type, f"Failed to register service: {str(e)}"
                ) from e

    def register_singleton(
        self, service_type: Type[T], implementation: Union[Type[T], Callable[[], T], T]
    ) -> None:
        """Register a singleton service.

        Args:
            service_type: The service type to register
            implementation: The implementation
        """
        self.register(service_type, implementation, ServiceLifetime.SINGLETON)

    def register_transient(
        self, service_type: Type[T], implementation: Union[Type[T], Callable[[], T], T]
    ) -> None:
        """Register a transient service.

        Args:
            service_type: The service type to register
            implementation: The implementation
        """
        self.register(service_type, implementation, ServiceLifetime.TRANSIENT)

    def register_scoped(
        self, service_type: Type[T], implementation: Union[Type[T], Callable[[], T], T]
    ) -> None:
        """Register a scoped service.

        Args:
            service_type: The service type to register
            implementation: The implementation
        """
        self.register(service_type, implementation, ServiceLifetime.SCOPED)

    def is_registered(self, service_type: Type[T]) -> bool:
        """Check if a service is registered.

        Args:
            service_type: The service type to check

        Returns:
            True if the service is registered, False otherwise
        """
        return service_type in self._services

    def get_provider(self, service_type: Type[T]) -> ServiceProvider[T]:
        """Get the service provider for a type.

        Args:
            service_type: The service type

        Returns:
            The service provider

        Raises:
            ServiceNotFoundError: If the service is not registered
        """
        if service_type not in self._services:
            raise ServiceNotFoundError(service_type)
        return self._services[service_type]

    def get_service(self, service_type: Type[T]) -> T:
        """Get a service instance.

        Args:
            service_type: The service type

        Returns:
            The service instance

        Raises:
            ServiceNotFoundError: If the service is not registered
            ServiceResolutionError: If the service cannot be resolved
        """
        try:
            provider = self.get_provider(service_type)

            if provider.get_lifetime() == ServiceLifetime.SCOPED:
                return self._get_scoped_service(service_type)

            if provider.get_lifetime() == ServiceLifetime.SINGLETON:
                if service_type not in self._singletons:
                    self._singletons[service_type] = provider.get_service()
                return self._singletons[service_type]

            return provider.get_service()
        except ServiceNotFoundError:
            raise
        except Exception as e:
            raise ServiceResolutionError(
                service_type, f"Failed to resolve service: {str(e)}"
            ) from e

    def create_scope(self) -> ServiceScope:
        """Create a new service scope.

        Returns:
            A new service scope
        """
        return DIContainerScope(self)

    def _get_scoped_service(self, service_type: Type[T]) -> T:
        """Get a scoped service.

        Args:
            service_type: The service type

        Returns:
            The scoped service instance
        """
        current_thread = threading.current_thread()
        if current_thread not in self._scopes:
            self._scopes[current_thread] = self.create_scope()

        return self._scopes[current_thread].get_service(service_type)

    def dispose(self) -> None:
        """Dispose of the container and all its services."""
        with self._lock:
            # Dispose of all scopes
            for scope in self._scopes.values():
                scope.dispose()
            self._scopes.clear()

            # Clear singletons
            self._singletons.clear()

            # Clear services
            self._services.clear()


class DIContainerScope(ServiceScope):
    """Service scope implementation."""

    def __init__(self, container: DIContainer):
        """Initialize the scope.

        Args:
            container: The parent container
        """
        self._container = container
        self._scoped_instances: Dict[Type, Any] = {}

    def get_service(self, service_type: Type[T]) -> T:
        """Get a service from the scope.

        Args:
            service_type: The service type

        Returns:
            The service instance
        """
        if service_type not in self._scoped_instances:
            provider = self._container.get_provider(service_type)
            self._scoped_instances[service_type] = provider.get_service()

        return self._scoped_instances[service_type]

    def dispose(self) -> None:
        """Dispose of the scope and its services."""
        # Dispose of scoped instances if they have a dispose method
        for instance in self._scoped_instances.values():
            if hasattr(instance, "dispose"):
                try:
                    instance.dispose()
                except Exception:
                    pass  # Ignore disposal errors

        self._scoped_instances.clear()


def resolve_dependencies(
    container: DIContainer,
    service_type: Type[T],
    dependency_chain: Optional[list[Type]] = None,
) -> T:
    """Resolve dependencies for a service type.

    Args:
        container: The DI container
        service_type: The service type to resolve
        dependency_chain: Current dependency chain for circular dependency detection

    Returns:
        The resolved service instance

    Raises:
        CircularDependencyError: If a circular dependency is detected
        ServiceResolutionError: If the service cannot be resolved
    """
    if dependency_chain is None:
        dependency_chain = []

    if service_type in dependency_chain:
        raise CircularDependencyError(dependency_chain + [service_type])

    # Check if service is registered
    if not container.is_registered(service_type):
        # Try to auto-register if it's a concrete type
        if not inspect.isabstract(service_type):
            container.register_transient(service_type, service_type)
        else:
            raise ServiceNotFoundError(service_type)

    # Get constructor parameters
    try:
        signature = inspect.signature(service_type.__init__)
        parameters = signature.parameters
    except (ValueError, TypeError):
        # No constructor or not callable
        return container.get_service(service_type)

    # Resolve constructor dependencies
    resolved_args = {}
    new_chain = dependency_chain + [service_type]

    for param_name, param in parameters.items():
        if param_name == "self":
            continue

        param_type = param.annotation
        if param_type == inspect.Parameter.empty:
            continue

        # Resolve the dependency
        try:
            resolved_args[param_name] = resolve_dependencies(
                container, param_type, new_chain
            )
        except ServiceNotFoundError:
            if param.default != inspect.Parameter.empty:
                continue  # Use default value
            raise

    # Create the service instance
    try:
        if resolved_args:
            return service_type(**resolved_args)
        else:
            return service_type()
    except Exception as e:
        raise ServiceResolutionError(
            service_type, f"Failed to create service instance: {str(e)}"
        ) from e


# Global container instance
_container: Optional[DIContainer] = None
_container_lock = threading.Lock()


def get_container() -> DIContainer:
    """Get the global container instance.

    Returns:
        The global container instance
    """
    global _container
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = DIContainer()
    return _container


def set_container(container: DIContainer) -> None:
    """Set the global container instance.

    Args:
        container: The container instance to set
    """
    global _container
    with _container_lock:
        _container = container


def clear_container() -> None:
    """Clear the global container instance."""
    global _container
    with _container_lock:
        if _container is not None:
            _container.dispose()
            _container = None
