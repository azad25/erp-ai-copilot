"""Cache Module for RAG Engine

This module provides caching functionality for the RAG engine using Redis,
improving performance for frequently accessed documents and search results.
"""

import json
import hashlib
from typing import Dict, List, Optional, Any, Union, TypeVar, Generic, Type
from datetime import datetime, timedelta

import structlog
from pydantic import BaseModel

from app.config.settings import get_settings
from app.database.connection import DatabaseManager

logger = structlog.get_logger(__name__)
settings = get_settings()

T = TypeVar('T')


class CacheManager(Generic[T]):
    """Cache manager for RAG engine using Redis."""
    
    def __init__(self, db_manager: DatabaseManager, model_type: Type[T], prefix: str = "rag"):
        """Initialize the cache manager.
        
        Args:
            db_manager: Database manager instance
            model_type: Type of model to cache
            prefix: Cache key prefix
        """
        self.redis = db_manager.get_redis_client()
        self.model_type = model_type
        self.prefix = prefix
        self.default_ttl = 3600  # 1 hour default TTL
    
    async def get(self, key: str) -> Optional[T]:
        """Get item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached item or None if not found
        """
        cache_key = self._make_key(key)
        
        try:
            # Get from Redis
            data = await self.redis.get(cache_key)
            
            if not data:
                return None
            
            # Deserialize and convert to model
            json_data = json.loads(data)
            return self.model_type(**json_data)
            
        except Exception as e:
            logger.error(
                "Error getting item from cache",
                key=cache_key,
                error=str(e)
            )
            return None
    
    async def set(self, key: str, value: T, ttl: Optional[int] = None) -> bool:
        """Set item in cache.
        
        Args:
            key: Cache key
            value: Item to cache
            ttl: Time to live in seconds (None for default)
            
        Returns:
            Success status
        """
        cache_key = self._make_key(key)
        ttl = ttl if ttl is not None else self.default_ttl
        
        try:
            # Convert model to JSON
            if isinstance(value, BaseModel):
                json_data = value.dict()
            else:
                json_data = value
                
            # Serialize and store in Redis
            data = json.dumps(json_data)
            await self.redis.set(cache_key, data, ex=ttl)
            
            logger.debug(
                "Item set in cache",
                key=cache_key,
                ttl=ttl
            )
            return True
            
        except Exception as e:
            logger.error(
                "Error setting item in cache",
                key=cache_key,
                error=str(e)
            )
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Success status
        """
        cache_key = self._make_key(key)
        
        try:
            # Delete from Redis
            await self.redis.delete(cache_key)
            
            logger.debug(
                "Item deleted from cache",
                key=cache_key
            )
            return True
            
        except Exception as e:
            logger.error(
                "Error deleting item from cache",
                key=cache_key,
                error=str(e)
            )
            return False
    
    async def clear_prefix(self, sub_prefix: str) -> bool:
        """Clear all items with a specific prefix.
        
        Args:
            sub_prefix: Sub-prefix to clear
            
        Returns:
            Success status
        """
        pattern = f"{self.prefix}:{sub_prefix}:*"
        
        try:
            # Get all keys matching pattern
            keys = await self.redis.keys(pattern)
            
            if keys:
                # Delete all matching keys
                await self.redis.delete(*keys)
                
                logger.info(
                    "Cleared cache items with prefix",
                    prefix=pattern,
                    count=len(keys)
                )
            
            return True
            
        except Exception as e:
            logger.error(
                "Error clearing cache with prefix",
                prefix=pattern,
                error=str(e)
            )
            return False
    
    def _make_key(self, key: str) -> str:
        """Create a cache key with prefix.
        
        Args:
            key: Original key
            
        Returns:
            Prefixed cache key
        """
        return f"{self.prefix}:{key}"


class SearchCache:
    """Cache for search queries and results."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize the search cache.
        
        Args:
            db_manager: Database manager instance
        """
        self.redis = db_manager.get_redis_client()
        self.prefix = "rag:search"
        self.default_ttl = 1800  # 30 minutes default TTL for search results
    
    async def get_search_results(self, query: str, filters: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, Any]]]:
        """Get cached search results.
        
        Args:
            query: Search query
            filters: Search filters
            
        Returns:
            Cached search results or None if not found
        """
        cache_key = self._make_search_key(query, filters)
        
        try:
            # Get from Redis
            data = await self.redis.get(cache_key)
            
            if not data:
                return None
            
            # Deserialize
            return json.loads(data)
            
        except Exception as e:
            logger.error(
                "Error getting search results from cache",
                key=cache_key,
                error=str(e)
            )
            return None
    
    async def set_search_results(self, query: str, results: List[Dict[str, Any]], 
                               filters: Optional[Dict[str, Any]] = None, ttl: Optional[int] = None) -> bool:
        """Cache search results.
        
        Args:
            query: Search query
            results: Search results
            filters: Search filters
            ttl: Time to live in seconds (None for default)
            
        Returns:
            Success status
        """
        cache_key = self._make_search_key(query, filters)
        ttl = ttl if ttl is not None else self.default_ttl
        
        try:
            # Serialize and store in Redis
            data = json.dumps(results)
            await self.redis.set(cache_key, data, ex=ttl)
            
            logger.debug(
                "Search results cached",
                key=cache_key,
                results_count=len(results),
                ttl=ttl
            )
            return True
            
        except Exception as e:
            logger.error(
                "Error caching search results",
                key=cache_key,
                error=str(e)
            )
            return False
    
    async def invalidate_document_cache(self, document_id: str) -> bool:
        """Invalidate cache for a specific document.
        
        Args:
            document_id: Document ID
            
        Returns:
            Success status
        """
        pattern = f"{self.prefix}:doc:{document_id}:*"
        
        try:
            # Get all keys matching pattern
            keys = await self.redis.keys(pattern)
            
            if keys:
                # Delete all matching keys
                await self.redis.delete(*keys)
                
                logger.info(
                    "Invalidated document cache",
                    document_id=document_id,
                    keys_count=len(keys)
                )
            
            return True
            
        except Exception as e:
            logger.error(
                "Error invalidating document cache",
                document_id=document_id,
                error=str(e)
            )
            return False
    
    def _make_search_key(self, query: str, filters: Optional[Dict[str, Any]] = None) -> str:
        """Create a cache key for search results.
        
        Args:
            query: Search query
            filters: Search filters
            
        Returns:
            Cache key
        """
        # Normalize query
        normalized_query = query.lower().strip()
        
        # Create hash of query and filters
        key_parts = [normalized_query]
        
        if filters:
            # Sort filters by key for consistent hashing
            sorted_filters = json.dumps(filters, sort_keys=True)
            key_parts.append(sorted_filters)
        
        # Create hash
        hash_input = "|".join(key_parts)
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()
        
        return f"{self.prefix}:query:{hash_value}"