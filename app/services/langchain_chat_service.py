"""
LangChain Chat Service

Chat service using LangChain/LangGraph for intelligent responses.
"""

from typing import Dict, Any, Optional, AsyncGenerator
import asyncio
import logging
from datetime import datetime
import uuid

from langchain_core.messages import HumanMessage, AIMessage

from app.langgraph.agent_graph import agent_graph
from app.langgraph.state import AgentState
from app.services.conversation_service import conversation_service
from app.core.exceptions import ChatError, ValidationError

logger = logging.getLogger(__name__)


class LangChainChatService:
    """Chat service powered by LangChain and LangGraph"""
    
    def __init__(self):
        self.agent = agent_graph
        self.conversation_service = conversation_service
    
    async def send_message(
        self,
        message: str,
        user_id: str,
        organization_id: str,
        conversation_id: Optional[str] = None,
        user_role: str = "user",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a message and get AI response
        
        Args:
            message: User message
            user_id: User ID
            organization_id: Organization ID
            conversation_id: Conversation ID (creates new if None)
            user_role: User role for RBAC
            metadata: Additional metadata
            
        Returns:
            Response dictionary with content and metadata
        """
        try:
            # Initialize conversation service
            await self.conversation_service.initialize()
            
            # Create or get conversation
            if not conversation_id:
                conv_data = await self.conversation_service.create_conversation(
                    user_id=user_id,
                    organization_id=organization_id,
                    title=message[:100],
                    context=metadata or {}
                )
                conversation_id = conv_data["conversation_id"]
            
            # Store user message
            await self.conversation_service.add_message(
                conversation_id=conversation_id,
                role="user",
                content=message,
                user_id=user_id,
                metadata=metadata or {}
            )
            
            # Create agent state
            state: AgentState = {
                "messages": [HumanMessage(content=message)],
                "conversation_id": conversation_id,
                "user_id": user_id,
                "organization_id": organization_id,
                "user_role": user_role,
                "context": metadata or {}
            }
            
            # Invoke agent graph with limited recursion to prevent excessive API calls
            config = {"recursion_limit": 10}  # Reduced to prevent excessive API calls
            result = await self.agent.ainvoke(state, config=config)
            
            # Extract response
            ai_message = result["messages"][-1]
            response_content = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
            
            # Get provider info from state if available
            provider_info = result.get("context", {}).get("provider", "unknown")
            model_info = result.get("context", {}).get("model", "unknown")
            
            # Store AI response
            await self.conversation_service.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response_content,
                user_id="assistant",
                metadata={"model": model_info, "provider": provider_info, "langgraph": True}
            )
            
            return {
                "conversation_id": conversation_id,
                "content": response_content,
                "message_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "tools_used": self._extract_tools_used(result),
                    "framework": "langgraph"
                }
            }
            
        except Exception as e:
            logger.error(f"Error in LangChain chat service: {e}", exc_info=True)
            raise ChatError(f"Failed to process message: {str(e)}")
    
    async def send_message_stream(
        self,
        message: str,
        user_id: str,
        organization_id: str,
        conversation_id: Optional[str] = None,
        user_role: str = "user",
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a message and stream AI response
        
        Args:
            message: User message
            user_id: User ID
            organization_id: Organization ID
            conversation_id: Conversation ID
            user_role: User role
            metadata: Additional metadata
            
        Yields:
            Response chunks
        """
        try:
            # Initialize conversation service
            await self.conversation_service.initialize()
            
            # Create or get conversation
            if not conversation_id:
                conv_data = await self.conversation_service.create_conversation(
                    user_id=user_id,
                    organization_id=organization_id,
                    title=message[:100],
                    context=metadata or {}
                )
                conversation_id = conv_data["conversation_id"]
            
            # Store user message
            await self.conversation_service.add_message(
                conversation_id=conversation_id,
                role="user",
                content=message,
                user_id=user_id,
                metadata=metadata or {}
            )
            
            # Yield start event
            yield {
                "type": "start",
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Create agent state
            state: AgentState = {
                "messages": [HumanMessage(content=message)],
                "conversation_id": conversation_id,
                "user_id": user_id,
                "organization_id": organization_id,
                "user_role": user_role,
                "context": metadata or {}
            }
            
            # Stream agent execution with limited recursion to prevent excessive API calls
            full_response = ""
            config = {"recursion_limit": 10}  # Reduced to prevent excessive API calls
            async for event in self.agent.astream(state, config=config):
                # Extract content from event
                if "agent" in event:
                    agent_output = event["agent"]
                    if "messages" in agent_output:
                        last_message = agent_output["messages"][-1]
                        if hasattr(last_message, "content"):
                            content = last_message.content
                            if content and content != full_response:
                                # Yield new content
                                new_content = content[len(full_response):]
                                full_response = content
                                
                                yield {
                                    "type": "chunk",
                                    "content": new_content,
                                    "conversation_id": conversation_id
                                }
            
            # Store AI response
            if full_response:
                await self.conversation_service.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_response,
                    user_id="assistant",
                    metadata={"langgraph": True, "streamed": True}
                )
            
            # Yield completion
            yield {
                "type": "complete",
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in streaming: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
                "conversation_id": conversation_id
            }
    
    def _extract_tools_used(self, result: Dict[str, Any]) -> list:
        """Extract list of tools used from result"""
        tools_used = []
        
        if "messages" in result:
            for msg in result["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        if hasattr(tool_call, "name"):
                            tools_used.append(tool_call.name)
        
        return list(set(tools_used))


# Global instance
langchain_chat_service = LangChainChatService()
