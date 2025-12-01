"""
Test MCP Foundation

Tests for Phase 1: MCP Foundation implementation.
"""

import pytest
import asyncio
from mcp.client.mcp_client import MCPClient
from mcp.client.tool_discovery import ToolDiscovery
from mcp.client.code_executor import CodeExecutor
from mcp.sandbox.security_rules import SecurityValidator


class TestToolDiscovery:
    """Test tool discovery system"""
    
    @pytest.mark.asyncio
    async def test_tool_discovery_initialization(self):
        """Test tool discovery initializes correctly"""
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        assert discovery.tool_index is not None
        assert len(discovery.tool_index) > 0
        
        await discovery.close()
    
    @pytest.mark.asyncio
    async def test_discover_tools(self):
        """Test discovering tools for a task"""
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        tools = await discovery.discover_tools(
            task_description="Get list of users from API",
            detail_level="name_only"
        )
        
        assert isinstance(tools, list)
        assert len(tools) > 0
        
        # Should find call_api tool
        tool_names = [t["name"] for t in tools]
        assert "call_api" in tool_names
        
        await discovery.close()
    
    @pytest.mark.asyncio
    async def test_tool_detail_levels(self):
        """Test different detail levels"""
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        # Name only
        tools_name_only = await discovery.discover_tools(
            task_description="search documentation",
            detail_level="name_only"
        )
        
        # With description
        tools_with_desc = await discovery.discover_tools(
            task_description="search documentation",
            detail_level="with_description"
        )
        
        assert len(tools_name_only) > 0
        assert len(tools_with_desc) > 0
        
        # With description should have more info
        if len(tools_with_desc) > 0:
            assert "description" in tools_with_desc[0]
        
        await discovery.close()


class TestSecurityValidator:
    """Test security validation"""
    
    def test_safe_code(self):
        """Test that safe code passes validation"""
        validator = SecurityValidator()
        
        safe_code = """
import json
from mcp.servers.erp_api import call_api

async def main():
    result = await call_api("GET", "/api/v1/users", "token")
    return result
"""
        
        is_safe, violations = validator.validate(safe_code)
        assert is_safe is True
        assert len(violations) == 0
    
    def test_blocked_imports(self):
        """Test that dangerous imports are blocked"""
        validator = SecurityValidator()
        
        dangerous_code = """
import os
os.system("rm -rf /")
"""
        
        is_safe, violations = validator.validate(dangerous_code)
        assert is_safe is False
        assert len(violations) > 0
    
    def test_blocked_eval(self):
        """Test that eval is blocked"""
        validator = SecurityValidator()
        
        dangerous_code = """
eval("print('hello')")
"""
        
        is_safe, violations = validator.validate(dangerous_code)
        assert is_safe is False
        assert "eval" in str(violations).lower()
    
    def test_pii_tokenization(self):
        """Test PII tokenization"""
        validator = SecurityValidator()
        
        data = "Contact john@example.com or call 555-123-4567"
        tokenized = validator.tokenize_pii(data)
        
        assert "john@example.com" not in tokenized
        assert "555-123-4567" not in tokenized
        assert "[EMAIL_1]" in tokenized
        assert "[PHONE_1]" in tokenized


class TestCodeExecutor:
    """Test code execution"""
    
    @pytest.mark.asyncio
    async def test_executor_initialization(self):
        """Test executor initializes"""
        executor = CodeExecutor()
        await executor.initialize()
        
        assert executor.security_validator is not None
    
    @pytest.mark.asyncio
    async def test_execute_safe_code(self):
        """Test executing safe code"""
        executor = CodeExecutor()
        await executor.initialize()
        
        code = """
result = {"success": True, "message": "Hello from MCP"}
print(result)
"""
        
        result = await executor.execute(
            code=code,
            user_context={"user_id": "test"},
            execution_id="test_1",
            timeout=5
        )
        
        assert result["success"] is True
        assert "Hello from MCP" in result.get("output", "")
    
    @pytest.mark.asyncio
    async def test_execute_unsafe_code(self):
        """Test that unsafe code is blocked"""
        executor = CodeExecutor()
        await executor.initialize()
        
        code = """
import os
os.system("echo 'dangerous'")
"""
        
        result = await executor.execute(
            code=code,
            user_context={"user_id": "test"},
            execution_id="test_2",
            timeout=5
        )
        
        assert result["success"] is False
        assert "violations" in result or "error" in result


class TestMCPClient:
    """Test MCP client"""
    
    @pytest.mark.asyncio
    async def test_mcp_client_initialization(self):
        """Test MCP client initializes"""
        client = MCPClient()
        await client.initialize()
        
        assert client.tool_discovery is not None
        assert client.code_executor is not None
    
    @pytest.mark.asyncio
    async def test_get_execution_stats(self):
        """Test getting execution stats"""
        client = MCPClient()
        await client.initialize()
        
        stats = await client.get_execution_stats()
        
        assert "total_executions" in stats
        assert "successful" in stats
        assert "success_rate" in stats


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
