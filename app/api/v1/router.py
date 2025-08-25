"""API v1 router configuration for the AI Copilot service."""
from fastapi import APIRouter
from app.config.settings import get_settings

from .chat import router as chat_router
from .infrastructure import router as infrastructure_router
from .dashboard import router as dashboard_router
from .rag import router as rag_router

# Get settings
settings = get_settings()

# Create the main API router
api_router = APIRouter(prefix="/v1")

# Include all sub-routers
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(infrastructure_router, prefix="/infrastructure", tags=["infrastructure"])
api_router.include_router(dashboard_router, prefix="/ai-copilot", tags=["dashboard"])

# Include RAG router if enabled
if settings.rag.enabled:
    api_router.include_router(rag_router, prefix="/rag", tags=["rag"])