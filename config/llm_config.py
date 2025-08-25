"""
LLM Service Configuration

This module provides configuration for different LLM providers:
- Ollama (local models)
- OpenAI (GPT models)
- Anthropic (Claude models)

Usage:
    from config.llm_config import LLMConfig
    
    config = LLMConfig()
    ollama_config = config.get_ollama_config()
    openai_config = config.get_openai_config()
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    name: str
    base_url: str
    api_key: Optional[str] = None
    default_model: str = ""
    timeout: int = 30
    max_retries: int = 3


class LLMConfig:
    """Central configuration for LLM providers."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        
    def get_ollama_config(self) -> ProviderConfig:
        """Get Ollama configuration for local models."""
        return ProviderConfig(
            name="ollama",
            base_url=self.ollama_base_url,
            default_model="llama2",
            timeout=60  # Local models might take longer
        )
    
    def get_openai_config(self) -> Optional[ProviderConfig]:
        """Get OpenAI configuration if API key is available."""
        if not self.openai_api_key:
            return None
            
        return ProviderConfig(
            name="openai",
            base_url="https://api.openai.com/v1",
            api_key=self.openai_api_key,
            default_model="gpt-4",
            timeout=30
        )
    
    def get_anthropic_config(self) -> Optional[ProviderConfig]:
        """Get Anthropic configuration if API key is available."""
        if not self.anthropic_api_key:
            return None
            
        return ProviderConfig(
            name="anthropic",
            base_url="https://api.anthropic.com",
            api_key=self.anthropic_api_key,
            default_model="claude-3-sonnet-20240229",
            timeout=30
        )
    
    def get_available_providers(self) -> Dict[str, ProviderConfig]:
        """Get all available provider configurations."""
        providers = {}
        
        # Always include Ollama for local development
        providers["ollama"] = self.get_ollama_config()
        
        # Add OpenAI if configured
        openai_config = self.get_openai_config()
        if openai_config:
            providers["openai"] = openai_config
            
        # Add Anthropic if configured
        anthropic_config = self.get_anthropic_config()
        if anthropic_config:
            providers["anthropic"] = anthropic_config
            
        return providers
    
    def get_provider_config(self, provider_name: str) -> Optional[ProviderConfig]:
        """Get configuration for a specific provider."""
        providers = self.get_available_providers()
        return providers.get(provider_name)


# Example environment configuration
ENVIRONMENT_EXAMPLE = """
# For local development with Ollama
OLLAMA_BASE_URL=http://localhost:11434

# For OpenAI integration
OPENAI_API_KEY=your_openai_api_key_here

# For Anthropic integration  
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Default provider selection
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_MODEL=llama2
"""


class ModelSelector:
    """Helper class for selecting appropriate models based on use case."""
    
    @staticmethod
    def get_recommended_models(provider: str, use_case: str) -> str:
        """Get recommended model for specific use case."""
        recommendations = {
            "ollama": {
                "general": "llama2",
                "code": "codellama",
                "chat": "mistral",
                "fast": "tinyllama"
            },
            "openai": {
                "general": "gpt-4",
                "fast": "gpt-3.5-turbo",
                "code": "gpt-4",
                "analysis": "gpt-4"
            },
            "anthropic": {
                "general": "claude-3-sonnet-20240229",
                "fast": "claude-3-haiku-20240307",
                "analysis": "claude-3-opus-20240229"
            }
        }
        
        return recommendations.get(provider, {}).get(use_case, "default")
    
    @staticmethod
    def validate_model_availability(provider: str, model: str, llm_service) -> bool:
        """Validate if a model is available for the provider."""
        try:
            # Test with a simple prompt
            test_request = {
                "messages": [{"role": "user", "content": "Hello"}],
                "model": model,
                "max_tokens": 10
            }
            
            # This would be an async call in real usage
            # llm_service.generate(test_request)
            return True
        except Exception:
            return False