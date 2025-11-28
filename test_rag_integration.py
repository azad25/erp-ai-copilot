#!/usr/bin/env python3
"""
Test RAG and Data Integration

Quick test script to verify RAG and ERP data integration is working.
"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from app.database.connection import get_db_manager
from app.rag.service import RAGService
from app.rag.models import SearchQuery
from app.services.erp_data_service import get_erp_data_service
from app.agents.query_agent import QueryAgent
from app.agents.base_agent import AgentRequest


async def test_rag_service():
    """Test RAG service"""
    print("\n" + "="*60)
    print("TEST 1: RAG Service (Knowledge Base)")
    print("="*60)
    
    try:
        db_manager = await get_db_manager()
        rag_service = RAGService(db_manager)
        await rag_service.initialize()
        
        # Test search
        query = SearchQuery(
            query_text="What is the ERP architecture?",
            max_results=3,
            similarity_threshold=0.5
        )
        
        results = await rag_service.search(query)
        
        if isinstance(results, list):
            result_count = len(results)
        elif hasattr(results, 'results'):
            result_count = len(results.results)
        else:
            result_count = 0
        
        print(f"✓ RAG Service initialized")
        print(f"✓ Search query executed")
        print(f"✓ Found {result_count} relevant documents")
        
        if result_count > 0:
            print("\nSample result:")
            if isinstance(results, list):
                first_result = results[0]
            else:
                first_result = results.results[0]
            
            content = first_result.get("content", "")[:200]
            print(f"  Content: {content}...")
            print(f"  Similarity: {first_result.get('similarity', 0):.2f}")
        
        return True
        
    except Exception as e:
        print(f"✗ RAG Service test failed: {e}")
        return False


async def test_erp_data_service():
    """Test ERP Data Service"""
    print("\n" + "="*60)
    print("TEST 2: ERP Data Service (Real Data)")
    print("="*60)
    
    try:
        erp_service = await get_erp_data_service()
        
        # Test system overview
        overview = await erp_service.get_system_overview()
        print(f"✓ System overview retrieved")
        print(f"  Databases: {list(overview.get('databases', {}).keys())}")
        
        # Test user statistics
        user_stats = await erp_service.get_user_statistics()
        print(f"✓ User statistics retrieved")
        print(f"  Total users: {user_stats.get('total_users', 0)}")
        print(f"  Active users: {user_stats.get('active_users', 0)}")
        
        # Test conversation summary
        conv_summary = await erp_service.get_conversations_summary()
        print(f"✓ Conversation summary retrieved")
        print(f"  Total conversations: {conv_summary.get('total_conversations', 0)}")
        
        # Test cache statistics
        cache_stats = await erp_service.get_cache_statistics()
        print(f"✓ Cache statistics retrieved")
        print(f"  Total keys: {cache_stats.get('total_keys', 0)}")
        
        return True
        
    except Exception as e:
        print(f"✗ ERP Data Service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_query_agent():
    """Test Query Agent with RAG and Data"""
    print("\n" + "="*60)
    print("TEST 3: Query Agent (Combined RAG + Data)")
    print("="*60)
    
    try:
        agent = QueryAgent()
        
        # Test query about documentation (should use RAG)
        print("\nTest Query 1: Documentation question")
        request1 = AgentRequest(
            message="What is the ERP system architecture?",
            metadata={"use_rag": True}
        )
        
        response1 = await agent.process_request(request1)
        print(f"✓ Query processed")
        print(f"  Response length: {len(response1.content)} characters")
        print(f"  RAG used: {response1.metadata.get('rag_used', False)}")
        print(f"  Documents retrieved: {response1.metadata.get('rag_documents_count', 0)}")
        print(f"  Model: {response1.model_used}")
        
        # Test query about data (should use ERP Data Service)
        print("\nTest Query 2: Data question")
        request2 = AgentRequest(
            message="How many users are in the system?",
            metadata={"use_rag": True}
        )
        
        response2 = await agent.process_request(request2)
        print(f"✓ Query processed")
        print(f"  Response length: {len(response2.content)} characters")
        print(f"  Model: {response2.model_used}")
        
        # Show sample response
        print(f"\nSample response (first 300 chars):")
        print(f"  {response2.content[:300]}...")
        
        return True
        
    except Exception as e:
        print(f"✗ Query Agent test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("RAG AND DATA INTEGRATION TEST SUITE")
    print("="*60)
    
    results = []
    
    # Test 1: RAG Service
    results.append(await test_rag_service())
    
    # Test 2: ERP Data Service
    results.append(await test_erp_data_service())
    
    # Test 3: Query Agent
    results.append(await test_query_agent())
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total tests: {len(results)}")
    print(f"Passed: {sum(results)}")
    print(f"Failed: {len(results) - sum(results)}")
    
    if all(results):
        print("\n✓ ALL TESTS PASSED!")
        print("\nYour AI Copilot is ready with:")
        print("  - RAG system for documentation")
        print("  - Real-time data access")
        print("  - Combined intelligent responses")
    else:
        print("\n✗ SOME TESTS FAILED")
        print("\nPlease check:")
        print("  1. All databases are running (postgres, mongodb, redis, qdrant)")
        print("  2. Knowledge base is populated (run populate_knowledge_base.py)")
        print("  3. Database connections are configured correctly")
    
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
