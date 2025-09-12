"""Decorators for dependency injection."""

import functools
import inspect
from typing import Any, Callable, Optional, Type, TypeVar, get_type_hints

from .container import get_container

T = TypeVar("T")


def injectable(
    service_type: Optional[Type[T]] = None, lifetime: Optional[str] = None
) -> Callable[[Type[T]], Type[T]]:
    """Decorator to mark a class as injectable.

    Args:
        service_type: The service type (defaults to the class itself)
        lifetime: The service lifetime ('singleton', 'transient', 'scoped')

    Returns:
        The decorated class
    """

    def decorator(cls: Type[T]) -> Type[T]:
        # Register the service
        container = get_container()
        if service_type is None:
            service_type_to_register = cls
        else:
            service_type_to_register = service_type

        if lifetime == "singleton":
            container.register_singleton(service_type_to_register, cls)
        elif lifetime == "scoped":
            container.register_scoped(service_type_to_register, cls)
        else:
            container.register_transient(service_type_to_register, cls)

        return cls

    return decorator


def inject(
    service_type: Optional[Type[T]] = None, name: Optional[str] = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to inject dependencies into a function or method.

    Args:
        service_type: The service type to inject
        name: Optional parameter name for the injection

    Returns:
        The injected service
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get the container
            container = get_container()

            # Get type hints
            hints = get_type_hints(func)

            # Resolve dependencies
            resolved_kwargs = {}
            for param_name, param_type in hints.items():
                if param_name in kwargs:
                    continue  # Already provided

                if service_type is not None and param_type == service_type:
                    resolved_kwargs[param_name] = container.get_service(service_type)
                elif service_type is None and param_type != inspect.Parameter.empty:
                    try:
                        resolved_kwargs[param_name] = container.get_service(param_type)
                    except Exception:
                        continue  # Skip if not registered

            # Call the function with resolved dependencies
            return func(*args, **{**kwargs, **resolved_kwargs})

        return wrapper

    return decorator


def auto_inject(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to automatically inject all dependencies.

    Args:
        func: The function to decorate

    Returns:
        The decorated function
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Get the container
        container = get_container()

        # Get type hints
        hints = get_type_hints(func)

        # Resolve all dependencies
        resolved_kwargs = {}
        for param_name, param_type in hints.items():
            if param_name in kwargs:
                continue  # Already provided

            if param_type != inspect.Parameter.empty:
                try:
                    resolved_kwargs[param_name] = container.get_service(param_type)
                except Exception:
                    continue  # Skip if not registered

        # Call the function with resolved dependencies
        return func(*args, **{**kwargs, **resolved_kwargs})

    return wrapper


def singleton(cls: Type[T]) -> Type[T]:
    """Decorator to register a class as a singleton.

    Args:
        cls: The class to register

    Returns:
        The decorated class
    """
    container = get_container()
    container.register_singleton(cls, cls)
    return cls


def transient(cls: Type[T]) -> Type[T]:
    """Decorator to register a class as transient.

    Args:
        cls: The class to register

    Returns:
        The decorated class
    """
    container = get_container()
    container.register_transient(cls, cls)
    return cls


def scoped(cls: Type[T]) -> Type[T]:
    """Decorator to register a class as scoped.

    Args:
        cls: The class to register

    Returns:
        The decorated class
    """
    container = get_container()
    container.register_scoped(cls, cls)
    return cls


def factory(func: Callable[[], T]) -> Callable[[], T]:
    """Decorator to register a function as a factory.

    Args:
        func: The factory function

    Returns:
        The decorated function
    """
    container = get_container()

    # Try to infer the return type
    hints = get_type_hints(func)
    return_type = hints.get("return", type(None))

    if return_type != type(None):
        container.register_transient(return_type, func)

    return func


def instance(value: T) -> T:
    """Decorator to register an instance.

    Args:
        value: The instance to register

    Returns:
        The registered instance
    """
    container = get_container()
    container.register_singleton(type(value), value)
    return value


class ServiceLocator:
    """Service locator pattern implementation."""

    def __init__(self, container=None):
        """Initialize the service locator.

        Args:
            container: The DI container to use
        """
        self._container = container or get_container()

    def get_service(self, service_type: Type[T]) -> T:
        """Get a service.

        Args:
            service_type: The service type

        Returns:
            The service instance
        """
        return self._container.get_service(service_type)

    def get_services(self, service_type: Type[T]) -> list[T]:
        """Get all services of a type.

        Args:
            service_type: The service type

        Returns:
            List of service instances
        """
        # This would require a more complex implementation
        # to support multiple registrations of the same type
        return [self._container.get_service(service_type)]


# Global service locator
_service_locator: Optional[ServiceLocator] = None


def get_service_locator() -> ServiceLocator:
    """Get the global service locator.

    Returns:
        The global service locator
    """
    global _service_locator
    if _service_locator is None:
        _service_locator = ServiceLocator()
    return _service_locator


def set_service_locator(locator: ServiceLocator) -> None:
    """Set the global service locator.

    Args:
        locator: The service locator to set
    """
    global _service_locator
    _service_locator = locator
