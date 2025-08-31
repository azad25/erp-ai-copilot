"""
Database connection management for the AI Copilot service.
"""
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Any, Dict, List
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import asyncpg
import motor.motor_asyncio
import redis.asyncio as redis
import qdrant_client
from qdrant_client.http import models as qdrant_models
from elasticsearch import AsyncElasticsearch
import structlog

from app.config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Global instance of the database manager
_db_manager = None


async def get_db_manager() -> 'DatabaseManager':
    """Get or create the database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    return _db_manager


class DatabaseManager:
    """Database connection manager."""
    
    def __init__(self):
        self.postgres_engine: Optional[create_async_engine] = None
        self.postgres_session_factory: Optional[async_sessionmaker] = None
        self.mongodb_client: Optional[AsyncIOMotorClient] = None
        self.redis_client: Optional[Redis] = None
        self.qdrant_client: Optional[AsyncQdrantClient] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize all database connections."""
        if self._initialized:
            return
        
        try:
            # Initialize PostgreSQL
            await self._init_postgres()
            
            # Initialize MongoDB
            await self._init_mongodb()
            
            # Initialize Redis
            await self._init_redis()
            
            # Initialize Qdrant
            await self._init_qdrant()
            
            self._initialized = True
            logger.info("All database connections initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize database connections", error=str(e))
            raise
    
    async def _init_postgres(self):
        """Initialize PostgreSQL connection."""
        try:
            # Convert PostgreSQL URL to async format
            async_url = settings.database.url.replace("postgresql://", "postgresql+asyncpg://")
            
            engine_kwargs = {
                "echo": settings.service.debug,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            }
            
            if settings.service.debug:
                engine_kwargs["poolclass"] = NullPool
            else:
                engine_kwargs["pool_size"] = settings.database.max_connections
                engine_kwargs["max_overflow"] = settings.database.max_connections * 2
            
            self.postgres_engine = create_async_engine(async_url, **engine_kwargs)
            
            self.postgres_session_factory = async_sessionmaker(
                self.postgres_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
            
            # Test connection
            async with self.postgres_engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            logger.info("PostgreSQL connection initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize PostgreSQL connection", error=str(e))
            raise
    
    async def _init_mongodb(self):
        """Initialize MongoDB connection."""
        try:
            self.mongodb_client = AsyncIOMotorClient(
                settings.mongodb.uri,
                maxPoolSize=settings.mongodb.max_pool_size,
                minPoolSize=settings.mongodb.min_pool_size,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
            )
            
            # Test connection
            await self.mongodb_client.admin.command('ping')
            
            logger.info("MongoDB connection initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize MongoDB connection", error=str(e))
            raise
    
    async def _init_redis(self):
        """Initialize Redis connection."""
        try:
            pool = ConnectionPool.from_url(
                settings.redis.url,
                max_connections=settings.redis.pool_size,
                decode_responses=settings.redis.decode_responses,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            
            self.redis_client = Redis(connection_pool=pool)
            
            # Test connection
            await self.redis_client.ping()
            
            logger.info("Redis connection initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize Redis connection", error=str(e))
            raise
    
    async def _init_qdrant(self):
        """Initialize Qdrant connection."""
        try:
            self.qdrant_client = AsyncQdrantClient(
                host=settings.qdrant.host,
                port=settings.qdrant.port,
                api_key=settings.qdrant.api_key,
                https=False,  # Using HTTP for local development
                timeout=30.0
            )
            
            # Test connection
            await self.qdrant_client.get_collections()
            
            logger.info("Qdrant connection initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize Qdrant connection", error=str(e))
            raise
    
    async def get_postgres_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get PostgreSQL session."""
        if not self.postgres_session_factory:
            raise RuntimeError("PostgreSQL not initialized")
        
        session = self.postgres_session_factory()
        try:
            yield session
        except Exception as e:
            try:
                await session.rollback()
            except Exception as rollback_error:
                logger.error("Error during rollback", error=str(rollback_error))
            logger.error("Database session error", error=str(e))
            raise
        finally:
            try:
                await session.close()
            except Exception as close_error:
                logger.error("Error closing session", error=str(close_error))
                
    async def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        async with get_db_session() as session:
            try:
                if params:
                    result = await session.execute(text(query), params)
                else:
                    result = await session.execute(text(query))
                
                # Convert result to list of dictionaries
                columns = result.keys()
                rows = result.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            except Exception as e:
                logger.error("Error executing query", error=str(e))
                await session.rollback()
                raise
    
    def get_postgres_client(self):
        """Get PostgreSQL client."""
        if not self.postgres_engine:
            raise RuntimeError("PostgreSQL not initialized")
        return self.postgres_engine
    
    def get_mongodb_database(self):
        """Get MongoDB database instance."""
        if not self.mongodb_client:
            raise RuntimeError("MongoDB not initialized")
        return self.mongodb_client[settings.mongodb.database]
        
    def get_mongo_client(self):
        """Get MongoDB client."""
        if not self.mongodb_client:
            raise RuntimeError("MongoDB not initialized")
        return self.mongodb_client
    
    def get_redis_client(self) -> Redis:
        """Get Redis client."""
        if not self.redis_client:
            raise RuntimeError("Redis not initialized")
        return self.redis_client
    
    def get_qdrant_client(self) -> AsyncQdrantClient:
        """Get Qdrant client."""
        if not self.qdrant_client:
            raise RuntimeError("Qdrant not initialized")
        return self.qdrant_client
    
    async def close(self):
        """Close all database connections."""
        try:
            if self.postgres_engine:
                await self.postgres_engine.dispose()
                logger.info("PostgreSQL connections closed")
            
            if self.mongodb_client:
                self.mongodb_client.close()
                logger.info("MongoDB connections closed")
            
            if self.redis_client:
                await self.redis_client.close()
                logger.info("Redis connections closed")
            
            if self.qdrant_client:
                await self.qdrant_client.close()
                logger.info("Qdrant connections closed")
            
            self._initialized = False
            logger.info("All database connections closed successfully")
            
        except Exception as e:
            logger.error("Error closing database connections", error=str(e))
    
    async def health_check(self) -> dict:
        """Check health of all database connections."""
        health_status = {
            "postgres": {"status": "unknown", "error": None},
            "mongodb": {"status": "unknown", "error": None},
            "redis": {"status": "unknown", "error": None},
            "qdrant": {"status": "unknown", "error": None},
        }
        
        # Check PostgreSQL
        try:
            if self.postgres_engine:
                async with self.postgres_engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
                health_status["postgres"]["status"] = "healthy"
            else:
                health_status["postgres"]["status"] = "not_initialized"
        except Exception as e:
            health_status["postgres"]["status"] = "unhealthy"
            health_status["postgres"]["error"] = str(e)
        
        # Check MongoDB
        try:
            if self.mongodb_client:
                await self.mongodb_client.admin.command('ping')
                health_status["mongodb"]["status"] = "healthy"
            else:
                health_status["mongodb"]["status"] = "not_initialized"
        except Exception as e:
            health_status["mongodb"]["status"] = "unhealthy"
            health_status["mongodb"]["error"] = str(e)
        
        # Check Redis
        try:
            if self.redis_client:
                await self.redis_client.ping()
                health_status["redis"]["status"] = "healthy"
            else:
                health_status["redis"]["status"] = "not_initialized"
        except Exception as e:
            health_status["redis"]["status"] = "unhealthy"
            health_status["redis"]["error"] = str(e)
        
        # Check Qdrant
        try:
            if self.qdrant_client:
                await self.qdrant_client.get_collections()
                health_status["qdrant"]["status"] = "healthy"
            else:
                health_status["qdrant"]["status"] = "not_initialized"
        except Exception as e:
            health_status["qdrant"]["status"] = "unhealthy"
            health_status["qdrant"]["error"] = str(e)
        
        return health_status


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async for session in db_manager.get_postgres_session():
        yield session


async def get_mongodb():
    """Dependency to get MongoDB database."""
    return db_manager.get_mongodb_database()


async def get_redis():
    """Dependency to get Redis client."""
    return db_manager.get_redis_client()


async def get_qdrant():
    """Dependency to get Qdrant client."""
    return db_manager.get_qdrant_client()


async def init_database():
    """Initialize database connections."""
    await db_manager.initialize()


async def close_database():
    """Close database connections."""
    await db_manager.close()


async def check_database_health():
    """Check database health."""
    return await db_manager.health_check()
