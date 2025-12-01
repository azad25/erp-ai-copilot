"""
Test Tool Cache

Verify caching functionality and performance.
"""

import pytest
from mcp.client.tool_cache import ToolCache


class TestToolCache:
    """Test tool caching"""
    
    @pytest.mark.asyncio
    async def test_cache_initialization(self):
        """Test cache can be initialized"""
        cache = ToolCache()
        await cache.initialize()
        
        assert cache is not None
        await cache.close()
    
    @pytest.mark.asyncio
    async def test_cache_set_get_tool_definition(self):
        """Test caching tool definitions"""
        cache = ToolCache()
        await cache.initialize()
        
        # Set tool definition
        tool_data = {
            "name": "test_tool",
            "description": "Test tool",
            "parameters": {}
        }
        
        await cache.set_tool_definition(
            server="test-server",
            tool="test_tool",
            detail_level="full",
            data=tool_data
        )
        
        # Get tool definition
        cached = await cache.get_tool_definition(
            server="test-server",
            tool="test_tool",
            detail_level="full"
        )
        
        assert cached is not None
        assert cached["name"] == "test_tool"
        
        await cache.close()
    
    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Test cache miss behavior"""
        cache = ToolCache()
        await cache.initialize()
        
        # Try to get non-existent tool
        cached = await cache.get_tool_definition(
            server="nonexistent",
            tool="nonexistent",
            detail_level="full"
        )
        
        assert cached is None
        assert cache.stats["misses"] > 0
        
        await cache.close()
    
    @pytest.mark.asyncio
    async def test_cache_discovery_results(self):
        """Test caching discovery results"""
        cache = ToolCache()
        await cache.initialize()
        
        # Set discovery result
        results = [
            {"tool": "tool1", "score": 0.9},
            {"tool": "tool2", "score": 0.8}
        ]
        
        await cache.set_discovery_result(
            query="test query",
            results=results
        )
        
        # Get discovery result
        cached = await cache.get_discovery_result("test query")
        
        assert cached is not None
        assert len(cached) == 2
        assert cached[0]["tool"] == "tool1"
        
        await cache.close()
    
    @pytest.mark.asyncio
    async def test_cache_hit_rate(self):
        """Test hit rate calculation"""
        cache = ToolCache()
        await cache.initialize()
        
        # Initial hit rate should be 0
        assert cache.get_hit_rate() == 0.0
        
        # Set and get a tool (should increase hit rate)
        tool_data = {"name": "test"}
        await cache.set_tool_definition("server", "tool", "full", tool_data)
        await cache.get_tool_definition("server", "tool", "full")
        
        # Hit rate should be 100% (1 hit, 0 misses)
        assert cache.get_hit_rate() == 100.0
        
        # Try to get non-existent tool (should decrease hit rate)
        await cache.get_tool_definition("nonexistent", "tool", "full")
        
        # Hit rate should be 50% (1 hit, 1 miss)
        assert cache.get_hit_rate() == 50.0
        
        await cache.close()
    
    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test cache statistics"""
        cache = ToolCache()
        await cache.initialize()
        
        stats = cache.get_stats()
        
        assert "hits" in stats
        assert "misses" in stats
        assert "sets" in stats
        assert "hit_rate" in stats
        assert "cache_size" in stats
        
        await cache.close()
    
    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test cache clearing"""
        cache = ToolCache()
        await cache.initialize()
        
        # Add some data
        await cache.set_tool_definition("server", "tool", "full", {"name": "test"})
        
        # Clear cache
        await cache.clear()
        
        # Data should be gone
        cached = await cache.get_tool_definition("server", "tool", "full")
        assert cached is None
        
        await cache.close()
    
    @pytest.mark.asyncio
    async def test_cache_fallback_to_memory(self):
        """Test fallback to in-memory cache when Redis unavailable"""
        # Use invalid Redis URL to force fallback
        cache = ToolCache(redis_url="redis://invalid:9999")
        await cache.initialize()
        
        # Should still work with in-memory cache
        tool_data = {"name": "test"}
        await cache.set_tool_definition("server", "tool", "full", tool_data)
        
        cached = await cache.get_tool_definition("server", "tool", "full")
        assert cached is not None
        assert cached["name"] == "test"
        
        await cache.close()
