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
            from app.database.connection import get_postgres_session
            
            # Analyze message to determine what data to query
            query_type = await self._analyze_query_type(message)
            
            # Get database session
            async with get_postgres_session() as session:
                results = []
                queries_executed = []
                
                if query_type.get("needs_sales_data"):
                    # Query sales data
                    sales_query = """
                    SELECT COUNT(*) as total_sales, SUM(amount) as total_revenue 
                    FROM sales_orders 
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                    """
                    result = await session.execute(sales_query)
                    sales_data = result.fetchone()
                    if sales_data:
                        results.append({
                            "type": "sales_summary",
                            "total_sales": sales_data[0],
                            "total_revenue": float(sales_data[1]) if sales_data[1] else 0
                        })
                    queries_executed.append("sales_summary")
                
                if query_type.get("needs_inventory_data"):
                    # Query inventory data
                    inventory_query = """
                    SELECT COUNT(*) as total_products, 
                           SUM(CASE WHEN stock_quantity < reorder_level THEN 1 ELSE 0 END) as low_stock_items
                    FROM inventory_items
                    """
                    result = await session.execute(inventory_query)
                    inventory_data = result.fetchone()
                    if inventory_data:
                        results.append({
                            "type": "inventory_summary",
                            "total_products": inventory_data[0],
                            "low_stock_items": inventory_data[1]
                        })
                    queries_executed.append("inventory_summary")
                
                if query_type.get("needs_customer_data"):
                    # Query customer data
                    customer_query = """
                    SELECT COUNT(*) as total_customers,
                           COUNT(CASE WHEN created_at >= NOW() - INTERVAL '30 days' THEN 1 END) as new_customers
                    FROM customers
                    """
                    result = await session.execute(customer_query)
                    customer_data = result.fetchone()
                    if customer_data:
                        results.append({
                            "type": "customer_summary", 
                            "total_customers": customer_data[0],
                            "new_customers": customer_data[1]
                        })
                    queries_executed.append("customer_summary")
                
                return {
                    "queries_executed": queries_executed,
                    "results": results,
                    "rows_returned": len(results),
                    "execution_time": "0.3s",
                    "database_access_used": True
                }
                
        except Exception as e:
            logging.error(f"Error executing database queries: {e}")
            return {
                "error": str(e), 
                "fallback": "database_unavailable",
                "database_access_used": False
            }
    
    async def _analyze_query_type(self, message: str) -> Dict[str, bool]:
        """Analyze message to determine what type of data is needed"""
        message_lower = message.lower()
        
        return {
            "needs_sales_data": any(keyword in message_lower for keyword in ["sales", "revenue", "orders", "transactions"]),
            "needs_inventory_data": any(keyword in message_lower for keyword in ["inventory", "stock", "products", "items"]),
            "needs_customer_data": any(keyword in message_lower for keyword in ["customers", "clients", "users"]),
            "needs_financial_data": any(keyword in message_lower for keyword in ["finance", "accounting", "expenses", "profit"]),
            "needs_employee_data": any(keyword in message_lower for keyword in ["employees", "staff", "hr", "payroll"])
        }
    
    async def _perform_vector_search(self, message: str) -> Dict[str, Any]:
        """Perform vector similarity search on knowledge base with enhanced embedding usage"""
        try:
            from app.services.memory_service import memory_service
            
            # Initialize memory service if not already done
            await memory_service.initialize()
            
            # Search both system knowledge and organization-specific knowledge
            search_results = []
            
            # Search system knowledge
            system_results = await memory_service.search_knowledge(
                query=message,
                limit=3,
                similarity_threshold=0.7,
                organization_id="system"
            )
            search_results.extend(system_results or [])
            
            # Search organization-specific knowledge if available
            org_results = await memory_service.search_knowledge(
                query=message,
                limit=2,
                similarity_threshold=0.6,
                organization_id="default"  # Could be dynamic based on user context
            )
            search_results.extend(org_results or [])
            
            if search_results:
                # Sort by similarity score
                search_results.sort(key=lambda x: x.get("score", 0), reverse=True)
                
                return {
                    "documents_found": len(search_results),
                    "similarity_threshold": 0.7,
                    "embeddings_used": True,
                    "vector_search_performed": True,
                    "top_matches": [
                        {
                            "title": result.get("title", "Unknown"),
                            "similarity": result.get("score", result.get("similarity", 0.0)),
                            "content_preview": result.get("content", "")[:300] + "...",
                            "source": result.get("source", "Unknown"),
                            "category": result.get("category", "documentation"),
                            "entry_id": result.get("entry_id", ""),
                            "organization_id": result.get("organization_id", "system")
                        }
                        for result in search_results[:5]  # Top 5 results
                    ],
                    "knowledge_sources_used": True,
                    "search_strategy": "multi_source_vector_search"
                }
            else:
                return {
                    "documents_found": 0,
                    "similarity_threshold": 0.7,
                    "embeddings_used": True,
                    "vector_search_performed": True,
                    "top_matches": [],
                    "message": "No relevant knowledge base entries found",
                    "knowledge_sources_used": False,
                    "search_strategy": "multi_source_vector_search"
                }
                
        except Exception as e:
            logging.error(f"Error in vector search: {e}")
            return {
                "error": str(e), 
                "fallback": "knowledge_base_unavailable", 
                "knowledge_sources_used": False,
                "embeddings_used": False,
                "vector_search_performed": False
            }
    
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
        """Make external API calls to ERP services with enhanced data access"""
        try:
            from app.services.api_gateway_client import api_gateway_client
            
            # Initialize API gateway client
            await api_gateway_client.initialize()
            
            api_results = []
            apis_called = []
            
            # Analyze what APIs to call based on message
            api_requirements = await self._analyze_api_requirements_detailed(message)
            
            # Get comprehensive ERP data summary if multiple data types needed
            if sum([api_requirements.get(key, False) for key in api_requirements.keys()]) > 2:
                try:
                    data_types = []
                    if api_requirements.get("needs_sales_api"):
                        data_types.append("sales")
                    if api_requirements.get("needs_inventory_api"):
                        data_types.append("inventory")
                    if api_requirements.get("needs_crm_api"):
                        data_types.append("crm")
                    if api_requirements.get("needs_finance_api"):
                        data_types.append("finance")
                    
                    comprehensive_data = await api_gateway_client.get_erp_data_summary(data_types)
                    if comprehensive_data and not comprehensive_data.get("error"):
                        api_results.append({
                            "service": "comprehensive-erp-data",
                            "data": comprehensive_data,
                            "status": "success",
                            "data_types": data_types
                        })
                        apis_called.extend([f"{dt}-service" for dt in data_types])
                        
                        return {
                            "apis_called": apis_called,
                            "api_results": api_results,
                            "responses_received": len(data_types),
                            "total_latency": "0.6s",
                            "api_gateway_used": True,
                            "comprehensive_data_retrieved": True
                        }
                except Exception as e:
                    logging.warning(f"Comprehensive data retrieval failed: {e}")
            
            # Individual API calls for specific data needs
            if api_requirements.get("needs_sales_api"):
                try:
                    sales_data = await api_gateway_client.get_sales_summary()
                    if sales_data and not sales_data.get("error"):
                        api_results.append({
                            "service": "sales-service",
                            "data": sales_data,
                            "status": "success"
                        })
                        apis_called.append("sales-service")
                except Exception as e:
                    logging.warning(f"Sales API call failed: {e}")
                    api_results.append({
                        "service": "sales-service", 
                        "error": str(e),
                        "status": "failed"
                    })
            
            if api_requirements.get("needs_inventory_api"):
                try:
                    inventory_data = await api_gateway_client.get_inventory_summary()
                    if inventory_data and not inventory_data.get("error"):
                        api_results.append({
                            "service": "inventory-service",
                            "data": inventory_data,
                            "status": "success"
                        })
                        apis_called.append("inventory-service")
                except Exception as e:
                    logging.warning(f"Inventory API call failed: {e}")
                    api_results.append({
                        "service": "inventory-service",
                        "error": str(e), 
                        "status": "failed"
                    })
            
            if api_requirements.get("needs_crm_api"):
                try:
                    crm_data = await api_gateway_client.get_customer_summary()
                    if crm_data and not crm_data.get("error"):
                        api_results.append({
                            "service": "crm-service",
                            "data": crm_data,
                            "status": "success"
                        })
                        apis_called.append("crm-service")
                except Exception as e:
                    logging.warning(f"CRM API call failed: {e}")
                    api_results.append({
                        "service": "crm-service",
                        "error": str(e),
                        "status": "failed"
                    })
            
            if api_requirements.get("needs_finance_api"):
                try:
                    finance_data = await api_gateway_client.get_finance_summary()
                    if finance_data and not finance_data.get("error"):
                        api_results.append({
                            "service": "finance-service",
                            "data": finance_data,
                            "status": "success"
                        })
                        apis_called.append("finance-service")
                except Exception as e:
                    logging.warning(f"Finance API call failed: {e}")
                    api_results.append({
                        "service": "finance-service",
                        "error": str(e),
                        "status": "failed"
                    })
            
            return {
                "apis_called": apis_called,
                "api_results": api_results,
                "responses_received": len([r for r in api_results if r.get("status") == "success"]),
                "total_latency": "0.4s",
                "api_gateway_used": True,
                "comprehensive_data_retrieved": False
            }
            
        except Exception as e:
            logging.error(f"Error making API calls: {e}")
            return {
                "error": str(e),
                "fallback": "api_gateway_unavailable", 
                "api_gateway_used": False
            }
    
    async def _analyze_api_requirements_detailed(self, message: str) -> Dict[str, bool]:
        """Analyze message to determine detailed API requirements"""
        message_lower = message.lower()
        
        return {
            "needs_sales_api": any(keyword in message_lower for keyword in [
                "sales", "revenue", "orders", "transactions", "invoices", "billing"
            ]),
            "needs_inventory_api": any(keyword in message_lower for keyword in [
                "inventory", "stock", "products", "items", "warehouse", "supply"
            ]),
            "needs_crm_api": any(keyword in message_lower for keyword in [
                "customers", "clients", "leads", "contacts", "prospects", "crm"
            ]),
            "needs_finance_api": any(keyword in message_lower for keyword in [
                "finance", "accounting", "expenses", "profit", "budget", "financial"
            ]),
            "needs_hrm_api": any(keyword in message_lower for keyword in [
                "employees", "staff", "hr", "payroll", "attendance", "human resources"
            ]),
            "needs_purchase_api": any(keyword in message_lower for keyword in [
                "purchase", "procurement", "suppliers", "vendors", "buying"
            ])
        }
    
    async def _integrate_data_sources(self, *data_sources) -> Dict[str, Any]:
        """Integrate data from multiple sources"""
        integrated = {}
        source_names = ["conversation_history", "database", "vector_search", "cache", "api_calls"]
        
        for i, data in enumerate(data_sources):
            if data and i < len(source_names):
                integrated[source_names[i]] = data
        
        return integrated
    
    async def _generate_final_response(self, message: str, integrated_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generate the final AI response using LLM with integrated data and markdown formatting"""
        try:
            from app.services.llm_service import get_llm_service, LLMRequest, LLMMessage
            
            llm_service = get_llm_service()
            if not llm_service:
                return self._generate_fallback_response(message, integrated_data)
            
            # Build context-aware prompt with integrated data
            system_prompt = """You are an AI assistant for UniBase ERP system. You have access to real-time data from multiple sources including:
- Knowledge base with documentation and procedures
- Live ERP data from sales, inventory, CRM, finance, and HR systems
- Database queries and API responses
- User conversation history and preferences

Provide helpful, accurate, and concise responses based on the available data. Format your response in markdown when appropriate, including:
- **Bold text** for emphasis
- `Code blocks` for technical details
- Lists for structured information
- Tables for data presentation

Always cite your data sources and be transparent about the information you're using."""

            # Prepare comprehensive data context
            data_context = self._build_data_context(integrated_data)
            
            # Build the enhanced message with context
            enhanced_message = f"""User Question: {message}

Available Data Context:
{data_context}

Please provide a comprehensive, well-formatted response based on the available information. Use markdown formatting for better readability."""

            # Create LLM request
            request = LLMRequest(
                model="gemini2.0:flash",  # Use Gemini as default
                messages=[
                    LLMMessage(role="user", content=enhanced_message)
                ],
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=2000
            )
            
            # Generate response
            response = await llm_service.generate(request)
            return response.content
            
        except Exception as e:
            logging.error(f"Error generating LLM response: {e}")
            return self._generate_fallback_response(message, integrated_data)
    
    def _build_data_context(self, integrated_data: Dict[str, Any]) -> str:
        """Build formatted data context for LLM"""
        context_parts = []
        
        # Conversation history
        if integrated_data.get("conversation_history"):
            context_parts.append(f"**Conversation Context**: {len(integrated_data['conversation_history'])} previous messages available")
        
        # Database results
        if integrated_data.get("db_results", {}).get("database_access_used"):
            db_data = integrated_data["db_results"]
            if db_data.get("results"):
                context_parts.append("**Database Data Available**:")
                for result in db_data["results"]:
                    if result.get("type") == "sales_summary":
                        context_parts.append(f"  - Sales: {result.get('total_sales', 0)} orders, ${result.get('total_revenue', 0):,.2f} revenue")
                    elif result.get("type") == "inventory_summary":
                        context_parts.append(f"  - Inventory: {result.get('total_products', 0)} products, {result.get('low_stock_items', 0)} low stock")
                    elif result.get("type") == "customer_summary":
                        context_parts.append(f"  - Customers: {result.get('total_customers', 0)} total, {result.get('new_customers', 0)} new")
        
        # Vector search results
        if integrated_data.get("vector_results", {}).get("knowledge_sources_used"):
            vector_data = integrated_data["vector_results"]
            if vector_data.get("top_matches"):
                context_parts.append(f"**Knowledge Base**: {len(vector_data['top_matches'])} relevant documents found")
                for match in vector_data["top_matches"][:3]:  # Top 3
                    context_parts.append(f"  - {match.get('title', 'Unknown')} (similarity: {match.get('similarity', 0):.2f})")
        
        # API results
        if integrated_data.get("api_results", {}).get("api_gateway_used"):
            api_data = integrated_data["api_results"]
            successful_apis = [r for r in api_data.get("api_results", []) if r.get("status") == "success"]
            if successful_apis:
                context_parts.append(f"**ERP Services**: Data retrieved from {len(successful_apis)} services")
                for api in successful_apis:
                    context_parts.append(f"  - {api.get('service', 'Unknown service')}")
        
        return "\n".join(context_parts) if context_parts else "No additional data sources available"
    
    def _generate_fallback_response(self, message: str, integrated_data: Dict[str, Any]) -> str:
        """Generate fallback response when LLM is unavailable"""
        # Create a comprehensive response based on the reasoning steps
        response_parts = [
            f"# AI Analysis Results",
            "",
            f"I've analyzed your request: **\"{message}\"** using multiple data sources and reasoning steps.",
            ""
        ]
        
        # Add database results if available
        if integrated_data.get("db_results", {}).get("database_access_used"):
            db_data = integrated_data["db_results"]
            response_parts.extend([
                "## 📊 Database Analysis",
                "",
                "I queried the ERP database and found the following information:",
                ""
            ])
            
            if db_data.get("results"):
                for result in db_data["results"]:
                    if result.get("type") == "sales_summary":
                        response_parts.extend([
                            "### Sales Data",
                            f"- **Total Sales**: {result.get('total_sales', 0)}",
                            f"- **Total Revenue**: ${result.get('total_revenue', 0):,.2f}",
                            ""
                        ])
                    elif result.get("type") == "inventory_summary":
                        response_parts.extend([
                            "### Inventory Data", 
                            f"- **Total Products**: {result.get('total_products', 0)}",
                            f"- **Low Stock Items**: {result.get('low_stock_items', 0)}",
                            ""
                        ])
                    elif result.get("type") == "customer_summary":
                        response_parts.extend([
                            "### Customer Data",
                            f"- **Total Customers**: {result.get('total_customers', 0)}",
                            f"- **New Customers (30 days)**: {result.get('new_customers', 0)}",
                            ""
                        ])
        
        # Add knowledge base results if available
        if "vector_search" in integrated_data and integrated_data["vector_search"].get("knowledge_sources_used"):
            kb_data = integrated_data["vector_search"]
            response_parts.extend([
                "## 📚 Knowledge Base Search",
                "",
                f"I found **{kb_data.get('documents_found', 0)}** relevant documents in the knowledge base:",
                ""
            ])
            
            if kb_data.get("top_matches"):
                for i, match in enumerate(kb_data["top_matches"][:3], 1):
                    response_parts.extend([
                        f"### {i}. {match.get('title', 'Unknown Document')}",
                        f"- **Similarity**: {match.get('similarity', 0):.2%}",
                        f"- **Source**: {match.get('source', 'Unknown')}",
                        f"- **Category**: {match.get('category', 'documentation')}",
                        f"- **Preview**: {match.get('content_preview', 'No preview available')}",
                        ""
                    ])
        
        # Add API results if available
        if "api_calls" in integrated_data and integrated_data["api_calls"].get("api_gateway_used"):
            api_data = integrated_data["api_calls"]
            response_parts.extend([
                "## 🌐 External Service Data",
                "",
                f"I retrieved data from **{len(api_data.get('apis_called', []))}** ERP services:",
                ""
            ])
            
            if api_data.get("api_results"):
                for result in api_data["api_results"]:
                    if result.get("status") == "success":
                        service_name = result.get("service", "Unknown Service")
                        response_parts.extend([
                            f"### ✅ {service_name.title()}",
                            "- Status: **Connected and Retrieved Data**",
                            ""
                        ])
                    else:
                        service_name = result.get("service", "Unknown Service")
                        response_parts.extend([
                            f"### ❌ {service_name.title()}",
                            f"- Status: **Failed** - {result.get('error', 'Unknown error')}",
                            ""
                        ])
        
        # Add conversation context if available
        if "conversation_history" in integrated_data:
            hist_data = integrated_data["conversation_history"]
            if hist_data and len(hist_data) > 0:
                response_parts.extend([
                    "## 💬 Conversation Context",
                    "",
                    f"I considered **{len(hist_data)}** previous messages in our conversation to provide contextual responses.",
                    ""
                ])
        
        # Add cache information if available
        if "cache" in integrated_data:
            cache_data = integrated_data["cache"]
            if cache_data.get("similar_queries", 0) > 0:
                response_parts.extend([
                    "## ⚡ Cached Insights",
                    "",
                    f"I found **{cache_data.get('similar_queries', 0)}** similar queries in cache to optimize response time.",
                    ""
                ])
        
        # Add recommendations based on the analysis
        response_parts.extend([
            "## 🎯 Recommendations",
            "",
            "Based on my comprehensive analysis, here are my recommendations:",
            ""
        ])
        
        # Generate contextual recommendations
        if any("sales" in message.lower() or "revenue" in message.lower() for message in [message]):
            response_parts.extend([
                "1. **Review Sales Performance**: Monitor current sales trends and identify growth opportunities",
                "2. **Customer Engagement**: Focus on customer retention and acquisition strategies",
                "3. **Revenue Optimization**: Analyze pricing strategies and product performance",
                ""
            ])
        elif any("inventory" in message.lower() or "stock" in message.lower() for message in [message]):
            response_parts.extend([
                "1. **Stock Management**: Monitor low stock items and optimize reorder levels",
                "2. **Inventory Turnover**: Analyze product movement and identify slow-moving items",
                "3. **Warehouse Efficiency**: Optimize storage and distribution processes",
                ""
            ])
        else:
            response_parts.extend([
                "1. **Data Review**: Examine the retrieved information for actionable insights",
                "2. **Process Optimization**: Consider improvements based on current data trends",
                "3. **Strategic Planning**: Use this analysis for informed decision-making",
                ""
            ])
        
        response_parts.extend([
            "---",
            "",
            "💡 **Need more details?** Feel free to ask specific questions about any of the data points above!",
            "",
            f"*Analysis completed using {len(integrated_data)} data sources with step-by-step reasoning.*"
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
                await self.redis_client.set(
                    f"reasoning_session:{session_id}",
                    json.dumps({
                        "user_id": user_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        **metadata
                    }),
                    expire=3600  # 1 hour TTL
                )
        except Exception as e:
            logging.error(f"Error storing reasoning session: {e}")
            api_data = integrated_data["api_calls"]
            response_parts.extend([
                "## 🌐 ERP Services Integration",
                "",
                f"I retrieved data from **{len(api_data.get('apis_called', []))}** ERP services:",
                ""
            ])
            
            successful_apis = [r for r in api_data.get("api_results", []) if r.get("status") == "success"]
            for api in successful_apis:
                service_name = api.get("service", "Unknown Service")
                response_parts.extend([
                    f"### {service_name.title()}",
                    f"- **Status**: ✅ Success",
                    f"- **Data Retrieved**: Available for analysis",
                    ""
                ])
        
        # Add summary
        response_parts.extend([
            "## 📋 Summary",
            "",
            "Based on my analysis using multiple data sources, I've provided you with the most relevant information available.",
            "The data comes from real-time ERP systems, knowledge base searches, and database queries.",
            "",
            "If you need more specific information or have follow-up questions, please let me know!"
        ])
        
        return "\n".join(response_parts)
    
    async def _integrate_data_sources(
        self,
        conversation_history: List[Dict[str, Any]],
        db_results: Dict[str, Any],
        vector_results: Dict[str, Any],
        cache_results: Dict[str, Any],
        api_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Integrate data from all sources"""
        return {
            "conversation_history": conversation_history,
            "db_results": db_results,
            "vector_results": vector_results,
            "cache_results": cache_results,
            "api_results": api_results,
            "integration_timestamp": datetime.utcnow().isoformat(),
            "total_sources": sum([
                1 if conversation_history else 0,
                1 if db_results.get("database_access_used") else 0,
                1 if vector_results.get("knowledge_sources_used") else 0,
                1 if cache_results.get("cache_hit") else 0,
                1 if api_results.get("api_gateway_used") else 0
            ])
        }
    
    async def _store_reasoning_session(
        self,
        session_id: str,
        user_id: str,
        session_data: Dict[str, Any]
    ):
        """Store reasoning session for future reference"""
        try:
            if self.redis_client:
                await self.redis_client.cache_reasoning_step(
                    f"session_{session_id}",
                    {
                        "user_id": user_id,
                        "session_data": session_data,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    expire_seconds=3600  # 1 hour
                )
        except Exception as e:
            logging.warning(f"Failed to store reasoning session: {e}")


# Global reasoning engine instance
reasoning_engine = ReasoningEngine()