#!/usr/bin/env python3
"""
ERP AI Copilot - Unified Server Entry Point

This is the unified server entry point for the ERP AI Copilot system.
It combines functionality in multiple modes:
- Simple mode: Basic LLM service with FastAPI
- Full mode: Complete multi-agent system  
- Interactive mode: Command-line interface
- gRPC mode: gRPC server support

Usage:
    python cmd/server.py --mode simple
    python cmd/server.py --mode full --provider ollama
    python cmd/server.py --mode interactive
    python cmd/server.py --mode grpc
"""

import asyncio
import argparse
import os
import sys
import json
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Setup local environment
from config.local_config import setup_local_environment
setup_local_environment()

from app.services.llm_service import LLMService, LLMRequest, LLMMessage
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import structlog
import grpc

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Create minimal protobuf classes for gRPC
class MinimalAIProto:
    class ChatRequest:
        def __init__(self, message="", context=None, session_id="", user_id="", conversation_id="", agent_type="", model="", temperature=0.1, max_tokens=500):
            self.message = message
            self.context = context or {}
            self.session_id = session_id
            self.user_id = user_id
            self.conversation_id = conversation_id
            self.agent_type = agent_type
            self.model = model
            self.temperature = temperature
            self.max_tokens = max_tokens
    
    class ChatResponse:
        def __init__(self, content="", message_id="", timestamp=0, conversation_id="", response_type="text", metadata="", error="", suggested_actions=""):
            self.content = content
            self.message_id = message_id
            self.timestamp = timestamp
            self.conversation_id = conversation_id
            self.response_type = response_type
            self.metadata = metadata
            self.error = error
            self.suggested_actions = suggested_actions
    
    class HealthCheckRequest:
        def __init__(self, check_type=""):
            self.check_type = check_type
    
    class HealthCheckResponse:
        def __init__(self, status="", message="", timestamp=0, version="", details=""):
            self.status = status
            self.message = message
            self.timestamp = timestamp
            self.version = version
            self.details = details

class AIServiceServicer:
    """gRPC service implementation for AI Copilot."""
    
    def __init__(self, llm_service):
        self.llm_service = llm_service
    
    def Chat(self, request, context):
        """Handle chat requests."""
        try:
            llm_request = LLMRequest(
                messages=[LLMMessage(role="user", content=request.message)],
                model=request.model or "unibase-erp",
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(self.llm_service.generate(llm_request))
            finally:
                loop.close()
            
            return MinimalAIProto.ChatResponse(
                content=response.content,
                message_id=f"msg_{int(asyncio.get_event_loop().time())}",
                timestamp=int(asyncio.get_event_loop().time()),
                conversation_id=request.conversation_id or "",
                response_type="text",
                metadata=json.dumps({"provider": response.metadata.get("provider", "unknown")})
            )
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))
    
    def StreamChat(self, request, context):
        """Handle streaming chat requests."""
        try:
            llm_request = LLMRequest(
                messages=[LLMMessage(role="user", content=request.message)],
                model=request.model or "unibase-erp",
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(self.llm_service.generate(llm_request))
                yield MinimalAIProto.ChatResponse(
                    content=response.content,
                    message_id=f"msg_{int(asyncio.get_event_loop().time())}",
                    timestamp=int(asyncio.get_event_loop().time()),
                    conversation_id=request.conversation_id or "",
                    response_type="text"
                )
            finally:
                loop.close()
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))
    
    def HealthCheck(self, request, context):
        """Handle health check requests."""
        try:
            return MinimalAIProto.HealthCheckResponse(
                status="healthy",
                message="AI Copilot service is running",
                timestamp=int(asyncio.get_event_loop().time()),
                version="1.0.0",
                details="Service is operational and connected to LLM providers"
            )
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, str(e))


