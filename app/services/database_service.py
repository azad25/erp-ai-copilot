"""
Database Service

Direct database access for AI Copilot (admin only).
Supports PostgreSQL and MongoDB operations.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import asyncpg
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from contextlib import asynccontextmanager

from app.config.settings import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for direct database access"""
    
    def __init__(self):
        self.postgres_pool: Optional[asyncpg.Pool] = None
        self.mongodb_client: Optional[AsyncIOMotorClient] = None
        self.mongodb: Optional[AsyncIOMotorDatabase] = None
        
    async def initialize(self):
        """Initialize database connections"""
        try:
            # Initialize PostgreSQL connection pool
            postgres_settings = getattr(settings, 'postgres', None)
            if postgres_settings:
                self.postgres_pool = await asyncpg.create_pool(
                    host=postgres_settings.host,
                    port=postgres_settings.port,
                    user=postgres_settings.user,
                    password=postgres_settings.password,
                    database=postgres_settings.db,
                    min_size=2,
                    max_size=10,
                    command_timeout=60
                )
                logger.info("PostgreSQL connection pool initialized")
            
            # Initialize MongoDB connection
            mongodb_settings = settings.mongodb
            self.mongodb_client = AsyncIOMotorClient(mongodb_settings.uri)
            self.mongodb = self.mongodb_client[mongodb_settings.database]
            logger.info("MongoDB connection initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize database connections: {e}")
            raise
    
    async def close(self):
        """Close database connections"""
        if self.postgres_pool:
            await self.postgres_pool.close()
        if self.mongodb_client:
            self.mongodb_client.close()
    
    # PostgreSQL Operations
    
    async def execute_postgres_query(
        self,
        query: str,
        params: Optional[List[Any]] = None,
        fetch_mode: str = "all"
    ) -> Tuple[bool, Any, str]:
        """
        Execute PostgreSQL query
        
        Args:
            query: SQL query
            params: Query parameters
            fetch_mode: "all", "one", "none"
            
        Returns:
            (success, result, message)
        """
        if not self.postgres_pool:
            await self.initialize()
        
        try:
            async with self.postgres_pool.acquire() as conn:
                # Check if it's a SELECT query
                is_select = query.strip().upper().startswith('SELECT')
                
                if is_select:
                    if fetch_mode == "all":
                        rows = await conn.fetch(query, *(params or []))
                        result = [dict(row) for row in rows]
                        return True, result, f"Retrieved {len(result)} rows"
                    elif fetch_mode == "one":
                        row = await conn.fetchrow(query, *(params or []))
                        result = dict(row) if row else None
                        return True, result, "Retrieved 1 row" if result else "No rows found"
                    else:
                        rows = await conn.fetch(query, *(params or []))
                        return True, len(rows), f"Query returned {len(rows)} rows"
                else:
                    # INSERT, UPDATE, DELETE, etc.
                    result = await conn.execute(query, *(params or []))
                    return True, result, f"Query executed: {result}"
                    
        except Exception as e:
            logger.error(f"PostgreSQL query error: {e}")
            return False, None, f"Error: {str(e)}"
    
    async def get_postgres_tables(self, schema: str = "public") -> List[str]:
        """Get list of tables in PostgreSQL"""
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = $1 
            ORDER BY table_name
        """
        success, result, _ = await self.execute_postgres_query(query, [schema])
        if success:
            return [row['table_name'] for row in result]
        return []
    
    async def get_postgres_table_schema(self, table_name: str, schema: str = "public") -> List[Dict]:
        """Get table schema information"""
        query = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
        """
        success, result, _ = await self.execute_postgres_query(query, [schema, table_name])
        return result if success else []
    
    async def count_postgres_rows(self, table_name: str, where_clause: str = "") -> int:
        """Count rows in a table"""
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        success, result, _ = await self.execute_postgres_query(query, fetch_mode="one")
        if success and result:
            return result['count']
        return 0
    
    # MongoDB Operations
    
    async def execute_mongodb_query(
        self,
        collection_name: str,
        operation: str,
        query: Optional[Dict] = None,
        data: Optional[Dict] = None,
        limit: int = 100,
        sort: Optional[List[Tuple[str, int]]] = None
    ) -> Tuple[bool, Any, str]:
        """
        Execute MongoDB query
        
        Args:
            collection_name: Collection name
            operation: "find", "find_one", "insert_one", "insert_many", "update_one", "update_many", "delete_one", "delete_many", "count"
            query: Query filter
            data: Data for insert/update operations
            limit: Limit for find operations
            sort: Sort specification
            
        Returns:
            (success, result, message)
        """
        if not self.mongodb:
            await self.initialize()
        
        try:
            collection = self.mongodb[collection_name]
            query = query or {}
            
            if operation == "find":
                cursor = collection.find(query).limit(limit)
                if sort:
                    cursor = cursor.sort(sort)
                result = await cursor.to_list(length=limit)
                # Convert ObjectId to string
                for doc in result:
                    if '_id' in doc:
                        doc['_id'] = str(doc['_id'])
                return True, result, f"Retrieved {len(result)} documents"
                
            elif operation == "find_one":
                result = await collection.find_one(query)
                if result and '_id' in result:
                    result['_id'] = str(result['_id'])
                return True, result, "Retrieved 1 document" if result else "No document found"
                
            elif operation == "insert_one":
                result = await collection.insert_one(data)
                return True, str(result.inserted_id), f"Inserted document with ID: {result.inserted_id}"
                
            elif operation == "insert_many":
                result = await collection.insert_many(data)
                return True, [str(id) for id in result.inserted_ids], f"Inserted {len(result.inserted_ids)} documents"
                
            elif operation == "update_one":
                result = await collection.update_one(query, {"$set": data})
                return True, result.modified_count, f"Modified {result.modified_count} document(s)"
                
            elif operation == "update_many":
                result = await collection.update_many(query, {"$set": data})
                return True, result.modified_count, f"Modified {result.modified_count} document(s)"
                
            elif operation == "delete_one":
                result = await collection.delete_one(query)
                return True, result.deleted_count, f"Deleted {result.deleted_count} document(s)"
                
            elif operation == "delete_many":
                result = await collection.delete_many(query)
                return True, result.deleted_count, f"Deleted {result.deleted_count} document(s)"
                
            elif operation == "count":
                result = await collection.count_documents(query)
                return True, result, f"Count: {result}"
                
            else:
                return False, None, f"Unknown operation: {operation}"
                
        except Exception as e:
            logger.error(f"MongoDB query error: {e}")
            return False, None, f"Error: {str(e)}"
    
    async def get_mongodb_collections(self) -> List[str]:
        """Get list of collections in MongoDB"""
        if not self.mongodb:
            await self.initialize()
        
        try:
            collections = await self.mongodb.list_collection_names()
            return sorted(collections)
        except Exception as e:
            logger.error(f"Error getting MongoDB collections: {e}")
            return []
    
    async def get_mongodb_collection_stats(self, collection_name: str) -> Dict:
        """Get collection statistics"""
        if not self.mongodb:
            await self.initialize()
        
        try:
            stats = await self.mongodb.command("collStats", collection_name)
            return {
                "count": stats.get("count", 0),
                "size": stats.get("size", 0),
                "avgObjSize": stats.get("avgObjSize", 0),
                "storageSize": stats.get("storageSize", 0),
                "indexes": stats.get("nindexes", 0)
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {}


# Global instance
database_service = DatabaseService()
