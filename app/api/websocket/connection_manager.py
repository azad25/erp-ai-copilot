"""
WebSocket connection manager for handling active connections and broadcasting messages.
"""
from typing import Dict, Set, Optional
from fastapi import WebSocket
import structlog
from prometheus_client import Counter, Gauge

logger = structlog.get_logger(__name__)

# Prometheus metrics
WS_CONNECTIONS = Gauge('websocket_active_connections', 'Number of active WebSocket connections')
WS_MESSAGES = Counter('websocket_messages_total', 'Total WebSocket messages', ['message_type'])
WS_ERRORS = Counter('websocket_errors_total', 'Total WebSocket errors', ['error_type'])

class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self):
        """Initialize the connection manager with empty connection mappings."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set of connection_ids
        self.connection_users: Dict[str, str] = {}  # connection_id -> user_id
    
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: str) -> None:
        """Register a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            connection_id: Unique connection identifier
            user_id: Authenticated user ID
        """
        try:
            # WebSocket is already accepted in the router, so skip the accept call
                
            self.active_connections[connection_id] = websocket
            self.connection_users[connection_id] = user_id
            
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
            
            WS_CONNECTIONS.inc()
            logger.info(
                "WebSocket connected", 
                connection_id=connection_id, 
                user_id=user_id,
                active_connections=len(self.active_connections)
            )
            
        except Exception as e:
            logger.error(
                "Error in WebSocket connection", 
                error=str(e),
                connection_id=connection_id,
                user_id=user_id
            )
            raise
    
    def disconnect(self, connection_id: str) -> None:
        """Remove a WebSocket connection.
        
        Args:
            connection_id: The connection ID to remove
        """
        if connection_id in self.active_connections:
            user_id = self.connection_users.get(connection_id)
            if user_id and user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            del self.active_connections[connection_id]
            del self.connection_users[connection_id]
            
            WS_CONNECTIONS.dec()
            logger.info(
                "WebSocket disconnected", 
                connection_id=connection_id, 
                user_id=user_id,
                active_connections=len(self.active_connections)
            )
    
    async def send_text(self, message: str, connection_id: str) -> bool:
        """Send a text message to a specific connection.
        
        Args:
            message: The message to send
            connection_id: Target connection ID
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if connection_id not in self.active_connections:
            logger.debug("Connection not found", connection_id=connection_id)
            return False
            
        try:
            await self.active_connections[connection_id].send_text(message)
            WS_MESSAGES.labels(message_type="text").inc()
            return True
            
        except Exception as e:
            logger.error(
                "Error sending WebSocket message",
                connection_id=connection_id,
                error=str(e)
            )
            WS_ERRORS.labels(error_type="send_error").inc()
            self.disconnect(connection_id)
            return False
    
    async def send_json(self, data: dict, connection_id: str) -> bool:
        """Send JSON data to a specific connection.
        
        Args:
            data: The JSON-serializable data to send
            connection_id: Target connection ID
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if connection_id not in self.active_connections:
            logger.debug("Connection not found", connection_id=connection_id)
            return False
            
        try:
            await self.active_connections[connection_id].send_json(data)
            WS_MESSAGES.labels(message_type="json").inc()
            return True
            
        except Exception as e:
            logger.error(
                "Error sending WebSocket JSON",
                connection_id=connection_id,
                error=str(e),
                data_type=type(data).__name__
            )
            WS_ERRORS.labels(error_type="send_error").inc()
            self.disconnect(connection_id)
            return False
    
    async def broadcast_to_user(self, message: str, user_id: str) -> None:
        """Broadcast a message to all connections of a user.
        
        Args:
            message: The message to send
            user_id: Target user ID
        """
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id].copy():
                await self.send_text(message, connection_id)
    
    async def broadcast_json_to_user(self, data: dict, user_id: str) -> None:
        """Broadcast JSON data to all connections of a user.
        
        Args:
            data: The JSON-serializable data to send
            user_id: Target user ID
        """
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id].copy():
                await self.send_json(data, connection_id)
