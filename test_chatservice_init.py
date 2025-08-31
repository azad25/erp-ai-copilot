#!/usr/bin/env python3
"""
Test ChatService initialization to identify the root cause of WebSocket failures.
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, '/app')

async def test_chatservice_init():
    """Test ChatService initialization in isolation."""
    try:
        print("🧪 Testing ChatService initialization...")
        
        # Import ChatService
        from app.services.chat_service import ChatService
        print("✅ ChatService import successful")
        
        # Try to create ChatService instance
        print("🔧 Creating ChatService instance...")
        chat_service = ChatService()
        print("✅ ChatService instance created successfully")
        
        # Test basic method availability
        print("🔍 Checking available methods...")
        methods = [method for method in dir(chat_service) if not method.startswith('_')]
        print(f"📋 Available methods: {methods}")
        
        return True
        
    except Exception as e:
        print(f"❌ ChatService initialization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_chatservice_init())
    exit(0 if success else 1)
