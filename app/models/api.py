"""
API request and response models for the AI Copilot service.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from uuid import UUID
from pydantic import BaseModel, Field, validator
from enum import Enum


class MessageRole(str, Enum):
    """Message role enumeration."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AgentType(str, Enum):
    """Agent type enumeration."""
    QUERY = "query"
    ACTION = "action"
    ANALYTICS = "analytics"
    SCHEDULER = "scheduler"
    COMPLIANCE = "compliance"
    HELP = "help"


class ActionType(str, Enum):
    """Action type enumeration."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    ANALYZE = "analyze"
    SCHEDULE = "schedule"
    VALIDATE = "validate"


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConversationStatus(str, Enum):
    """Conversation status enumeration."""
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    DELETED = "deleted"


# Chat API Models
class ChatMessage(BaseModel):
    """Chat message model."""
    
    role: MessageRole
    content: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """Chat request model."""
    
    message: str
    conversation_id: Optional[UUID] = None
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    agent_type: Optional[AgentType] = None
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=4000, ge=1, le=8000)
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    """Chat response model."""
    
    message_id: UUID
    conversation_id: UUID
    content: str
    role: MessageRole = MessageRole.ASSISTANT
    agent_type: Optional[AgentType] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ChatStreamResponse(BaseModel):
    """Chat stream response model."""
    
    message_id: UUID
    conversation_id: UUID
    content: str
    role: MessageRole = MessageRole.ASSISTANT
    agent_type: Optional[AgentType] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    is_complete: bool = False
    chunk_index: int = 0
    total_chunks: Optional[int] = None


# Conversation API Models
class CreateConversationRequest(BaseModel):
    """Create conversation request model."""
    
    title: Optional[str] = None
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateConversationRequest(BaseModel):
    """Update conversation request model."""
    
    title: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    status: Optional[ConversationStatus] = None


class ConversationListResponse(BaseModel):
    """Conversation list response model."""
    
    conversations: List[Dict[str, Any]]
    total: int
    page: int
    size: int
    has_next: bool
    has_previous: bool


# Agent API Models
class AgentExecutionRequest(BaseModel):
    """Agent execution request model."""
    
    agent_type: AgentType
    action_type: ActionType
    input_data: Dict[str, Any] = Field(default_factory=dict)
    conversation_id: Optional[UUID] = None
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    timeout_seconds: Optional[int] = Field(default=60, ge=1, le=300)


class AgentExecutionResponse(BaseModel):
    """Agent execution response model."""
    
    execution_id: UUID
    agent_type: AgentType
    action_type: ActionType
    status: TaskStatus
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# Knowledge Base API Models
class CreateKnowledgeRequest(BaseModel):
    """Create knowledge base request model."""
    
    document_type: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    access_level: str = Field(default="all", regex="^(all|hr_only|manager_only|admin_only)$")
    version: str = Field(default="1.0", regex="^\\d+\\.\\d+$")


class UpdateKnowledgeRequest(BaseModel):
    """Update knowledge base request model."""
    
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    metadata: Optional[Dict[str, Any]] = None
    access_level: Optional[str] = Field(None, regex="^(all|hr_only|manager_only|admin_only)$")
    version: Optional[str] = Field(None, regex="^\\d+\\.\\d+$")


class KnowledgeSearchRequest(BaseModel):
    """Knowledge base search request model."""
    
    query: str = Field(..., min_length=1)
    document_type: Optional[str] = None
    access_level: Optional[str] = None
    max_results: Optional[int] = Field(default=10, ge=1, le=100)
    similarity_threshold: Optional[float] = Field(default=0.75, ge=0.0, le=1.0)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    """Knowledge base search response model."""
    
    results: List[Dict[str, Any]]
    total: int
    query: str
    search_time_ms: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Scheduled Task API Models
class CreateScheduledTaskRequest(BaseModel):
    """Create scheduled task request model."""
    
    task_type: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    cron_expression: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('cron_expression')
    def validate_cron_expression(cls, v):
        """Validate cron expression format."""
        if v is not None:
            # Basic cron validation (5 or 6 fields)
            parts = v.split()
            if len(parts) not in [5, 6]:
                raise ValueError("Cron expression must have 5 or 6 fields")
        return v


class UpdateScheduledTaskRequest(BaseModel):
    """Update scheduled task request model."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    cron_expression: Optional[str] = None
    status: Optional[TaskStatus] = None
    config: Optional[Dict[str, Any]] = None


class ScheduledTaskResponse(BaseModel):
    """Scheduled task response model."""
    
    id: UUID
    organization_id: UUID
    user_id: UUID
    task_type: str
    name: str
    description: Optional[str] = None
    cron_expression: Optional[str] = None
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    status: TaskStatus
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


# RAG API Models
class RAGQueryRequest(BaseModel):
    """RAG query request model."""
    
    query: str = Field(..., min_length=1)
    collection_name: Optional[str] = None
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    max_results: Optional[int] = Field(default=10, ge=1, le=50)
    similarity_threshold: Optional[float] = Field(default=0.75, ge=0.0, le=1.0)
    include_metadata: Optional[bool] = True
    use_hybrid_search: Optional[bool] = True


