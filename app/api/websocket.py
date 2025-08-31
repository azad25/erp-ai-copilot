"""
WebSocket router for real-time chat functionality.
"""
import asyncio
import json
import uuid
import time
from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import HTMLResponse
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from sqlalchemy.orm import selectinload

from app.services.auth_service import get_current_user_ws
from app.services.chat_service import ChatService
from app.database.connection import get_db_session
from app.database.models.database import Conversation, Message, User, ConversationTable, MessageTable
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
                WS_MESSAGES.labels(message_type="text").inc()
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected", connection_id=connection_id)
            except Exception as e:
                logger.error("Error handling WebSocket message", 
                           connection_id=connection_id, 
                           error=str(e), 
                           exc_info=True)
                WS_ERRORS.labels(error_type="message_error").inc()
    
    async def send_personal_json(self, data: dict, connection_id: str) -> bool:
        """
        Send JSON data to a specific connection.
        
        Args:
            data: The data to send (will be converted to JSON)
            connection_id: The ID of the connection to send to
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        if connection_id not in self.active_connections:
            logger.debug("Connection not found", connection_id=connection_id)
            return False
            
        try:
            # Ensure data is JSON serializable
            import json
            json.dumps(data)  # Test serialization
            
            await self.active_connections[connection_id].send_json(data)
            WS_MESSAGES.labels(message_type="json").inc()
            return True
            
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected during send", connection_id=connection_id)
            self.disconnect(connection_id)
            return False
            
        except (TypeError, ValueError) as e:
            logger.error("JSON serialization error", 
                       connection_id=connection_id, 
                       error=str(e),
                       data_type=type(data).__name__)
            WS_ERRORS.labels(error_type="serialization").inc()
            return False
            
        except Exception as e:
            logger.error("Error sending WebSocket message", 
                       connection_id=connection_id, 
                       error=str(e), 
                       exc_info=True)
            WS_ERRORS.labels(error_type="send_error").inc()
            return False
    
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
    import uuid
    from app.database.models.database import User
    from app.services.token_cache_service import validate_token_with_cache
    
    connection_id = str(uuid.uuid4())
    user = None
    
    try:
        logger.info("New WebSocket connection attempt", connection_id=connection_id)
        
        # Validate token using cache service (validates with auth service only once per token)
        if token:
            # Validate token with cache service
            user_info = await validate_token_with_cache(token)
            if not user_info:
                logger.warning("Token validation failed", connection_id=connection_id)
                await websocket.close(code=1008, reason="Invalid token")
                return
            
            # Create user object with data from cached user info
            user = User(
                id=user_info['id'],
                email=user_info['email'],
                organization_id=user_info['organization_id'],
                is_active=user_info['is_active'],
                is_verified=user_info['is_verified']
            )
            logger.info("User authenticated via token cache", 
                       connection_id=connection_id, 
                       user_id=user.id, 
                       email=user.email,
                       organization_id=user.organization_id)
        else:
            logger.warning("No token provided", connection_id=connection_id)
            await websocket.close(code=1008, reason="Token required")
            return
        
        logger.info("WebSocket user created", 
                   user_id=user.id,
                   email=user.email)
        
        # Connect to WebSocket
        await manager.connect(websocket, connection_id, str(user.id))
        logger.info("WebSocket connection accepted and added to manager", connection_id=connection_id)
        
        # Send connection confirmation
        status_message = WebSocketStatusMessage(
            type="status",
            status="connected",
            message="WebSocket connection established",
            data={"connection_id": connection_id, "user_id": str(user.id)}
        )
        await manager.send_personal_json(status_message.model_dump(), connection_id)
        logger.info("Connection confirmation sent", connection_id=connection_id)
        
        # Handle incoming messages
        while True:
            try:
                # Receive message with timeout to prevent hanging
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=300)  # 5 minute timeout
                except asyncio.TimeoutError:
                    logger.info("WebSocket connection timed out", connection_id=connection_id)
                    break
                    
                try:
                    message_data = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.warning("Invalid JSON received", 
                                 connection_id=connection_id,
                                 error=str(e))
                    await manager.send_personal_json(
                        WebSocketStatusMessage(
                            type="error",
                            status="error",
                            message="Invalid JSON format"
                        ).model_dump(), 
                        connection_id
                    )
                    continue
                
                # Process valid message
                try:
                    message_type = message_data.get("type")
                    if message_type in ["chat_message", "chat"]:
                        await handle_chat_message(connection_id, user, message_data)
                    elif message_type == "ping":
                        # Handle ping for keep-alive
                        await manager.send_personal_json(
                            WebSocketStatusMessage(
                                type="pong",
                                status="ok",
                                message="pong"
                            ).model_dump(),
                            connection_id
                        )
                    else:
                        # Unknown message type
                        await manager.send_personal_json(
                            WebSocketStatusMessage(
                                type="error",
                                status="error",
                                message="Unknown message type",
                                data={"received_type": message_type}
                            ).model_dump(),
                            connection_id
                        )
                except Exception as e:
                    logger.error("Error processing message", 
                               connection_id=connection_id, 
                               error=str(e), 
                               exc_info=True)
                    WS_ERRORS.labels(error_type="processing").inc()
                    
                    # Try to send error message to client
                    try:
                        await manager.send_personal_json(
                            WebSocketStatusMessage(
                                type="error",
                                status="error",
                                message="Error processing message"
                            ).model_dump(),
                            connection_id
                        )
                    except Exception as send_error:
                        logger.error("Failed to send error message to client",
                                   connection_id=connection_id,
                                   error=str(send_error))
                        break  # Exit if we can't send error messages
                
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected normally", 
                          connection_id=connection_id, 
                          user_id=str(user.id) if user else None)
                break
                
            except RuntimeError as e:
                if "Cannot call" in str(e) and "disconnect" in str(e):
                    logger.info("WebSocket disconnected (runtime)", 
                              connection_id=connection_id,
                              error=str(e))
                else:
                    logger.error("WebSocket runtime error", 
                               connection_id=connection_id,
                               error=str(e),
                               exc_info=True)
                break
                
            except Exception as e:
                logger.error("Unexpected WebSocket error", 
                           connection_id=connection_id,
                           error=str(e),
                           exc_info=True)
                WS_ERRORS.labels(error_type="unexpected").inc()
                break
                
    except Exception as e:
        logger.error("Fatal WebSocket error", 
                   connection_id=connection_id,
                   error=str(e),
                   exc_info=True)
        WS_ERRORS.labels(error_type="fatal").inc()
        
    finally:
        # Ensure cleanup happens even if an exception occurred
        if connection_id in manager.active_connections:
            manager.disconnect(connection_id)
            logger.info("WebSocket connection cleaned up", connection_id=connection_id)


async def handle_chat_message(connection_id: str, user: User, message_data: dict):
    """Handle incoming chat messages."""
    try:
        # Extract message data - handle both direct message and nested data structure
        conversation_id = message_data.get("conversation_id") or message_data.get("data", {}).get("conversation_id")
        message_content = message_data.get("message") or message_data.get("data", {}).get("message")
        
        # Log the message data for debugging
        logger.info("Processing chat message", 
                   connection_id=connection_id,
                   message_type=message_data.get("type"),
                   has_message=bool(message_content),
                   message_keys=list(message_data.keys()))
        
        if not message_content:
            error_message = WebSocketStatusMessage(
                type="error",
                status="error",
                message="Message content is required"
            )
            await manager.send_personal_json(error_message.model_dump(), connection_id)
            return
        
        # Get or create conversation
        async with get_db_session() as db:
            if conversation_id:
                # Verify conversation belongs to user
                result = await db.execute(
                    select(ConversationTable).where(
                        and_(
                            ConversationTable.id == conversation_id,
                            ConversationTable.user_id == user.id,
                            ConversationTable.organization_id == user.organization_id
                        )
                    )
                )
                conversation = result.scalar_one_or_none()
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
                conversation_id = uuid.uuid4()
                conversation = ConversationTable(
                    id=conversation_id,
                    organization_id=uuid.UUID(user.organization_id) if isinstance(user.organization_id, str) else user.organization_id,
                    user_id=uuid.UUID(user.id) if isinstance(user.id, str) else user.id,
                    title=message_content[:100] + "..." if len(message_content) > 100 else message_content,
                    context={},
                    meta_data={"source": "websocket"}
                )
                db.add(conversation)
                await db.flush()  # Get the ID without committing
            
            # Generate AI response using ChatService (handles message storage internally)
            try:
                logger.info("Creating ChatService instance", connection_id=connection_id)
                chat_service = ChatService()
                logger.info("ChatService created, sending message", connection_id=connection_id)
                response = await chat_service.send_message(
                    conversation_id=str(conversation_id),
                    user_id=user.id,
                    message=message_content
                )
                logger.info("ChatService response received", connection_id=connection_id, response_type=type(response))
            except Exception as chat_error:
                logger.error("ChatService error", connection_id=connection_id, error=str(chat_error), exc_info=True)
                raise
            
            # Send response back to user (ChatService already stores the AI message)
            chat_response = WebSocketChatResponse(
                type="chat_response",
                conversation_id=conversation_id,
                message_id=str(response.message_id),
                content=response.content,
                agent_type=response.agent_type,
                is_complete=True,
                chunk_index=1,
                total_chunks=1
            )
            
            await manager.send_personal_json(chat_response.model_dump(), connection_id)
            
            # Update conversation title if needed
            if not conversation.title or conversation.title.startswith("..."):
                conversation.title = message_content[:100] + "..." if len(message_content) > 100 else message_content
            
            await db.commit()
            
            logger.info(
                "WebSocket chat response generated",
                connection_id=connection_id,
                conversation_id=str(conversation_id),
                user_id=str(user.id)
            )
            
    except Exception as e:
        WS_ERRORS.labels(error_type="chat_handler").inc()
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
