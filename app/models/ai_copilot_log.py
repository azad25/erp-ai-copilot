"""
AI Copilot Audit Log Models

MongoDB models for logging all AI Copilot interactions.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId

from app.models.mongodb_models import PyObjectId


class AIToolUsage(BaseModel):
    """Tool usage information"""
    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    execution_time_ms: Optional[int] = None
    success: bool = True


class AIErrorLog(BaseModel):
    """Error information"""
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AICopilotLogMongo(BaseModel):
    """MongoDB AI Copilot Log model"""
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    log_id: str = Field(default_factory=lambda: str(uuid4()))
    
    # User and Organization
    user_id: str
    organization_id: str
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    
    # Request Information
    prompt: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Response Information
    response: str
    
    # Token Usage
    prompt_tokens: Optional[int] = None  # Tokens in user prompt
    response_tokens: Optional[int] = None  # Tokens in AI response
    total_tokens: Optional[int] = None  # Total tokens used
    embedding_tokens: Optional[int] = None  # Tokens used for embeddings (RAG)
    
    # Tool Usage
    tools_used: List[AIToolUsage] = Field(default_factory=list)
    
    # Errors
    errors: List[AIErrorLog] = Field(default_factory=list)
    
    # Status
    status: bool  # True = success, False = failed
    status_message: Optional[str] = None
    
    # Performance Metrics
    total_execution_time_ms: Optional[int] = None
    llm_model_used: Optional[str] = None
    
    # Metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_source: Optional[str] = None  # web, mobile, api
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()}
    )


class AICopilotLogResponse(BaseModel):
    """Response model for AI Copilot logs"""
    
    log_id: str
    user_id: str
    organization_id: str
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    prompt: str
    response: str
    
    # Token usage
    prompt_tokens: Optional[int] = None
    response_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    embedding_tokens: Optional[int] = None
    
    tools_used: List[AIToolUsage]
    errors: List[AIErrorLog]
    status: bool
    status_message: Optional[str] = None
    total_execution_time_ms: Optional[int] = None
    llm_model_used: Optional[str] = None
    created_at: datetime


class AICopilotLogQuery(BaseModel):
    """Query parameters for AI Copilot logs"""
    
    organization_id: Optional[str] = None
    user_id: Optional[str] = None
    status: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search_prompt: Optional[str] = None
    search_response: Optional[str] = None
    tool_name: Optional[str] = None
    limit: int = 50
    skip: int = 0


class AICopilotLogStats(BaseModel):
    """Statistics for AI Copilot logs"""
    
    total_queries: int
    successful_queries: int
    failed_queries: int
    total_tools_used: int
    total_errors: int
    avg_execution_time_ms: Optional[float] = None
    
    # Token statistics
    total_tokens_used: Optional[int] = None
    total_prompt_tokens: Optional[int] = None
    total_response_tokens: Optional[int] = None
    total_embedding_tokens: Optional[int] = None
    avg_tokens_per_query: Optional[float] = None
    
    most_used_tools: List[Dict[str, Any]] = Field(default_factory=list)
    most_active_users: List[Dict[str, Any]] = Field(default_factory=list)
    most_used_models: List[Dict[str, Any]] = Field(default_factory=list)
