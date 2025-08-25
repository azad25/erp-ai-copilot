"""Configuration settings for the RAG engine.

This module defines the configuration settings for the RAG engine, including
database connections, vector store settings, embedding model settings, and
caching parameters.
"""

from pydantic import BaseSettings, Field
from typing import Optional, Dict, Any, List


class RAGSettings(BaseSettings):
    """Configuration settings for the RAG engine."""
    
    # Feature flag to enable/disable RAG functionality
    rag_enabled: bool = Field(True, env="RAG_ENABLED")
    
    # MongoDB settings
    mongodb_collection: str = Field("documents", env="RAG_MONGODB_COLLECTION")
    
    # Vector store settings
    vector_store_type: str = Field("qdrant", env="RAG_VECTOR_STORE_TYPE")
    qdrant_host: str = Field("localhost", env="QDRANT_HOST")
    qdrant_port: int = Field(6333, env="QDRANT_PORT")
    qdrant_grpc_port: int = Field(6334, env="QDRANT_GRPC_PORT")
    qdrant_api_key: Optional[str] = Field(None, env="QDRANT_API_KEY")
    qdrant_collection_name: str = Field("documents", env="QDRANT_COLLECTION_NAME")
    qdrant_prefer_grpc: bool = Field(True, env="QDRANT_PREFER_GRPC")
    
    # Embedding model settings
    embedding_model_name: str = Field(
        "sentence-transformers/all-MiniLM-L6-v2", 
        env="RAG_EMBEDDING_MODEL_NAME"
    )
    embedding_model_device: str = Field("cpu", env="RAG_EMBEDDING_MODEL_DEVICE")
    embedding_model_cache_dir: Optional[str] = Field(None, env="RAG_EMBEDDING_MODEL_CACHE_DIR")
    
    # Document processing settings
    chunk_size: int = Field(500, env="RAG_CHUNK_SIZE")
    chunk_overlap: int = Field(50, env="RAG_CHUNK_OVERLAP")
    max_tokens_per_chunk: int = Field(256, env="RAG_MAX_TOKENS_PER_CHUNK")
    
    # Redis cache settings
    redis_enabled: bool = Field(True, env="REDIS_ENABLED")
    redis_host: str = Field("localhost", env="REDIS_HOST")
    redis_port: int = Field(6379, env="REDIS_PORT")
    redis_db: int = Field(0, env="REDIS_DB")
    redis_password: Optional[str] = Field(None, env="REDIS_PASSWORD")
    redis_cache_ttl: int = Field(3600, env="REDIS_CACHE_TTL")  # 1 hour in seconds
    
    # Kafka settings
    kafka_enabled: bool = Field(True, env="KAFKA_ENABLED")
    kafka_bootstrap_servers: str = Field("localhost:9092", env="KAFKA_BOOTSTRAP_SERVERS")
    kafka_document_ingestion_topic: str = Field(
        "document-ingestion", 
        env="KAFKA_DOCUMENT_INGESTION_TOPIC"
    )
    kafka_document_search_topic: str = Field(
        "document-search", 
        env="KAFKA_DOCUMENT_SEARCH_TOPIC"
    )
    kafka_document_update_topic: str = Field(
        "document-update", 
        env="KAFKA_DOCUMENT_UPDATE_TOPIC"
    )
    kafka_document_deletion_topic: str = Field(
        "document-deletion", 
        env="KAFKA_DOCUMENT_DELETION_TOPIC"
    )
    
    # Search settings
    default_search_limit: int = Field(10, env="RAG_DEFAULT_SEARCH_LIMIT")
    default_similarity_threshold: float = Field(0.7, env="RAG_DEFAULT_SIMILARITY_THRESHOLD")
    
    # Collection settings
    default_collections: List[str] = Field(
        ["guides", "policies", "procedures", "faq", "general"],
        env="RAG_DEFAULT_COLLECTIONS"
    )
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_rag_settings() -> RAGSettings:
    """Get the RAG settings.
    
    Returns:
        RAGSettings: The RAG settings.
    """
    return RAGSettings()