"""gRPC router for AI Copilot service.

This module provides gRPC endpoints for the AI Copilot service to integrate with the API gateway.
"""

import asyncio
import grpc
import time
from fastapi import APIRouter
import structlog
from concurrent import futures

from app.config.settings import get_settings
from app.agents.master_agent import MasterAgent

# Import generated gRPC code
from app.proto.ai_copilot_pb2 import ChatRequest, ChatResponse, HealthCheckRequest, HealthCheckResponse
from app.proto.ai_copilot_pb2_grpc import AICopilotServicer, add_AICopilotServicer_to_server

logger = structlog.get_logger(__name__)
settings = get_settings()

# Create router
grpc_router = APIRouter()

# Define gRPC servicer
class AICopilotServicerImpl(AICopilotServicer):
    """gRPC servicer for AI Copilot service."""
    
    def __init__(self):
        """Initialize the servicer."""
        self.master_agent = MasterAgent()
    
    async def Chat(self, request, context):
        """Handle chat requests."""
        try:
            # Extract request parameters
            message = request.message
            conversation_id = request.conversation_id
            user_id = request.user_id
            agent_type = request.agent_type
            model = request.model if request.model else None
            temperature = request.temperature if request.temperature else None
            max_tokens = request.max_tokens if request.max_tokens else None
            context_data = request.context if request.context else None
            
            # Log request
            logger.info(
                "gRPC chat request received",
                user_id=user_id,
                conversation_id=conversation_id,
                agent_type=agent_type,
                model=model
            )
            
            # Process request with master agent
            agent_response = await self.master_agent.process_message(
                message=message,
                conversation_id=conversation_id,
                user_id=user_id,
                agent_type=agent_type,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                context=context_data
            )
            
            # Create gRPC response
            response = ChatResponse(
                content=agent_response.get("content", ""),
                conversation_id=conversation_id,
                message_id=agent_response.get("message_id", ""),
                response_type="text",
                timestamp=int(time.time()),
                metadata=agent_response.get("metadata", ""),
                error="",
                suggested_actions=agent_response.get("suggested_actions", "")
            )
            
            # Return response
            return response
            
        except Exception as e:
            logger.error("Error processing gRPC chat request", error=str(e), exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")
            return ChatResponse(
                content="",
                conversation_id=request.conversation_id,
                message_id="",
                response_type="error",
                timestamp=int(time.time()),
                metadata="",
                error=str(e),
                suggested_actions=""
            )
            
    async def StreamChat(self, request, context):
        """Handle streaming chat requests."""
        try:
            # Extract request parameters
            message = request.message
            conversation_id = request.conversation_id
            user_id = request.user_id
            agent_type = request.agent_type
            model = request.model if request.model else None
            temperature = request.temperature if request.temperature else None
            max_tokens = request.max_tokens if request.max_tokens else None
            context_data = request.context if request.context else None
            
            # Log request
            logger.info(
                "gRPC stream chat request received",
                user_id=user_id,
                conversation_id=conversation_id,
                agent_type=agent_type,
                model=model
            )
            
            # Process streaming request with master agent
            async for chunk in self.master_agent.process_stream_message(
                message=message,
                conversation_id=conversation_id,
                user_id=user_id,
                agent_type=agent_type,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                context=context_data
            ):
                # Create gRPC response for each chunk
                response = ChatResponse(
                    content=chunk.get("content", ""),
                    conversation_id=conversation_id,
                    message_id=chunk.get("message_id", ""),
                    response_type="stream",
                    timestamp=int(time.time()),
                    metadata=chunk.get("metadata", ""),
                    error="",
                    suggested_actions=""
                )
                
                # Yield response
                yield response
                
        except Exception as e:
            logger.error("Error processing gRPC stream chat request", error=str(e), exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")
            yield ChatResponse(
                content="",
                conversation_id=request.conversation_id,
                message_id="",
                response_type="error",
                timestamp=int(time.time()),
                metadata="",
                error=str(e),
                suggested_actions=""
            )
    
    async def HealthCheck(self, request, context):
        """Handle health check requests."""
        try:
            # Get settings
            settings = get_settings()
            
            # Log request
            logger.info("gRPC health check request received", check_type=request.check_type)
            
            # Create response
            response = HealthCheckResponse(
                status="ok",
                details="AI Copilot service is healthy",
                version=settings.service.version,
                timestamp=int(time.time())
            )
            
            # Return response
            return response
            
        except Exception as e:
            logger.error("Error processing gRPC health check request", error=str(e), exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")
            return HealthCheckResponse(
                status="error",
                details=f"Error: {str(e)}",
                version="",
                timestamp=int(time.time())
            )

# gRPC server
grpc_server = None

@grpc_router.on_event("startup")
async def start_grpc_server():
    """Start the gRPC server on application startup."""
    global grpc_server
    
    try:
        # Get settings
        settings = get_settings()
        
        # Create a gRPC server
        server = grpc.aio.server(
            options=[
                ("grpc.max_send_message_length", settings.grpc.max_message_size),
                ("grpc.max_receive_message_length", settings.grpc.max_message_size),
                ("grpc.max_concurrent_streams", settings.grpc.max_concurrent_rpcs),
            ],
            maximum_concurrent_rpcs=settings.grpc.max_concurrent_rpcs,
            compression=grpc.Compression.Gzip,
        )
        
        # Add the servicer to the server
        servicer = AICopilotServicerImpl()
        add_AICopilotServicer_to_server(servicer, server)
        
        # Add a secure port with SSL/TLS credentials if in production
        if settings.environment == "production":
            # Load SSL/TLS credentials
            with open(settings.grpc.ssl_cert_path, "rb") as f:
                cert = f.read()
            with open(settings.grpc.ssl_key_path, "rb") as f:
                key = f.read()
            
            # Create server credentials
            server_credentials = grpc.ssl_server_credentials([(key, cert)])
            server.add_secure_port(f"[::]:{settings.grpc.port}", server_credentials)
            logger.info("Starting secure gRPC server", port=settings.grpc.port)
        else:
            # Add insecure port for development
            server.add_insecure_port(f"[::]:{settings.grpc.port}")
            logger.info("Starting insecure gRPC server", port=settings.grpc.port)
        
        # Start the server
        await server.start()
        grpc_server = server
        
        logger.info("gRPC server started successfully", port=settings.grpc.port)
    except Exception as e:
        logger.error("Failed to start gRPC server", error=str(e), exc_info=True)
        raise

@grpc_router.on_event("shutdown")
async def stop_grpc_server():
    """Stop the gRPC server on application shutdown."""
    global grpc_server
    
    if grpc_server is not None:
        try:
            logger.info("Stopping gRPC server")
            
            # Stop accepting new RPCs
            await grpc_server.stop(grace=5.0)
            
            # Wait for all RPCs to finish
            await grpc_server.wait_for_termination()
            
            logger.info("gRPC server stopped successfully")
        except Exception as e:
            logger.error("Error stopping gRPC server", error=str(e), exc_info=True)
        finally:
            grpc_server = None