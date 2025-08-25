"""
WebSocket router for real-time chat functionality.
"""
import json
import uuid
import time
from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import HTMLResponse
import structlog

from app.services.auth_service import get_current_user_ws
from app.services.chat_service import ChatService
from app.database.connection import get_db_session
from app.database.models.database import Conversation, Message, User
from app.models.api import WebSocketMessage, WebSocketChatMessage, WebSocketChatResponse, WebSocketStatusMessage
from app.core.metrics import WS_CONNECTIONS, WS_MESSAGES, WS_ERRORS

logger = structlog.get_logger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set of connection_ids
        self.connection_users: Dict[str, str] = {}  # connection_id -> user_id
    
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: str):
        """Connect a new WebSocket."""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.connection_users[connection_id] = user_id
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        
        WS_CONNECTIONS.inc()
        logger.info("WebSocket connected", connection_id=connection_id, user_id=user_id)
    
    def disconnect(self, connection_id: str):
        """Disconnect a WebSocket."""
        if connection_id in self.active_connections:
            user_id = self.connection_users.get(connection_id)
            if user_id and user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            del self.active_connections[connection_id]
            del self.connection_users[connection_id]
            
            WS_CONNECTIONS.dec()
            logger.info("WebSocket disconnected", connection_id=connection_id, user_id=user_id)
    
    async def send_personal_message(self, message: str, connection_id: str):
        """Send a message to a specific connection."""
        if connection_id in self.active_connections:
            try:
                await self.active_connections[connection_id].send_text(message)
                WS_MESSAGES.inc()
            except Exception as e:
                logger.error("Failed to send message", connection_id=connection_id, error=str(e))
                self.disconnect(connection_id)
    
    async def send_personal_json(self, data: dict, connection_id: str):
        """Send JSON data to a specific connection."""
        if connection_id in self.active_connections:
            try:
                await self.active_connections[connection_id].send_json(data)
                WS_MESSAGES.inc()
            except Exception as e:
                logger.error("Failed to send JSON", connection_id=connection_id, error=str(e))
                self.disconnect(connection_id)
    
    async def broadcast_to_user(self, message: str, user_id: str):
        """Broadcast a message to all connections of a user."""
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id].copy():
                await self.send_personal_message(message, connection_id)
    
    async def broadcast_to_user_json(self, data: dict, user_id: str):
        """Broadcast JSON data to all connections of a user."""
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id].copy():
                await self.send_personal_json(data, connection_id)


# Global connection manager
manager = ConnectionManager()


@router.get("/")
async def websocket_info():
    """WebSocket information endpoint."""
    return {
        "websocket": True,
        "endpoint": "/ws/chat",
        "protocol": "ws:// or wss://",
        "message_format": "JSON"
    }


@router.websocket("/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: Optional[str] = None
):
    """WebSocket endpoint for real-time chat."""
    connection_id = str(uuid.uuid4())
    user = None
    
    try:
        # Authenticate user
        if not token:
            await websocket.close(code=4001, reason="Authentication token required")
            return
        
        try:
            user = await get_current_user_ws(token)
        except Exception as e:
            logger.warning("WebSocket authentication failed", error=str(e))
            await websocket.close(code=4001, reason="Authentication failed")
            return
        
        # Connect to WebSocket
        await manager.connect(websocket, connection_id, str(user.id))
        
        # Send connection confirmation
        status_message = WebSocketStatusMessage(
            type="status",
            status="connected",
            message="WebSocket connection established",
            data={"connection_id": connection_id, "user_id": str(user.id)}
        )
        await manager.send_personal_json(status_message.model_dump(), connection_id)
        
        # Handle incoming messages
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Validate message format
                if message_data.get("type") == "chat_message":
                    await handle_chat_message(connection_id, user, message_data)
                elif message_data.get("type") == "ping":
                    # Handle ping for keep-alive
                    pong_message = WebSocketStatusMessage(
                        type="pong",
                        status="ok",
                        message="pong",
                        timestamp=time.time()
                    )
                    await manager.send_personal_json(pong_message.model_dump(), connection_id)
                else:
                    # Unknown message type
                    error_message = WebSocketStatusMessage(
                        type="error",
                        status="error",
                        message="Unknown message type",
                        data={"received_type": message_data.get("type")}
                    )
                    await manager.send_personal_json(error_message.model_dump(), connection_id)
                
            except json.JSONDecodeError:
                error_message = WebSocketStatusMessage(
                    type="error",
                    status="error",
                    message="Invalid JSON format"
                )
                await manager.send_personal_json(error_message.model_dump(), connection_id)
                
            except Exception as e:
                WS_ERRORS.inc()
                logger.error("WebSocket message handling error", error=str(e), exc_info=True)
                error_message = WebSocketStatusMessage(
                    type="error",
                    status="error",
                    message="Internal server error"
                )
                await manager.send_personal_json(error_message.model_dump(), connection_id)
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", connection_id=connection_id, user_id=str(user.id) if user else None)
    except Exception as e:
        WS_ERRORS.inc()
        logger.error("WebSocket error", error=str(e), exc_info=True)
    finally:
        manager.disconnect(connection_id)


