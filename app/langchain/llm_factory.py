"""
LLM Factory

Creates LangChain LLM instances for different providers.
"""

from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.llms.base import BaseLLM
from langchain.embeddings.base import Embeddings

from app.config.settings import get_settings

settings = get_settings()


def get_llm(
    provider: str = "gemini",
    model: Optional[str] = None,
    temperature: float = 0.7,
    **kwargs
) -> BaseLLM:
    """
    Get LangChain LLM instance
    
    Args:
        provider: LLM provider (gemini, openai, anthropic, ollama)
        model: Model name (optional, uses default)
        temperature: Temperature for generation
        **kwargs: Additional provider-specific arguments
        
    Returns:
        LangChain LLM instance
    """
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model or "gemini-2.0-flash-exp",
            google_api_key=settings.gemini_api_key,
            temperature=temperature,
            **kwargs
        )
    
    elif provider == "openai":
        return ChatOpenAI(
            model=model or "gpt-4",
            openai_api_key=settings.openai_api_key,
            temperature=temperature,
            **kwargs
        )
    
    elif provider == "anthropic":
        return ChatAnthropic(
            model=model or "claude-3-sonnet-20240229",
            anthropic_api_key=settings.anthropic_api_key,
            temperature=temperature,
            **kwargs
        )
    
    else:
        # Default to Gemini
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=settings.gemini_api_key,
            temperature=temperature,
            **kwargs
        )


def get_embeddings(
    model_name: str = "all-MiniLM-L6-v2",
    **kwargs
) -> Embeddings:
    """
    Get HuggingFace embeddings for RAG
    
    Args:
        model_name: HuggingFace model name
        **kwargs: Additional arguments
        
    Returns:
        LangChain Embeddings instance
    """
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True},
        **kwargs
    )
