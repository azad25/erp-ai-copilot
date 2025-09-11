"""
Handler for ping/pong WebSocket messages.
"""
import time
import json
import uuid
from typing import Dict, Any
from datetime import datetime

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.database import User
from app.api.websocket.handlers.base_handler import BaseMessageHandler
from app.api.websocket.models.messages import WebSocketPingMessage, WebSocketStatusMessage

def json_encoder(obj):
    """Custom JSON encoder for WebSocket messages."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

class PingHandler(BaseMessageHandler):
    """Handler for ping/pong WebSocket messages."""
    
    async def can_handle(self, message_type: str) -> bool:
        """Check if this handler can handle the message type."""
        return message_type == "ping"
    
    async def handle(
        self,
        websocket: WebSocket,
        message: WebSocketPingMessage,
        user: User,
        db_session: AsyncSession
    ) -> None:
        """Handle a ping message by responding with a pong."""
        try:
            # Calculate latency if timestamp is provided
            latency_ms = None
            if message.timestamp:
                latency_ms = int((time.time() - message.timestamp) * 1000)
            
            # Send pong response
            pong = WebSocketStatusMessage(
                type="pong",
                status="ok",
                message="pong",
                data={"latency_ms": latency_ms} if latency_ms is not None else None
            )
            await websocket.send_text(json.dumps(pong.dict(), default=json_encoder))
            
        except Exception as e:
            # Log the error but don't fail the connection
            self.logger.error(
                "Error handling ping message",
                error=str(e),
                user_id=user.id,
                exc_info=True
            )
