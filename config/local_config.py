"""
Local configuration for testing with local Ollama installation
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file first
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Set environment variables for local testing (only if not already set in .env)
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("DEFAULT_LLM_PROVIDER", "gemini")  # Use gemini from .env
os.environ.setdefault("DEFAULT_MODEL", "gemini2.0:flash")  # Use gemini model from .env
os.environ.setdefault("LOG_LEVEL", "debug")
os.environ.setdefault("ENVIRONMENT", "development")

# Service configuration
SERVICE_CONFIG = {
    "name": "ai-copilot",
    "version": "1.0.0",
    "environment": "development",
    "debug": True,
    "log_level": "debug"
}

# API configuration
API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8003,
    "grpc_port": 50051,
    "cors_origins": ["http://localhost:3000", "http://localhost:8003"]
}

# LLM configuration
LLM_CONFIG = {
    "default_provider": "gemini",
    "default_model": "gemini2.0:flash",
    "ollama": {
        "base_url": "http://localhost:11434",
        "timeout": 60,
        "max_retries": 3
    }
}

# Database configuration (for local testing)
DATABASE_CONFIG = {
    "enabled": False,  # Disable database for local testing
    "host": "localhost",
    "port": 5432,
    "name": "erp_ai_copilot",
    "user": "postgres",
    "password": "postgres"
}

# Redis configuration (for local testing)
REDIS_CONFIG = {
    "enabled": False,  # Disable Redis for local testing
    "host": "localhost",
    "port": 6379,
    "password": "",
    "db": 0
}

# RAG configuration
RAG_CONFIG = {
    "enabled": False,  # Disable RAG for local testing
    "collection_prefix": "erp",
    "embedding_model": "all-MiniLM-L6-v2",
    "similarity_threshold": 0.75,
    "max_results": 10
}

# Agent configuration
AGENT_CONFIG = {
    "timeout_seconds": 60,
    "max_retries": 3,
    "memory_ttl_hours": 24
}

def get_local_config():
    """Get local configuration dictionary."""
    return {
        "service": SERVICE_CONFIG,
        "api": API_CONFIG,
        "llm": LLM_CONFIG,
        "database": DATABASE_CONFIG,
        "redis": REDIS_CONFIG,
        "rag": RAG_CONFIG,
        "agent": AGENT_CONFIG
    }

def setup_local_environment():
    """Setup local environment variables."""
    config = get_local_config()
    
    # Set environment variables
    for section, settings in config.items():
        if isinstance(settings, dict):
            for key, value in settings.items():
                env_key = f"{section.upper()}_{key.upper()}"
                if isinstance(value, (str, int, bool)):
                    os.environ.setdefault(env_key, str(value))
    
    print("✅ Local environment configured successfully!")
    print(f"🤖 LLM Provider: {config['llm']['default_provider']}")
    print(f"🤖 Default Model: {config['llm']['default_model']}")
    print(f"🌐 API Host: {config['api']['host']}:{config['api']['port']}")
    print(f"🔧 Environment: {config['service']['environment']}")

if __name__ == "__main__":
    setup_local_environment()
