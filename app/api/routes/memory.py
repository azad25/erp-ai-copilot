"""
Memory Management API routes for AI Copilot
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Any, Optional
from uuid import UUID
import logging

from app.services.memory_service import memory_service
from app.services.auth_service import get_current_user
from app.models.api import User, MemoryRequest, MemoryResponse

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=Dict[str, Any])
async def memory_root_endpoint(
    current_user: User = Depends(get_current_user)
):
    """Root memory endpoint for testing"""
    return {
        "status": "Memory service is running",
        "endpoints": [
            "/store",
            "/retrieve/{memory_id}",
            "/search",
            "/context/{conversation_id}",
            "/delete/{memory_id}",
            "/stats"
        ]
    }

@router.post("/store", response_model=Dict[str, Any])
async def store_memory(
    request: MemoryRequest,
    current_user: User = Depends(get_current_user)
):
    """Store a new memory"""
    try:
        memory_id = await memory_service.store_memory(
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            memory_type=request.memory_type,
            content=request.content,
            context=request.context,
            importance=request.importance
        )
        
        return {
            "memory_id": memory_id,
            "status": "stored",
            "timestamp": memory_service._get_current_time().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/retrieve/{memory_id}", response_model=MemoryResponse)
async def retrieve_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user)
):
    """Retrieve a specific memory by ID"""
    try:
        memory = await memory_service.retrieve_memory(memory_id, current_user.id)
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return MemoryResponse(**memory)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search", response_model=List[MemoryResponse])
async def search_memories(
    query: str = Query(..., description="Search query"),
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    limit: int = Query(10, description="Maximum number of results"),
    current_user: User = Depends(get_current_user)
):
    """Search memories by content"""
    try:
        memories = await memory_service.search_memories(
            user_id=current_user.id,
            query=query,
            memory_type=memory_type,
            limit=limit
        )
        
        return [MemoryResponse(**memory) for memory in memories]
        
    except Exception as e:
        logger.error(f"Failed to search memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/context/{conversation_id}", response_model=Dict[str, Any])
async def get_conversation_context(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get conversation context and related memories"""
    try:
        context = await memory_service.get_conversation_context(
            conversation_id=conversation_id,
            user_id=current_user.id
        )
        
        return context
        
    except Exception as e:
        logger.error(f"Failed to get conversation context: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete/{memory_id}")
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a memory"""
    try:
        success = await memory_service.delete_memory(memory_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        
        return {"status": "deleted", "memory_id": memory_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats", response_model=Dict[str, Any])
async def get_memory_stats(
    current_user: User = Depends(get_current_user)
):
    """Get memory usage statistics"""
    try:
        stats = await memory_service.get_user_memory_stats(current_user.id)
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
