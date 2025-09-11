#!/usr/bin/env python3
"""
Quick test to verify AI Copilot implementation
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_services():
    print('🧪 Testing AI Copilot Services Implementation...')
    print('=' * 50)
    
    # Test 1: Reasoning Engine
    try:
        from app.services.reasoning_engine import reasoning_engine
        steps = await reasoning_engine.generate_reasoning_steps('test query', 'conv1', 'user1')
        print(f'✅ Reasoning Engine: Generated {len(steps)} reasoning steps')
    except Exception as e:
        print(f'❌ Reasoning Engine error: {e}')
    
    # Test 2: Memory Service
    try:
        from app.services.memory_service import memory_service
        await memory_service.initialize()
        print('✅ Memory Service: Initialized successfully')
    except Exception as e:
        print(f'❌ Memory Service error: {e}')
    
    # Test 3: API Gateway Client
    try:
        from app.services.api_gateway_client import api_gateway_client
        await api_gateway_client.initialize()
        print('✅ API Gateway Client: Initialized successfully')
    except Exception as e:
        print(f'❌ API Gateway Client error: {e}')
    
    # Test 4: LLM Service
    try:
        from app.services.llm_service import initialize_llm_service
        llm_service = initialize_llm_service(provider="gemini")
        print('✅ LLM Service: Initialized successfully')
    except Exception as e:
        print(f'❌ LLM Service error: {e}')
    
    # Test 5: Startup Service
    try:
        from app.services.startup_service import startup_service
        status = startup_service.get_initialization_status()
        print(f'✅ Startup Service: Status retrieved - {status["initialization_complete"]}')
    except Exception as e:
        print(f'❌ Startup Service error: {e}')
    
    print('=' * 50)
    print('🎯 Implementation test completed!')
    print('')
    print('Next steps:')
    print('1. Start the service: python -m uvicorn app.main:app --host 0.0.0.0 --port 8003')
    print('2. Run the test suite: ./test-ai-copilot-complete.sh')
    print('3. Test WebSocket reasoning at: ws://localhost:8003/ws/reasoning/{conversation_id}')

if __name__ == "__main__":
    asyncio.run(test_services())