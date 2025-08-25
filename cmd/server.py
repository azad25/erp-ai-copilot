"""
ERP AI Copilot - Server Entry Point

This is the main server entry point for the ERP AI Copilot system.
It initializes the LLM service and starts the application.

Usage:
    python cmd/server.py
    
Or with specific configuration:
    python cmd/server.py --provider ollama --model llama2
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.config.llm_config import LLMConfig
from app.services.llm_service import LLMService
from app.agents.master_agent import MasterAgent
from fastapi import FastAPI
import uvicorn


class ERPAICopilot:
    """Main ERP AI Copilot application class."""
    
    def __init__(self):
        """Initialize the ERP AI Copilot system."""
        self.config = LLMConfig()
        self.llm_service = LLMService()
        self.master_agent = None
        
    async def initialize(self, provider: str = None, model: str = None):
        """Initialize the system with specified LLM provider."""
        print("🚀 Initializing ERP AI Copilot...")
        
        # Validate provider
        if provider:
            provider_config = self.config.get_provider_config(provider)
            if not provider_config:
                available = list(self.config.get_available_providers().keys())
                raise ValueError(f"Provider '{provider}' not available. Available: {available}")
        else:
            # Use default provider
            provider = os.getenv("DEFAULT_LLM_PROVIDER", "ollama")
            
        print(f"📡 Using LLM Provider: {provider}")
        
        # Initialize master agent
        self.master_agent = MasterAgent(
            llm_service=self.llm_service,
            default_model=model or self.config.get_provider_config(provider).default_model
        )
        
        print("✅ ERP AI Copilot initialized successfully!")
        
    async def process_query(self, query: str) -> str:
        """Process a natural language query through the system."""
        if not self.master_agent:
            raise RuntimeError("System not initialized. Call initialize() first.")
            
        try:
            response = await self.master_agent.execute({
                "query": query,
                "user_id": "system",
                "context": {}
            })
            return response.get("response", "No response generated")
        except Exception as e:
            return f"Error processing query: {str(e)}"
            
    def create_api_app(self) -> FastAPI:
        """Create FastAPI application for the ERP AI Copilot."""
        app = FastAPI(
            title="ERP AI Copilot API",
            description="AI-powered ERP system with natural language interface",
            version="1.0.0"
        )
        
        @app.on_event("startup")
        async def startup_event():
            """Initialize system on startup."""
            await self.initialize()
            
        @app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "message": "ERP AI Copilot API",
                "status": "running",
                "providers": list(self.config.get_available_providers().keys())
            }
            
        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "service": "ERP AI Copilot"}
            
        @app.post("/query")
        async def process_query_endpoint(query: dict):
            """Process a natural language query."""
            try:
                user_query = query.get("query", "")
                if not user_query:
                    return {"error": "Query is required"}
                    
                response = await self.process_query(user_query)
                return {"query": user_query, "response": response}
                
            except Exception as e:
                return {"error": str(e)}
                
        @app.get("/providers")
        async def get_providers():
            """Get available LLM providers."""
            return self.config.get_available_providers()
            
        return app


async def interactive_mode(copilot: ERPAICopilot):
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
    parser = argparse.ArgumentParser(description="ERP AI Copilot")
    parser.add_argument("--provider", help="LLM provider (ollama, openai, anthropic)")
    parser.add_argument("--model", help="Specific model to use")
    parser.add_argument("--mode", choices=["api", "interactive"], default="interactive", 
                       help="Run mode")
    parser.add_argument("--host", default="0.0.0.0", help="API host")
    parser.add_argument("--port", type=int, default=8000, help="API port")
    
    args = parser.parse_args()
    
    copilot = ERPAICopilot()
    
    try:
        await copilot.initialize(provider=args.provider, model=args.model)
        
        if args.mode == "api":
            print(f"🌐 Starting API server on {args.host}:{args.port}")
            app = copilot.create_api_app()
            uvicorn.run(app, host=args.host, port=args.port)
        else:
            await interactive_mode(copilot)
            
    except Exception as e:
        print(f"❌ Failed to start: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())