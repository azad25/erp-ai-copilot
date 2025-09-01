"""
Base WebSocket message handler.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.database import User
from app.api.websocket.connection_manager import ConnectionManager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.api.websocket.models.messages import WebSocketMessage


class BaseMessageHandler(ABC):
    """Base class for WebSocket message handlers."""
    
    def __init__(self, connection_manager: ConnectionManager):
        """Initialize the handler with a connection manager."""
        self.connection_manager = connection_manager
    
    @abstractmethod
    async def can_handle(self, message_type: str) -> bool:
        """Check if this handler can handle the given message type.
        
        Args:
            message_type: The message type to check
            
        Returns:
            bool: True if this handler can handle the message type
        """
        pass
    
    @abstractmethod
    async def handle(
        self,
        websocket: WebSocket,
        message: 'WebSocketMessage',
        user: User,
        db_session: AsyncSession
    ) -> None:
        """Handle a WebSocket message.
        
        Args:
            websocket: The WebSocket connection
            message: The message to handle
            user: The authenticated user
            db_session: Database session
        """
        pass
    
    async def _send_error(
        self,
        websocket: WebSocket,
        error_message: str,
        error_code: str = "processing_error",
        status_code: int = 400,
        **additional_data
    ) -> None:
        """Send an error response to the client.
        
        Args:
            websocket: The WebSocket connection
            error_message: Error message to send
            error_code: Error code
            status_code: HTTP status code
            **additional_data: Additional error data
        """
        from app.api.websocket.models.responses import WebSocketErrorResponse
        
        error = WebSocketErrorResponse(
            code=error_code,
            message=error_message,
            status_code=status_code,
            **additional_data
        )
        await websocket.send_json(error.dict())
