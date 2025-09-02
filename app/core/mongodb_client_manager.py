"""
MongoDB client manager to prevent synchronous client creation and background tasks.
"""
import asyncio
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
import structlog

logger = structlog.get_logger(__name__)


class MongoDBClientManager:
    """
    Manages MongoDB client lifecycle to prevent background sync operations
    that cause timeout errors.
    """
    
    def __init__(self):
        self._client: Optional[AsyncIOMotorClient] = None
        self._lock = asyncio.Lock()
    
    async def get_client(self, uri: str, **kwargs) -> AsyncIOMotorClient:
        """Get or create MongoDB client with proper configuration."""
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    # Configure client to minimize background operations
                    client_kwargs = {
                        'serverSelectionTimeoutMS': 30000,
                        'connectTimeoutMS': 30000,
                        'socketTimeoutMS': 30000,
                        'heartbeatFrequencyMS': 60000,  # Reduce heartbeat frequency
                        'retryWrites': True,
                        'retryReads': True,
                        'appname': 'ai_copilot_async',
                        # Disable background monitoring
                        'directConnection': False,
                        **kwargs
                    }
                    
                    self._client = AsyncIOMotorClient(uri, **client_kwargs)
                    
                    # Test connection
                    try:
                        await asyncio.wait_for(
                            self._client.admin.command('ping'),
                            timeout=15.0
                        )
                        logger.info("MongoDB client created successfully")
                    except Exception as e:
                        logger.error("Failed to test MongoDB connection", error=str(e))
                        self._client.close()
                        self._client = None
                        raise
        
        return self._client
    
    async def close(self):
        """Close the MongoDB client."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("MongoDB client closed")
    
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._client is not None


# Global client manager instance
mongodb_client_manager = MongoDBClientManager()
