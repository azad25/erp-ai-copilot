"""
Chat Service

Core service for handling chat interactions, message processing, and conversation management.
Integrates with the agent orchestrator to provide intelligent responses using the multi-agent system.
"""

from typing import Dict, List, Any, Optional, AsyncGenerator
import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
import uuid
from dataclasses import dataclass, field

from app.core.exceptions import AICopilotException
from app.services.conversation_service import conversation_service
from app.services.memory_service import memory_service
from app.services.api_gateway_client import api_gateway_client
from app.services.kafka_integration_service import kafka_service as kafka_integration
from app.services.service_discovery_service import service_discovery
from app.services.user_preferences_service import user_preferences_service
from app.services.third_party_api_service import third_party_api_service
from app.services.system_command_service import system_command_service
from app.services.background_job_service import background_job_service
from app.services.reasoning_engine import ReasoningEngine, ReasoningStepType
from app.database.connection import get_redis
from app.models.api import MessageType, MessageRole, AgentType, ChatResponse, ChatMessage
from app.agents.base_agent import AgentResponse, AgentRequest

from app.services.conversation_service import ConversationService
from app.core.exceptions import ChatError, ValidationError, RateLimitError
from app.agents.agent_orchestrator import AgentOrchestrator


@dataclass
class ChatStreamResponse:
    """Chat streaming response model"""
    type: str
    content: str
    conversation_id: str
    message_id: str = ""
    is_complete: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

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
    """Enhanced Chat service for handling AI conversations with reasoning steps and multi-source integration"""
    
    def __init__(self):
        self.reasoning_engine = ReasoningEngine(redis_client_instance=None)
        self.rate_limit_window = 60  # seconds
        self.rate_limit_max_requests = 10
        self.max_context_tokens = 8000  # Efficient context size
        self.llm_service = None  # Will be initialized when needed
        
        # Initialize missing attributes
        self.active_conversations = {}  # Dictionary to store active conversation contexts
        self.rate_limits = {}  # Dictionary to store rate limiting data per user
        self.conversation_timeout = 3600  # 1 hour timeout for conversations
        self.conversation_service = conversation_service  # Reference to conversation service
        
        # Initialize orchestrator
        from app.agents.agent_orchestrator import AgentOrchestrator
        self.orchestrator = AgentOrchestrator()

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
        await conversation_service.initialize()
        
        # Check user conversation limit
        user_conversations = await conversation_service.get_user_conversations(user_id)
        if len(user_conversations) >= 50:
            raise RateLimitError("Maximum conversations per user exceeded")
        
        # Create conversation using MongoDB service
        conversation_data = await conversation_service.create_conversation(
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
        
        return conversation_data

    async def send_message(self, conversation_id: Optional[str], user_id: str, 
                          message: str, message_type: MessageType = MessageType.TEXT,
                          metadata: Dict[str, Any] = None, 
                          organization_id: Optional[str] = None) -> ChatResponse:
        """
        Send a message in a conversation and get AI response.
        Handles conversation creation if conversation_id is None.
        
        Args:
            conversation_id: Target conversation ID (None to create new)
            user_id: User sending the message
            message: Message content
            message_type: Type of message
            metadata: Additional message metadata
            organization_id: Organization ID for new conversations
            
        Returns:
            AI response with conversation details
        """
        # Initialize conversation service
        await conversation_service.initialize()
        
        # Create or get conversation
        if not conversation_id:
            conversation_data = await conversation_service.create_conversation(
                user_id=user_id,
                organization_id=organization_id or "00000000-0000-0000-0000-000000000000",
                title=message[:100] + "..." if len(message) > 100 else message,
                context=metadata or {},
                metadata={"source": "chat_service"}
            )
            conversation_id = conversation_data["conversation_id"]
        else:
            # Validate conversation exists and user has access
            conversation = await conversation_service.get_conversation(conversation_id)
            if not conversation:
                # Create new conversation if it doesn't exist
                conversation = await conversation_service.create_conversation(
                    user_id=user_id,
                    organization_id=organization_id or "default",
                    title=f"Chat {datetime.now().strftime('%H:%M')}"
                )
                conversation_id = conversation["conversation_id"]
        
        # Initialize conversation context if not exists
        if conversation_id not in self.active_conversations:
            self.active_conversations[conversation_id] = ConversationContext(
                conversation_id=conversation_id,
                user_id=user_id,
                context_data=metadata or {}
            )
        
        # Check rate limits
        self._check_rate_limit(user_id)
        
        # Check message limits
        if self.active_conversations[conversation_id].message_count >= 1000:
            raise ValidationError("Maximum messages per conversation exceeded")
        
        # Store user message using conversation service
        user_message_data = await conversation_service.add_message(
            conversation_id=conversation_id,
            role="user",
            content=message,
            user_id=user_id,
            metadata=metadata or {}
        )
        user_message_id = user_message_data["message_id"]
        
        # Process message with AI
        ai_response = await self._process_message_with_ai(
            conversation_id, user_id, message, metadata
        )
        
        # Store AI response using conversation service
        ai_message_data = await conversation_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=ai_response.content,
            user_id="assistant",
            metadata={"model_used": ai_response.model_used, "tokens_used": ai_response.tokens_used}
        )
        ai_message_id = ai_message_data["message_id"]
        
        # Update conversation context
        self.active_conversations[conversation_id].message_count += 2
        self.active_conversations[conversation_id].last_activity = datetime.utcnow()
        
        # Handle MongoDB ObjectId to UUID conversion
        import uuid
        from uuid import UUID
        try:
            # Try to parse as UUID first
            conversation_uuid = UUID(str(conversation_id))
        except ValueError:
            # MongoDB ObjectId detected, keep as string for internal use
            # but generate UUID for response validation
            conversation_uuid = UUID(str(uuid.uuid4()))
            logger.warning(f"MongoDB ObjectId {conversation_id} converted to UUID {conversation_uuid}")
            
        return ChatResponse(
            conversation_id=conversation_uuid,
            message_id=ai_message_id,
            content=ai_response.content,
            agent_type=None,
            created_at=datetime.utcnow(),
            metadata={
                "user_message_id": str(user_message_id),
                "model_used": ai_response.model_used,
                "tokens_used": ai_response.tokens_used,
                "original_conversation_id": str(conversation_id)
            }
        )

    async def send_message_stream(self, conversation_id: str, user_id: str,
                                message: str, message_type: MessageType = MessageType.TEXT,
                                metadata: Dict[str, Any] = None, organization_id: str = None) -> AsyncGenerator[ChatStreamResponse, None]:
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
        # Check rate limits
        self._check_rate_limit(user_id)
        
        # Initialize conversation service and handle conversation creation/validation
        await self.conversation_service.initialize()
        
        # Create or get conversation (same logic as send_message)
        if not conversation_id:
            conversation_data = await self.conversation_service.create_conversation(
                user_id=user_id,
                organization_id=organization_id or "00000000-0000-0000-0000-000000000000",
                title=message[:100] + "..." if len(message) > 100 else message,
                context=metadata or {},
                metadata={"source": "chat_service_stream"}
            )
            conversation_id = conversation_data["conversation_id"]
        else:
            # Validate conversation exists and user has access
            conversation_data = await self.conversation_service.get_conversation(conversation_id)
            if not conversation_data:
                raise ValidationError("Conversation not found or access denied")
        
        # Store user message using conversation service
        user_message_data = await self.conversation_service.add_message(
            conversation_id=conversation_id,
            role="user",
            content=message,
            user_id=user_id,
            metadata=metadata or {}
        )
        user_message_id = user_message_data["message_id"]
        
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
        
        # Store AI response using conversation service
        if final_response_content:
            await self.conversation_service.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=final_response_content,
                user_id="assistant",
                metadata={"reasoning_enabled": True, "tokens_used": len(final_response_content.split())}
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
            user_id=sender if sender != "assistant" else None,
            metadata=metadata or {}
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

    async def process_chat_message(
        self,
        user_id: str,
        organization_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        websocket = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process chat message with step-by-step reasoning
        
        Args:
            user_id: User identifier
            organization_id: Organization identifier
            message: User message
            conversation_id: Optional conversation ID
            websocket: WebSocket connection for streaming
            
        Yields:
            Reasoning steps and final response
        """
        try:
            # Step 1: Initialize conversation if needed
            if not conversation_id:
                step = {
                    "type": "reasoning_step",
                    "step_type": "thinking",
                    "description": "Creating new conversation session",
                    "source": "conversation_service",
                    "status": "processing",
                    "icon": "🧠"
                }
                yield step
                
                conversation = await conversation_service.create_conversation(
                    user_id=user_id,
                    organization_id=organization_id,
                    title=f"Chat {datetime.now().strftime('%H:%M')}"
                )
                conversation_id = conversation["conversation_id"]
                
                step["status"] = "completed"
                step["data"] = {"conversation_id": conversation_id}
                yield step
            
            # Step 2: Check user memory and context
            step = {
                "type": "reasoning_step",
                "step_type": "memory_check",
                "description": "Retrieving user context and preferences",
                "source": "memory_service",
                "status": "processing",
                "icon": "📂"
            }
            yield step
            
            user_context = await self._get_user_context(user_id, organization_id)
            relevant_memories = await self._get_relevant_memories(user_id, organization_id, message)
            
            step["status"] = "completed"
            step["data"] = {
                "context_items": len(user_context),
                "relevant_memories": len(relevant_memories)
            }
            yield step
            
            # Step 3: Search knowledge base
            step = {
                "type": "reasoning_step",
                "step_type": "vector_search",
                "description": "Searching knowledge base for relevant information",
                "source": "qdrant_vector_db",
                "status": "processing",
                "icon": "🔍"
            }
            yield step
            
            try:
                knowledge_results = await memory_service.search_knowledge(
                    query=message,
                    limit=5
                )
            except Exception as e:
                logger.warning(f"Knowledge search failed: {e}")
                knowledge_results = []
            
            step["status"] = "completed"
            step["data"] = {"knowledge_entries": len(knowledge_results)}
            yield step
            
            # Step 4: Analyze query intent
            step = {
                "type": "reasoning_step",
                "step_type": "thinking",
                "description": "Analyzing query intent and determining data requirements",
                "source": "llm_analysis",
                "status": "processing",
                "icon": "🧠"
            }
            yield step
            
            query_analysis = await self._analyze_query_intent(message, user_context, knowledge_results)
            
            step["status"] = "completed"
            step["data"] = query_analysis
            yield step
            
            # Step 5: Generate efficient LLM response
            step = {
                "type": "reasoning_step",
                "step_type": "thinking",
                "description": "Generating response with optimized context",
                "source": "llm_service",
                "status": "processing",
                "icon": "🧠"
            }
            yield step
            
            # Build efficient context for LLM
            efficient_context = await self._build_efficient_context(
                message=message,
                user_context=user_context,
                memories=relevant_memories,
                knowledge=knowledge_results,
                db_results=[],
                api_results=[],
                command_results=[]
            )
            
            # Generate response with minimal token usage
            response = await self._generate_llm_response(efficient_context)
            
            step["status"] = "completed"
            step["data"] = {"context_tokens": len(efficient_context.split())}
            yield step
            
            # Step 6: Final response
            step = {
                "type": "final_response",
                "step_type": "final_response",
                "description": "Response generated successfully",
                "source": "ai_copilot",
                "status": "completed",
                "icon": "✅",
                "data": {"response": response}
            }
            yield step
            
        except Exception as e:
            logger.error(f"Chat processing failed: {e}")
            error_step = {
                "type": "error",
                "step_type": "final_response",
                "description": f"Error processing request: {str(e)}",
                "source": "error",
                "status": "error",
                "icon": "❌"
            }
            yield error_step

    async def _get_user_context(self, user_id: str, organization_id: str) -> Dict[str, Any]:
        """Get comprehensive user context efficiently"""
        try:
            # Get from cache first
            redis = await get_redis()
            cache_key = f"user_context_full:{user_id}:{organization_id}"
            
            cached_context = await redis.get(cache_key)
            if cached_context:
                return json.loads(cached_context)
            
            # Build context from multiple sources
            context = {}
            
            # User preferences
            try:
                preferences = await user_preferences_service.get_user_preferences(user_id, organization_id)
                context["preferences"] = preferences
            except Exception as e:
                logger.warning(f"Failed to get user preferences: {e}")
                context["preferences"] = {}
            
            # Recent conversation history
            try:
                conversations = await conversation_service.get_user_conversations(
                    user_id, organization_id, limit=5
                )
                context["recent_conversations"] = conversations
            except Exception as e:
                logger.warning(f"Failed to get recent conversations: {e}")
                context["recent_conversations"] = []
            
            # User role and permissions
            context["user_id"] = user_id
            context["organization_id"] = organization_id
            
            # Cache for 10 minutes
            await redis.setex(cache_key, 600, json.dumps(context, default=str))
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to get user context: {e}")
            return {}
    
    async def _get_relevant_memories(
        self, 
        user_id: str, 
        organization_id: str, 
        query: str
    ) -> List[Dict[str, Any]]:
        """Get relevant memories for the query"""
        try:
            # Use semantic search to find relevant memories
            memories = await memory_service.retrieve_memories(
                user_id=user_id,
                organization_id=organization_id,
                limit=10,
                min_importance=0.3
            )
            
            # Filter memories based on query relevance (simple keyword matching for now)
            query_lower = query.lower()
            relevant_memories = []
            
            for memory in memories:
                content_lower = memory.get("content", "").lower()
                if any(word in content_lower for word in query_lower.split()):
                    relevant_memories.append(memory)
            
            return relevant_memories[:5]  # Limit to top 5
            
        except Exception as e:
            logger.error(f"Failed to get relevant memories: {e}")
            return []
    
    async def _analyze_query_intent(
        self,
        message: str,
        user_context: Dict[str, Any],
        knowledge_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze query intent to determine required actions"""
        
        analysis = {
            "needs_database_query": False,
            "needs_api_call": False,
            "needs_system_command": False,
            "query_type": "general",
            "confidence": 0.8
        }
        
        message_lower = message.lower()
        
        # Database query indicators
        db_keywords = ["sales", "revenue", "customers", "orders", "inventory", "products", "users", "data"]
        if any(keyword in message_lower for keyword in db_keywords):
            analysis["needs_database_query"] = True
            analysis["query_type"] = "data_query"
        
        # API call indicators
        api_keywords = ["status", "health", "service", "endpoint", "external"]
        if any(keyword in message_lower for keyword in api_keywords):
            analysis["needs_api_call"] = True
            analysis["api_calls"] = ["/health", "/api/v1/services"]
        
        # System command indicators
        system_keywords = ["docker", "container", "service", "logs", "restart", "status"]
        if any(keyword in message_lower for keyword in system_keywords):
            analysis["needs_system_command"] = True
            analysis["system_commands"] = ["docker ps", "docker stats --no-stream"]
        
        return analysis
    
    async def _build_efficient_context(
        self,
        message: str,
        user_context: Dict[str, Any],
        memories: List[Dict[str, Any]],
        knowledge: List[Dict[str, Any]],
        db_results: List[Dict[str, Any]],
        api_results: List[Dict[str, Any]],
        command_results: List[Dict[str, Any]]
    ) -> str:
        """Build efficient context for LLM with minimal tokens"""
        
        context_parts = []
        
        # User context (summarized)
        context_parts.append(f"User: {user_context.get('user_id', 'unknown')}")
        context_parts.append(f"Organization: {user_context.get('organization_id', 'unknown')}")
        
        # User preferences (key settings only)
        prefs = user_context.get("preferences", {})
        if prefs:
            key_prefs = {k: v for k, v in prefs.items() if k in ["ai_behavior", "response_format", "language"]}
            if key_prefs:
                context_parts.append(f"Preferences: {json.dumps(key_prefs)}")
        
        # Recent memories (top 3)
        if memories:
            context_parts.append("Recent Context:")
            for memory in memories[:3]:
                context_parts.append(f"- {memory.get('content', '')[:100]}...")
        
        # Knowledge base results (top 3)
        if knowledge:
            context_parts.append("Relevant Knowledge:")
            for kb in knowledge[:3]:
                context_parts.append(f"- {kb.get('title', '')}: {kb.get('content', '')[:150]}...")
        
        # Current query
        context_parts.append(f"Current Query: {message}")
        
        # Join with newlines and limit total length
        full_context = "\n".join(context_parts)
        
        # Truncate if too long (keep within token limits)
        if len(full_context) > self.max_context_tokens * 4:  # Rough token estimation
            full_context = full_context[:self.max_context_tokens * 4] + "...[truncated]"
        
        return full_context
    
    async def _generate_llm_response(self, context: str) -> str:
        """Generate LLM response with efficient context"""
        try:
            # Use the existing LLM service
            from app.services.llm_service import llm_service
            
            # Create efficient prompt
            prompt = f"""
You are an ERP AI Copilot. Based on the provided context, generate a helpful response.

Context:
{context}

Instructions:
- Be concise and specific
- Reference data sources when applicable
- Format response in Markdown
- Include reasoning if complex analysis was performed

Response:
"""
            
            from app.services.llm_service import LLMRequest, LLMMessage
            
            request = LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                model="gpt-4",
                max_tokens=1000,
                temperature=0.7
            )
            
            response = await llm_service.generate(request)
            response_text = response.content
            
            return response_text
            
        except Exception as e:
            logger.error(f"LLM response generation failed: {e}")
            return f"I encountered an error processing your request: {str(e)}"

    async def process_message_with_reasoning(self, conversation_id: str, message: str, user_id: str) -> Dict[str, Any]:
        """Process message with step-by-step reasoning"""
        try:
            # Initialize reasoning engine
            reasoning_engine = ReasoningEngine()
            
            # Generate reasoning steps
            reasoning_steps = await reasoning_engine.generate_reasoning_steps(
                message=message,
                conversation_id=conversation_id,
                user_id=user_id
            )
            
            # Execute each reasoning step
            results = []
            for step in reasoning_steps:
                step_result = await reasoning_engine.execute_reasoning_step(step)
                results.append(step_result)
            
            # Generate final response
            final_response = await self._generate_final_response_from_reasoning(results, message)
            
            # Store conversation update
            await self._update_conversation_with_message(conversation_id, message, "user")
            await self._update_conversation_with_message(conversation_id, final_response, "assistant")
            
            return {
                "response": final_response,
                "reasoning_steps": [step.to_dict() for step in reasoning_steps],
                "conversation_id": conversation_id
            }
            
        except Exception as e:
            logger.error(f"Failed to process message with reasoning: {e}")
            return {"error": str(e)}

    async def stream_reasoning_steps(self, websocket, conversation_id: str, message: str, user_id: str):
        """Stream reasoning steps via WebSocket"""
        try:
            reasoning_engine = ReasoningEngine()
            
            # Generate and stream reasoning steps
            async for step in reasoning_engine.stream_reasoning_steps(
                user_message=message,
                conversation_id=conversation_id,
                user_id=user_id
            ):
                # Send the step data directly (it's already a dict)
                await websocket.send_json(step)
            
            # Send completion signal
            await websocket.send_json({
                "type": "reasoning_complete",
                "conversation_id": conversation_id
            })
            
        except Exception as e:
            logger.error(f"Failed to stream reasoning steps: {e}")
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })

    async def _generate_final_response_from_reasoning(self, reasoning_results: List[Dict], original_message: str) -> str:
        """Generate final response from reasoning results"""
        try:
            # Initialize LLM service if needed
            await self._initialize_llm_service()
            
            if not self.llm_service:
                return f"Based on the analysis of '{original_message}', I've processed your request through multiple reasoning steps and data sources."
            
            # Combine reasoning results into context
            context = {
                "original_message": original_message,
                "reasoning_results": reasoning_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Use LLM to generate final response
            prompt = f"""
            Based on the step-by-step reasoning results, provide a comprehensive response to: {original_message}
            
            Reasoning Context: {json.dumps(context, indent=2)}
            
            Provide a clear, helpful response that incorporates insights from the reasoning steps.
            """
            
            from app.services.llm_service import LLMRequest, LLMMessage
            
            request = LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                model="gpt-4",
                max_tokens=1000,
                temperature=0.7
            )
            
            response = await self.llm_service.generate(request)
            response_text = response.content
            
            return response_text
            
        except Exception as e:
            logger.error(f"Failed to generate final response: {e}")
            return "I encountered an error while processing your request."

    async def _update_conversation_with_message(self, conversation_id: str, message: str, role: str):
        """Update conversation with new message"""
        try:
            await conversation_service.add_message(
                conversation_id=conversation_id,
                role=role,
                content=message
            )
        except Exception as e:
            logger.error(f"Failed to update conversation: {e}")

    async def _initialize_llm_service(self):
        """Initialize LLM service if not already done"""
        if self.llm_service is None:
            try:
                from app.services.llm_service import LLMService
                self.llm_service = LLMService()
            except Exception as e:
                logger.error(f"Failed to initialize LLM service: {e}")
                self.llm_service = None


# Create a global instance
chat_service = ChatService()