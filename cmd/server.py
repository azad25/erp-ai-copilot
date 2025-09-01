#!/usr/bin/env python3
"""
ERP AI Copilot - Server Entry Point

This is the main entry point for the ERP AI Copilot server.
It supports different server modes:
- simple: Basic REST API with LLM service
- full: Complete service with REST API, gRPC, and WebSockets
- grpc: gRPC service only
- interactive: Command-line interface

Usage:
    python -m cmd.server --mode simple
    python -m cmd.server --mode full
    python -m cmd.server --mode grpc
    python -m cmd.server --mode interactive
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Setup local environment
from config.local_config import setup_local_environment
setup_local_environment()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import the server orchestrator
from app.server.orchestrator import AICopilotServer


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="ERP AI Copilot Server")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["simple", "full", "grpc", "interactive"],
        default="simple",
        help="Server mode (simple, full, grpc, or interactive)"
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["ollama", "gemini"],
        default="ollama",
        help="LLM provider to use (ollama or gemini)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the server to"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on"
    )
    return parser.parse_args()


async def interactive_mode():
    """Run in interactive mode for testing."""
    from app.services.llm_service import LLMService
    
    print("🚀 Starting AI Copilot in interactive mode...")
    print("Type 'exit' or 'quit' to exit\n")
    
    llm_service = LLMService()
    
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ("exit", "quit"):
                break
                
            if not user_input:
                continue
                
            # Create a simple chat request
            messages = [{"role": "user", "content": user_input}]
            
            # Stream the response
            print("\nAssistant: ", end="", flush=True)
            
            response = await llm_service.generate(
                messages=messages,
                model="unibase-erp",
                stream=True
            )
            
            async for chunk in response:
                print(chunk.choices[0].delta.get("content", ""), end="", flush=True)
            
            print("\n")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {str(e)}")


async def main():
    """Main entry point for the server."""
    args = parse_arguments()
    
    if args.mode == "interactive":
        await interactive_mode()
        return
    
    try:
        # Create and start the server
        server = AICopilotServer(
            mode=args.mode, 
            config_path=args.config,
            llm_provider=args.provider
        )
        
        # Initialize the server
        await server.initialize()
        
        # Run the server
        if args.mode in ["simple", "full"]:
            # For web server modes, use the main FastAPI app with WebSocket support
            import uvicorn
            from app.main import app
            
            config = uvicorn.Config(
                app=app,
                host=args.host,
                port=args.port,
                log_level="info"
            )
            
            uvicorn_server = uvicorn.Server(config)
            await uvicorn_server.serve()
        else:
            # For gRPC mode, use the server's start method
            await server.start()
            
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise
    finally:
        if 'server' in locals():
            await server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
