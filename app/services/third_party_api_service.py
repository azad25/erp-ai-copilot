"""
Third-Party API Access Management Service

Manages external API integrations, access controls, rate limiting,
and secure credential management for AI Copilot third-party integrations.
"""

from typing import Dict, List, Any, Optional, Tuple
import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import base64
# from cryptography.fernet import Fernet  # Temporarily disabled to fix Docker startup

from app.config.settings import get_settings
from app.services.user_preferences_service import user_preferences_service, PreferenceCategory
from app.database.connection import get_mongodb, get_redis

logger = logging.getLogger(__name__)


class APIProvider(Enum):
    """Supported API providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE_CLOUD = "google_cloud"
    AWS = "aws"
    AZURE = "azure"
    SLACK = "slack"
    MICROSOFT_TEAMS = "microsoft_teams"
    GITHUB = "github"
    GITLAB = "gitlab"
    JIRA = "jira"
    CONFLUENCE = "confluence"
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    STRIPE = "stripe"
    PAYPAL = "paypal"
    TWILIO = "twilio"
    SENDGRID = "sendgrid"


@dataclass
class APICredential:
    """API credential structure"""
    credential_id: str
    user_id: str
    organization_id: str
    provider: APIProvider
    api_key: str  # Encrypted
    additional_config: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    usage_count: int = 0


@dataclass
class APIUsage:
    """API usage tracking"""
    usage_id: str
    user_id: str
    organization_id: str
    provider: APIProvider
    endpoint: str
    method: str
    status_code: int
    response_time: float
    tokens_used: int = 0
    cost: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ThirdPartyAPIService:
    """
    Third-Party API Access Management Service
    
    Features:
    - Secure credential storage with encryption
    - Rate limiting per user and organization
    - API usage tracking and analytics
    - Cost monitoring and budget controls
    - Provider-specific integrations
    - Webhook management
    - API health monitoring
    """
    
    def __init__(self):
        # Temporarily disable encryption for Docker startup
        # self.encryption_key = self._get_encryption_key()
        # self.cipher_suite = Fernet(self.encryption_key)
        self.encryption_key = None
        self.cipher_suite = None
        self.rate_limits = self._initialize_rate_limits()
        self.provider_configs = self._initialize_provider_configs()
        
    def _get_encryption_key(self) -> bytes:
        """Get or generate encryption key for API credentials"""
        settings = get_settings()
        key = getattr(settings, 'API_ENCRYPTION_KEY', 'default-encryption-key-for-dev')
        if not key:
            # Generate a new key (in production, this should be stored securely)
            key = Fernet.generate_key()
            logger.warning("Generated new encryption key - store this securely!")
        
        if isinstance(key, str):
            key = key.encode()
        
        return base64.urlsafe_b64decode(key) if len(key) == 44 else key
    
    def _initialize_rate_limits(self) -> Dict[str, Dict[str, int]]:
        """Initialize default rate limits per provider"""
        return {
            APIProvider.OPENAI.value: {
                "requests_per_minute": 60,
                "tokens_per_minute": 90000,
                "requests_per_day": 10000
            },
            APIProvider.ANTHROPIC.value: {
                "requests_per_minute": 50,
                "tokens_per_minute": 40000,
                "requests_per_day": 8000
            },
            APIProvider.GOOGLE_CLOUD.value: {
                "requests_per_minute": 100,
                "requests_per_day": 50000
            },
            APIProvider.SLACK.value: {
                "requests_per_minute": 100,
                "requests_per_day": 20000
            },
            APIProvider.GITHUB.value: {
                "requests_per_minute": 60,
                "requests_per_day": 5000
            },
            "default": {
                "requests_per_minute": 30,
                "requests_per_day": 1000
            }
        }
    
    def _initialize_provider_configs(self) -> Dict[str, Dict[str, Any]]:
        """Initialize provider-specific configurations"""
        return {
            APIProvider.OPENAI.value: {
                "base_url": "https://api.openai.com/v1",
                "auth_header": "Authorization",
                "auth_prefix": "Bearer",
                "supported_endpoints": ["chat/completions", "embeddings", "models"],
                "cost_per_1k_tokens": {"gpt-4": 0.03, "gpt-3.5-turbo": 0.002}
            },
            APIProvider.ANTHROPIC.value: {
                "base_url": "https://api.anthropic.com/v1",
                "auth_header": "x-api-key",
                "auth_prefix": "",
                "supported_endpoints": ["messages", "models"],
                "cost_per_1k_tokens": {"claude-3": 0.015}
            },
            APIProvider.SLACK.value: {
                "base_url": "https://slack.com/api",
                "auth_header": "Authorization",
                "auth_prefix": "Bearer",
                "supported_endpoints": ["chat.postMessage", "users.list", "channels.list"]
            },
            APIProvider.GITHUB.value: {
                "base_url": "https://api.github.com",
                "auth_header": "Authorization",
                "auth_prefix": "token",
                "supported_endpoints": ["repos", "issues", "pulls", "search"]
            }
        }
    
    async def store_api_credential(
        self,
        user_id: str,
        organization_id: str,
        provider: APIProvider,
        api_key: str,
        additional_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store encrypted API credential"""
        try:
            # Encrypt API key
            encrypted_key = self.cipher_suite.encrypt(api_key.encode()).decode()
            
            credential_id = str(uuid4())
            credential = APICredential(
                credential_id=credential_id,
                user_id=user_id,
                organization_id=organization_id,
                provider=provider,
                api_key=encrypted_key,
                additional_config=additional_config or {}
            )
            
            # Store in MongoDB
            mongodb = await get_mongodb()
            
            credential_doc = {
                "credential_id": credential_id,
                "user_id": user_id,
                "organization_id": organization_id,
                "provider": provider.value,
                "api_key": encrypted_key,
                "additional_config": additional_config or {},
                "is_active": True,
                "created_at": credential.created_at,
                "usage_count": 0
            }
            
            await mongodb.api_credentials.insert_one(credential_doc)
            
            # Cache credential metadata (not the key)
            redis = await get_redis()
            cache_key = f"api_cred:{user_id}:{organization_id}:{provider.value}"
            await redis.hset(cache_key, mapping={
                "credential_id": credential_id,
                "provider": provider.value,
                "is_active": "true",
                "created_at": credential.created_at.isoformat()
            })
            await redis.expire(cache_key, 3600)
            
            logger.info(f"Stored API credential for {provider.value}")
            return credential_id
            
        except Exception as e:
            logger.error(f"Failed to store API credential: {e}")
            raise
    
    async def get_api_credentials(
        self,
        user_id: str,
        organization_id: str,
        provider: APIProvider
    ) -> Optional[Dict[str, Any]]:
        """Get API credentials with configuration"""
        try:
            mongodb = await get_mongodb()
            
            credential_doc = await mongodb.api_credentials.find_one({
                "user_id": user_id,
                "organization_id": organization_id,
                "provider": provider.value,
                "is_active": True
            })
            
            if credential_doc:
                encrypted_key = credential_doc["api_key"]
                decrypted_key = self.cipher_suite.decrypt(encrypted_key.encode()).decode()
                
                # Update last used timestamp
                await mongodb.api_credentials.update_one(
                    {"credential_id": credential_doc["credential_id"]},
                    {
                        "$set": {"last_used": datetime.utcnow()},
                        "$inc": {"usage_count": 1}
                    }
                )
                
                return {
                    "api_key": decrypted_key,
                    "provider": provider.value,
                    "additional_config": credential_doc.get("additional_config", {})
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get API credentials: {e}")
            return None

    async def get_api_credential(
        self,
        user_id: str,
        organization_id: str,
        provider: APIProvider
    ) -> Optional[str]:
        """Get decrypted API credential"""
        try:
            mongodb = await get_mongodb()
            
            credential_doc = await mongodb.api_credentials.find_one({
                "user_id": user_id,
                "organization_id": organization_id,
                "provider": provider.value,
                "is_active": True
            })
            
            if credential_doc:
                encrypted_key = credential_doc["api_key"]
                decrypted_key = self.cipher_suite.decrypt(encrypted_key.encode()).decode()
                
                # Update last used timestamp
                await mongodb.api_credentials.update_one(
                    {"credential_id": credential_doc["credential_id"]},
                    {
                        "$set": {"last_used": datetime.utcnow()},
                        "$inc": {"usage_count": 1}
                    }
                )
                
                return decrypted_key
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get API credential: {e}")
            return None
    
    async def make_api_request(
        self,
        user_id: str,
        organization_id: str,
        provider: APIProvider,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Make authenticated API request with rate limiting"""
        # Check rate limits
        if not await self._check_rate_limit(user_id, organization_id, provider):
            return False, {"error": "Rate limit exceeded"}
        
        # Get API credential
        api_key = await self.get_api_credential(user_id, organization_id, provider)
        if not api_key:
            return False, {"error": "API credential not found"}
        
        # Get provider configuration
        provider_config = self.provider_configs.get(provider.value, {})
        base_url = provider_config.get("base_url", "")
        
        if not base_url:
            return False, {"error": "Provider configuration not found"}
        
        # Prepare request
        url = f"{base_url}/{endpoint.lstrip('/')}"
        request_headers = headers or {}
        
        # Add authentication
        auth_header = provider_config.get("auth_header", "Authorization")
        auth_prefix = provider_config.get("auth_prefix", "Bearer")
        request_headers[auth_header] = f"{auth_prefix} {api_key}".strip()
        
        # Make request
        start_time = datetime.utcnow()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    json=data,
                    headers=request_headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_data = await response.json()
                    status_code = response.status
                    
            end_time = datetime.utcnow()
            response_time = (end_time - start_time).total_seconds()
            
            # Track usage
            await self._track_api_usage(
                user_id=user_id,
                organization_id=organization_id,
                provider=provider,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time=response_time,
                tokens_used=self._estimate_tokens(data, response_data),
                cost=self._calculate_cost(provider, data, response_data)
            )
            
            # Update rate limit counters
            await self._update_rate_limit_counters(user_id, organization_id, provider)
            
            success = 200 <= status_code < 300
            return success, response_data
            
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return False, {"error": str(e)}
    
    async def _check_rate_limit(
        self,
        user_id: str,
        organization_id: str,
        provider: APIProvider
    ) -> bool:
        """Check if user is within rate limits"""
        try:
            redis = await get_redis()
            
            # Get user's rate limits (may be customized)
            user_limits = await user_preferences_service.get_user_preference(
                user_id,
                organization_id,
                PreferenceCategory.INTEGRATIONS,
                "api_rate_limits"
            )
            
            provider_limits = user_limits.get(provider.value, self.rate_limits.get(provider.value, self.rate_limits["default"]))
            
            # Check minute limit
            minute_key = f"rate_limit:{user_id}:{provider.value}:minute:{datetime.utcnow().strftime('%Y%m%d%H%M')}"
            minute_count = await redis.get(minute_key)
            
            if minute_count and int(minute_count) >= provider_limits.get("requests_per_minute", 30):
                return False
            
            # Check daily limit
            day_key = f"rate_limit:{user_id}:{provider.value}:day:{datetime.utcnow().strftime('%Y%m%d')}"
            day_count = await redis.get(day_key)
            
            if day_count and int(day_count) >= provider_limits.get("requests_per_day", 1000):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return False
    
    async def _update_rate_limit_counters(
        self,
        user_id: str,
        organization_id: str,
        provider: APIProvider
    ):
        """Update rate limit counters"""
        try:
            redis = await get_redis()
            
            # Update minute counter
            minute_key = f"rate_limit:{user_id}:{provider.value}:minute:{datetime.utcnow().strftime('%Y%m%d%H%M')}"
            await redis.incr(minute_key)
            await redis.expire(minute_key, 60)
            
            # Update daily counter
            day_key = f"rate_limit:{user_id}:{provider.value}:day:{datetime.utcnow().strftime('%Y%m%d')}"
            await redis.incr(day_key)
            await redis.expire(day_key, 86400)
            
        except Exception as e:
            logger.error(f"Failed to update rate limit counters: {e}")
    
    async def _track_api_usage(
        self,
        user_id: str,
        organization_id: str,
        provider: APIProvider,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float,
        tokens_used: int = 0,
        cost: float = 0.0
    ):
        """Track API usage for analytics and billing"""
        try:
            usage = APIUsage(
                usage_id=str(uuid4()),
                user_id=user_id,
                organization_id=organization_id,
                provider=provider,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time=response_time,
                tokens_used=tokens_used,
                cost=cost
            )
            
            # Store in MongoDB
            mongodb = await get_mongodb()
            
            usage_doc = {
                "usage_id": usage.usage_id,
                "user_id": user_id,
                "organization_id": organization_id,
                "provider": provider.value,
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "response_time": response_time,
                "tokens_used": tokens_used,
                "cost": cost,
                "timestamp": usage.timestamp
            }
            
            await mongodb.api_usage.insert_one(usage_doc)
            
            # Update usage statistics in Redis
            redis = await get_redis()
            stats_key = f"api_stats:{user_id}:{organization_id}:{provider.value}"
            
            await redis.hincrby(stats_key, "total_requests", 1)
            await redis.hincrbyfloat(stats_key, "total_cost", cost)
            await redis.hincrby(stats_key, "total_tokens", tokens_used)
            await redis.expire(stats_key, 86400)
            
        except Exception as e:
            logger.error(f"Failed to track API usage: {e}")
    
    def _estimate_tokens(self, request_data: Optional[Dict[str, Any]], response_data: Dict[str, Any]) -> int:
        """Estimate token usage for the API call"""
        tokens = 0
        
        # Estimate based on text content
        if request_data:
            request_text = json.dumps(request_data)
            tokens += len(request_text.split()) * 1.3  # Rough token estimation
        
        if response_data:
            response_text = json.dumps(response_data)
            tokens += len(response_text.split()) * 1.3
        
        # Check for specific token usage in response
        if "usage" in response_data:
            usage = response_data["usage"]
            if "total_tokens" in usage:
                tokens = usage["total_tokens"]
        
        return int(tokens)
    
    def _calculate_cost(
        self,
        provider: APIProvider,
        request_data: Optional[Dict[str, Any]],
        response_data: Dict[str, Any]
    ) -> float:
        """Calculate cost for the API call"""
        provider_config = self.provider_configs.get(provider.value, {})
        cost_per_1k = provider_config.get("cost_per_1k_tokens", {})
        
        if not cost_per_1k:
            return 0.0
        
        # Get model from request
        model = "default"
        if request_data and "model" in request_data:
            model = request_data["model"]
        
        # Get token usage
        tokens = self._estimate_tokens(request_data, response_data)
        
        # Calculate cost
        model_cost = cost_per_1k.get(model, list(cost_per_1k.values())[0] if cost_per_1k else 0.0)
        return (tokens / 1000) * model_cost
    
    async def get_user_api_usage(
        self,
        user_id: str,
        organization_id: str,
        provider: Optional[APIProvider] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get user API usage statistics"""
        try:
            mongodb = await get_mongodb()
            
            start_date = datetime.utcnow() - timedelta(days=days)
            
            query = {
                "user_id": user_id,
                "organization_id": organization_id,
                "timestamp": {"$gte": start_date}
            }
            
            if provider:
                query["provider"] = provider.value
            
            # Aggregate usage statistics
            pipeline = [
                {"$match": query},
                {
                    "$group": {
                        "_id": "$provider",
                        "total_requests": {"$sum": 1},
                        "total_tokens": {"$sum": "$tokens_used"},
                        "total_cost": {"$sum": "$cost"},
                        "avg_response_time": {"$avg": "$response_time"},
                        "success_rate": {
                            "$avg": {
                                "$cond": [
                                    {"$and": [{"$gte": ["$status_code", 200]}, {"$lt": ["$status_code", 300]}]},
                                    1,
                                    0
                                ]
                            }
                        }
                    }
                }
            ]
            
            cursor = mongodb.api_usage.aggregate(pipeline)
            usage_stats = {}
            
            async for doc in cursor:
                provider_name = doc["_id"]
                usage_stats[provider_name] = {
                    "total_requests": doc["total_requests"],
                    "total_tokens": doc["total_tokens"],
                    "total_cost": round(doc["total_cost"], 4),
                    "avg_response_time": round(doc["avg_response_time"], 3),
                    "success_rate": round(doc["success_rate"], 3)
                }
            
            return {
                "usage_stats": usage_stats,
                "period_days": days,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get API usage: {e}")
            return {}
    
    async def list_user_credentials(
        self,
        user_id: str,
        organization_id: str
    ) -> List[Dict[str, Any]]:
        """List user's API credentials (without keys)"""
        try:
            mongodb = await get_mongodb()
            
            cursor = mongodb.api_credentials.find({
                "user_id": user_id,
                "organization_id": organization_id,
                "is_active": True
            })
            
            credentials = []
            async for doc in cursor:
                credentials.append({
                    "credential_id": doc["credential_id"],
                    "provider": doc["provider"],
                    "created_at": doc["created_at"].isoformat(),
                    "last_used": doc.get("last_used").isoformat() if doc.get("last_used") else None,
                    "usage_count": doc.get("usage_count", 0)
                })
            
            return credentials
            
        except Exception as e:
            logger.error(f"Failed to list credentials: {e}")
            return []
    
    async def delete_api_credential(
        self,
        user_id: str,
        organization_id: str,
        credential_id: str
    ) -> bool:
        """Delete an API credential"""
        try:
            mongodb = await get_mongodb()
            redis = await get_redis()
            
            # Soft delete - mark as inactive
            result = await mongodb.api_credentials.update_one(
                {
                    "credential_id": credential_id,
                    "user_id": user_id,
                    "organization_id": organization_id
                },
                {"$set": {"is_active": False, "deleted_at": datetime.utcnow()}}
            )
            
            # Clear cache
            cache_pattern = f"api_cred:{user_id}:{organization_id}:*"
            keys = await redis.keys(cache_pattern)
            if keys:
                await redis.delete(*keys)
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete credential: {e}")
            return False
    
    async def test_api_connection(
        self,
        user_id: str,
        organization_id: str,
        provider: APIProvider
    ) -> Tuple[bool, str]:
        """Test API connection and credential validity"""
        try:
            # Get test endpoint for provider
            test_endpoints = {
                APIProvider.OPENAI: ("models", "GET"),
                APIProvider.ANTHROPIC: ("models", "GET"),
                APIProvider.SLACK: ("auth.test", "POST"),
                APIProvider.GITHUB: ("user", "GET")
            }
            
            endpoint, method = test_endpoints.get(provider, ("", "GET"))
            if not endpoint:
                return False, "No test endpoint available for this provider"
            
            success, response = await self.make_api_request(
                user_id=user_id,
                organization_id=organization_id,
                provider=provider,
                endpoint=endpoint,
                method=method
            )
            
            if success:
                return True, "Connection successful"
            else:
                error_msg = response.get("error", "Unknown error")
                return False, f"Connection failed: {error_msg}"
            
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False, str(e)
    
    async def get_supported_providers(self) -> List[Dict[str, Any]]:
        """Get list of supported API providers"""
        providers = []
        
        for provider in APIProvider:
            config = self.provider_configs.get(provider.value, {})
            providers.append({
                "name": provider.value,
                "display_name": provider.value.replace("_", " ").title(),
                "base_url": config.get("base_url", ""),
                "supported_endpoints": config.get("supported_endpoints", []),
                "requires_api_key": True
            })
        
        return providers
    
    async def make_api_request(
        self,
        user_id: str,
        organization_id: str,
        provider: APIProvider,
        endpoint: str,
        method: str,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Make API request to third-party provider"""
        try:
            credentials = await self.get_api_credentials(user_id, organization_id, provider)
            if not credentials:
                logger.warning(f"No {provider.value} credentials found for API request")
                return False, {"error": "No credentials found"}
            
            # Check rate limits
            if not await self._check_rate_limit(user_id, organization_id, provider, endpoint):
                logger.warning(f"Rate limit exceeded for {provider.value} {endpoint}")
                return False, {"error": "Rate limit exceeded"}
            
            headers = {
                "Authorization": f"Bearer {credentials.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    f"{credentials.base_url}{endpoint}",
                    headers=headers,
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Track usage
                        await self._track_api_usage(
                            user_id, organization_id, provider, endpoint,
                            tokens_used=result.get("usage", {}).get("total_tokens", 0)
                        )
                        
                        return True, result
                    else:
                        error_text = await response.text()
                        logger.error(f"{provider.value} API error: {response.status} - {error_text}")
                        return False, {"error": error_text}
                        
        except Exception as e:
            logger.error(f"Failed to make API request to {provider.value}: {e}")
            return {"error": str(e), "status": "failed"}
    
    async def generate_embedding(
        self,
        text: str,
        user_id: str = "system",
        organization_id: str = "system",
        model: str = "text-embedding-ada-002"
    ) -> Optional[List[float]]:
        """
        Generate text embedding using OpenAI
        
        Args:
            text: Text to embed
            user_id: User identifier
            organization_id: Organization identifier
            model: Embedding model to use
            
        Returns:
            Embedding vector or None if failed
        """
        try:
            credentials = await self.get_api_credentials(user_id, organization_id, APIProvider.OPENAI)
            if not credentials:
                logger.warning("No OpenAI credentials found for embedding generation")
                return None
            
            # Check rate limits
            if not await self._check_rate_limit(user_id, organization_id, APIProvider.OPENAI, "embeddings"):
                logger.warning("Rate limit exceeded for OpenAI embeddings")
                return None
            
            headers = {
                "Authorization": f"Bearer {credentials.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "input": text,
                "model": model
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/embeddings",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        embedding = result["data"][0]["embedding"]
                        
                        # Track usage
                        await self._track_api_usage(
                            user_id, organization_id, APIProvider.OPENAI, "embeddings",
                            tokens_used=result.get("usage", {}).get("total_tokens", 0)
                        )
                        
                        return embedding
                    else:
                        error_text = await response.text()
                        logger.error(f"OpenAI embedding API error: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None


# Global third-party API service instance
third_party_api_service = ThirdPartyAPIService()
