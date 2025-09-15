"""
WebSocket API routes for AI Copilot real-time reasoning
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request
from typing import Dict, Any
import json
import logging
from datetime import datetime
from pydantic import BaseModel

from app.services.chat_service import chat_service
from app.services.auth_service import get_current_user_ws
from app.models.api import User

logger = logging.getLogger(__name__)

router = APIRouter()

class TestReasoningRequest(BaseModel):
    message: str
    conversation_id: str
    user_id: str

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
        
        # Handle both User object and dict responses
        user_id = user.id if hasattr(user, 'id') else user.get("user_id") or user.get("id")
        await manager.connect(websocket, str(user_id))
        
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                if message_data.get("type") == "chat_message":
                    message = message_data.get("message", "")
                    
                    # Stream reasoning steps using ChatService with enhanced animation support
                    from app.services.chat_service import ChatService
                    chat_service = ChatService()
                    
                    try:
                        # Send initial processing message
                        await websocket.send_json({
                            "type": "processing_start",
                            "content": "Starting AI analysis...",
                            "conversation_id": conversation_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "animation": {
                                "type": "pulse",
                                "duration": 1000
                            }
                        })
                        
                        step_count = 0
                        async for stream_response in chat_service.send_message_stream(
                            conversation_id=conversation_id,
                            user_id=str(user_id),
                            message=message,
                            metadata={"source": "websocket_reasoning"},
                            organization_id=getattr(user, 'organization_id', '00000000-0000-0000-0000-000000000000')
                        ):
                            # Enhanced streaming response with animation metadata
                            response_data = {
                                "type": stream_response.type,
                                "content": stream_response.content,
                                "conversation_id": str(stream_response.conversation_id) if stream_response.conversation_id else None,
                                "message_id": str(stream_response.message_id) if stream_response.message_id else None,
                                "metadata": stream_response.metadata,
                                "is_complete": getattr(stream_response, 'is_complete', False),
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            
                            # Add animation metadata for reasoning steps
                            if stream_response.type == "reasoning_step":
                                step_count += 1
                                response_data["animation"] = {
                                    "type": "slide_in",
                                    "duration": 500,
                                    "delay": step_count * 100,  # Stagger animations
                                    "step_number": step_count
                                }
                                
                                # Parse reasoning step for enhanced display
                                try:
                                    step_data = json.loads(stream_response.content)
                                    response_data["reasoning_step"] = {
                                        "step_number": step_data.get("step_number", step_count),
                                        "step_type": step_data.get("step_type", "analysis"),
                                        "title": step_data.get("title", "Processing..."),
                                        "description": step_data.get("description", ""),
                                        "source": step_data.get("source", "AI"),
                                        "icon": step_data.get("icon", "🧠"),
                                        "status": step_data.get("status", "processing")
                                    }
                                except:
                                    # Fallback for non-JSON content
                                    response_data["reasoning_step"] = {
                                        "step_number": step_count,
                                        "step_type": "analysis",
                                        "title": "Processing step",
                                        "description": stream_response.content,
                                        "source": "AI",
                                        "icon": "🧠",
                                        "status": "processing"
                                    }
                            
                            elif stream_response.type == "chunk":
                                # Add typing animation for text chunks
                                response_data["animation"] = {
                                    "type": "typing",
                                    "duration": 50
                                }
                            
                            elif stream_response.type == "start":
                                response_data["animation"] = {
                                    "type": "fade_in",
                                    "duration": 300
                                }
                            
                            # Send enhanced response to WebSocket
                            await websocket.send_json(response_data)
                            
                        # Send completion message
                        await websocket.send_json({
                            "type": "processing_complete",
                            "content": "Analysis complete",
                            "conversation_id": conversation_id,
                            "total_steps": step_count,
                            "timestamp": datetime.utcnow().isoformat(),
                            "animation": {
                                "type": "success_pulse",
                                "duration": 800
                            }
                        })
                        
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "content": f"Reasoning error: {str(e)}",
                            "conversation_id": conversation_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "animation": {
                                "type": "shake",
                                "duration": 500
                            }
                        })
                
                elif message_data.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
                    
        except WebSocketDisconnect:
            manager.disconnect(str(user_id))
            logger.info(f"WebSocket disconnected for user: {user_id}")
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass

@router.websocket("/chat")
async def websocket_chat_endpoint_simple(
    websocket: WebSocket,
    token: str = None
):
    """WebSocket endpoint for real-time chat without conversation_id in path"""
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
        
        # Handle both User object and dict responses
        user_id = user.id if hasattr(user, 'id') else user.get("user_id") or user.get("id")
        await manager.connect(websocket, str(user_id))
        
        try:
            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                if message_data.get("type") == "message":
                    message = message_data.get("content", "")
                    conversation_id = message_data.get("conversation_id")
                    
                    # Process message with reasoning
                    result = await chat_service.process_message_with_reasoning(
                        conversation_id=conversation_id,
                        message=message,
                        user_id=str(user_id)
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
            manager.disconnect(str(user_id))
            
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass

@router.websocket("/ws/chat/{conversation_id}")
async def websocket_chat_endpoint_with_id(
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
        
        # Handle both User object and dict responses
        user_id = user.id if hasattr(user, 'id') else user.get("user_id") or user.get("id")
        await manager.connect(websocket, str(user_id))
        
        try:
            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                if message_data.get("type") == "message":
                    message = message_data.get("content", "")
                    
                    # Process message with reasoning
                    result = await chat_service.process_message_with_reasoning(
                        conversation_id=conversation_id,
                        message=message,
                        user_id=str(user_id)
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
            manager.disconnect(str(user_id))
            
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass

@router.post("/test-reasoning")
async def test_reasoning_endpoint(request: dict):
    """Test endpoint for reasoning functionality"""
    try:
        from app.services.chat_service import ChatService
        chat_service = ChatService()
        
        conversation_id = request.get("conversation_id")
        message = request.get("message", "")
        user_id = request.get("user_id", "test-user")
        
        # Collect reasoning steps from streaming response
        reasoning_steps = []
        final_response = ""
        
        async for stream_response in chat_service.send_message_stream(
            conversation_id=conversation_id,
            user_id=user_id,
            message=message,
            metadata={"source": "test_reasoning"}
        ):
            if stream_response.type == "reasoning_step":
                # Parse reasoning step from content
                import json
                try:
                    step_data = json.loads(stream_response.content)
                    reasoning_steps.append({
                        "step_type": step_data.get("step_type", "analysis"),
                        "description": step_data.get("description", stream_response.content),
                        "source": step_data.get("source", "AI"),
                        "icon": step_data.get("icon", "🧠"),
                        "content": step_data.get("content", stream_response.content)
                    })
                except:
                    reasoning_steps.append({
                        "step_type": "analysis",
                        "description": stream_response.content,
                        "source": "AI",
                        "icon": "🧠",
                        "content": stream_response.content
                    })
            elif stream_response.type == "chunk":
                final_response += stream_response.content
        
        return {
            "status": "success",
            "conversation_id": conversation_id,
            "response": final_response,
            "reasoning_steps": reasoning_steps,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Test reasoning error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
