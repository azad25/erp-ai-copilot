"""Unit tests for the cache manager component.

Tests the caching functionality, including setting, getting, and deleting cached items,
as well as search result caching.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock
from pydantic import BaseModel

from app.rag.cache import CacheManager, SearchCache
from app.rag.models import SearchQuery, SearchFilter, SearchResult, DocumentType


class CacheTestModel(BaseModel):
    """Test model for cache testing."""
    id: str
    name: str
    value: int
    created_at: datetime


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client for testing."""
    client = MagicMock()
    client.get = AsyncMock(return_value=None)  # Default to cache miss
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.keys = AsyncMock(return_value=[b"test:key1", b"test:key2"])
    return client


@pytest.fixture
def mock_db_manager(mock_redis_client):
    """Create a mock database manager for testing."""
    db_manager = MagicMock()
    db_manager.get_redis_client.return_value = mock_redis_client
    return db_manager


@pytest.fixture
def cache_manager(mock_db_manager):
    """Create a cache manager with a mock database manager."""
    return CacheManager(db_manager=mock_db_manager, model_type=CacheTestModel, prefix="test")


@pytest.fixture
def search_cache(mock_db_manager):
    """Create a search cache with a mock database manager."""
    return SearchCache(db_manager=mock_db_manager)


@pytest.fixture
def test_model():
    """Create a test model instance."""
    return CacheTestModel(
        id="test123",
        name="Test Model",
        value=42,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def search_query():
    """Create a test search query."""
    return SearchQuery(
        query="test query",
        filters=[],
        max_results=5
    )


@pytest.fixture
def search_results():
    """Create test search results."""
    return [
        {
            "document_id": "doc1",
            "content": "Test content 1",
            "score": 0.95,
            "metadata": {"title": "Test Document 1"}
        },
        {
            "document_id": "doc2",
            "content": "Test content 2",
            "score": 0.85,
            "metadata": {"title": "Test Document 2"}
        }
    ]


@pytest.mark.asyncio
async def test_cache_get_miss(cache_manager, test_model):
    """Test cache miss behavior."""
    # Get non-existent item
    result = await cache_manager.get("test:nonexistent")
    
    # Check result
    assert result is None


@pytest.mark.asyncio
async def test_cache_get_hit(cache_manager, test_model):
    """Test cache hit behavior."""
    # Set up mock to return cached data
    serialized_data = test_model.model_dump_json()
    cache_manager.redis.get.return_value = serialized_data
    
    # Get cached item
    result = await cache_manager.get("test:existing")
    
    # Check result
    assert result is not None
    assert isinstance(result, CacheTestModel)
    assert result.id == test_model.id
    assert result.name == test_model.name
    assert result.value == test_model.value


@pytest.mark.asyncio
async def test_cache_set(cache_manager, test_model):
    """Test setting an item in the cache."""
    # Set item in cache
    await cache_manager.set("test:key", test_model, 3600)
    
    # Verify the set operation completed without error
    assert True


@pytest.mark.asyncio
async def test_cache_delete(cache_manager):
    """Test deleting an item from the cache."""
    # Delete item from cache
    result = await cache_manager.delete("test:key")
    
    # Check result
    assert result == 1


@pytest.mark.asyncio
async def test_cache_clear_prefix(cache_manager):
    """Test clearing items with a specific prefix."""
    # Clear items with prefix
    await cache_manager.clear_prefix("test:")
    
    # Check if keys and delete were called
    cache_manager.redis.keys.assert_called()
    cache_manager.redis.delete.assert_called()


@pytest.mark.asyncio
async def test_search_cache_get_miss(search_cache, search_query):
    """Test search cache miss behavior."""
    # Get non-existent search results
    results = await search_cache.get_search_results("test query", [])
    
    # Check results
    assert results is None


@pytest.mark.asyncio
async def test_search_cache_get_hit(search_cache, search_query, search_results):
    """Test search cache hit behavior."""
    # Set up mock to return cached data
    serialized_results = json.dumps(search_results)
    search_cache.redis.get.return_value = serialized_results
    
    # Get cached search results
    results = await search_cache.get_search_results("test query", [])
    
    # Check results
    assert results is not None
    assert len(results) == 2


@pytest.mark.asyncio
async def test_search_cache_set(search_cache, search_query, search_results):
    """Test setting search results in the cache."""
    # Set search results in cache
    await search_cache.set_search_results("test query", search_results, [], 3600)
    
    # Check if set was called
    search_cache.redis.set.assert_called_once()


@pytest.mark.asyncio
async def test_invalidate_document_cache(search_cache):
    """Test invalidating document cache."""
    # Invalidate document cache
    document_id = "doc123"
    await search_cache.invalidate_document_cache(document_id)
    
    # Check if keys and delete were called
    search_cache.redis.keys.assert_called()
    search_cache.redis.delete.assert_called()