#!/usr/bin/env python3
"""
Test script for Ollama integration with unibase-erp model
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from app.services.llm_service import LLMService, LLMRequest, LLMMessage


async def test_ollama_integration():
    """Test the Ollama integration with unibase-erp model."""
    print("🧪 Testing Ollama Integration with unibase-erp model...")
    
    try:
        # Initialize LLM service
        llm_service = LLMService()
        
        # Check available providers
        providers = llm_service.get_available_providers()
        print(f"✅ Available providers: {providers}")
        
        # Check available models
        models = llm_service.get_available_models()
        print(f"✅ Available models: {models}")
        
        # Test with unibase-erp model
        print("\n🤖 Testing unibase-erp model...")
        
        # Create test request
        request = LLMRequest(
            messages=[
                LLMMessage(role="user", content="What is the current inventory status?")
            ],
            model="unibase-erp",
            temperature=0.1,
            max_tokens=500,
            system_prompt="You are an AI assistant for an ERP system. Answer the user's question based only on the following context. If the context doesn't contain the answer, say you don't know. Context: ERP system with inventory management, sales tracking, and financial reporting."
        )
        
        # Generate response
        print("🔄 Generating response...")
        response = await llm_service.generate(request)
        
        print(f"✅ Response generated successfully!")
        print(f"📝 Content: {response.content}")
        print(f"🤖 Model: {response.model}")
        print(f"🔢 Tokens used: {response.tokens_used}")
        print(f"🏷️  Provider: {response.metadata.get('provider', 'unknown')}")
        
        # Test streaming
        print("\n🌊 Testing streaming response...")
        print("🔄 Streaming response:")
        
        async for chunk in llm_service.generate_stream(request):
            print(chunk, end="", flush=True)
        
        print("\n✅ Streaming test completed!")
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_health_check():
    """Test health check for Ollama service."""
    print("\n🏥 Testing Ollama health check...")
    
    try:
        from app.services.llm_service import llm_service
        
        # Check if Ollama provider is available
        if "ollama" in llm_service.providers:
            ollama_provider = llm_service.providers["ollama"]
            
            # Test connection
            print("🔄 Testing Ollama connection...")
            
            # Try to list models
            if hasattr(ollama_provider, 'client') and ollama_provider.client:
                try:
                    models = await ollama_provider.client.list()
                    available_models = [model['name'] for model in models.get('models', [])]
                    print(f"✅ Ollama connection successful!")
                    print(f"📚 Available models: {available_models}")
                    
                    if "unibase-erp" in available_models:
                        print("🎯 unibase-erp model found!")
                    else:
                        print("⚠️  unibase-erp model not found in available models")
                        
                except Exception as e:
                    print(f"❌ Failed to list models: {str(e)}")
            else:
                print("❌ Ollama client not initialized")
        else:
            print("❌ Ollama provider not available")
            
    except Exception as e:
        print(f"❌ Health check failed: {str(e)}")
        import traceback
        traceback.print_exc()


async def main():
    """Main test function."""
    print("🚀 Starting Ollama Integration Tests...")
    print("=" * 50)
    
    # Test health check first
    await test_health_check()
    
    print("\n" + "=" * 50)
    
    # Test full integration
    success = await test_ollama_integration()
    
    print("\n" + "=" * 50)
    
    if success:
        print("🎉 All tests passed! Ollama integration is working correctly.")
    else:
        print("💥 Some tests failed. Check the error messages above.")
    
    return success


if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
