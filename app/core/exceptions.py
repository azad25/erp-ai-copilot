"""
Centralized exception handling for the AI Copilot service.
"""
from typing import Any, Dict, Optional
import structlog

logger = structlog.get_logger(__name__)


class AICopilotException(Exception):
    """Base exception for AI Copilot service."""
    
    def __init__(
        self,
        message: str,
        error_code: str = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
        user_message: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.status_code = status_code
        self.user_message = user_message or message
        
        super().__init__(self.message)
        
        # Log the exception
        logger.error(
            "AI Copilot exception raised",
            error_code=self.error_code,
            message=self.message,
            details=self.details,
            status_code=self.status_code
        )


class AuthenticationError(AICopilotException):
    """Authentication and authorization errors."""
    
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            details=details,
            status_code=401
        )


class AuthorizationError(AICopilotException):
    """Permission and access control errors."""
    
    def __init__(self, message: str = "Access denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            details=details,
            status_code=403
        )


class ValidationError(AICopilotException):
    """Data validation errors."""
    
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details,
            status_code=400
        )


class ResourceNotFoundError(AICopilotException):
    """Resource not found errors."""
    
    def __init__(self, resource_type: str, resource_id: str, details: Optional[Dict[str, Any]] = None):
        message = f"{resource_type} with id '{resource_id}' not found"
        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            details=details or {"resource_type": resource_type, "resource_id": resource_id},
            status_code=404
        )


class DatabaseError(AICopilotException):
    """Database operation errors."""
    
    def __init__(self, operation: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Database {operation} failed: {message}",
            error_code="DATABASE_ERROR",
            details=details or {"operation": operation},
            status_code=500
        )


class CacheError(AICopilotException):
    """Cache operation errors."""
    
    def __init__(self, operation: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Cache {operation} failed: {message}",
            error_code="CACHE_ERROR",
            details=details or {"operation": operation},
            status_code=500
        )


class ExternalServiceError(AICopilotException):
    """External service integration errors."""
    
    def __init__(self, service: str, operation: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"{service} {operation} failed: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            details=details or {"service": service, "operation": operation},
            status_code=502
        )


class AIModelError(AICopilotException):
    """AI model operation errors."""
    
    def __init__(self, provider: str, model: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"AI model {provider}/{model} failed: {message}",
            error_code="AI_MODEL_ERROR",
            details=details or {"provider": provider, "model": model},
            status_code=500
        )


class RAGError(AICopilotException):
    """RAG system errors."""
    
    def __init__(self, operation: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"RAG {operation} failed: {message}",
            error_code="RAG_ERROR",
            details=details or {"operation": operation},
            status_code=500
        )


class AgentError(AICopilotException):
    """Agent execution errors."""
    
    def __init__(self, agent_type: str, action: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Agent {agent_type} {action} failed: {message}",
            error_code="AGENT_ERROR",
            details=details or {"agent_type": agent_type, "action": action},
            status_code=500
        )


class WebSocketError(AICopilotException):
    """WebSocket operation errors."""
    
    def __init__(self, operation: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"WebSocket {operation} failed: {message}",
            error_code="WEBSOCKET_ERROR",
            details=details or {"operation": operation},
            status_code=500
        )


class TaskError(AICopilotException):
    """Background task errors."""
    
    def __init__(self, task_type: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Task {task_type} failed: {message}",
            error_code="TASK_ERROR",
            details=details or {"task_type": task_type},
            status_code=500
        )


class ConfigurationError(AICopilotException):
    """Configuration and setup errors."""
    
    def __init__(self, component: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Configuration error in {component}: {message}",
            error_code="CONFIGURATION_ERROR",
            details=details or {"component": component},
            status_code=500
        )


class RateLimitError(AICopilotException):
    """Rate limiting errors."""
    
    def __init__(self, limit_type: str, retry_after: int = 60, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Rate limit exceeded for {limit_type}",
            error_code="RATE_LIMIT_ERROR",
            details=details or {"limit_type": limit_type, "retry_after": retry_after},
            status_code=429
        )


class TimeoutError(AICopilotException):
    """Operation timeout errors."""
    
    def __init__(self, operation: str, timeout_seconds: int, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Operation {operation} timed out after {timeout_seconds} seconds",
            error_code="TIMEOUT_ERROR",
            details=details or {"operation": operation, "timeout_seconds": timeout_seconds},
            status_code=408
        )


class BusinessLogicError(AICopilotException):
    """Business rule violation errors."""
    
    def __init__(self, rule: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Business rule violation: {rule} - {message}",
            error_code="BUSINESS_LOGIC_ERROR",
            details=details or {"rule": rule},
            status_code=400
        )


class DataIntegrityError(AICopilotException):
    """Data consistency and integrity errors."""
    
    def __init__(self, entity: str, constraint: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Data integrity error in {entity}: {constraint} - {message}",
            error_code="DATA_INTEGRITY_ERROR",
            details=details or {"entity": entity, "constraint": constraint},
            status_code=400
        )


class ConcurrencyError(AICopilotException):
    """Concurrent access and locking errors."""
    
    def __init__(self, resource: str, operation: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Concurrency error on {resource} during {operation}: {message}",
            error_code="CONCURRENCY_ERROR",
            details=details or {"resource": resource, "operation": operation},
            status_code=409
        )


def handle_exception(exc: Exception) -> Dict[str, Any]:
    """Convert any exception to a standardized error response."""
    if isinstance(exc, AICopilotException):
        return {
            "error": exc.error_code,
            "message": exc.user_message,
            "details": exc.details,
            "status_code": exc.status_code,
            "timestamp": None  # Will be set by the handler
        }
    
    # Handle unexpected exceptions
    logger.error("Unexpected exception", error=str(exc), exc_info=True)
    
    return {
        "error": "INTERNAL_ERROR",
        "message": "An unexpected error occurred",
        "details": {"original_error": str(exc)},
        "status_code": 500,
        "timestamp": None
    }


def is_client_error(exc: Exception) -> bool:
    """Check if the exception represents a client error (4xx)."""
    if isinstance(exc, AICopilotException):
        return 400 <= exc.status_code < 500
    return False


def is_server_error(exc: Exception) -> bool:
    """Check if the exception represents a server error (5xx)."""
    if isinstance(exc, AICopilotException):
        return 500 <= exc.status_code < 600
    return True  # Unexpected exceptions are treated as server errors


def get_retry_after(exc: Exception) -> Optional[int]:
    """Get retry-after value for rate limit errors."""
    if isinstance(exc, RateLimitError):
        return exc.details.get("retry_after", 60)
    return None


def should_retry(exc: Exception) -> bool:
    """Determine if an operation should be retried."""
    if isinstance(exc, AICopilotException):
        # Don't retry client errors
        if is_client_error(exc):
            return False
        
        # Retry specific server errors
        retryable_errors = [
            "EXTERNAL_SERVICE_ERROR",
            "TIMEOUT_ERROR",
            "DATABASE_ERROR",
            "CACHE_ERROR"
        ]
        return exc.error_code in retryable_errors
    
    # Retry unexpected exceptions
    return True
