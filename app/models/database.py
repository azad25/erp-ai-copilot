"""
Database models for the AI Copilot service.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from pydantic import BaseModel, Field

Base = declarative_base()


# Organization data comes from auth service via gRPC - no local table needed


# User data comes from auth service via gRPC - no local table needed


class Conversation(Base):
    """Conversation model - no foreign keys to users/orgs."""
    
    __tablename__ = "conversations"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)  # References auth service
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)  # References auth service
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    context: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships (only to local tables)
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    agent_executions: Mapped[List["AgentExecution"]] = relationship("AgentExecution", back_populates="conversation", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_conversations_org_user', 'organization_id', 'user_id'),
        Index('idx_conversations_created_at', 'created_at'),
        Index('idx_conversations_status', 'status'),
    )


class Message(Base):
    """Message model - no foreign keys to users."""
    
    __tablename__ = "messages"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)  # References auth service
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships (only to local tables)
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    
    # Indexes
    __table_args__ = (
        Index('idx_messages_conversation_id', 'conversation_id'),
        Index('idx_messages_created_at', 'created_at'),
        Index('idx_messages_role', 'role'),
    )


class AgentExecution(Base):
    """Agent execution model - no foreign keys to users."""
    
    __tablename__ = "agent_executions"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)  # References auth service
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    input_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    output_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships (only to local tables)
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="agent_executions")
    
    # Indexes
    __table_args__ = (
        Index('idx_agent_executions_conversation_id', 'conversation_id'),
        Index('idx_agent_executions_user_id', 'user_id'),
        Index('idx_agent_executions_agent_type', 'agent_type'),
        Index('idx_agent_executions_status', 'status'),
    )


class KnowledgeBase(Base):
    """Knowledge base model - no foreign keys to orgs."""
    
    __tablename__ = "knowledge_base"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)  # References auth service
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    embedding_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vector_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    access_level: Mapped[str] = mapped_column(String(50), default="all")
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_knowledge_base_org_type', 'organization_id', 'document_type'),
        Index('idx_knowledge_base_title', 'title'),
        Index('idx_knowledge_base_access_level', 'access_level'),
    )


class ScheduledTask(Base):
    """Scheduled task model - no foreign keys to users/orgs."""
    
    __tablename__ = "scheduled_tasks"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)  # References auth service
    user_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)  # References auth service
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cron_expression: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    config: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_scheduled_tasks_org_status', 'organization_id', 'status'),
        Index('idx_scheduled_tasks_next_run', 'next_run_at'),
        Index('idx_scheduled_tasks_task_type', 'task_type'),
    )


class AuditLog(Base):
    """Audit log model - no foreign keys to users/orgs."""
    
    __tablename__ = "audit_logs"
    
    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)  # References auth service
    user_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)  # References auth service
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[UUID]] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    details: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 compatible
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_logs_org_action', 'organization_id', 'action'),
        Index('idx_audit_logs_created_at', 'created_at'),
        Index('idx_audit_logs_resource_type', 'resource_type'),
    )


# Pydantic models for API responses
# Organization response models removed - data comes from auth service


# User response models removed - data comes from auth service


class ConversationResponse(BaseModel):
    """Conversation response model."""
    
    id: UUID
    organization_id: UUID
    user_id: UUID
    title: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Message response model."""
    
    id: UUID
    conversation_id: UUID
    user_id: Optional[UUID] = None
    role: str
    content: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    tokens_used: int = 0
    model_used: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class AgentExecutionResponse(BaseModel):
    """Agent execution response model."""
    
    id: UUID
    conversation_id: UUID
    user_id: UUID
    agent_type: str
    action_type: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    status: str
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class KnowledgeBaseResponse(BaseModel):
    """Knowledge base response model."""
    
    id: UUID
    organization_id: UUID
    document_type: str
    title: str
    content: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    embedding_id: Optional[str] = None
    vector_id: Optional[str] = None
    access_level: str
    version: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


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
    status: str
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Audit log response model."""
    
    id: UUID
    organization_id: UUID
    user_id: Optional[UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[UUID] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
