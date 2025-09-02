"""
Main FastAPI application for the AI Copilot service.
"""
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.openmetrics.exposition import generate_latest as generate_openmetrics

from app.config.settings import get_settings
from app.database.connection import init_database, close_database, check_database_health, get_db_manager
from app.services.kafka_service import kafka_service
from app.services.conversation_service import conversation_service
from app.services.memory_service import memory_service
from app.services.api_gateway_client import api_gateway_client
from app.services.kafka_integration_service import kafka_service as kafka_integration
from app.services.service_discovery_service import service_discovery
from app.services.user_preferences_service import user_preferences_service
from app.services.third_party_api_service import third_party_api_service
from app.services.system_command_service import system_command_service
from app.api.v1.router import api_router
from app.api.routes import conversations, background_jobs, websocket, memory, system_commands, third_party_apis
try:
    from app.api.routes import grpc_router
except ImportError:
    grpc_router = None
from app.api.websocket_handler import websocket_handler
from app.services.knowledge_base_initialization_service import knowledge_base_init_service
from app.services.background_job_service import background_job_service
from app.services.file_watcher_service import file_watcher_service
from app.api.routes.conversations import router as conversations_router
from app.api.websocket.router import router as websocket_router
from app.api.routes.knowledge_base import router as knowledge_base_router
from app.api.routes.background_jobs import router as background_jobs_router
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.core.metrics import setup_metrics
from app.rag.service import RAGService
from app.clients.auth_grpc import get_auth_service_client, close_auth_service_client
from app.services.jwt_service import initialize_jwt_service
from app.services.token_cache_service import initialize_token_cache_service
import redis.asyncio as redis

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)
settings = get_settings()

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting AI Copilot service", version=settings.service.version, environment=settings.service.environment)
    
    try:
        # Initialize database connections
        await init_database()
        logger.info("Database connections initialized")
        
        # Initialize Kafka service
        await kafka_service.initialize()
        logger.info("Kafka service initialized")
        
        # Setup metrics
        setup_metrics()
        logger.info("Metrics setup completed")
        
        # Initialize RAG engine if enabled
        if settings.rag.enabled:
            try:
                db_manager = await get_db_manager()
                rag_service = RAGService(db_manager)
                await rag_service.initialize()
                logger.info("RAG engine initialized successfully")
                app.state.rag_service = rag_service
            except Exception as e:
                logger.error("Failed to initialize RAG engine", error=str(e))
                if settings.service.debug:
                    raise
        else:
            logger.info("RAG engine disabled in settings")
            
        # Initialize Redis connection for token caching
        try:
            redis_client = redis.Redis(
                host=settings.redis.host,
                port=settings.redis.port,
                password=settings.redis.password,
                db=settings.redis.db,
                decode_responses=True
            )
            # Test Redis connection
            await redis_client.ping()
            logger.info("Redis connection established successfully")
            app.state.redis_client = redis_client
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            if settings.service.debug:
                raise
        
        # Initialize token cache service
        try:
            token_cache_service = initialize_token_cache_service(redis_client, cache_ttl_minutes=30)
            logger.info("Token cache service initialized successfully")
            app.state.token_cache_service = token_cache_service
        except Exception as e:
            logger.error("Failed to initialize token cache service", error=str(e))
            if settings.service.debug:
                raise
        
        # Initialize JWT service for local token validation (fallback)
        try:
            jwt_secret = settings.security.jwt_secret
            jwt_algorithm = settings.security.jwt_algorithm
            jwt_service = initialize_jwt_service(jwt_secret, jwt_algorithm)
            logger.info("JWT service initialized successfully")
            app.state.jwt_service = jwt_service
        except Exception as e:
            logger.error("Failed to initialize JWT service", error=str(e))
            if settings.service.debug:
                raise
        
        # Initialize LLM service
        try:
            from app.services.llm_service import initialize_llm_service
            llm_service = initialize_llm_service()
            logger.info("LLM service initialized successfully")
            app.state.llm_service = llm_service
        except Exception as e:
            logger.error("Failed to initialize LLM service", error=str(e))
            if settings.service.debug:
                raise
        
        # Start background job service
        try:
            await background_job_service.start()
            logger.info("Background job service started")
        except Exception as e:
            logger.error("Failed to start background job service", error=str(e))
        
        # Start file watcher service
        try:
            await file_watcher_service.start_monitoring()
            logger.info("File watcher service started")
        except Exception as e:
            logger.error("Failed to start file watcher service", error=str(e))
        
        # Initialize knowledge base from documentation (only if not already initialized)
        try:
            db_manager = await get_db_manager()
            if db_manager.mongodb_client is not None:
                status = await knowledge_base_init_service.get_initialization_status()
            else:
                status = {"status": "not_initialized", "total_knowledge_entries": 0}
            if status.get("status") != "ready" or status.get("total_knowledge_entries", 0) == 0:
                logger.info("Scheduling knowledge base initialization...")
                # Schedule as background job instead of blocking startup
                await background_job_service.schedule_job(
                    job_type="initialize_knowledge_base",
                    function_name="refresh_knowledge_base",
                    priority=background_job_service.JobPriority.HIGH
                )
                logger.info("Knowledge base initialization scheduled")
            else:
                logger.info(f"Knowledge base already initialized with {status.get('total_knowledge_entries', 0)} entries")
        except Exception as e:
            logger.error("Failed to initialize knowledge base", error=str(e))
            # Don't fail startup if knowledge base init fails
        
        # Initialize gRPC clients
        try:
            # Initialize auth service client
            auth_client = get_auth_service_client()
            logger.info("gRPC clients initialized successfully")
            app.state.auth_client = auth_client
        except Exception as e:
            logger.error("Failed to initialize gRPC clients", error=str(e))
            if settings.service.debug:
                raise
        
        yield
        
    except Exception as e:
        logger.error("Failed to start service", error=str(e))
        raise
    
    finally:
        # Cleanup resources
        logger.info("Shutting down AI Copilot Service...")
        
        # Close Redis connection
        if hasattr(app.state, 'redis_client'):
            await app.state.redis_client.close()
            logger.info("Redis connection closed")
        
        # Close database connections
        await close_database()
        
        # Close gRPC clients
        await close_auth_service_client()
        
        # Stop file watcher service
        if file_watcher_service:
            await file_watcher_service.stop_monitoring()
        
        # Stop background job service
        if background_job_service:
            await background_job_service.stop()
        
        # Close Kafka service
        if kafka_service:
            await kafka_service.close()
        
        logger.info("AI Copilot Service shutdown complete")
        
        # Close gRPC clients
        await close_auth_service_client()
        logger.info("gRPC clients closed")