class UnifiedAICopilot:
    """Unified AI Copilot service supporting multiple modes."""
    
    def __init__(self, mode: str = "simple"):
        """Initialize the unified AI Copilot service."""
        self.mode = mode
        self.llm_service = None
        self.master_agent = None
        self.app = None
        self.grpc_server = None
        
    async def initialize(self, provider: str = None, model: str = None):
        """Initialize the service components based on mode."""
        print(f"🚀 Initializing AI Copilot Service in {self.mode} mode...")
        
        try:
            # Initialize LLM service
            self.llm_service = LLMService()
            print("✅ LLM Service initialized")
            
            # Check available providers and models
            providers = self.llm_service.get_available_providers()
            models = self.llm_service.get_available_models()
            print(f"📡 Available LLM providers: {providers}")
            print(f"🤖 Available models: {models}")
            
            # Initialize based on mode
            if self.mode == "full":
                await self._initialize_full_mode(provider, model)
            elif self.mode == "grpc":
                self._initialize_grpc_mode()
            
            # Create FastAPI app for all modes except pure gRPC
            if self.mode != "grpc":
                self.app = self.create_api_app()
                print("✅ FastAPI app created")
            
            print(f"🎉 AI Copilot Service ({self.mode} mode) initialized successfully!")
            
        except Exception as e:
            print(f"❌ Failed to initialize: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    async def _initialize_full_mode(self, provider: str = None, model: str = None):
        """Initialize full mode with multi-agent system."""
        try:
            from app.agents.master_agent import MasterAgent
            
            # Use default provider if not specified
            if not provider:
                provider = os.getenv("DEFAULT_LLM_PROVIDER", "ollama")
                
            print(f"📡 Using LLM Provider: {provider}")
            
            # Initialize master agent
            self.master_agent = MasterAgent(self.llm_service)
            print("✅ Master Agent initialized")
        except ImportError as e:
            print(f"⚠️ Full mode requires complete agent system: {e}")
            print("🔄 Falling back to simple mode")
            self.mode = "simple"
    
    def _initialize_grpc_mode(self):
        """Initialize gRPC mode."""
        self.grpc_server = grpc.server(ThreadPoolExecutor(max_workers=10))
        servicer = AIServiceServicer(self.llm_service)
        print("✅ gRPC server initialized")
    
    async def process_query(self, query: str) -> str:
        """Process a natural language query through the system."""
        if self.mode == "full" and self.master_agent:
            try:
                from app.agents.base_agent import AgentRequest
                request = AgentRequest(message=query)
                response = await self.master_agent.process_request(request)
                return response.content
            except Exception as e:
                return f"Error processing query: {str(e)}"
        else:
            # Simple mode - direct LLM interaction
            try:
                llm_request = LLMRequest(
                    messages=[LLMMessage(role="user", content=query)],
                    model="unibase-erp",
                    temperature=0.1,
                    max_tokens=500
                )
                response = await self.llm_service.generate(llm_request)
                return response.content
            except Exception as e:
                return f"Error processing query: {str(e)}"
    
    def create_api_app(self) -> FastAPI:
        """Create FastAPI application based on mode."""
        if self.mode == "full":
            return self._create_full_app()
        else:
            return self._create_simple_app()
    
    def _create_simple_app(self) -> FastAPI:
        """Create simple FastAPI app for basic LLM service."""
        app = FastAPI(
            title=f"AI Copilot Service ({self.mode.title()} Mode)",
            description="AI Copilot service for ERP systems",
            version="1.0.0"
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        @app.get("/")
        async def root():
            return {
                "message": f"AI Copilot Service ({self.mode.title()} Mode)",
                "status": "running",
                "mode": self.mode,
                "providers": self.llm_service.get_available_providers() if self.llm_service else [],
                "models": self.llm_service.get_available_models() if self.llm_service else {}
            }
        
        @app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "service": "AI Copilot Service",
                "mode": self.mode,
                "llm_service": "available" if self.llm_service else "unavailable"
            }
        
        @app.post("/chat")
        async def chat(request: Request):
            try:
                body = await request.json()
                message = body.get("message", "")
                model = body.get("model", "unibase-erp")
                
                if not message:
                    return {"error": "Message is required"}
                
                # Create LLM request
                llm_request = LLMRequest(
                    messages=[LLMMessage(role="user", content=message)],
                    model=model,
                    temperature=0.1,
                    max_tokens=500
                )
                
                # Generate response
                response = await self.llm_service.generate(llm_request)
                
                return {
                    "success": True,
                    "response": response.content,
                    "model": response.model,
                    "provider": response.metadata.get("provider", "unknown"),
                    "tokens_used": response.tokens_used
                }
                
            except Exception as e:
                logger.error("Chat error", error=str(e))
                return {"error": str(e)}
        
        @app.post("/query")
        async def query(request: Request):
            try:
                body = await request.json()
                user_query = body.get("query", "")
                if not user_query:
                    return {"error": "Query is required"}
                    
                response = await self.process_query(user_query)
                return {"query": user_query, "response": response}
                
            except Exception as e:
                return {"error": str(e)}
        
        @app.get("/models")
        async def get_models():
            if not self.llm_service:
                return {"error": "LLM service not initialized"}
            
            return {
                "providers": self.llm_service.get_available_providers(),
                "models": self.llm_service.get_available_models()
            }
        
        return app
    
    def _create_full_app(self) -> FastAPI:
        """Create full FastAPI app with enterprise features."""
        try:
            # Import the full app from app.main
            from app.main import app
            return app
        except ImportError:
            print("⚠️ Full app not available, using simple app")
            return self._create_simple_app()
    
    async def start_server(self, host: str = "0.0.0.0", port: int = 8003):
        """Start the FastAPI server."""
        if not self.app:
            raise RuntimeError("App not initialized. Call initialize() first.")
        
        print(f"🌐 Starting HTTP server on {host}:{port}")
        
        # Start gRPC server if available
        if self.grpc_server:
            grpc_port = int(os.getenv('GRPC_PORT', 50055))
            print(f"🔌 gRPC server available on port {grpc_port}")
        
        # Start HTTP server
        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            log_level="info",
            reload=False
        )
        
        server = uvicorn.Server(config)
        await server.serve()


