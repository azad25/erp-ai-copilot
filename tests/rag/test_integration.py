"""Integration tests for the RAG engine.

Tests the integration of all RAG engine components working together.
"""

import pytest
import os
import uuid
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from app.rag.engine import RAGEngine
from app.rag.document_processor import DocumentProcessor
from app.rag.vector_store import VectorStore
from app.rag.embeddings import EmbeddingProvider
from app.rag.cache import CacheManager, SearchCache
from app.rag.kafka_integration import KafkaManager
from app.rag.service import RAGService
from app.rag.models import Document, DocumentType, AccessLevel, SearchQuery, SearchFilter
from app.database.connection import DBManager


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    db_manager = MagicMock(spec=DBManager)
    db_manager.get_mongodb_client = AsyncMock(return_value=MagicMock())
    db_manager.get_mongodb_database = AsyncMock(return_value=MagicMock())
    db_manager.get_mongodb_collection = AsyncMock(return_value=MagicMock())
    
    # Mock MongoDB operations
    collection = db_manager.get_mongodb_collection.return_value
    collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="doc123"))
    collection.find_one = AsyncMock(return_value={
        "_id": "doc123",
        "title": "Test Document",
        "content": "This is a test document.",
        "document_type": "guide",
        "access_level": "internal",
        "metadata": {"department": "engineering", "tags": ["test"]},
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    })
    collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    
    return db_manager


@pytest.fixture
def mock_embedding_provider():
    """Create a mock embedding provider."""
    provider = MagicMock(spec=EmbeddingProvider)
    provider.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4])
    provider.get_embeddings = AsyncMock(return_value=[[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]])
    provider.get_vector_size = MagicMock(return_value=4)
    provider.get_distance_metric = MagicMock(return_value="cosine")
    return provider


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = MagicMock(spec=VectorStore)
    store.initialize_collection = AsyncMock(return_value=True)
    store.add_vectors = AsyncMock(return_value=["vector1", "vector2"])
    store.search = AsyncMock(return_value=[
        {"id": "chunk1", "score": 0.95, "payload": {"document_id": "doc1", "content": "Test content 1"}},
        {"id": "chunk2", "score": 0.85, "payload": {"document_id": "doc2", "content": "Test content 2"}}
    ])
    store.delete_vectors = AsyncMock(return_value=True)
    store.delete_collection = AsyncMock(return_value=True)
    return store


@pytest.fixture
def mock_document_processor():
    """Create a mock document processor."""
    processor = MagicMock(spec=DocumentProcessor)
    processor.process_document = AsyncMock(return_value=[
        {"chunk_id": "chunk1", "content": "Chunk 1 content", "metadata": {"position": 1}},
        {"chunk_id": "chunk2", "content": "Chunk 2 content", "metadata": {"position": 2}}
    ])
    return processor


@pytest.fixture
def mock_cache_manager():
    """Create a mock cache manager."""
    cache = MagicMock(spec=CacheManager)
    cache.get = AsyncMock(return_value=None)  # Default to cache miss
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.clear_prefix = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def mock_search_cache():
    """Create a mock search cache."""
    cache = MagicMock(spec=SearchCache)
    cache.get_search_results = AsyncMock(return_value=None)  # Default to cache miss
    cache.set_search_results = AsyncMock(return_value=True)
    cache.invalidate_document_cache = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def mock_kafka_manager():
    """Create a mock Kafka manager."""
    manager = MagicMock(spec=KafkaManager)
    manager.initialize = AsyncMock(return_value=True)
    manager.shutdown = AsyncMock(return_value=True)
    manager.send_document_ingestion_message = AsyncMock(return_value=True)
    manager.send_document_search_message = AsyncMock(return_value=True)
    manager.send_document_update_message = AsyncMock(return_value=True)
    manager.send_document_deletion_message = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def rag_service(mock_db_manager, mock_embedding_provider, mock_vector_store, 
               mock_document_processor, mock_cache_manager, mock_search_cache, mock_kafka_manager):
    """Create a RAG service with mock components."""
    service = RAGService(
        db_manager=mock_db_manager,
        embedding_provider=mock_embedding_provider,
        vector_store=mock_vector_store,
        document_processor=mock_document_processor,
        cache_manager=mock_cache_manager,
        search_cache=mock_search_cache,
        kafka_manager=mock_kafka_manager
    )
    return service


@pytest.mark.asyncio
async def test_full_document_lifecycle(rag_service):
    """Test the full document lifecycle: ingest, search, retrieve, update, delete."""
    # 1. Document Ingestion
    document = Document(
        title="Integration Test Document",
        content="This is a document for integration testing.",
        document_type=DocumentType.GUIDE,
        access_level=AccessLevel.INTERNAL,
        metadata={"department": "engineering", "tags": ["test", "integration"]}
    )
    
    success, doc_id, vector_ids = await rag_service.ingest_document(document)
    
    assert success is True
    assert doc_id == "doc123"  # From mock
    assert vector_ids == ["vector1", "vector2"]  # From mock
    
    # 2. Document Retrieval
    retrieved_doc = await rag_service.get_document(doc_id)
    
    assert retrieved_doc is not None
    assert retrieved_doc["_id"] == "doc123"
    assert retrieved_doc["title"] == "Test Document"
    assert retrieved_doc["document_type"] == "guide"
    
    # 3. Document Search
    search_query = SearchQuery(
        query_text="integration test",
        filters=SearchFilter(
            document_type=DocumentType.GUIDE,
            access_level=AccessLevel.INTERNAL,
            metadata={"department": "engineering"}
        ),
        max_results=5
    )
    
    search_results = await rag_service.search(search_query)
    
    assert len(search_results) == 2
    assert search_results[0].document_id == "doc1"
    assert search_results[0].score == 0.95
    assert search_results[0].content == "Test content 1"
    
    # 4. Document Update
    updated_document = Document(
        document_id=doc_id,
        title="Updated Integration Test Document",
        content="This document has been updated for integration testing.",
        document_type=DocumentType.GUIDE,
        access_level=AccessLevel.INTERNAL,
        metadata={"department": "engineering", "tags": ["test", "integration", "updated"]}
    )
    
    update_success = await rag_service.update_document(doc_id, updated_document)
    
    assert update_success is True
    
    # 5. Document Deletion
    delete_success = await rag_service.delete_document(doc_id)
    
    assert delete_success is True


