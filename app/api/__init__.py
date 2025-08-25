"""
API Package

REST API endpoints for the UNIBASE ERP AI Copilot service
"""

from fastapi import APIRouter

# Import all routers
from .chat import router as chat_router
from .conversations import router as conversations_router
from .rag import router as rag_router
from .health import router as health_router

__all__ = ["chat_router", "conversations_router", "rag_router", "health_router"]