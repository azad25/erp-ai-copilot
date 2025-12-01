"""
Call API Tool (MCP Format)

MCP-compatible wrapper for calling ERP API endpoints.
This tool can be imported and used in generated code.
"""

from typing import Dict, Any, Optional
import httpx
import structlog

logger = structlog.get_logger(__name__)


async def call_api(
    method: str,
    endpoint: str,
    user_token: str,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Call ERP API endpoint
    
    This is an MCP tool wrapper that can be imported and used in generated code.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        endpoint: API endpoint path (e.g., /api/v1/users)
        user_token: JWT token for authentication
        data: Request body data (for POST, PUT, PATCH)
        params: Query parameters
        
    Returns:
        API response with success status and data
        
    Example:
        ```python
        from mcp.servers.erp_api import call_api
        
        result = await call_api(
            method="GET",
            endpoint="/api/v1/users",
            user_token=user_context["token"],
            params={"limit": 10}
        )
        ```
    """
    # Get API Gateway URL from environment
    import os
    api_gateway_url = os.getenv("API_GATEWAY_URL", "http://localhost:8000")
    
    logger.info(
        "Calling API",
        method=method,
        endpoint=endpoint
    )
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=f"{api_gateway_url}{endpoint}",
                headers={
                    "Authorization": f"Bearer {user_token}",
                    "Content-Type": "application/json"
                },
                json=data,
                params=params
            )
            
            # Parse response
            try:
                response_data = response.json()
            except:
                response_data = {"text": response.text}
            
            result = {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "data": response_data
            }
            
            logger.info(
                "API call completed",
                method=method,
                endpoint=endpoint,
                status_code=response.status_code,
                success=result["success"]
            )
            
            return result
            
    except httpx.TimeoutException:
        logger.error(
            "API call timeout",
            method=method,
            endpoint=endpoint
        )
        return {
            "success": False,
            "error": "Request timeout",
            "status_code": 408
        }
        
    except Exception as e:
        logger.error(
            "API call failed",
            method=method,
            endpoint=endpoint,
            error=str(e)
        )
        return {
            "success": False,
            "error": str(e),
            "status_code": 500
        }


# Tool metadata for discovery
__tool_metadata__ = {
    "name": "call_api",
    "description": "Call ERP API endpoints to retrieve or modify data",
    "category": "API",
    "parameters": {
        "method": {
            "type": "string",
            "description": "HTTP method",
            "required": True,
            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
        },
        "endpoint": {
            "type": "string",
            "description": "API endpoint path",
            "required": True
        },
        "user_token": {
            "type": "string",
            "description": "JWT authentication token",
            "required": True
        },
        "data": {
            "type": "object",
            "description": "Request body data",
            "required": False
        },
        "params": {
            "type": "object",
            "description": "Query parameters",
            "required": False
        }
    }
}