async def handle_chat_message(connection_id: str, user: User, message_data: dict):
    """Handle incoming chat messages."""
    try:
        # Extract message data
        conversation_id = message_data.get("conversation_id")
        message_content = message_data.get("message")
        
        if not message_content:
            error_message = WebSocketStatusMessage(
                type="error",
                status="error",
                message="Message content is required"
            )
            await manager.send_personal_json(error_message.model_dump(), connection_id)
            return
        
        # Get or create conversation
        db = await get_db_session().__anext__()
        try:
            if conversation_id:
                # Verify conversation belongs to user
                conversation = await db.execute(
                    "SELECT * FROM conversations WHERE id = $1 AND user_id = $2 AND organization_id = $3",
                    (conversation_id, user.id, user.organization_id)
                )
                conversation = conversation.fetchone()
                if not conversation:
                    error_message = WebSocketStatusMessage(
                        type="error",
                        status="error",
                        message="Conversation not found"
                    )
                    await manager.send_personal_json(error_message.model_dump(), connection_id)
                    return
            else:
                # Create new conversation
                conversation = await db.execute(
                    "INSERT INTO conversations (organization_id, user_id, title, context, metadata) VALUES ($1, $2, $3, $4, $5) RETURNING *",
                    (
                        user.organization_id,
                        user.id,
                        message_content[:100] + "..." if len(message_content) > 100 else message_content,
                        {},
                        {"source": "websocket"}
                    )
                )
                conversation = conversation.fetchone()
                conversation_id = conversation["id"]
            
            # Save user message
            user_message = await db.execute(
                "INSERT INTO messages (conversation_id, user_id, role, content, metadata) VALUES ($1, $2, $3, $4, $5) RETURNING *",
                (
                    conversation_id,
                    user.id,
                    "user",
                    message_content,
                    {"source": "websocket"}
                )
            )
            user_message = user_message.fetchone()
            
            # Generate AI response
            chat_service = ChatService(db, user)
            response = await chat_service.generate_response(
                conversation_id=conversation_id,
                user_message=message_content,
                context={}
            )
            
            # Save AI response
            ai_message = await db.execute(
                "INSERT INTO messages (conversation_id, user_id, role, content, metadata) VALUES ($1, $2, $3, $4, $5) RETURNING *",
                (
                    conversation_id,
                    None,
                    "assistant",
                    response["content"],
                    {
                        "agent_type": response.get("agent_type"),
                        "model_used": response.get("model_used"),
                        "tokens_used": response.get("tokens_used"),
                        "source": "websocket"
                    }
                )
            )
            ai_message = ai_message.fetchone()
            
            # Send response back to user
            chat_response = WebSocketChatResponse(
                type="chat_response",
                conversation_id=conversation_id,
                message_id=ai_message["id"],
                content=response["content"],
                agent_type=response.get("agent_type"),
                is_complete=True,
                chunk_index=1,
                total_chunks=1
            )
            
            await manager.send_personal_json(chat_response.model_dump(), connection_id)
            
            # Update conversation title if needed
            if not conversation["title"] or conversation["title"].startswith("..."):
                await db.execute(
                    "UPDATE conversations SET title = $1 WHERE id = $2",
                    (message_content[:100] + "..." if len(message_content) > 100 else message_content, conversation_id)
                )
            
            await db.commit()
            
            logger.info(
                "WebSocket chat response generated",
                connection_id=connection_id,
                conversation_id=str(conversation_id),
                user_id=str(user.id)
            )
            
        finally:
            await db.close()
            
    except Exception as e:
        WS_ERRORS.inc()
        logger.error("Failed to handle chat message", error=str(e), exc_info=True)
        error_message = WebSocketStatusMessage(
            type="error",
            status="error",
            message="Failed to process message"
        )
        await manager.send_personal_json(error_message.model_dump(), connection_id)


