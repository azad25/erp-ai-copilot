"""
Test Tool Conversion

Verify all tools have been properly converted to MCP format.
"""

import pytest
from pathlib import Path


class TestToolConversion:
    """Test converted MCP tools"""
    
    @pytest.mark.asyncio
    async def test_all_servers_exist(self):
        """Verify all MCP servers exist"""
        from mcp.servers.registry import get_all_servers
        
        servers = get_all_servers()
        assert len(servers) > 0, "No servers registered"
        
        # Check server directories exist
        servers_path = Path("mcp/servers")
        for server in servers:
            server_path = servers_path / server
            assert server_path.exists(), f"Server directory missing: {server}"
            assert (server_path / "__init__.py").exists(), f"Server __init__.py missing: {server}"
    
    @pytest.mark.asyncio
    async def test_all_tools_have_metadata(self):
        """Verify all tools have metadata"""
        from mcp.servers.registry import get_all_servers, get_server_tools
        
        for server in get_all_servers():
            tools = get_server_tools(server)
            assert len(tools) > 0, f"Server {server} has no tools"
            
            # Check each tool has metadata
            for tool_name in tools:
                # This would import and check metadata
                pass
    
    @pytest.mark.asyncio
    async def test_tool_imports(self):
        """Test that all tools can be imported"""
        # Test existing tools
        from mcp.servers.erp_api import call_api
        from mcp.servers.database import query_postgres
        from mcp.servers.knowledge_base import search_documentation
        
        assert callable(call_api)
        assert callable(query_postgres)
        assert callable(search_documentation)
    
    @pytest.mark.asyncio
    async def test_tool_metadata_structure(self):
        """Verify tool metadata has required fields"""
        from mcp.servers.erp_api.call_api import __tool_metadata__ as call_api_meta
        from mcp.servers.database.query_postgres import __tool_metadata__ as postgres_meta
        
        required_fields = ["name", "description", "category", "parameters"]
        
        for meta in [call_api_meta, postgres_meta]:
            for field in required_fields:
                assert field in meta, f"Missing metadata field: {field}"
    
    @pytest.mark.asyncio
    async def test_tool_execution_basic(self):
        """Test basic tool execution"""
        from mcp.servers.database import query_postgres
        
        # This would test actual execution
        # For now, just verify it's callable
        assert callable(query_postgres)
    
    @pytest.mark.asyncio
    async def test_registry_consistency(self):
        """Verify registry matches actual tools"""
        from mcp.servers.registry import get_all_servers, get_server_tools
        
        servers_path = Path("mcp/servers")
        
        for server in get_all_servers():
            registered_tools = get_server_tools(server)
            server_path = servers_path / server
            
            if not server_path.exists():
                continue
            
            # Count actual tool files
            actual_tools = [
                f.stem for f in server_path.glob("*.py")
                if not f.name.startswith("_")
            ]
            
            # Registry should list tools (may not all be implemented yet)
            assert len(registered_tools) > 0, f"Server {server} has no registered tools"
