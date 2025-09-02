"""
API Models for AI Copilot Service

Common Pydantic models used across API routes for request/response validation.
"""

from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class StandardResponse(BaseModel):
    """Standard API response format"""
    success: bool = Field(description="Whether the operation was successful")
    message: str = Field(description="Human-readable message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class ErrorResponse(BaseModel):
    """Error response format"""
    success: bool = Field(default=False)
    error: str = Field(description="Error message")
    error_code: Optional[str] = Field(default=None, description="Error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel):
    """Paginated response format"""
    success: bool = Field(default=True)
    data: List[Dict[str, Any]] = Field(description="Response data items")
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    per_page: int = Field(description="Items per page")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there are more pages")
    has_prev: bool = Field(description="Whether there are previous pages")


class JobStatus(str, Enum):
    """Background job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    """Background job priority enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class BackgroundJobResponse(BaseModel):
    """Background job response format"""
    job_id: str = Field(description="Unique job identifier")
    status: JobStatus = Field(description="Current job status")
    priority: JobPriority = Field(description="Job priority")
    created_at: datetime = Field(description="Job creation timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Job completion timestamp")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Job result data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    progress: int = Field(default=0, description="Job progress percentage")


class ConversationMessage(BaseModel):
    """Conversation message model"""
    id: str = Field(description="Message ID")
    conversation_id: str = Field(description="Conversation ID")
    user_id: str = Field(description="User ID")
    content: str = Field(description="Message content")
    role: str = Field(description="Message role (user/assistant)")
    timestamp: datetime = Field(description="Message timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class ReasoningStep(BaseModel):
    """Reasoning step model for WebSocket streaming"""
    step_id: str = Field(description="Step identifier")
    type: str = Field(description="Step type")
    content: str = Field(description="Step content")
    icon: str = Field(description="Step icon")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class MemoryEntry(BaseModel):
    """Memory entry model"""
    id: str = Field(description="Memory entry ID")
    user_id: str = Field(description="User ID")
    conversation_id: Optional[str] = Field(default=None, description="Associated conversation ID")
    content: str = Field(description="Memory content")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Memory context")
    importance: int = Field(default=1, description="Memory importance (1-10)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SystemCommandRequest(BaseModel):
    """System command execution request"""
    command: str = Field(description="Command to execute")
    args: Optional[List[str]] = Field(default=None, description="Command arguments")
    working_directory: Optional[str] = Field(default=None, description="Working directory")
    timeout: int = Field(default=30, description="Command timeout in seconds")
    user_role: str = Field(description="User role for RBAC validation")


class SystemCommandResponse(BaseModel):
    """System command execution response"""
    success: bool = Field(description="Whether command executed successfully")
    exit_code: int = Field(description="Command exit code")
    stdout: str = Field(description="Standard output")
    stderr: str = Field(description="Standard error")
    execution_time: float = Field(description="Execution time in seconds")
    command: str = Field(description="Executed command")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ThirdPartyAPIRequest(BaseModel):
    """Third-party API request model"""
    provider: str = Field(description="API provider name")
    endpoint: str = Field(description="API endpoint")
    method: str = Field(default="GET", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Request headers")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Request body data")
    user_id: str = Field(description="User ID for rate limiting")


class ThirdPartyAPIResponse(BaseModel):
    """Third-party API response model"""
    success: bool = Field(description="Whether request was successful")
    status_code: int = Field(description="HTTP status code")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")
    error: Optional[str] = Field(default=None, description="Error message")
    rate_limit_remaining: Optional[int] = Field(default=None, description="Remaining rate limit")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
