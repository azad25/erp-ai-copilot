"""
Authentication service for the AI Copilot.

This module provides authentication and authorization functionality,
including user retrieval from JWT tokens and dependency injection.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config.settings import get_settings
from app.database.connection import get_db_session
from app.clients.auth_grpc import get_auth_service_client
from app.services.token_cache_service import validate_token_with_cache
from app.models.api import User

settings = get_settings()
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """
    Get the current authenticated user from JWT token using gRPC auth service.
    
    Args:
        credentials: HTTP authorization credentials containing JWT token
        db: Database session (kept for backward compatibility but not used)
        
    Returns:
        User: The authenticated user object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user info using token cache service (validates with auth service only once per token)
    user_info = await validate_token_with_cache(credentials.credentials)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create a user object with fields matching the API User model
    full_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
    user = User(
        id=user_info['id'],
        username=user_info.get('email', '').split('@')[0],  # Use email prefix as username
        email=user_info['email'],
        full_name=full_name if full_name else None,
        is_active=user_info.get('is_active', True),
        is_superuser=user_info.get('is_superuser', False),
        roles=user_info.get('roles', []),
        organization_id=user_info.get('organization_id')
    )
    
    return user


async def get_current_user_ws(token: str) -> User:
    """
    Get the current authenticated user from WebSocket token using token cache service.
    
    Args:
        token: JWT token from WebSocket connection
        
    Returns:
        User: The authenticated user object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not token:
        logger.warning("No token provided to get_current_user_ws")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
        )
    
    logger.info(f"Validating token (first 10 chars): {token[:10]}...")
    
    try:
        # Get user info using token cache service (validates with auth service only once per token)
        logger.info("Validating token with cache service...")
        user_info = await validate_token_with_cache(token)
        
        if not user_info:
            logger.warning("Token validation returned no user info")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token (no user info)",
            )
            
        logger.info(f"Token validation successful, user_id: {user_info.get('id')}")
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user_ws: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication service error: {str(e)}"
        )
    
    # Create a user object with fields matching the API User model
    full_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
    user = User(
        id=user_info['id'],
        username=user_info.get('email', '').split('@')[0],  # Use email prefix as username
        email=user_info['email'],
        full_name=full_name if full_name else None,
        is_active=user_info.get('is_active', True),
        is_superuser=user_info.get('is_superuser', False),
        roles=user_info.get('roles', []),
        organization_id=user_info.get('organization_id')
    )
    
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> Optional[User]:
    """
    Get the current authenticated user if token is provided, otherwise return None.
    
    Args:
        credentials: HTTP authorization credentials containing JWT token
        db: Database session (kept for backward compatibility but not used)
        
    Returns:
        Optional[User]: The authenticated user object or None if no valid token
    """
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None