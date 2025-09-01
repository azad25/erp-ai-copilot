"""
WebSocket service for handling WebSocket connections and message routing.
"""
import json
import logging
import asyncio
from typing import Dict, Type, Optional, Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database.models.database import User
from app.database.connection import get_db_session
from app.api.websocket.connection_manager import ConnectionManager
from app.api.websocket.handlers import (
    BaseMessageHandler,
    ChatMessageHandler,
    TypingIndicatorHandler,
    PingHandler,
    SubscribeHandler,
    UnsubscribeHandler,
    HeartbeatHandler
)
from app.api.websocket.models.messages import WebSocketMessage
from app.api.websocket.exceptions import (
    WebSocketError,
    AuthenticationError,
    InvalidMessageFormat
)
from app.services.token_cache_service import get_token_cache_service, TokenCacheService
from app.database.connection import db_manager

logger = structlog.get_logger(__name__)

class WebSocketService:
    """Service for managing WebSocket connections and message handling."""
    
    def __init__(self, connection_manager: Optional[ConnectionManager] = None):
        """Initialize the WebSocket service with handlers and connection manager."""
        self.connection_manager = connection_manager or ConnectionManager()
        self.handlers: Dict[str, Type[BaseMessageHandler]] = {
            "chat_message": ChatMessageHandler,
            "ai_chat": ChatMessageHandler,  # Support both message types for compatibility
            "typing_indicator": TypingIndicatorHandler,
            "ping": PingHandler,
            "subscribe": SubscribeHandler,
            "unsubscribe": UnsubscribeHandler,
            "heartbeat": HeartbeatHandler
        }
    
    async def authenticate_connection(
        self,
        websocket: WebSocket,
        token: Optional[str] = None
    ) -> Optional[User]:
        """Authenticate a WebSocket connection using the provided token.
        
        Args:
            websocket: The WebSocket connection
            token: Authentication token
            
        Returns:
            User: Authenticated user if successful, None otherwise
        """
        if not token:
            raise AuthenticationError("Authentication token is required")
        
        try:
            # Get or create token cache service instance
            token_cache_service = get_token_cache_service()
            if not token_cache_service:
                # Fallback: get Redis client from FastAPI app state
                from fastapi import Request
                import redis.asyncio as redis
                from app.config.settings import get_settings
                
                settings = get_settings()
                redis_client = redis.Redis(
                    host=settings.redis.host,
                    port=settings.redis.port,
                    password=settings.redis.password,
                    db=settings.redis.db,
                    decode_responses=True
                )
                token_cache_service = TokenCacheService(redis_client)
            
            # Validate token using cache service
            user_info = await token_cache_service.validate_and_cache_token(token)
            if not user_info:
                raise AuthenticationError("Invalid or expired token")
            
            # Create user object from token claims
            user = User(
                id=user_info.get('id'),
                email=user_info.get('email', ''),
                organization_id=user_info.get('organization_id'),
                is_active=user_info.get('is_active', False),
                is_verified=user_info.get('is_verified', False),
                username=user_info.get('email', '').split('@')[0],
                full_name=user_info.get('full_name', '')
            )
            
            # Verify user is active and verified
            if not user.is_active or not user.is_verified:
                raise AuthenticationError("User account is not active or not verified")
                
            return user
            
        except Exception as e:
            logger.error(
                "WebSocket authentication failed",
                error=str(e),
                token_start=token[:5] + '...' if token else 'None'
            )
            if not isinstance(e, WebSocketError):
                raise AuthenticationError("Authentication failed") from e
            raise
    
    def get_message_handler(self, message_type: str) -> Optional[Type[BaseMessageHandler]]:
        """Get the appropriate handler for a message type.
        
        Args:
            message_type: The message type to get a handler for
            
        Returns:
            Type[BaseMessageHandler]: The handler class or None if not found
        """
        return self.handlers.get(message_type)
    
    def register_handler(self, message_type: str, handler: Type[BaseMessageHandler]) -> None:
        """Register a new message handler.
        
        Args:
            message_type: The message type to handle
            handler: The handler class
        """
        self.handlers[message_type] = handler
    
    async def handle_connection(self, websocket: WebSocket, token: Optional[str] = None) -> None:
        """Handle a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            token: Authentication token
        """
        connection_id = str(id(websocket))
        user = None
        
        try:
            logger.info(f"WebSocket connection attempt with token: {'present' if token else 'missing'}")
            
            # Accept the WebSocket connection first
            await websocket.accept()
            logger.info("WebSocket connection accepted successfully")
            
            # Authenticate the connection
            try:
                user = await self.authenticate_connection(websocket, token)
                logger.info(f"Authentication result: {'success' if user else 'failed'}")
            except Exception as auth_error:
                logger.error(f"Authentication error: {str(auth_error)}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Authentication failed: {str(auth_error)}"
                }))
                await websocket.close(code=1008, reason="Authentication failed")
                return
                
            if not user:
                await websocket.send_text(json.dumps({
                    "type": "error", 
                    "message": "Authentication failed"
                }))
                await websocket.close(code=1008, reason="Authentication failed")
                return
            
            await self._handle_authenticated_connection_logic(websocket, user, connection_id)
            
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected", connection_id=connection_id)
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}", connection_id=connection_id, exc_info=True)
        finally:
            # Clean up connection
            if connection_id in self.connection_manager.active_connections:
                await self.connection_manager.disconnect(connection_id)
                logger.info(f"WebSocket connection cleaned up", connection_id=connection_id)

    async def handle_authenticated_connection(self, websocket: WebSocket, token: str) -> None:
        """Handle a WebSocket connection that has already been accepted.
        
        Args:
            websocket: The already-accepted WebSocket connection
            token: Authentication token
        """
        connection_id = str(id(websocket))
        
        try:
            logger.info("Handling pre-accepted WebSocket connection")
            
            # Authenticate the connection
            user = await self.authenticate_connection(websocket, token)
            logger.info(f"Authentication result: {'success' if user else 'failed'}")
            
            if not user:
                await websocket.send_json({
                    "type": "error", 
                    "message": "Authentication failed"
                })
                await websocket.close(code=1008, reason="Authentication failed")
                return
            
            await self._handle_authenticated_connection_logic(websocket, user, connection_id)
            
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected", connection_id=connection_id)
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}", connection_id=connection_id, exc_info=True)
        finally:
            # Clean up connection
            if connection_id in self.connection_manager.active_connections:
                await self.connection_manager.disconnect(connection_id)
                logger.info(f"WebSocket connection cleaned up", connection_id=connection_id)

    async def _handle_authenticated_connection_logic(self, websocket: WebSocket, user: User, connection_id: str) -> None:
        """Handle the main connection logic for authenticated users.
        
        Args:
            websocket: The WebSocket connection
            user: Authenticated user
            connection_id: Connection identifier
        """
        # Connect the WebSocket
        await self.connection_manager.connect(websocket, connection_id, str(user.id))
        logger.info(
            "WebSocket connection established",
            connection_id=connection_id,
            user_id=user.id
        )
        
        # Main message loop
        while True:
            try:
                # Receive message with timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=300)
                
                try:
                    message_data = json.loads(data)
                    message_type = message_data.get("type")
                    
                    if not message_type:
                        raise InvalidMessageFormat("Message type is required")
                    
                    # Get the appropriate handler
                    handler_class = self.get_message_handler(message_type)
                    if not handler_class:
                        raise InvalidMessageFormat(f"Unsupported message type: {message_type}")
                    
                    # Process the message with the handler
                    async for db_session in get_db_session():
                        handler = handler_class(self.connection_manager)
                        await handler.handle(
                            websocket=websocket,
                            message=message_data,
                            user=user,
                            db_session=db_session
                        )
                        
                except json.JSONDecodeError as e:
                    logger.warning("Invalid JSON received", error=str(e))
                    await self._send_error(
                        websocket,
                        "Invalid JSON format",
                        "invalid_json",
                        4003
                    )
                    
            except asyncio.TimeoutError:
                # Send ping to check if connection is still alive
                try:
                    await websocket.send_json({"type": "ping", "timestamp": asyncio.get_event_loop().time()})
                    # Wait for pong with a short timeout
                    await asyncio.wait_for(websocket.receive_text(), timeout=5)
                except (asyncio.TimeoutError, WebSocketDisconnect):
                    logger.info("WebSocket connection timed out", connection_id=connection_id)
                    break
                    
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected", connection_id=connection_id)
                break
                
            except Exception as e:
                logger.error(
                    "Error processing WebSocket message",
                    error=str(e),
                    connection_id=connection_id,
                    user_id=user.id if user else None,
                    exc_info=True
                )
                
                if websocket.client_state.value != 3:  # 3 = DISCONNECTED state
                    await self._send_error(
                        websocket,
                        str(e),
                        getattr(e, "code", "internal_error"),
                        getattr(e, "status_code", 4000)
                    )
            
    async def _send_error(
        self,
        websocket: WebSocket,
        message: str,
        error_code: str = "internal_error",
        status_code: int = 4000
    ) -> None:
        """Send an error message to the client."""
        try:
            error_msg = {
                "type": "error",
                "code": error_code,
                "message": message,
                "status_code": status_code
            }
            await websocket.send_json(error_msg)
        except Exception as e:
            logger.error("Failed to send error message", error=str(e))
