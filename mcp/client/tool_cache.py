"""
Tool Cache Manager

Redis-based caching for tool definitions and results.
"""

import json
import hashlib
from typing import Dict, Any, Optional, List
import structlog

logger = structlog.get_logger(__name__)


class ToolCache:
    """
    Tool caching with Redis
    
    Caches:
    - Tool definitions
    - Tool discovery results
    - Frequently used tool results
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[Any] = None
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0
        }
        self._in_memory_cache: Dict[str, Any] = {}  # Fallback cache
    
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            import redis.asyncio as redis
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Tool cache initialized with Redis")
        except ImportError:
            logger.warning("Redis not available, using in-memory cache")
            self.redis_client = None
        except Exception as e:
            logger.warning("Redis connection failed, using in-memory cache", error=str(e))
            self.redis_client = None
    
    async def get_tool_definition(
        self,
        server: str,
        tool: str,
        detail_level: str
    ) -> Optional[Dict]:
        """Get cached tool definition"""
        key = f"mcp:tool:{server}:{tool}:{detail_level}"
        
        # Try Redis first
        if self.redis_client:
            try:
                cached = await self.redis_client.get(key)
                if cached:
                    self.stats["hits"] += 1
                    return json.loads(cached)
            except Exception as e:
                logger.warning("Cache read failed", error=str(e))
        
        # Fallback to in-memory cache
        if key in self._in_memory_cache:
            self.stats["hits"] += 1
            return self._in_memory_cache[key]
        
        self.stats["misses"] += 1
        return None
    
    async def set_tool_definition(
        self,
        server: str,
        tool: str,
        detail_level: str,
        data: Dict,
        ttl: int = 3600
    ):
        """Cache tool definition"""
        key = f"mcp:tool:{server}:{tool}:{detail_level}"
        
        # Try Redis first
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(data)
                )
                self.stats["sets"] += 1
                return
            except Exception as e:
                logger.warning("Cache write failed", error=str(e))
        
        # Fallback to in-memory cache
        self._in_memory_cache[key] = data
        self.stats["sets"] += 1
    
    async def get_discovery_result(self, query: str) -> Optional[List[Dict]]:
        """Get cached discovery result"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        key = f"mcp:discovery:{query_hash}"
        
        # Try Redis first
        if self.redis_client:
            try:
                cached = await self.redis_client.get(key)
                if cached:
                    self.stats["hits"] += 1
                    return json.loads(cached)
            except Exception as e:
                logger.warning("Cache read failed", error=str(e))
        
        # Fallback to in-memory cache
        if key in self._in_memory_cache:
            self.stats["hits"] += 1
            return self._in_memory_cache[key]
        
        self.stats["misses"] += 1
        return None
    
    async def set_discovery_result(
        self,
        query: str,
        results: List[Dict],
        ttl: int = 300
    ):
        """Cache discovery result"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        key = f"mcp:discovery:{query_hash}"
        
        # Try Redis first
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(results)
                )
                self.stats["sets"] += 1
                return
            except Exception as e:
                logger.warning("Cache write failed", error=str(e))
        
        # Fallback to in-memory cache
        self._in_memory_cache[key] = results
        self.stats["sets"] += 1
    
    async def warm_cache(self):
        """Pre-load frequently used tools"""
        logger.info("Warming tool cache...")
        
        # Load common tools
        common_tools = [
            ("erp-api", "call_api"),
            ("knowledge-base", "search_documentation"),
            ("database", "query_postgres")
        ]
        
        # This would be called during startup
        logger.info("Cache warmed", tools=len(common_tools))
    
    def get_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.stats["hits"] + self.stats["misses"]
        if total == 0:
            return 0.0
        return (self.stats["hits"] / total) * 100
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            **self.stats,
            "hit_rate": self.get_hit_rate(),
            "cache_size": len(self._in_memory_cache)
        }
    
    async def clear(self):
        """Clear all caches"""
        if self.redis_client:
            try:
                # Clear Redis keys with mcp: prefix
                keys = await self.redis_client.keys("mcp:*")
                if keys:
                    await self.redis_client.delete(*keys)
            except Exception as e:
                logger.warning("Redis clear failed", error=str(e))
        
        self._in_memory_cache.clear()
        logger.info("Cache cleared")
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