@pytest.mark.asyncio
async def test_cache_integration(rag_service, mock_search_cache):
    """Test the integration of caching with search operations."""
    # Set up mock to return cached results
    cached_results = [
        {"document_id": "cached1", "content": "Cached content 1", "score": 0.98, "metadata": {"title": "Cached Document 1"}},
        {"document_id": "cached2", "content": "Cached content 2", "score": 0.88, "metadata": {"title": "Cached Document 2"}}
    ]
    mock_search_cache.get_search_results.return_value = cached_results
    
    # Search with a query that should hit the cache
    search_query = SearchQuery(
        query_text="cached query",
        max_results=5
    )
    
    search_results = await rag_service.search(search_query)
    
    # Check if cache was used and results match cached data
    mock_search_cache.get_search_results.assert_called_once()
    assert len(search_results) == 2
    assert search_results[0].document_id == "cached1"
    assert search_results[0].content == "Cached content 1"
    assert search_results[0].score == 0.98
    
    # Reset mock to simulate cache miss
    mock_search_cache.get_search_results.reset_mock()
    mock_search_cache.get_search_results.return_value = None
    
    # Search with a query that should miss the cache
    search_query = SearchQuery(
        query_text="uncached query",
        max_results=5
    )
    
    search_results = await rag_service.search(search_query)
    
    # Check if cache was checked, missed, and then set with new results
    mock_search_cache.get_search_results.assert_called_once()
    mock_search_cache.set_search_results.assert_called_once()
    assert len(search_results) == 2  # From vector store mock


@pytest.mark.asyncio
async def test_kafka_integration(rag_service, mock_kafka_manager):
    """Test the integration of Kafka messaging with RAG operations."""
    # 1. Document Ingestion with Kafka
    document = Document(
        title="Kafka Test Document",
        content="This is a document for Kafka integration testing.",
        document_type=DocumentType.GUIDE,
        access_level=AccessLevel.INTERNAL,
        metadata={"department": "engineering", "tags": ["test", "kafka"]}
    )
    
    await rag_service.ingest_document(document, use_kafka=True)
    
    # Check if Kafka message was sent
    mock_kafka_manager.send_document_ingestion_message.assert_called_once()
    
    # 2. Document Search with Kafka
    search_query = SearchQuery(
        query_text="kafka test",
        max_results=5
    )
    
    await rag_service.search(search_query, use_kafka=True)
    
    # Check if Kafka message was sent
    mock_kafka_manager.send_document_search_message.assert_called_once()
    
    # 3. Document Update with Kafka
    updated_document = Document(
        document_id="doc123",
        title="Updated Kafka Test Document",
        content="This document has been updated for Kafka integration testing.",
        document_type=DocumentType.GUIDE,
        access_level=AccessLevel.INTERNAL,
        metadata={"department": "engineering", "tags": ["test", "kafka", "updated"]}
    )
    
    await rag_service.update_document("doc123", updated_document, use_kafka=True)
    
    # Check if Kafka message was sent
    mock_kafka_manager.send_document_update_message.assert_called_once()
    
    # 4. Document Deletion with Kafka
    await rag_service.delete_document("doc123", use_kafka=True)
    
    # Check if Kafka message was sent
    mock_kafka_manager.send_document_deletion_message.assert_called_once()


@pytest.mark.asyncio
async def test_error_handling(rag_service, mock_db_manager, mock_vector_store):
    """Test error handling in the RAG service."""
    # 1. Test database error during document retrieval
    mock_db_manager.get_mongodb_collection.return_value.find_one.side_effect = Exception("Database error")
    
    # Document retrieval should handle the error and return None
    result = await rag_service.get_document("doc123")
    assert result is None
    
    # Reset mock
    mock_db_manager.get_mongodb_collection.return_value.find_one.side_effect = None
    
    # 2. Test vector store error during search
    mock_vector_store.search.side_effect = Exception("Vector store error")
    
    # Search should handle the error and return empty results
    search_query = SearchQuery(
        query_text="error test",
        max_results=5
    )
    
    search_results = await rag_service.search(search_query)
    assert len(search_results) == 0
    
    # Reset mock
    mock_vector_store.search.side_effect = None
    
    # 3. Test error during document update
    mock_db_manager.get_mongodb_collection.return_value.update_one.side_effect = Exception("Update error")
    
    # Update should handle the error and return False
    updated_document = Document(
        document_id="doc123",
        title="Error Test Document",
        content="This document tests error handling.",
        document_type=DocumentType.GUIDE,
        access_level=AccessLevel.INTERNAL
    )
    
    update_success = await rag_service.update_document("doc123", updated_document)
    assert update_success is False