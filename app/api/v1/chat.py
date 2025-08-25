"""
Chat API endpoints for the AI Copilot service.
"""
import uuid
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import structlog

from app.database.connection import get_db_session
from app.database.models.database import Conversation, Message, User
from app.models.api import (
    ChatRequest, ChatResponse, ChatStreamResponse,
    CreateConversationRequest, UpdateConversationRequest,
    ConversationListResponse, ConversationResponse, MessageResponse
)
from app.services.chat_service import ChatService
from app.services.auth_service import get_current_user
from app.core.metrics import CHAT_REQUESTS, CHAT_RESPONSES, CHAT_ERRORS

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Send a chat message and get a response."""
    start_time = time.time()
    
    try:
        CHAT_REQUESTS.inc()
        
        # Get or create conversation
        conversation_id = request.conversation_id
        if not conversation_id:
            # Create new conversation
            conversation = Conversation(
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                title=request.message[:100] + "..." if len(request.message) > 100 else request.message,
                context=request.context,
                metadata={"source": "api", "agent_type": request.agent_type}
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)
            conversation_id = conversation.id
        else:
            # Verify conversation belongs to user
            conversation = await db.execute(
                select(Conversation).where(
                    and_(
                        Conversation.id == conversation_id,
                        Conversation.user_id == current_user.id,
                        Conversation.organization_id == current_user.organization_id
                    )
                )
            )
            conversation = conversation.scalar_one_or_none()
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Save user message
        user_message = Message(
            conversation_id=conversation_id,
            user_id=current_user.id,
            role="user",
            content=request.message,
            metadata={
                "agent_type": request.agent_type,
                "model": request.model,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens
            }
        )
        db.add(user_message)
        await db.commit()
        await db.refresh(user_message)
        
        # Get AI response
        chat_service = ChatService(db, current_user)
        response = await chat_service.generate_response(
            conversation_id=conversation_id,
            user_message=request.message,
            agent_type=request.agent_type,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            context=request.context
        )
        
        # Save AI response
        ai_message = Message(
            conversation_id=conversation_id,
            user_id=None,
            role="assistant",
            content=response["content"],
            metadata={
                "agent_type": response.get("agent_type"),
                "model_used": response.get("model_used"),
                "tokens_used": response.get("tokens_used"),
                "execution_time_ms": response.get("execution_time_ms")
            }
        )
        db.add(ai_message)
        await db.commit()
        await db.refresh(ai_message)
        
        # Update conversation title if it's the first message
        if not conversation.title or conversation.title.startswith("..."):
            conversation.title = request.message[:100] + "..." if len(request.message) > 100 else request.message
            await db.commit()
        
        # Record metrics
        response_time = time.time() - start_time
        CHAT_RESPONSES.observe(response_time)
        
        logger.info(
            "Chat response generated",
            conversation_id=str(conversation_id),
            user_id=str(current_user.id),
            response_time=response_time,
            tokens_used=response.get("tokens_used", 0)
        )
        
        return ChatResponse(
            message_id=ai_message.id,
            conversation_id=conversation_id,
            content=response["content"],
            agent_type=response.get("agent_type"),
            model_used=response.get("model_used"),
            tokens_used=response.get("tokens_used", 0),
            metadata=response.get("metadata", {}),
            created_at=ai_message.created_at
        )
        
    except Exception as e:
        CHAT_ERRORS.inc()
        logger.error(
            "Chat error",
            conversation_id=str(conversation_id) if 'conversation_id' in locals() else None,
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")


@router.post("/stream", response_model=ChatStreamResponse)
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Send a chat message and get a streaming response."""
    start_time = time.time()
    
    try:
        CHAT_REQUESTS.inc()
        
        # Get or create conversation
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation = Conversation(
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                title=request.message[:100] + "..." if len(request.message) > 100 else request.message,
                context=request.context,
                metadata={"source": "api", "agent_type": request.agent_type}
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)
            conversation_id = conversation.id
        else:
            conversation = await db.execute(
                select(Conversation).where(
                    and_(
                        Conversation.id == conversation_id,
                        Conversation.user_id == current_user.id,
                        Conversation.organization_id == current_user.organization_id
                    )
                )
            )
            conversation = conversation.scalar_one_or_none()
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Save user message
        user_message = Message(
            conversation_id=conversation_id,
            user_id=current_user.id,
            role="user",
            content=request.message,
            metadata={
                "agent_type": request.agent_type,
                "model": request.model,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens
            }
        )
        db.add(user_message)
        await db.commit()
        await db.refresh(user_message)
        
        # Generate streaming response
        chat_service = ChatService(db, current_user)
        
        async def generate_stream():
            message_id = uuid.uuid4()
            content_buffer = ""
            chunk_index = 0
            
            try:
                async for chunk in chat_service.generate_streaming_response(
                    conversation_id=conversation_id,
                    user_message=request.message,
                    agent_type=request.agent_type,
                    model=request.model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    context=request.context
                ):
                    content_buffer += chunk
                    chunk_index += 1
                    
                    yield ChatStreamResponse(
                        message_id=message_id,
                        conversation_id=conversation_id,
                        content=chunk,
                        agent_type=request.agent_type,
                        chunk_index=chunk_index,
                        is_complete=False
                    ).model_dump_json() + "\n"
                
                # Save complete AI response
                ai_message = Message(
                    conversation_id=conversation_id,
                    user_id=None,
                    role="assistant",
                    content=content_buffer,
                    metadata={
                        "agent_type": request.agent_type,
                        "model": request.model,
                        "chunks": chunk_index,
                        "streaming": True
                    }
                )
                db.add(ai_message)
                await db.commit()
                
                # Send final chunk
                yield ChatStreamResponse(
                    message_id=message_id,
                    conversation_id=conversation_id,
                    content="",
                    agent_type=request.agent_type,
                    chunk_index=chunk_index,
                    total_chunks=chunk_index,
                    is_complete=True
                ).model_dump_json() + "\n"
                
            except Exception as e:
                logger.error("Streaming error", error=str(e))
                yield ChatStreamResponse(
                    message_id=message_id,
                    conversation_id=conversation_id,
                    content="Error occurred during streaming",
                    agent_type=request.agent_type,
                    chunk_index=chunk_index,
                    is_complete=True
                ).model_dump_json() + "\n"
        
        # Update conversation title if needed
        if not conversation.title or conversation.title.startswith("..."):
            conversation.title = request.message[:100] + "..." if len(request.message) > 100 else request.message
            await db.commit()
        
        return StreamingResponse(
            generate_stream(),
            media_type="application/x-ndjson",
            headers={
                "X-Conversation-Id": str(conversation_id),
                "X-Message-Id": str(user_message.id)
            }
        )
        
    except Exception as e:
        CHAT_ERRORS.inc()
        logger.error("Chat stream error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate streaming response: {str(e)}")


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new conversation."""
    try:
        conversation = Conversation(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            title=request.title,
            context=request.context,
            metadata=request.metadata
        )
        
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        
        logger.info("Conversation created", conversation_id=str(conversation.id), user_id=str(current_user.id))
        
        return ConversationResponse.from_orm(conversation)
        
    except Exception as e:
        logger.error("Failed to create conversation", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List user's conversations."""
    try:
        # Build query
        query = select(Conversation).where(
            and_(
                Conversation.user_id == current_user.id,
                Conversation.organization_id == current_user.organization_id
            )
        )
        
        if status:
            query = query.where(Conversation.status == status)
        
        # Get total count
        count_query = select(Conversation).where(
            and_(
                Conversation.user_id == current_user.id,
                Conversation.organization_id == current_user.organization_id
            )
        )
        if status:
            count_query = count_query.where(Conversation.status == status)
        
        total_result = await db.execute(count_query)
        total = len(total_result.scalars().all())
        
        # Get paginated results
        query = query.order_by(Conversation.updated_at.desc()).offset((page - 1) * size).limit(size)
        result = await db.execute(query)
        conversations = result.scalars().all()
        
        # Convert to response format
        conversation_data = []
        for conv in conversations:
            # Get message count
            message_count = await db.execute(
                select(Message).where(Message.conversation_id == conv.id)
            )
            message_count = len(message_count.scalars().all())
            
            conversation_data.append({
                "id": conv.id,
                "title": conv.title,
                "status": conv.status,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
                "message_count": message_count
            })
        
        return ConversationListResponse(
            conversations=conversation_data,
            total=total,
            page=page,
            size=size,
            has_next=page * size < total,
            has_previous=page > 1
        )
        
    except Exception as e:
        logger.error("Failed to list conversations", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get a specific conversation."""
    try:
        result = await db.execute(
            select(Conversation).where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == current_user.id,
                    Conversation.organization_id == current_user.organization_id
                )
            )
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return ConversationResponse.from_orm(conversation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get conversation", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get conversation: {str(e)}")


@router.put("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    request: UpdateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update a conversation."""
    try:
        result = await db.execute(
            select(Conversation).where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == current_user.id,
                    Conversation.organization_id == current_user.organization_id
                )
            )
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Update fields
        if request.title is not None:
            conversation.title = request.title
        if request.context is not None:
            conversation.context = request.context
        if request.metadata is not None:
            conversation.metadata = request.metadata
        if request.status is not None:
            conversation.status = request.status
        
        await db.commit()
        await db.refresh(conversation)
        
        logger.info("Conversation updated", conversation_id=str(conversation_id), user_id=str(current_user.id))
        
        return ConversationResponse.from_orm(conversation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update conversation", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update conversation: {str(e)}")


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a conversation."""
    try:
        result = await db.execute(
            select(Conversation).where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == current_user.id,
                    Conversation.organization_id == current_user.organization_id
                )
            )
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Soft delete by changing status
        conversation.status = "deleted"
        await db.commit()
        
        logger.info("Conversation deleted", conversation_id=str(conversation_id), user_id=str(current_user.id))
        
        return {"message": "Conversation deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete conversation", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get messages from a conversation."""
    try:
        # Verify conversation belongs to user
        conversation_result = await db.execute(
            select(Conversation).where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.user_id == current_user.id,
                    Conversation.organization_id == current_user.organization_id
                )
            )
        )
        conversation = conversation_result.scalar_one_or_none()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get messages
        query = select(Message).where(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).offset((page - 1) * size).limit(size)
        
        result = await db.execute(query)
        messages = result.scalars().all()
        
        return [MessageResponse.from_orm(msg) for msg in messages]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get conversation messages", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get conversation messages: {str(e)}")
