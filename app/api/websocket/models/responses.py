"""
Response models for WebSocket communication.
"""
from typing import Optional, Dict, Any, List, Union, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from ..models.messages import MessageType


class ResponseStatus(str, Enum):
    """Status of WebSocket responses."""
    SUCCESS = "success"
    ERROR = "error"
    PROCESSING = "processing"


class WebSocketResponse(BaseModel):
    """Base response model for WebSocket communication."""
    type: str = Field(..., description="Response type")
    status: ResponseStatus = Field(..., description="Response status")
    message: Optional[str] = Field(None, description="Response message")
    data: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Response data"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WebSocketChatResponse(WebSocketResponse):
    """Chat message response model."""
    type: Literal["chat_response"] = "chat_response"
    message_id: str = Field(..., description="Unique message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    sender_id: str = Field(..., description="ID of the message sender")
    content: str = Field(..., description="Message content")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional message metadata"
    )


class WebSocketErrorResponse(WebSocketResponse):
    """Error response model for WebSocket communication."""
    type: Literal["error"] = "error"
    status: Literal[ResponseStatus.ERROR] = ResponseStatus.ERROR
    code: str = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details"
    )
    
    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        code: str = "internal_error",
        status_code: int = 500,
        **kwargs
    ) -> 'WebSocketErrorResponse':
        """Create an error response from an exception."""
        return cls(
            code=code,
            message=str(exception),
            data={
                "exception_type": exception.__class__.__name__,
                "status_code": status_code,
                **kwargs
            }
        )
