"""
REST API implementation for the AI Copilot server.
"""
import structlog
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import json
import logging
from typing import Dict, Any, Optional

from app.services.llm_service import LLMService, LLMRequest, LLMMessage
from app.server.config import ServerConfig

class RestAPI:
    """REST API server for AI Copilot."""
    
    def __init__(self, llm_service: LLMService, config: ServerConfig):
        """Initialize the REST API server.
        
        Args:
            llm_service: Instance of LLMService
            config: Server configuration
        """
        self.llm_service = llm_service
        self.config = config
        self.app = self._create_app()
        self._setup_middleware()
        self._setup_routes()
        self._setup_exception_handlers()
    
    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(
            title="AI Copilot API",
            description="REST API for AI Copilot service",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        return app
    
    def _setup_middleware(self) -> None:
        """Configure middleware for the FastAPI app."""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Logging middleware
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            logger = structlog.get_logger("api")
            logger.info(
                "Request received",
                method=request.method,
                path=request.url.path,
                query_params=dict(request.query_params)
            )
            
            try:
                response = await call_next(request)
                logger.info(
                    "Response sent",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code
                )
                return response
            except Exception as e:
                logger.error(
                    "Request failed",
                    method=request.method,
                    path=request.url.path,
                    error=str(e)
                )
                raise
    
    def _setup_routes(self) -> None:
        """Define API routes."""
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "service": "ai-copilot",
                "version": "1.0.0"
            }
            
        @self.app.post("/v1/chat/completions")
        async def chat_completion(request: Dict[str, Any]):
            """Handle chat completion requests."""
            try:
                # Extract messages from request
                messages = request.get("messages", [])
                if not messages:
                    raise HTTPException(status_code=400, detail="No messages provided")
                
                # Create LLM request
                llm_request = LLMRequest(
                    messages=[
                        LLMMessage(role=msg.get("role", "user"), 
                                 content=msg.get("content", ""))
                        for msg in messages
                    ],
                    model=request.get("model", "unibase-erp"),
                    temperature=request.get("temperature", 0.7),
                    max_tokens=request.get("max_tokens", 2000),
                    stream=request.get("stream", False)
                )
                
                # Generate response
                if llm_request.stream:
                    return await self._handle_streaming_response(llm_request)
                else:
                    response = await self.llm_service.generate(llm_request)
                    return self._format_chat_response(response)
                    
            except Exception as e:
                logging.error(f"Error in chat completion: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/v1/models")
        async def list_models():
            """List available models."""
            try:
                models = self.llm_service.get_available_models()
                providers = self.llm_service.get_available_providers()
                
                return {
                    "object": "list",
                    "data": [
                        {
                            "id": model_id,
                            "object": "model",
                            "provider": provider,
                            "capabilities": ["chat"]
                        }
                        for provider, models in models.items()
                        for model_id in models
                    ]
                }
            except Exception as e:
                logging.error(f"Error listing models: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def _setup_exception_handlers(self) -> None:
        """Configure exception handlers."""
        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {
                        "message": str(exc.detail),
                        "type": "api_error",
                        "code": exc.status_code
                    }
                }
            )
            
        @self.app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request: Request, exc: RequestValidationError):
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "message": "Validation error",
                        "type": "validation_error",
                        "details": exc.errors()
                    }
                }
            )
            
        @self.app.exception_handler(Exception)
        async def global_exception_handler(request: Request, exc: Exception):
            logging.error(f"Unhandled exception: {str(exc)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "message": "Internal server error",
                        "type": "internal_error",
                        "code": 500
                    }
                }
            )
    
    async def _handle_streaming_response(self, llm_request: LLMRequest):
        """Handle streaming response for chat completions."""
        from fastapi.responses import StreamingResponse
        import json
        
        async def generate():
            try:
                # Send initial response with model info
                initial_response = {
                    'id': 'chatcmpl-123',
                    'object': 'chat.completion.chunk',
                    'created': 1694268190,
                    'model': 'unibase-erp',
                    'choices': [{
                        'index': 0,
                        'delta': {
                            'role': 'assistant',
                            'content': ''
                        },
                        'finish_reason': None
                    }]
                }
                yield f"data: {json.dumps(initial_response)}\n\n"
                
                # Stream responses
                async for chunk in await self.llm_service.agenerate(llm_request):
                    if chunk.content:
                        chunk_response = {
                            'id': 'chatcmpl-123',
                            'object': 'chat.completion.chunk',
                            'created': 1694268190,
                            'model': llm_request.model,
                            'choices': [{
                                'index': 0,
                                'delta': {'content': chunk.content},
                                'finish_reason': None
                            }]
                        }
                        yield f"data: {json.dumps(chunk_response)}\n\n"
                
                # Send completion message
                completion_response = {
                    'id': 'chatcmpl-123',
                    'object': 'chat.completion.chunk',
                    'created': 1694268190,
                    'model': 'unibase-erp',
                    'choices': [{
                        'index': 0,
                        'delta': {},
                        'finish_reason': 'stop'
                    }]
                }
                yield f"data: {json.dumps(completion_response)}\n\n"
                
            except Exception as e:
                logging.error(f"Error in streaming response: {str(e)}")
                error_response = {
                    'error': {
                        'message': str(e),
                        'type': 'stream_error'
                    }
                }
                yield f"data: {json.dumps(error_response)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    def _format_chat_response(self, response: Any) -> Dict[str, Any]:
        """Format chat response in OpenAI-compatible format."""
        return {
            "id": f"chatcmpl-{response.id}",
            "object": "chat.completion",
            "created": int(response.created_at.timestamp()),
            "model": response.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response.content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": response.usage.get("prompt_tokens", 0),
                "completion_tokens": response.usage.get("completion_tokens", 0),
                "total_tokens": response.usage.get("total_tokens", 0)
            }
        }
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self.app
