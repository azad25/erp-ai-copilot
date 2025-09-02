"""
Reasoning API endpoint for AI Copilot step-by-step reasoning
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import time
import structlog

from app.database.connection import get_db_session
from app.services.auth_service import get_current_user
from app.services.enhanced_chat_service import enhanced_chat_service
from app.models.api import User
from app.models.chat import ReasoningRequest, ReasoningResponse, ReasoningStep
from app.core.metrics import CHAT_REQUESTS, CHAT_RESPONSES, CHAT_ERRORS

logger = structlog.get_logger(__name__)

router = APIRouter()

@router.post("/", response_model=ReasoningResponse)
async def reasoning(
    request: ReasoningRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Generate step-by-step reasoning for a message."""
    start_time = time.time()
    
    try:
        agent_type = getattr(request, 'agent_type', 'reasoning')
        model = getattr(request, 'model', 'gemini2.0:flash')
        CHAT_REQUESTS.labels(agent_type=agent_type, model=model).inc()
        
        # Initialize enhanced chat service
        await enhanced_chat_service.initialize()
        
        # Process message with reasoning
        reasoning_steps = await enhanced_chat_service.process_message_with_reasoning(
            conversation_id=request.conversation_id,
            message=request.message,
            user_id=str(current_user.id),
            metadata=request.metadata or {}
        )
        
        # Record metrics
        response_time = time.time() - start_time
        try:
            CHAT_RESPONSES.observe(response_time)
        except Exception as metric_error:
            logger.warning(f"Failed to record metrics: {metric_error}")
        
        logger.info(
            "Reasoning response generated",
            conversation_id=request.conversation_id,
            user_id=str(current_user.id),
            response_time=response_time,
            steps_count=len(reasoning_steps)
        )
        
        return ReasoningResponse(
            conversation_id=request.conversation_id,
            reasoning_steps=reasoning_steps,
            total_steps=len(reasoning_steps),
            processing_time=response_time,
            metadata={
                "user_id": str(current_user.id),
                "agent_type": agent_type,
                "model": model,
                "timestamp": time.time()
            }
        )
        
    except Exception as e:
        agent_type = getattr(request, 'agent_type', 'reasoning')
        CHAT_ERRORS.labels(agent_type=agent_type, error_type="reasoning_error").inc()
        logger.error(
            "Reasoning error",
            conversation_id=request.conversation_id,
            user_id=str(current_user.id),
            error=str(e),
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Failed to generate reasoning: {str(e)}")
