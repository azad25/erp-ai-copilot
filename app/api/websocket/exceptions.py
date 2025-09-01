"""
Custom exceptions for WebSocket handling.
"""

class WebSocketError(Exception):
    """Base WebSocket error."""
    def __init__(self, message: str, code: str = "websocket_error", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(WebSocketError):
    """Authentication related errors."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "authentication_error", 1008)


class ConnectionLimitExceeded(WebSocketError):
    """Raised when connection limit is exceeded."""
    def __init__(self, message: str = "Connection limit exceeded"):
        super().__init__(message, "connection_limit_exceeded", 1013)


class InvalidMessageFormat(WebSocketError):
    """Raised when message format is invalid."""
    def __init__(self, message: str = "Invalid message format"):
        super().__init__(message, "invalid_message_format", 1003)


class RateLimitExceeded(WebSocketError):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "rate_limit_exceeded", 1008)


class ResourceNotFound(WebSocketError):
    """Raised when a requested resource is not found."""
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            f"{resource_type} not found: {resource_id}",
            "resource_not_found",
            1008
        )
