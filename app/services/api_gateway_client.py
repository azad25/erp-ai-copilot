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
try:
    import jwt
except ImportError:
    jwt = None
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
        """Ensure HTTP session is initialized with connection resilience"""
        if self.session is None or self.session.closed:
            # Add DNS resolution and connection timeout settings
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,  # Cache DNS for 5 minutes
                use_dns_cache=True,
                keepalive_timeout=60,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(
                total=60,  # Increased total timeout
                connect=15,  # Increased connection timeout
                sock_read=30,  # Increased socket read timeout
                sock_connect=10  # Socket connection timeout
            )
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
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
        await self._ensure_session()
        
        # Test connectivity first
        if await self._test_connectivity():
            await self._authenticate()
            await self._discover_services()
        else:
            logger.error("API Gateway is not reachable, skipping initialization")
    
    async def _test_connectivity(self) -> bool:
        """Test basic connectivity to API Gateway"""
        try:
            # Try to reach the health endpoint without authentication
            health_url = f"{self.base_url}/health"
            
            # Use shorter timeout for connectivity test
            test_timeout = aiohttp.ClientTimeout(total=10, connect=5)
            
            async with self.session.get(health_url, timeout=test_timeout) as response:
                if response.status in [200, 401, 403]:  # Any response means it's reachable
                    logger.info("API Gateway is reachable")
                    return True
                else:
                    logger.warning(f"API Gateway health check returned: {response.status}")
                    return False
                    
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Cannot reach API Gateway at {self.base_url}: {e}")
            return False
        except asyncio.TimeoutError as e:
            logger.error(f"API Gateway connectivity test timed out: {e}")
            return False
        except Exception as e:
            logger.error(f"Connectivity test failed: {e}")
            return False
    
    async def _authenticate(self):
        """Authenticate with API Gateway with retry logic"""
        await self._ensure_session()
        
        settings = get_settings()
        max_retries = settings.api_gateway.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                auth_data = {
                    "email": settings.api_gateway.admin_email,
                    "password": settings.api_gateway.admin_password
                }
                
                auth_url = f"{self.base_url}/auth/login"
                
                # Use longer timeout for authentication
                auth_timeout = aiohttp.ClientTimeout(total=45, connect=15, sock_read=30)
                
                async with self.session.post(auth_url, json=auth_data, timeout=auth_timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.auth_token = data.get("access_token")
                        
                        # Extract token expiration
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
                        return
                    elif response.status == 404:
                        logger.debug(f"Authentication endpoint not found: {auth_url}")
                        return  # Skip authentication if endpoint doesn't exist
                    else:
                        logger.error(f"Authentication failed: {response.status}")
                        if attempt < max_retries:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Connection error to API Gateway (attempt {attempt + 1}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error("Failed to connect to API Gateway after all retries")
                    raise
            except asyncio.TimeoutError as e:
                logger.error(f"Authentication timeout (attempt {attempt + 1}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error("Authentication timed out after all retries")
                    raise
            except Exception as e:
                logger.error(f"Authentication error (attempt {attempt + 1}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
    
    async def _discover_services(self):
        """Discover available services from API Gateway"""
        try:
            # Try multiple discovery endpoints
            discovery_endpoints = [
                f"{self.base_url}/api/v1/services",
                f"{self.base_url}/services", 
                f"{self.base_url}/discovery/services"
            ]
            
            headers = await self._get_auth_headers()
            
            for discovery_url in discovery_endpoints:
                try:
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
                            
                            logger.info(f"Discovered {len(services.get('services', []))} services from {discovery_url}")
                            return  # Success, exit early
                        elif response.status == 404:
                            logger.debug(f"Service discovery endpoint not found: {discovery_url}")
                            continue  # Try next endpoint
                        else:
                            logger.debug(f"Service discovery returned {response.status} from {discovery_url}")
                            continue
                except Exception as endpoint_error:
                    logger.debug(f"Failed to query {discovery_url}: {endpoint_error}")
                    continue
            
            # If all endpoints failed, log as debug instead of warning
            logger.debug("No service discovery endpoints available, using static configuration")
                    
        except Exception as e:
            logger.debug(f"Service discovery failed: {e}")
    
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
    
    async def _make_authenticated_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an authenticated request to the API Gateway"""
        await self._ensure_session()
        
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        headers = await self._get_auth_headers()
        
        try:
            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    # Token expired, retry once
                    await self._authenticate()
                    headers = await self._get_auth_headers()
                    
                    async with self.session.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=data,
                        params=params
                    ) as retry_response:
                        if retry_response.status == 200:
                            return await retry_response.json()
                        else:
                            logger.error(f"Request failed after retry: {retry_response.status}")
                            return {"error": f"Request failed: {retry_response.status}"}
                else:
                    logger.error(f"Request failed: {response.status}")
                    return {"error": f"Request failed: {response.status}"}
                    
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {"error": str(e)}
    
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
            "sales_orders": "sales",
            "customers": "crm", 
            "leads": "crm",
            "products": "inventory",
            "inventory_items": "inventory",
            "stock_movements": "inventory",
            "employees": "hrm",
            "departments": "hrm",
            "accounts": "finance",
            "transactions": "finance",
            "budgets": "finance"
        }
        
        service_name = service_mapping.get(table, "sales")  # Default to sales
        
        endpoint = f"/api/v1/database/{query_type}"
        request_data = {
            "table": table,
            "data": data,
            "filters": filters,
            "user_role": user_role,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return await self.post_service_data(service_name, endpoint, request_data)
    
    async def get_erp_data_summary(self, data_types: List[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive ERP data summary from multiple services
        
        Args:
            data_types: List of data types to retrieve (sales, inventory, crm, finance, hrm)
            
        Returns:
            Comprehensive data summary
        """
        if not data_types:
            data_types = ["sales", "inventory", "crm", "finance"]
        
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "data_sources": {},
            "errors": []
        }
        
        # Fetch data from each requested service
        for data_type in data_types:
            try:
                if data_type == "sales":
                    summary["data_sources"]["sales"] = await self.get_sales_summary()
                elif data_type == "inventory":
                    summary["data_sources"]["inventory"] = await self.get_inventory_summary()
                elif data_type == "crm":
                    summary["data_sources"]["crm"] = await self.get_customer_summary()
                elif data_type == "finance":
                    summary["data_sources"]["finance"] = await self.get_finance_summary()
                elif data_type == "hrm":
                    summary["data_sources"]["hrm"] = await self.get_hrm_data("overview")
                    
            except Exception as e:
                logger.error(f"Failed to fetch {data_type} data: {e}")
                summary["errors"].append(f"{data_type}: {str(e)}")
        
        return summary

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
    
    async def get_sales_summary(self) -> Dict[str, Any]:
        """Get sales summary data"""
        try:
            return await self.get_sales_data("overview") or {
                "total_sales": 0,
                "total_revenue": 0,
                "recent_orders": 0,
                "error": "Sales service unavailable"
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def get_inventory_summary(self) -> Dict[str, Any]:
        """Get inventory summary data"""
        try:
            return await self.get_inventory_data("overview") or {
                "total_products": 0,
                "low_stock_items": 0,
                "total_stock_value": 0,
                "error": "Inventory service unavailable"
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def get_customer_summary(self) -> Dict[str, Any]:
        """Get customer summary data"""
        try:
            return await self.get_crm_data("overview") or {
                "total_customers": 0,
                "new_customers": 0,
                "active_leads": 0,
                "error": "CRM service unavailable"
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def get_finance_summary(self) -> Dict[str, Any]:
        """Get finance summary data"""
        try:
            return await self.get_finance_data("overview") or {
                "total_revenue": 0,
                "total_expenses": 0,
                "profit_margin": 0,
                "error": "Finance service unavailable"
            }
        except Exception as e:
            return {"error": str(e)}

    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()


# Global API Gateway client instance
api_gateway_client = APIGatewayClient()
