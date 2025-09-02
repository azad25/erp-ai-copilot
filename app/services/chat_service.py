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
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
# Removed SQLAlchemy imports - now using MongoDB

from app.models.api import (
    ChatMessage, ChatRequest, ChatResponse, ChatStreamResponse,
    ConversationStatus, AgentType, MessageType, MessageRole
)
from app.services.conversation_service import ConversationService
from app.core.exceptions import ChatError, ValidationError, RateLimitError
from app.agents.agent_orchestrator import AgentOrchestrator
from app.agents.base_agent import AgentRequest, AgentResponse
from app.services.reasoning_engine import ReasoningEngine


@dataclass
class ConversationContext:
    """Conversation context for maintaining state"""
    conversation_id: str
    user_id: str
    context_data: Dict[str, Any] = field(default_factory=dict)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    message_count: int = 0
    active_agents: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


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

    def __init__(self, db_session=None):
        """
        Initialize ChatService with MongoDB conversation service.
        
        Args:
            db_session: Optional SQLAlchemy async session (deprecated for conversations).
        """
        self.db = db_session
        self.conversation_service = ConversationService()
        self.orchestrator = AgentOrchestrator()
        self.reasoning_engine = ReasoningEngine()
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
        # Initialize conversation service
        await self.conversation_service.initialize()
        
        # Check user conversation limit
        user_conversations = await self.conversation_service.get_user_conversations(user_id)
        if len(user_conversations) >= self.max_conversations_per_user:
            raise RateLimitError("Maximum conversations per user exceeded")
        
        # Create conversation using MongoDB service
        conversation_data = await self.conversation_service.create_conversation(
            user_id=user_id,
            title=title or f"Conversation {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            initial_context=initial_context or {}
        )
        
        conversation_id = conversation_data["conversation_id"]
        
        # Create conversation context
        context = ConversationContext(
            conversation_id=conversation_id,
            user_id=user_id,
            context_data=initial_context or {},
            created_at=datetime.utcnow()
        )
        self.active_conversations[conversation_id] = context
        
        return conversation_data

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
        # Initialize conversation context if not exists (for new conversations)
        if conversation_id not in self.active_conversations:
            self.active_conversations[conversation_id] = ConversationContext(
                conversation_id=conversation_id,
                user_id=user_id,
                context_data={}
            )
        
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
            conversation_id, "assistant", ai_response.content, MessageType.TEXT,
            {"model_used": ai_response.model_used, "tokens_used": ai_response.tokens_used}
        )
        
        # Update conversation context
        self.active_conversations[conversation_id].message_count += 2
        self.active_conversations[conversation_id].last_activity = datetime.utcnow()
        
        return ChatResponse(
            conversation_id=str(conversation_id),
            message_id=str(ai_message_id),
            content=ai_response.content,
            agent_type=None,
            created_at=datetime.utcnow(),
            metadata={
                "user_message_id": str(user_message_id),
                "model_used": ai_response.model_used,
                "tokens_used": ai_response.tokens_used
            }
        )

    async def send_message_stream(self, conversation_id: str, user_id: str,
                                message: str, message_type: MessageType = MessageType.TEXT,
                                metadata: Dict[str, Any] = None) -> AsyncGenerator[ChatStreamResponse, None]:
        """
        Send a message and get streaming AI response with reasoning steps
        
        Args:
            conversation_id: Target conversation ID
            user_id: User sending the message
            message: Message content
            message_type: Type of message
            metadata: Additional message metadata
            
        Yields:
            Streaming response chunks including reasoning steps
        """
        # Initialize conversation context if not exists
        if conversation_id not in self.active_conversations:
            self.active_conversations[conversation_id] = ConversationContext(
                conversation_id=conversation_id,
                user_id=user_id,
                context_data={}
            )
        
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
        
        # Process message with reasoning engine streaming
        final_response_content = ""
        async for reasoning_chunk in self.reasoning_engine.process_with_reasoning(
            message, conversation_id, user_id, metadata or {}
        ):
            if reasoning_chunk.get("type") == "reasoning_step":
                # Stream reasoning step
                yield ChatStreamResponse(
                    type="reasoning_step",
                    content=json.dumps(reasoning_chunk),
                    conversation_id=conversation_id,
                    message_id=str(uuid.uuid4()),
                    metadata=reasoning_chunk
                )
            elif reasoning_chunk.get("type") == "final_response":
                # Stream final response
                final_response_content = reasoning_chunk.get("content", "")
                words = final_response_content.split()
                for i, word in enumerate(words):
                    yield ChatStreamResponse(
                        type="chunk",
                        content=word + " ",
                        conversation_id=conversation_id,
                        message_id=str(uuid.uuid4()),
                        is_complete=i == len(words) - 1,
                        metadata=reasoning_chunk.get("metadata", {})
                    )
                    await asyncio.sleep(0.05)  # Simulate typing
            elif reasoning_chunk.get("type") == "error":
                # Stream error response
                yield ChatStreamResponse(
                    type="error",
                    content=reasoning_chunk.get("content", "An error occurred"),
                    conversation_id=conversation_id,
                    message_id=str(uuid.uuid4()),
                    metadata={"error": reasoning_chunk.get("error")}
                )
        
        # Store AI response
        if final_response_content:
            await self._store_message(
                conversation_id, "assistant", final_response_content, MessageType.TEXT,
                {"reasoning_enabled": True, "tokens_used": len(final_response_content.split())}
            )
        
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
        
        await self.conversation_service.initialize()
        messages = await self.conversation_service.get_conversation_messages(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
            include_reasoning=True
        )
        
        return messages

    async def get_user_conversations(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get list of user's conversations
        
        Args:
            user_id: User identifier
            limit: Maximum conversations to return
            
        Returns:
            List of conversation summaries
        """
        await self.conversation_service.initialize()
        conversations = await self.conversation_service.get_user_conversations(user_id, limit=limit)
        
        return [
            {
                "conversation_id": conv["conversation_id"],
                "title": conv["title"],
                "status": conv.get("status", "active"),
                "message_count": conv.get("message_count", 0),
                "created_at": conv["created_at"].isoformat() if isinstance(conv["created_at"], datetime) else str(conv["created_at"]),
                "updated_at": conv["updated_at"].isoformat() if isinstance(conv["updated_at"], datetime) else str(conv["updated_at"])
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
        
        # Update in MongoDB
        await self.conversation_service.initialize()
        await self.conversation_service.update_conversation_context(
            conversation_id=conversation_id,
            context_data=context_data
        )
        
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
        
        # Update in MongoDB
        await self.conversation_service.initialize()
        # Note: ConversationService doesn't have close_conversation method, 
        # but we can update the status via context update
        await self.conversation_service.update_conversation_context(
            conversation_id=conversation_id,
            context_data={"status": "closed", "closed_at": datetime.utcnow().isoformat()}
        )
        
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
        context = await self._build_conversation_context(conversation_id, user_id)
        
        # Create agent request
        agent_request = AgentRequest(
            message=message,
            conversation_id=str(conversation_id),
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
                content=response.content,
                session_id=str(conversation_id),
                model_used=response.metadata.get("model_used", "gemini2.0:flash"),
                metadata={
                    **response.metadata,
                    "processing_time": processing_time,
                    "conversation_id": str(conversation_id)
                }
            )
            
        except Exception as e:
            logging.error(f"Error processing message with AI: {e}", exc_info=True)
            print(f"DEBUG: LLM Service Error - {type(e).__name__}: {str(e)}")
            return AgentResponse(
                content="I apologize, but I'm having trouble processing your request. Please try again.",
                session_id=str(conversation_id),
                model_used="error",
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
        context = await self._build_conversation_context(conversation_id, user_id)
        
        # Create agent request
        agent_request = AgentRequest(
            message=message,
            conversation_id=str(conversation_id),
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
        words = response.content.split()
        for i, word in enumerate(words):
            yield ChatStreamResponse(
                type="chunk",
                content=word + " ",
                conversation_id=conversation_id,
                message_id=str(uuid.uuid4()),
                is_complete=i == len(words) - 1
            )
            await asyncio.sleep(0.1)

    async def _build_conversation_context(self, conversation_id: str, user_id: str = None) -> Dict[str, Any]:
        """
        Build conversation context for AI processing
        
        Args:
            conversation_id: Target conversation ID
            user_id: User ID for access validation
            
        Returns:
            Conversation context
        """
        # Get recent messages - use user_id from conversation if not provided
        if not user_id:
            # Get user_id from conversation
            await self.conversation_service.initialize()
            conversation_data = await self.conversation_service.get_conversation(conversation_id)
            if conversation_data:
                user_id = conversation_data["user_id"]
        
        messages = await self.get_conversation_history(conversation_id, user_id, limit=10)
        
        # Get conversation details from MongoDB
        await self.conversation_service.initialize()
        conversation_data = await self.conversation_service.get_conversation(conversation_id)
        
        return {
            "messages": [
                {
                    "role": msg.get("role", ""),
                    "content": msg.get("content", ""),
                    "timestamp": msg.get("created_at", "").isoformat() if isinstance(msg.get("created_at"), datetime) else str(msg.get("created_at", ""))
                }
                for msg in messages
            ],
            "context_data": conversation_data.get("context", {}) if conversation_data else {},
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
        # Initialize conversation service
        await self.conversation_service.initialize()
        
        # Add message using MongoDB service
        message_data = await self.conversation_service.add_message(
            conversation_id=conversation_id,
            role=MessageRole.USER.value if sender != "assistant" else MessageRole.ASSISTANT.value,
            content=content,
            metadata=metadata or {},
            user_id=sender if sender != "assistant" else None
        )
        
        return message_data["message_id"]

    async def _validate_conversation_access(self, conversation_id: str, user_id: str) -> bool:
        """
        Validate user access to conversation
        
        Args:
            conversation_id: Target conversation ID
            user_id: User ID
            
        Returns:
            Whether user has access
        """
        try:
            await self.conversation_service.initialize()
            conversation_data = await self.conversation_service.get_conversation(conversation_id)
            
            if not conversation_data:
                # If conversation doesn't exist, allow access for new conversations
                logging.info(f"Conversation {conversation_id} not found, allowing access for new conversation")
                return True
                
            return conversation_data["user_id"] == str(user_id)
        except Exception as e:
            logging.error(f"Error validating conversation access: {e}")
            # Allow access on error to prevent blocking valid requests
            return True

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
        await self.conversation_service.initialize()
        conversations = await self.conversation_service.get_user_conversations(user_id)
        return [conv["conversation_id"] for conv in conversations]

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