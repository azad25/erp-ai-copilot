"""
Startup script for the AI Copilot service.
This script starts both the FastAPI HTTP server and the gRPC server.
"""
import asyncio
import uvicorn
import logging
from app.config.settings import get_settings
from app.api.grpc import start_grpc_server, stop_grpc_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_servers():
    """Start both HTTP and gRPC servers."""
    settings = get_settings()
    
    try:
        # Start gRPC server in the background
        logger.info("Starting gRPC server...")
        await start_grpc_server()
        
        # Start FastAPI server
        logger.info("Starting FastAPI server...")
        config = uvicorn.Config(
            "app.main:app",
            host=settings.service.host,
            port=settings.service.port,
            log_level="info",
            reload=settings.service.debug,
        )
        server = uvicorn.Server(config)
        await server.serve()
        
    except Exception as e:
        logger.error(f"Failed to start servers: {e}")
        raise
    finally:
        # Cleanup
        await stop_grpc_server()

if __name__ == "__main__":
    asyncio.run(start_servers())
