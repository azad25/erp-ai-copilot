import requests
import websockets
import asyncio
import json
import logging
from urllib.parse import urljoin

# Enable debug logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebSocketTester:
    def __init__(self, base_url="http://localhost"):
        self.base_url = base_url.rstrip('/')
        self.ws_url = self.base_url.replace('http', 'ws')  # Convert to WebSocket URL
        self.token = None
        
    async def get_auth_token(self, email="admin@unibaseerp.com", password="admin123"):
        """Get authentication token."""
        url = f"{self.base_url}/api/v1/auth/login"
        try:
            response = requests.post(url, json={"email": email, "password": password})
            response.raise_for_status()
            self.token = response.json()['data']['access_token']
            logger.info(f"Successfully obtained auth token: {self.token[:10]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to get auth token: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False
    
    async def test_websocket_connection(self):
        """Test WebSocket connection with authentication."""
        if not self.token:
            logger.error("No authentication token available")
            return False
            
        ws_url = f"{self.ws_url}/ws/chat?token={self.token}"
        logger.info(f"Connecting to WebSocket: {ws_url}")
        
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as websocket:
                logger.info("✅ WebSocket connection established")
                
                # Wait for connection confirmation
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    logger.info(f"Connection response: {response}")
                    
                    # Send test message
                    test_message = {
                        "type": "ai_chat",
                        "data": {
                            "message": "Hello, can you hear me?",
                            "context": {
                                "application": "erp-suite",
                                "version": "1.0.0",
                                "environment": "development"
                            },
                            "session_id": "test-session-123"
                        },
                        "timestamp": str(asyncio.get_event_loop().time())
                    }
                    await websocket.send(json.dumps(test_message))
                    logger.info(f"Sent message: {test_message}")
                    
                    # Wait for response
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    logger.info(f"Received response: {response}")
                    
                    return True
                    
                except asyncio.TimeoutError:
                    logger.error("Timeout waiting for WebSocket response")
                    return False
                    
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            return False

async def main():
    tester = WebSocketTester("http://localhost")  # Test through nginx proxy
    
    # Get auth token
    if not await tester.get_auth_token():
        logger.error("Authentication failed, cannot proceed with WebSocket test")
        return
    
    # Test WebSocket connection
    if await tester.test_websocket_connection():
        logger.info("✅ WebSocket test completed successfully")
    else:
        logger.error("❌ WebSocket test failed")

if __name__ == "__main__":
    asyncio.run(main())
