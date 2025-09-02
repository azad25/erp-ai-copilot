"""
WebSocket endpoints for AI Copilot with reasoning steps support
"""

import json
import logging
from fastapi import WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.routing import APIRouter
from app.api.websocket_handler import websocket_handler
from app.services.enhanced_chat_service import enhanced_chat_service
from app.middleware.auth import verify_websocket_token

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws/chat")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token"),
    user_id: str = Query(..., description="User ID")
):
    """
    WebSocket endpoint for AI chat with reasoning steps streaming
    
    Features:
    - Real-time reasoning step streaming
    - Step-by-step AI processing transparency
    - Multi-source data integration display
    - Interactive chat with context awareness
    """
    await websocket.accept()
    
    try:
        # Verify authentication token
        auth_data = await verify_websocket_token(token)
        if not auth_data or auth_data.get("user_id") != user_id:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Authentication failed"
            }))
            await websocket.close()
            return
        
        organization_id = auth_data.get("organization_id")
        logger.info(f"WebSocket chat connected for user {user_id}")
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection",
            "status": "connected",
            "user_id": user_id,
            "organization_id": organization_id
        }))
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "chat_message":
                message = message_data.get("message", "")
                conversation_id = message_data.get("conversation_id")
                
                if not message.strip():
                    continue
                
                # Process message with reasoning steps
                async for step in enhanced_chat_service.process_chat_message(
                    user_id=user_id,
                    organization_id=organization_id,
                    message=message,
                    conversation_id=conversation_id,
                    websocket=websocket
                ):
                    # Stream each reasoning step to frontend
                    await websocket.send_text(json.dumps({
                        "type": "reasoning_step",
                        "step": step
                    }))
                    
                    # Small delay for better UX
                    import asyncio
                    await asyncio.sleep(0.1)
                
                # Send completion signal
                await websocket.send_text(json.dumps({
                    "type": "chat_complete",
                    "conversation_id": conversation_id
                }))
            
            elif message_data.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
