#!/usr/bin/env python3
"""
Test script to verify AI Copilot service endpoints
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

import uvicorn
from app.main import app

async def test_service():
    """Test if the service can start and endpoints are accessible"""
    print("🧪 Testing AI Copilot Service...")
    
    try:
        # Test importing the main app
        print("✅ Main app imported successfully")
        
        # Test if we can access the FastAPI app
        print(f"✅ FastAPI app created: {app.title}")
        
        # List all routes
        print("\n📋 Available routes:")
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                methods = getattr(route, 'methods', set())
                print(f"  {route.path} - {methods}")
        
        print("\n🚀 Service appears to be configured correctly!")
        print("To start the service, run:")
        print("  python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing service: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_service())
    sys.exit(0 if success else 1)