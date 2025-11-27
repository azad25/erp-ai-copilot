"""
LLM Provider Settings Model

Database model for storing LLM provider configurations and API keys.
"""

from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.models.database import Base


class LLMProviderSettings(Base):
    """Model for LLM provider settings."""
    
    __tablename__ = "llm_provider_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    provider_name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    api_key = Column(Text, nullable=True)  # Encrypted in production
    base_url = Column(String(255), nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    priority = Column(Integer, default=0, nullable=False)  # Higher priority = tried first
    config = Column(JSON, nullable=True)  # Additional provider-specific config
    available_models = Column(JSON, nullable=True)  # List of available models
    default_model = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<LLMProviderSettings(provider={self.provider_name}, enabled={self.is_enabled})>"
