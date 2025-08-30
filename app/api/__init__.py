"""
API Package

REST API endpoints for the UNIBASE ERP AI Copilot service
"""

from fastapi import APIRouter

# Import all routers
from .v1.chat import router as chat_router

__all__ = ["chat_router"]