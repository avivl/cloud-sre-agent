"""Exceptions for the dependency injection system."""



class ServiceNotFoundError(Exception):
    """Raised when a requested service is not found in the container."""

    def __init__(self, service_type: type, message: str | None = None):
        """Initialize the exception.

        Args:
            service_type: The type of service that was not found
            message: Optional custom error message
        """
        self.service_type = service_type
        if message is None:
            message = f"Service of type {service_type.__name__} is not registered"
        super().__init__(message)


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected during service resolution."""

    def __init__(self, dependency_chain: list[type], message: str | None = None):
        """Initialize the exception.

        Args:
            dependency_chain: The chain of types involved in the circular dependency
            message: Optional custom error message
        """
        self.dependency_chain = dependency_chain
        if message is None:
            chain_str = " -> ".join(t.__name__ for t in dependency_chain)
            message = f"Circular dependency detected: {chain_str}"
        super().__init__(message)


class ServiceRegistrationError(Exception):
    """Raised when there is an error during service registration."""

    def __init__(self, service_type: type, message: str | None = None):
        """Initialize the exception.

        Args:
            service_type: The type of service that failed to register
            message: Optional custom error message
        """
        self.service_type = service_type
        if message is None:
            message = f"Failed to register service of type {service_type.__name__}"
        super().__init__(message)


class ServiceResolutionError(Exception):
    """Raised when there is an error during service resolution."""

    def __init__(self, service_type: type, message: str | None = None):
        """Initialize the exception.

        Args:
            service_type: The type of service that failed to resolve
            message: Optional custom error message
        """
        self.service_type = service_type
        if message is None:
            message = f"Failed to resolve service of type {service_type.__name__}"
        super().__init__(message)


class ServiceScopeError(Exception):
    """Raised when there is an error with service scopes."""

    def __init__(self, message: str):
        """Initialize the exception.

        Args:
            message: Error message
        """
        super().__init__(message)


class ServiceDisposalError(Exception):
    """Raised when there is an error during service disposal."""

    def __init__(self, service_type: type, message: str | None = None):
        """Initialize the exception.

        Args:
            service_type: The type of service that failed to dispose
            message: Optional custom error message
        """
        self.service_type = service_type
        if message is None:
            message = f"Failed to dispose service of type {service_type.__name__}"
        super().__init__(message)
