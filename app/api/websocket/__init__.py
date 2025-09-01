"""
WebSocket package for real-time communication in the ERP Suite.

This package provides WebSocket functionality for real-time features
like chat, notifications, and live updates.
"""
from .connection_manager import ConnectionManager
from .service import WebSocketService
from .router import router as websocket_router
from .models import (
    WebSocketMessage,
    WebSocketChatMessage,
    WebSocketTypingIndicator,
    WebSocketPingMessage,
    WebSocketStatusMessage,
    WebSocketResponse,
    WebSocketChatResponse,
    WebSocketErrorResponse
)

__all__ = [
    'ConnectionManager',
    'WebSocketService',
    'websocket_router',
    'WebSocketMessage',
    'WebSocketChatMessage',
    'WebSocketTypingIndicator',
    'WebSocketPingMessage',
    'WebSocketStatusMessage',
    'WebSocketResponse',
    'WebSocketChatResponse',
    'WebSocketErrorResponse'
]
