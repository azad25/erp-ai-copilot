"""
Server orchestrator for the AI Copilot service.

This module provides the main orchestration logic for the AI Copilot server,
managing the lifecycle of all server components including REST API, gRPC service,
and WebSocket connections.
"""
import asyncio
import signal
import logging
from typing import Dict, Any, Optional, List

from app.services.llm_service import LLMService
from app.server.config import ServerConfig
from app.server.grpc.service import AIGrpcService
from app.server.rest.api import RestAPI
from app.api.websocket.router import router as websocket_router

class AICopilotServer:
    """Main server orchestrator for AI Copilot service."""
    
    def __init__(self, mode: str = "simple", config_path: Optional[str] = None, llm_provider: str = "ollama"):
        """Initialize the AI Copilot server.
        
        Args:
            mode: Server mode (simple, full, grpc, interactive)
            config_path: Optional path to config file
            llm_provider: LLM provider to use (ollama or gemini)
        """
        self.mode = mode
        self.llm_provider = llm_provider.lower()
        self.config = ServerConfig(mode=mode, config_path=config_path)
        self.llm_service: Optional[LLMService] = None
        self.grpc_service: Optional[AIGrpcService] = None
        self.rest_api: Optional[RestAPI] = None
        self.running = False
        self._shutdown_event = asyncio.Event()
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_shutdown_signal)
    
    def _handle_shutdown_signal(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logging.info(f"Received signal {signal.Signals(signum).name}, shutting down...")
        self._shutdown_event.set()
    
    async def initialize(self) -> None:
        """Initialize all server components."""
        logging.info("Initializing AI Copilot server...")
        
        try:
            # Initialize database connections
            from app.database.connection import init_database
            await init_database()
            logging.info("Database connections initialized")
            
            # Initialize token cache service
            from app.services.token_cache_service import initialize_token_cache_service
            from app.database.connection import db_manager
            redis_client = db_manager.get_redis_client()
            initialize_token_cache_service(redis_client)
            logging.info("Token cache service initialized")
            
            # Initialize JWT service
            from app.services.jwt_service import initialize_jwt_service
            from app.core.config import settings
            initialize_jwt_service(settings.JWT_SECRET)
            logging.info("JWT service initialized")
            
            # Initialize LLM service with the specified provider
            from app.services.llm_service import initialize_llm_service
            # Use environment variable if no provider specified via command line
            provider = self.llm_provider or settings.DEFAULT_LLM_PROVIDER
            self.llm_service = initialize_llm_service(provider=provider)
            logging.info(f"LLM service initialized with provider: {provider}")
            logging.info(f"Available providers: {', '.join(self.llm_service.get_available_providers())}")
            
            # Initialize components based on mode
            if self.mode in ["simple", "full"]:
                self._initialize_rest_api()
                logging.info("REST API initialized")
                
                if self.mode == "full":
                    self._initialize_grpc_service()
                    logging.info("gRPC service initialized")
            
            # Initialize WebSocket router
            self._initialize_websocket_router()
            logging.info("WebSocket router initialized")
            
            logging.info("Server initialization complete")
            
        except Exception as e:
            logging.error(f"Failed to initialize server: {str(e)}")
            await self.shutdown()
            raise
    
    def _initialize_rest_api(self) -> None:
        """Initialize the REST API server."""
        if not self.llm_service:
            raise ValueError("LLM service must be initialized before REST API")
        self.rest_api = RestAPI(self.llm_service, self.config)
    
    def _initialize_grpc_service(self) -> None:
        """Initialize the gRPC service."""
        if not self.llm_service:
            raise ValueError("LLM service must be initialized before gRPC service")
        self.grpc_service = AIGrpcService(self.llm_service, self.config)
    
    def _initialize_websocket_router(self) -> None:
        """Initialize the WebSocket router."""
        if not self.llm_service:
            raise ValueError("LLM service must be initialized before WebSocket router")
        # The WebSocket router is already imported and will be used by FastAPI
    
    async def start(self) -> None:
        """Start all server components."""
        if self.running:
            logging.warning("Server is already running")
            return
        
        try:
            # Start gRPC server if enabled
            if self.grpc_service:
                await self.grpc_service.start()
            
            # Start REST API server
            if self.rest_api:
                import uvicorn
                
                config = self.config.get_rest_settings()
                host = config.get("host", "0.0.0.0")
                port = config.get("port", 8000)
                
                # Run the FastAPI app in a separate task
                server_config = uvicorn.Config(
                    app=self.rest_api.app,
                    host=host,
                    port=port,
                    log_level="info"
                )
                server = uvicorn.Server(server_config)
                
                # Start the server in the background
                server_task = asyncio.create_task(server.serve())
                logging.info(f"REST API server started on http://{host}:{port}")
            
            # Set running flag
            self.running = True
            
            # Keep the server running until shutdown is requested
            await self._shutdown_event.wait()
            
        except Exception as e:
            logging.error(f"Failed to start server: {str(e)}")
            await self.shutdown()
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """Shut down all server components gracefully."""
        if not self.running:
            return
        
        logging.info("Shutting down server...")
        
        # Shut down gRPC server if running
        if self.grpc_service:
            await self.grpc_service.stop()
            logging.info("gRPC server stopped")
        
        # Set shutdown event
        self._shutdown_event.set()
        self.running = False
        
        logging.info("Server shutdown complete")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.shutdown()
