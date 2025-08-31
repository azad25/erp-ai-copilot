"""
JWT Token Service for local token validation.

This service handles JWT token decoding and validation locally without
requiring gRPC calls to the auth service on every request.
"""
import jwt
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger(__name__)


class JWTService:
    """Service for local JWT token validation."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """
        Initialize JWT service with secret key.
        
        Args:
            secret_key: JWT secret key for token validation
            algorithm: JWT algorithm (default: HS256)
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        logger.info("JWT service initialized", algorithm=algorithm)
    
    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode and validate JWT token locally.
        
        Args:
            token: JWT token string
            
        Returns:
            Dict containing token payload if valid, None otherwise
        """
        if not token:
            logger.warning("Empty token provided")
            return None
        
        try:
            # Remove Bearer prefix if present
            if token.startswith("Bearer "):
                token = token[7:]
            
            # Decode token without audience verification for now
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": True, "verify_aud": False}
            )
            
            # Check if token is expired
            exp = payload.get("exp")
            if exp:
                exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
                if datetime.now(timezone.utc) > exp_datetime:
                    logger.warning("Token expired", exp=exp_datetime)
                    return None
            
            logger.info("Token decoded successfully", 
                       user_id=payload.get("user_id"),
                       organization_id=payload.get("organization_id"))
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token", error=str(e))
            return None
        except Exception as e:
            logger.error("Token decoding error", error=str(e))
            return None
    
    def extract_user_info(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Extract user information from JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Dict containing user information if valid, None otherwise
        """
        payload = self.decode_token(token)
        if not payload:
            return None
        
        return {
            "id": payload.get("user_id"),
            "organization_id": payload.get("organization_id"),
            "email": payload.get("email"),
            "is_active": True,  # Assume active if token is valid
            "is_verified": True,  # Assume verified if token is valid
            "token_type": payload.get("token_type", "access"),
            "session_id": payload.get("session_id"),
            "ip_address": payload.get("ip_address"),
            "expires_at": payload.get("exp")
        }


# Global JWT service instance
_jwt_service: Optional[JWTService] = None


def initialize_jwt_service(secret_key: str, algorithm: str = "HS256") -> JWTService:
    """Initialize the global JWT service instance."""
    global _jwt_service
    _jwt_service = JWTService(secret_key, algorithm)
    return _jwt_service


def get_jwt_service() -> Optional[JWTService]:
    """Get the global JWT service instance."""
    return _jwt_service


def validate_token_locally(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate token using the global JWT service.
    
    Args:
        token: JWT token string
        
    Returns:
        Dict containing user information if valid, None otherwise
    """
    if not _jwt_service:
        logger.error("JWT service not initialized")
        return None
    
    return _jwt_service.extract_user_info(token)
