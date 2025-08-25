"""Unit tests for the RAG service component.

Tests the RAG service functionality, including document ingestion, search,
retrieval, update, and deletion operations.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from app.rag.service import RAGService
from app.rag.models import Document, DocumentChunk, SearchQuery, SearchFilter, DocumentType, AccessLevel, SearchResult
from app.rag.engine import RAGEngine
from app.rag.document_processor import DocumentProcessor
from app.rag.vector_store import VectorStore
from app.rag.embeddings import EmbeddingProvider
from app.rag.cache import CacheManager, SearchCache
from app.rag.kafka_integration import KafkaManager


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    db_manager = MagicMock()
    db_manager.get_mongodb_client.return_value = AsyncMock()
    db_manager.get_mongodb_client.return_value.get_database.return_value = AsyncMock()
    db_manager.get_mongodb_client.return_value.get_database.return_value.get_collection.return_value = AsyncMock()
    db_manager.get_mongodb_client.return_value.get_database.return_value.get_collection.return_value.insert_one = AsyncMock(return_value=MagicMock(inserted_id="doc123"))
    db_manager.get_mongodb_client.return_value.get_database.return_value.get_collection.return_value.find_one = AsyncMock(return_value={"_id": "doc123", "title": "Test Document"})
    db_manager.get_mongodb_client.return_value.get_database.return_value.get_collection.return_value.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db_manager.get_mongodb_client.return_value.get_database.return_value.get_collection.return_value.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    return db_manager


@pytest.fixture
def mock_rag_engine():
    """Create a mock RAG engine."""
    engine = MagicMock(spec=RAGEngine)
    engine.initialize = AsyncMock()
    engine.process_document = AsyncMock(return_value=(["chunk1", "chunk2"], ["vector1", "vector2"]))
    engine.search = AsyncMock(return_value=[
        SearchResult(document_id="doc1", content="Test content 1", score=0.95, metadata={"title": "Test Document 1"}),
        SearchResult(document_id="doc2", content="Test content 2", score=0.85, metadata={"title": "Test Document 2"})
    ])
    return engine


@pytest.fixture
def mock_document_processor():
    """Create a mock document processor."""
    processor = MagicMock(spec=DocumentProcessor)
    processor.process_document = AsyncMock(return_value=(Document(title="Processed Document", content="Processed content"), [
        DocumentChunk(document_id="doc123", chunk_index=0, text="Chunk 1", metadata={}),
        DocumentChunk(document_id="doc123", chunk_index=1, text="Chunk 2", metadata={})
    ]))
    return processor


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = MagicMock(spec=VectorStore)
    store.initialize_collection = AsyncMock()
    store.add_vectors = AsyncMock(return_value=["vector1", "vector2"])
    store.delete_vectors = AsyncMock()
    store.search = AsyncMock()
    return store


@pytest.fixture
def mock_embedding_provider():
    """Create a mock embedding provider."""
    provider = MagicMock(spec=EmbeddingProvider)
    provider.get_vector_size = MagicMock(return_value=384)
    provider.get_distance_metric = MagicMock(return_value="cosine")
    provider.generate_embedding = AsyncMock(return_value=[0.1] * 384)
    provider.generate_embeddings = AsyncMock(return_value=[[0.1] * 384, [0.2] * 384])
    return provider


@pytest.fixture
def mock_cache_manager():
    """Create a mock cache manager."""
    cache = MagicMock(spec=CacheManager)
    cache.get = AsyncMock(return_value=None)  # Default to cache miss
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    cache.clear_prefix = AsyncMock()
    return cache


@pytest.fixture
def mock_search_cache():
    """Create a mock search cache."""
    cache = MagicMock(spec=SearchCache)
    cache.get_search_results = AsyncMock(return_value=None)  # Default to cache miss
    cache.set_search_results = AsyncMock()
    cache.invalidate_document_cache = AsyncMock()
    return cache


@pytest.fixture
def mock_kafka_manager():
    """Create a mock Kafka manager."""
    manager = MagicMock(spec=KafkaManager)
    manager.initialize = AsyncMock()
    manager.shutdown = AsyncMock()
    manager.send_document_ingestion_message = AsyncMock()
    manager.send_document_search_message = AsyncMock()
    manager.send_document_update_message = AsyncMock()
    manager.send_document_deletion_message = AsyncMock()
    manager.register_consumer = AsyncMock()
    return manager


@pytest.fixture
def sample_document():
    """Create a sample document for testing."""
    return Document(
        title="Test Document",
        content="This is a test document for RAG service testing.",
        document_type=DocumentType.GUIDE,
        access_level=AccessLevel.INTERNAL,
        metadata={"department": "engineering", "tags": ["test", "service"]},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def rag_service(mock_db_manager, mock_rag_engine, mock_document_processor, mock_vector_store, 
               mock_embedding_provider, mock_cache_manager, mock_search_cache, mock_kafka_manager):
    """Create a RAG service with mock components."""
    with patch("app.rag.service.RAGEngine", return_value=mock_rag_engine), \
         patch("app.rag.service.DocumentProcessor", return_value=mock_document_processor), \
         patch("app.rag.service.VectorStore", return_value=mock_vector_store), \
         patch("app.rag.service.get_embedding_provider", return_value=mock_embedding_provider), \
         patch("app.rag.service.CacheManager", return_value=mock_cache_manager), \
         patch("app.rag.service.SearchCache", return_value=mock_search_cache), \
         patch("app.rag.service.KafkaManager", return_value=mock_kafka_manager):
        service = RAGService(db_manager=mock_db_manager)
        return service


@pytest.mark.asyncio
async def test_rag_service_initialization(rag_service):
    """Test RAG service initialization."""
    # Initialize service
    await rag_service.initialize()
    
    # Check if components were initialized
    rag_service.rag_engine.initialize.assert_called_once()
    rag_service.kafka_manager.initialize.assert_called_once()


@pytest.mark.asyncio
async def test_document_ingestion(rag_service, sample_document):
    """Test document ingestion functionality."""
    # Initialize service
    await rag_service.initialize()
    
    # Ingest document
    success, document_id, vector_ids = await rag_service.ingest_document(sample_document)
    
    # Check results
    assert success is True
    assert document_id == "doc123"
    assert vector_ids == ["vector1", "vector2"]
    
    # Check if document processor was called
    rag_service.document_processor.process_document.assert_called_with(sample_document)
    
    # Check if MongoDB was used to store document
    mongodb_collection = rag_service.db_manager.get_mongodb_client.return_value.get_database.return_value.get_collection.return_value
    mongodb_collection.insert_one.assert_called_once()
    
    # Check if vector store was used to store embeddings
    rag_service.vector_store.add_vectors.assert_called_once()
    
    # Check if Kafka message was sent
    rag_service.kafka_manager.send_document_ingestion_message.assert_called_once()


@pytest.mark.asyncio
async def test_document_search(rag_service):
    """Test document search functionality."""
    # Initialize service
    await rag_service.initialize()
    
    # Create search query
    query = SearchQuery(
        query_text="test query",
        filters=SearchFilter(document_type=DocumentType.GUIDE),
        max_results=5
    )
    
    # Perform search
    results = await rag_service.search(query)
    
    # Check results
    assert results is not None
    assert len(results) == 2
    assert results[0].document_id == "doc1"
    assert results[1].document_id == "doc2"
    
    # Check if search cache was checked
    rag_service.search_cache.get_search_results.assert_called_with(query)
    
    # Check if RAG engine search was called
    rag_service.rag_engine.search.assert_called_with(query)
    
    # Check if results were cached
    rag_service.search_cache.set_search_results.assert_called_once()


@pytest.mark.asyncio
async def test_document_retrieval(rag_service):
    """Test document retrieval functionality."""
    # Initialize service
    await rag_service.initialize()
    
    # Retrieve document
    document_id = "doc123"
    document = await rag_service.get_document(document_id)
    
    # Check results
    assert document is not None
    assert document["_id"] == document_id
    assert document["title"] == "Test Document"
    
    # Check if cache was checked
    rag_service.cache_manager.get.assert_called_once()
    
    # Check if MongoDB was queried
    mongodb_collection = rag_service.db_manager.get_mongodb_client.return_value.get_database.return_value.get_collection.return_value
    mongodb_collection.find_one.assert_called_with({"_id": document_id})
    
    # Check if result was cached
    rag_service.cache_manager.set.assert_called_once()


@pytest.mark.asyncio
async def test_document_update(rag_service, sample_document):
    """Test document update functionality."""
    # Initialize service
    await rag_service.initialize()
    
    # Update document
    document_id = "doc123"
    success = await rag_service.update_document(document_id, sample_document)
    
    # Check results
    assert success is True
    
    # Check if document processor was called
    rag_service.document_processor.process_document.assert_called_with(sample_document)
    
    # Check if MongoDB was used to update document
    mongodb_collection = rag_service.db_manager.get_mongodb_client.return_value.get_database.return_value.get_collection.return_value
    mongodb_collection.update_one.assert_called_once()
    
    # Check if old vectors were deleted
    rag_service.vector_store.delete_vectors.assert_called_once()
    
    # Check if new vectors were added
    rag_service.vector_store.add_vectors.assert_called_once()
    
    # Check if cache was invalidated
    rag_service.cache_manager.delete.assert_called_once()
    rag_service.search_cache.invalidate_document_cache.assert_called_with(document_id)
    
    # Check if Kafka message was sent
    rag_service.kafka_manager.send_document_update_message.assert_called_with(document_id, sample_document)


@pytest.mark.asyncio
async def test_document_deletion(rag_service):
    """Test document deletion functionality."""
    # Initialize service
    await rag_service.initialize()
    
    # Delete document
    document_id = "doc123"
    success = await rag_service.delete_document(document_id)
    
    # Check results
    assert success is True
    
    # Check if MongoDB was used to delete document
    mongodb_collection = rag_service.db_manager.get_mongodb_client.return_value.get_database.return_value.get_collection.return_value
    mongodb_collection.delete_one.assert_called_with({"_id": document_id})
    
    # Check if vectors were deleted
    rag_service.vector_store.delete_vectors.assert_called_once()
    
    # Check if cache was invalidated
    rag_service.cache_manager.delete.assert_called_once()
    rag_service.search_cache.invalidate_document_cache.assert_called_with(document_id)
    
    # Check if Kafka message was sent
    rag_service.kafka_manager.send_document_deletion_message.assert_called_with(document_id)