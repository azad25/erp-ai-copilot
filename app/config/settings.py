"""
Configuration settings for the AI Copilot service.
"""
from typing import List, Optional
from pydantic import BaseSettings, Field, validator
import os


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    host: str = Field(default="localhost", env="DB_HOST")
    port: int = Field(default=5432, env="DB_PORT")
    name: str = Field(default="erp_ai_copilot", env="DB_NAME")
    user: str = Field(default="postgres", env="DB_USER")
    password: str = Field(default="postgres", env="DB_PASSWORD")
    ssl_mode: str = Field(default="disable", env="DB_SSL_MODE")
    max_connections: int = Field(default=20, env="DB_MAX_CONNECTIONS")
    min_connections: int = Field(default=5, env="DB_MIN_CONNECTIONS")
    
    @property
    def url(self) -> str:
        """Get database connection URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
    
    class Config:
        env_prefix = "DB_"


class RedisSettings(BaseSettings):
    """Redis configuration settings."""
    
    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    db: int = Field(default=0, env="REDIS_DB")
    pool_size: int = Field(default=10, env="REDIS_POOL_SIZE")
    decode_responses: bool = True
    
    @property
    def url(self) -> str:
        """Get Redis connection URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"
    
    class Config:
        env_prefix = "REDIS_"


class MongoDBSettings(BaseSettings):
    """MongoDB configuration settings."""
    
    uri: str = Field(default="mongodb://localhost:27017", env="MONGODB_URI")
    database: str = Field(default="erp_ai_conversations", env="MONGODB_DATABASE")
    max_pool_size: int = Field(default=10, env="MONGODB_MAX_POOL_SIZE")
    min_pool_size: int = Field(default=1, env="MONGODB_MIN_POOL_SIZE")
    
    class Config:
        env_prefix = "MONGODB_"


class QdrantSettings(BaseSettings):
    """Qdrant vector database configuration settings."""
    
    host: str = Field(default="localhost", env="QDRANT_HOST")
    port: int = Field(default=6333, env="QDRANT_PORT")
    grpc_port: int = Field(default=6334, env="QDRANT_GRPC_PORT")
    api_key: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    timeout: int = Field(default=30, env="QDRANT_TIMEOUT")
    
    @property
    def http_url(self) -> str:
        """Get Qdrant HTTP URL."""
        return f"http://{self.host}:{self.port}"
    
    @property
    def grpc_url(self) -> str:
        """Get Qdrant gRPC URL."""
        return f"{self.host}:{self.grpc_port}"
    
    class Config:
        env_prefix = "QDRANT_"


class KafkaSettings(BaseSettings):
    """Kafka configuration settings."""
    
    brokers: List[str] = Field(default=["localhost:9092"], env="KAFKA_BROKERS")
    topic_prefix: str = Field(default="ai-copilot", env="KAFKA_TOPIC_PREFIX")
    client_id: str = Field(default="ai-copilot-service", env="KAFKA_CLIENT_ID")
    group_id: str = Field(default="ai-copilot-group", env="KAFKA_GROUP_ID")
    auto_offset_reset: str = Field(default="earliest", env="KAFKA_AUTO_OFFSET_RESET")
    enable_auto_commit: bool = Field(default=True, env="KAFKA_ENABLE_AUTO_COMMIT")
    
    @validator('brokers', pre=True)
    def parse_brokers(cls, v):
        """Parse brokers string to list."""
        if isinstance(v, str):
            return [broker.strip() for broker in v.split(',')]
        return v
    
    class Config:
        env_prefix = "KAFKA_"


class AuthServiceSettings(BaseSettings):
    """Auth service gRPC configuration settings."""
    
    host: str = Field(default="localhost", env="AUTH_SERVICE_GRPC_HOST")
    port: int = Field(default=50051, env="AUTH_SERVICE_GRPC_PORT")
    timeout: int = Field(default=10, env="AUTH_SERVICE_GRPC_TIMEOUT")
    max_retries: int = Field(default=3, env="AUTH_SERVICE_GRPC_MAX_RETRIES")
    
    @property
    def address(self) -> str:
        """Get gRPC address."""
        return f"{self.host}:{self.port}"
    
    class Config:
        env_prefix = "AUTH_SERVICE_GRPC_"


class APIGatewaySettings(BaseSettings):
    """API Gateway configuration settings."""
    
    url: str = Field(default="http://localhost:8000", env="API_GATEWAY_URL")
    timeout: int = Field(default=30, env="API_GATEWAY_TIMEOUT")
    max_retries: int = Field(default=3, env="API_GATEWAY_MAX_RETRIES")
    
    class Config:
        env_prefix = "API_GATEWAY_"


class AISettings(BaseSettings):
    """AI model configuration settings."""
    
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    default_model: str = Field(default="gpt-4", env="AI_DEFAULT_MODEL")
    max_tokens: int = Field(default=4000, env="AI_MAX_TOKENS")
    temperature: float = Field(default=0.7, env="AI_TEMPERATURE")
    
    class Config:
        env_prefix = "AI_"


