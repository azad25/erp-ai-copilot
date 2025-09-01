"""
Handler for subscribe/unsubscribe WebSocket messages.
"""
from typing import Dict, Any, Optional
import json
import logging
from datetime import datetime

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database.models.database import User
from app.api.websocket.handlers.base_handler import BaseMessageHandler

logger = structlog.get_logger(__name__)

class SubscribeHandler(BaseMessageHandler):
    """Handler for subscribe WebSocket messages."""
    
    async def can_handle(self, message_type: str) -> bool:
        """Check if this handler can handle the message type."""
        return message_type == "subscribe"
    
    async def handle(
        self,
        websocket: WebSocket,
        message: dict,
        user: User,
        db_session: AsyncSession
    ) -> None:
        """Handle a subscribe message."""
        try:
            # Extract channel from message data
            channel = message.get("data", {}).get("channel")
            
            if not channel:
                await self._send_error(
                    websocket,
                    "Missing required field: channel",
                    error_code="validation_error",
                    status_code=400
                )
                return
            
            logger.info(
                "User subscribed to channel",
                user_id=str(user.id),
                channel=channel
            )
            
            # Send subscription confirmation
            await websocket.send_text(json.dumps({
                "type": "subscription_confirmed",
                "channel": channel,
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Successfully subscribed to {channel}"
            }))
            
        except Exception as e:
            logger.error(
                "Error handling subscribe message",
                user_id=str(user.id),
                error=str(e),
                exc_info=True
            )
            await self._send_error(
                websocket,
                f"Failed to process subscribe request: {str(e)}",
                error_code="processing_error",
                status_code=500
            )


class UnsubscribeHandler(BaseMessageHandler):
    """Handler for unsubscribe WebSocket messages."""
    
    async def can_handle(self, message_type: str) -> bool:
        """Check if this handler can handle the message type."""
        return message_type == "unsubscribe"
    
    async def handle(
        self,
        websocket: WebSocket,
        message: dict,
        user: User,
        db_session: AsyncSession
    ) -> None:
        """Handle an unsubscribe message."""
        try:
            # Extract channel from message data
            channel = message.get("data", {}).get("channel")
            
            if not channel:
                await self._send_error(
                    websocket,
                    "Missing required field: channel",
                    error_code="validation_error",
                    status_code=400
                )
                return
            
            logger.info(
                "User unsubscribed from channel",
                user_id=str(user.id),
                channel=channel
            )
            
            # Send unsubscription confirmation
            await websocket.send_text(json.dumps({
                "type": "unsubscription_confirmed",
                "channel": channel,
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Successfully unsubscribed from {channel}"
            }))
            
        except Exception as e:
            logger.error(
                "Error handling unsubscribe message",
                user_id=str(user.id),
                error=str(e),
                exc_info=True
            )
            await self._send_error(
                websocket,
                f"Failed to process unsubscribe request: {str(e)}",
                error_code="processing_error",
                status_code=500
            )
