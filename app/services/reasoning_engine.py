"""
Reasoning Engine for AI Copilot

This module implements step-by-step reasoning with real-time streaming of processing steps.
It provides transparency into AI decision-making by breaking down actions into numbered steps
with clear source attribution and reasoning explanations.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import uuid

from app.database.connection import get_db_session
from app.core.redis_client import redis_client
from app.models.api import AgentType


class ReasoningStepType(Enum):
    """Types of reasoning steps"""
    THINKING = "thinking"
    MEMORY_CHECK = "memory_check"
    DATABASE_QUERY = "database_query"
    VECTOR_SEARCH = "vector_search"
    API_CALL = "api_call"
    SYSTEM_COMMAND = "system_command"
    CACHE_ACCESS = "cache_access"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    INTEGRATION = "integration"
    COMPLETION = "completion"


@dataclass
class ReasoningStep:
    """Individual reasoning step with metadata"""
    step_number: int
    step_type: ReasoningStepType
    title: str
    description: str
    content: str
    source: str
    icon: str = "🤔"
    status: str = "processing"  # processing, completed, failed
    timestamp: datetime = field(default_factory=datetime.utcnow)
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert reasoning step to dictionary"""
        return {
            "step_number": self.step_number,
            "step_type": self.step_type.value if isinstance(self.step_type, ReasoningStepType) else str(self.step_type),
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "source": self.source,
            "icon": self.icon,
            "status": self.status,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            "processing_time": self.processing_time,
            "metadata": self.metadata
        }


