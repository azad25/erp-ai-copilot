"""
Tool Registry

Centralized registry for managing all tools in the AI Copilot system.
Provides discovery, execution, and management capabilities for tools.
"""

from typing import Dict, List, Optional, Type
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
from .base_tool import BaseTool, ToolRequest, ToolResponse

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry for managing all tools in the system.
    
    Features:
    - Tool discovery and registration
    - Tool execution with monitoring
    - Rate limiting
    - Health monitoring
    - Permission management
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._tool_classes: Dict[str, Type[BaseTool]] = {}
        self._rate_limits: Dict[str, List[datetime]] = defaultdict(list)
        self._execution_stats: Dict[str, Dict] = defaultdict(lambda: {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time": 0.0,
            "last_execution": None
        })
    
    def register_tool(self, tool_instance: BaseTool) -> None:
        """
        Register a tool instance with the registry
        
        Args:
            tool_instance: Instance of BaseTool to register
        """
        tool_name = tool_instance.metadata.name
        self._tools[tool_name] = tool_instance
        logger.info(f"Registered tool: {tool_name}")
    
    def register_tool_class(self, tool_class: Type[BaseTool]) -> None:
        """
        Register a tool class for lazy instantiation
        
        Args:
            tool_class: BaseTool subclass to register
        """
        tool_instance = tool_class()
        tool_name = tool_instance.metadata.name
        self._tool_classes[tool_name] = tool_class
        self.register_tool(tool_instance)
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        Get a tool by name
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(tool_name)
    
    def list_tools(self) -> List[Dict[str, any]]:
        """
        List all available tools with their metadata
        
        Returns:
            List of tool metadata dictionaries
        """
        return [
            {
                **tool.get_schema(),
                "available": tool.is_available(),
                "execution_count": self._execution_stats[tool.metadata.name]["total_executions"]
            }
            for tool in self._tools.values()
        ]
    
    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """
        Get all tools in a specific category
        
        Args:
            category: Tool category
            
        Returns:
            List of tools in the category
        """
        return [
            tool for tool in self._tools.values()
            if tool.metadata.category.lower() == category.lower()
        ]
    
    def search_tools(self, query: str) -> List[Dict[str, any]]:
        """
        Search tools by name or description
        
        Args:
            query: Search query
            
        Returns:
            List of matching tool metadata
        """
        query_lower = query.lower()
        return [
            tool.get_schema()
            for tool in self._tools.values()
            if query_lower in tool.metadata.name.lower() or 
               query_lower in tool.metadata.description.lower()
        ]
    
    def _check_rate_limit(self, tool_name: str, rate_limit: int) -> bool:
        """
        Check if tool execution is within rate limit
        
        Args:
            tool_name: Name of the tool
            rate_limit: Maximum executions per minute
            
        Returns:
            True if within limit, False otherwise
        """
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean old entries
        self._rate_limits[tool_name] = [
            timestamp for timestamp in self._rate_limits[tool_name]
            if timestamp > minute_ago
        ]
        
        if len(self._rate_limits[tool_name]) >= rate_limit:
            return False
        
        self._rate_limits[tool_name].append(now)
        return True
    
    async def execute_tool(self, request: ToolRequest) -> ToolResponse:
        """
        Execute a tool with the given request
        
        Args:
            request: Tool execution request
            
        Returns:
            Tool execution response
        """
        tool_name = request.tool_name
        tool = self.get_tool(tool_name)
        
        if not tool:
            return ToolResponse(
                success=False,
                error=f"Tool '{tool_name}' not found"
            )
        
        if not tool.is_available():
            return ToolResponse(
                success=False,
                error=f"Tool '{tool_name}' is not available"
            )
        
        # Check rate limiting
        rate_limit = tool.metadata.rate_limit
        if rate_limit and not self._check_rate_limit(tool_name, rate_limit):
            return ToolResponse(
                success=False,
                error=f"Rate limit exceeded for tool '{tool_name}'"
            )
        
        # Execute tool
        start_time = datetime.utcnow()
        try:
            response = await tool._execute_with_monitoring(request)
            
            # Update statistics
            stats = self._execution_stats[tool_name]
            stats["total_executions"] += 1
            if response.success:
                stats["successful_executions"] += 1
            else:
                stats["failed_executions"] += 1
            stats["last_execution"] = start_time
            
            # Update average execution time
            if stats["total_executions"] > 0:
                total_time = stats["average_execution_time"] * (stats["total_executions"] - 1)
                total_time += response.execution_time
                stats["average_execution_time"] = total_time / stats["total_executions"]
            
            return response
            
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            self._execution_stats[tool_name]["failed_executions"] += 1
            return ToolResponse(
                success=False,
                error=str(e)
            )
    
    async def execute_tools_batch(self, requests: List[ToolRequest]) -> List[ToolResponse]:
        """
        Execute multiple tools in parallel
        
        Args:
            requests: List of tool execution requests
            
        Returns:
            List of tool execution responses
        """
        tasks = [self.execute_tool(request) for request in requests]
        return await asyncio.gather(*tasks)
    
    def get_tool_stats(self, tool_name: Optional[str] = None) -> Dict[str, any]:
        """
        Get execution statistics for tools
        
        Args:
            tool_name: Specific tool name, or None for all tools
            
        Returns:
            Tool execution statistics
        """
        if tool_name:
            return {
                "tool_name": tool_name,
                **self._execution_stats[tool_name]
            }
        
        return {
            "total_tools": len(self._tools),
            "tool_stats": dict(self._execution_stats)
        }
    
    async def health_check(self) -> Dict[str, any]:
        """
        Perform health check on all registered tools
        
        Returns:
            Health check results
        """
        health_results = {}
        
        for tool_name, tool in self._tools.items():
            try:
                health = await tool.health_check()
                health_results[tool_name] = health
            except Exception as e:
                health_results[tool_name] = {
                    "name": tool_name,
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "tools": health_results,
            "overall_status": "healthy" if all(
                h.get("status") == "healthy" for h in health_results.values()
            ) else "unhealthy"
        }
    
    def clear_registry(self) -> None:
        """Clear all registered tools"""
        self._tools.clear()
        self._tool_classes.clear()
        self._rate_limits.clear()
        self._execution_stats.clear()
        logger.info("Tool registry cleared")


# Global tool registry instance
tool_registry = ToolRegistry()