# Create FastAPI application
app = FastAPI(
    title="AI Copilot Service",
    description="Enterprise AI Copilot service for ERP systems",
    version=settings.service.version,
    docs_url="/docs" if settings.service.debug else None,
    redoc_url="/redoc" if settings.service.debug else None,
    openapi_url="/openapi.json" if settings.service.debug else None,
    lifespan=lifespan,
)

# Add startup event to start gRPC server if needed
@app.on_event("startup")
async def startup_event():
    """Start additional services on application startup."""
    if settings.service.mode in ["grpc", "both"]:
        from app.api.grpc import start_grpc_server
        await start_grpc_server()
        logger.info("gRPC server started", port=settings.grpc.port)

# Add shutdown event to clean up resources
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown."""
    if settings.service.mode in ["grpc", "both"]:
        from app.api.grpc import stop_grpc_server
        await stop_grpc_server()
        logger.info("gRPC server stopped")

# Enable CORS middleware with WebSocket support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for WebSocket testing
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

# Temporarily disable all middleware to test WebSocket connections
# app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
# app.add_middleware(LoggingMiddleware)
# app.add_middleware(RateLimitMiddleware)

# Include API routers
app.include_router(conversations_router, prefix="/api/v1/conversations", tags=["conversations"])
app.include_router(background_jobs_router, prefix="/api/v1/background-jobs", tags=["background-jobs"])
app.include_router(knowledge_base_router, prefix="/api/v1/knowledge-base", tags=["knowledge-base"])
app.include_router(websocket_router, prefix="/api/v1/ws", tags=["websocket"])
app.include_router(websocket.router, prefix="/api/v1/websocket", tags=["websocket-reasoning"])
app.include_router(memory.router, prefix="/api/v1/memory", tags=["memory"])
app.include_router(system_commands.router, prefix="/api/v1/system-commands", tags=["system-commands"])
app.include_router(third_party_apis.router, prefix="/api/v1/third-party-apis", tags=["third-party-apis"])
app.include_router(api_router, prefix="/api/v1")

if grpc_router:
    app.include_router(grpc_router, prefix="/api/v1/grpc", tags=["grpc"])

# Include gRPC router if enabled
try:
    from app.api.grpc import grpc_router
    if settings.service.mode in ["grpc", "both"]:
        app.include_router(grpc_router, prefix="/grpc")
except ImportError:
    logger.warning("gRPC router not available")

# Temporarily disable HTTP middleware that interferes with WebSocket connections
# @app.middleware("http")
# async def add_process_time_header(request: Request, call_next):
#     """Add process time header to responses."""
#     start_time = time.time()
#     
#     response = await call_next(request)
#     
#     process_time = time.time() - start_time
#     response.headers["X-Process-Time"] = str(process_time)
#     
#     # Record metrics
#     REQUEST_LATENCY.observe(process_time)
#     
#     return response


# @app.middleware("http")
# async def metrics_middleware(request: Request, call_next):
#     """Record metrics for all requests."""
#     start_time = time.time()
#     
#     try:
#         response = await call_next(request)
#         REQUEST_COUNT.labels(
#             method=request.method,
#             endpoint=request.url.path,
#             status=response.status_code
#         ).inc()
#         return response
#         
#     except Exception as e:
#         REQUEST_COUNT.labels(
#             method=request.method,
#             endpoint=request.url.path,
#             status=500
#         ).inc()
#         raise


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    logger.warning("Validation error", path=request.url.path, errors=exc.errors())
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "details": exc.errors(),
            "timestamp": time.time(),
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    logger.warning("HTTP exception", path=request.url.path, status_code=exc.status_code, detail=exc.detail)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": time.time(),
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error("Unhandled exception", path=request.url.path, error=str(exc), exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "Internal server error",
            "timestamp": time.time(),
        }
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "AI Copilot Service is running", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connectivity
        db_status = await check_database_health()
        
        return {
            "status": "ok",
            "service": "ai-copilot",
            "timestamp": time.time(),
            "database": db_status,
            "version": settings.service.version
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/status")
async def service_status():
    """Service status endpoint for debugging."""
    return {
        "service": "ai-copilot",
        "status": "running",
        "features": {
            "websocket_reasoning": True,
            "background_jobs": True,
            "knowledge_base": True,
            "conversation_management": True,
            "file_watcher": True
        },
        "endpoints": {
            "conversations": "/conversations",
            "knowledge_base": "/knowledge-base",
            "background_jobs": "/background-jobs",
            "websocket": "/ws/chat"
        }
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest()


@app.get("/async-test")
async def async_test():
    """Test endpoint for async/await patterns."""
    import asyncio
    
    # Simulate async operations
    await asyncio.sleep(0.1)
    
    return {
        "message": "Async operations completed successfully",
        "timestamp": time.time()
    }