@router.get("/status")
async def websocket_status():
    """Get WebSocket connection status."""
    return {
        "active_connections": len(manager.active_connections),
        "connected_users": len(manager.user_connections),
        "status": "running"
    }


@router.get("/test")
async def websocket_test_page():
    """Simple WebSocket test page."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WebSocket Chat Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
            .chat-box { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; margin: 10px 0; }
            .input-group { margin: 10px 0; }
            input[type="text"] { width: 70%; padding: 8px; }
            button { padding: 8px 16px; background: #007bff; color: white; border: none; cursor: pointer; }
            button:hover { background: #0056b3; }
            .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
            .connected { background: #d4edda; color: #155724; }
            .disconnected { background: #f8d7da; color: #721c24; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>WebSocket Chat Test</h1>
            <div id="status" class="status disconnected">Disconnected</div>
            
            <div class="input-group">
                <input type="text" id="token" placeholder="Enter JWT token" style="width: 100%;">
            </div>
            
            <div class="input-group">
                <button onclick="connect()">Connect</button>
                <button onclick="disconnect()">Disconnect</button>
            </div>
            
            <div class="chat-box" id="chatBox"></div>
            
            <div class="input-group">
                <input type="text" id="message" placeholder="Type your message..." onkeypress="handleKeyPress(event)">
                <button onclick="sendMessage()">Send</button>
            </div>
        </div>
        
        <script>
            let ws = null;
            let conversationId = null;
            
            function updateStatus(connected) {
                const status = document.getElementById('status');
                if (connected) {
                    status.textContent = 'Connected';
                    status.className = 'status connected';
                } else {
                    status.textContent = 'Disconnected';
                    status.className = 'status disconnected';
                }
            }
            
            function addMessage(message, isUser = false) {
                const chatBox = document.getElementById('chatBox');
                const messageDiv = document.createElement('div');
                messageDiv.style.margin = '5px 0';
                messageDiv.style.padding = '5px';
                messageDiv.style.backgroundColor = isUser ? '#e3f2fd' : '#f5f5f5';
                messageDiv.style.borderRadius = '4px';
                messageDiv.textContent = (isUser ? 'You: ' : 'AI: ') + message;
                chatBox.appendChild(messageDiv);
                chatBox.scrollTop = chatBox.scrollHeight;
            }
            
            function connect() {
                const token = document.getElementById('token').value;
                if (!token) {
                    alert('Please enter a JWT token');
                    return;
                }
                
                const wsUrl = `ws://${window.location.host}/ws/chat?token=${token}`;
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function() {
                    updateStatus(true);
                    addMessage('Connected to WebSocket');
                };
                
                ws.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type === 'chat_response') {
                            addMessage(data.content);
                            conversationId = data.conversation_id;
                        } else if (data.type === 'status') {
                            addMessage(`Status: ${data.message}`);
                        } else if (data.type === 'error') {
                            addMessage(`Error: ${data.message}`);
                        }
                    } catch (e) {
                        addMessage(`Raw message: ${event.data}`);
                    }
                };
                
                ws.onclose = function() {
                    updateStatus(false);
                    addMessage('Disconnected from WebSocket');
                };
                
                ws.onerror = function(error) {
                    addMessage(`WebSocket error: ${error}`);
                };
            }
            
            function disconnect() {
                if (ws) {
                    ws.close();
                    ws = null;
                }
            }
            
            function sendMessage() {
                const messageInput = document.getElementById('message');
                const message = messageInput.value.trim();
                
                if (!message || !ws) return;
                
                const chatMessage = {
                    type: 'chat_message',
                    conversation_id: conversationId,
                    message: message
                };
                
                ws.send(JSON.stringify(chatMessage));
                addMessage(message, true);
                messageInput.value = '';
            }
            
            function handleKeyPress(event) {
                if (event.key === 'Enter') {
                    sendMessage();
                }
            }
            
            // Auto-connect on page load for testing
            // connect();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
