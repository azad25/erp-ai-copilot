"""
Knowledge Base API Routes

Endpoints for managing the AI Copilot's knowledge base initialization,
status checking, and manual refresh operations.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any
import logging

from app.services.knowledge_base_initialization_service import knowledge_base_init_service
from app.middleware.auth import get_current_user_with_org
from app.core.exceptions import ServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.post("/initialize")
async def initialize_knowledge_base(
    background_tasks: BackgroundTasks,
    force_refresh: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user_with_org)
):
    """
    Initialize the knowledge base from documentation files
    
    - Processes all markdown files in docs/ folder
    - Creates embeddings and vectors in Qdrant
    - Indexes ERP architecture and API documentation
    - Runs as background task for large document sets
    """
    try:
        # Check if user has admin permissions
        user_role = current_user.get("role", "user")
        if user_role not in ["admin", "super_admin"]:
            raise HTTPException(
                status_code=403, 
                detail="Only administrators can initialize knowledge base"
            )
        
        # Run initialization as background task
        background_tasks.add_task(
            knowledge_base_init_service.initialize_knowledge_base,
            force_refresh
        )
        
        return {
            "message": "Knowledge base initialization started",
            "force_refresh": force_refresh,
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Knowledge base initialization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_knowledge_base_status(
    current_user: Dict[str, Any] = Depends(get_current_user_with_org)
):
    """
    Get knowledge base initialization status and statistics
    
    Returns:
    - Total knowledge entries count
    - Categories breakdown
    - Vector count in Qdrant
    - Processing status
    """
    try:
        status = await knowledge_base_init_service.get_initialization_status()
        return status
        
    except Exception as e:
        logger.error(f"Failed to get knowledge base status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_knowledge_base(
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user_with_org)
):
    """
    Refresh the entire knowledge base
    
    - Clears existing knowledge entries
    - Re-processes all documentation
    - Updates embeddings and vectors
    """
    try:
        # Check admin permissions
        user_role = current_user.get("role", "user")
        if user_role not in ["admin", "super_admin"]:
            raise HTTPException(
                status_code=403, 
                detail="Only administrators can refresh knowledge base"
            )
        
        background_tasks.add_task(knowledge_base_init_service.refresh_knowledge_base)
        
        return {
            "message": "Knowledge base refresh started",
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Knowledge base refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-documentation")
async def add_new_documentation(
    file_path: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user_with_org)
):
    """
    Add new documentation file to knowledge base
    
    Args:
        file_path: Absolute path to the markdown file to add
    """
    try:
        # Check permissions
        user_role = current_user.get("role", "user")
        if user_role not in ["admin", "manager", "super_admin"]:
            raise HTTPException(
                status_code=403, 
                detail="Insufficient permissions to add documentation"
            )
        
        background_tasks.add_task(
            knowledge_base_init_service.add_new_documentation,
            file_path
        )
        
        return {
            "message": f"Documentation file {file_path} will be added to knowledge base",
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Failed to add documentation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_knowledge_base(
    query: str,
    limit: int = 10,
    category: str = None,
    current_user: Dict[str, Any] = Depends(get_current_user_with_org)
):
    """
    Search the knowledge base using semantic search
    
    Args:
        query: Search query text
        limit: Maximum number of results
        category: Optional category filter
    """
    try:
        from app.services.memory_service import memory_service
        
        results = await memory_service.search_knowledge(
            query=query,
            limit=limit,
            category=category
        )
        
        return {
            "query": query,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Knowledge base search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_knowledge_categories(
    current_user: Dict[str, Any] = Depends(get_current_user_with_org)
):
    """Get all available knowledge base categories"""
    try:
        from app.database.connection import get_mongodb
        
        mongodb = await get_mongodb()
        
        # Get distinct categories
        categories = await mongodb.knowledge_base.distinct("category")
        
        # Get count per category
        pipeline = [
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        cursor = mongodb.knowledge_base.aggregate(pipeline)
        category_counts = {}
        
        async for doc in cursor:
            category_counts[doc["_id"]] = doc["count"]
        
        return {
            "categories": categories,
            "category_counts": category_counts
        }
        
    except Exception as e:
        logger.error(f"Failed to get knowledge categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))
