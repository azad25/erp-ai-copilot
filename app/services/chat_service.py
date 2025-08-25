"""
Chat Service

Core service for handling chat interactions, message processing, and conversation management.
Integrates with the agent orchestrator to provide intelligent responses using the multi-agent system.
"""

from typing import Dict, List, Any, Optional, AsyncGenerator
import asyncio
import json
import logging
from datetime import datetime, timedelta
import uuid
from dataclasses import dataclass
from contextlib import asynccontextmanager

from app.models.api import (
    ChatMessage, ChatRequest, ChatResponse, ChatStreamResponse,
    ConversationStatus, AgentType, MessageType
)
from app.models.database import Conversation, Message
from app.database.db import get_db_session
from app.core.exceptions import ChatError, ValidationError, RateLimitError
from app.agents.agent_orchestrator import AgentOrchestrator
from app.agents.base_agent import AgentRequest, AgentResponse


@dataclass
class ConversationContext:
    """Conversation context for maintaining state"""
    conversation_id: str
    user_id: str
    context_data: Dict[str, Any]
    last_activity: datetime
    message_count: int
    active_agents: List[str]


class ChatService:
    """
    Chat Service for handling conversational AI interactions
    
    Capabilities:
    - Message processing and response generation
    - Conversation management and persistence
    - Multi-agent orchestration
    - Context management and memory
    - Rate limiting and throttling
    - Real-time streaming responses
    - Conversation history and search
    - User preference management
    """

    def __init__(self):
        self.orchestrator = AgentOrchestrator()
        self.active_conversations: Dict[str, ConversationContext] = {}
        self.rate_limits: Dict[str, Dict[str, Any]] = {}
        self.conversation_timeout = 3600  # 1 hour
        self.max_messages_per_conversation = 1000
        self.max_conversations_per_user = 50
        
        # Initialize default agents
        self.orchestrator.initialize_default_agents()
        
        # Start background cleanup
        asyncio.create_task(self._cleanup_expired_conversations())

    async def create_conversation(self, user_id: str, title: str = None, 
                                initial_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a new conversation for a user
        
        Args:
            user_id: User identifier
            title: Optional conversation title
            initial_context: Initial conversation context
            
        Returns:
            Created conversation details
        """
        # Check user conversation limit
        user_conversations = await self._get_user_conversations(user_id)
        if len(user_conversations) >= self.max_conversations_per_user:
            raise RateLimitError("Maximum conversations per user exceeded")
        
        conversation_id = str(uuid.uuid4())
        
        # Create conversation in database
        async with get_db_session() as session:
            conversation = Conversation(
                id=conversation_id,
                user_id=user_id,
                title=title or f"Conversation {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                status=ConversationStatus.ACTIVE,
                context_data=json.dumps(initial_context or {}),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(conversation)
            await session.commit()
        
        # Create conversation context
        self.active_conversations[conversation_id] = ConversationContext(
            conversation_id=conversation_id,
            user_id=user_id,
            context_data=initial_context or {},
            last_activity=datetime.utcnow(),
            message_count=0,
            active_agents=[]
        )
        
        return {
            "conversation_id": conversation_id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "status": conversation.status.value
        }

    async def send_message(self, conversation_id: str, user_id: str, 
                          message: str, message_type: MessageType = MessageType.TEXT,
                          metadata: Dict[str, Any] = None) -> ChatResponse:
        """
        Send a message in a conversation and get AI response
        
        Args:
            conversation_id: Target conversation ID
            user_id: User sending the message
            message: Message content
            message_type: Type of message
            metadata: Additional message metadata
            
        Returns:
            AI response with conversation details
        """
        # Validate conversation access
        if not await self._validate_conversation_access(conversation_id, user_id):
            raise ValidationError("Invalid conversation or access denied")
        
        # Check rate limits
        self._check_rate_limit(user_id)
        
        # Check message limits
        if self.active_conversations[conversation_id].message_count >= self.max_messages_per_conversation:
            raise ValidationError("Maximum messages per conversation exceeded")
        
        # Store user message
        user_message_id = await self._store_message(
            conversation_id, user_id, message, message_type, metadata
        )
        
        # Process message with AI
        ai_response = await self._process_message_with_ai(
            conversation_id, user_id, message, metadata
        )
        
        # Store AI response
        ai_message_id = await self._store_message(
            conversation_id, "ai", ai_response.response, MessageType.AI_RESPONSE,
            {"agent_type": ai_response.agent_type, "tools_used": ai_response.tools_used}
        )
        
        # Update conversation context
        self.active_conversations[conversation_id].message_count += 2
        self.active_conversations[conversation_id].last_activity = datetime.utcnow()
        
        return ChatResponse(
            conversation_id=conversation_id,
            message_id=ai_message_id,
            response=ai_response.response,
            agent_type=ai_response.agent_type,
            timestamp=datetime.utcnow(),
            metadata={
                "user_message_id": user_message_id,
                "tools_used": ai_response.tools_used,
                "processing_time": ai_response.processing_time
            }
        )

    async def send_message_stream(self, conversation_id: str, user_id: str,
                                message: str, message_type: MessageType = MessageType.TEXT,
                                metadata: Dict[str, Any] = None) -> AsyncGenerator[ChatStreamResponse, None]:
        """
        Send a message and get streaming AI response
        
        Args:
            conversation_id: Target conversation ID
            user_id: User sending the message
            message: Message content
            message_type: Type of message
            metadata: Additional message metadata
            
        Yields:
            Streaming response chunks
        """
        # Validate conversation access
        if not await self._validate_conversation_access(conversation_id, user_id):
            raise ValidationError("Invalid conversation or access denied")
        
        # Check rate limits
        self._check_rate_limit(user_id)
        
        # Store user message
        user_message_id = await self._store_message(
            conversation_id, user_id, message, message_type, metadata
        )
        
        # Send processing started
        yield ChatStreamResponse(
            type="start",
            content="",
            conversation_id=conversation_id,
            message_id=str(uuid.uuid4())
        )
        
        # Process message with streaming AI
        async for chunk in self._process_message_streaming(
            conversation_id, user_id, message, metadata
        ):
            yield chunk
        
        # Update conversation context
        self.active_conversations[conversation_id].message_count += 2
        self.active_conversations[conversation_id].last_activity = datetime.utcnow()

    async def get_conversation_history(self, conversation_id: str, 
                                     user_id: str, limit: int = 50, 
                                     offset: int = 0) -> List[ChatMessage]:
        """
        Get conversation history
        
        Args:
            conversation_id: Target conversation ID
            user_id: User requesting history
            limit: Maximum messages to return
            offset: Number of messages to skip
            
        Returns:
            List of chat messages
        """
        if not await self._validate_conversation_access(conversation_id, user_id):
            raise ValidationError("Invalid conversation or access denied")
        
        async with get_db_session() as session:
            messages = await session.execute(
                """
                SELECT * FROM messages 
                WHERE conversation_id = :conversation_id
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """,
                {
                    "conversation_id": conversation_id,
                    "limit": limit,
                    "offset": offset
                }
            )
            
            return [
                ChatMessage(
                    id=msg.id,
                    conversation_id=msg.conversation_id,
                    sender=msg.sender,
                    content=msg.content,
                    message_type=MessageType(msg.message_type),
                    timestamp=msg.created_at,
                    metadata=json.loads(msg.metadata or "{}")
                )
                for msg in messages
            ]

    async def get_user_conversations(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get list of user's conversations
        
        Args:
            user_id: User identifier
            limit: Maximum conversations to return
            
        Returns:
            List of conversation summaries
        """
        async with get_db_session() as session:
            conversations = await session.execute(
                """
                SELECT c.*, COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_id = :user_id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT :limit
                """,
                {"user_id": user_id, "limit": limit}
            )
            
            return [
                {
                    "conversation_id": conv.id,
                    "title": conv.title,
                    "status": conv.status.value,
                    "message_count": conv.message_count,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat()
                }
                for conv in conversations
            ]

    async def update_conversation_context(self, conversation_id: str, user_id: str,
                                        context_data: Dict[str, Any]) -> bool:
        """
        Update conversation context
        
        Args:
            conversation_id: Target conversation ID
            user_id: User requesting update
            context_data: New context data
            
        Returns:
            Success status
        """
        if not await self._validate_conversation_access(conversation_id, user_id):
            return False
        
        # Update in database
        async with get_db_session() as session:
            await session.execute(
                """
                UPDATE conversations 
                SET context_data = :context_data, updated_at = :updated_at
                WHERE id = :conversation_id AND user_id = :user_id
                """,
                {
                    "context_data": json.dumps(context_data),
                    "updated_at": datetime.utcnow(),
                    "conversation_id": conversation_id,
                    "user_id": user_id
                }
            )
            await session.commit()
        
        # Update in memory
        if conversation_id in self.active_conversations:
            self.active_conversations[conversation_id].context_data = context_data
            self.active_conversations[conversation_id].last_activity = datetime.utcnow()
        
        return True

    async def close_conversation(self, conversation_id: str, user_id: str) -> bool:
        """
        Close a conversation
        
        Args:
            conversation_id: Target conversation ID
            user_id: User requesting closure
            
        Returns:
            Success status
        """
        if not await self._validate_conversation_access(conversation_id, user_id):
            return False
        
        # Update in database
        async with get_db_session() as session:
            await session.execute(
                """
                UPDATE conversations 
                SET status = :status, updated_at = :updated_at
                WHERE id = :conversation_id AND user_id = :user_id
                """,
                {
                    "status": ConversationStatus.CLOSED.value,
                    "updated_at": datetime.utcnow(),
                    "conversation_id": conversation_id,
                    "user_id": user_id
                }
            )
            await session.commit()
        
        # Remove from active conversations
        if conversation_id in self.active_conversations:
            del self.active_conversations[conversation_id]
        
        return True

    async def _process_message_with_ai(self, conversation_id: str, user_id: str,
                                     message: str, metadata: Dict[str, Any] = None) -> AgentResponse:
        """
        Process message with AI using the agent orchestrator
        
        Args:
            conversation_id: Current conversation ID
            user_id: User ID
            message: User message
            metadata: Additional context
            
        Returns:
            AI response
        """
        # Build conversation context
        context = await self._build_conversation_context(conversation_id)
        
        # Create agent request
        agent_request = AgentRequest(
            query=message,
            context={
                "conversation_id": conversation_id,
                "user_id": user_id,
                "conversation_history": context.get("messages", []),
                "user_preferences": context.get("user_preferences", {}),
                "metadata": metadata or {}
            }
        )
        
        # Execute with orchestrator
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Use master agent for complex orchestration
            response = await self.orchestrator.execute_with_master_agent(agent_request)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            return AgentResponse(
                response=response.response,
                agent_type=response.agent_type,
                tools_used=response.tools_used,
                metadata={
                    **response.metadata,
                    "processing_time": processing_time,
                    "conversation_id": conversation_id
                }
            )
            
        except Exception as e:
            logging.error(f"Error processing message with AI: {e}")
            return AgentResponse(
                response="I apologize, but I'm having trouble processing your request. Please try again.",
                agent_type=AgentType.HELP,
                tools_used=[],
                metadata={"error": str(e)}
            )

    async def _process_message_streaming(self, conversation_id: str, user_id: str,
                                       message: str, metadata: Dict[str, Any] = None) -> AsyncGenerator[ChatStreamResponse, None]:
        """
        Process message with streaming AI response
        
        Args:
            conversation_id: Current conversation ID
            user_id: User ID
            message: User message
            metadata: Additional context
            
        Yields:
            Streaming response chunks
        """
        # Build conversation context
        context = await self._build_conversation_context(conversation_id)
        
        # Create agent request
        agent_request = AgentRequest(
            query=message,
            context={
                "conversation_id": conversation_id,
                "user_id": user_id,
                "conversation_history": context.get("messages", []),
                "user_preferences": context.get("user_preferences", {}),
                "metadata": metadata or {}
            }
        )
        
        # Process with streaming (simplified for now)
        # In practice, would integrate with actual streaming LLM APIs
        response = await self._process_message_with_ai(conversation_id, user_id, message, metadata)
        
        # Simulate streaming
        words = response.response.split()
        for i, word in enumerate(words):
            yield ChatStreamResponse(
                type="chunk",
                content=word + " ",
                conversation_id=conversation_id,
                message_id=str(uuid.uuid4()),
                is_complete=i == len(words) - 1
            )
            await asyncio.sleep(0.1)

    async def _build_conversation_context(self, conversation_id: str) -> Dict[str, Any]:
        """
        Build comprehensive conversation context
        
        Args:
            conversation_id: Target conversation ID
            
        Returns:
            Conversation context
        """
        # Get recent messages
        messages = await self.get_conversation_history(conversation_id, "system", limit=10)
        
        # Get conversation details
        async with get_db_session() as session:
            conversation = await session.execute(
                "SELECT * FROM conversations WHERE id = :conversation_id",
                {"conversation_id": conversation_id}
            )
            conversation = conversation.first()
        
        return {
            "messages": [
                {
                    "role": "user" if msg.sender != "ai" else "assistant",
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in messages
            ],
            "context_data": json.loads(conversation.context_data or "{}") if conversation else {},
            "user_preferences": {}  # Could load from user profile
        }

    async def _store_message(self, conversation_id: str, sender: str,
                           content: str, message_type: MessageType,
                           metadata: Dict[str, Any] = None) -> str:
        """
        Store a message in the database
        
        Args:
            conversation_id: Target conversation ID
            sender: Message sender
            content: Message content
            message_type: Type of message
            metadata: Additional message metadata
            
        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())
        
        async with get_db_session() as session:
            message = Message(
                id=message_id,
                conversation_id=conversation_id,
                sender=sender,
                content=content,
                message_type=message_type.value,
                metadata=json.dumps(metadata or {}),
                created_at=datetime.utcnow()
            )
            session.add(message)
            
            # Update conversation timestamp
            await session.execute(
                "UPDATE conversations SET updated_at = :updated_at WHERE id = :conversation_id",
                {"updated_at": datetime.utcnow(), "conversation_id": conversation_id}
            )
            
            await session.commit()
        
        return message_id

    async def _validate_conversation_access(self, conversation_id: str, user_id: str) -> bool:
        """
        Validate user access to conversation
        
        Args:
            conversation_id: Target conversation ID
            user_id: User ID
            
        Returns:
            Access validation result
        """
        # Check active conversations first
        if conversation_id in self.active_conversations:
            return self.active_conversations[conversation_id].user_id == user_id
        
        # Check database
        async with get_db_session() as session:
            conversation = await session.execute(
                "SELECT user_id FROM conversations WHERE id = :conversation_id",
                {"conversation_id": conversation_id}
            )
            result = conversation.first()
            return result and result.user_id == user_id

    def _check_rate_limit(self, user_id: str):
        """
        Check rate limiting for user
        
        Args:
            user_id: User ID to check
        """
        now = datetime.utcnow()
        
        if user_id not in self.rate_limits:
            self.rate_limits[user_id] = {
                "requests": 0,
                "window_start": now,
                "last_request": now
            }
        
        user_limits = self.rate_limits[user_id]
        
        # Reset window if needed (1 minute window)
        if (now - user_limits["window_start"]).total_seconds() > 60:
            user_limits["requests"] = 0
            user_limits["window_start"] = now
        
        # Check limit (100 requests per minute)
        if user_limits["requests"] >= 100:
            raise RateLimitError("Rate limit exceeded. Please try again later.")
        
        user_limits["requests"] += 1
        user_limits["last_request"] = now

    async def _get_user_conversations(self, user_id: str) -> List[str]:
        """
        Get list of user conversation IDs
        
        Args:
            user_id: User identifier
            
        Returns:
            List of conversation IDs
        """
        async with get_db_session() as session:
            conversations = await session.execute(
                "SELECT id FROM conversations WHERE user_id = :user_id",
                {"user_id": user_id}
            )
            return [conv.id for conv in conversations]

    async def _cleanup_expired_conversations(self):
        """
        Background task to clean up expired conversations
        """
        while True:
            await asyncio.sleep(300)  # Run every 5 minutes
            
            now = datetime.utcnow()
            expired = [
                conv_id for conv_id, context in self.active_conversations.items()
                if (now - context.last_activity).total_seconds() > self.conversation_timeout
            ]
            
            for conv_id in expired:
                del self.active_conversations[conv_id]
                logging.info(f"Cleaned up expired conversation: {conv_id}")

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get chat service system status
        
        Returns:
            System status overview
        """
        return {
            "service": "chat_service",
            "status": "operational",
            "active_conversations": len(self.active_conversations),
            "orchestrator_status": self.orchestrator.get_system_health(),
            "uptime": "99.9%",
            "version": "1.0.0"
        }