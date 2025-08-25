"""Unit tests for the embedding provider component.

Tests the embedding generation functionality, including single and batch embedding
generation, similarity calculation, and caching.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from app.rag.embeddings import EmbeddingProvider, get_embedding_provider


@pytest.fixture
def mock_sentence_transformer():
    """Create a mock SentenceTransformer for testing."""
    transformer = MagicMock()
    transformer.encode.return_value = np.array([0.1, 0.2, 0.3, 0.4])
    transformer.get_sentence_embedding_dimension.return_value = 4
    transformer.encode = MagicMock(return_value=np.array([0.1, 0.2, 0.3, 0.4]))
    return transformer


@pytest.fixture
def embedding_provider(mock_sentence_transformer):
    """Create an embedding provider with a mock transformer."""
    with patch("app.rag.embeddings.SentenceTransformer", return_value=mock_sentence_transformer):
        provider = EmbeddingProvider(model_name="all-MiniLM-L6-v2")
        return provider


@pytest.mark.asyncio
async def test_get_vector_size(embedding_provider, mock_sentence_transformer):
    """Test getting the vector size from the model."""
    vector_size = embedding_provider.vector_size
    assert vector_size == 4
    mock_sentence_transformer.get_sentence_embedding_dimension.assert_called_once()


def test_get_distance_metric(embedding_provider):
    """Test getting the distance metric."""
    distance_metric = embedding_provider.distance_metric
    assert distance_metric == "cosine"


@pytest.mark.asyncio
async def test_generate_embedding(embedding_provider, mock_sentence_transformer):
    """Test generating a single embedding."""
    text = "This is a test sentence."
    embedding = await embedding_provider.get_embedding(text)
    
    # Check embedding properties
    assert embedding is not None
    assert len(embedding) == 4
    assert all(isinstance(val, float) for val in embedding)
    mock_sentence_transformer.encode.assert_called_with(text, convert_to_numpy=True)


@pytest.mark.asyncio
async def test_generate_embeddings(embedding_provider, mock_sentence_transformer):
    """Test generating multiple embeddings."""
    texts = ["First test sentence.", "Second test sentence."]
    embeddings = await embedding_provider.get_embeddings(texts)
    
    # Check embeddings properties
    assert embeddings is not None
    assert len(embeddings) == 2
    assert all(len(embedding) == 4 for embedding in embeddings)
    assert all(isinstance(val, float) for embedding in embeddings for val in embedding)
    mock_sentence_transformer.encode.assert_called_with(texts, convert_to_numpy=True)


@pytest.mark.asyncio
async def test_calculate_similarity(embedding_provider):
    """Test calculating similarity between embeddings."""
    embedding1 = [0.1, 0.2, 0.3, 0.4]
    embedding2 = [0.2, 0.3, 0.4, 0.5]
    
    # Calculate similarity
    similarity = embedding_provider.calculate_similarity(embedding1, embedding2)
    
    # Check similarity value
    assert 0 <= similarity <= 1
    
    # Test with identical embeddings
    identical_similarity = embedding_provider.calculate_similarity(embedding1, embedding1)
    assert abs(identical_similarity - 1.0) < 1e-10


@pytest.mark.asyncio
async def test_get_embedding_provider_caching():
    """Test caching in the get_embedding_provider factory function."""
    with patch("app.rag.embeddings.EmbeddingProvider") as mock_provider_class:
        # First call should create a new provider
        provider1 = get_embedding_provider("all-MiniLM-L6-v2")
        mock_provider_class.assert_called_once_with(model_name="all-MiniLM-L6-v2")
        
        # Reset mock to check second call
        mock_provider_class.reset_mock()
        
        # Second call with same model should use cached provider
        provider2 = get_embedding_provider("all-MiniLM-L6-v2")
        mock_provider_class.assert_not_called()
        
        # Call with different model should create new provider
        provider3 = get_embedding_provider("different-model")
        mock_provider_class.assert_called_once_with(model_name="different-model")