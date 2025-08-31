"""
gRPC client for the Auth Service.

This module provides a client to interact with the Auth Service gRPC server.
"""
import grpc
import logging
from typing import Optional, Dict, Any
from datetime import datetime

# Import generated gRPC code
from app.proto.generated.auth.v1 import auth_pb2 as pb
from app.proto.generated.auth.v1 import auth_pb2_grpc as pb_grpc
from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AuthServiceClient:
    """gRPC client for the Auth Service."""
    
    def __init__(self):
        """Initialize the Auth Service gRPC client."""
        self.channel = None
        self.stub = None
        self._connect()
    
    def _connect(self):
        """Establish connection to the Auth Service gRPC server."""
        try:
            # Log the connection details for debugging
            logger.info(f"Attempting to connect to Auth Service at {settings.AUTH_SERVICE_GRPC_URL}")
            logger.info(f"Auth Service host: {settings.auth_service.host}")
            logger.info(f"Auth Service port: {settings.auth_service.port}")
            logger.info(f"Auth Service use_ssl: {settings.auth_service.use_ssl}")
            
            # Create insecure channel for now, consider adding TLS in production
            self.channel = grpc.aio.insecure_channel(
                settings.AUTH_SERVICE_GRPC_URL,
                options=[
                    ('grpc.max_send_message_length', 50 * 1024 * 1024),
                    ('grpc.max_receive_message_length', 50 * 1024 * 1024),
                    ('grpc.keepalive_time_ms', 30000),
                ]
            )
            self.stub = pb_grpc.AuthServiceStub(self.channel)
            logger.info(f"Successfully connected to Auth Service at {settings.AUTH_SERVICE_GRPC_URL}")
            
            # Note: Health check will be done lazily when first RPC call is made
            logger.info("gRPC client initialized, connection will be tested on first use")
                
        except Exception as e:
            logger.error(f"Failed to connect to Auth Service: {str(e)}", exc_info=True)
            raise
    
    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a JWT token with the Auth Service.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Dict containing user information if token is valid, None otherwise
        """
        if not token:
            logger.warning("Empty token provided for validation")
            return None
        
        # Log token details (redact actual token for security)
        logger.info(f"Validating token (first 10 chars): {token[:10]}...")
        
        try:
            # Log the request being made
            logger.info("Creating ValidateTokenRequest...")
            request = pb.ValidateTokenRequest(token=token)
            
            # Log the gRPC call
            logger.info(f"Calling ValidateToken RPC on stub: {self.stub}")
            logger.info(f"gRPC channel state: {self.channel.get_state(try_to_connect=True)}")
            
            # Make the gRPC call
            response = await self.stub.ValidateToken(request)
            logger.info(f"Received response from Auth Service: valid={response.valid}")
            
            if not response.valid:
                logger.warning(f"Token validation failed. Error: {response.error}")
                return None
                
            # Log successful validation
            logger.info(f"Token validation successful for user_id={response.user_id}")
            logger.info(f"Organization ID: {response.organization_id}")
            logger.info(f"Email: {response.email}")
            
            # Prepare user info
            user_info = {
                'user_id': response.user_id,
                'organization_id': response.organization_id,
                'email': response.email,
                'expires_at': response.expires_at.ToDatetime() if response.HasField('expires_at') else None
            }
            
            logger.info(f"Returning user info: {user_info}")
            return user_info
            
        except grpc.RpcError as e:
            logger.error(f"gRPC error validating token: {e.code()}: {e.details()}")
            logger.error(f"gRPC debug error string: {e.debug_error_string()}")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error validating token: {str(e)}", exc_info=True)
            return None
    
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information by user ID.
        
        Args:
            user_id: ID of the user to retrieve
            
        Returns:
            Dict containing user information if found, None otherwise
        """
        try:
            request = pb.GetUserRequest(user_id=user_id)
            response = await self.stub.GetUser(request)
            
            if not response.user:
                logger.warning(f"User not found: {user_id}")
                return None
                
            return self._convert_user_proto_to_dict(response.user)
            
        except grpc.RpcError as e:
            logger.error(f"gRPC error getting user: {e.code()}: {e.details()}")
            return None
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}", exc_info=True)
            return None
    
    async def check_permission(self, user_id: str, resource: str, action: str) -> bool:
        """
        Check if a user has permission to perform an action on a resource.
        
        Args:
            user_id: ID of the user
            resource: Resource to check permission for
            action: Action to check permission for
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        try:
            request = pb.CheckPermissionRequest(
                user_id=user_id,
                resource=resource,
                action=action
            )
            response = await self.stub.CheckPermission(request)
            return response.has_permission
            
        except grpc.RpcError as e:
            logger.error(f"gRPC error checking permission: {e.code()}: {e.details()}")
            return False
        except Exception as e:
            logger.error(f"Error checking permission: {str(e)}", exc_info=True)
            return False
    
    def _convert_user_proto_to_dict(self, user_proto) -> Dict[str, Any]:
        """
        Convert a User proto message to a dictionary.
        
        Args:
            user_proto: User proto message
            
        Returns:
            Dict containing user information
        """
        return {
            'id': user_proto.id,
            'organization_id': user_proto.organization_id,
            'email': user_proto.email,
            'first_name': user_proto.first_name,
            'last_name': user_proto.last_name,
            'is_active': user_proto.is_active,
            'is_verified': user_proto.is_verified,
            'last_login_at': user_proto.last_login_at.ToDatetime() if user_proto.HasField('last_login_at') else None,
            'created_at': user_proto.created_at.ToDatetime() if user_proto.HasField('created_at') else None,
            'updated_at': user_proto.updated_at.ToDatetime() if user_proto.HasField('updated_at') else None
        }
    
    async def close(self):
        """Close the gRPC channel."""
        if self.channel:
            await self.channel.close()
            logger.info("Closed Auth Service gRPC channel")


# Singleton instance
_auth_service_client = None


def get_auth_service_client() -> AuthServiceClient:
    """Get or create the Auth Service client singleton instance."""
    global _auth_service_client
    if _auth_service_client is None:
        _auth_service_client = AuthServiceClient()
    return _auth_service_client


async def close_auth_service_client():
    """Close the Auth Service client if it exists."""
    global _auth_service_client
    if _auth_service_client is not None:
        await _auth_service_client.close()
        _auth_service_client = None
