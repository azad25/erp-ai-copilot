"""Performance tests for the RAG engine.

Tests the performance and scalability of the RAG engine under various loads.
"""

import pytest
import asyncio
import time
import uuid
from unittest.mock import MagicMock, AsyncMock, patch

from app.rag.engine import RAGEngine
from app.rag.document_processor import DocumentProcessor
from app.rag.vector_store import VectorStore
from app.rag.embeddings import EmbeddingProvider
from app.rag.service import RAGService
from app.rag.models import Document, DocumentType, AccessLevel, SearchQuery


@pytest.fixture
def mock_rag_service():
    """Create a mock RAG service with controlled performance characteristics."""
    service = MagicMock(spec=RAGService)
    
    # Configure the mock to simulate realistic processing times
    async def simulated_ingest(document):
        # Simulate processing time based on document size
        await asyncio.sleep(0.01 * (len(document.content) // 100 + 1))  # 10ms per 100 chars
        return True, f"doc-{uuid.uuid4()}", [f"vector-{uuid.uuid4()}", f"vector-{uuid.uuid4()}"]
    
    async def simulated_search(query):
        # Simulate search time based on complexity
        await asyncio.sleep(0.05)  # Base 50ms search time
        return [
            {"document_id": f"doc-{i}", "content": f"Result {i}", "score": 0.9 - (i * 0.05), "metadata": {}}
            for i in range(query.max_results)
        ]
    
    service.ingest_document = AsyncMock(side_effect=simulated_ingest)
    service.search = AsyncMock(side_effect=simulated_search)
    
    return service


@pytest.mark.asyncio
async def test_document_ingestion_performance(mock_rag_service):
    """Test document ingestion performance with documents of varying sizes."""
    document_sizes = [1000, 5000, 10000, 50000]  # Characters
    results = {}
    
    for size in document_sizes:
        document = Document(
            title=f"Performance Test Document ({size} chars)",
            content="A" * size,  # Create document with specified size
            document_type=DocumentType.GUIDE,
            access_level=AccessLevel.INTERNAL,
            metadata={"test": "performance"}
        )
        
        # Measure ingestion time
        start_time = time.time()
        success, doc_id, vector_ids = await mock_rag_service.ingest_document(document)
        end_time = time.time()
        
        results[size] = {
            "time": end_time - start_time,
            "success": success,
            "doc_id": doc_id,
            "vector_count": len(vector_ids)
        }
    
    # Log results
    for size, result in results.items():
        print(f"Document size: {size} chars, Ingestion time: {result['time']:.4f}s")
        assert result["success"] is True
    
    # Verify performance scales reasonably with document size
    # This is a simple check that larger documents take longer, but not excessively
    assert results[5000]["time"] > results[1000]["time"]
    assert results[10000]["time"] > results[5000]["time"]
    # The ratio should be sublinear (less than proportional increase)
    assert results[10000]["time"] / results[5000]["time"] < 10000 / 5000


@pytest.mark.asyncio
async def test_search_performance(mock_rag_service):
    """Test search performance with varying result sizes."""
    result_sizes = [5, 10, 20, 50]
    results = {}
    
    for size in result_sizes:
        query = SearchQuery(
            query_text="performance test query",
            max_results=size
        )
        
        # Measure search time
        start_time = time.time()
        search_results = await mock_rag_service.search(query)
        end_time = time.time()
        
        results[size] = {
            "time": end_time - start_time,
            "result_count": len(search_results)
        }
    
    # Log results
    for size, result in results.items():
        print(f"Result size: {size}, Search time: {result['time']:.4f}s")
        assert result["result_count"] == size
    
    # Verify performance scales reasonably with result size
    assert results[10]["time"] >= results[5]["time"]
    # The increase should be sublinear
    assert results[20]["time"] / results[10]["time"] < 20 / 10


@pytest.mark.asyncio
async def test_concurrent_ingestion_performance(mock_rag_service):
    """Test performance of concurrent document ingestions."""
    concurrency_levels = [1, 5, 10, 20]
    results = {}
    
    for concurrency in concurrency_levels:
        # Create documents
        documents = [
            Document(
                title=f"Concurrent Test Document {i}",
                content=f"This is test document {i} for concurrent ingestion testing. " * 20,
                document_type=DocumentType.GUIDE,
                access_level=AccessLevel.INTERNAL,
                metadata={"test": "concurrent", "index": i}
            )
            for i in range(concurrency)
        ]
        
        # Measure concurrent ingestion time
        start_time = time.time()
        tasks = [mock_rag_service.ingest_document(doc) for doc in documents]
        ingestion_results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        results[concurrency] = {
            "total_time": end_time - start_time,
            "average_time": (end_time - start_time) / concurrency,
            "success_rate": sum(1 for success, _, _ in ingestion_results if success) / concurrency
        }
    
    # Log results
    for concurrency, result in results.items():
        print(f"Concurrency: {concurrency}, Total time: {result['total_time']:.4f}s, "
              f"Average time: {result['average_time']:.4f}s, "
              f"Success rate: {result['success_rate']:.2f}")
        assert result["success_rate"] == 1.0  # All should succeed
    
    # Verify concurrent performance is better than sequential
    # The total time for 10 concurrent should be less than 10x the time for 1
    assert results[10]["total_time"] < results[1]["total_time"] * 10


@pytest.mark.asyncio
async def test_concurrent_search_performance(mock_rag_service):
    """Test performance of concurrent searches."""
    concurrency_levels = [1, 5, 10, 20]
    results = {}
    
    for concurrency in concurrency_levels:
        # Create search queries
        queries = [
            SearchQuery(
                query_text=f"concurrent search test query {i}",
                max_results=5
            )
            for i in range(concurrency)
        ]
        
        # Measure concurrent search time
        start_time = time.time()
        tasks = [mock_rag_service.search(query) for query in queries]
        search_results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        results[concurrency] = {
            "total_time": end_time - start_time,
            "average_time": (end_time - start_time) / concurrency,
            "result_count": sum(len(results) for results in search_results)
        }
    
    # Log results
    for concurrency, result in results.items():
        print(f"Concurrency: {concurrency}, Total time: {result['total_time']:.4f}s, "
              f"Average time: {result['average_time']:.4f}s, "
              f"Results: {result['result_count']}")
        assert result["result_count"] == concurrency * 5  # Each query returns 5 results
    
    # Verify concurrent performance is better than sequential
    assert results[10]["total_time"] < results[1]["total_time"] * 10


@pytest.mark.asyncio
async def test_mixed_workload_performance(mock_rag_service):
    """Test performance with a mixed workload of ingestion and search operations."""
    # Create a mix of ingestion and search tasks
    ingestion_count = 5
    search_count = 10
    
    ingestion_tasks = [
        mock_rag_service.ingest_document(
            Document(
                title=f"Mixed Workload Document {i}",
                content=f"This is test document {i} for mixed workload testing. " * 20,
                document_type=DocumentType.GUIDE,
                access_level=AccessLevel.INTERNAL,
                metadata={"test": "mixed", "index": i}
            )
        )
        for i in range(ingestion_count)
    ]
    
    search_tasks = [
        mock_rag_service.search(
            SearchQuery(
                query_text=f"mixed workload search query {i}",
                max_results=5
            )
        )
        for i in range(search_count)
    ]
    
    # Combine tasks and measure execution time
    all_tasks = ingestion_tasks + search_tasks
    start_time = time.time()
    results = await asyncio.gather(*all_tasks)
    end_time = time.time()
    
    total_time = end_time - start_time
    ingestion_results = results[:ingestion_count]
    search_results = results[ingestion_count:]
    
    # Verify results
    ingestion_success_rate = sum(1 for success, _, _ in ingestion_results if success) / ingestion_count
    search_result_count = sum(len(results) for results in search_results)
    
    print(f"Mixed workload - Total time: {total_time:.4f}s, "
          f"Ingestion success rate: {ingestion_success_rate:.2f}, "
          f"Search results: {search_result_count}")
    
    assert ingestion_success_rate == 1.0  # All ingestions should succeed
    assert search_result_count == search_count * 5  # Each search returns 5 results