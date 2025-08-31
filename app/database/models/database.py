"""Database models for AI Copilot service."""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(BaseModel):
    """User model for authentication."""
    id: str
    email: str
    organization_id: Optional[str] = None
    is_active: bool = True
    is_verified: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Conversation(BaseModel):
    """Conversation model for chat sessions."""
    id: str
    user_id: str
    organization_id: str
    title: str
    context: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Message(BaseModel):
    """Message model for chat messages."""
    id: str
    conversation_id: str
    user_id: Optional[str] = None
    role: str  # "user", "assistant", "system"
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# SQLAlchemy table definitions (if needed)
class ConversationTable(Base):
    """SQLAlchemy table for conversations."""
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), nullable=False)  # No FK constraint - references auth service
    organization_id = Column(UUID(as_uuid=True), nullable=False)  # No FK constraint - references auth service
    title = Column(String, nullable=False)
    context = Column(JSON, default={})
    meta_data = Column("metadata_json", JSON, default={})
    status = Column(String, default='active')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MessageTable(Base):
    """SQLAlchemy table for messages."""
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    conversation_id = Column(UUID(as_uuid=True), nullable=False)  # References local conversations table
    user_id = Column(UUID(as_uuid=True), nullable=True)  # No FK constraint - references auth service
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    meta_data = Column("metadata_json", JSON, default={})  # Map to 'metadata' column in DB
    tokens_used = Column(Integer, default=0)
    model_used = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
