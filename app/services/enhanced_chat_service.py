"""
Enhanced Chat Service with Reasoning Steps and Efficient LLM Usage

Implements the complete AI Copilot chat processing pipeline with:
- Step-by-step reasoning display
- Multi-source data integration
- Efficient LLM context management
- WebSocket streaming of reasoning steps
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
from enum import Enum
import uuid

from app.services.conversation_service import conversation_service
from app.services.memory_service import memory_service
from app.services.api_gateway_client import api_gateway_client
from app.services.kafka_integration_service import kafka_service as kafka_integration
from app.services.service_discovery_service import service_discovery
from app.services.user_preferences_service import user_preferences_service
from app.services.third_party_api_service import third_party_api_service
from app.services.system_command_service import system_command_service
from app.services.background_job_service import background_job_service
from app.services.reasoning_engine import ReasoningEngine
from app.database.connection import get_redis

logger = logging.getLogger(__name__)


class ReasoningStepType(Enum):
    """Types of reasoning steps"""
    THINKING = "thinking"
    MEMORY_CHECK = "memory_check"
    VECTOR_SEARCH = "vector_search"
    DATABASE_QUERY = "database_query"
    API_CALL = "api_call"
    SYSTEM_COMMAND = "system_command"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    CONTEXT_UPDATE = "context_update"
    FINAL_RESPONSE = "final_response"


class ReasoningStep:
    """Represents a single reasoning step"""
    
    def __init__(
        self,
        step_type: ReasoningStepType,
        description: str,
        source: str,
        data: Optional[Dict[str, Any]] = None,
        status: str = "processing"
    ):
        self.step_id = str(uuid.uuid4())
        self.step_type = step_type
        self.description = description
        self.source = source
        self.data = data or {}
        self.status = status
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary for WebSocket transmission"""
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "description": self.description,
            "source": self.source,
            "data": self.data,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "icon": self._get_step_icon()
        }
    
    def _get_step_icon(self) -> str:
        """Get icon for step type"""
        icons = {
            ReasoningStepType.THINKING: "🧠",
            ReasoningStepType.MEMORY_CHECK: "📂",
            ReasoningStepType.VECTOR_SEARCH: "🔍",
            ReasoningStepType.DATABASE_QUERY: "💾",
            ReasoningStepType.API_CALL: "🌐",
            ReasoningStepType.SYSTEM_COMMAND: "💻",
            ReasoningStepType.KNOWLEDGE_RETRIEVAL: "🗂️",
            ReasoningStepType.CONTEXT_UPDATE: "💡",
            ReasoningStepType.FINAL_RESPONSE: "✅"
        }
        return icons.get(self.step_type, "⚡")


