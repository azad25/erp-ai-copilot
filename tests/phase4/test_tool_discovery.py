"""
Test Tool Discovery Optimization

Verify optimized tool discovery performance.
"""

import pytest
import time
from mcp.client.tool_discovery import ToolDiscovery


class TestToolDiscoveryOptimization:
    """Test optimized tool discovery"""
    
    @pytest.mark.asyncio
    async def test_discovery_initialization(self):
        """Test discovery can be initialized"""
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        assert discovery is not None
        await discovery.close()
    
    @pytest.mark.asyncio
    async def test_discovery_performance(self):
        """Test discovery performance is under 200ms"""
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        # Time tool discovery
        start_time = time.time()
        tools = await discovery.discover_tools(
            task_description="Get users from database",
            detail_level="name_only"
        )
        discovery_time = (time.time() - start_time) * 1000  # ms
        
        # Should be under 200ms
        assert discovery_time < 200, f"Discovery took {discovery_time:.1f}ms (target: <200ms)"
        
        await discovery.close()
    
    @pytest.mark.asyncio
    async def test_discovery_returns_relevant_tools(self):
        """Test discovery returns relevant tools"""
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        # Search for database-related tools
        tools = await discovery.discover_tools(
            task_description="Query PostgreSQL database",
            detail_level="with_description"
        )
        
        assert len(tools) > 0, "No tools discovered"
        
        # Should include database tools
        tool_names = [t["name"] for t in tools]
        assert any("postgres" in name.lower() or "database" in name.lower() for name in tool_names)
        
        await discovery.close()
    
    @pytest.mark.asyncio
    async def test_discovery_detail_levels(self):
        """Test different detail levels"""
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        task = "Get users from ERP system"
        
        # Test name_only
        tools_name = await discovery.discover_tools(task, detail_level="name_only")
        assert len(tools_name) > 0
        assert "name" in tools_name[0]
        
        # Test with_description
        tools_desc = await discovery.discover_tools(task, detail_level="with_description")
        assert len(tools_desc) > 0
        assert "description" in tools_desc[0]
        
        # Test full
        tools_full = await discovery.discover_tools(task, detail_level="full")
        assert len(tools_full) > 0
        assert "parameters" in tools_full[0]
        
        await discovery.close()
    
    @pytest.mark.asyncio
    async def test_discovery_with_cache(self):
        """Test discovery uses cache"""
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        task = "Get users from database"
        
        # First call (cache miss)
        start1 = time.time()
        tools1 = await discovery.discover_tools(task, detail_level="name_only")
        time1 = (time.time() - start1) * 1000
        
        # Second call (should be cached)
        start2 = time.time()
        tools2 = await discovery.discover_tools(task, detail_level="name_only")
        time2 = (time.time() - start2) * 1000
        
        # Cached call should be faster
        assert time2 < time1, "Cached call should be faster"
        
        # Results should be the same
        assert len(tools1) == len(tools2)
        
        await discovery.close()
    
    @pytest.mark.asyncio
    async def test_discovery_max_results(self):
        """Test max_results parameter"""
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        # Request only 3 tools
        tools = await discovery.discover_tools(
            task_description="ERP operations",
            detail_level="name_only",
            max_results=3
        )
        
        assert len(tools) <= 3, "Should return at most 3 tools"
        
        await discovery.close()
