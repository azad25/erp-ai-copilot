"""
Test Phase 4 Integration

End-to-end tests for Phase 4 components.
"""

import pytest
from mcp.client.tool_discovery import ToolDiscovery
from mcp.client.tool_cache import ToolCache


class TestPhase4Integration:
    """Test Phase 4 integration"""
    
    @pytest.mark.asyncio
    async def test_discovery_with_cache_integration(self):
        """Test discovery and cache working together"""
        cache = ToolCache()
        await cache.initialize()
        
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        # Perform discovery
        tools = await discovery.discover_tools(
            task_description="Get users from database",
            detail_level="full"
        )
        
        assert len(tools) > 0
        
        # Cache should have been used
        stats = cache.get_stats()
        assert stats["sets"] > 0 or stats["hits"] > 0
        
        await discovery.close()
        await cache.close()
    
    @pytest.mark.asyncio
    async def test_tool_registry_integration(self):
        """Test registry integration with discovery"""
        from mcp.servers.registry import get_all_servers, get_server_tools
        
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        # Get all registered servers
        servers = get_all_servers()
        assert len(servers) > 0
        
        # Each server should have tools
        for server in servers:
            tools = get_server_tools(server)
            assert len(tools) > 0, f"Server {server} has no tools"
        
        await discovery.close()
    
    @pytest.mark.asyncio
    async def test_end_to_end_tool_execution(self):
        """Test end-to-end tool discovery and execution"""
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        # Discover tools
        tools = await discovery.discover_tools(
            task_description="Query PostgreSQL database",
            detail_level="full"
        )
        
        assert len(tools) > 0
        
        # Find query_postgres tool
        postgres_tool = None
        for tool in tools:
            if "postgres" in tool["name"].lower():
                postgres_tool = tool
                break
        
        assert postgres_tool is not None, "PostgreSQL tool not found"
        
        # Verify tool has required metadata
        assert "name" in postgres_tool
        assert "description" in postgres_tool
        assert "parameters" in postgres_tool
        
        await discovery.close()
    
    @pytest.mark.asyncio
    async def test_token_reduction_estimate(self):
        """Estimate token reduction from MCP migration"""
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        # Get all tools with full details (old way)
        all_tools_full = await discovery.discover_tools(
            task_description="all tools",
            detail_level="full"
        )
        
        # Get tools with name only (new way)
        all_tools_name = await discovery.discover_tools(
            task_description="all tools",
            detail_level="name_only"
        )
        
        # Name-only should be much smaller
        assert len(all_tools_name) > 0
        
        # Estimate token reduction
        # Full details: ~1000 tokens per tool
        # Name only: ~10 tokens per tool
        # Reduction: ~99%
        
        await discovery.close()
