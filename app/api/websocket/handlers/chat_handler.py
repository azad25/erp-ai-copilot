"""
Handler for chat message WebSocket messages.
"""
from typing import Dict, Any, Optional
import uuid
import json
import logging
from datetime import datetime

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.database.models.database import User, MessageTable as MessageModel, ConversationTable as ConversationModel
from app.services.chat_service import ChatService
from app.api.websocket.handlers.base_handler import BaseMessageHandler
from app.api.websocket.models.messages import WebSocketChatMessage, WebSocketStatusMessage
from app.api.websocket.models.responses import WebSocketChatResponse, WebSocketErrorResponse

logger = structlog.get_logger(__name__)

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
            
            if not conversation_id or not message_text:
                await self._send_error(
                    websocket,
                    "Missing required fields: conversation_id and message",
                    error_code="validation_error",
                    status_code=400
                )
                return
            
            # Create or get conversation
            conversation = await self._get_or_create_conversation(
                conversation_id, user.id, db_session
            )
            
            if not conversation:
                await self._send_error(
                    websocket,
                    "Failed to create or retrieve conversation",
                    error_code="conversation_error",
                    status_code=500
                )
                return
            
            # Message will be saved by ChatService, so skip saving here
            logger.info(
                "Processing chat message",
                conversation_id=str(conversation.id),
                user_id=user.id,
                content_length=len(message_text)
            )
            
            # Process the message with the chat service
            chat_service = ChatService(db_session)
            response = await chat_service.send_message(
                conversation_id=conversation.id,
                user_id=user.id,
                message=message_text,
                metadata=metadata
            )
            
            # Create and send the response as a simple dict
            response_data = {
                "type": "chat_response",
                "status": "success",
                "message_id": str(getattr(response, 'message_id', uuid.uuid4())),
                "conversation_id": str(conversation.id),
                "sender_id": str(user.id),
                "content": response.content,
                "timestamp": datetime.utcnow().isoformat(),
                "data": {},
                "metadata": {
                    "response_id": str(getattr(response, 'message_id', response.conversation_id)),
                    "model_used": str(response.metadata.get("model_used", "unknown")),
                    "tokens_used": response.metadata.get("tokens_used", 0)
                }
            }
            
            await websocket.send_json(response_data)
            
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
    
    async def _get_or_create_conversation(
        self, 
        conversation_id: Optional[str], 
        user_id: str,
        db_session: AsyncSession
    ) -> Optional[ConversationModel]:
        """Get or create a conversation."""
        try:
            import uuid as uuid_lib
            
            # Convert string IDs to UUID objects
            if conversation_id:
                try:
                    conv_uuid = uuid_lib.UUID(conversation_id)
                except ValueError:
                    # If conversation_id is not a valid UUID, generate a new one
                    conv_uuid = uuid_lib.uuid4()
            else:
                conv_uuid = uuid_lib.uuid4()
                
            try:
                user_uuid = uuid_lib.UUID(user_id)
            except ValueError:
                # If user_id is not a valid UUID, generate a new one based on string
                user_uuid = uuid_lib.uuid5(uuid_lib.NAMESPACE_DNS, user_id)
            
            if conversation_id:
                # Try to get existing conversation
                result = await db_session.execute(
                    select(ConversationModel)
                    .where(ConversationModel.id == conv_uuid)
                    .where(ConversationModel.user_id == user_uuid)
                )
                conversation = result.scalars().first()
                if conversation:
                    return conversation
            
            # Create new conversation in database
            new_conversation = ConversationModel(
                id=conv_uuid,
                user_id=user_uuid,
                organization_id=uuid_lib.UUID("00000000-0000-0000-0000-000000000000"),
                title="Chat Conversation"
            )
            db_session.add(new_conversation)
            await db_session.commit()
            
            logger.info(
                "Created new conversation in database",
                conversation_id=str(conv_uuid),
                user_id=user_id
            )
            
            return new_conversation
            
        except Exception as e:
            logger.error(
                "Error getting or creating conversation",
                error=str(e),
                user_id=user_id,
                conversation_id=conversation_id,
                exc_info=True
            )
            return None
    
    async def _get_user_conversations(
        self, 
        user_id: str, 
        db_session: AsyncSession
    ) -> list:
        """Get all conversations for a user."""
        result = await db_session.execute(
            select(ConversationModel)
            .where(ConversationModel.user_id == user_id)
            .order_by(ConversationModel.created_at.desc())
        )
        return result.scalars().all()
