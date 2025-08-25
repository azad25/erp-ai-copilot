"""RAG Engine Data Models

This module defines the data models used by the RAG engine for document processing,
chunking, embedding, and retrieval operations.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, validator


class DocumentType(str, Enum):
    """Document type enumeration."""
    DOCUMENT = "document"
    POLICY = "policy"
    MANUAL = "manual"
    FAQ = "faq"
    KNOWLEDGE_BASE = "knowledge_base"


class AccessLevel(str, Enum):
    """Document access level enumeration."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class Document(BaseModel):
    """Document model for RAG processing."""
    id: Optional[str] = None
    title: str
    content: str
    document_type: Optional[str] = DocumentType.DOCUMENT
    metadata: Dict[str, Any] = Field(default_factory=dict)
    access_level: str = AccessLevel.INTERNAL
    version: Optional[str] = "1.0"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    
    @validator('created_at', 'updated_at', pre=True, always=True)
    def set_datetime(cls, v):
        return v or datetime.utcnow()


class DocumentChunk(BaseModel):
    """Document chunk model for vector storage."""
    document_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    document_type: Optional[str] = None
    chunk_index: int = 0


class SearchFilter(BaseModel):
    """Filter for vector search operations."""
    field: str
    value: Any
    operator: str = "=="  # ==, !=, >, <, >=, <=, in, not_in


class SearchQuery(BaseModel):
    """Search query model."""
    query: str
    collection_name: Optional[str] = None
    filters: List[Dict[str, Any]] = Field(default_factory=list)
    max_results: Optional[int] = None
    similarity_threshold: Optional[float] = None
    hybrid_search: bool = False


class SearchResult(BaseModel):
    """Search result model."""
    query: str
    results: List[Dict[str, Any]] = Field(default_factory=list)
    total_results: int = 0
    search_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)