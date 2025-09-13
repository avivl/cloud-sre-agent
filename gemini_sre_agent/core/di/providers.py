"""Service provider implementations for dependency injection."""

from collections.abc import Callable
from typing import TypeVar

from .interfaces import ServiceLifetime, ServiceProvider

T = TypeVar("T")


class TypeProvider(ServiceProvider[T]):
    """Provider for type-based services."""

    def __init__(self, implementation_type: type[T], lifetime: ServiceLifetime):
        """Initialize the provider.

        Args:
            implementation_type: The implementation type
            lifetime: The service lifetime
        """
        self._implementation_type = implementation_type
        self._lifetime = lifetime

    def get_lifetime(self) -> ServiceLifetime:
        """Get the service lifetime.

        Returns:
            The service lifetime
        """
        return self._lifetime

    def get_service(self) -> T:
        """Get a service instance.

        Returns:
            A new service instance
        """
        return self._implementation_type()


class FactoryProvider(ServiceProvider[T]):
    """Provider for factory-based services."""

    def __init__(self, factory: Callable[[], T], lifetime: ServiceLifetime):
        """Initialize the provider.

        Args:
            factory: The factory function
            lifetime: The service lifetime
        """
        self._factory = factory
        self._lifetime = lifetime

    def get_lifetime(self) -> ServiceLifetime:
        """Get the service lifetime.

        Returns:
            The service lifetime
        """
        return self._lifetime

    def get_service(self) -> T:
        """Get a service instance.

        Returns:
            A new service instance from the factory
        """
        return self._factory()


class InstanceProvider(ServiceProvider[T]):
    """Provider for instance-based services."""

    def __init__(self, instance: T):
        """Initialize the provider.

        Args:
            instance: The service instance
        """
        self._instance = instance

    def get_lifetime(self) -> ServiceLifetime:
        """Get the service lifetime.

        Returns:
            Always returns SINGLETON for instances
        """
        return ServiceLifetime.SINGLETON

    def get_service(self) -> T:
        """Get the service instance.

        Returns:
            The stored instance
        """
        return self._instance


class LazyProvider(ServiceProvider[T]):
    """Provider for lazy-loaded services."""

    def __init__(self, factory: Callable[[], T], lifetime: ServiceLifetime):
        """Initialize the provider.

        Args:
            factory: The factory function
            lifetime: The service lifetime
        """
        self._factory = factory
        self._lifetime = lifetime
        self._instance: T | None = None
        self._initialized = False

    def get_lifetime(self) -> ServiceLifetime:
        """Get the service lifetime.

        Returns:
            The service lifetime
        """
        return self._lifetime

    def get_service(self) -> T:
        """Get a service instance.

        Returns:
            The lazy-loaded service instance
        """
        if not self._initialized:
            self._instance = self._factory()
            self._initialized = True

        return self._instance  # type: ignore


class CachedProvider(ServiceProvider[T]):
    """Provider that caches service instances."""

    def __init__(self, provider: ServiceProvider[T]):
        """Initialize the provider.

        Args:
            provider: The underlying provider
        """
        self._provider = provider
        self._cached_instance: T | None = None
        self._cached = False

    def get_lifetime(self) -> ServiceLifetime:
        """Get the service lifetime.

        Returns:
            The underlying provider's lifetime
        """
        return self._provider.get_lifetime()

    def get_service(self) -> T:
        """Get a service instance.

        Returns:
            The cached service instance
        """
        if not self._cached:
            self._cached_instance = self._provider.get_service()
            self._cached = True

        return self._cached_instance  # type: ignore


class ConditionalProvider(ServiceProvider[T]):
    """Provider that conditionally creates services."""

    def __init__(
        self,
        condition: Callable[[], bool],
        true_provider: ServiceProvider[T],
        false_provider: ServiceProvider[T],
    ):
        """Initialize the provider.

        Args:
            condition: The condition function
            true_provider: Provider to use when condition is True
            false_provider: Provider to use when condition is False
        """
        self._condition = condition
        self._true_provider = true_provider
        self._false_provider = false_provider

    def get_lifetime(self) -> ServiceLifetime:
        """Get the service lifetime.

        Returns:
            The lifetime of the active provider
        """
        if self._condition():
            return self._true_provider.get_lifetime()
        else:
            return self._false_provider.get_lifetime()

    def get_service(self) -> T:
        """Get a service instance.

        Returns:
            A service instance from the appropriate provider
        """
        if self._condition():
            return self._true_provider.get_service()
        else:
            return self._false_provider.get_service()


class DecoratorProvider(ServiceProvider[T]):
    """Provider that decorates another provider."""

    def __init__(self, provider: ServiceProvider[T], decorator: Callable[[T], T]):
        """Initialize the provider.

        Args:
            provider: The underlying provider
            decorator: The decorator function
        """
        self._provider = provider
        self._decorator = decorator

    def get_lifetime(self) -> ServiceLifetime:
        """Get the service lifetime.

        Returns:
            The underlying provider's lifetime
        """
        return self._provider.get_lifetime()

    def get_service(self) -> T:
        """Get a service instance.

        Returns:
            The decorated service instance
        """
        instance = self._provider.get_service()
        return self._decorator(instance)
