"""Unit tests for the vector store component.

Tests the vector store functionality, including initialization, vector storage,
retrieval, and deletion operations with Qdrant.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from app.rag.vector_store import VectorStore


@pytest.fixture
def mock_qdrant_client():
    """Create a mock Qdrant client for testing."""
    client = MagicMock()
    client.get_collection = AsyncMock()
    client.create_collection = AsyncMock()
    client.upsert = AsyncMock(return_value=MagicMock(operation_id="test_operation"))
    client.search = AsyncMock()
    client.delete_points = AsyncMock()
    client.delete_collection = AsyncMock()
    return client


@pytest.fixture
def vector_store(mock_qdrant_client):
    """Create a vector store instance with mock Qdrant client."""
    return VectorStore(mock_qdrant_client)


@pytest.mark.asyncio
async def test_initialize_collection(vector_store, mock_qdrant_client):
    """Test collection initialization."""
    # Set up mock response for collection existence check
    collection_response = MagicMock()
    collection_response.status = 200
    mock_qdrant_client.get_collection.return_value = collection_response
    
    # Test initializing an existing collection
    await vector_store.initialize_collection("test_collection", 384, "cosine")
    mock_qdrant_client.get_collection.assert_called_with(collection_name="test_collection")
    mock_qdrant_client.create_collection.assert_not_called()
    
    # Set up mock response for collection not found
    mock_qdrant_client.get_collection.side_effect = Exception("Collection not found")
    
    # Test initializing a new collection
    await vector_store.initialize_collection("new_collection", 384, "cosine")
    mock_qdrant_client.create_collection.assert_called()


@pytest.mark.asyncio
async def test_add_vectors(vector_store, mock_qdrant_client):
    """Test adding vectors to the collection."""
    # Test data
    collection_name = "test_collection"
    vectors = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6]
    ]
    payloads = [
        {"document_id": "doc1", "chunk_index": 0, "text": "Test content 1"},
        {"document_id": "doc1", "chunk_index": 1, "text": "Test content 2"}
    ]
    
    # Add vectors
    vector_ids = await vector_store.add_vectors(collection_name, vectors, payloads)
    
    # Check results
    assert vector_ids is not None
    assert len(vector_ids) == 2
    mock_qdrant_client.upsert.assert_called_with(
        collection_name=collection_name,
        points=pytest.approx([
            {"id": vector_ids[0], "vector": vectors[0], "payload": payloads[0]},
            {"id": vector_ids[1], "vector": vectors[1], "payload": payloads[1]}
        ], abs=1e-6)
    )


@pytest.mark.asyncio
async def test_search(vector_store, mock_qdrant_client):
    """Test vector search functionality."""
    # Set up mock search response
    search_results = [
        {"id": "id1", "payload": {"document_id": "doc1", "chunk_index": 0, "text": "Test content 1"}, "score": 0.95},
        {"id": "id2", "payload": {"document_id": "doc1", "chunk_index": 1, "text": "Test content 2"}, "score": 0.85}
    ]
    mock_qdrant_client.search.return_value = search_results
    
    # Test parameters
    collection_name = "test_collection"
    query_vector = [0.1, 0.2, 0.3]
    filter_conditions = {"document_id": "doc1"}
    limit = 5
    
    # Perform search
    results = await vector_store.search(collection_name, query_vector, filter_conditions, limit)
    
    # Check results
    assert results == search_results
    mock_qdrant_client.search.assert_called_with(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=pytest.approx({"must": [{"key": "document_id", "match": {"value": "doc1"}}]}),
        limit=limit
    )


@pytest.mark.asyncio
async def test_delete_vectors(vector_store, mock_qdrant_client):
    """Test deleting vectors by ID."""
    # Test parameters
    collection_name = "test_collection"
    vector_ids = ["id1", "id2"]
    
    # Delete vectors
    await vector_store.delete_vectors(collection_name, vector_ids)
    
    # Check if delete was called correctly
    mock_qdrant_client.delete_points.assert_called_with(
        collection_name=collection_name,
        points=vector_ids
    )


@pytest.mark.asyncio
async def test_delete_collection(vector_store, mock_qdrant_client):
    """Test deleting a collection."""
    # Test parameters
    collection_name = "test_collection"
    
    # Delete collection
    await vector_store.delete_collection(collection_name)
    
    # Check if delete was called correctly
    mock_qdrant_client.delete_collection.assert_called_with(
        collection_name=collection_name
    )


@pytest.mark.asyncio
async def test_get_collection_info(vector_store, mock_qdrant_client):
    """Test getting collection information."""
    # Set up mock response
    collection_info = MagicMock()
    collection_info.status = 200
    collection_info.config = MagicMock()
    collection_info.config.params = MagicMock()
    collection_info.config.params.vectors = MagicMock()
    collection_info.config.params.vectors.size = 384
    collection_info.config.params.vectors.distance = "Cosine"
    mock_qdrant_client.get_collection.return_value = collection_info
    
    # Test parameters
    collection_name = "test_collection"
    
    # Get collection info
    info = await vector_store.get_collection_info(collection_name)
    
    # Check results
    assert info is not None
    assert info.get("vector_size") == 384
    assert info.get("distance") == "Cosine"
    mock_qdrant_client.get_collection.assert_called_with(
        collection_name=collection_name
    )