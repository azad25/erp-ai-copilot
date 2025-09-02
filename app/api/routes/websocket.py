"""
WebSocket API routes for AI Copilot real-time reasoning
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Dict, Any
import json
import logging
from datetime import datetime

from app.services.enhanced_chat_service import enhanced_chat_service
from app.services.auth_service import get_current_user_ws
from app.models.api import User

logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket connected for user: {user_id}")
    
    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"WebSocket disconnected for user: {user_id}")
    
    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)

manager = ConnectionManager()

@router.websocket("/ws/reasoning/{conversation_id}")
async def websocket_reasoning_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    token: str = None
):
    """WebSocket endpoint for step-by-step reasoning streaming"""
    try:
        # Authenticate user - extract token from query params
        query_params = dict(websocket.query_params)
        token = query_params.get("token")
        if not token:
            await websocket.close(code=1008, reason="Token required")
            return
        
        user = await get_current_user_ws(token)
        if not user:
            await websocket.close(code=1008, reason="Authentication failed")
            return
        
        await manager.connect(websocket, user.get("user_id"))
        
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                if message_data.get("type") == "chat_message":
                    message = message_data.get("message", "")
                    
                    # Stream reasoning steps
                    await enhanced_chat_service.stream_reasoning_steps(
                        websocket=websocket,
                        conversation_id=conversation_id,
                        message=message,
                        user_id=user.get("user_id")
                    )
                
                elif message_data.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
                    
        except WebSocketDisconnect:
            manager.disconnect(user.get("user_id"))
            logger.info(f"WebSocket disconnected for user: {user.get('user_id')}")
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass

@router.websocket("/ws/chat/{conversation_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    token: str = None
):
    """WebSocket endpoint for real-time chat"""
    try:
        # Authenticate user - extract token from query params
        query_params = dict(websocket.query_params)
        token = query_params.get("token")
        if not token:
            await websocket.close(code=1008, reason="Token required")
            return
        
        user = await get_current_user_ws(token)
        if not user:
            await websocket.close(code=1008, reason="Authentication failed")
            return
        
        await manager.connect(websocket, user.get("user_id"))
        
        try:
            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                if message_data.get("type") == "message":
                    message = message_data.get("content", "")
                    
                    # Process message with reasoning
                    result = await enhanced_chat_service.process_message_with_reasoning(
                        conversation_id=conversation_id,
                        message=message,
                        user_id=user.get("user_id")
                    )
                    
                    # Send response
                    await websocket.send_json({
                        "type": "response",
                        "conversation_id": conversation_id,
                        "response": result.get("response"),
                        "reasoning_steps": result.get("reasoning_steps", []),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
        except WebSocketDisconnect:
            manager.disconnect(user.get("user_id"))
            
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
