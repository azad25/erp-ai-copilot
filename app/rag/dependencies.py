"""Dependency functions for RAG engine.

Provides dependency injection functions for FastAPI endpoints that need access to the RAG service.
"""

from fastapi import Depends, Request, HTTPException, status
from app.database.connection import get_db_manager
from app.rag.service import RAGService


async def get_rag_service(request: Request) -> RAGService:
    """Dependency function to get the RAG service instance.
    
    Args:
        request: The FastAPI request object
        
    Returns:
        RAGService: An initialized RAG service instance
        
    Raises:
        HTTPException: If the RAG service is not available or not initialized
    """
    # Check if RAG service is stored in app state (initialized during startup)
    if hasattr(request.app.state, "rag_service"):
        return request.app.state.rag_service
    
    # If not in app state, create a new instance
    try:
        db_manager = await get_db_manager()
        rag_service = RAGService(db_manager)
        await rag_service.initialize()
        return rag_service
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"RAG service unavailable: {str(e)}"
        )