class RAGSettings(BaseSettings):
    """RAG (Retrieval-Augmented Generation) configuration settings."""
    
    enabled: bool = Field(default=True, env="RAG_ENABLED")
    collection_prefix: str = Field(default="erp", env="RAG_COLLECTION_PREFIX")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", env="RAG_EMBEDDING_MODEL")
    similarity_threshold: float = Field(default=0.75, env="RAG_SIMILARITY_THRESHOLD")
    max_results: int = Field(default=10, env="RAG_MAX_RESULTS")
    chunk_size: int = Field(default=1000, env="RAG_CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="RAG_CHUNK_OVERLAP")
    
    class Config:
        env_prefix = "RAG_"


class AgentSettings(BaseSettings):
    """Agent configuration settings."""
    
    timeout_seconds: int = Field(default=60, env="AGENT_TIMEOUT_SECONDS")
    max_retries: int = Field(default=3, env="AGENT_MAX_RETRIES")
    memory_ttl_hours: int = Field(default=24, env="AGENT_MEMORY_TTL_HOURS")
    max_concurrent_agents: int = Field(default=10, env="AGENT_MAX_CONCURRENT")
    
    class Config:
        env_prefix = "AGENT_"


class WebSocketSettings(BaseSettings):
    """WebSocket configuration settings."""
    
    max_connections: int = Field(default=1000, env="WS_MAX_CONNECTIONS")
    heartbeat_interval: int = Field(default=30, env="WS_HEARTBEAT_INTERVAL")
    connection_timeout: int = Field(default=300, env="WS_CONNECTION_TIMEOUT")
    max_message_size: int = Field(default=1048576, env="WS_MAX_MESSAGE_SIZE")  # 1MB
    
    class Config:
        env_prefix = "WS_"


class GRPCSettings(BaseSettings):
    """gRPC server configuration settings."""
    
    max_workers: int = Field(default=10, env="GRPC_MAX_WORKERS")
    max_concurrent_rpcs: int = Field(default=100, env="GRPC_MAX_CONCURRENT_RPCS")
    max_connection_idle: int = Field(default=300, env="GRPC_MAX_CONNECTION_IDLE")
    max_connection_age: int = Field(default=600, env="GRPC_MAX_CONNECTION_AGE")
    
    class Config:
        env_prefix = "GRPC_"


class SecuritySettings(BaseSettings):
    """Security configuration settings."""
    
    jwt_secret: str = Field(default="your-super-secret-jwt-key-change-in-production", env="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expiry_hours: int = Field(default=24, env="JWT_EXPIRY_HOURS")
    cors_origins: List[str] = Field(default=["http://localhost:3000"], env="CORS_ORIGINS")
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=3600, env="RATE_LIMIT_WINDOW")
    
    @validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins string to list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    class Config:
        env_prefix = "SECURITY_"


class MonitoringSettings(BaseSettings):
    """Monitoring and metrics configuration settings."""
    
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    health_check_interval: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")
    prometheus_port: int = Field(default=9090, env="PROMETHEUS_PORT")
    log_level: str = Field(default="info", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    
    class Config:
        env_prefix = "MONITORING_"


class ServiceSettings(BaseSettings):
    """Main service configuration settings."""
    
    name: str = Field(default="ai-copilot", env="SERVICE_NAME")
    version: str = Field(default="1.0.0", env="SERVICE_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # HTTP server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8080, env="PORT")
    workers: int = Field(default=1, env="WORKERS")
    
    # Resource limits
    max_concurrent_requests: int = Field(default=100, env="MAX_CONCURRENT_REQUESTS")
    request_timeout: int = Field(default=300, env="REQUEST_TIMEOUT")
    memory_limit_mb: int = Field(default=2048, env="MEMORY_LIMIT_MB")
    
    class Config:
        env_prefix = "SERVICE_"


class Settings(BaseSettings):
    """Main settings class that combines all configuration sections."""
    
    # Service configuration
    service: ServiceSettings = ServiceSettings()
    
    # Database configurations
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    mongodb: MongoDBSettings = MongoDBSettings()
    qdrant: QdrantSettings = QdrantSettings()
    
    # External services
    kafka: KafkaSettings = KafkaSettings()
    auth_service: AuthServiceSettings = AuthServiceSettings()
    api_gateway: APIGatewaySettings = APIGatewaySettings()
    
    # AI and RAG
    ai: AISettings = AISettings()
    rag: RAGSettings = RAGSettings()
    agent: AgentSettings = AgentSettings()
    
    # Communication
    websocket: WebSocketSettings = WebSocketSettings()
    grpc: GRPCSettings = GRPCSettings()
    
    # Security and monitoring
    security: SecuritySettings = SecuritySettings()
    monitoring: MonitoringSettings = MonitoringSettings()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings


# Environment-specific overrides
if os.getenv("ENVIRONMENT") == "production":
    settings.service.debug = False
    settings.monitoring.log_level = "warning"
    settings.database.max_connections = 50
    settings.redis.pool_size = 20
elif os.getenv("ENVIRONMENT") == "testing":
    settings.service.debug = True
    settings.monitoring.log_level = "debug"
    settings.database.name = "erp_ai_copilot_test"
    settings.mongodb.database = "erp_ai_conversations_test"
