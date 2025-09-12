"""Dependency injection system for the Gemini SRE Agent.

This module provides a comprehensive dependency injection system that supports:
- Service registration with different lifetimes (singleton, transient, scoped)
- Automatic dependency resolution
- Circular dependency detection
- Service scopes
- Decorators for easy service registration and injection
- Factory pattern support
- Service locator pattern

The main components are:
- DIContainer: The main container for service registration and resolution
- ServiceProvider: Interface for different types of service providers
- ServiceScope: Interface for managing service scopes
- Decorators: Easy-to-use decorators for service registration and injection
- Exceptions: Custom exceptions for error handling

Example usage:
    from gemini_sre_agent.core.di import DIContainer, injectable, inject

    # Create a container
    container = DIContainer()

    # Register services
    @injectable(lifetime='singleton')
    class DatabaseService:
        def __init__(self):
            self.connection = "database_connection"

    @injectable(lifetime='transient')
    class UserService:
        def __init__(self, db: DatabaseService):
            self.db = db

    # Use services
    @inject
    def get_user(user_service: UserService):
        return user_service.get_user()

    # Or use the container directly
    user_service = container.get_service(UserService)
"""

from .container import (
    DIContainer,
    DIContainerScope,
    clear_container,
    get_container,
    resolve_dependencies,
    set_container,
)
from .decorators import (
    ServiceLocator,
    auto_inject,
    factory,
    get_service_locator,
    inject,
    injectable,
    instance,
    scoped,
    set_service_locator,
    singleton,
    transient,
)
from .exceptions import (
    CircularDependencyError,
    ServiceNotFoundError,
    ServiceRegistrationError,
    ServiceResolutionError,
    ServiceScopeError,
)
from .interfaces import ServiceLifetime, ServiceProvider, ServiceRegistry, ServiceScope
from .providers import (
    CachedProvider,
    ConditionalProvider,
    DecoratorProvider,
    FactoryProvider,
    InstanceProvider,
    LazyProvider,
    TypeProvider,
)

__all__ = [
    # Container
    "DIContainer",
    "DIContainerScope",
    "get_container",
    "set_container",
    "clear_container",
    "resolve_dependencies",
    # Decorators
    "injectable",
    "inject",
    "auto_inject",
    "singleton",
    "transient",
    "scoped",
    "factory",
    "instance",
    "ServiceLocator",
    "get_service_locator",
    "set_service_locator",
    # Exceptions
    "CircularDependencyError",
    "ServiceNotFoundError",
    "ServiceRegistrationError",
    "ServiceResolutionError",
    "ServiceScopeError",
    # Interfaces
    "ServiceLifetime",
    "ServiceProvider",
    "ServiceRegistry",
    "ServiceScope",
    # Providers
    "TypeProvider",
    "FactoryProvider",
    "InstanceProvider",
    "LazyProvider",
    "CachedProvider",
    "ConditionalProvider",
    "DecoratorProvider",
]
