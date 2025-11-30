"""
WebSocket message models for incoming WebSocket messages.
"""
from enum import Enum
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, validator


class MessageType(str, Enum):
    """Types of WebSocket messages."""
    CHAT = "chat_message"
    TYPING = "typing_indicator"
    PING = "ping"
    PONG = "pong"
    STATUS = "status"


class WebSocketMessage(BaseModel):
    """Base WebSocket message model."""
    type: MessageType = Field(..., description="Type of the WebSocket message")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            MessageType: lambda v: v.value
        }


class WebSocketChatMessage(WebSocketMessage):
    """Chat message model for WebSocket communication."""
    type: Literal[MessageType.CHAT] = MessageType.CHAT
    conversation_id: str = Field(..., description="Target conversation ID")
    message: str = Field(..., description="Message content")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional message metadata"
    )


class WebSocketTypingIndicator(WebSocketMessage):
    """Typing indicator message model."""
    type: Literal[MessageType.TYPING] = MessageType.TYPING
    is_typing: bool = Field(..., description="Whether the user is typing")
    conversation_id: Optional[str] = Field(
        None,
        description="Conversation ID where typing is occurring"
    )


class WebSocketPingMessage(WebSocketMessage):
    """Ping message for connection keep-alive."""
    type: Literal[MessageType.PING] = MessageType.PING
    timestamp: Optional[float] = Field(
        None,
        description="Timestamp when ping was sent"
    )


class WebSocketPongMessage(WebSocketMessage):
    """Pong response message for connection keep-alive."""
    type: Literal[MessageType.PONG] = MessageType.PONG
    message: str = Field(default="pong", description="Pong message")
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional pong data (e.g., latency)"
    )


class WebSocketStatusMessage(WebSocketMessage):
    """Status message for WebSocket communication."""
    type: Literal[MessageType.STATUS] = MessageType.STATUS
    status: str = Field(..., description="Status type (e.g., 'connected', 'error')")
    message: str = Field(..., description="Status message")
    data: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional status data"
    )
    code: Optional[int] = Field(
        None,
        description="Status code (for errors)",
        ge=1000,
        le=1015
    )
    
    @validator('status')
    def validate_status(cls, v):
        """Validate status field values."""
        valid_statuses = {'connected', 'error', 'disconnected', 'warning', 'info'}
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v
