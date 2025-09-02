"""
MongoDB wrapper with circuit breaker protection to prevent synchronous client creation.
"""
import asyncio
from typing import Any, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import structlog

from app.core.circuit_breaker import circuit_manager, MONGODB_CIRCUIT_CONFIG
from app.core.resilience import with_circuit_breaker, with_retry, DATABASE_RETRY_CONFIG
from app.core.exceptions import DatabaseError

logger = structlog.get_logger(__name__)


class MongoDBWrapper:
    """
    Wrapper for MongoDB operations that ensures all operations go through 
    the circuit breaker protected async client.
    """
    
    def __init__(self, client: AsyncIOMotorClient, database_name: str):
        self.client = client
        self.database_name = database_name
        self._database = None
    
    @property
    def database(self) -> AsyncIOMotorDatabase:
        """Get the database instance."""
        if self._database is None:
            self._database = self.client[self.database_name]
        return self._database
    
    @with_circuit_breaker("mongodb_operation", MONGODB_CIRCUIT_CONFIG)
    async def ping(self) -> bool:
        """Ping MongoDB to check connection."""
        try:
            await asyncio.wait_for(
                self.client.admin.command('ping'),
                timeout=10.0
            )
            return True
        except Exception as e:
            logger.error("MongoDB ping failed", error=str(e))
            raise DatabaseError("mongodb_ping", str(e))
    
    @with_circuit_breaker("mongodb_operation", MONGODB_CIRCUIT_CONFIG)
    async def find_one(self, collection_name: str, filter_dict: Dict[str, Any], **kwargs) -> Optional[Dict[str, Any]]:
        """Find one document with circuit breaker protection."""
        try:
            collection = self.database[collection_name]
            result = await asyncio.wait_for(
                collection.find_one(filter_dict, **kwargs),
                timeout=15.0
            )
            return result
        except Exception as e:
            logger.error("MongoDB find_one failed", collection=collection_name, error=str(e))
            raise DatabaseError("mongodb_find_one", str(e))
    
    @with_circuit_breaker("mongodb_operation", MONGODB_CIRCUIT_CONFIG)
    async def find(self, collection_name: str, filter_dict: Dict[str, Any], **kwargs) -> list:
        """Find documents with circuit breaker protection."""
        try:
            collection = self.database[collection_name]
            cursor = collection.find(filter_dict, **kwargs)
            result = await asyncio.wait_for(
                cursor.to_list(length=None),
                timeout=30.0
            )
            return result
        except Exception as e:
            logger.error("MongoDB find failed", collection=collection_name, error=str(e))
            raise DatabaseError("mongodb_find", str(e))
    
    @with_circuit_breaker("mongodb_operation", MONGODB_CIRCUIT_CONFIG)
    async def insert_one(self, collection_name: str, document: Dict[str, Any]) -> Any:
        """Insert one document with circuit breaker protection."""
        try:
            collection = self.database[collection_name]
            result = await asyncio.wait_for(
                collection.insert_one(document),
                timeout=15.0
            )
            return result
        except Exception as e:
            logger.error("MongoDB insert_one failed", collection=collection_name, error=str(e))
            raise DatabaseError("mongodb_insert_one", str(e))
    
    @with_circuit_breaker("mongodb_operation", MONGODB_CIRCUIT_CONFIG)
    async def insert_many(self, collection_name: str, documents: list) -> Any:
        """Insert many documents with circuit breaker protection."""
        try:
            collection = self.database[collection_name]
            result = await asyncio.wait_for(
                collection.insert_many(documents),
                timeout=30.0
            )
            return result
        except Exception as e:
            logger.error("MongoDB insert_many failed", collection=collection_name, error=str(e))
            raise DatabaseError("mongodb_insert_many", str(e))
    
    @with_circuit_breaker("mongodb_operation", MONGODB_CIRCUIT_CONFIG)
    async def update_one(self, collection_name: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any], **kwargs) -> Any:
        """Update one document with circuit breaker protection."""
        try:
            collection = self.database[collection_name]
            result = await asyncio.wait_for(
                collection.update_one(filter_dict, update_dict, **kwargs),
                timeout=15.0
            )
            return result
        except Exception as e:
            logger.error("MongoDB update_one failed", collection=collection_name, error=str(e))
            raise DatabaseError("mongodb_update_one", str(e))
    
    @with_circuit_breaker("mongodb_operation", MONGODB_CIRCUIT_CONFIG)
    async def update_many(self, collection_name: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any], **kwargs) -> Any:
        """Update many documents with circuit breaker protection."""
        try:
            collection = self.database[collection_name]
            result = await asyncio.wait_for(
                collection.update_many(filter_dict, update_dict, **kwargs),
                timeout=30.0
            )
            return result
        except Exception as e:
            logger.error("MongoDB update_many failed", collection=collection_name, error=str(e))
            raise DatabaseError("mongodb_update_many", str(e))
    
    @with_circuit_breaker("mongodb_operation", MONGODB_CIRCUIT_CONFIG)
    async def delete_one(self, collection_name: str, filter_dict: Dict[str, Any]) -> Any:
        """Delete one document with circuit breaker protection."""
        try:
            collection = self.database[collection_name]
            result = await asyncio.wait_for(
                collection.delete_one(filter_dict),
                timeout=15.0
            )
            return result
        except Exception as e:
            logger.error("MongoDB delete_one failed", collection=collection_name, error=str(e))
            raise DatabaseError("mongodb_delete_one", str(e))
    
    @with_circuit_breaker("mongodb_operation", MONGODB_CIRCUIT_CONFIG)
    async def delete_many(self, collection_name: str, filter_dict: Dict[str, Any]) -> Any:
        """Delete many documents with circuit breaker protection."""
        try:
            collection = self.database[collection_name]
            result = await asyncio.wait_for(
                collection.delete_many(filter_dict),
                timeout=30.0
            )
            return result
        except Exception as e:
            logger.error("MongoDB delete_many failed", collection=collection_name, error=str(e))
            raise DatabaseError("mongodb_delete_many", str(e))
    
    @with_circuit_breaker("mongodb_operation", MONGODB_CIRCUIT_CONFIG)
    async def count_documents(self, collection_name: str, filter_dict: Dict[str, Any]) -> int:
        """Count documents with circuit breaker protection."""
        try:
            collection = self.database[collection_name]
            result = await asyncio.wait_for(
                collection.count_documents(filter_dict),
                timeout=15.0
            )
            return result
        except Exception as e:
            logger.error("MongoDB count_documents failed", collection=collection_name, error=str(e))
            raise DatabaseError("mongodb_count_documents", str(e))
    
    @with_circuit_breaker("mongodb_operation", MONGODB_CIRCUIT_CONFIG)
    async def aggregate(self, collection_name: str, pipeline: list) -> list:
        """Aggregate documents with circuit breaker protection."""
        try:
            collection = self.database[collection_name]
            cursor = collection.aggregate(pipeline)
            result = await asyncio.wait_for(
                cursor.to_list(length=None),
                timeout=30.0
            )
            return result
        except Exception as e:
            logger.error("MongoDB aggregate failed", collection=collection_name, error=str(e))
            raise DatabaseError("mongodb_aggregate", str(e))
    
    @with_circuit_breaker("mongodb_operation", MONGODB_CIRCUIT_CONFIG)
    async def create_index(self, collection_name: str, keys, **kwargs) -> str:
        """Create index with circuit breaker protection."""
        try:
            collection = self.database[collection_name]
            result = await asyncio.wait_for(
                collection.create_index(keys, **kwargs),
                timeout=30.0
            )
            return result
        except Exception as e:
            logger.error("MongoDB create_index failed", collection=collection_name, error=str(e))
            raise DatabaseError("mongodb_create_index", str(e))
    
    async def close(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB wrapper connection closed")
