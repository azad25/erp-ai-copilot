"""
WebSocket router for the application.
"""
from fastapi import APIRouter, WebSocket, Query, Depends
from fastapi.responses import HTMLResponse

from .service import WebSocketService
from .connection_manager import ConnectionManager

# Create router
router = APIRouter()

# Initialize WebSocket service
websocket_service = WebSocketService()

@router.websocket("/test")
async def websocket_test_endpoint(websocket: WebSocket):
    """Minimal WebSocket test endpoint."""
    await websocket.accept()
    await websocket.send_json({"type": "connection", "message": "Test connection successful"})
    
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "echo", "message": f"Echo: {data}"})
    except:
        pass

@router.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication.
    
    This endpoint handles the WebSocket connection and message routing.
    Authentication is handled within the connection handler.
    
    Args:
        websocket: The WebSocket connection
    """
    import structlog
    logger = structlog.get_logger(__name__)
    
    try:
        # Accept the connection first to avoid 403 errors
        await websocket.accept()
        logger.info("WebSocket connection accepted")
        
        # Extract token from query parameters
        token = websocket.query_params.get("token")
        logger.info(f"Token extracted: {'present' if token else 'missing'}")
        
        if not token:
            logger.error("No token provided in WebSocket connection")
            await websocket.send_json({
                "type": "error",
                "message": "Authentication token is required"
            })
            await websocket.close(code=1008, reason="Authentication required")
            return
        
        # Use the WebSocket service to handle the connection (skip accept since we already did it)
        logger.info("Calling handle_authenticated_connection")
        await websocket_service.handle_authenticated_connection(websocket, token)
        
    except Exception as e:
        logger.error(f"WebSocket endpoint error: {str(e)}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error", 
                "message": f"Connection failed: {str(e)}"
            })
            await websocket.close(code=1011, reason="Internal error")
        except Exception as close_error:
            logger.error(f"Failed to close WebSocket properly: {str(close_error)}")
            pass

@router.get("/health")
async def health_check():
    """Health check endpoint for the WebSocket service."""
    return {"status": "ok", "service": "websocket"}

@router.get("/info")
async def websocket_info():
    """Get WebSocket connection information."""
    return {
        "websocket": True,
        "endpoint": "/ws/chat",
        "protocol": "ws:// or wss://",
        "message_format": "JSON",
        "authentication": "token (query parameter)"
    }
