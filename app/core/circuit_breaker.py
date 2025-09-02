"""
Circuit breaker pattern implementation for resilient database and external service connections.
"""
import asyncio
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from enum import Enum
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service is recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5          # Number of failures to open circuit
    recovery_timeout: int = 60          # Seconds to wait before trying again
    success_threshold: int = 3          # Successful calls needed to close circuit
    timeout: int = 30                   # Operation timeout in seconds
    expected_exception: tuple = (Exception,)  # Exceptions that count as failures


class CircuitBreaker:
    """Circuit breaker implementation with exponential backoff."""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.next_attempt_time = 0
        self._lock = asyncio.Lock()
        
        logger.info(
            "Circuit breaker initialized",
            name=self.name,
            config=self.config
        )
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            # Check if circuit should transition states
            await self._check_state_transition()
            
            # If circuit is open, fail fast
            if self.state == CircuitState.OPEN:
                if time.time() < self.next_attempt_time:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is open. "
                        f"Next attempt in {int(self.next_attempt_time - time.time())} seconds"
                    )
                else:
                    # Transition to half-open to test service
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(
                        "Circuit breaker transitioning to half-open",
                        name=self.name
                    )
        
        # Execute the function with timeout
        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            # Record success
            await self._record_success()
            return result
            
        except self.config.expected_exception as e:
            # Record failure
            await self._record_failure(e)
            raise
        except asyncio.TimeoutError as e:
            # Timeout is also a failure
            timeout_error = CircuitBreakerTimeoutError(
                f"Operation timed out after {self.config.timeout} seconds"
            )
            await self._record_failure(timeout_error)
            raise timeout_error
    
    async def _check_state_transition(self):
        """Check if circuit breaker should change state."""
        current_time = time.time()
        
        if self.state == CircuitState.OPEN:
            if current_time >= self.next_attempt_time:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info(
                    "Circuit breaker transitioning to half-open",
                    name=self.name
                )
    
    async def _record_success(self):
        """Record a successful operation."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                logger.debug(
                    "Circuit breaker success recorded",
                    name=self.name,
                    success_count=self.success_count,
                    threshold=self.config.success_threshold
                )
                
                if self.success_count >= self.config.success_threshold:
                    # Close the circuit
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    logger.info(
                        "Circuit breaker closed after successful recovery",
                        name=self.name
                    )
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0
    
    async def _record_failure(self, exception: Exception):
        """Record a failed operation."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            logger.warning(
                "Circuit breaker failure recorded",
                name=self.name,
                failure_count=self.failure_count,
                threshold=self.config.failure_threshold,
                error=str(exception)
            )
            
            if (self.state in [CircuitState.CLOSED, CircuitState.HALF_OPEN] and 
                self.failure_count >= self.config.failure_threshold):
                
                # Open the circuit
                self.state = CircuitState.OPEN
                self.next_attempt_time = (
                    time.time() + 
                    self.config.recovery_timeout * (2 ** min(self.failure_count - self.config.failure_threshold, 5))
                )
                
                logger.error(
                    "Circuit breaker opened due to failures",
                    name=self.name,
                    failure_count=self.failure_count,
                    next_attempt_time=self.next_attempt_time
                )
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "next_attempt_time": self.next_attempt_time,
            "is_available": self.state != CircuitState.OPEN or time.time() >= self.next_attempt_time
        }
    
    async def reset(self):
        """Manually reset the circuit breaker."""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = 0
            self.next_attempt_time = 0
            
            logger.info("Circuit breaker manually reset", name=self.name)


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreakerTimeoutError(Exception):
    """Raised when operation times out."""
    pass


class CircuitBreakerManager:
    """Manages multiple circuit breakers."""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_breaker(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in self.breakers:
            async with self._lock:
                if name not in self.breakers:
                    self.breakers[name] = CircuitBreaker(name, config)
        
        return self.breakers[name]
    
    async def call_with_breaker(
        self, 
        name: str, 
        func: Callable[..., T], 
        *args, 
        config: CircuitBreakerConfig = None,
        **kwargs
    ) -> T:
        """Execute function with circuit breaker protection."""
        breaker = await self.get_breaker(name, config)
        return await breaker.call(func, *args, **kwargs)
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get state of all circuit breakers."""
        return {name: breaker.get_state() for name, breaker in self.breakers.items()}
    
    async def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self.breakers.values():
            await breaker.reset()
        
        logger.info("All circuit breakers reset")
    
    async def reset_breaker(self, name: str):
        """Reset specific circuit breaker."""
        if name in self.breakers:
            await self.breakers[name].reset()
        else:
            logger.warning(f"Circuit breaker '{name}' not found")


# Global circuit breaker manager
circuit_manager = CircuitBreakerManager()


# Predefined configurations for different services
DATABASE_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=30,
    success_threshold=2,
    timeout=10,
    expected_exception=(Exception,)
)

MONGODB_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60,
    success_threshold=3,
    timeout=15,
    expected_exception=(Exception,)
)

REDIS_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=20,
    success_threshold=2,
    timeout=5,
    expected_exception=(Exception,)
)

EXTERNAL_API_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=120,
    success_threshold=3,
    timeout=30,
    expected_exception=(Exception,)
)

AI_MODEL_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=180,
    success_threshold=2,
    timeout=60,
    expected_exception=(Exception,)
)
