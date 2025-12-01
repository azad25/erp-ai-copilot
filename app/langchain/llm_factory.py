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
    provider: str = "huggingface",
    model: Optional[str] = None,
    temperature: float = 0.7,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs
) -> BaseLLM:
    """
    Get LangChain LLM instance
    
    Args:
        provider: LLM provider (gemini, openai, anthropic, ollama, huggingface)
        model: Model name (optional, uses default)
        temperature: Temperature for generation
        api_key: API key for the provider
        base_url: Base URL for custom endpoints (e.g., HuggingFace router)
        **kwargs: Additional provider-specific arguments
        
    Returns:
        LangChain LLM instance
    """
    if provider == "gemini":
        gemini_key = api_key or settings.llm.gemini_api_key
        if not gemini_key:
            raise ValueError("Gemini API key not configured")
        return ChatGoogleGenerativeAI(
            model=model or "gemini-2.0-flash-exp",
            google_api_key=gemini_key,
            temperature=temperature,
            **kwargs
        )
    
    elif provider == "openai":
        openai_key = api_key or settings.llm.openai_api_key
        if not openai_key:
            raise ValueError("OpenAI API key not configured")
        return ChatOpenAI(
            model=model or "gpt-4",
            openai_api_key=openai_key,
            temperature=temperature,
            **kwargs
        )
    
    elif provider == "anthropic":
        anthropic_key = api_key or settings.llm.anthropic_api_key
        if not anthropic_key:
            raise ValueError("Anthropic API key not configured")
        return ChatAnthropic(
            model=model or "claude-3-sonnet-20240229",
            anthropic_api_key=anthropic_key,
            temperature=temperature,
            **kwargs
        )
    
    elif provider == "huggingface":
        import os
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Get API token from parameter, environment, or settings
        api_token = api_key or os.getenv("HUGGINGFACEHUB_API_TOKEN") or os.getenv("HF_TOKEN")
        if not api_token:
            raise ValueError("HuggingFace API token not configured. Provide api_key parameter or set HUGGINGFACEHUB_API_TOKEN/HF_TOKEN environment variable.")
        
        # Clean the token (remove whitespace and quotes)
        api_token = api_token.strip().strip('"').strip("'")
        
        # Log token info for debugging (first/last 4 chars only)
        if len(api_token) > 8:
            logger.info(f"Using HuggingFace token: {api_token[:4]}...{api_token[-4:]}")
        
        model_name = model or settings.llm.default_model
        
        logger.info(f"HuggingFace provider - model: {model_name}, base_url: {base_url}")
        
        # Remove provider suffix from model name if present (e.g., "model:groq" -> "model")
        if ":" in model_name:
            logger.info(f"Detected model format with provider suffix: {model_name}")
            model_name = model_name.split(":")[0]
            logger.info(f"Using model name: {model_name}")
        
        # If base_url is provided, use OpenAI-compatible client (HuggingFace router, Novita, etc.)
        if base_url and base_url.strip():
            from langchain_openai import ChatOpenAI
            logger.info(f"Creating OpenAI-compatible client for custom endpoint: {base_url}")
            logger.info(f"Model: {model_name}")
            
            # For HuggingFace router, the API key should be the HF token
            # The OpenAI client will automatically add it as "Bearer <token>"
            # We just need to make sure we're passing the right token
            if "huggingface" in base_url.lower():
                logger.info("Detected HuggingFace router endpoint - using HF token as API key")
            
            return ChatOpenAI(
                model=model_name,
                api_key=api_token,  # Use api_key instead of openai_api_key
                base_url=base_url,
                temperature=temperature,
                **kwargs
            )
        
        # Otherwise use standard HuggingFace endpoint
        try:
            from langchain_huggingface import HuggingFaceEndpoint
            
            endpoint_kwargs = {
                "repo_id": model_name,
                "huggingfacehub_api_token": api_token,
                "temperature": temperature,
            }
            
            # Add any additional kwargs
            endpoint_kwargs.update(kwargs)
            
            logger.info(f"Creating HuggingFaceEndpoint with model: {model_name}")
            return HuggingFaceEndpoint(**endpoint_kwargs)
            
        except Exception as e:
            logger.error(f"Failed to create HuggingFaceEndpoint: {e}")
            logger.error(f"Model: {model_name}")
            logger.error(f"Token length: {len(api_token)}")
            
            # Try to provide more helpful error message
            error_msg = str(e)
            if "authenticate" in error_msg.lower():
                raise ValueError(
                    f"Failed to authenticate with HuggingFace. "
                    f"Please verify:\n"
                    f"1. Your API token is valid (get one from https://huggingface.co/settings/tokens)\n"
                    f"2. The token has 'Read access to contents of all public gated repos you can access' permission\n"
                    f"3. The model '{model_name}' exists and you have access to it\n"
                    f"4. If using HuggingFace router or custom endpoint, set the base_url in provider settings\n"
                    f"Original error: {error_msg}"
                )
            else:
                raise ValueError(f"Failed to create HuggingFace endpoint: {error_msg}")
    
    elif provider == "groq":
        from langchain_openai import ChatOpenAI
        import os
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Get Groq API key
        groq_key = api_key or os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise ValueError("Groq API key not configured. Provide api_key parameter or set GROQ_API_KEY environment variable.")
        
        # Clean the key
        groq_key = groq_key.strip().strip('"').strip("'")
        
        logger.info("Creating Groq client")
        
        return ChatOpenAI(
            model=model or "llama-3.3-70b-versatile",
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=temperature,
            **kwargs
        )
    
    elif provider == "ollama":
        # Use langchain-ollama for proper tool support (0.3.x+)
        from langchain_ollama import ChatOllama
        import os
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Get Ollama base URL (no API key needed for local Ollama)
        ollama_base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        logger.info(f"Creating Ollama client with base_url: {ollama_base_url}")
        logger.info(f"Using model: {model or 'unibase-erp:latest'}")
        
        # ChatOllama from langchain-ollama supports tool binding for compatible models
        return ChatOllama(
            model=model or "unibase-erp:latest",
            base_url=ollama_base_url,
            temperature=temperature,
            format="json" if kwargs.get("format") == "json" else None,  # Enable JSON mode if requested
            **{k: v for k, v in kwargs.items() if k != "format"}  # Pass other kwargs
        )
    
    else:
        # Default to HuggingFace
        from langchain_huggingface import HuggingFaceEndpoint
        import os
        
        # Get API token from parameter, environment, or settings
        api_token = api_key or os.getenv("HUGGINGFACEHUB_API_TOKEN") or os.getenv("HF_TOKEN")
        if not api_token:
            raise ValueError("HuggingFace API token not configured. Provide api_key parameter or set HUGGINGFACEHUB_API_TOKEN/HF_TOKEN environment variable.")
        
        return HuggingFaceEndpoint(
            repo_id=model or settings.llm.default_model,
            huggingfacehub_api_token=api_token,
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
