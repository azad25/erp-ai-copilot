"""
Handler for chat message WebSocket messages.
"""
from typing import Dict, Any, Optional
import uuid
import json
import logging

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.database.models.database import User, Message as MessageModel, Conversation as ConversationModel
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
        message: WebSocketChatMessage,
        user: User,
        db_session: AsyncSession
    ) -> None:
        """Handle a chat message."""
        try:
            # Create or get conversation
            conversation = await self._get_or_create_conversation(
                message.conversation_id, user.id, db_session
            )
            
            if not conversation:
                await self._send_error(
                    websocket,
                    "Failed to create or retrieve conversation",
                    error_code="conversation_error",
                    status_code=500
                )
                return
            
            # Save the message to the database
            message_id = str(uuid.uuid4())
            db_message = MessageModel(
                id=message_id,
                conversation_id=conversation.id,
                user_id=user.id,
                content=message.message,
                metadata=message.metadata or {}
            )
            db_session.add(db_message)
            await db_session.commit()
            
            # Process the message with the chat service
            chat_service = ChatService(db_session)
            response = await chat_service.send_message(
                conversation_id=conversation.id,
                user_id=user.id,
                message=message.message,
                metadata=message.metadata or {}
            )
            
            # Create and send the response
            chat_response = WebSocketChatResponse(
                message_id=message_id,
                conversation_id=conversation.id,
                sender_id=user.id,
                content=response.response,
                status="success",
                metadata={
                    "response_id": response.message_id,
                    "agent_type": response.agent_type,
                    **response.metadata
                }
            )
            
            await websocket.send_json(chat_response.dict())
            
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
            if conversation_id:
                # Try to get existing conversation
                result = await db_session.execute(
                    select(ConversationModel)
                    .where(ConversationModel.id == conversation_id)
                    .where(ConversationModel.user_id == user_id)
                )
                conversation = result.scalars().first()
                if conversation:
                    return conversation
            
            # Create new conversation if not found
            new_conversation = ConversationModel(
                id=conversation_id or str(uuid.uuid4()),
                user_id=user_id,
                title=f"Conversation {len(await self._get_user_conversations(user_id, db_session)) + 1}",
            )
            db_session.add(new_conversation)
            await db_session.commit()
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