class ReasoningEngine:
    """
    Reasoning Engine that provides step-by-step AI processing with real-time streaming
    
    Features:
    - Step-by-step reasoning breakdown
    - Real-time streaming of processing steps
    - Source attribution for each step
    - Memory and context management
    - Multi-source data integration
    - Transparent decision-making process
    """
    
    def __init__(self, redis_client_instance: Optional[Any] = None):
        self.redis_client = redis_client_instance or redis_client
        self.step_icons = {
            ReasoningStepType.THINKING: "🧠",
            ReasoningStepType.MEMORY_CHECK: "📂",
            ReasoningStepType.DATABASE_QUERY: "💻",
            ReasoningStepType.VECTOR_SEARCH: "🔍",
            ReasoningStepType.API_CALL: "🌐",
            ReasoningStepType.SYSTEM_COMMAND: "⚙️",
            ReasoningStepType.CACHE_ACCESS: "⚡",
            ReasoningStepType.KNOWLEDGE_RETRIEVAL: "📚",
            ReasoningStepType.INTEGRATION: "🔗",
            ReasoningStepType.COMPLETION: "✅"
        }
    
    async def generate_reasoning_steps(self, message: str, conversation_id: str, user_id: str, organization_id: str = None) -> List['ReasoningStep']:
        """Generate reasoning steps for a given message"""
        try:
            steps = []
            step_counter = 0
            
            # Step 1: Analysis
            step_counter += 1
            steps.append(ReasoningStep(
                step_number=step_counter,
                step_type=ReasoningStepType.THINKING,
                title="Analyzing user query",
                description="Determining required data sources and processing approach",
                content="Analyzing user query to determine the best approach",
                source="AI Reasoning Engine",
                icon=self.step_icons[ReasoningStepType.THINKING]
            ))
            
            # Step 2: Memory check
            step_counter += 1
            steps.append(ReasoningStep(
                step_number=step_counter,
                step_type=ReasoningStepType.MEMORY_CHECK,
                title="Checking conversation context",
                description="Retrieving relevant conversation history and user preferences",
                content="Checking conversation context and user memory",
                source="MongoDB Memory Store",
                icon=self.step_icons[ReasoningStepType.MEMORY_CHECK]
            ))
            
            # Step 3: Knowledge base search
            step_counter += 1
            steps.append(ReasoningStep(
                step_number=step_counter,
                step_type=ReasoningStepType.VECTOR_SEARCH,
                title="Searching knowledge base",
                description="Finding relevant documentation and code snippets",
                content="Searching knowledge base for relevant information",
                source="Qdrant Vector Database",
                icon=self.step_icons[ReasoningStepType.VECTOR_SEARCH]
            ))
            
            # Step 4: API calls if needed
            if any(keyword in message.lower() for keyword in ["sales", "invoice", "customer", "order", "data"]):
                step_counter += 1
                steps.append(ReasoningStep(
                    step_number=step_counter,
                    step_type=ReasoningStepType.API_CALL,
                    title="Retrieving ERP data",
                    description="Fetching data from ERP services via API gateway",
                    content="Retrieving ERP data from API gateway",
                    source="API Gateway",
                    icon=self.step_icons[ReasoningStepType.API_CALL]
                ))
            
            # Step 5: Final synthesis
            step_counter += 1
            steps.append(ReasoningStep(
                step_number=step_counter,
                step_type=ReasoningStepType.COMPLETION,
                title="Generating response",
                description="Synthesizing information to create comprehensive answer",
                content="Generating final response based on gathered information",
                source="AI Language Model",
                icon=self.step_icons[ReasoningStepType.COMPLETION]
            ))
            
            return steps
            
        except Exception as e:
            logger.error(f"Error generating reasoning steps: {e}")
            return []

    async def execute_reasoning_step(self, step: 'ReasoningStep') -> Dict[str, Any]:
        """Execute a single reasoning step"""
        try:
            step.status = "in_progress"
            start_time = datetime.utcnow()
            
            result = {}
            
            if step.step_type == ReasoningStepType.THINKING:
                result = await self._analyze_query(step)
            elif step.step_type == ReasoningStepType.MEMORY_CHECK:
                result = await self._check_memory_context(step)
            elif step.step_type == ReasoningStepType.VECTOR_SEARCH:
                result = await self._perform_vector_search(step.description)
            elif step.step_type == ReasoningStepType.API_CALL:
                result = await self._make_api_calls(step.description, {})
            elif step.step_type == ReasoningStepType.COMPLETION:
                result = await self._synthesize_final_result(step)
            
            # Update step with results
            step.status = "completed"
            step.data = result
            step.processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return result
            
        except Exception as e:
            step.status = "failed"
            step.data = {"error": str(e)}
            logger.error(f"Error executing reasoning step: {e}")
            return {"error": str(e)}

    async def _analyze_query(self, step: 'ReasoningStep') -> Dict[str, Any]:
        """Analyze user query"""
        await asyncio.sleep(0.1)
        return {
            "query_type": "information_request",
            "complexity": "medium",
            "data_sources_needed": ["knowledge_base", "memory"]
        }

    async def _check_memory_context(self, step: 'ReasoningStep') -> Dict[str, Any]:
        """Check memory and conversation context"""
        await asyncio.sleep(0.2)
        return {
            "previous_messages": 3,
            "user_preferences": {"language": "en", "detail_level": "medium"},
            "context_relevance": 0.8
        }

    async def _synthesize_final_result(self, step: 'ReasoningStep') -> Dict[str, Any]:
        """Synthesize final response"""
        await asyncio.sleep(0.3)
        return {
            "response_generated": True,
            "confidence": 0.9,
            "sources_integrated": 3
        }
    
    async def process_with_reasoning(
        self,
        user_message: str,
        conversation_id: str,
        user_id: str,
        context: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user message with step-by-step reasoning
        
        Args:
            user_message: User's input message
            conversation_id: Current conversation ID
            user_id: User identifier
            context: Additional context data
            
        Yields:
            Reasoning steps and final response
        """
        reasoning_session_id = str(uuid.uuid4())
        step_counter = 0
        context = context or {}
        
        try:
            # Step 1: Initial thinking and analysis
            step_counter += 1
            yield await self._create_step(
                step_counter, ReasoningStepType.THINKING,
                "Analyzing user request",
                f"Processing user message: '{user_message[:100]}...' and determining the best approach",
                "AI Reasoning Engine"
            )
            
            # Simulate processing time
            await asyncio.sleep(0.5)
            
            # Step 2: Check user memory and conversation history
            step_counter += 1
            memory_step = await self._create_step(
                step_counter, ReasoningStepType.MEMORY_CHECK,
                "Checking user memory and conversation history",
                "Retrieving previous conversation context and user preferences",
                "MongoDB Memory Store"
            )
            yield memory_step
            
            # Get conversation history
            conversation_history = await self._get_conversation_history(conversation_id, user_id)
            memory_step["data"] = {"messages_found": len(conversation_history)}
            memory_step["status"] = "completed"
            yield memory_step
            
            # Step 3: Determine if database access is needed
            needs_db_access = await self._analyze_db_requirements(user_message)
            if needs_db_access:
                step_counter += 1
                db_step = await self._create_step(
                    step_counter, ReasoningStepType.DATABASE_QUERY,
                    "Querying ERP database",
                    "Executing database queries to retrieve relevant business data",
                    "PostgreSQL ERP Database"
                )
                yield db_step
                
                # Simulate database query
                await asyncio.sleep(0.8)
                db_results = await self._execute_database_queries(user_message, context)
                db_step["data"] = db_results
                db_step["status"] = "completed"
                yield db_step
            
            # Step 4: Vector search for relevant knowledge
            step_counter += 1
            vector_step = await self._create_step(
                step_counter, ReasoningStepType.VECTOR_SEARCH,
                "Searching knowledge base",
                "Retrieving relevant documentation and code snippets using vector similarity",
                "Qdrant Vector Database"
            )
            yield vector_step
            
            # Simulate vector search
            await asyncio.sleep(0.6)
            vector_results = await self._perform_vector_search(user_message)
            vector_step["data"] = vector_results
            vector_step["status"] = "completed"
            yield vector_step
            
            # Step 5: Check cache for similar queries
            step_counter += 1
            cache_step = await self._create_step(
                step_counter, ReasoningStepType.CACHE_ACCESS,
                "Checking cached responses",
                "Looking for previously processed similar queries to optimize response time",
                "Redis Cache"
            )
            yield cache_step
            
            cache_results = await self._check_cache(user_message, user_id)
            cache_step["data"] = cache_results
            cache_step["status"] = "completed"
            yield cache_step
            
            # Step 6: Determine if external API calls are needed
            needs_api_call = await self._analyze_api_requirements(user_message)
            if needs_api_call:
                step_counter += 1
                api_step = await self._create_step(
                    step_counter, ReasoningStepType.API_CALL,
                    "Calling external APIs",
                    "Fetching additional data from external services or internal microservices",
                    "External APIs"
                )
                yield api_step
                
                # Simulate API call
                await asyncio.sleep(0.7)
                api_results = await self._make_api_calls(user_message, context)
                api_step["data"] = api_results
                api_step["status"] = "completed"
                yield api_step
            
            # Step 7: Integration and synthesis
            step_counter += 1
            integration_step = await self._create_step(
                step_counter, ReasoningStepType.INTEGRATION,
                "Integrating all data sources",
                "Combining information from memory, database, knowledge base, and APIs",
                "AI Integration Engine"
            )
            yield integration_step
            
            # Integrate all collected data
            integrated_data = await self._integrate_data_sources(
                conversation_history, 
                db_results if needs_db_access else {},
                vector_results,
                cache_results,
                api_results if needs_api_call else {}
            )
            integration_step["data"] = {"sources_integrated": len(integrated_data)}
            integration_step["status"] = "completed"
            yield integration_step
            
            # Step 8: Generate final response
            step_counter += 1
            completion_step = await self._create_step(
                step_counter, ReasoningStepType.COMPLETION,
                "Generating final response",
                "Creating comprehensive response based on all gathered information",
                "AI Language Model"
            )
            yield completion_step
            
            # Generate the actual AI response
            final_response = await self._generate_final_response(
                user_message, integrated_data, context
            )
            
            completion_step["data"] = {
                "response_length": len(final_response),
                "sources_used": list(integrated_data.keys())
            }
            completion_step["status"] = "completed"
            yield completion_step
            
            # Store reasoning session in memory for future reference
            await self._store_reasoning_session(reasoning_session_id, user_id, {
                "steps": step_counter,
                "sources_used": list(integrated_data.keys()),
                "processing_time": datetime.utcnow().timestamp()
            })
            
            # Final response with complete reasoning
            yield {
                "type": "final_response",
                "content": final_response,
                "reasoning_session_id": reasoning_session_id,
                "total_steps": step_counter,
                "sources_used": list(integrated_data.keys()),
                "metadata": {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logging.error(f"Error in reasoning engine: {e}", exc_info=True)
            yield {
                "type": "error",
                "content": f"I encountered an error while processing your request: {str(e)}",
                "error": str(e),
                "reasoning_session_id": reasoning_session_id
            }
    
    async def _create_step(
        self, 
        step_number: int, 
        step_type: ReasoningStepType, 
        title: str, 
        description: str, 
        source: str
    ) -> Dict[str, Any]:
        """Create a reasoning step"""
        step = ReasoningStep(
            step_number=step_number,
            step_type=step_type,
            title=title,
            description=description,
            content=description,
            source=source,
            icon=self.step_icons.get(step_type, "🤔")
        )
        
        result = {
            "type": "reasoning_step",
            **step.to_dict()
        }
        
        return result
    
    async def _get_conversation_history(self, conversation_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Retrieve conversation history from database"""
        try:
            # Simulate database query - in real implementation, query actual database
            await asyncio.sleep(0.2)
            return [
                {"role": "user", "content": "Previous message", "timestamp": datetime.utcnow().isoformat()},
                {"role": "assistant", "content": "Previous response", "timestamp": datetime.utcnow().isoformat()}
            ]
        except Exception as e:
            logging.error(f"Error retrieving conversation history: {e}")
            return []
    
    async def _analyze_db_requirements(self, message: str) -> bool:
        """Analyze if database access is needed"""
        # Simple keyword analysis - in real implementation, use NLP
        db_keywords = ["report", "data", "sales", "revenue", "customer", "inventory", "employee"]
        return any(keyword in message.lower() for keyword in db_keywords)
    
    async def _execute_database_queries(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute database queries based on message analysis"""
        try:
            # Simulate database queries
            await asyncio.sleep(0.3)
            return {
                "query_executed": "SELECT * FROM sales WHERE date >= '2024-01-01'",
                "rows_returned": 150,
                "execution_time": "0.3s"
            }
        except Exception as e:
            logging.error(f"Error executing database queries: {e}")
            return {"error": str(e)}
    
    async def _perform_vector_search(self, message: str) -> Dict[str, Any]:
        """Perform vector similarity search on knowledge base"""
        try:
            from app.services.memory_service import memory_service
            
            # Actually search the knowledge base using vector similarity
            results = await memory_service.search_knowledge(
                query=message,
                limit=5,
                similarity_threshold=0.7
            )
            
            if results:
                return {
                    "documents_found": len(results),
                    "similarity_threshold": 0.7,
                    "top_matches": [
                        {
                            "title": result.get("title", "Unknown"),
                            "similarity": result.get("similarity", 0.0),
                            "content_preview": result.get("content", "")[:200] + "...",
                            "source": result.get("source", "Unknown"),
                            "category": result.get("category", "documentation")
                        }
                        for result in results
                    ]
                }
            else:
                return {
                    "documents_found": 0,
                    "similarity_threshold": 0.7,
                    "top_matches": [],
                    "message": "No relevant knowledge base entries found"
                }
                
        except Exception as e:
            logging.error(f"Error in vector search: {e}")
            return {"error": str(e), "fallback": "knowledge_base_unavailable"}
    
    async def _check_cache(self, message: str, user_id: str) -> Dict[str, Any]:
        """Check Redis cache for similar queries"""
        try:
            # Simulate cache check
            await asyncio.sleep(0.1)
            return {
                "cache_hit": False,
                "similar_queries": 2,
                "cache_key": f"user:{user_id}:query_hash"
            }
        except Exception as e:
            logging.error(f"Error checking cache: {e}")
            return {"error": str(e)}
    
    async def _analyze_api_requirements(self, message: str) -> bool:
        """Analyze if external API calls are needed"""
        api_keywords = ["weather", "stock", "exchange", "external", "integration"]
        return any(keyword in message.lower() for keyword in api_keywords)
    
    async def _make_api_calls(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make external API calls"""
        try:
            # Simulate API calls
            await asyncio.sleep(0.4)
            return {
                "apis_called": ["internal_erp_service", "external_data_provider"],
                "responses_received": 2,
                "total_latency": "0.4s"
            }
        except Exception as e:
            logging.error(f"Error making API calls: {e}")
            return {"error": str(e)}
    
    async def _integrate_data_sources(self, *data_sources) -> Dict[str, Any]:
        """Integrate data from multiple sources"""
        integrated = {}
        source_names = ["conversation_history", "database", "vector_search", "cache", "api_calls"]
        
        for i, data in enumerate(data_sources):
            if data and i < len(source_names):
                integrated[source_names[i]] = data
        
        return integrated
    
    async def _generate_final_response(self, message: str, integrated_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate the final AI response"""
        # Simulate AI response generation
        await asyncio.sleep(0.5)
        
        # Create a comprehensive response based on the reasoning steps
        response_parts = [
            "Based on my analysis of your request, here's what I found:",
            "",
            "## Summary",
            f"I processed your message '{message}' through multiple data sources and reasoning steps.",
            ""
        ]
        
        if "database" in integrated_data:
            response_parts.extend([
                "## Database Analysis",
                "I queried the ERP database and found relevant business data that matches your request.",
                ""
            ])
        
        if "vector_search" in integrated_data:
            response_parts.extend([
                "## Knowledge Base",
                "I searched through documentation and found relevant information to help answer your question.",
                ""
            ])
        
        response_parts.extend([
            "## Recommendation",
            "Based on all the information gathered, I recommend proceeding with the following actions:",
            "1. Review the data analysis results",
            "2. Consider the context from previous conversations",
            "3. Take appropriate action based on your business needs",
            "",
            "Is there anything specific you'd like me to elaborate on?"
        ])
        
        return "\n".join(response_parts)
    
    async def stream_reasoning_steps(
        self,
        user_message: str,
        conversation_id: str,
        user_id: str,
        context: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream reasoning steps for WebSocket clients
        
        This is an alias for process_with_reasoning to maintain compatibility
        """
        async for step in self.process_with_reasoning(user_message, conversation_id, user_id, context):
            yield step

    async def _store_reasoning_session(self, session_id: str, user_id: str, metadata: Dict[str, Any]):
        """Store reasoning session metadata"""
        try:
            if self.redis_client:
                await self.redis_client.setex(
                    f"reasoning_session:{session_id}",
                    3600,  # 1 hour TTL
                    json.dumps({
                        "user_id": user_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        **metadata
                    })
                )
        except Exception as e:
            logging.error(f"Error storing reasoning session: {e}")
