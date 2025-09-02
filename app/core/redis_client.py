"""
Redis Client Module

Provides Redis client functionality for caching, session management,
and real-time data operations for the AI Copilot service.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

import redis.asyncio as redis
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis Client for AI Copilot Service
    
    Features:
    - Async Redis operations
    - User context caching
    - Session management
    - Real-time data storage
    - Connection pooling
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[redis.Redis] = None
        self.connection_pool: Optional[redis.ConnectionPool] = None
        
    async def connect(self):
        """Initialize Redis connection"""
        try:
            # Create connection pool
            self.connection_pool = redis.ConnectionPool.from_url(
                self.settings.redis.url,
                max_connections=self.settings.redis.max_connections,
                retry_on_timeout=True,
                decode_responses=True
            )
            
            # Create Redis client
            self.client = redis.Redis(
                connection_pool=self.connection_pool,
                socket_connect_timeout=self.settings.redis.connect_timeout,
                socket_timeout=self.settings.redis.socket_timeout
            )
            
            # Test connection
            await self.client.ping()
            logger.info("Redis client connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Close Redis connection"""
        try:
            if self.client:
                await self.client.close()
            if self.connection_pool:
                await self.connection_pool.disconnect()
            logger.info("Redis client disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting Redis: {e}")
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Union[str, Dict, List], 
        expire: Optional[int] = None
    ) -> bool:
        """Set key-value pair with optional expiration"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            result = await self.client.set(key, value, ex=expire)
            return result
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    async def delete(self, *keys: str) -> int:
        """Delete keys"""
        try:
            return await self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis EXISTS error for key {key}: {e}")
            return False
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field value"""
        try:
            return await self.client.hget(name, key)
        except Exception as e:
            logger.error(f"Redis HGET error for {name}.{key}: {e}")
            return None
    
    async def hset(self, name: str, mapping: Dict[str, Any]) -> int:
        """Set hash fields"""
        try:
            # Convert dict/list values to JSON
            processed_mapping = {}
            for k, v in mapping.items():
                if isinstance(v, (dict, list)):
                    processed_mapping[k] = json.dumps(v)
                else:
                    processed_mapping[k] = str(v)
            
            return await self.client.hset(name, mapping=processed_mapping)
        except Exception as e:
            logger.error(f"Redis HSET error for {name}: {e}")
            return 0
    
    async def hgetall(self, name: str) -> Dict[str, str]:
        """Get all hash fields"""
        try:
            return await self.client.hgetall(name)
        except Exception as e:
            logger.error(f"Redis HGETALL error for {name}: {e}")
            return {}
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration"""
        try:
            return await self.client.expire(key, seconds)
        except Exception as e:
            logger.error(f"Redis EXPIRE error for key {key}: {e}")
            return False
    
    async def zadd(self, name: str, mapping: Dict[str, float]) -> int:
        """Add to sorted set"""
        try:
            return await self.client.zadd(name, mapping)
        except Exception as e:
            logger.error(f"Redis ZADD error for {name}: {e}")
            return 0
    
    async def zrange(
        self, 
        name: str, 
        start: int = 0, 
        end: int = -1, 
        withscores: bool = False
    ) -> List[Union[str, tuple]]:
        """Get sorted set range"""
        try:
            return await self.client.zrange(name, start, end, withscores=withscores)
        except Exception as e:
            logger.error(f"Redis ZRANGE error for {name}: {e}")
            return []
    
    async def keys(self, pattern: str) -> List[str]:
        """Get keys matching pattern"""
        try:
            return await self.client.keys(pattern)
        except Exception as e:
            logger.error(f"Redis KEYS error for pattern {pattern}: {e}")
            return []
    
    async def flushdb(self) -> bool:
        """Flush current database"""
        try:
            await self.client.flushdb()
            return True
        except Exception as e:
            logger.error(f"Redis FLUSHDB error: {e}")
            return False
    
    async def ping(self) -> bool:
        """Test Redis connection"""
        try:
            await self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis PING error: {e}")
            return False
    
    async def cache_user_context(
        self, 
        user_id: str, 
        organization_id: str, 
        context: Dict[str, Any],
        expire_seconds: int = 3600
    ) -> bool:
        """Cache user context for AI Copilot"""
        try:
            key = f"user_context:{user_id}:{organization_id}"
            return await self.set(key, context, expire_seconds)
        except Exception as e:
            logger.error(f"Failed to cache user context: {e}")
            return False
    
    async def get_user_context(
        self, 
        user_id: str, 
        organization_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached user context"""
        try:
            key = f"user_context:{user_id}:{organization_id}"
            data = await self.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get user context: {e}")
            return None
    
    async def cache_reasoning_step(
        self,
        conversation_id: str,
        step_data: Dict[str, Any],
        expire_seconds: int = 1800
    ) -> bool:
        """Cache reasoning step for conversation"""
        try:
            key = f"reasoning_steps:{conversation_id}"
            # Get existing steps
            existing = await self.get(key)
            steps = json.loads(existing) if existing else []
            
            # Add new step
            steps.append({
                **step_data,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return await self.set(key, steps, expire_seconds)
        except Exception as e:
            logger.error(f"Failed to cache reasoning step: {e}")
            return False
    
    async def get_conversation_steps(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get cached reasoning steps for conversation"""
        try:
            key = f"reasoning_steps:{conversation_id}"
            data = await self.get(key)
            if data:
                return json.loads(data)
            return []
        except Exception as e:
            logger.error(f"Failed to get conversation steps: {e}")
            return []


# Global Redis client instance
redis_client = RedisClient()
