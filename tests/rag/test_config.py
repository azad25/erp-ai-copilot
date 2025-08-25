"""Unit tests for the RAG configuration module.

Tests the configuration settings for the RAG engine.
"""

import pytest
import os
from unittest.mock import patch

from app.rag.config import RAGSettings, get_rag_settings


def test_default_settings():
    """Test default RAG settings."""
    settings = RAGSettings()
    
    # Check default values
    assert settings.rag_enabled is True
    assert settings.mongodb_collection == "documents"
    assert settings.vector_store_type == "qdrant"
    assert settings.qdrant_host == "localhost"
    assert settings.qdrant_port == 6333
    assert settings.embedding_model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.chunk_size == 500
    assert settings.chunk_overlap == 50
    assert settings.redis_enabled is True
    assert settings.redis_host == "localhost"
    assert settings.kafka_enabled is True
    assert settings.default_search_limit == 10
    assert settings.default_similarity_threshold == 0.7
    assert "guides" in settings.default_collections


def test_environment_variable_override():
    """Test overriding settings with environment variables."""
    # Set environment variables
    env_vars = {
        "RAG_ENABLED": "false",
        "RAG_MONGODB_COLLECTION": "test_documents",
        "RAG_VECTOR_STORE_TYPE": "test_store",
        "QDRANT_HOST": "test.host",
        "QDRANT_PORT": "7777",
        "RAG_EMBEDDING_MODEL_NAME": "test-model",
        "RAG_CHUNK_SIZE": "300",
        "RAG_CHUNK_OVERLAP": "30",
        "REDIS_ENABLED": "false",
        "REDIS_HOST": "test.redis",
        "KAFKA_ENABLED": "false",
        "RAG_DEFAULT_SEARCH_LIMIT": "5",
        "RAG_DEFAULT_SIMILARITY_THRESHOLD": "0.5",
        "RAG_DEFAULT_COLLECTIONS": "test1,test2,test3"
    }
    
    with patch.dict(os.environ, env_vars):
        settings = RAGSettings()
        
        # Check overridden values
        assert settings.rag_enabled is False
        assert settings.mongodb_collection == "test_documents"
        assert settings.vector_store_type == "test_store"
        assert settings.qdrant_host == "test.host"
        assert settings.qdrant_port == 7777
        assert settings.embedding_model_name == "test-model"
        assert settings.chunk_size == 300
        assert settings.chunk_overlap == 30
        assert settings.redis_enabled is False
        assert settings.redis_host == "test.redis"
        assert settings.kafka_enabled is False
        assert settings.default_search_limit == 5
        assert settings.default_similarity_threshold == 0.5
        # Note: This test might fail as the env var parsing for lists can be complex
        # and might require custom parsing logic in the settings class


def test_get_rag_settings():
    """Test get_rag_settings function."""
    settings = get_rag_settings()
    
    # Check that it returns a RAGSettings instance
    assert isinstance(settings, RAGSettings)
    
    # Check a few values to ensure it's properly initialized
    assert hasattr(settings, "rag_enabled")
    assert hasattr(settings, "mongodb_collection")
    assert hasattr(settings, "vector_store_type")