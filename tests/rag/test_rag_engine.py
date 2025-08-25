"""Unit tests for the RAG engine.

Tests the core functionality of the RAG engine, including document processing,
embedding, storage, and retrieval.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

from app.rag.engine import RAGEngine
from app.rag.models import Document, DocumentChunk, SearchQuery, SearchFilter, DocumentType, AccessLevel
from app.database.connection import DatabaseManager


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    db_manager = MagicMock(spec=DatabaseManager)
    return db_manager


@pytest.fixture
def sample_document():
    """Create a sample document for testing."""
    return Document(
        title="Test Document",
        content="This is a test document with multiple sentences. It contains information that can be retrieved. This is for testing the RAG engine.",
        document_type=DocumentType.GUIDE,
        metadata={"department": "engineering", "tags": ["test", "documentation"]},
        access_level=AccessLevel.INTERNAL,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.mark.asyncio
async def test_rag_engine_initialization(mock_db_manager):
    """Test RAG engine initialization."""
    engine = RAGEngine(mock_db_manager)
    
    # Mock the vector store methods
    with patch.object(engine.vector_store, 'initialize', new_callable=AsyncMock) as mock_initialize, \
         patch.object(engine.vector_store, 'create_collection_if_not_exists', new_callable=AsyncMock) as mock_create_collection:
        
        await engine.initialize()
        
        # Check if collections were initialized
        mock_initialize.assert_called_once()
        assert mock_create_collection.call_count >= 4  # Should create at least 4 collections


@pytest.mark.asyncio
async def test_document_processing(mock_db_manager, sample_document):
    """Test document processing and chunking."""
    engine = RAGEngine(mock_db_manager)
    
    # Mock the embedding provider and vector store
    with patch.object(engine.embedding_provider, 'get_embeddings', new_callable=AsyncMock) as mock_get_embeddings, \
         patch.object(engine.vector_store, 'add_vector', new_callable=AsyncMock) as mock_add_vector:
        
        mock_get_embeddings.return_value = [[0.1] * 384, [0.2] * 384]
        mock_add_vector.return_value = "chunk-id"
        
        # Process the document
        result = await engine.process_document(sample_document)
        
        # Check if document was processed properly
        assert "document_id" in result
        assert "chunks_created" in result
        assert result["chunks_created"] > 0
        assert "embedding_model" in result
        assert "vector_ids" in result


@pytest.mark.asyncio
async def test_document_storage(mock_db_manager, sample_document):
    """Test document storage in vector database."""
    engine = RAGEngine(mock_db_manager)
    
    # Mock the embedding provider and vector store
    with patch.object(engine.embedding_provider, 'get_embeddings', new_callable=AsyncMock) as mock_get_embeddings, \
         patch.object(engine.vector_store, 'add_vector', new_callable=AsyncMock) as mock_add_vector:
        
        mock_get_embeddings.return_value = [[0.1] * 384, [0.2] * 384]
        mock_add_vector.return_value = "chunk-id"
        
        # Process the document (which includes storage)
        result = await engine.process_document(sample_document)
        
        # Check if vectors were added to the store
        assert result is not None
        assert len(result["vector_ids"]) > 0
        mock_add_vector.assert_called()


@pytest.mark.asyncio
async def test_document_search(mock_db_manager):
    """Test document search functionality."""
    engine = RAGEngine(mock_db_manager)
    
    # Mock the embedding provider and vector store
    with patch.object(engine.embedding_provider, 'get_embedding', new_callable=AsyncMock) as mock_get_embedding, \
         patch.object(engine.vector_store, 'search', new_callable=AsyncMock) as mock_search:
        
        mock_get_embedding.return_value = [0.1] * 384
        mock_search.return_value = [
            {
                "id": "id1", 
                "payload": {"document_id": "doc1", "content": "Test content 1"}, 
                "score": 0.95
            },
            {
                "id": "id2", 
                "payload": {"document_id": "doc1", "content": "Test content 2"}, 
                "score": 0.85
            }
        ]
        
        # Create a search query
        query = SearchQuery(
            query_text="test information",
            filters=SearchFilter(document_type=DocumentType.GUIDE),
            max_results=5
        )
        
        # Perform search
        results = await engine.search(query)
        
        # Check search results
        assert results is not None
        assert len(results["results"]) > 0
        mock_get_embedding.assert_called_once()
        mock_search.assert_called_once()
        
        # Check result properties
        for result in results["results"]:
            assert "document_id" in result
            assert "content" in result
            assert "similarity" in result