async def interactive_mode(copilot: UnifiedAICopilot):
    """Run in interactive mode for testing."""
    print("🎯 Interactive Mode - Type 'exit' to quit")
    print("💡 Try asking: 'What is our current inventory status?' or 'Show me sales trends'")
    
    while True:
        try:
            query = input("\n🤖 Enter your query: ").strip()
            if query.lower() in ['exit', 'quit', 'q']:
                break
                
            if not query:
                continue
                
            print("🔄 Processing...")
            response = await copilot.process_query(query)
            print(f"📊 Response: {response}")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")


async def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(description="ERP AI Copilot - Unified Server")
    parser.add_argument("--mode", choices=["simple", "full", "interactive", "grpc"], 
                       default="simple", help="Run mode")
    parser.add_argument("--provider", help="LLM provider (ollama, openai, anthropic)")
    parser.add_argument("--model", help="Specific model to use")
    parser.add_argument("--host", default="0.0.0.0", help="API host")
    parser.add_argument("--port", type=int, default=8003, help="API port")
    
    args = parser.parse_args()
    
    copilot = UnifiedAICopilot(mode=args.mode)
    
    try:
        await copilot.initialize(provider=args.provider, model=args.model)
        
        if args.mode == "interactive":
            await interactive_mode(copilot)
        elif args.mode == "grpc":
            print("🔌 gRPC mode - Server ready but requires proper protobuf implementation")
            # In production, you would start the gRPC server here
            await asyncio.sleep(3600)  # Keep alive
        else:
            await copilot.start_server(host=args.host, port=args.port)
            
    except KeyboardInterrupt:
        print("\n🛑 Service stopped by user")
    except Exception as e:
        print(f"❌ Service failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())