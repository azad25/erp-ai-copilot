"""
Chat-specific models for reasoning and enhanced chat functionality.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum

from .api import MessageRole, AgentType


class ReasoningStepType(str, Enum):
    """Reasoning step type enumeration."""
    THINKING = "thinking"
    MEMORY_CHECK = "memory_check"
    VECTOR_SEARCH = "vector_search"
    API_CALL = "api_call"
    DATA_ANALYSIS = "data_analysis"
    COMPLETION = "completion"


class ReasoningStep(BaseModel):
    """Individual reasoning step model."""
    
    step_number: int
    step_type: ReasoningStepType
    title: str
    description: str
    content: str
    icon: str
    source: Optional[str] = None
    data_source: Optional[str] = None  # Deprecated, use 'source'
    status: str = "processing"  # processing, completed, failed
    processing_time: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReasoningRequest(BaseModel):
    """Reasoning request model."""
    
    message: str
    conversation_id: Optional[str] = None
    agent_type: Optional[AgentType] = None
    model: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ReasoningResponse(BaseModel):
    """Reasoning response model."""
    
    conversation_id: str
    reasoning_steps: List[ReasoningStep]
    total_steps: int
    processing_time: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
