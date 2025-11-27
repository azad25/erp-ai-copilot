"""
Test script for HuggingFace provider integration.

Usage:
    python test_huggingface_provider.py
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_huggingface_provider():
    """Test HuggingFace provider functionality."""
    print("🧪 Testing HuggingFace Provider Integration\n")
    
    # Import after loading env
    from app.services.llm_service import LLMService, LLMRequest, LLMMessage
    
    # Check if HF_TOKEN is set
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("❌ HF_TOKEN not found in environment")
        print("   Please set HF_TOKEN in .env file or environment")
        return
    
    print(f"✅ HF_TOKEN found: {hf_token[:10]}...")
    
    # Initialize LLM service
    print("\n📦 Initializing LLM Service...")
    try:
        llm_service = LLMService()
        print("✅ LLM Service initialized")
    except Exception as e:
        print(f"❌ Failed to initialize LLM Service: {e}")
        return
    
    # Check available providers
    print("\n🔍 Available Providers:")
    providers = llm_service.get_available_providers()
    for provider in providers:
        print(f"   - {provider}")
    
    if "huggingface" not in providers:
        print("\n⚠️  HuggingFace provider not available")
        print("   Check if HF_TOKEN is valid")
        return
    
    print("\n✅ HuggingFace provider is available")
    
    # Test models
    print("\n📋 Available HuggingFace Models:")
    models = llm_service.get_available_models().get("huggingface", [])
    for model in models:
        print(f"   - {model}")
    
    # Test simple query
    print("\n🚀 Testing simple query...")
    test_model = "meta-llama/Llama-3.3-70B-Instruct"
    
    request = LLMRequest(
        messages=[
            LLMMessage(role="user", content="What is 2+2? Answer in one word.")
        ],
        model=test_model,
        max_tokens=10,
        temperature=0.1
    )
    
    try:
        print(f"   Model: {test_model}")
        print("   Query: What is 2+2?")
        print("   Waiting for response...")
        
        response = await llm_service.generate(request)
        
        print(f"\n✅ Response received!")
        print(f"   Content: {response.content}")
        print(f"   Model: {response.model}")
        print(f"   Tokens: {response.tokens_used}")
        print(f"   Provider: {response.metadata.get('provider')}")
        
    except Exception as e:
        print(f"\n❌ Query failed: {e}")
        print("\n🔄 Testing fallback mechanism...")
        
        # The service should automatically try fallback providers
        print("   (Fallback should happen automatically)")
    
    # Test streaming
    print("\n🌊 Testing streaming response...")
    
    stream_request = LLMRequest(
        messages=[
            LLMMessage(role="user", content="Count from 1 to 5.")
        ],
        model=test_model,
        max_tokens=50,
        temperature=0.1,
        stream=True
    )
    
    try:
        print("   Streaming: ", end="", flush=True)
        async for chunk in llm_service.generate_stream(stream_request):
            print(chunk, end="", flush=True)
        print("\n✅ Streaming completed!")
        
    except Exception as e:
        print(f"\n❌ Streaming failed: {e}")
    
    # Test fallback
    print("\n🔄 Testing fallback mechanism...")
    print("   Using invalid model to trigger fallback...")
    
    fallback_request = LLMRequest(
        messages=[
            LLMMessage(role="user", content="Hello")
        ],
        model="invalid-model-name",
        max_tokens=20
    )
    
    try:
        response = await llm_service.generate(fallback_request)
        print(f"✅ Fallback worked!")
        print(f"   Response: {response.content[:50]}...")
        print(f"   Provider: {response.metadata.get('provider')}")
    except Exception as e:
        print(f"❌ Fallback failed: {e}")
    
    print("\n" + "="*60)
    print("🎉 Testing completed!")
    print("="*60)


async def test_provider_health():
    """Test provider health check."""
    print("\n🏥 Testing Provider Health Check...")
    
    from app.services.llm_service import LLMService
    
    try:
        llm_service = LLMService()
        health = await llm_service.health_check()
        
        print("\n📊 Provider Health Status:")
        for provider, status in health.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {provider}: {'Healthy' if status else 'Unhealthy'}")
            
    except Exception as e:
        print(f"❌ Health check failed: {e}")


if __name__ == "__main__":
    print("="*60)
    print("  HuggingFace Provider Integration Test")
    print("="*60)
    
    asyncio.run(test_huggingface_provider())
    asyncio.run(test_provider_health())
    
    print("\n💡 Next steps:")
    print("   1. Check the AI Settings page: http://localhost:3000/ai/settings")
    print("   2. Configure providers via the UI")
    print("   3. Test connections using the Test button")
    print("   4. Monitor logs: docker logs erp-ai-copilot -f")
