"""
LangChain Tools

Tools for API calls, database access, and document search.
"""

from typing import List, Dict, Any, Optional
from langchain.tools import Tool, StructuredTool
from langchain.pydantic_v1 import BaseModel, Field

from app.services.api_gateway_client import get_api_gateway_client
from app.services.erp_data_service import get_erp_data_service
from app.langchain.rag_chain import search_documents


# Tool input schemas
class APICallInput(BaseModel):
    """Input for API call tool"""
    method: str = Field(description="HTTP method (GET, POST, PUT, DELETE)")
    endpoint: str = Field(description="API endpoint path (e.g., /api/v1/users)")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Request body data")


class DataQueryInput(BaseModel):
    """Input for data query tool"""
    query_type: str = Field(description="Type of query (users, conversations, cache, system)")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Query filters")


class DocumentSearchInput(BaseModel):
    """Input for document search tool"""
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, description="Maximum number of results")


# Tool functions
async def call_api_tool(method: str, endpoint: str, data: Optional[Dict] = None) -> str:
    """Call ERP API endpoint"""
    try:
        client = await get_api_gateway_client()
        response = await client.call_api(
            method=method,
            endpoint=endpoint,
            data=data
        )
        
        if response.get("success"):
            return f"API call successful:\n{client.format_api_response_for_llm(response)}"
        else:
            error = response.get("error", {})
            return f"API call failed: {error.get('message', 'Unknown error')}"
    except Exception as e:
        return f"Error calling API: {str(e)}"


async def query_data_tool(query_type: str, filters: Optional[Dict] = None) -> str:
    """Query ERP data from databases"""
    try:
        service = await get_erp_data_service()
        
        if query_type == "users":
            data = await service.get_user_statistics()
        elif query_type == "conversations":
            data = await service.get_conversations_summary()
        elif query_type == "cache":
            data = await service.get_cache_statistics()
        elif query_type == "system":
            data = await service.get_system_overview()
        else:
            return f"Unknown query type: {query_type}"
        
        # Format data for LLM
        import json
        return f"Data query results:\n{json.dumps(data, indent=2)}"
    except Exception as e:
        return f"Error querying data: {str(e)}"


async def search_docs_tool(query: str, max_results: int = 5, organization_id: Optional[str] = None) -> str:
    """Search ERP documentation with organization isolation"""
    try:
        # Get organization_id from context if not provided
        # TODO: Extract from current user context
        if not organization_id:
            organization_id = "default"  # Fallback
        
        documents = await search_documents(
            query=query,
            organization_id=organization_id,
            k=max_results
        )
        
        if not documents:
            return "No relevant documentation found."
        
        result = f"Found {len(documents)} relevant documents:\n\n"
        
        for i, doc in enumerate(documents, 1):
            content = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
            metadata = doc.metadata
            source = metadata.get("source", metadata.get("filename", "Unknown"))
            
            result += f"{i}. **{source}**\n{content}\n\n"
        
        return result
    except Exception as e:
        return f"Error searching documents: {str(e)}"


async def create_background_task_tool(task_type: str, parameters: Dict[str, Any]) -> str:
    """Create a background task"""
    try:
        from app.services.background_task_service import background_task_service, TaskType
        
        # Get user_id from context (would come from request in real implementation)
        user_id = parameters.get('user_id', 'system')
        
        task_id = await background_task_service.create_task(
            task_type=TaskType(task_type),
            user_id=user_id,
            parameters=parameters
        )
        
        return f"Background task created successfully. Task ID: {task_id}. You will be notified when it completes."
    except Exception as e:
        return f"Error creating background task: {str(e)}"


async def generate_chart_tool(chart_type: str, query: str) -> str:
    """Generate a chart or visualization"""
    try:
        from app.services.chart_service import chart_service
        import json
        
        chart_data = chart_service.create_chart_from_query(query, None)
        
        # Return as JSON string that will be parsed by the frontend
        return json.dumps(chart_data)
    except Exception as e:
        return f"Error generating chart: {str(e)}"


class BackgroundTaskInput(BaseModel):
    """Input for background task tool"""
    task_type: str = Field(description="Type of task (report_generation, chart_generation, forecast_calculation, data_analysis, bulk_export)")
    parameters: Dict[str, Any] = Field(description="Task parameters")


class ChartGenerationInput(BaseModel):
    """Input for chart generation tool"""
    chart_type: str = Field(description="Type of chart (line, bar, pie, area, scatter)")
    query: str = Field(description="User's query to determine chart content")


