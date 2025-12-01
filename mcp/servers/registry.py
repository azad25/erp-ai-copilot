"""
MCP Server Registry

Central registry for all MCP servers and their tools.
"""

from typing import Dict, List, Optional

SERVER_REGISTRY: Dict[str, Dict] = {
    "erp-api": {
        "name": "ERP API Server",
        "description": "ERP system API operations",
        "tools": ["call_api", "get_users", "create_order", "update_product", "get_customers"]
    },
    "database": {
        "name": "Database Server",
        "description": "Database query and manipulation",
        "tools": ["query_postgres", "query_mongodb", "execute_sql"]
    },
    "analytics": {
        "name": "Analytics Server",
        "description": "Analytics and reporting",
        "tools": ["generate_report", "create_chart", "forecast"]
    },
    "knowledge-base": {
        "name": "Knowledge Base Server",
        "description": "Knowledge and documentation access",
        "tools": ["search_documentation", "semantic_search", "retrieve_context", "architecture_info"]
    },
    "communication": {
        "name": "Communication Server",
        "description": "Communication and notifications",
        "tools": ["send_email", "send_notification", "send_message"]
    },
    "integrations": {
        "name": "Integrations Server",
        "description": "External system integrations",
        "tools": ["call_external_api", "webhook_trigger"]
    },
    "system": {
        "name": "System Server",
        "description": "System-level operations",
        "tools": ["execute_command", "run_script"]
    }
}


def get_all_servers() -> List[str]:
    """Get list of all server names"""
    return list(SERVER_REGISTRY.keys())


def get_server_info(server_name: str) -> Optional[Dict]:
    """Get server information"""
    return SERVER_REGISTRY.get(server_name)


def get_server_tools(server_name: str) -> List[str]:
    """Get tools for a server"""
    server = SERVER_REGISTRY.get(server_name, {})
    return server.get("tools", [])


def get_all_tools() -> Dict[str, List[str]]:
    """Get all tools organized by server"""
    return {
        server: info["tools"]
        for server, info in SERVER_REGISTRY.items()
    }


def find_tool_server(tool_name: str) -> Optional[str]:
    """Find which server contains a tool"""
    for server, info in SERVER_REGISTRY.items():
        if tool_name in info["tools"]:
            return server
    return None
