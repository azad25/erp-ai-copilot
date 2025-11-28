"""
API Gateway Client

Service for making HTTP requests to any ERP API endpoint.
Handles authentication, request formatting, and response parsing.
"""

from typing import Dict, Any, Optional, List
import httpx
import structlog
from datetime import datetime

from app.config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class APIGatewayClient:
    """Client for calling ERP API endpoints through the API Gateway"""
    
    def __init__(self):
        self.base_url = settings.api_gateway.url or "http://api-gateway:8000"
        self.timeout = float(settings.api_gateway.timeout or 30)
        self._client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self):
        """Initialize HTTP client"""
        if not self._client:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                follow_redirects=True
            )
            logger.info("API Gateway Client initialized", base_url=self.base_url)
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def call_api(
        self,
        method: str,
        endpoint: str,
        user_token: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Call any ERP API endpoint
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint path (e.g., "/api/v1/users")
            user_token: User's JWT token for authentication
            data: Request body data (for POST, PUT, PATCH)
            params: Query parameters
            headers: Additional headers
            
        Returns:
            API response as dictionary
        """
        if not self._client:
            await self.initialize()
        
        # Prepare headers
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Add user token if provided
        if user_token:
            request_headers["Authorization"] = f"Bearer {user_token}"
        
        # Add custom headers
        if headers:
            request_headers.update(headers)
        
        # Ensure endpoint starts with /
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        
        try:
            logger.info(
                "Calling API",
                method=method,
                endpoint=endpoint,
                has_token=bool(user_token)
            )
            
            # Make request
            response = await self._client.request(
                method=method.upper(),
                url=endpoint,
                json=data,
                params=params,
                headers=request_headers
            )
            
            # Parse response
            result = {
                "success": response.is_success,
                "status_code": response.status_code,
                "data": None,
                "error": None,
                "headers": dict(response.headers),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Try to parse JSON response
            try:
                result["data"] = response.json()
            except Exception:
                result["data"] = response.text
            
            # Handle errors
            if not response.is_success:
                result["error"] = {
                    "message": f"API request failed with status {response.status_code}",
                    "status_code": response.status_code,
                    "response": result["data"]
                }
                logger.warning(
                    "API request failed",
                    method=method,
                    endpoint=endpoint,
                    status_code=response.status_code
                )
            else:
                logger.info(
                    "API request successful",
                    method=method,
                    endpoint=endpoint,
                    status_code=response.status_code
                )
            
            return result
            
        except httpx.TimeoutException as e:
            logger.error("API request timeout", endpoint=endpoint, error=str(e))
            return {
                "success": False,
                "status_code": 408,
                "data": None,
                "error": {
                    "message": "Request timeout",
                    "details": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error("API request error", endpoint=endpoint, error=str(e))
            return {
                "success": False,
                "status_code": 500,
                "data": None,
                "error": {
                    "message": "Request failed",
                    "details": str(e)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def get(
        self,
        endpoint: str,
        user_token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """GET request"""
        return await self.call_api("GET", endpoint, user_token, params=params)
    
    async def post(
        self,
        endpoint: str,
        data: Dict[str, Any],
        user_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """POST request"""
        return await self.call_api("POST", endpoint, user_token, data=data)
    
    async def put(
        self,
        endpoint: str,
        data: Dict[str, Any],
        user_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """PUT request"""
        return await self.call_api("PUT", endpoint, user_token, data=data)
    
    async def delete(
        self,
        endpoint: str,
        user_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """DELETE request"""
        return await self.call_api("DELETE", endpoint, user_token)
    
    async def get_available_endpoints(self) -> List[Dict[str, Any]]:
        """Get list of available API endpoints"""
        # This would typically call an API discovery endpoint
        # For now, return common endpoints
        return [
            {
                "path": "/api/v1/users",
                "methods": ["GET", "POST"],
                "description": "User management"
            },
            {
                "path": "/api/v1/users/{id}",
                "methods": ["GET", "PUT", "DELETE"],
                "description": "User operations"
            },
            {
                "path": "/api/v1/organizations",
                "methods": ["GET", "POST"],
                "description": "Organization management"
            },
            {
                "path": "/api/v1/sales/orders",
                "methods": ["GET", "POST"],
                "description": "Sales orders"
            },
            {
                "path": "/api/v1/inventory/products",
                "methods": ["GET", "POST"],
                "description": "Product inventory"
            },
            {
                "path": "/api/v1/finance/transactions",
                "methods": ["GET", "POST"],
                "description": "Financial transactions"
            }
        ]
    
    def format_api_response_for_llm(self, response: Dict[str, Any]) -> str:
        """Format API response for LLM consumption"""
        if not response.get("success"):
            error = response.get("error", {})
            return f"""API Request Failed:
Status: {response.get('status_code')}
Error: {error.get('message', 'Unknown error')}
Details: {error.get('details', 'No details available')}"""
        
        data = response.get("data")
        status = response.get("status_code")
        
        formatted = f"""API Request Successful:
Status: {status}

Response Data:
{self._format_data(data)}"""
        
        return formatted
    
    def _format_data(self, data: Any, indent: int = 0) -> str:
        """Recursively format data for display"""
        if data is None:
            return "null"
        
        if isinstance(data, dict):
            lines = []
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{'  ' * indent}{key}:")
                    lines.append(self._format_data(value, indent + 1))
                else:
                    lines.append(f"{'  ' * indent}{key}: {value}")
            return "\n".join(lines)
        
        elif isinstance(data, list):
            if not data:
                return "[]"
            lines = []
            for i, item in enumerate(data[:10]):  # Limit to first 10 items
                lines.append(f"{'  ' * indent}[{i}]:")
                lines.append(self._format_data(item, indent + 1))
            if len(data) > 10:
                lines.append(f"{'  ' * indent}... and {len(data) - 10} more items")
            return "\n".join(lines)
        
        else:
            return str(data)


# Global instance
_api_gateway_client: Optional[APIGatewayClient] = None


async def get_api_gateway_client() -> APIGatewayClient:
    """Get or create API Gateway Client instance"""
    global _api_gateway_client
    
    if _api_gateway_client is None:
        _api_gateway_client = APIGatewayClient()
        await _api_gateway_client.initialize()
    
    return _api_gateway_client


# Create a singleton instance for backward compatibility
class APIGatewayClientSingleton:
    """Singleton wrapper for backward compatibility"""
    _instance: Optional[APIGatewayClient] = None
    
    def __getattr__(self, name):
        if self._instance is None:
            # Create instance synchronously for imports
            self._instance = APIGatewayClient()
        return getattr(self._instance, name)
    
    async def initialize(self):
        if self._instance is None:
            self._instance = APIGatewayClient()
        await self._instance.initialize()


# Export singleton instance for backward compatibility
api_gateway_client = APIGatewayClientSingleton()