async def query_ai_logs_tool(
    query_type: str,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
    date_from: Optional[str] = None,
    limit: int = 10
) -> str:
    """Query AI Copilot logs (admin only)"""
    try:
        from app.services.ai_copilot_logging_service import ai_copilot_logging_service
        from app.models.ai_copilot_log import AICopilotLogQuery
        from app.core.user_context import get_current_organization_id, get_current_user_role
        from datetime import datetime, timedelta
        import json
        
        # Get requester context
        requester_org_id = organization_id or get_current_organization_id() or "default"
        requester_role = get_current_user_role() or "user"
        
        # Check if user has permission (admin only)
        from app.services.rbac_service import rbac_service, Permission
        if not rbac_service.has_permission(requester_role, Permission.READ_ALL_DATA):
            return "Error: Only administrators can access AI Copilot logs"
        
        # Parse date_from if provided
        date_from_dt = None
        if date_from:
            if date_from == "today":
                date_from_dt = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_from == "yesterday":
                date_from_dt = (datetime.utcnow() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_from == "week":
                date_from_dt = datetime.utcnow() - timedelta(days=7)
            elif date_from == "month":
                date_from_dt = datetime.utcnow() - timedelta(days=30)
        
        if query_type == "recent":
            # Get recent logs
            logs = await ai_copilot_logging_service.get_recent_logs(
                organization_id=requester_org_id,
                user_id=user_id,
                limit=limit
            )
            
            if not logs:
                return "No recent logs found."
            
            result = f"Found {len(logs)} recent AI Copilot interactions:\n\n"
            for i, log in enumerate(logs, 1):
                status_icon = "✅" if log.status else "❌"
                result += f"{i}. {status_icon} **{log.user_email or log.user_id}** ({log.created_at.strftime('%Y-%m-%d %H:%M')})\n"
                result += f"   Prompt: {log.prompt[:100]}...\n"
                result += f"   Tools: {', '.join([t.tool_name for t in log.tools_used])}\n"
                if log.total_tokens:
                    result += f"   Tokens: {log.total_tokens} (prompt: {log.prompt_tokens}, response: {log.response_tokens})\n"
                if log.errors:
                    result += f"   Errors: {len(log.errors)}\n"
                result += "\n"
            
            return result
            
        elif query_type == "stats":
            # Get statistics
            stats = await ai_copilot_logging_service.get_stats(
                organization_id=requester_org_id,
                user_id=user_id,
                date_from=date_from_dt
            )
            
            result = "AI Copilot Usage Statistics:\n\n"
            result += f"**Total Queries:** {stats.total_queries}\n"
            result += f"**Successful:** {stats.successful_queries} ({stats.successful_queries/stats.total_queries*100:.1f}%)\n" if stats.total_queries > 0 else ""
            result += f"**Failed:** {stats.failed_queries}\n"
            result += f"**Total Tools Used:** {stats.total_tools_used}\n"
            result += f"**Total Errors:** {stats.total_errors}\n"
            if stats.avg_execution_time_ms:
                result += f"**Avg Execution Time:** {stats.avg_execution_time_ms:.0f}ms\n"
            
            # Token usage statistics
            if stats.total_tokens_used:
                result += f"\n**Token Usage:**\n"
                result += f"  - Total Tokens: {stats.total_tokens_used:,}\n"
                result += f"  - Prompt Tokens: {stats.total_prompt_tokens:,}\n"
                result += f"  - Response Tokens: {stats.total_response_tokens:,}\n"
                if stats.total_embedding_tokens:
                    result += f"  - Embedding Tokens: {stats.total_embedding_tokens:,}\n"
                if stats.avg_tokens_per_query:
                    result += f"  - Avg per Query: {stats.avg_tokens_per_query:.0f} tokens\n"
            
            if stats.most_used_tools:
                result += "\n**Most Used Tools:**\n"
                for tool in stats.most_used_tools[:5]:
                    result += f"  - {tool['tool']}: {tool['count']} times\n"
            
            if stats.most_used_models:
                result += "\n**Most Used Models:**\n"
                for model in stats.most_used_models[:5]:
                    result += f"  - {model['model']}: {model['count']} times\n"
            
            if stats.most_active_users:
                result += "\n**Most Active Users:**\n"
                for user in stats.most_active_users[:5]:
                    result += f"  - {user['user_id']}: {user['count']} queries\n"
            
            return result
            
        elif query_type == "search":
            # Search logs
            query = AICopilotLogQuery(
                organization_id=requester_org_id,
                user_id=user_id,
                date_from=date_from_dt,
                limit=limit
            )
            
            logs = await ai_copilot_logging_service.get_logs(
                query=query,
                requester_org_id=requester_org_id,
                requester_role=requester_role
            )
            
            if not logs:
                return "No logs found matching the criteria."
            
            result = f"Found {len(logs)} AI Copilot logs:\n\n"
            for i, log in enumerate(logs, 1):
                status_icon = "✅" if log.status else "❌"
                result += f"{i}. {status_icon} **{log.user_email or log.user_id}**\n"
                result += f"   Time: {log.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                result += f"   Model: {log.llm_model_used or 'N/A'}\n"
                result += f"   Prompt: {log.prompt[:150]}...\n"
                result += f"   Response: {log.response[:150]}...\n"
                result += f"   Tools: {', '.join([t.tool_name for t in log.tools_used])}\n"
                if log.total_tokens:
                    result += f"   Tokens: {log.total_tokens} (prompt: {log.prompt_tokens}, response: {log.response_tokens})\n"
                if log.total_execution_time_ms:
                    result += f"   Time: {log.total_execution_time_ms}ms\n"
                if log.errors:
                    result += f"   ⚠️ Errors: {', '.join([e.error_message for e in log.errors])}\n"
                result += "\n"
            
            return result
        
        else:
            return f"Unknown query type: {query_type}. Use 'recent', 'stats', or 'search'."
            
    except Exception as e:
        return f"Error querying AI logs: {str(e)}"


class AILogsQueryInput(BaseModel):
    """Input for AI logs query tool"""
    query_type: str = Field(description="Type of query: 'recent', 'stats', or 'search'")
    organization_id: Optional[str] = Field(default=None, description="Organization ID (optional, defaults to current org)")
    user_id: Optional[str] = Field(default=None, description="User ID to filter by (optional)")
    date_from: Optional[str] = Field(default=None, description="Date filter: 'today', 'yesterday', 'week', 'month' (optional)")
    limit: int = Field(default=10, description="Number of results to return")


def get_erp_tools() -> List[Tool]:
    """
    Get all ERP tools for LangChain agents
    
    Returns:
        List of LangChain tools
    """
    tools = [
        StructuredTool.from_function(
            coroutine=call_api_tool,
            name="call_api",
            description="""Call ERP API endpoints to retrieve or modify data.
            Use this when you need to:
            - Get user information
            - Create/update/delete records
            - Access business data
            
            Examples:
            - GET /api/v1/users - List users
            - POST /api/v1/sales/orders - Create order
            - GET /api/v1/inventory/products - List products
            """,
            args_schema=APICallInput
        ),
        
        StructuredTool.from_function(
            coroutine=query_data_tool,
            name="query_database",
            description="""Query ERP databases for statistics and summaries.
            Use this when you need:
            - User statistics (total, active, recent signups)
            - Conversation analytics
            - Cache statistics
            - System overview
            
            Query types: users, conversations, cache, system
            """,
            args_schema=DataQueryInput
        ),
        
        StructuredTool.from_function(
            coroutine=search_docs_tool,
            name="search_documentation",
            description="""Search ERP documentation and knowledge base.
            Use this when you need to:
            - Explain how the system works
            - Find technical documentation
            - Answer questions about features
            - Provide implementation details
            
            Always search docs first before answering questions about the ERP system.
            """,
            args_schema=DocumentSearchInput
        ),
        
        StructuredTool.from_function(
            coroutine=create_background_task_tool,
            name="create_background_task",
            description="""Create a background task for long-running operations.
            Use this when user requests:
            - Report generation (PDF/Excel)
            - Complex data analysis
            - Forecast calculations
            - Bulk data exports
            
            Task types: report_generation, chart_generation, forecast_calculation, data_analysis, bulk_export
            
            The user will be notified via WebSocket when the task completes.
            """,
            args_schema=BackgroundTaskInput
        ),
        
        StructuredTool.from_function(
            coroutine=generate_chart_tool,
            name="generate_chart",
            description="""Generate interactive charts and visualizations.
            Use this when user wants to see:
            - Sales trends (line/area charts)
            - Comparisons (bar charts)
            - Distributions (pie/donut charts)
            - Forecasts (line charts with predictions)
            - KPI metrics
            - Data tables
            
            The chart will be rendered directly in the chat interface.
            """,
            args_schema=ChartGenerationInput
        ),
        
        StructuredTool.from_function(
            coroutine=query_ai_logs_tool,
            name="query_ai_copilot_logs",
            description="""Query AI Copilot audit logs (ADMIN ONLY).
            Use this when admin users ask about:
            - "Show me recent AI logs"
            - "What queries did user X ask today?"
            - "Show me AI Copilot usage statistics"
            - "Show me failed AI queries"
            - "What tools are being used most?"
            
            Query types:
            - 'recent': Get recent interactions
            - 'stats': Get usage statistics
            - 'search': Search logs with filters
            
            Only administrators can access these logs.
            """,
            args_schema=AILogsQueryInput
        ),
    ]
    
    return tools
