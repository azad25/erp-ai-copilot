"""
Unit tests for Enhanced Knowledge Manager
Tests duplicate detection, content hashing, and versioning functionality
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import hashlib

from app.services.enhanced_knowledge_manager import (
    EnhancedKnowledgeManager, 
    KnowledgeEntry
)


class TestKnowledgeEntry:
    """Test KnowledgeEntry data class"""
    
    def test_knowledge_entry_creation(self):
        """Test creating a knowledge entry"""
        now = datetime.utcnow()
        entry = KnowledgeEntry(
            id="test-id",
            content="test content",
            content_hash="hash123",
            embeddings=[0.1, 0.2, 0.3],
            metadata={"type": "test"},
            source="test_source",
            created_at=now,
            updated_at=now,
            version=1
        )
        
        assert entry.id == "test-id"
        assert entry.content == "test content"
        assert entry.content_hash == "hash123"
        assert entry.version == 1
        assert entry.similarity_threshold == 0.85  # default value
    
    def test_knowledge_entry_to_dict(self):
        """Test converting knowledge entry to dictionary"""
        now = datetime.utcnow()
        entry = KnowledgeEntry(
            id="test-id",
            content="test content",
            content_hash="hash123",
            embeddings=[0.1, 0.2, 0.3],
            metadata={"type": "test"},
            source="test_source",
            created_at=now,
            updated_at=now,
            version=1
        )
        
        data = entry.to_dict()
        
        assert data["id"] == "test-id"
        assert data["content"] == "test content"
        assert data["created_at"] == now.isoformat()
        assert data["updated_at"] == now.isoformat()
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)
    
    def test_knowledge_entry_from_dict(self):
        """Test creating knowledge entry from dictionary"""
        now = datetime.utcnow()
        data = {
            "id": "test-id",
            "content": "test content",
            "content_hash": "hash123",
            "embeddings": [0.1, 0.2, 0.3],
            "metadata": {"type": "test"},
            "source": "test_source",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "version": 1,
            "similarity_threshold": 0.85
        }
        
        entry = KnowledgeEntry.from_dict(data)
        
        assert entry.id == "test-id"
        assert entry.content == "test content"
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.updated_at, datetime)


class TestEnhancedKnowledgeManager:
    """Test Enhanced Knowledge Manager functionality"""
    
    @pytest.fixture
    def manager(self):
        """Create Enhanced Knowledge Manager instance"""
        return EnhancedKnowledgeManager()
    
    def test_generate_content_hash(self, manager):
        """Test content hash generation"""
        content = "This is test content"
        expected_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        actual_hash = manager._generate_content_hash(content)
        
        assert actual_hash == expected_hash
        assert len(actual_hash) == 64  # SHA-256 produces 64-character hex string
    
    def test_generate_content_hash_consistency(self, manager):
        """Test that same content produces same hash"""
        content = "Consistent content for testing"
        
        hash1 = manager._generate_content_hash(content)
        hash2 = manager._generate_content_hash(content)
        
        assert hash1 == hash2
    
    def test_generate_content_hash_different_content(self, manager):
        """Test that different content produces different hashes"""
        content1 = "First content"
        content2 = "Second content"
        
        hash1 = manager._generate_content_hash(content1)
        hash2 = manager._generate_content_hash(content2)
        
        assert hash1 != hash2
    
    def test_generate_entry_id(self, manager):
        """Test entry ID generation"""
        source = "test_source"
        content_hash = "abc123"
        
        entry_id = manager._generate_entry_id(source, content_hash)
        
        # Should be MD5 hash of "source:content_hash"
        expected = hashlib.md5(f"{source}:{content_hash}".encode('utf-8')).hexdigest()
        assert entry_id == expected
        assert len(entry_id) == 32  # MD5 produces 32-character hex string
    
    @pytest.mark.asyncio
    async def test_check_duplicate_content_not_found(self, manager):
        """Test duplicate check when content doesn't exist"""
        content = "New unique content"
        
        # Mock MongoDB to return None
        with patch('app.services.enhanced_knowledge_manager.get_mongodb') as mock_mongo:
            mock_db = AsyncMock()
            mock_collection = AsyncMock()
            mock_collection.find_one.return_value = None
            mock_db.__getitem__.return_value = mock_collection
            mock_mongo.return_value = mock_db
            
            result = await manager.check_duplicate_content(content)
            
            assert result is None
            mock_collection.find_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_duplicate_content_found_in_cache(self, manager):
        """Test duplicate check when content exists in cache"""
        content = "Cached content"
        content_hash = manager._generate_content_hash(content)
        expected_id = "cached-entry-id"
        
        # Add to cache
        manager.content_hashes[content_hash] = expected_id
        
        result = await manager.check_duplicate_content(content)
        
        assert result == expected_id
    
    @pytest.mark.asyncio
    async def test_check_duplicate_content_found_in_db(self, manager):
        """Test duplicate check when content exists in database"""
        content = "Database content"
        content_hash = manager._generate_content_hash(content)
        expected_id = "db-entry-id"
        
        # Mock MongoDB to return existing entry
        with patch('app.services.enhanced_knowledge_manager.get_mongodb') as mock_mongo:
            mock_db = AsyncMock()
            mock_collection = AsyncMock()
            mock_collection.find_one.return_value = {"id": expected_id}
            mock_db.__getitem__.return_value = mock_collection
            mock_mongo.return_value = mock_db
            
            result = await manager.check_duplicate_content(content)
            
            assert result == expected_id
            # Should be added to cache
            assert manager.content_hashes[content_hash] == expected_id
    
    @pytest.mark.asyncio
    async def test_add_knowledge_entry_new_content(self, manager):
        """Test adding new knowledge entry"""
        content = "New knowledge content"
        metadata = {"type": "documentation", "category": "api"}
        source = "test_docs"
        
        # Mock dependencies
        with patch('app.services.enhanced_knowledge_manager.get_mongodb') as mock_mongo, \
             patch('app.services.enhanced_knowledge_manager.get_qdrant') as mock_qdrant, \
             patch('app.services.enhanced_knowledge_manager.get_llm_service') as mock_get_llm:
            
            # Setup mocks
            mock_db = AsyncMock()
            mock_collection = AsyncMock()
            mock_collection.find_one.return_value = None  # No duplicate
            mock_collection.replace_one = AsyncMock()
            mock_db.__getitem__.return_value = mock_collection
            mock_mongo.return_value = mock_db
            
            mock_qdrant_client = AsyncMock()
            mock_qdrant_client.upsert = AsyncMock()
            mock_qdrant.return_value = mock_qdrant_client
            
            mock_embeddings = [0.1, 0.2, 0.3, 0.4, 0.5]
            mock_llm_service = AsyncMock()
            mock_llm_service.generate_embeddings.return_value = mock_embeddings
            mock_get_llm.return_value = mock_llm_service
            
            # Execute
            result = await manager.add_knowledge_entry(content, metadata, source)
            
            # Verify
            assert result is not None
            assert len(result) == 32  # MD5 hash length
            
            # Verify LLM service was called
            mock_llm_service.generate_embeddings.assert_called_once_with(content)
            
            # Verify Qdrant was called
            mock_qdrant_client.upsert.assert_called_once()
            
            # Verify MongoDB was called
            mock_collection.replace_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_knowledge_entry_duplicate_content(self, manager):
        """Test adding duplicate knowledge entry updates existing"""
        content = "Duplicate content"
        metadata = {"type": "documentation"}
        source = "test_docs"
        existing_id = "existing-entry-id"
        
        # Mock duplicate detection
        with patch.object(manager, 'check_duplicate_content') as mock_check, \
             patch.object(manager, '_update_existing_entry') as mock_update:
            
            mock_check.return_value = existing_id
            mock_update.return_value = existing_id
            
            result = await manager.add_knowledge_entry(content, metadata, source)
            
            assert result == existing_id
            mock_check.assert_called_once_with(content)
            mock_update.assert_called_once_with(existing_id, content, metadata)
    
    @pytest.mark.asyncio
    async def test_query_knowledge_base(self, manager):
        """Test querying knowledge base"""
        query = "test query"
        
        # Mock dependencies
        with patch('app.services.enhanced_knowledge_manager.get_qdrant') as mock_qdrant, \
             patch('app.services.enhanced_knowledge_manager.get_llm_service') as mock_get_llm:
            
            # Setup mocks
            mock_qdrant_client = AsyncMock()
            mock_result = MagicMock()
            mock_result.id = "result-id"
            mock_result.score = 0.95
            mock_result.payload = {
                "content": "Result content",
                "source": "test_source",
                "metadata": {"type": "test"},
                "version": 1,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
            mock_qdrant_client.search.return_value = [mock_result]
            mock_qdrant.return_value = mock_qdrant_client
            
            mock_embeddings = [0.1, 0.2, 0.3]
            mock_llm_service = AsyncMock()
            mock_llm_service.generate_embeddings.return_value = mock_embeddings
            mock_get_llm.return_value = mock_llm_service
            
            # Execute
            results = await manager.query_knowledge_base(query, limit=5)
            
            # Verify
            assert len(results) == 1
            assert results[0]["id"] == "result-id"
            assert results[0]["score"] == 0.95
            assert results[0]["content"] == "Result content"
            
            # Verify LLM service was called
            mock_llm.generate_embeddings.assert_called_once_with(query)
            
            # Verify Qdrant search was called
            mock_qdrant_client.search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_status(self, manager):
        """Test getting knowledge manager status"""
        # Mock dependencies
        with patch('app.services.enhanced_knowledge_manager.get_qdrant') as mock_qdrant, \
             patch('app.services.enhanced_knowledge_manager.get_mongodb') as mock_mongo:
            
            # Setup mocks
            mock_qdrant_client = AsyncMock()
            mock_collection_info = MagicMock()
            mock_collection_info.vectors_count = 100
            mock_qdrant_client.get_collection.return_value = mock_collection_info
            mock_qdrant.return_value = mock_qdrant_client
            
            mock_db = AsyncMock()
            mock_collection = AsyncMock()
            mock_collection.count_documents.return_value = 95
            mock_db.__getitem__.return_value = mock_collection
            mock_mongo.return_value = mock_db
            
            # Add some cache entries
            manager.content_hashes = {"hash1": "id1", "hash2": "id2"}
            
            # Execute
            status = await manager.get_status()
            
            # Verify
            assert status["vector_count"] == 100
            assert status["metadata_count"] == 95
            assert status["cache_size"] == 2
            assert status["status"] == "active"
            assert status["similarity_threshold"] == 0.85


if __name__ == "__main__":
    pytest.main([__file__])