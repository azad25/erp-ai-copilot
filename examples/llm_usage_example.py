"""
Example usage of the LLM Service

This file demonstrates how to use the LLM service with different providers:
- Ollama for local models
- OpenAI for GPT models
- Anthropic for Claude models

Run this file to test the LLM integration:
    python examples/llm_usage_example.py

For FastAPI endpoint testing:
    python -m uvicorn examples.llm_usage_example:app --reload
"""

import asyncio
import os
import sys
from typing import Dict, Any, List

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.llm_service import LLMService
from config.llm_config import LLMConfig, ModelSelector


class LLMExample:
    """Example class demonstrating LLM service usage."""
    
    def __init__(self):
        """Initialize the LLM service with configuration."""
        self.config = LLMConfig()
        self.llm_service = LLMService()
        
    async def test_all_providers(self):
        """Test all available providers with a simple prompt."""
        providers = self.config.get_available_providers()
        
        print("=== Testing Available LLM Providers ===")
        print(f"Found {len(providers)} providers")
        
        test_prompt = "Explain what an ERP system is in one sentence."
        
        for provider_name, config in providers.items():
            print(f"\n--- Testing {provider_name.upper()} ---")
            print(f"Base URL: {config.base_url}")
            print(f"Default Model: {config.default_model}")
            
            try:
                # Test with streaming disabled
                response = await self.llm_service.generate({
                    "messages": [{"role": "user", "content": test_prompt}],
                    "model": config.default_model,
                    "max_tokens": 100,
                    "temperature": 0.7
                })
                
                print(f"Response: {response['content'][:100]}...")
                print(f"Tokens used: {response.get('usage', {}).get('total_tokens', 'N/A')}")
                
            except Exception as e:
                print(f"Error: {str(e)}")
                
    async def test_erp_query(self):
        """Test with a more complex ERP-related query."""
        print("\n=== Testing ERP Query ===")
        
        erp_prompt = """
        I need to analyze our inventory data. We have:
        - 500 units of Product A with low demand
        - 50 units of Product B with high demand  
        - 1000 units of Product C with stable demand
        
        What recommendations would you give for inventory optimization?
        """
        
        try:
            response = await self.llm_service.generate({
                "messages": [
                    {"role": "system", "content": "You are an ERP system expert. Provide actionable business insights."},
                    {"role": "user", "content": erp_prompt}
                ],
                "model": "llama2",  # Using Ollama's default
                "max_tokens": 200,
                "temperature": 0.5
            })
            
            print("ERP Analysis Response:")
            print(response['content'])
            
        except Exception as e:
            print(f"ERP Query Error: {str(e)}")
            
    async def test_streaming(self):
        """Test streaming responses."""
        print("\n=== Testing Streaming ===")
        
        stream_prompt = "Explain the benefits of implementing an AI-powered ERP system."
        
        try:
            print("Streaming response:")
            chunks = []
            
            async for chunk in self.llm_service.stream({
                "messages": [{"role": "user", "content": stream_prompt}],
                "model": "llama2",
                "max_tokens": 150,
                "temperature": 0.7
            }):
                if chunk.get('content'):
                    chunks.append(chunk['content'])
                    print(chunk['content'], end='', flush=True)
                    
            print("\n\nStreaming completed!")
            
        except Exception as e:
            print(f"Streaming Error: {str(e)}")
            
    def list_available_models(self):
        """List available models for each provider."""
        print("\n=== Available Models ===")
        
        selector = ModelSelector()
        providers = self.config.get_available_providers()
        
        for provider_name in providers.keys():
            print(f"\n{provider_name.upper()} Models:")
            use_cases = ["general", "code", "fast", "analysis"]
            
            for use_case in use_cases:
                recommended = selector.get_recommended_models(provider_name, use_case)
                print(f"  {use_case}: {recommended}")


# FastAPI endpoint example
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="LLM Service API", description="ERP AI Copilot LLM Integration")


class ChatRequest(BaseModel):
    message: str
    provider: str = "ollama"
    model: str = None
    system_prompt: str = "You are an AI assistant for ERP systems."
    max_tokens: int = 150
    temperature: float = 0.7


class ChatResponse(BaseModel):
    response: str
    provider: str
    model: str
    tokens_used: int = 0


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Simple chat endpoint for testing LLM integration."""
    try:
        llm_service = LLMService()
        config = LLMConfig()
        
        # Get model if not specified
        if not request.model:
            provider_config = config.get_provider_config(request.provider)
            if provider_config:
                request.model = provider_config.default_model
            else:
                raise HTTPException(400, f"Provider {request.provider} not available")
        
        response = await llm_service.generate({
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.message}
            ],
            "model": request.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature
        })
        
        return ChatResponse(
            response=response['content'],
            provider=request.provider,
            model=request.model,
            tokens_used=response.get('usage', {}).get('total_tokens', 0)
        )
        
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/providers")
async def get_providers():
    """Get available LLM providers and their configurations."""
    config = LLMConfig()
    providers = config.get_available_providers()
    
    return {
        "providers": {
            name: {
                "base_url": config.base_url,
                "default_model": config.default_model,
                "timeout": config.timeout
            }
            for name, config in providers.items()
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "LLM Integration"}


async def main():
    """Main function to run examples."""
    example = LLMExample()
    
    print("Starting LLM Integration Examples...")
    
    # Check configuration
    example.list_available_models()
    
    # Run tests
    await example.test_all_providers()
    await example.test_erp_query()
    await example.test_streaming()
    
    print("\n=== Examples Complete ===")
    print("To test the FastAPI endpoints:")
    print("  python -m uvicorn examples.llm_usage_example:app --reload")
    print("Then visit: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(main())