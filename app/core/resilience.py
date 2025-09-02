"""
Resilience utilities for graceful error handling and retry logic.
"""
import asyncio
import random
import time
from typing import Any, Callable, Optional, TypeVar, Union, List
from functools import wraps
import structlog

from .circuit_breaker import circuit_manager, CircuitBreakerConfig
from .exceptions import (
    DatabaseError, CacheError, ExternalServiceError, TimeoutError,
    should_retry, AICopilotException
)

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry logic."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    config: RetryConfig = None,
    **kwargs
) -> T:
    """Execute function with exponential backoff retry logic."""
    config = config or RetryConfig()
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            result = await func(*args, **kwargs)
            
            if attempt > 0:
                logger.info(
                    "Operation succeeded after retry",
                    function=func.__name__,
                    attempt=attempt + 1,
                    total_attempts=config.max_attempts
                )
            
            return result
            
        except config.retryable_exceptions as e:
            last_exception = e
            
            # Don't retry on last attempt
            if attempt == config.max_attempts - 1:
                break
            
            # Check if we should retry this specific exception
            if isinstance(e, AICopilotException) and not should_retry(e):
                logger.info(
                    "Not retrying non-retryable exception",
                    function=func.__name__,
                    error=str(e),
                    error_code=getattr(e, 'error_code', 'UNKNOWN')
                )
                break
            
            # Calculate delay with exponential backoff
            delay = min(
                config.base_delay * (config.exponential_base ** attempt),
                config.max_delay
            )
            
            # Add jitter to prevent thundering herd
            if config.jitter:
                delay *= (0.5 + random.random() * 0.5)
            
            logger.warning(
                "Operation failed, retrying",
                function=func.__name__,
                attempt=attempt + 1,
                total_attempts=config.max_attempts,
                delay=delay,
                error=str(e)
            )
            
            await asyncio.sleep(delay)
    
    # All attempts failed
    logger.error(
        "All retry attempts failed",
        function=func.__name__,
        total_attempts=config.max_attempts,
        final_error=str(last_exception)
    )
    
    raise last_exception


def with_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig = None,
    retry_config: RetryConfig = None
):
    """Decorator to add circuit breaker protection to functions."""
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # First apply retry logic, then circuit breaker
            if retry_config:
                async def retry_func():
                    return await circuit_manager.call_with_breaker(
                        name, func, *args, config=config, **kwargs
                    )
                return await retry_with_backoff(retry_func, config=retry_config)
            else:
                return await circuit_manager.call_with_breaker(
                    name, func, *args, config=config, **kwargs
                )
        
        return wrapper
    return decorator


def with_retry(config: RetryConfig = None):
    """Decorator to add retry logic to functions."""
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry_with_backoff(func, *args, config=config, **kwargs)
        
        return wrapper
    return decorator


async def safe_execute(
    func: Callable[..., T],
    *args,
    default_value: T = None,
    log_errors: bool = True,
    **kwargs
) -> Optional[T]:
    """Execute function safely, returning default value on error."""
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.warning(
                "Safe execution failed",
                function=func.__name__,
                error=str(e),
                default_value=default_value
            )
        return default_value


class GracefulDegradation:
    """Handles graceful degradation when services are unavailable."""
    
    def __init__(self):
        self.fallback_handlers = {}
        self.service_status = {}
    
    def register_fallback(self, service: str, handler: Callable):
        """Register a fallback handler for a service."""
        self.fallback_handlers[service] = handler
        logger.info(f"Registered fallback handler for service: {service}")
    
    async def execute_with_fallback(
        self,
        service: str,
        primary_func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Execute function with fallback if primary fails."""
        try:
            result = await primary_func(*args, **kwargs)
            self.service_status[service] = "healthy"
            return result
            
        except Exception as e:
            self.service_status[service] = "degraded"
            
            logger.warning(
                "Primary service failed, attempting fallback",
                service=service,
                error=str(e)
            )
            
            if service in self.fallback_handlers:
                try:
                    return await self.fallback_handlers[service](*args, **kwargs)
                except Exception as fallback_error:
                    logger.error(
                        "Fallback handler also failed",
                        service=service,
                        primary_error=str(e),
                        fallback_error=str(fallback_error)
                    )
                    raise
            else:
                logger.error(f"No fallback handler registered for service: {service}")
                raise
    
    def get_service_status(self) -> dict:
        """Get status of all services."""
        return self.service_status.copy()


# Global graceful degradation manager
degradation_manager = GracefulDegradation()


# Predefined retry configurations
DATABASE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    retryable_exceptions=(DatabaseError, TimeoutError, ConnectionError)
)

CACHE_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=0.5,
    max_delay=5.0,
    retryable_exceptions=(CacheError, TimeoutError, ConnectionError)
)

EXTERNAL_API_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=(ExternalServiceError, TimeoutError, ConnectionError)
)


class HealthChecker:
    """Monitors service health and provides circuit breaker insights."""
    
    def __init__(self):
        self.health_checks = {}
        self.last_check_times = {}
    
    def register_health_check(self, service: str, check_func: Callable):
        """Register a health check function for a service."""
        self.health_checks[service] = check_func
        logger.info(f"Registered health check for service: {service}")
    
    async def check_service_health(self, service: str) -> dict:
        """Check health of a specific service."""
        if service not in self.health_checks:
            return {"status": "unknown", "error": "No health check registered"}
        
        try:
            start_time = time.time()
            result = await self.health_checks[service]()
            response_time = time.time() - start_time
            
            self.last_check_times[service] = time.time()
            
            return {
                "status": "healthy",
                "response_time": response_time,
                "timestamp": self.last_check_times[service],
                "details": result if isinstance(result, dict) else {}
            }
            
        except Exception as e:
            self.last_check_times[service] = time.time()
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": self.last_check_times[service]
            }
    
    async def check_all_services(self) -> dict:
        """Check health of all registered services."""
        results = {}
        
        for service in self.health_checks:
            results[service] = await self.check_service_health(service)
        
        # Add circuit breaker states
        circuit_states = circuit_manager.get_all_states()
        
        return {
            "services": results,
            "circuit_breakers": circuit_states,
            "degradation_status": degradation_manager.get_service_status(),
            "overall_status": self._calculate_overall_status(results, circuit_states)
        }
    
    def _calculate_overall_status(self, service_results: dict, circuit_states: dict) -> str:
        """Calculate overall system health status."""
        # Check if any critical services are down
        unhealthy_services = [
            service for service, result in service_results.items()
            if result["status"] == "unhealthy"
        ]
        
        # Check if any circuit breakers are open
        open_circuits = [
            name for name, state in circuit_states.items()
            if state["state"] == "open"
        ]
        
        if unhealthy_services or open_circuits:
            if len(unhealthy_services) > len(service_results) // 2:
                return "critical"
            else:
                return "degraded"
        
        return "healthy"


# Global health checker
health_checker = HealthChecker()
