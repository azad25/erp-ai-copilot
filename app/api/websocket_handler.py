"""
WebSocket Handler for AI Copilot with Reasoning Steps Support

This module handles WebSocket connections and provides real-time streaming
of AI reasoning steps and responses to connected clients.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from app.services.chat_service import ChatService
from app.models.api import MessageType
from app.core.exceptions import ValidationError, RateLimitError


class ConnectionManager:
    """Manages WebSocket connections for real-time communication"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, List[str]] = {}
        
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(connection_id)
        
        logging.info(f"WebSocket connection established: {connection_id} for user {user_id}")
    
    def disconnect(self, connection_id: str, user_id: str):
        """Remove a WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        if user_id in self.user_connections:
            if connection_id in self.user_connections[user_id]:
                self.user_connections[user_id].remove(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        logging.info(f"WebSocket connection closed: {connection_id} for user {user_id}")
    
    async def send_personal_message(self, message: dict, connection_id: str):
        """Send a message to a specific connection"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logging.error(f"Error sending message to {connection_id}: {e}")
                    # Remove broken connection
                    if connection_id in self.active_connections:
                        del self.active_connections[connection_id]
    
    async def broadcast_to_user(self, message: dict, user_id: str):
        """Send a message to all connections of a specific user"""
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id].copy():
                await self.send_personal_message(message, connection_id)


class WebSocketHandler:
    """WebSocket handler for AI Copilot with reasoning steps support"""
    
    def __init__(self):
        self.manager = ConnectionManager()
        self.chat_service = ChatService()
    
    async def handle_connection(self, websocket: WebSocket, user_id: str, token: str):
        """Handle a new WebSocket connection"""
        connection_id = str(uuid.uuid4())
        
        try:
            # Validate token and user (simplified for demo)
            if not await self._validate_user_token(user_id, token):
                await websocket.close(code=1008, reason="Invalid authentication")
                return
            
            # Accept connection
            await self.manager.connect(websocket, connection_id, user_id)
            
            # Send welcome message
            await self.manager.send_personal_message({
                "type": "connection_established",
                "connection_id": connection_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "features": ["reasoning_steps", "real_time_streaming", "multi_agent_support"]
            }, connection_id)
            
            # Handle incoming messages
            try:
                while True:
                    # Receive message from client
                    data = await websocket.receive_text()
                    message_data = json.loads(data)
                    
                    # Process the message
                    await self._process_message(message_data, connection_id, user_id)
                    
            except WebSocketDisconnect:
                logging.info(f"WebSocket disconnected: {connection_id}")
            except Exception as e:
                logging.error(f"Error in WebSocket handler: {e}", exc_info=True)
                await self.manager.send_personal_message({
                    "type": "error",
                    "message": "An error occurred while processing your request",
                    "error": str(e)
                }, connection_id)
        
        finally:
            self.manager.disconnect(connection_id, user_id)
    
    async def _validate_user_token(self, user_id: str, token: str) -> bool:
        """Validate user authentication token"""
        # Simplified validation - in production, validate JWT token
        return len(token) > 10 and user_id
    
    async def _process_message(self, message_data: dict, connection_id: str, user_id: str):
        """Process incoming WebSocket message"""
        message_type = message_data.get("type")
        
        if message_type == "chat_message":
            await self._handle_chat_message(message_data, connection_id, user_id)
        elif message_type == "ping":
            await self._handle_ping(connection_id)
        elif message_type == "get_conversation_history":
            await self._handle_get_history(message_data, connection_id, user_id)
        else:
            await self.manager.send_personal_message({
                "type": "error",
                "message": f"Unknown message type: {message_type}"
            }, connection_id)
    
    async def _handle_chat_message(self, message_data: dict, connection_id: str, user_id: str):
        """Handle chat message with reasoning steps streaming"""
        try:
            message = message_data.get("message", "")
            conversation_id = message_data.get("conversation_id")
            metadata = message_data.get("metadata", {})
            
            if not message:
                await self.manager.send_personal_message({
                    "type": "error",
                    "message": "Message content is required"
                }, connection_id)
                return
            
            # Create conversation if not provided
            if not conversation_id:
                conversation = await self.chat_service.create_conversation(
                    user_id=user_id,
                    title=f"Chat {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
                )
                conversation_id = conversation["conversation_id"]
                
                # Send conversation created notification
                await self.manager.send_personal_message({
                    "type": "conversation_created",
                    "conversation_id": conversation_id,
                    "title": conversation["title"]
                }, connection_id)
            
            # Send acknowledgment
            await self.manager.send_personal_message({
                "type": "message_received",
                "conversation_id": conversation_id,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }, connection_id)
            
            # Stream AI response with reasoning steps
            async for stream_response in self.chat_service.send_message_stream(
                conversation_id=conversation_id,
                user_id=user_id,
                message=message,
                message_type=MessageType.TEXT,
                metadata=metadata
            ):
                # Convert ChatStreamResponse to WebSocket message
                ws_message = {
                    "type": stream_response.type,
                    "content": stream_response.content,
                    "conversation_id": stream_response.conversation_id,
                    "message_id": stream_response.message_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Add additional fields for reasoning steps
                if hasattr(stream_response, 'metadata') and stream_response.metadata:
                    ws_message["metadata"] = stream_response.metadata
                
                if hasattr(stream_response, 'is_complete'):
                    ws_message["is_complete"] = stream_response.is_complete
                
                await self.manager.send_personal_message(ws_message, connection_id)
            
            # Send completion notification
            await self.manager.send_personal_message({
                "type": "response_complete",
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat()
            }, connection_id)
            
        except ValidationError as e:
            await self.manager.send_personal_message({
                "type": "validation_error",
                "message": str(e)
            }, connection_id)
        except RateLimitError as e:
            await self.manager.send_personal_message({
                "type": "rate_limit_error",
                "message": str(e)
            }, connection_id)
        except Exception as e:
            logging.error(f"Error handling chat message: {e}", exc_info=True)
            await self.manager.send_personal_message({
                "type": "error",
                "message": "An error occurred while processing your message",
                "error": str(e)
            }, connection_id)
    
    async def _handle_ping(self, connection_id: str):
        """Handle ping message"""
        await self.manager.send_personal_message({
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat()
        }, connection_id)
    
    async def _handle_get_history(self, message_data: dict, connection_id: str, user_id: str):
        """Handle request for conversation history"""
        try:
            conversation_id = message_data.get("conversation_id")
            limit = message_data.get("limit", 50)
            offset = message_data.get("offset", 0)
            
            if not conversation_id:
                await self.manager.send_personal_message({
                    "type": "error",
                    "message": "Conversation ID is required"
                }, connection_id)
                return
            
            # Get conversation history
            history = await self.chat_service.get_conversation_history(
                conversation_id=conversation_id,
                user_id=user_id,
                limit=limit,
                offset=offset
            )
            
            # Send history
            await self.manager.send_personal_message({
                "type": "conversation_history",
                "conversation_id": conversation_id,
                "messages": [
                    {
                        "role": msg.role.value,
                        "content": msg.content,
                        "metadata": msg.metadata,
                        "timestamp": getattr(msg, 'created_at', datetime.utcnow()).isoformat()
                    }
                    for msg in history
                ],
                "limit": limit,
                "offset": offset,
                "total": len(history)
            }, connection_id)
            
        except Exception as e:
            logging.error(f"Error getting conversation history: {e}", exc_info=True)
            await self.manager.send_personal_message({
                "type": "error",
                "message": "Failed to retrieve conversation history",
                "error": str(e)
            }, connection_id)


# Global WebSocket handler instance
websocket_handler = WebSocketHandler()