class RAGQueryResponse(BaseModel):
    """RAG query response model."""
    
    query: str
    results: List[Dict[str, Any]]
    total_results: int
    search_time_ms: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGDocumentRequest(BaseModel):
    """RAG document ingestion request model."""
    
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    document_type: str = Field(..., min_length=1, max_length=50)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    access_level: str = Field(default="all", regex="^(all|hr_only|manager_only|admin_only)$")
    version: str = Field(default="1.0", regex="^\\d+\\.\\d+$")
    chunk_size: Optional[int] = Field(default=1000, ge=100, le=5000)
    chunk_overlap: Optional[int] = Field(default=200, ge=0, le=1000)


class RAGDocumentResponse(BaseModel):
    """RAG document ingestion response model."""
    
    document_id: UUID
    chunks_created: int
    embedding_model: str
    vector_ids: List[str]
    processing_time_ms: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


# WebSocket Models
class WebSocketMessage(BaseModel):
    """WebSocket message model."""
    
    type: str = Field(..., description="Message type")
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message_id: Optional[str] = None


class WebSocketChatMessage(WebSocketMessage):
    """WebSocket chat message model."""
    
    type: str = Field(default="chat_message")
    conversation_id: UUID
    message: str
    user_id: Optional[UUID] = None


class WebSocketChatResponse(WebSocketMessage):
    """WebSocket chat response model."""
    
    type: str = Field(default="chat_response")
    conversation_id: UUID
    message_id: UUID
    content: str
    agent_type: Optional[AgentType] = None
    is_complete: bool = False
    chunk_index: int = 0
    total_chunks: Optional[int] = None


class WebSocketStatusMessage(WebSocketMessage):
    """WebSocket status message model."""
    
    type: str = Field(default="status")
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None


# Error Models
class ErrorResponse(BaseModel):
    """Error response model."""
    
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None


class ValidationError(BaseModel):
    """Validation error model."""
    
    field: str
    message: str
    value: Optional[Any] = None


class ValidationErrorResponse(BaseModel):
    """Validation error response model."""
    
    error: str = "validation_error"
    message: str = "Validation failed"
    details: List[ValidationError]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None


# Health Check Models
class HealthCheckResponse(BaseModel):
    """Health check response model."""
    
    status: str
    timestamp: datetime
    version: str
    environment: str
    services: Dict[str, Dict[str, Any]]
    uptime_seconds: float


# Analytics Models
class ConversationAnalyticsRequest(BaseModel):
    """Conversation analytics request model."""
    
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    user_id: Optional[UUID] = None
    agent_type: Optional[AgentType] = None
    group_by: Optional[str] = Field(default="day", regex="^(hour|day|week|month)$")


class ConversationAnalyticsResponse(BaseModel):
    """Conversation analytics response model."""
    
    period: str
    data: List[Dict[str, Any]]
    summary: Dict[str, Any]
    generated_at: datetime


# Bulk Operations
class BulkOperationRequest(BaseModel):
    """Bulk operation request model."""
    
    operation: str = Field(..., regex="^(create|update|delete|query)$")
    items: List[Dict[str, Any]] = Field(..., min_items=1, max_items=1000)
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)


class BulkOperationResponse(BaseModel):
    """Bulk operation response model."""
    
    operation: str
    total_items: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]
    processing_time_ms: float
    errors: List[Dict[str, Any]] = Field(default_factory=list)


# Search and Filter Models
class SearchFilter(BaseModel):
    """Search filter model."""
    
    field: str
    operator: str = Field(..., regex="^(eq|ne|gt|gte|lt|lte|in|nin|contains|regex)$")
    value: Any
    case_sensitive: bool = False


class SortOrder(str, Enum):
    """Sort order enumeration."""
    ASC = "asc"
    DESC = "desc"


class SearchRequest(BaseModel):
    """Generic search request model."""
    
    query: Optional[str] = None
    filters: List[SearchFilter] = Field(default_factory=list)
    sort_by: Optional[str] = None
    sort_order: SortOrder = SortOrder.DESC
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    include_total: bool = True


class SearchResponse(BaseModel):
    """Generic search response model."""
    
    results: List[Dict[str, Any]]
    total: Optional[int] = None
    page: int
    size: int
    has_next: bool
    has_previous: bool
    search_time_ms: float
    query: Optional[str] = None
    filters_applied: List[SearchFilter] = Field(default_factory=list)


# Infrastructure Models
class InfrastructureCommandRequest(BaseModel):
    """Request model for infrastructure command execution."""
    command: str = Field(..., description="Command to execute")
    command_type: str = Field(..., description="Type of command (system, docker, database, network, monitoring)")
    execution_level: str = Field(default="user", description="Execution privilege level (user, elevated, root, container)")
    timeout: Optional[int] = Field(None, ge=1, le=3600, description="Command timeout in seconds")
    working_dir: Optional[str] = Field(None, description="Working directory for command execution")
    environment: Optional[Dict[str, str]] = Field(None, description="Environment variables for command execution")


class InfrastructureCommandResponse(BaseModel):
    """Response model for infrastructure command execution."""
    success: bool
    data: Dict[str, Any]
    message: str


class SystemOverviewResponse(BaseModel):
    """Response model for system overview."""
    success: bool
    data: Dict[str, Any]
    message: str


class SystemMetricsResponse(BaseModel):
    """Response model for system metrics."""
    success: bool
    data: Dict[str, Any]
    message: str


class ContainerLogsResponse(BaseModel):
    """Response model for container logs."""
    success: bool
    data: Dict[str, Any]
    message: str


class ContainerActionResponse(BaseModel):
    """Response model for container actions."""
    success: bool
    data: Dict[str, Any]
    message: str
