#!/usr/bin/env python3
"""
Initialize default LLM providers in the database.

This script creates default provider configurations for all supported LLM providers.
Run this after database setup to populate the llm_provider_settings table.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database.connection import get_db_session, init_database, close_database
from app.models.llm_provider_settings import LLMProviderSettings
import structlog

logger = structlog.get_logger(__name__)


DEFAULT_PROVIDERS = [
    {
        "provider_name": "gemini",
        "display_name": "Google Gemini",
        "is_enabled": True,
        "is_default": True,
        "priority": 100,
        "available_models": ["gemini2.0:flash", "gemini2.5:pro"],
        "default_model": "gemini2.0:flash",
        "config": {
            "description": "Google's Gemini AI models with fast response times",
            "requires_api_key": True,
            "env_var": "GEMINI_API_KEY"
        }
    },
    {
        "provider_name": "groq",
        "display_name": "Groq",
        "is_enabled": False,
        "is_default": False,
        "priority": 90,
        "available_models": [
            "llama-3.3-70b-versatile",
            "llama-3.3-70b-specdec",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
            "openai/gpt-oss-20b"
        ],
        "default_model": "llama-3.3-70b-versatile",
        "config": {
            "description": "Groq's ultra-fast LLM inference with various open-source models",
            "requires_api_key": True,
            "env_var": "GROQ_API_KEY",
            "base_url": "https://api.groq.com/openai/v1"
        }
    },
    {
        "provider_name": "huggingface",
        "display_name": "HuggingFace",
        "is_enabled": False,
        "is_default": False,
        "priority": 80,
        "available_models": [
            "moonshotai/Kimi-K2-Thinking:novita",
            "meta-llama/Llama-3.3-70B-Instruct",
            "Qwen/Qwen2.5-72B-Instruct",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "google/gemma-2-9b-it",
            "microsoft/Phi-3-medium-4k-instruct"
        ],
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "base_url": "https://router.huggingface.co/v1",
        "config": {
            "description": "HuggingFace Router API with access to various open-source models",
            "requires_api_key": True,
            "env_var": "HF_TOKEN"
        }
    },
    {
        "provider_name": "openai",
        "display_name": "OpenAI",
        "is_enabled": False,
        "is_default": False,
        "priority": 70,
        "available_models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini"],
        "default_model": "gpt-4o-mini",
        "config": {
            "description": "OpenAI's GPT models including GPT-4 and GPT-3.5",
            "requires_api_key": True,
            "env_var": "OPENAI_API_KEY"
        }
    },
    {
        "provider_name": "anthropic",
        "display_name": "Anthropic Claude",
        "is_enabled": False,
        "is_default": False,
        "priority": 60,
        "available_models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229"
        ],
        "default_model": "claude-3-5-sonnet-20241022",
        "config": {
            "description": "Anthropic's Claude models with strong reasoning capabilities",
            "requires_api_key": True,
            "env_var": "ANTHROPIC_API_KEY"
        }
    },
    {
        "provider_name": "ollama",
        "display_name": "Ollama (Local)",
        "is_enabled": False,
        "is_default": False,
        "priority": 50,
        "available_models": ["unibase-erp"],
        "default_model": "unibase-erp",
        "base_url": "http://localhost:11434",
        "config": {
            "description": "Local Ollama instance for running models on-premise",
            "requires_api_key": False,
            "env_var": None
        }
    }
]


async def init_providers():
    """Initialize default LLM providers in the database."""
    logger.info("Initializing LLM providers...")
    
    try:
        # Initialize database
        await init_database()
        logger.info("Database connection established")
        
        # Get database session
        async for db in get_db_session():
            # Check existing providers
            result = await db.execute(select(LLMProviderSettings))
            existing_providers = {p.provider_name: p for p in result.scalars().all()}
            
            logger.info(f"Found {len(existing_providers)} existing providers")
            
            # Add or update providers
            for provider_data in DEFAULT_PROVIDERS:
                provider_name = provider_data["provider_name"]
                
                if provider_name in existing_providers:
                    logger.info(f"Provider '{provider_name}' already exists, skipping...")
                    continue
                
                # Create new provider
                provider = LLMProviderSettings(**provider_data)
                db.add(provider)
                logger.info(f"Added provider: {provider_name}")
            
            # Commit changes
            await db.commit()
            logger.info("All providers initialized successfully")
            
            # Display summary
            result = await db.execute(select(LLMProviderSettings))
            all_providers = result.scalars().all()
            
            print("\n" + "="*60)
            print("LLM PROVIDERS SUMMARY")
            print("="*60)
            for p in all_providers:
                status = "✓ ENABLED" if p.is_enabled else "✗ DISABLED"
                default = " (DEFAULT)" if p.is_default else ""
                print(f"{status}{default} - {p.display_name} ({p.provider_name})")
                print(f"  Priority: {p.priority}")
                print(f"  Models: {len(p.available_models or [])} available")
                print(f"  Default Model: {p.default_model or 'N/A'}")
                if p.api_key:
                    print(f"  API Key: Configured")
                else:
                    print(f"  API Key: Not configured")
                print()
            print("="*60)
            
            break  # Exit after first session
        
    except Exception as e:
        logger.error(f"Failed to initialize providers: {str(e)}", exc_info=True)
        raise
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(init_providers())
