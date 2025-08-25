"""
Optimized Redis cache manager for high-performance caching.
"""
import asyncio
import json
import hashlib
import time
from typing import Any, Optional, Dict, List, Union
from functools import wraps
import structlog
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool
from app.config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class CacheManager:
    """High-performance Redis cache manager with connection pooling."""
    
    def __init__(self):
        self._redis: Optional[Redis] = None
        self._pool: Optional[ConnectionPool] = None
        self._initialized = False
        
    async def initialize(self):
        """Initialize Redis connection pool with optimized settings."""
        if self._initialized:
            return
            
        try:
            # Create optimized connection pool
            self._pool = ConnectionPool.from_url(
                settings.redis.url,
                max_connections=50,  # Increased for better concurrency
                decode_responses=True,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=60,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            
            self._redis = Redis(connection_pool=self._pool)
            
            # Test connection
            await self._redis.ping()
            self._initialized = True
            
            logger.info("Cache manager initialized with optimized connection pool")
            
        except Exception as e:
            logger.error("Failed to initialize cache manager", error=str(e))
            raise
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache with automatic deserialization."""
        if not self._redis:
            return None
            
        try:
            value = await self._redis.get(key)
            if value is None:
                return None
                
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
                
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: int = 3600, 
        compress: bool = False
    ) -> bool:
        """Set value in cache with optional compression."""
        if not self._redis:
            return False
            
        try:
            # Serialize complex objects
            if isinstance(value, (dict, list, tuple)):
                serialized = json.dumps(value, separators=(',', ':'))
            else:
                serialized = str(value)
            
            # Set with TTL
            await self._redis.setex(key, ttl, serialized)
            return True
            
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._redis:
            return False
            
        try:
            result = await self._redis.delete(key)
            return result > 0
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self._redis:
            return False
            
        try:
            return await self._redis.exists(key)
        except Exception as e:
            logger.warning("Cache exists check failed", key=key, error=str(e))
            return False
    
    async def mget(self, keys: List[str]) -> List[Optional[Any]]:
        """Get multiple keys efficiently."""
        if not self._redis or not keys:
            return [None] * len(keys)
            
        try:
            values = await self._redis.mget(keys)
            return [
                json.loads(v) if v and v.startswith(('{', '[')) else v 
                for v in values
            ]
        except Exception as e:
            logger.warning("Cache mget failed", error=str(e))
            return [None] * len(keys)
    
    async def mset(self, mapping: Dict[str, Any], ttl: int = 3600) -> bool:
        """Set multiple keys efficiently."""
        if not self._redis or not mapping:
            return False
            
        try:
            # Prepare serialized mapping
            serialized = {
                k: json.dumps(v, separators=(',', ':')) if isinstance(v, (dict, list)) else str(v)
                for k, v in mapping.items()
            }
            
            # Use pipeline for efficiency
            async with self._redis.pipeline(transaction=False) as pipe:
                pipe.mset(serialized)
                for key in mapping.keys():
                    pipe.expire(key, ttl)
                await pipe.execute()
                
            return True
            
        except Exception as e:
            logger.warning("Cache mset failed", error=str(e))
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Atomic increment operation."""
        if not self._redis:
            return None
            
        try:
            return await self._redis.incrby(key, amount)
        except Exception as e:
            logger.warning("Cache increment failed", key=key, error=str(e))
            return None
    
    async def get_ttl(self, key: str) -> int:
        """Get remaining TTL for a key."""
        if not self._redis:
            return -2
            
        try:
            return await self._redis.ttl(key)
        except Exception as e:
            logger.warning("Cache TTL check failed", key=key, error=str(e))
            return -2
    
    def generate_key(self, prefix: str, *args) -> str:
        """Generate consistent cache key from arguments."""
        parts = [prefix]
        for arg in args:
            if isinstance(arg, dict):
                # Sort dict keys for consistent hashing
                sorted_dict = json.dumps(arg, sort_keys=True, separators=(',', ':'))
                parts.append(hashlib.md5(sorted_dict.encode()).hexdigest()[:8])
            else:
                parts.append(str(arg))
        return ':'.join(parts)
    
    async def close(self):
        """Close Redis connections."""
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.disconnect()
        logger.info("Cache manager connections closed")


# Global cache manager instance
cache_manager = CacheManager()


def cache_result(ttl: int = 3600, key_prefix: str = None):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_prefix:
                cache_key = cache_manager.generate_key(key_prefix, *args, **kwargs)
            else:
                cache_key = cache_manager.generate_key(func.__name__, *args, **kwargs)
            
            # Try to get from cache
            cached = await cache_manager.get(cache_key)
            if cached is not None:
                return cached
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


class CacheKeys:
    """Cache key patterns for different data types."""
    
    @staticmethod
    def agent_response(agent_type: str, user_id: str, query_hash: str) -> str:
        return f"agent:{agent_type}:{user_id}:{query_hash}"
    
    @staticmethod
    def user_conversations(user_id: str) -> str:
        return f"user:conversations:{user_id}"
    
    @staticmethod
    def rag_results(query_hash: str) -> str:
        return f"rag:results:{query_hash}"
    
    @staticmethod
    def system_metrics(metric_name: str) -> str:
        return f"system:metrics:{metric_name}"
    
    @staticmethod
    def auth_token(user_id: str) -> str:
        return f"auth:token:{user_id}"


# Export for use
__all__ = ['cache_manager', 'CacheManager', 'cache_result', 'CacheKeys']