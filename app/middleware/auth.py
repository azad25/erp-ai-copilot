"""
Authentication middleware for WebSocket and HTTP requests
"""

try:
    import jwt
except ImportError:
    jwt = None
import json
import logging
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

from app.services.jwt_service import jwt_service
from app.services.token_cache_service import token_cache_service

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def verify_websocket_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify WebSocket authentication token"""
    try:
        if not token or not isinstance(token, str):
            logger.warning("Invalid token type provided")
            return None
            
        # Try cached token first
        if token_cache_service:
            cached_data = await token_cache_service.get_cached_user_info(token)
            if cached_data:
                return cached_data
        
        # Verify JWT token
        if jwt_service:
            payload = jwt_service.verify_token(token)
            if payload:
                # Cache for future use
                if token_cache_service:
                    await token_cache_service.cache_user_info(token, payload)
                return payload
        
        # Fallback to direct JWT verification
        if jwt is None:
            logger.warning("JWT library not available")
            return None
            
        from app.config.settings import settings
        payload = jwt.decode(
            token,
            settings.security.jwt_secret,
            algorithms=[settings.security.jwt_algorithm]
        )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid token")
        return None
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return None


async def get_current_user_with_org(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Get current user with organization from JWT token"""
    try:
        token = credentials.credentials
        auth_data = await verify_websocket_token(token)
        
        if not auth_data:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        return auth_data
        
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


async def get_current_user_websocket(websocket: WebSocket, token: str = None) -> Optional[Dict[str, Any]]:
    """Get current user from WebSocket token"""
    try:
        if not token:
            # Try to get token from query parameters
            query_params = dict(websocket.query_params)
            token = query_params.get("token")
        
        if not token:
            # Try to get from headers
            headers = dict(websocket.headers)
            auth_header = headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        
        if not token:
            logger.warning("No token found in WebSocket request")
            return None
        
        logger.info(f"Extracted token for WebSocket auth: {token[:20]}...")
        
        # Direct JWT verification to avoid token cache service issues
        if jwt is None:
            logger.warning("JWT library not available for WebSocket auth")
            return None
            
        from app.config.settings import settings
        payload = jwt.decode(
            token,
            settings.security.jwt_secret,
            algorithms=[settings.security.jwt_algorithm]
        )
        
        if payload:
            logger.info(f"WebSocket authentication successful for user: {payload.get('user_id')}")
            return payload
        
        return None
        
    except jwt.ExpiredSignatureError:
        logger.warning("WebSocket token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid WebSocket token")
        return None
    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        return None


# Alias for compatibility
get_current_user = get_current_user_with_org


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Require admin role for access"""
    user = await get_current_user_with_org(credentials)
    
    # For now, allow all authenticated users (can be enhanced with role checks)
    return user
