#!/usr/bin/env python3
"""
Validate MCP Phase 1 Implementation

Quick validation script to check if Phase 1 is set up correctly.
"""

import asyncio
import sys
from pathlib import Path


async def validate_phase1():
    """Validate Phase 1 implementation"""
    print("🚀 Validating MCP Phase 1 Implementation\n")
    
    checks_passed = 0
    checks_total = 0
    
    # Check 1: Directory structure
    print("✓ Checking directory structure...")
    checks_total += 1
    required_dirs = [
        "mcp/client",
        "mcp/sandbox",
        "mcp/servers/erp-api",
        "mcp/servers/knowledge-base",
        "tests/mcp"
    ]
    
    all_dirs_exist = True
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            print(f"  ✗ Missing directory: {dir_path}")
            all_dirs_exist = False
    
    if all_dirs_exist:
        print("  ✓ All directories exist")
        checks_passed += 1
    
    # Check 2: Core files
    print("\n✓ Checking core files...")
    checks_total += 1
    required_files = [
        "mcp/client/mcp_client.py",
        "mcp/client/tool_discovery.py",
        "mcp/client/code_executor.py",
        "mcp/sandbox/security_rules.py",
        "mcp/sandbox/docker_sandbox.py",
        "mcp/servers/erp-api/call_api.py",
        "mcp/servers/knowledge-base/search_documentation.py"
    ]
    
    all_files_exist = True
    for file_path in required_files:
        if not Path(file_path).exists():
            print(f"  ✗ Missing file: {file_path}")
            all_files_exist = False
    
    if all_files_exist:
        print("  ✓ All core files exist")
        checks_passed += 1
    
    # Check 3: Import MCP client
    print("\n✓ Checking MCP client import...")
    checks_total += 1
    try:
        from mcp.client import MCPClient, ToolDiscovery, CodeExecutor
        from mcp.sandbox import SecurityValidator
        print("  ✓ MCP modules import successfully")
        checks_passed += 1
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
    
    # Check 4: Tool discovery
    print("\n✓ Checking tool discovery...")
    checks_total += 1
    try:
        from mcp.client import ToolDiscovery
        discovery = ToolDiscovery()
        await discovery.initialize()
        
        if len(discovery.tool_index) > 0:
            print(f"  ✓ Tool index built: {len(discovery.tool_index)} servers found")
            for server, tools in discovery.tool_index.items():
                print(f"    - {server}: {len(tools)} tools")
            checks_passed += 1
        else:
            print("  ✗ No tools found in index")
        
        await discovery.close()
    except Exception as e:
        print(f"  ✗ Tool discovery error: {e}")
    
    # Check 5: Security validator
    print("\n✓ Checking security validator...")
    checks_total += 1
    try:
        from mcp.sandbox import SecurityValidator
        validator = SecurityValidator()
        
        # Test safe code
        safe_code = "import json\nresult = {'success': True}"
        is_safe, violations = validator.validate(safe_code)
        
        if is_safe:
            print("  ✓ Security validator working (safe code passed)")
            checks_passed += 1
        else:
            print(f"  ✗ Security validator failed on safe code: {violations}")
    except Exception as e:
        print(f"  ✗ Security validator error: {e}")
    
    # Check 6: Code executor
    print("\n✓ Checking code executor...")
    checks_total += 1
    try:
        from mcp.client import CodeExecutor
        executor = CodeExecutor()
        await executor.initialize()
        
        # Test simple execution
        code = "result = {'success': True, 'message': 'Hello MCP'}\nprint(result)"
        result = await executor.execute(
            code=code,
            user_context={"user_id": "test"},
            execution_id="validation_test",
            timeout=5
        )
        
        if result.get("success"):
            print("  ✓ Code executor working")
            checks_passed += 1
        else:
            print(f"  ✗ Code execution failed: {result.get('error')}")
    except Exception as e:
        print(f"  ✗ Code executor error: {e}")
    
    # Check 7: MCP tools
    print("\n✓ Checking MCP tools...")
    checks_total += 1
    try:
        from mcp.servers.erp_api import call_api
        from mcp.servers.knowledge_base import search_documentation
        
        print("  ✓ MCP tools import successfully")
        print("    - call_api")
        print("    - search_documentation")
        checks_passed += 1
    except ImportError as e:
        print(f"  ✗ Tool import error: {e}")
    
    # Summary
    print("\n" + "="*50)
    print(f"📊 Validation Summary: {checks_passed}/{checks_total} checks passed")
    print("="*50)
    
    if checks_passed == checks_total:
        print("\n✅ Phase 1 validation PASSED! Ready to proceed.")
        print("\nNext steps:")
        print("1. Run tests: pytest tests/mcp/test_mcp_foundation.py -v")
        print("2. Start Phase 2: Kafka Task System")
        return 0
    else:
        print("\n❌ Phase 1 validation FAILED. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(validate_phase1())
    sys.exit(exit_code)
