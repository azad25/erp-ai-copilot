"""
Handler for typing indicator WebSocket messages.
"""
from typing import Dict, Any

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.database import User
from app.api.websocket.handlers.base_handler import BaseMessageHandler
from app.api.websocket.models.messages import WebSocketTypingIndicator

class TypingIndicatorHandler(BaseMessageHandler):
    """Handler for typing indicator WebSocket messages."""
    
    async def can_handle(self, message_type: str) -> bool:
        """Check if this handler can handle the message type."""
        return message_type == "typing_indicator"
    
    async def handle(
        self,
        websocket: WebSocket,
        message: WebSocketTypingIndicator,
        user: User,
        db_session: AsyncSession
    ) -> None:
        """Handle a typing indicator message."""
        try:
            # Broadcast typing status to all connections of the user
            # (excluding the sender's connection)
            typing_message = {
                "type": "typing_indicator",
                "user_id": str(user.id),
                "is_typing": message.is_typing,
                "conversation_id": message.conversation_id
            }
            
            # Get the connection ID from the WebSocket
            connection_id = None
            for conn_id, ws in self.connection_manager.active_connections.items():
                if ws == websocket:
                    connection_id = conn_id
                    break
            
            # Broadcast to all user connections except the sender
            if connection_id and str(user.id) in self.connection_manager.user_connections:
                for conn_id in self.connection_manager.user_connections[str(user.id)]:
                    if conn_id != connection_id:  # Don't send back to sender
                        await self.connection_manager.send_json(
                            typing_message,
                            conn_id
                        )
        
        except Exception as e:
            # Log the error but don't fail the connection
            self.logger.error(
                "Error handling typing indicator",
                error=str(e),
                user_id=user.id,
                exc_info=True
            )
