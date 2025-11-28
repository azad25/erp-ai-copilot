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


async def search_docs_tool(query: str, max_results: int = 5) -> str:
    """Search ERP documentation"""
    try:
        documents = await search_documents(query, k=max_results)
        
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
    ]
    
    return tools
