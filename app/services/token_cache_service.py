"""
Token Cache Service for caching validated tokens in Redis.

This service caches validated user tokens to avoid repeated gRPC calls
to the auth service for the same user tokens.
"""
import json
import hashlib
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import structlog
import redis.asyncio as redis
from app.clients.auth_grpc import get_auth_service_client
from app.services.jwt_service import get_jwt_service

logger = structlog.get_logger(__name__)


class TokenCacheService:
    """Service for caching validated tokens in Redis."""
    
    def __init__(self, redis_client: redis.Redis, cache_ttl_minutes: int = 30):
        """
        Initialize token cache service.
        
        Args:
            redis_client: Redis client instance
            cache_ttl_minutes: Cache TTL in minutes (default: 30)
        """
        self.redis_client = redis_client
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.cache_prefix = "token_cache:"
        logger.info("Token cache service initialized", ttl_minutes=cache_ttl_minutes)
    
    def _get_token_hash(self, token: str) -> str:
        """Generate a hash for the token to use as cache key."""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def _get_cache_key(self, token: str) -> str:
        """Get Redis cache key for token."""
        token_hash = self._get_token_hash(token)
        return f"{self.cache_prefix}{token_hash}"
    
    async def get_cached_user_info(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get cached user info for token.
        
        Args:
            token: JWT token string
            
        Returns:
            Dict containing cached user info if found, None otherwise
        """
        if not token:
            return None
        
        try:
            cache_key = self._get_cache_key(token)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                user_info = json.loads(cached_data)
                logger.info("Token found in cache", 
                           user_id=user_info.get('id'),
                           cache_key=cache_key[:16] + "...")
                return user_info
            
            logger.debug("Token not found in cache", cache_key=cache_key[:16] + "...")
            return None
            
        except Exception as e:
            logger.error("Error retrieving token from cache", error=str(e))
            return None
    
    async def cache_user_info(self, token: str, user_info: Dict[str, Any]) -> bool:
        """
        Cache user info for token.
        
        Args:
            token: JWT token string
            user_info: User information to cache
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not token or not user_info:
            return False
        
        try:
            cache_key = self._get_cache_key(token)
            cached_data = json.dumps(user_info)
            
            # Set with TTL
            await self.redis_client.setex(
                cache_key,
                int(self.cache_ttl.total_seconds()),
                cached_data
            )
            
            logger.info("Token cached successfully", 
                       user_id=user_info.get('id'),
                       cache_key=cache_key[:16] + "...",
                       ttl_seconds=int(self.cache_ttl.total_seconds()))
            return True
            
        except Exception as e:
            logger.error("Error caching token", error=str(e))
            return False
    
    async def validate_and_cache_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate token with auth service and cache the result.
        Falls back to local JWT validation if auth service fails.
        
        Args:
            token: JWT token string
            
        Returns:
            Dict containing user info if valid, None otherwise
        """
        if not token:
            logger.warning("Empty token provided for validation")
            return None
        
        # Check cache first
        cached_user_info = await self.get_cached_user_info(token)
        if cached_user_info:
            logger.info("Using cached token validation", user_id=cached_user_info.get('id'))
            return cached_user_info
        
        # Not in cache, try auth service first
        try:
            logger.info("Attempting to validate token with auth service")
            auth_client = get_auth_service_client()
            
            if not auth_client or not hasattr(auth_client, 'validate_token'):
                logger.warning("Auth client not properly initialized, falling back to local validation")
                return await self._fallback_to_local_validation(token)
            
            # Validate token with auth service with timeout
            try:
                user_info = await asyncio.wait_for(auth_client.validate_token(token), timeout=5.0)
                if not user_info:
                    logger.warning("Auth service returned empty response")
                    return await self._fallback_to_local_validation(token)
                
                # Get full user details from auth service
                user_details = await asyncio.wait_for(
                    auth_client.get_user(user_info['user_id']), 
                    timeout=5.0
                )
                
                if not user_details:
                    logger.warning("User not found in auth service", user_id=user_info['user_id'])
                    return await self._fallback_to_local_validation(token)
                
                # Prepare user info for caching
                cached_user_info = {
                    "id": user_details.get('id'),
                    "email": user_details.get('email', 'unknown@example.com'),
                    "organization_id": user_details.get('organization_id'),
                    "is_active": user_details.get('is_active', False),
                    "is_verified": user_details.get('is_verified', False),
                    "validated_at": datetime.utcnow().isoformat(),
                    "validation_method": "auth_service"
                }
                
                # Cache the validated user info
                await self.cache_user_info(token, cached_user_info)
                
                logger.info("Token validated and cached via auth service", 
                          user_id=cached_user_info['id'],
                          email=cached_user_info['email'])
                
                return cached_user_info
                
            except asyncio.TimeoutError:
                logger.warning("Auth service request timed out, falling back to local validation")
                return await self._fallback_to_local_validation(token)
                
            except Exception as e:
                logger.error(f"Error during auth service validation: {str(e)}", exc_info=True)
                return await self._fallback_to_local_validation(token)
            
        except Exception as e:
            logger.error(f"Unexpected error in validate_and_cache_token: {str(e)}", exc_info=True)
            return await self._fallback_to_local_validation(token)
    
    async def _fallback_to_local_validation(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Fallback to local JWT validation when auth service fails.
        
        Args:
            token: JWT token string
            
        Returns:
            Dict containing user info if valid, None otherwise
        """
        try:
            logger.info("Falling back to local JWT validation")
            jwt_service = get_jwt_service()
            if not jwt_service:
                logger.warning("JWT service not available for fallback, initializing...")
                from app.services.jwt_service import initialize_jwt_service
                from app.core.config import settings
                initialize_jwt_service(settings.JWT_SECRET)
                jwt_service = get_jwt_service()
            
            # Extract user info from JWT token locally
            user_info = jwt_service.extract_user_info(token)
            if not user_info:
                logger.warning("Local JWT validation failed")
                return None
            
            # Prepare user info for caching
            cached_user_info = {
                "id": user_info['id'],
                "email": user_info.get('email', 'unknown@example.com'),
                "organization_id": user_info.get('organization_id'),
                "is_active": user_info.get('is_active', True),
                "is_verified": user_info.get('is_verified', True),
                "validated_at": datetime.utcnow().isoformat(),
                "validation_method": "local_jwt"
            }
            
            # Cache the validated user info
            await self.cache_user_info(token, cached_user_info)
            
            logger.info("Token validated and cached via local JWT", 
                       user_id=cached_user_info['id'],
                       validation_method="local_jwt")
            
            return cached_user_info
            
        except Exception as e:
            logger.error("Error in local JWT validation fallback", error=str(e))
            return None
    
    async def invalidate_token(self, token: str) -> bool:
        """
        Invalidate cached token.
        
        Args:
            token: JWT token string
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        if not token:
            return False
        
        try:
            cache_key = self._get_cache_key(token)
            result = await self.redis_client.delete(cache_key)
            
            if result:
                logger.info("Token invalidated from cache", cache_key=cache_key[:16] + "...")
                return True
            else:
                logger.debug("Token not found in cache for invalidation", cache_key=cache_key[:16] + "...")
                return False
                
        except Exception as e:
            logger.error("Error invalidating token from cache", error=str(e))
            return False
    
    async def clear_cache(self) -> bool:
        """
        Clear all cached tokens.
        
        Returns:
            True if cleared successfully, False otherwise
        """
        try:
            pattern = f"{self.cache_prefix}*"
            keys = await self.redis_client.keys(pattern)
            
            if keys:
                await self.redis_client.delete(*keys)
                logger.info("Token cache cleared", keys_deleted=len(keys))
            else:
                logger.info("No tokens found in cache to clear")
            
            return True
            
        except Exception as e:
            logger.error("Error clearing token cache", error=str(e))
            return False


# Global token cache service instance
_token_cache_service: Optional[TokenCacheService] = None


def initialize_token_cache_service(redis_client: redis.Redis, cache_ttl_minutes: int = 30) -> TokenCacheService:
    """Initialize the global token cache service instance."""
    global _token_cache_service
    _token_cache_service = TokenCacheService(redis_client, cache_ttl_minutes)
    return _token_cache_service


def get_token_cache_service() -> Optional[TokenCacheService]:
    """Get the global token cache service instance."""
    return _token_cache_service


async def validate_token_with_cache(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate token using the global token cache service.
    
    Args:
        token: JWT token string
        
    Returns:
        Dict containing user information if valid, None otherwise
    """
    if not _token_cache_service:
        logger.error("Token cache service not initialized")
        return None
    
    return await _token_cache_service.validate_and_cache_token(token)
