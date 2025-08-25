"""
Base Agent

Abstract base class for all AI Copilot agents.
Provides common functionality for LLM integration, tool execution, memory management, and error handling.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
import uuid
import structlog
from pydantic import BaseModel, Field

from app.services.llm_service import llm_service, LLMRequest, LLMMessage, LLMResponse
from app.core.exceptions import AgentError, AIModelError
from app.core.cache_manager import CacheManager


class AgentRequest(BaseModel):
    """Request model for agent interactions"""
    message: str = Field(..., description="User message")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Session identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AgentResponse(BaseModel):
    """Response model for agent interactions"""
    content: str = Field(..., description="Agent response content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tokens_used: int = Field(default=0, description="Number of tokens used")
    model_used: str = Field(..., description="Model used for generation")


class AgentMemory(BaseModel):
    """Memory model for agent conversations"""
    session_id: str
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BaseAgent(ABC):
    """
    Abstract base class for all AI Copilot agents.
    
    Provides common functionality including:
    - LLM integration with multiple providers
    - Tool execution and management
    - Memory management and caching
    - Error handling and logging
    - Performance monitoring
    """

    def __init__(
        self,
        name: str,
        model: str = "gpt-4",
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7
    ):
        self.name = name
        self.model = model
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        self.logger = structlog.get_logger(f"agent.{name}")
        self.cache = CacheManager()
        
        # Initialize memory storage
        self._memory: Dict[str, AgentMemory] = {}
        
        # Performance tracking
        self._stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "total_errors": 0,
            "average_response_time": 0.0
        }

    @abstractmethod
    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for this agent"""
        pass

    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get available tools for this agent"""
        pass

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """
        Process a user request using the LLM service.
        
        Args:
            request: AgentRequest containing user message and context
            
        Returns:
            AgentResponse with the generated content
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            self.logger.info(
                "Processing request",
                agent=self.name,
                model=self.model,
                session_id=request.session_id
            )

            # Validate model availability
            available_models = llm_service.get_available_models()
            provider = llm_service.get_provider_for_model(self.model)
            if not provider:
                raise AIModelError(
                    f"Model {self.model} not available. "
                    f"Available models: {available_models}"
                )

            # Get or create memory for session
            memory = self._get_or_create_memory(request.session_id)
            
            # Build conversation history
            messages = self._build_conversation_history(memory, request)
            
            # Create LLM request
            llm_request = LLMRequest(
                messages=messages,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
                system_prompt=self.system_prompt
            )

            # Generate response
            response = await llm_service.generate(llm_request)
            
            # Update memory
            self._update_memory(memory, request.message, response.content)
            
            # Update performance stats
            end_time = asyncio.get_event_loop().time()
            self._update_stats(response.tokens_used, end_time - start_time)

            return AgentResponse(
                content=response.content,
                metadata=response.metadata,
                session_id=request.session_id,
                tokens_used=response.tokens_used,
                model_used=response.model
            )

        except Exception as e:
            self.logger.error(
                "Error processing request",
                error=str(e),
                agent=self.name,
                session_id=request.session_id
            )
            self._stats["total_errors"] += 1
            raise AgentError(f"Failed to process request: {str(e)}")

    async def process_request_stream(
        self, 
        request: AgentRequest
    ) -> AsyncGenerator[str, None]:
        """
        Process a user request with streaming response.
        
        Args:
            request: AgentRequest containing user message and context
            
        Yields:
            Response chunks as they are generated
        """
        try:
            self.logger.info(
                "Processing streaming request",
                agent=self.name,
                model=self.model,
                session_id=request.session_id
            )

            # Validate model availability
            provider = llm_service.get_provider_for_model(self.model)
            if not provider:
                raise AIModelError(f"Model {self.model} not available")

            # Get or create memory for session
            memory = self._get_or_create_memory(request.session_id)
            
            # Build conversation history
            messages = self._build_conversation_history(memory, request)
            
            # Create LLM request
            llm_request = LLMRequest(
                messages=messages,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
                system_prompt=self.system_prompt
            )

            # Collect full response for memory
            full_response = []
            
            # Generate streaming response
            async for chunk in llm_service.generate_stream(llm_request):
                full_response.append(chunk)
                yield chunk

            # Update memory with complete response
            complete_response = "".join(full_response)
            self._update_memory(memory, request.message, complete_response)

        except Exception as e:
            self.logger.error(
                "Error processing streaming request",
                error=str(e),
                agent=self.name,
                session_id=request.session_id
            )
            raise AgentError(f"Failed to process streaming request: {str(e)}")

    def _get_or_create_memory(self, session_id: str) -> AgentMemory:
        """Get existing memory or create new one for session"""
        if session_id not in self._memory:
            self._memory[session_id] = AgentMemory(session_id=session_id)
        return self._memory[session_id]

    def _build_conversation_history(
        self, 
        memory: AgentMemory, 
        request: AgentRequest
    ) -> List[LLMMessage]:
        """Build conversation history for LLM"""
        messages = []
        
        # Add previous conversation history (limit to last 10 messages)
        history_messages = memory.messages[-10:] if memory.messages else []
        
        for msg in history_messages:
            messages.append(LLMMessage(
                role=msg.get("role", "user"),
                content=msg.get("content", "")
            ))
        
        # Add current user message
        messages.append(LLMMessage(role="user", content=request.message))
        
        return messages

    def _update_memory(self, memory: AgentMemory, user_message: str, assistant_response: str):
        """Update memory with new conversation"""
        memory.messages.append({"role": "user", "content": user_message})
        memory.messages.append({"role": "assistant", "content": assistant_response})
        memory.updated_at = datetime.utcnow()

    def _update_stats(self, tokens_used: int, response_time: float):
        """Update performance statistics"""
        self._stats["total_requests"] += 1
        self._stats["total_tokens"] += tokens_used
        
        # Update average response time
        current_avg = self._stats["average_response_time"]
        total_requests = self._stats["total_requests"]
        self._stats["average_response_time"] = (
            (current_avg * (total_requests - 1) + response_time) / total_requests
        )

    async def get_session_history(self, session_id: str) -> Optional[AgentMemory]:
        """Get conversation history for a session"""
        return self._memory.get(session_id)

    async def clear_session(self, session_id: str):
        """Clear conversation history for a session"""
        if session_id in self._memory:
            del self._memory[session_id]

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for this agent"""
        return self._stats.copy()

    async def health_check(self) -> Dict[str, Any]:
        """Check agent and LLM provider health"""
        health = {
            "agent": {
                "name": self.name,
                "status": "healthy",
                "model": self.model,
                "stats": self._stats
            },
            "llm_service": await llm_service.health_check()
        }

        # Check if current model is available
        provider = llm_service.get_provider_for_model(self.model)
        if not provider:
            health["agent"]["status"] = "error"
            health["agent"]["error"] = f"Model {self.model} not available"

        return health

    def validate_request(self, request: AgentRequest) -> bool:
        """Validate agent request"""
        if not request.message or not request.message.strip():
            return False
        
        if not request.session_id:
            return False
            
        return True

    def format_context(self, context: Dict[str, Any]) -> str:
        """Format context for LLM consumption"""
        if not context:
            return ""
            
        formatted_parts = []
        for key, value in context.items():
            if isinstance(value, dict):
                formatted_parts.append(f"{key}: {json.dumps(value, indent=2)}")
            else:
                formatted_parts.append(f"{key}: {value}")
        
        return "\n".join(formatted_parts)