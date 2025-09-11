"""
Heartbeat handler for WebSocket connections.
Handles heartbeat/ping messages to keep connections alive.
"""

import structlog
import json
import uuid
from typing import Dict, Any
from datetime import datetime

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.database import User
from .base_handler import BaseMessageHandler

def json_encoder(obj):
    """Custom JSON encoder for WebSocket messages."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

logger = structlog.get_logger(__name__)

class HeartbeatHandler(BaseMessageHandler):
    """Handler for heartbeat/ping messages."""
    
    async def can_handle(self, message_type: str) -> bool:
        """Check if this handler can handle the given message type."""
        return message_type in ["heartbeat", "ping"]
    
    async def handle(
        self,
        websocket: WebSocket,
        message: dict,
        user: User,
        db_session: AsyncSession
    ) -> None:
        """
        Handle heartbeat message.
        
        Args:
            websocket: WebSocket connection
            message: Message data containing heartbeat info
            user: User object from authentication
            db_session: Database session
        """
        try:
            logger.info(
                "Processing heartbeat message",
                user_id=str(user.id),
                message_data=message
            )
            
            # Extract heartbeat data
            heartbeat_data = message.get('data', {})
            status = heartbeat_data.get('status', 'ping')
            
            # Prepare heartbeat response
            response = {
                "type": "heartbeat",
                "status": "success",
                "data": {
                    "status": "pong" if status == "ping" else "alive",
                    "server_time": datetime.utcnow().isoformat(),
                    "connection_status": "active"
                },
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Heartbeat acknowledged"
            }
            
            # Send heartbeat response
            await websocket.send_text(json.dumps(response, default=json_encoder))
            
            logger.info(
                "Heartbeat response sent successfully",
                user_id=str(user.id),
                response_status=response["status"]
            )
            
        except Exception as e:
            logger.error(
                "Error processing heartbeat message",
                user_id=str(user.id),
                error=str(e),
                exc_info=True
            )
            
            # Send error response
            error_response = {
                "type": "error",
                "status": "error",
                "message": "Failed to process heartbeat",
                "data": {},
                "timestamp": datetime.utcnow().isoformat(),
                "code": "heartbeat_error",
                "details": str(e)
            }
            
            try:
                await websocket.send_text(json.dumps(error_response, default=json_encoder))
            except Exception as send_error:
                logger.error(
                    "Failed to send heartbeat error response",
                    user_id=str(user.id),
                    send_error=str(send_error)
                )


class PingHandler(HeartbeatHandler):
    """Alias for HeartbeatHandler to handle 'ping' message type."""
    pass
