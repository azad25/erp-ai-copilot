"""
MongoDB models for the AI Copilot service.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List, Annotated
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic v2."""
    
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetJsonSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema([
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(cls.validate),
                ])
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x)
            ),
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str):
            if ObjectId.is_valid(v):
                return ObjectId(v)
        raise ValueError("Invalid ObjectId")

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string", "format": "objectid"}


class ConversationMongo(BaseModel):
    """MongoDB Conversation model."""
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    user_id: str
    title: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class MessageMongo(BaseModel):
    """MongoDB Message model."""
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    user_id: Optional[str] = None
    role: str
    content: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    tokens_used: int = 0
    model_used: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class AgentExecutionMongo(BaseModel):
    """MongoDB Agent execution model."""
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    user_id: str
    agent_type: str
    action_type: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class KnowledgeBaseMongo(BaseModel):
    """MongoDB Knowledge base model."""
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    document_id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    document_type: str
    title: str
    content: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    embedding_id: Optional[str] = None
    vector_id: Optional[str] = None
    access_level: str = "all"
    version: str = "1.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class MemoryMongo(BaseModel):
    """MongoDB Memory model."""
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    memory_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    organization_id: str
    memory_type: str
    content: str
    importance: float = 0.5
    tags: List[str] = Field(default_factory=list)
    embedding_id: Optional[str] = None
    vector_id: Optional[str] = None
    access_count: int = 0
    last_accessed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


# Response models for API
class ConversationResponse(BaseModel):
    """Conversation response model."""
    
    conversation_id: str
    organization_id: str
    user_id: str
    title: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    """Message response model."""
    
    message_id: str
    conversation_id: str
    user_id: Optional[str] = None
    role: str
    content: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    tokens_used: int = 0
    model_used: Optional[str] = None
    created_at: datetime


class AgentExecutionResponse(BaseModel):
    """Agent execution response model."""
    
    execution_id: str
    conversation_id: str
    user_id: str
    agent_type: str
    action_type: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    status: str
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class KnowledgeBaseResponse(BaseModel):
    """Knowledge base response model."""
    
    document_id: str
    organization_id: str
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


class MemoryResponse(BaseModel):
    """Memory response model."""
    
    memory_id: str
    user_id: str
    organization_id: str
    memory_type: str
    content: str
    importance: float
    tags: List[str]
    embedding_id: Optional[str] = None
    vector_id: Optional[str] = None
    access_count: int
    last_accessed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
