"""
Handler for chat message WebSocket messages.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import json
import uuid

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database.models.database import User
from app.services.chat_service import ChatService
from app.api.websocket.handlers.base_handler import BaseMessageHandler

logger = structlog.get_logger(__name__)

def json_encoder(obj):
    """Custom JSON encoder for WebSocket messages."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif hasattr(obj, '__dict__'):
        # Handle objects with dict representation
        return {k: json_encoder(v) if isinstance(v, (datetime, uuid.UUID)) else v 
                for k, v in obj.__dict__.items() if not k.startswith('_')}
    return str(obj)

class ChatMessageHandler(BaseMessageHandler):
    """Handler for chat message WebSocket messages."""
    
    async def can_handle(self, message_type: str) -> bool:
        """Check if this handler can handle the message type."""
        return message_type == "chat_message"
    
    async def handle(
        self,
        websocket: WebSocket,
        message: dict,
        user: User,
        db_session: AsyncSession
    ) -> None:
        """Handle a chat message."""
        try:
            # Extract message data from dict - handle both direct and nested formats
            data = message.get("data", {})
            conversation_id = message.get("conversation_id") or data.get("conversationId") or data.get("conversation_id")
            message_text = message.get("message") or data.get("message")
            metadata = message.get("metadata", data.get("context", {}))
            
            if not message_text:
                await self._send_error(
                    websocket,
                    "Missing required field: message",
                    error_code="validation_error",
                    status_code=400
                )
                return
            
            # Process the message with ChatService - it handles all conversation management
            chat_service = ChatService()
            
            logger.info(
                "Processing WebSocket chat message",
                conversation_id=conversation_id,
                user_id=user.id,
                content_length=len(message_text)
            )
            
            # Stream the response with reasoning steps
            async for stream_response in chat_service.send_message_stream(
                conversation_id=conversation_id,
                user_id=str(user.id),
                message=message_text,
                metadata=metadata,
                organization_id=str(getattr(user, 'organization_id', '00000000-0000-0000-0000-000000000000'))
            ):
                # Send each streaming chunk to the frontend
                if stream_response.type == "reasoning_step":
                    # Send reasoning step with proper formatting
                    reasoning_data = {
                        "type": "reasoning_step",
                        "conversation_id": str(stream_response.conversation_id) if stream_response.conversation_id else None,
                        "message_id": str(stream_response.message_id) if stream_response.message_id else None,
                        "timestamp": datetime.utcnow().isoformat(),
                        **stream_response.metadata  # Include all reasoning step data
                    }
                    await websocket.send_json(reasoning_data)
                    
                elif stream_response.type == "chunk":
                    # Send text chunks for typewriter effect
                    chunk_data = {
                        "type": "chunk",
                        "conversation_id": str(stream_response.conversation_id) if stream_response.conversation_id else None,
                        "message_id": str(stream_response.message_id) if stream_response.message_id else None,
                        "content": stream_response.content,
                        "is_complete": getattr(stream_response, 'is_complete', False),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await websocket.send_json(chunk_data)
                    
                elif stream_response.type == "start":
                    # Send processing started indicator
                    start_data = {
                        "type": "processing_started",
                        "conversation_id": str(stream_response.conversation_id) if stream_response.conversation_id else None,
                        "message_id": str(stream_response.message_id) if stream_response.message_id else None,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await websocket.send_json(start_data)
                    
                elif stream_response.type == "error":
                    # Send error message
                    error_data = {
                        "type": "error",
                        "conversation_id": str(stream_response.conversation_id) if stream_response.conversation_id else None,
                        "message_id": str(stream_response.message_id) if stream_response.message_id else None,
                        "content": stream_response.content,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await websocket.send_json(error_data)
            
            # Send completion message to indicate streaming is finished
            completion_data = {
                "type": "final_response",
                "conversation_id": str(conversation_id) if conversation_id else None,
                "message_id": "completion",
                "content": "",  # Content was already sent in chunks
                "timestamp": datetime.utcnow().isoformat(),
                "status": "completed"
            }
            await websocket.send_json(completion_data)
            
        except Exception as e:
            logger.error(
                "Error processing chat message",
                error=str(e),
                user_id=user.id,
                conversation_id=getattr(message, 'conversation_id', 'unknown'),
                exc_info=True
            )
            await self._send_error(
                websocket,
                f"Failed to process message: {str(e)}",
                error_code="message_processing_error",
                status_code=500
            )
    
    # Removed redundant conversation management methods
    # ChatService now handles all conversation operations
