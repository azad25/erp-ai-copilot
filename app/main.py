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
from app.api.v1.router import api_router
from app.api.websocket import websocket_router
from app.api.grpc import grpc_router
from app.middleware.auth import AuthMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.core.metrics import setup_metrics
from app.rag.service import RAGService

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
        
        yield
        
    except Exception as e:
        logger.error("Failed to start service", error=str(e))
        raise
    
    finally:
        # Shutdown
        logger.info("Shutting down AI Copilot service")
        
        # Close Kafka connections
        await kafka_service.close()
        logger.info("Kafka connections closed")
        
        # Close database connections
        await close_database()
        logger.info("Service shutdown completed")


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

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/ws")
app.include_router(grpc_router, prefix="/grpc")


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add process time header to responses."""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # Record metrics
    REQUEST_LATENCY.observe(process_time)
    
    return response


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Record metrics for all requests."""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        return response
        
    except Exception as e:
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=500
        ).inc()
        raise


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
    return {
        "message": "AI Copilot Service is running",
        "version": settings.service.version,
        "status": "healthy",
        "timestamp": time.time()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db_health = await check_database_health()
    
    return {
        "status": "healthy",
        "database": db_health,
        "timestamp": time.time()
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
