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
from app.api.health import router as health_router
from app.core.exceptions import handle_exception, AICopilotException
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
        # Initialize database connections with graceful error handling
        try:
            await init_database()
            logger.info("Database connections initialized")
        except Exception as e:
            logger.error("Database initialization failed, service will continue with limited functionality", error=str(e))
            # Don't fail startup completely if database init fails
        
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
    title="ERP AI Copilot Service",
    description="""
    **Enterprise AI Copilot with Step-by-Step Reasoning**
    
    A comprehensive AI assistant for ERP systems featuring:
    
    ## 🤖 Core Features
    - **Step-by-Step Reasoning**: Transparent AI decision-making with real-time streaming
    - **Multi-Source Integration**: Access to databases, APIs, knowledge base, and system commands
    - **WebSocket Streaming**: Real-time reasoning steps with visual indicators
    - **Conversation Management**: Session-based chat with persistent context
    - **Background Processing**: Async job handling for heavy operations
    
    ## 🔧 Technical Capabilities
    - **Memory & Context**: MongoDB-based user memory and session context
    - **Knowledge Base**: Automatic documentation indexing with file watching
    - **API Gateway Integration**: Secure access to ERP service endpoints
    - **System Commands**: RBAC-enforced command execution
    - **Third-party APIs**: Secure proxy for external service integration
    - **Vector Search**: Qdrant-powered semantic search and RAG
    
    ## 🌐 WebSocket Endpoints
    - `/api/v1/websocket/ws/reasoning/{conversation_id}` - Real-time reasoning streaming
    - `/api/v1/ws/chat/{conversation_id}` - Interactive chat sessions
    
    ## 📊 API Categories
    
    ### 💬 Conversation Management (`/api/v1/conversations/*`)
    - `POST /conversations` - Create new conversation session
    - `GET /conversations` - List user conversations with pagination
    - `GET /conversations/{id}` - Get conversation with optional messages
    - `PATCH /conversations/{id}` - Update conversation metadata
    - `DELETE /conversations/{id}` - Delete conversation
    - `POST /conversations/{id}/archive` - Archive conversation
    - `GET /conversations/search` - Search conversations
    - `GET /conversations/analytics` - Conversation analytics
    - `GET /conversations/{id}/messages` - Get conversation messages
    
    ### 🧠 Memory & Context (`/api/v1/memory/*`)
    - `POST /memory/store` - Store user memory/context
    - `GET /memory/retrieve/{id}` - Retrieve specific memory
    - `GET /memory/search` - Search memories by content
    - `GET /memory/context/{conversation_id}` - Get conversation context
    - `DELETE /memory/delete/{id}` - Delete memory
    - `GET /memory/stats` - Memory usage statistics
    
    ### 📚 Knowledge Base (`/api/v1/knowledge-base/*`)
    - `POST /knowledge-base/initialize` - Initialize knowledge base
    - `GET /knowledge-base/status` - Get initialization status
    - `POST /knowledge-base/refresh` - Refresh entire knowledge base
    - `POST /knowledge-base/add-documentation` - Add new documentation
    - `GET /knowledge-base/search` - Semantic search knowledge base
    - `GET /knowledge-base/categories` - Get knowledge categories
    
    ### ⚙️ Background Jobs (`/api/v1/background-jobs/*`)
    - `GET /background-jobs/status` - Job queue status
    - `GET /background-jobs/job/{id}` - Specific job status
    - `POST /background-jobs/schedule` - Schedule background job
    - `DELETE /background-jobs/job/{id}` - Cancel job
    - `GET /background-jobs/file-watcher/status` - File watcher status
    - `POST /background-jobs/file-watcher/rescan` - Force file rescan
    - `POST /background-jobs/knowledge-base/refresh` - Schedule KB refresh
    - `POST /background-jobs/optimize-context/{user_id}` - Optimize user context
    
    ### 🖥️ System Commands (`/api/v1/system-commands/*`)
    - `POST /system-commands/execute` - Execute system command (RBAC)
    - `GET /system-commands/permissions` - Get user permissions
    - `GET /system-commands/history` - Command execution history
    - `POST /system-commands/validate` - Validate command without execution
    
    ### 🌐 Third-party APIs (`/api/v1/third-party-apis/*`)
    - `POST /third-party-apis/call` - Secure API proxy call
    - `GET /third-party-apis/available` - Available APIs for user
    - `POST /third-party-apis/configure` - Configure API credentials
    - `GET /third-party-apis/usage/{api_name}` - API usage statistics
    
    ### 💬 Chat & RAG (`/api/v1/chat/*`, `/api/v1/rag/*`)
    - `POST /chat/message` - Send chat message with reasoning
    - `GET /chat/history/{conversation_id}` - Get chat history
    - `POST /rag/query` - RAG-powered query processing
    - `GET /rag/status` - RAG system status
    
    ### 📊 Infrastructure & Monitoring (`/api/v1/infrastructure/*`)
    - `GET /infrastructure/health` - System health check
    - `GET /infrastructure/metrics` - Performance metrics
    - `GET /infrastructure/services` - Service discovery status
    """,
    version=settings.service.version,
    docs_url="/docs" if settings.service.debug else None,
    redoc_url="/redoc" if settings.service.debug else None,
    openapi_url="/openapi.json" if settings.service.debug else None,
    lifespan=lifespan,
    contact={
        "name": "ERP Suite Development Team",
        "url": "https://github.com/azad25/erp-suite",
        "email": "dev@erpsuite.com"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    },
    servers=[
        {
            "url": "http://localhost:8003",
            "description": "Development server"
        },
        {
            "url": "https://api.erpsuite.com",
            "description": "Production server"
        }
    ]
)

# Add startup event to start gRPC server if needed
@app.on_event("startup")
async def startup_event():
    """Start additional services on application startup."""
    if settings.SERVICE_MODE in ["grpc", "both"]:
        from app.api.grpc import start_grpc_server
        try:
            grpc_task = asyncio.create_task(start_grpc_server())
            logger.info("gRPC server startup task created")
        except Exception as e:
            logger.error(f"Failed to start gRPC server: {e}")
            grpc_task = None

# Add shutdown event to clean up resources
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown."""
    logger.info("Shutting down AI Copilot service...")
    # Add any cleanup logic here if needed

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
app.include_router(health_router, prefix="/api/v1", tags=["health"])
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
    if hasattr(settings, 'SERVICE_MODE') and settings.SERVICE_MODE in ["grpc", "both"]:
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


@app.exception_handler(AICopilotException)
async def ai_copilot_exception_handler(request: Request, exc: AICopilotException):
    """Handle AI Copilot specific exceptions."""
    logger.warning(
        "AI Copilot exception",
        path=request.url.path,
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code
    )
    
    error_response = handle_exception(exc)
    error_response["timestamp"] = time.time()
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions with circuit breaker awareness."""
    logger.error("Unhandled exception", path=request.url.path, error=str(exc), exc_info=True)
    
    error_response = handle_exception(exc)
    error_response["timestamp"] = time.time()
    
    return JSONResponse(
        status_code=error_response["status_code"],
        content=error_response
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