class EnhancedChatService:
    """
    Enhanced Chat Service with Reasoning and Efficient LLM Usage
    
    Features:
    - Step-by-step reasoning with WebSocket streaming
    - Multi-source data integration
    - Efficient context management
    - User-specific memory and preferences
    - ERP system awareness
    """
    
    def __init__(self):
        self.max_context_tokens = 8000  # Efficient context size
        self.reasoning_steps: List[ReasoningStep] = []
        self.llm_service = None  # Will be initialized when needed
        
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
        self.reasoning_steps = []
        
        try:
            # Step 1: Initialize conversation if needed
            if not conversation_id:
                step = ReasoningStep(
                    ReasoningStepType.THINKING,
                    "Creating new conversation session",
                    "conversation_service"
                )
                yield step.to_dict()
                
                conversation = await conversation_service.create_conversation(
                    user_id=user_id,
                    organization_id=organization_id,
                    title=f"Chat {datetime.now().strftime('%H:%M')}"
                )
                conversation_id = conversation["conversation_id"]
                
                step.status = "completed"
                step.data = {"conversation_id": conversation_id}
                yield step.to_dict()
            
            # Step 2: Check user memory and context
            step = ReasoningStep(
                ReasoningStepType.MEMORY_CHECK,
                "Retrieving user context and preferences",
                "memory_service"
            )
            yield step.to_dict()
            
            user_context = await self._get_user_context(user_id, organization_id)
            relevant_memories = await self._get_relevant_memories(user_id, organization_id, message)
            
            step.status = "completed"
            step.data = {
                "context_items": len(user_context),
                "relevant_memories": len(relevant_memories)
            }
            yield step.to_dict()
            
            # Step 3: Search knowledge base
            step = ReasoningStep(
                ReasoningStepType.VECTOR_SEARCH,
                "Searching knowledge base for relevant information",
                "qdrant_vector_db"
            )
            yield step.to_dict()
            
            knowledge_results = await memory_service.search_knowledge(
                query=message,
                limit=5
            )
            
            step.status = "completed"
            step.data = {"knowledge_entries": len(knowledge_results)}
            yield step.to_dict()
            
            # Step 4: Analyze query intent and determine data needs
            step = ReasoningStep(
                ReasoningStepType.THINKING,
                "Analyzing query intent and determining data requirements",
                "llm_analysis"
            )
            yield step.to_dict()
            
            query_analysis = await self._analyze_query_intent(message, user_context, knowledge_results)
            
            step.status = "completed"
            step.data = query_analysis
            yield step.to_dict()
            
            # Step 5: Fetch required data based on intent
            if query_analysis.get("needs_database_query"):
                step = ReasoningStep(
                    ReasoningStepType.DATABASE_QUERY,
                    f"Executing database query: {query_analysis.get('database_query', 'N/A')}",
                    "postgresql"
                )
                yield step.to_dict()
                
                db_results = await self._execute_database_query(
                    query_analysis.get("database_query"),
                    user_id,
                    organization_id
                )
                
                step.status = "completed"
                step.data = {"rows_returned": len(db_results) if db_results else 0}
                yield step.to_dict()
            else:
                db_results = []
            
            # Step 6: API calls if needed
            if query_analysis.get("needs_api_call"):
                step = ReasoningStep(
                    ReasoningStepType.API_CALL,
                    f"Calling API: {query_analysis.get('api_endpoint', 'N/A')}",
                    "api_gateway"
                )
                yield step.to_dict()
                
                api_results = await self._make_api_calls(
                    query_analysis.get("api_calls", []),
                    user_id,
                    organization_id
                )
                
                step.status = "completed"
                step.data = {"api_responses": len(api_results)}
                yield step.to_dict()
            else:
                api_results = []
            
            # Step 7: System commands if needed
            if query_analysis.get("needs_system_command"):
                step = ReasoningStep(
                    ReasoningStepType.SYSTEM_COMMAND,
                    f"Executing system command: {query_analysis.get('system_command', 'N/A')}",
                    "system"
                )
                yield step.to_dict()
                
                command_results = await self._execute_system_commands(
                    query_analysis.get("system_commands", []),
                    user_id,
                    organization_id
                )
                
                step.status = "completed"
                step.data = {"commands_executed": len(command_results)}
                yield step.to_dict()
            else:
                command_results = []
            
            # Step 8: Generate efficient LLM response
            step = ReasoningStep(
                ReasoningStepType.THINKING,
                "Generating response with optimized context",
                "llm_service"
            )
            yield step.to_dict()
            
            # Build efficient context for LLM
            efficient_context = await self._build_efficient_context(
                message=message,
                user_context=user_context,
                memories=relevant_memories,
                knowledge=knowledge_results,
                db_results=db_results,
                api_results=api_results,
                command_results=command_results
            )
            
            # Generate response with minimal token usage
            response = await self._generate_llm_response(efficient_context)
            
            step.status = "completed"
            step.data = {"context_tokens": len(efficient_context.split())}
            yield step.to_dict()
            
            # Step 9: Schedule background context optimization
            step = ReasoningStep(
                ReasoningStepType.CONTEXT_UPDATE,
                "Scheduling background context optimization",
                "background_jobs"
            )
            yield step.to_dict()
            
            # Schedule background job for heavy context processing
            job_id = await background_job_service.schedule_chat_processing_job(
                user_id=user_id,
                organization_id=organization_id,
                conversation_id=conversation_id,
                message=message,
                context_data={
                    "query_analysis": query_analysis,
                    "knowledge_used": knowledge_results,
                    "reasoning_steps": [step.to_dict() for step in self.reasoning_steps]
                }
            )
            
            # Update conversation immediately (lightweight operation)
            await self._update_conversation_quick(
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
                response=response
            )
            
            step.status = "completed"
            step.data = {"background_job_id": job_id}
            yield step.to_dict()
            
            # Step 10: Final response
            step = ReasoningStep(
                ReasoningStepType.FINAL_RESPONSE,
                "Response generated successfully",
                "ai_copilot",
                {"response": response}
            )
            yield step.to_dict()
            
        except Exception as e:
            logger.error(f"Chat processing failed: {e}")
            error_step = ReasoningStep(
                ReasoningStepType.FINAL_RESPONSE,
                f"Error processing request: {str(e)}",
                "error",
                status="error"
            )
            yield error_step.to_dict()
    
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
            preferences = await user_preferences_service.get_user_preferences(user_id, organization_id)
            context["preferences"] = preferences
            
            # Recent conversation history
            conversations = await conversation_service.get_user_conversations(
                user_id, organization_id, limit=5
            )
            context["recent_conversations"] = conversations
            
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
            
            # Generate appropriate database query
            if "sales" in message_lower or "revenue" in message_lower:
                analysis["database_query"] = "SELECT * FROM sales_data ORDER BY created_at DESC LIMIT 10"
            elif "customers" in message_lower:
                analysis["database_query"] = "SELECT * FROM customers ORDER BY created_at DESC LIMIT 10"
            elif "inventory" in message_lower:
                analysis["database_query"] = "SELECT * FROM inventory ORDER BY updated_at DESC LIMIT 10"
        
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
    
    async def _execute_database_query(
        self,
        query: Optional[str],
        user_id: str,
        organization_id: str
    ) -> List[Dict[str, Any]]:
        """Execute database query safely"""
        if not query:
            return []
        
        try:
            # Use API Gateway for secure database access
            response = await api_gateway_client.make_request(
                endpoint="/api/v1/query",
                method="POST",
                data={"query": query, "user_id": user_id},
                user_id=user_id,
                organization_id=organization_id
            )
            
            if response.get("success"):
                return response.get("data", [])
            
        except Exception as e:
            logger.error(f"Database query failed: {e}")
        
        return []
    
    async def _make_api_calls(
        self,
        api_calls: List[str],
        user_id: str,
        organization_id: str
    ) -> List[Dict[str, Any]]:
        """Make API calls through API Gateway"""
        results = []
        
        for endpoint in api_calls:
            try:
                response = await api_gateway_client.make_request(
                    endpoint=endpoint,
                    method="GET",
                    user_id=user_id,
                    organization_id=organization_id
                )
                results.append({
                    "endpoint": endpoint,
                    "response": response,
                    "success": response.get("success", False)
                })
                
            except Exception as e:
                logger.error(f"API call to {endpoint} failed: {e}")
                results.append({
                    "endpoint": endpoint,
                    "error": str(e),
                    "success": False
                })
        
        return results
    
    async def _execute_system_commands(
        self,
        commands: List[str],
        user_id: str,
        organization_id: str
    ) -> List[Dict[str, Any]]:
        """Execute system commands with RBAC"""
        results = []
        
        for command in commands:
            try:
                result = await system_command_service.execute_command(
                    command=command,
                    user_id=user_id,
                    organization_id=organization_id
                )
                results.append({
                    "command": command,
                    "result": result,
                    "success": result.get("success", False)
                })
                
            except Exception as e:
                logger.error(f"System command '{command}' failed: {e}")
                results.append({
                    "command": command,
                    "error": str(e),
                    "success": False
                })
        
        return results
    
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
        
        # Database results (summarized)
        if db_results:
            context_parts.append(f"Database Results: {len(db_results)} records found")
            if db_results:
                context_parts.append(f"Sample: {json.dumps(db_results[0]) if db_results else 'No data'}")
        
        # API results (summarized)
        if api_results:
            context_parts.append("API Results:")
            for api_result in api_results:
                if api_result.get("success"):
                    context_parts.append(f"- {api_result['endpoint']}: Success")
        
        # System command results (summarized)
        if command_results:
            context_parts.append("System Status:")
            for cmd_result in command_results:
                if cmd_result.get("success"):
                    context_parts.append(f"- {cmd_result['command']}: Success")
        
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
    
    async def _update_memory_and_context(
        self,
        user_id: str,
        organization_id: str,
        conversation_id: str,
        message: str,
        response: str,
        context_data: Dict[str, Any]
    ):
        """Update user memory and conversation context"""
        try:
            # Store message in conversation
            await conversation_service.add_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=message
            )
            
            await conversation_service.add_message(
                conversation_id=conversation_id,
                user_id=None,  # AI message
                role="assistant",
                content=response
            )
            
            # Store important context in memory
            if context_data.get("query_analysis", {}).get("confidence", 0) > 0.7:
                await memory_service.store_memory(
                    user_id=user_id,
                    organization_id=organization_id,
                    memory_type="conversation_context",
                    content=f"Query: {message}\nResponse: {response[:200]}...",
                    context=context_data,
                    importance=0.6
                )
            
            # Schedule background processing
            if hasattr(self, 'background_job_service'):
                await self.background_job_service.schedule_job(
                    job_type="chat_context_optimization",
                    data={
                        "conversation_id": conversation_id,
                        "message_id": message_obj.id
                    },
                    priority=2
                )
            
            return True
        except Exception as e:
            logger.error(f"Failed to quick update conversation: {e}")
            return False

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
            final_response = await self._generate_final_response(results, message)
            
            # Store conversation update
            await self._update_conversation(conversation_id, message, "user")
            await self._update_conversation(conversation_id, final_response, "assistant")
            
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

    async def _generate_final_response(self, reasoning_results: List[Dict], original_message: str) -> str:
        """Generate final response from reasoning results"""
        try:
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

    async def _update_conversation(self, conversation_id: str, message: str, role: str):
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

    async def _generate_final_response(self, reasoning_results: List[Dict], original_message: str) -> str:
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

# Global enhanced chat service instance
enhanced_chat_service = EnhancedChatService()
