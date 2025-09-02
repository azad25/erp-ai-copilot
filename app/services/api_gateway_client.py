"""
API Gateway Client Service

Handles communication with the ERP API Gateway to access data from various services.
Provides service discovery, authentication, and data retrieval capabilities.
"""

from typing import Dict, List, Any, Optional, Union, Tuple
import asyncio
import json
import logging
from datetime import datetime, timedelta
import aiohttp
from urllib.parse import urljoin
import jwt
from dataclasses import dataclass

from app.config.settings import get_settings
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


@dataclass
class ServiceEndpoint:
    """Service endpoint configuration"""
    name: str
    base_url: str
    version: str
    health_endpoint: str
    auth_required: bool = True


class APIGatewayClient:
    """
    API Gateway Client for ERP Service Communication
    
    Features:
    - Service discovery and health monitoring
    - Authenticated requests to ERP services
    - Data retrieval from multiple services
    - Caching and rate limiting
    - Error handling and retry logic
    """
    
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.api_gateway.url
        self.auth_service = AuthService()
        self.session: Optional[aiohttp.ClientSession] = None
        self.service_registry: Dict[str, ServiceEndpoint] = {}
        self.auth_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        
        # Initialize known services
        self._initialize_service_registry()
    
    async def _ensure_session(self):
        """Ensure HTTP session is initialized"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=aiohttp.TCPConnector(limit=100, limit_per_host=30)
            )
        
    def _initialize_service_registry(self):
        """Initialize known ERP services"""
        self.service_registry = {
            "auth": ServiceEndpoint(
                name="auth-service",
                base_url=f"{self.base_url}/auth",
                version="v1",
                health_endpoint="/health",
                auth_required=False
            ),
            "sales": ServiceEndpoint(
                name="sales-service", 
                base_url=f"{self.base_url}/sales",
                version="v1",
                health_endpoint="/health"
            ),
            "inventory": ServiceEndpoint(
                name="inventory-service",
                base_url=f"{self.base_url}/inventory", 
                version="v1",
                health_endpoint="/health"
            ),
            "finance": ServiceEndpoint(
                name="finance-service",
                base_url=f"{self.base_url}/finance",
                version="v1", 
                health_endpoint="/health"
            ),
            "crm": ServiceEndpoint(
                name="crm-service",
                base_url=f"{self.base_url}/crm",
                version="v1",
                health_endpoint="/health"
            ),
            "hrm": ServiceEndpoint(
                name="hrm-service",
                base_url=f"{self.base_url}/hrm",
                version="v1",
                health_endpoint="/health"
            ),
            "purchase": ServiceEndpoint(
                name="purchase-service",
                base_url=f"{self.base_url}/purchase",
                version="v1",
                health_endpoint="/health"
            ),
            "documents": ServiceEndpoint(
                name="document-service",
                base_url=f"{self.base_url}/documents",
                version="v1",
                health_endpoint="/health"
            )
        }
    
    async def initialize(self):
        """Initialize HTTP session and authenticate"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
            
        await self._authenticate()
        await self._discover_services()
    
    async def _authenticate(self):
        """Authenticate with the API Gateway"""
        try:
            # Use root admin credentials for AI Copilot internal authentication
            settings = get_settings()
            auth_data = {
                "email": settings.api_gateway.admin_email,
                "password": settings.api_gateway.admin_password
            }
            
            auth_url = f"{self.base_url}/auth/login"
            
            async with self.session.post(auth_url, json=auth_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.auth_token = data.get("access_token")
                    
                    # Decode token to get expiration
                    if self.auth_token:
                        try:
                            decoded = jwt.decode(
                                self.auth_token, 
                                options={"verify_signature": False}
                            )
                            self.token_expires_at = datetime.fromtimestamp(decoded.get("exp", 0))
                        except Exception:
                            # Set default expiration
                            self.token_expires_at = datetime.utcnow() + timedelta(hours=1)
                    
                    logger.info("Successfully authenticated with API Gateway")
                else:
                    logger.error(f"Authentication failed: {response.status}")
                    
        except Exception as e:
            logger.error(f"Authentication error: {e}")
    
    async def _discover_services(self):
        """Discover available services from API Gateway"""
        try:
            discovery_url = f"{self.base_url}/discovery/services"
            headers = await self._get_auth_headers()
            
            async with self.session.get(discovery_url, headers=headers) as response:
                if response.status == 200:
                    services = await response.json()
                    
                    for service in services.get("services", []):
                        service_name = service.get("name", "").replace("-service", "")
                        if service_name and service_name not in self.service_registry:
                            self.service_registry[service_name] = ServiceEndpoint(
                                name=service.get("name"),
                                base_url=service.get("url"),
                                version=service.get("version", "v1"),
                                health_endpoint=service.get("health_endpoint", "/health")
                            )
                    
                    logger.info(f"Discovered {len(services.get('services', []))} services")
                    
        except Exception as e:
            logger.warning(f"Service discovery failed: {e}")
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        headers = {}
        
        # Check if token needs refresh
        if (not self.auth_token or 
            not self.token_expires_at or 
            self.token_expires_at <= datetime.utcnow() + timedelta(minutes=5)):
            await self._authenticate()
        
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
            
        return headers
    
    async def get_service_data(
        self,
        service_name: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get data from a specific service
        
        Args:
            service_name: Name of the service (sales, inventory, etc.)
            endpoint: API endpoint path
            params: Query parameters
            filters: Additional filters
            
        Returns:
            Service response data or None if failed
        """
        if not self.session:
            await self.initialize()
            
        service = self.service_registry.get(service_name)
        if not service:
            logger.error(f"Unknown service: {service_name}")
            return None
            
        try:
            url = urljoin(service.base_url, endpoint.lstrip('/'))
            headers = await self._get_auth_headers()
            
            # Combine params and filters
            query_params = {}
            if params:
                query_params.update(params)
            if filters:
                query_params.update(filters)
            
            async with self.session.get(url, headers=headers, params=query_params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    # Token expired, retry once
                    await self._authenticate()
                    headers = await self._get_auth_headers()
                    
                    async with self.session.get(url, headers=headers, params=query_params) as retry_response:
                        if retry_response.status == 200:
                            return await retry_response.json()
                        else:
                            logger.error(f"Service request failed after retry: {retry_response.status}")
                else:
                    logger.error(f"Service request failed: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error calling service {service_name}: {e}")
            
        return None
    
    async def post_service_data(
        self,
        service_name: str,
        endpoint: str,
        data: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Post data to a specific service
        
        Args:
            service_name: Name of the service
            endpoint: API endpoint path
            data: Data to post
            params: Query parameters
            
        Returns:
            Service response data or None if failed
        """
        if not self.session:
            await self.initialize()
            
        service = self.service_registry.get(service_name)
        if not service:
            logger.error(f"Unknown service: {service_name}")
            return None
            
        try:
            url = urljoin(service.base_url, endpoint.lstrip('/'))
            headers = await self._get_auth_headers()
            
            async with self.session.post(url, headers=headers, json=data, params=params) as response:
                if response.status in [200, 201]:
                    return await response.json()
                elif response.status == 401:
                    # Token expired, retry once
                    await self._authenticate()
                    headers = await self._get_auth_headers()
                    
                    async with self.session.post(url, headers=headers, json=data, params=params) as retry_response:
                        if retry_response.status in [200, 201]:
                            return await retry_response.json()
                        else:
                            logger.error(f"Service POST failed after retry: {retry_response.status}")
                else:
                    logger.error(f"Service POST failed: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error posting to service {service_name}: {e}")
            
        return None
    
    async def get_sales_data(
        self,
        data_type: str = "overview",
        filters: Optional[Dict[str, Any]] = None,
        date_range: Optional[tuple[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get sales data"""
        endpoint_map = {
            "overview": "/api/v1/dashboard/overview",
            "invoices": "/api/v1/invoices",
            "customers": "/api/v1/customers", 
            "products": "/api/v1/products",
            "reports": "/api/v1/reports"
        }
        
        endpoint = endpoint_map.get(data_type, "/api/v1/dashboard/overview")
        params = {}
        
        if date_range:
            params["start_date"] = date_range[0]
            params["end_date"] = date_range[1]
            
        return await self.get_service_data("sales", endpoint, params, filters)
    
    async def get_inventory_data(
        self,
        data_type: str = "overview",
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get inventory data"""
        endpoint_map = {
            "overview": "/api/v1/dashboard/overview",
            "products": "/api/v1/products",
            "stock": "/api/v1/stock",
            "movements": "/api/v1/movements",
            "warehouses": "/api/v1/warehouses"
        }
        
        endpoint = endpoint_map.get(data_type, "/api/v1/dashboard/overview")
        return await self.get_service_data("inventory", endpoint, filters=filters)
    
    async def get_finance_data(
        self,
        data_type: str = "overview",
        filters: Optional[Dict[str, Any]] = None,
        date_range: Optional[tuple[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get finance data"""
        endpoint_map = {
            "overview": "/api/v1/dashboard/overview",
            "accounts": "/api/v1/accounts",
            "transactions": "/api/v1/transactions",
            "reports": "/api/v1/reports",
            "budgets": "/api/v1/budgets"
        }
        
        endpoint = endpoint_map.get(data_type, "/api/v1/dashboard/overview")
        params = {}
        
        if date_range:
            params["start_date"] = date_range[0]
            params["end_date"] = date_range[1]
            
        return await self.get_service_data("finance", endpoint, params, filters)
    
    async def get_crm_data(
        self,
        data_type: str = "overview",
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get CRM data"""
        endpoint_map = {
            "overview": "/api/v1/dashboard/overview",
            "customers": "/api/v1/customers",
            "leads": "/api/v1/leads",
            "opportunities": "/api/v1/opportunities",
            "contacts": "/api/v1/contacts"
        }
        
        endpoint = endpoint_map.get(data_type, "/api/v1/dashboard/overview")
        return await self.get_service_data("crm", endpoint, filters=filters)
    
    async def get_hrm_data(
        self,
        data_type: str = "overview",
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Get HRM data"""
        endpoint_map = {
            "overview": "/api/v1/dashboard/overview",
            "employees": "/api/v1/employees",
            "departments": "/api/v1/departments",
            "payroll": "/api/v1/payroll",
            "attendance": "/api/v1/attendance"
        }
        
        endpoint = endpoint_map.get(data_type, "/api/v1/dashboard/overview")
        return await self.get_service_data("hrm", endpoint, filters=filters)
    
    async def execute_database_query(
        self,
        query_type: str,
        table: str,
        data: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        user_role: str = "user"
    ) -> Optional[Dict[str, Any]]:
        """
        Execute database operations based on user prompts and RBAC
        
        Args:
            query_type: Type of operation (select, insert, update, delete)
            table: Target table/collection
            data: Data for insert/update operations
            filters: Filters for select/update/delete operations
            user_role: User role for RBAC validation
            
        Returns:
            Query results or operation status
        """
        # RBAC validation
        allowed_operations = {
            "admin": ["select", "insert", "update", "delete"],
            "manager": ["select", "insert", "update"],
            "user": ["select"],
            "readonly": ["select"]
        }
        
        if query_type not in allowed_operations.get(user_role, []):
            logger.warning(f"User role {user_role} not allowed to perform {query_type}")
            return {"error": "Insufficient permissions"}
        
        # Route to appropriate service based on table
        service_mapping = {
            "invoices": "sales",
            "customers": "crm", 
            "products": "inventory",
            "employees": "hrm",
            "accounts": "finance",
            "transactions": "finance"
        }
        
        service_name = service_mapping.get(table, "sales")  # Default to sales
        
        endpoint = f"/api/v1/database/{query_type}"
        request_data = {
            "table": table,
            "data": data,
            "filters": filters,
            "user_role": user_role
        }
        
        return await self.get_service_data(service_name, endpoint, method="POST", data=data)

    async def discover_services(self) -> Dict[str, Any]:
        """Discover available ERP services through API gateway"""
        try:
            await self._ensure_session()
            
            response = await self._make_authenticated_request(
                "GET", 
                "/api/v1/services/discovery"
            )
            
            # Update service registry
            if response.get("services"):
                for service in response["services"]:
                    self.service_registry[service["name"]] = ServiceEndpoint(
                        name=service["name"],
                        base_url=service["base_url"],
                        health_check_url=service.get("health_check_url"),
                        version=service.get("version"),
                        status=service.get("status", "unknown")
                    )
            
            return response
            
        except Exception as e:
            logger.error(f"Service discovery failed: {e}")
            return {"error": str(e), "services": []}
    
    async def check_service_health(self, service_name: str) -> bool:
        """Check if a service is healthy"""
        service = self.service_registry.get(service_name)
        if not service:
            return False
            
        try:
            url = urljoin(service.base_url, service.health_endpoint)
            
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                return response.status == 200
                
        except Exception:
            return False
    
    async def get_all_services_health(self) -> Dict[str, bool]:
        """Get health status of all services"""
        health_status = {}
        
        tasks = []
        for service_name in self.service_registry.keys():
            tasks.append(self.check_service_health(service_name))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, service_name in enumerate(self.service_registry.keys()):
            health_status[service_name] = results[i] if not isinstance(results[i], Exception) else False
            
        return health_status
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()


# Global API Gateway client instance
api_gateway_client = APIGatewayClient()
