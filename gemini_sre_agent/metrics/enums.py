from enum import Enum


class ErrorCategory(Enum):
    """
    Categories for errors that occur during LLM requests.
    """

    TRANSIENT = "transient"
    """Transient errors that may be resolved by retrying."""

    AUTHENTICATION = "authentication"
    """Errors related to authentication or authorization."""

    NOT_FOUND = "not_found"
    """Errors indicating that the requested resource was not found."""

    RATE_LIMIT = "rate_limit"
    """Errors due to exceeding rate limits."""

    BAD_REQUEST = "bad_request"
    """Errors caused by invalid or malformed requests."""

    SERVER_ERROR = "server_error"
    """Errors originating from the server."""

    TIMEOUT = "timeout"
    """Errors due to request timeouts."""

    UNKNOWN = "unknown"
    """Errors of unknown or uncategorized type."""
