"""
AI Interaction Logger

Wrapper to automatically log all AI Copilot interactions.
"""

import logging
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from app.services.ai_copilot_logging_service import ai_copilot_logging_service
from app.models.ai_copilot_log import AIToolUsage, AIErrorLog
from app.core.user_context import get_current_user_id, get_current_organization_id, get_current_user_role

logger = logging.getLogger(__name__)


class AIInteractionLogger:
    """Logger for AI Copilot interactions"""
    
    def __init__(self):
        self.current_tools: List[AIToolUsage] = []
        self.current_errors: List[AIErrorLog] = []
        self.start_time: Optional[float] = None
        
    def start_interaction(self):
        """Start tracking an interaction"""
        self.current_tools = []
        self.current_errors = []
        self.start_time = time.time()
    
    def log_tool_usage(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        success: bool = True
    ):
        """Log a tool usage"""
        tool_usage = AIToolUsage(
            tool_name=tool_name,
            parameters=parameters,
            result=result[:500] if result else None,  # Truncate long results
            execution_time_ms=execution_time_ms,
            success=success
        )
        self.current_tools.append(tool_usage)
    
    def log_error(
        self,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None
    ):
        """Log an error"""
        error_log = AIErrorLog(
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace
        )
        self.current_errors.append(error_log)
    
    async def finish_interaction(
        self,
        prompt: str,
        response: str,
        status: bool,
        conversation_id: Optional[str] = None,
        llm_model_used: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        response_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        embedding_tokens: Optional[int] = None,
        status_message: Optional[str] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        user_role: Optional[str] = None
    ) -> str:
        """
        Finish interaction and log to MongoDB
        
        Returns:
            Log ID
        """
        # Calculate execution time
        execution_time_ms = None
        if self.start_time:
            execution_time_ms = int((time.time() - self.start_time) * 1000)
        
        # Get user context if not provided
        if not user_id:
            user_id = get_current_user_id() or "unknown"
        if not organization_id:
            organization_id = get_current_organization_id() or "default"
        if not user_role:
            user_role = get_current_user_role()
        
        try:
            log_id = await ai_copilot_logging_service.log_interaction(
                user_id=user_id,
                organization_id=organization_id,
                prompt=prompt,
                response=response,
                tools_used=self.current_tools,
                errors=self.current_errors,
                status=status,
                conversation_id=conversation_id,
                user_role=user_role,
                total_execution_time_ms=execution_time_ms,
                llm_model_used=llm_model_used,
                prompt_tokens=prompt_tokens,
                response_tokens=response_tokens,
                total_tokens=total_tokens,
                embedding_tokens=embedding_tokens,
                status_message=status_message
            )
            
            logger.info(f"Logged AI interaction: {log_id}")
            return log_id
            
        except Exception as e:
            logger.error(f"Failed to log AI interaction: {e}")
            return ""


@asynccontextmanager
async def log_ai_interaction(
    prompt: str,
    conversation_id: Optional[str] = None,
    llm_model: Optional[str] = None
):
    """
    Context manager for logging AI interactions
    
    Usage:
        async with log_ai_interaction(prompt="User query", conversation_id="conv_123") as logger:
            # Process AI request
            logger.log_tool_usage("search_docs", {"query": "..."})
            response = await process_query()
            
        # Automatically logs on exit
    """
    interaction_logger = AIInteractionLogger()
    interaction_logger.start_interaction()
    
    response = ""
    status = False
    status_message = None
    
    try:
        yield interaction_logger
        status = True
        
    except Exception as e:
        status = False
        status_message = f"Error: {str(e)}"
        interaction_logger.log_error(
            error_type=type(e).__name__,
            error_message=str(e),
            stack_trace=None
        )
        raise
        
    finally:
        # Log the interaction
        if hasattr(interaction_logger, '_response'):
            response = interaction_logger._response
        
        await interaction_logger.finish_interaction(
            prompt=prompt,
            response=response,
            status=status,
            conversation_id=conversation_id,
            llm_model_used=llm_model,
            status_message=status_message
        )


# Global instance
ai_interaction_logger = AIInteractionLogger()
