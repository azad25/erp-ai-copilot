"""
API Call Tool

Tool for AI agents to call ERP API endpoints.
Includes RBAC checks and response formatting.
"""

from typing import Dict, Any, Optional
import structlog

from app.services.api_gateway_client import get_api_gateway_client
from app.services.rbac_service import get_rbac_service

logger = structlog.get_logger(__name__)


class APICallTool:
    """Tool for making API calls from AI agents"""
    
    def __init__(self):
        self.name = "api_call"
        self.description = "Call ERP API endpoints to retrieve or modify data"
        self.rbac_service = get_rbac_service()
    
    async def execute(
        self,
        method: str,
        endpoint: str,
        user_context: Dict[str, Any],
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute API call with RBAC checks
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            user_context: User context with role, org_id, user_id, token
            data: Request body data
            params: Query parameters
            
        Returns:
            API response with success status and data
        """
        try:
            # Extract user info
            user_role = user_context.get("role", "user")
            user_token = user_context.get("token")
            user_id = user_context.get("user_id")
            org_id = user_context.get("organization_id")
            
            logger.info(
                "API call requested",
                method=method,
                endpoint=endpoint,
                user_role=user_role,
                user_id=user_id
            )
            
            # Check RBAC permissions
            can_call, reason = self.rbac_service.can_call_api(
                user_role=user_role,
                method=method,
                endpoint=endpoint
            )
            
            if not can_call:
                logger.warning(
                    "API call denied",
                    user_role=user_role,
                    endpoint=endpoint,
                    reason=reason
                )
                return {
                    "success": False,
                    "error": {
                        "message": "Permission denied",
                        "reason": reason,
                        "required_role": "admin or super_admin"
                    },
                    "data": None
                }
            
            # Get API client
            api_client = await get_api_gateway_client()
            
            # Make API call
            response = await api_client.call_api(
                method=method,
                endpoint=endpoint,
                user_token=user_token,
                data=data,
                params=params
            )
            
            # Filter response data based on user permissions
            if response.get("success") and response.get("data"):
                response["data"] = self._filter_response_data(
                    response["data"],
                    user_role,
                    org_id,
                    user_id
                )
            
            logger.info(
                "API call completed",
                method=method,
                endpoint=endpoint,
                success=response.get("success"),
                status_code=response.get("status_code")
            )
            
            return response
            
        except Exception as e:
            logger.error(
                "API call error",
                method=method,
                endpoint=endpoint,
                error=str(e)
            )
            return {
                "success": False,
                "error": {
                    "message": "API call failed",
                    "details": str(e)
                },
                "data": None
            }
    
    def _filter_response_data(
        self,
        data: Any,
        user_role: str,
        org_id: str,
        user_id: str
    ) -> Any:
        """Filter response data based on user permissions"""
        # Super admin sees everything
        if user_role.lower() == "super_admin":
            return data
        
        # If data is a list, filter items
        if isinstance(data, list):
            return self.rbac_service.filter_data_by_access(
                user_role=user_role,
                user_org_id=org_id,
                user_id=user_id,
                data_list=data
            )
        
        # If data is a dict with items/results, filter those
        if isinstance(data, dict):
            if "items" in data and isinstance(data["items"], list):
                data["items"] = self.rbac_service.filter_data_by_access(
                    user_role=user_role,
                    user_org_id=org_id,
                    user_id=user_id,
                    data_list=data["items"]
                )
            elif "results" in data and isinstance(data["results"], list):
                data["results"] = self.rbac_service.filter_data_by_access(
                    user_role=user_role,
                    user_org_id=org_id,
                    user_id=user_id,
                    data_list=data["results"]
                )
            
            # Check if single item belongs to user's org
            if "organization_id" in data:
                if user_role.lower() != "admin" and data["organization_id"] != org_id:
                    return None  # Hide data from other orgs
        
        return data
    
    def format_for_llm(self, response: Dict[str, Any]) -> str:
        """Format API response for LLM consumption"""
        api_client = None
        try:
            # Use sync method to get client
            import asyncio
            loop = asyncio.get_event_loop()
            api_client = loop.run_until_complete(get_api_gateway_client())
        except:
            pass
        
        if api_client:
            return api_client.format_api_response_for_llm(response)
        
        # Fallback formatting
        if not response.get("success"):
            return f"API Error: {response.get('error', {}).get('message', 'Unknown error')}"
        
        return f"API Success: {response.get('data')}"
    
    def get_tool_schema(self) -> Dict[str, Any]:
        """Get tool schema for LLM function calling"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                        "description": "HTTP method"
                    },
                    "endpoint": {
                        "type": "string",
                        "description": "API endpoint path (e.g., /api/v1/users)"
                    },
                    "data": {
                        "type": "object",
                        "description": "Request body data (for POST, PUT, PATCH)"
                    },
                    "params": {
                        "type": "object",
                        "description": "Query parameters"
                    }
                },
                "required": ["method", "endpoint"]
            }
        }


# Global instance
_api_call_tool: Optional[APICallTool] = None


def get_api_call_tool() -> APICallTool:
    """Get or create API Call Tool instance"""
    global _api_call_tool
    
    if _api_call_tool is None:
        _api_call_tool = APICallTool()
    
    return _api_call_tool
