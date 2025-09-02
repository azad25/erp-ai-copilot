"""
Database connection management for the AI Copilot service.
"""
from typing import Optional, Any, Dict, List, TypeVar, Type, Union, Tuple, AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool
import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis, ConnectionPool
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models
from elasticsearch import AsyncElasticsearch
import asyncio
import structlog

from app.core.config import settings
from app.core.circuit_breaker import (
    circuit_manager, MONGODB_CIRCUIT_CONFIG, REDIS_CIRCUIT_CONFIG, 
    DATABASE_CIRCUIT_CONFIG, CircuitBreakerOpenError
)
from app.core.resilience import (
    with_circuit_breaker, with_retry, DATABASE_RETRY_CONFIG, 
    CACHE_RETRY_CONFIG, health_checker, safe_execute
)
from app.core.exceptions import DatabaseError, CacheError

# Type variables for better type hints
T = TypeVar('T')
ResultType = List[Dict[str, Any]]

logger = structlog.get_logger(__name__)

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
        """Initialize all database connections with graceful error handling."""
        if self._initialized:
            return
        
        initialization_results = {
            "postgres": False,
            "mongodb": False,
            "redis": False,
            "qdrant": False
        }
        
        # Initialize PostgreSQL
        try:
            await self._init_postgres()
            initialization_results["postgres"] = True
        except Exception as e:
            logger.warning("PostgreSQL initialization failed, continuing with other services", error=str(e))
        
        # Initialize MongoDB
        try:
            await self._init_mongodb()
            initialization_results["mongodb"] = True
        except Exception as e:
            logger.warning("MongoDB initialization failed, continuing with other services", error=str(e))
        
        # Initialize Redis
        try:
            await self._init_redis()
            initialization_results["redis"] = True
        except Exception as e:
            logger.warning("Redis initialization failed, continuing with other services", error=str(e))
        
        # Initialize Qdrant
        try:
            await self._init_qdrant()
            initialization_results["qdrant"] = True
        except Exception as e:
            logger.warning("Qdrant initialization failed, continuing with other services", error=str(e))
        
        # Register health checks
        await self._register_health_checks()
        
        self._initialized = True
        successful_services = [service for service, success in initialization_results.items() if success]
        failed_services = [service for service, success in initialization_results.items() if not success]
        
        logger.info(
            "Database initialization completed",
            successful_services=successful_services,
            failed_services=failed_services,
            total_successful=len(successful_services)
        )
        
        # Only raise if all services failed
        if not any(initialization_results.values()):
            raise DatabaseError("initialization", "All database services failed to initialize")
    
    @with_circuit_breaker("postgres_init", DATABASE_CIRCUIT_CONFIG)
    @with_retry(DATABASE_RETRY_CONFIG)
    async def _init_postgres(self):
        """Initialize PostgreSQL connection with circuit breaker and retry logic."""
        try:
            # Convert PostgreSQL URL to async format
            async_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
            
            engine_kwargs = {
                "echo": settings.DEBUG,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
                "connect_args": {
                    "command_timeout": 30,
                    "server_settings": {
                        "application_name": "ai_copilot",
                    },
                },
            }
            
            if settings.DEBUG:
                engine_kwargs["poolclass"] = NullPool
            else:
                engine_kwargs["pool_size"] = settings.DB_MAX_CONNECTIONS
                engine_kwargs["max_overflow"] = settings.DB_MAX_CONNECTIONS * 2
                engine_kwargs["pool_timeout"] = 30
            
            self.postgres_engine = create_async_engine(async_url, **engine_kwargs)
            
            self.postgres_session_factory = async_sessionmaker(
                self.postgres_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
            
            # Test connection with timeout
            async with asyncio.timeout(15.0):
                async with self.postgres_engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
            
            logger.info("PostgreSQL connection initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize PostgreSQL connection", error=str(e))
            raise DatabaseError("postgres_init", str(e))
    
    @with_circuit_breaker("mongodb_init", MONGODB_CIRCUIT_CONFIG)
    @with_retry(DATABASE_RETRY_CONFIG)
    async def _init_mongodb(self):
        """Initialize MongoDB connection with circuit breaker and retry logic."""
        try:
            # Create MongoDB client with minimal background operations to prevent sync client timeouts
            self.mongodb_client = AsyncIOMotorClient(
                settings.MONGODB_URI,
                maxPoolSize=5,  # Reduced pool size
                minPoolSize=0,  # No minimum connections
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
                socketTimeoutMS=30000,
                retryWrites=False,  # Disable retries to prevent background tasks
                retryReads=False,
                # Minimize background operations that create sync clients
                heartbeatFrequencyMS=300000,  # 5 minutes between heartbeats
                appname="ai_copilot_async",
                directConnection=True,  # Direct connection to prevent topology monitoring
                maxIdleTimeMS=600000,  # 10 minutes idle time
                waitQueueTimeoutMS=30000,
                # Disable server monitoring to prevent background sync operations
                connect=False,  # Don't connect immediately
            )
            
            # Test connection with timeout
            await asyncio.wait_for(
                self.mongodb_client.admin.command('ping'),
                timeout=15.0
            )
            
            logger.info("MongoDB connection initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize MongoDB connection", error=str(e))
            raise DatabaseError("mongodb_init", str(e))
    
    @with_circuit_breaker("redis_init", REDIS_CIRCUIT_CONFIG)
    @with_retry(CACHE_RETRY_CONFIG)
    async def _init_redis(self):
        """Initialize Redis connection with circuit breaker and retry logic."""
        try:
            pool = ConnectionPool.from_url(
                settings.redis_url,
                max_connections=settings.REDIS_POOL_SIZE,
                decode_responses=True,
                retry_on_timeout=True,
                health_check_interval=30,
                socket_connect_timeout=10,
                socket_timeout=10,
            )
            
            self.redis_client = Redis(connection_pool=pool)
            
            # Test connection with timeout
            await asyncio.wait_for(
                self.redis_client.ping(),
                timeout=10.0
            )
            
            logger.info("Redis connection initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize Redis connection", error=str(e))
            raise CacheError("redis_init", str(e))
    
    async def _init_qdrant(self):
        """Initialize Qdrant connection."""
        try:
            # Use HTTPS if API key is provided, otherwise HTTP for local development
            use_https = bool(settings.QDRANT_API_KEY)
            
            self.qdrant_client = AsyncQdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
                https=use_https,
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
                
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> ResultType:
        """
        Execute a SQL query and return the results as a list of dictionaries.
        
        Args:
            query: The SQL query to execute
            params: Optional dictionary of parameters for parameterized queries
            
        Returns:
            List[Dict[str, Any]]: Query results as a list of dictionaries
            
        Raises:
            SQLAlchemyError: If there's an error executing the query
        """
        result: ResultType = []
        
        async with get_db_session() as session:
            try:
                # Execute the query with parameters if provided
                if params:
                    result_proxy = await session.execute(text(query), params)
                else:
                    result_proxy = await session.execute(text(query))
                
                # Convert result to list of dictionaries
                if result_proxy.returns_rows:
                    columns = list(result_proxy.keys())
                    rows = result_proxy.fetchall()
                    result = [dict(zip(columns, row)) for row in rows]
                
                return result
                
            except SQLAlchemyError as e:
                logger.error("Database query error", query=query, error=str(e))
                await session.rollback()
                raise
                
            except Exception as e:
                logger.error("Unexpected error executing query", query=query, error=str(e))
                await session.rollback()
                raise SQLAlchemyError(f"Failed to execute query: {str(e)}")
    
    def get_postgres_client(self) -> 'sqlalchemy.ext.asyncio.AsyncEngine':
        """Get PostgreSQL client.
        
        Returns:
            AsyncEngine: The async SQLAlchemy engine instance for PostgreSQL
        """
        if not self.postgres_engine:
            raise RuntimeError("PostgreSQL not initialized")
        return self.postgres_engine
    
    async def get_mongodb_database(self) -> 'motor.motor_asyncio.AsyncIOMotorDatabase':
        """Get MongoDB database instance with circuit breaker protection."""
        if self.mongodb_client is None:
            # Try to reinitialize if not connected
            try:
                await self._init_mongodb()
            except Exception as e:
                raise DatabaseError("mongodb_reconnect", f"Failed to reconnect to MongoDB: {str(e)}")
        
        return self.mongodb_client[settings.MONGODB_DATABASE]
        
    def get_mongo_client(self) -> 'motor.motor_asyncio.AsyncIOMotorClient':
        """Get MongoDB client."""
        if self.mongodb_client is None:
            raise RuntimeError("MongoDB not initialized")
        return self.mongodb_client
    
    async def get_redis_client(self) -> Redis:
        """Get Redis client with circuit breaker protection."""
        if not self.redis_client:
            # Try to reinitialize if not connected
            try:
                await self._init_redis()
            except Exception as e:
                raise CacheError("redis_reconnect", f"Failed to reconnect to Redis: {str(e)}")
        
        return self.redis_client
    
    async def get_qdrant_client(self) -> AsyncQdrantClient:
        """Get Qdrant client."""
        if not self.qdrant_client:
            raise RuntimeError("Qdrant not initialized")
        return self.qdrant_client

    async def get_redis(self):
        """Get Redis client."""
        if not self.redis_client:
            await self._init_redis()
        return self.redis_client

    async def initialize_database(self):
        """Initialize all database connections."""
        await self.initialize()
    
    async def close(self):
        """Close all database connections."""
        try:
            if self.postgres_engine:
                await self.postgres_engine.dispose()
                logger.info("PostgreSQL connections closed")
            
            if self.mongodb_client is not None:
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
    
    async def _register_health_checks(self):
        """Register health check functions for all database services."""
        # PostgreSQL health check
        async def postgres_health():
            if not self.postgres_engine:
                return {"status": "not_initialized"}
            async with asyncio.timeout(5.0):
                async with self.postgres_engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
            return {"status": "healthy"}
        
        # MongoDB health check
        async def mongodb_health():
            if not self.mongodb_client:
                return {"status": "not_initialized"}
            async with asyncio.timeout(5.0):
                await self.mongodb_client.admin.command('ping')
            return {"status": "healthy"}
        
        # Redis health check
        async def redis_health():
            if not self.redis_client:
                return {"status": "not_initialized"}
            async with asyncio.timeout(5.0):
                await self.redis_client.ping()
            return {"status": "healthy"}
        
        # Qdrant health check
        async def qdrant_health():
            if not self.qdrant_client:
                return {"status": "not_initialized"}
            async with asyncio.timeout(5.0):
                await self.qdrant_client.get_collections()
            return {"status": "healthy"}
        
        # Register all health checks
        health_checker.register_health_check("postgres", postgres_health)
        health_checker.register_health_check("mongodb", mongodb_health)
        health_checker.register_health_check("redis", redis_health)
        health_checker.register_health_check("qdrant", qdrant_health)
    
    async def health_check(self) -> dict:
        """Check health of all database connections using the health checker."""
        return await health_checker.check_all_services()


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async for session in db_manager.get_postgres_session():
        yield session


async def get_mongodb():
    """Dependency to get MongoDB database with circuit breaker protection."""
    try:
        return await db_manager.get_mongodb_database()
    except CircuitBreakerOpenError:
        logger.warning("MongoDB circuit breaker is open, service unavailable")
        raise DatabaseError("mongodb", "Service temporarily unavailable")


async def get_redis():
    """Dependency to get Redis client with circuit breaker protection."""
    try:
        return await db_manager.get_redis_client()
    except CircuitBreakerOpenError:
        logger.warning("Redis circuit breaker is open, service unavailable")
        raise CacheError("redis", "Service temporarily unavailable")


async def get_qdrant():
    """Dependency to get Qdrant client."""
    return await db_manager.get_qdrant_client()


async def init_database():
    """Initialize database connections."""
    await db_manager.initialize()


async def close_database():
    """Close database connections."""
    await db_manager.close()


async def check_database_health():
    """Check database health."""
    return await db_manager.health_check()
