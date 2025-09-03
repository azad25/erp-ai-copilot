"""
Connection Health Check Service

Monitors and validates connections to external services including API Gateway,
databases, and other ERP services. Provides health status and connection diagnostics.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import aiohttp
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient
import socket

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class ConnectionHealthService:
    """
    Service to monitor and validate connections to external dependencies
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.health_status: Dict[str, Dict[str, Any]] = {}
        self.last_check: Optional[datetime] = None
        
    async def check_all_connections(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all external connections"""
        checks = [
            self._check_api_gateway(),
            self._check_mongodb(),
            self._check_redis(),
            self._check_qdrant(),
            self._check_auth_service(),
            self._check_postgres()
        ]
        
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        # Process results
        services = ["api-gateway", "mongodb", "redis", "qdrant", "auth-service", "postgres"]
        for i, result in enumerate(results):
            service_name = services[i]
            if isinstance(result, Exception):
                self.health_status[service_name] = {
                    "status": "error",
                    "error": str(result),
                    "last_check": datetime.utcnow().isoformat()
                }
            else:
                self.health_status[service_name] = result
        
        self.last_check = datetime.utcnow()
        return self.health_status
    
    async def _check_api_gateway(self) -> Dict[str, Any]:
        """Check API Gateway connectivity"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = f"{self.settings.api_gateway.url}/health"
                
                async with session.get(url) as response:
                    return {
                        "status": "healthy" if response.status == 200 else "degraded",
                        "response_code": response.status,
                        "response_time_ms": 0,  # Could add timing
                        "last_check": datetime.utcnow().isoformat(),
                        "endpoint": url
                    }
                    
        except aiohttp.ClientConnectorError as e:
            return {
                "status": "unreachable",
                "error": f"Connection failed: {str(e)}",
                "last_check": datetime.utcnow().isoformat(),
                "endpoint": self.settings.api_gateway.url,
                "suggestion": "Check if API Gateway container is running and network is accessible"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }
    
    async def _check_mongodb(self) -> Dict[str, Any]:
        """Check MongoDB connectivity"""
        try:
            client = AsyncIOMotorClient(
                self.settings.mongodb.uri,
                serverSelectionTimeoutMS=5000
            )
            
            # Test connection
            await client.admin.command('ping')
            
            return {
                "status": "healthy",
                "last_check": datetime.utcnow().isoformat(),
                "endpoint": self.settings.mongodb.uri.split('@')[-1] if '@' in self.settings.mongodb.uri else self.settings.mongodb.uri
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat(),
                "suggestion": "Check MongoDB container status and network connectivity"
            }
    
    async def _check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity"""
        try:
            redis_url = self.settings.redis.url
            redis_client = redis.from_url(redis_url, socket_timeout=5)
            
            # Test connection
            await redis_client.ping()
            await redis_client.close()
            
            return {
                "status": "healthy",
                "last_check": datetime.utcnow().isoformat(),
                "endpoint": f"{self.settings.redis.host}:{self.settings.redis.port}"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat(),
                "suggestion": "Check Redis container status and credentials"
            }
    
    async def _check_qdrant(self) -> Dict[str, Any]:
        """Check Qdrant connectivity"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = f"{self.settings.qdrant.http_url}/health"
                
                async with session.get(url) as response:
                    return {
                        "status": "healthy" if response.status == 200 else "degraded",
                        "response_code": response.status,
                        "last_check": datetime.utcnow().isoformat(),
                        "endpoint": url
                    }
                    
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat(),
                "suggestion": "Check Qdrant container status and port accessibility"
            }
    
    async def _check_auth_service(self) -> Dict[str, Any]:
        """Check Auth Service connectivity"""
        try:
            # Test HTTP endpoint
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = f"http://{self.settings.auth_service.host}:{self.settings.auth_service.port}/health"
                
                async with session.get(url) as response:
                    return {
                        "status": "healthy" if response.status == 200 else "degraded",
                        "response_code": response.status,
                        "last_check": datetime.utcnow().isoformat(),
                        "endpoint": url
                    }
                    
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat(),
                "suggestion": "Check Auth Service container status and HTTP port"
            }
    
    async def _check_postgres(self) -> Dict[str, Any]:
        """Check PostgreSQL connectivity"""
        try:
            # Simple socket connection test
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            # Try to connect to postgres host
            result = sock.connect_ex((self.settings.database.host, self.settings.database.port))
            sock.close()
            
            if result == 0:
                return {
                    "status": "healthy",
                    "last_check": datetime.utcnow().isoformat(),
                    "endpoint": f"{self.settings.database.host}:{self.settings.database.port}"
                }
            else:
                return {
                    "status": "unreachable",
                    "error": f"Connection refused to {self.settings.database.host}:{self.settings.database.port}",
                    "last_check": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat(),
                "suggestion": "Check PostgreSQL container status and network connectivity"
            }
    
    async def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary"""
        if not self.health_status or not self.last_check:
            await self.check_all_connections()
        
        healthy_count = sum(1 for status in self.health_status.values() if status.get("status") == "healthy")
        total_count = len(self.health_status)
        
        overall_status = "healthy" if healthy_count == total_count else "degraded" if healthy_count > 0 else "critical"
        
        return {
            "overall_status": overall_status,
            "healthy_services": healthy_count,
            "total_services": total_count,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "services": self.health_status
        }
    
    async def diagnose_connection_issues(self) -> List[str]:
        """Diagnose common connection issues and provide suggestions"""
        suggestions = []
        
        await self.check_all_connections()
        
        for service_name, status in self.health_status.items():
            if status.get("status") != "healthy":
                error = status.get("error", "")
                
                if "Name or service not known" in error or "nodename nor servname provided" in error:
                    suggestions.append(f"🔍 {service_name}: DNS resolution issue - check Docker network configuration")
                elif "Connection refused" in error:
                    suggestions.append(f"🚫 {service_name}: Service not running or port not accessible")
                elif "timeout" in error.lower():
                    suggestions.append(f"⏱️ {service_name}: Connection timeout - service may be slow to start")
                elif "unreachable" in status.get("status", ""):
                    suggestions.append(f"🌐 {service_name}: Network connectivity issue")
                else:
                    suggestions.append(f"❌ {service_name}: {error}")
        
        # Add general suggestions
        if any("DNS" in s for s in suggestions):
            suggestions.append("💡 General: Ensure all services are on the same Docker network (erp-network)")
        
        if any("Connection refused" in s for s in suggestions):
            suggestions.append("💡 General: Check service startup order and health checks")
        
        return suggestions


# Global instance
connection_health_service = ConnectionHealthService()
