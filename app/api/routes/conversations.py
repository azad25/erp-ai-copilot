"""
Conversation Management API Routes

Provides REST endpoints for conversation session management,
message retrieval, and conversation analytics.
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from pydantic import BaseModel, Field
from datetime import datetime

from app.services.conversation_service import conversation_service
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    title: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationResponse(BaseModel):
    conversation_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    message_count: int
    context: Dict[str, Any]
    metadata: Dict[str, Any]


class MessageResponse(BaseModel):
    message_id: str
    conversation_id: str
    role: str
    content: str
    metadata: Dict[str, Any]
    created_at: str


class ConversationWithMessagesResponse(BaseModel):
    conversation: ConversationResponse
    messages: List[MessageResponse]


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    user_id: str = Query(..., description="User ID"),
    organization_id: str = Query(..., description="Organization ID")
):
    """Create a new conversation session"""
    try:
        conversation = await conversation_service.create_conversation(
            user_id=user_id,
            organization_id=organization_id,
            title=request.title,
            context=request.context,
            metadata=request.metadata
        )
        
        return ConversationResponse(**conversation)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=Dict[str, Any])
async def get_user_conversations(
    user_id: str = Query(..., description="User ID"),
    organization_id: str = Query(..., description="Organization ID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """Get user's conversation sessions with pagination"""
    try:
        conversations = await conversation_service.get_user_conversations(
            user_id=user_id,
            organization_id=organization_id,
            limit=limit,
            offset=(page - 1) * limit,
            status=status
        )
        
        return {
            "conversations": [ConversationResponse(**conv) for conv in conversations["conversations"]],
            "total": conversations["total"],
            "page": page,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}", response_model=ConversationWithMessagesResponse)
async def get_conversation(
    conversation_id: str = Path(..., description="Conversation ID"),
    include_messages: bool = Query(False, description="Include conversation messages"),
    message_limit: int = Query(50, ge=1, le=200, description="Maximum messages to return")
):
    """Get conversation details and optionally messages"""
    try:
        conversation = await conversation_service.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = []
        if include_messages:
            messages_data = await conversation_service.get_conversation_messages(
                conversation_id=conversation_id,
                limit=message_limit
            )
            messages = [MessageResponse(**msg) for msg in messages_data]
        
        return ConversationWithMessagesResponse(
            conversation=ConversationResponse(**conversation),
            messages=messages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str = Path(..., description="Conversation ID"),
    request: UpdateConversationRequest = None
):
    """Update conversation metadata"""
    try:
        updates = {}
        if request.title is not None:
            updates["title"] = request.title
        if request.context is not None:
            updates["context"] = request.context
        if request.metadata is not None:
            updates["metadata"] = request.metadata
        
        conversation = await conversation_service.update_conversation(
            conversation_id=conversation_id,
            updates=updates
        )
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return ConversationResponse(**conversation)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{conversation_id}/archive")
async def archive_conversation(
    conversation_id: str = Path(..., description="Conversation ID")
):
    """Archive a conversation"""
    try:
        success = await conversation_service.archive_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"message": "Conversation archived successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str = Path(..., description="Conversation ID")
):
    """Delete a conversation"""
    try:
        success = await conversation_service.delete_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"message": "Conversation deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=Dict[str, Any])
async def search_conversations(
    user_id: str = Query(..., description="User ID"),
    organization_id: str = Query(..., description="Organization ID"),
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results")
):
    """Search user's conversations"""
    try:
        results = await conversation_service.search_conversations(
            user_id=user_id,
            organization_id=organization_id,
            query=query,
            limit=limit
        )
        
        return {
            "conversations": [ConversationResponse(**conv) for conv in results],
            "query": query,
            "total": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics", response_model=Dict[str, Any])
async def get_conversation_analytics(
    user_id: str = Query(..., description="User ID"),
    organization_id: str = Query(..., description="Organization ID"),
    conversation_id: Optional[str] = Query(None, description="Specific conversation ID"),
    days: int = Query(30, ge=1, le=365, description="Analytics period in days")
):
    """Get conversation analytics"""
    try:
        analytics = await conversation_service.get_conversation_analytics(
            user_id=user_id,
            organization_id=organization_id,
            conversation_id=conversation_id,
            days=days
        )
        
        return analytics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str = Path(..., description="Conversation ID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Messages per page")
):
    """Get messages for a specific conversation"""
    try:
        messages = await conversation_service.get_conversation_messages(
            conversation_id=conversation_id,
            page=page,
            limit=limit
        )
        
        return [MessageResponse(**msg) for msg in messages]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
