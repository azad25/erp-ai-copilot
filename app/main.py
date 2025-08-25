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
from app.database.connection import init_database, close_database
from app.api.v1.router import api_router
from app.api.websocket import websocket_router
from app.api.grpc import grpc_router
from app.middleware.auth import AuthMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.core.metrics import setup_metrics

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
        
        # Setup metrics
        setup_metrics()
        logger.info("Metrics setup completed")
        
        yield
        
    except Exception as e:
        logger.error("Failed to start service", error=str(e))
        raise
    
    finally:
        # Shutdown
        logger.info("Shutting down AI Copilot service")
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
        "service": "AI Copilot Service",
        "version": settings.service.version,
        "environment": settings.service.environment,
        "status": "running",
        "timestamp": time.time(),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from app.database.connection import check_database_health
    
    try:
        db_health = await check_database_health()
        
        # Determine overall health
        overall_status = "healthy"
        if any(service["status"] == "unhealthy" for service in db_health.values()):
            overall_status = "degraded"
        if any(service["status"] == "not_initialized" for service in db_health.values()):
            overall_status = "initializing"
        
        return {
            "status": overall_status,
            "timestamp": time.time(),
            "version": settings.service.version,
            "environment": settings.service.environment,
            "services": db_health,
        }
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": time.time(),
                "error": str(e),
            }
        )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest()


@app.get("/metrics/openmetrics")
async def openmetrics():
    """OpenMetrics format metrics endpoint."""
    return generate_openmetrics()


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    from app.database.connection import check_database_health
    
    try:
        db_health = await check_database_health()
        
        # Check if all services are healthy
        all_healthy = all(service["status"] == "healthy" for service in db_health.values())
        
        if all_healthy:
            return {"status": "ready", "timestamp": time.time()}
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "timestamp": time.time(),
                    "services": db_health,
                }
            )
            
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "timestamp": time.time(),
                "error": str(e),
            }
        )


@app.get("/info")
async def service_info():
    """Service information endpoint."""
    return {
        "service": {
            "name": settings.service.name,
            "version": settings.service.version,
            "environment": settings.service.environment,
            "debug": settings.service.debug,
        },
        "capabilities": {
            "ai_models": {
                "openai": bool(settings.ai.openai_api_key),
                "anthropic": bool(settings.ai.anthropic_api_key),
                "ollama": True,  # Always available locally
            },
            "rag_enabled": settings.rag.enabled,
            "websocket": True,
            "grpc": True,
            "background_tasks": True,
        },
        "limits": {
            "max_concurrent_requests": settings.service.max_concurrent_requests,
            "request_timeout": settings.service.request_timeout,
            "memory_limit_mb": settings.service.memory_limit_mb,
        },
        "timestamp": time.time(),
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.service.host,
        port=settings.service.port,
        reload=settings.service.debug,
        workers=settings.service.workers,
        log_level=settings.monitoring.log_level.lower(),
    )
