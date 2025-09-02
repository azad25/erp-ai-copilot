"""
Configuration settings for the AI Copilot service.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyHttpUrl
from typing import Dict, Any, Optional, List, Union
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Service Configuration
    SERVICE_NAME: str = Field(default="ai-copilot", env="SERVICE_NAME")
    SERVICE_VERSION: str = Field(default="1.0.0", env="SERVICE_VERSION")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")
    LOG_LEVEL: str = Field(default="info", env="LOG_LEVEL")
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8003, env="PORT")
    SERVICE_MODE: str = Field(default="both", env="SERVICE_MODE")  # http, grpc, or both
    
    # Database Configuration (PostgreSQL)
    DB_HOST: str = Field(default="postgres", env="DB_HOST")
    DB_PORT: int = Field(default=5432, env="DB_PORT")
    DB_NAME: str = Field(default="erp_ai_copilot", env="DB_NAME")
    DB_USER: str = Field(default="postgres", env="DB_USER")
    DB_PASSWORD: str = Field(default="postgres", env="DB_PASSWORD")
    DB_SSL_MODE: str = Field(default="disable", env="DB_SSL_MODE")
    DB_MAX_CONNECTIONS: int = Field(default=20, env="DB_MAX_CONNECTIONS")
    DB_MIN_CONNECTIONS: int = Field(default=5, env="DB_MIN_CONNECTIONS")
    
    # MongoDB Configuration
    MONGODB_URI: str = Field(default="mongodb://root:password@mongodb:27017/", env="MONGODB_URI")
    MONGODB_DATABASE: str = Field(default="erp_ai_conversations", env="MONGODB_DATABASE")
    MONGODB_MAX_POOL_SIZE: int = Field(default=10, env="MONGODB_MAX_POOL_SIZE")
    MONGODB_MIN_POOL_SIZE: int = Field(default=1, env="MONGODB_MIN_POOL_SIZE")
    
    # Redis Configuration
    REDIS_HOST: str = Field(default="redis", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_PASSWORD: str = Field(default="redispassword", env="REDIS_PASSWORD")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_POOL_SIZE: int = Field(default=10, env="REDIS_POOL_SIZE")
    
    # Qdrant Configuration
    QDRANT_HOST: str = Field(default="qdrant", env="QDRANT_HOST")
    QDRANT_PORT: int = Field(default=6333, env="QDRANT_PORT")
    QDRANT_GRPC_PORT: int = Field(default=6334, env="QDRANT_GRPC_PORT")
    QDRANT_API_KEY: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    QDRANT_TIMEOUT: int = Field(default=30, env="QDRANT_TIMEOUT")
    
    # Kafka Configuration
    KAFKA_BROKERS: str = Field(default="kafka:29092", env="KAFKA_BROKERS")
    KAFKA_TOPIC_PREFIX: str = Field(default="ai-copilot", env="KAFKA_TOPIC_PREFIX")
    KAFKA_CLIENT_ID: str = Field(default="ai-copilot-service", env="KAFKA_CLIENT_ID")
    KAFKA_GROUP_ID: str = Field(default="ai-copilot-group", env="KAFKA_GROUP_ID")
    KAFKA_AUTO_OFFSET_RESET: str = Field(default="earliest", env="KAFKA_AUTO_OFFSET_RESET")
    
    # Elasticsearch Configuration
    ELASTICSEARCH_URLS: str = Field(default="http://elasticsearch:9200", env="ELASTICSEARCH_URLS")
    ELASTICSEARCH_INDEX_PREFIX: str = Field(default="ai-copilot", env="ELASTICSEARCH_INDEX_PREFIX")
    
    # JWT Configuration
    JWT_SECRET: str = Field(default="your-super-secret-jwt-key-change-in-production", env="JWT_SECRET")
    SECURITY_JWT_SECRET: str = Field(default="your-super-secret-jwt-key-change-in-production", env="SECURITY_JWT_SECRET")
    SECURITY_JWT_ALGORITHM: str = Field(default="HS256", env="SECURITY_JWT_ALGORITHM")
    SECURITY_JWT_EXPIRY_HOURS: int = Field(default=24, env="SECURITY_JWT_EXPIRY_HOURS")
    
    # CORS Configuration
    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://erp-frontend:3000,http://localhost:8003,http://localhost", env="CORS_ORIGINS")
    SECURITY_CORS_ORIGINS: str = Field(default="http://localhost:3000,http://erp-frontend:3000,http://localhost:8003,http://localhost", env="SECURITY_CORS_ORIGINS")
    
    # AI Model Configuration
    DEFAULT_LLM_PROVIDER: str = Field(default="gemini", env="DEFAULT_LLM_PROVIDER")
    DEFAULT_MODEL: str = Field(default="gemini2.0:flash", env="DEFAULT_MODEL")
    AI_DEFAULT_MODEL: str = Field(default="gemini2.0:flash", env="AI_DEFAULT_MODEL")
    AI_MAX_TOKENS: int = Field(default=4000, env="AI_MAX_TOKENS")
    AI_TEMPERATURE: float = Field(default=0.7, env="AI_TEMPERATURE")
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")
    OLLAMA_BASE_URL: str = Field(default="http://172.17.0.1:11434", env="OLLAMA_BASE_URL")
    
    # Auth Service Configuration
    AUTH_SERVICE_GRPC_HOST: str = Field(default="erp-suite-auth-service", env="AUTH_SERVICE_GRPC_HOST")
    AUTH_SERVICE_GRPC_PORT: int = Field(default=50051, env="AUTH_SERVICE_GRPC_PORT")
    
    # API Configuration
    API_HOST: str = Field(default="0.0.0.0", env="API_HOST")
    API_PORT: int = Field(default=8003, env="API_PORT")
    GRPC_PORT: int = Field(default=50055, env="GRPC_PORT")
    
    # Resource Limits
    MAX_CONCURRENT_REQUESTS: int = Field(default=100, env="MAX_CONCURRENT_REQUESTS")
    REQUEST_TIMEOUT: int = Field(default=300, env="REQUEST_TIMEOUT")
    MEMORY_LIMIT_MB: int = Field(default=2048, env="MEMORY_LIMIT_MB")
    
    # Agent Configuration
    AGENT_TIMEOUT_SECONDS: int = Field(default=60, env="AGENT_TIMEOUT_SECONDS")
    AGENT_MAX_RETRIES: int = Field(default=3, env="AGENT_MAX_RETRIES")
    AGENT_MEMORY_TTL_HOURS: int = Field(default=24, env="AGENT_MEMORY_TTL_HOURS")
    AGENT_MAX_CONCURRENT: int = Field(default=10, env="AGENT_MAX_CONCURRENT")
    
    # WebSocket Configuration
    WS_MAX_CONNECTIONS: int = Field(default=1000, env="WS_MAX_CONNECTIONS")
    WS_HEARTBEAT_INTERVAL: int = Field(default=30, env="WS_HEARTBEAT_INTERVAL")
    WS_CONNECTION_TIMEOUT: int = Field(default=300, env="WS_CONNECTION_TIMEOUT")
    WS_MAX_MESSAGE_SIZE: int = Field(default=1048576, env="WS_MAX_MESSAGE_SIZE")
    
    # gRPC Configuration
    GRPC_PORT: int = Field(default=50055, env="GRPC_PORT")
    GRPC_MAX_WORKERS: int = Field(default=10, env="GRPC_MAX_WORKERS")
    GRPC_MAX_CONCURRENT_RPCS: int = Field(default=100, env="GRPC_MAX_CONCURRENT_RPCS")
    GRPC_MAX_CONNECTION_IDLE: int = Field(default=300, env="GRPC_MAX_CONNECTION_IDLE")
    GRPC_MAX_CONNECTION_AGE: int = Field(default=600, env="GRPC_MAX_CONNECTION_AGE")
    GRPC_MAX_MESSAGE_SIZE: int = Field(default=52428800, env="GRPC_MAX_MESSAGE_SIZE")
    GRPC_SSL_CERT_PATH: str = Field(default="", env="GRPC_SSL_CERT_PATH")
    GRPC_SSL_KEY_PATH: str = Field(default="", env="GRPC_SSL_KEY_PATH")
    
    # RAG Configuration
    RAG_ENABLED: bool = Field(default=True, env="RAG_ENABLED")
    RAG_COLLECTION_PREFIX: str = Field(default="erp", env="RAG_COLLECTION_PREFIX")
    RAG_EMBEDDING_MODEL: str = Field(default="all-MiniLM-L6-v2", env="RAG_EMBEDDING_MODEL")
    RAG_SIMILARITY_THRESHOLD: float = Field(default=0.75, env="RAG_SIMILARITY_THRESHOLD")
    RAG_MAX_RESULTS: int = Field(default=10, env="RAG_MAX_RESULTS")
    RAG_CHUNK_SIZE: int = Field(default=1000, env="RAG_CHUNK_SIZE")
    RAG_CHUNK_OVERLAP: int = Field(default=200, env="RAG_CHUNK_OVERLAP")
    
    # Monitoring Configuration
    METRICS_ENABLED: bool = Field(default=True, env="METRICS_ENABLED")
    HEALTH_CHECK_INTERVAL: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")
    MONITORING_METRICS_ENABLED: bool = Field(default=True, env="MONITORING_METRICS_ENABLED")
    MONITORING_HEALTH_CHECK_INTERVAL: int = Field(default=30, env="MONITORING_HEALTH_CHECK_INTERVAL")
    MONITORING_PROMETHEUS_PORT: int = Field(default=9090, env="MONITORING_PROMETHEUS_PORT")
    MONITORING_LOG_LEVEL: str = Field(default="info", env="MONITORING_LOG_LEVEL")
    MONITORING_LOG_FORMAT: str = Field(default="json", env="MONITORING_LOG_FORMAT")
    
    @property
    def database_url(self) -> str:
        """Construct PostgreSQL database URL."""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL."""
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def qdrant_url(self) -> str:
        """Construct Qdrant URL."""
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS origins string to list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def kafka_brokers_list(self) -> List[str]:
        """Convert Kafka brokers string to list."""
        return [broker.strip() for broker in self.KAFKA_BROKERS.split(",")]
    
    @property
    def elasticsearch_urls_list(self) -> List[str]:
        """Convert Elasticsearch URLs string to list."""
        return [url.strip() for url in self.ELASTICSEARCH_URLS.split(",")]

# Create settings instance
settings = Settings()

# Service configuration
service = {
    "debug": settings.DEBUG,
    "name": settings.SERVICE_NAME,
    "version": settings.SERVICE_VERSION,
    "environment": settings.ENVIRONMENT
}
