"""
LLM Service

Provides unified interface for interacting with various LLM providers:
- Local Ollama models
- OpenAI API (GPT-4, GPT-3.5-turbo, etc.)
- Anthropic API (Claude models)
- Google Gemini API
- Future extensibility for other providers
"""

import os
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator, ClassVar
from abc import ABC, abstractmethod
import structlog
from pydantic import BaseModel, Field
import httpx
import json
from pathlib import Path

# Import settings
from app.core.config import settings
from app.utils.modelfile_loader import get_default_system_prompt

# Import LLM provider libraries
try:
    import openai
    from openai import AsyncOpenAI
except ImportError:
    openai = None

try:
    import anthropic
    from anthropic import AsyncAnthropic
except ImportError:
    anthropic = None

try:
    import ollama
except ImportError:
    ollama = None

try:
    from google import genai
except ImportError:
    genai = None

from app.core.exceptions import AIModelError


class LLMMessage(BaseModel):
    """Message format for LLM interactions"""
    role: str  # 'system', 'user', 'assistant'
    content: str


class LLMRequest(BaseModel):
    """Request model for LLM calls"""
    messages: List[LLMMessage]
    model: str
    temperature: float = 0.7
    max_tokens: int = 4000
    stream: bool = False
    system_prompt: Optional[str] = Field(
        default=None,
        description="System prompt to guide the model's behavior. If None, the default system prompt will be used."
    )


class LLMResponse(BaseModel):
    """Response model for LLM calls"""
    content: str
    model: str
    tokens_used: int
    finish_reason: str
    metadata: Dict[str, Any] = {}


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM"""
        pass

    @abstractmethod
    async def generate_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the LLM"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate that the provider is properly configured"""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = None
        if self.api_key and openai:
            self.client = AsyncOpenAI(api_key=self.api_key)

    def validate_config(self) -> bool:
        return self.api_key is not None and openai is not None

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.client:
            raise AIModelError("openai", request.model, "OpenAI client not initialized")

        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            
            messages.extend([
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ])

            response = await self.client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                tokens_used=response.usage.total_tokens,
                finish_reason=response.choices[0].finish_reason,
                metadata={"provider": "openai"}
            )

        except Exception as e:
            raise AIModelError("openai", request.model, f"OpenAI API error: {str(e)}")

    async def generate_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        if not self.client:
            raise AIModelError("openai", request.model, "OpenAI client not initialized")

        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            
            messages.extend([
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ])

            stream = await self.client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise AIModelError("openai", request.model, f"OpenAI streaming error: {str(e)}")


class AnthropicProvider(BaseLLMProvider):
    """Anthropic API provider"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = None
        if self.api_key and anthropic:
            self.client = AsyncAnthropic(api_key=self.api_key)

    def validate_config(self) -> bool:
        return self.api_key is not None and anthropic is not None

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.client:
            raise AIModelError("anthropic", request.model, "Anthropic client not initialized")

        try:
            system_prompt = request.system_prompt
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
                if msg.role != "system"
            ]

            response = await self.client.messages.create(
                model=request.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                system=system_prompt,
                messages=messages
            )

            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                finish_reason=response.stop_reason,
                metadata={"provider": "anthropic"}
            )

        except Exception as e:
            raise AIModelError("anthropic", request.model, f"Anthropic API error: {str(e)}")

    async def generate_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        if not self.client:
            raise AIModelError("anthropic", request.model, "Anthropic client not initialized")

        try:
            system_prompt = request.system_prompt
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
                if msg.role != "system"
            ]

            stream = await self.client.messages.create(
                model=request.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                system=system_prompt,
                messages=messages,
                stream=True
            )

            async for chunk in stream:
                if chunk.type == "content_block_delta":
                    yield chunk.delta.text

        except Exception as e:
            raise AIModelError("anthropic", request.model, f"Anthropic streaming error: {str(e)}")


class OllamaProvider(BaseLLMProvider):
    """Local Ollama provider"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.client = None
        if ollama:
            self.client = ollama.AsyncClient(host=self.base_url)

    def validate_config(self) -> bool:
        return ollama is not None

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.client:
            raise AIModelError("ollama", request.model, "Ollama client not initialized")

        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            
            messages.extend([
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ])

            response = await self.client.chat(
                model=request.model,
                messages=messages,
                options={
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens
                }
            )

            return LLMResponse(
                content=response["message"]["content"],
                model=response["model"],
                tokens_used=response.get("eval_count", 0) + response.get("prompt_eval_count", 0),
                finish_reason="stop",
                metadata={"provider": "ollama"}
            )

        except Exception as e:
            raise AIModelError("ollama", request.model, f"Ollama API error: {str(e)}")

    async def generate_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        if not self.client:
            raise AIModelError("ollama", request.model, "Ollama client not initialized")

        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            
            messages.extend([
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ])

            stream = await self.client.chat(
                model=request.model,
                messages=messages,
                options={
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens
                },
                stream=True
            )

            async for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]

        except Exception as e:
            raise AIModelError("ollama", request.model, f"Ollama streaming error: {str(e)}")


# Gemini Integration
try:
    import httpx
except ImportError:
    httpx = None


class GroqProvider(BaseLLMProvider):
    """Groq API provider using OpenAI-compatible interface."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Groq provider.
        
        Args:
            api_key: Groq API key
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1"
        self.client = None
        self.logger = structlog.get_logger("groq_provider")
        
        if self.api_key and openai:
            try:
                self.client = AsyncOpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key
                )
                self.logger.info("Groq provider initialized", base_url=self.base_url)
            except Exception as e:
                self.logger.warning(f"Failed to initialize Groq client: {str(e)}")

    def validate_config(self) -> bool:
        """Validate that the provider is properly configured."""
        if not self.api_key:
            self.logger.warning("Groq API key not configured")
            return False
        if not openai:
            self.logger.warning("OpenAI library not available for Groq provider")
            return False
        return True

    def get_available_models(self) -> List[str]:
        """Get list of available models for this provider."""
        return [
            "llama-3.3-70b-versatile",
            "llama-3.3-70b-specdec",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
            "openai/gpt-oss-20b"
        ]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM.
        
        Args:
            request: The LLM request containing messages and generation parameters
            
        Returns:
            LLMResponse containing the generated content and metadata
            
        Raises:
            AIModelError: If there's an error generating the response
        """
        if not self.client:
            raise AIModelError("groq", request.model, "Groq client not initialized")

        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            
            messages.extend([
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ])

            response = await self.client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                finish_reason=response.choices[0].finish_reason,
                metadata={"provider": "groq"}
            )

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Groq API error: {error_msg}", model=request.model)
            raise AIModelError("groq", request.model, f"Groq API error: {error_msg}")

    async def generate_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the LLM.
        
        Args:
            request: The LLM request containing messages and generation parameters
            
        Yields:
            Chunks of the generated response as they become available
            
        Raises:
            AIModelError: If there's an error generating the response
        """
        if not self.client:
            raise AIModelError("groq", request.model, "Groq client not initialized")

        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            
            messages.extend([
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ])

            stream = await self.client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Groq streaming error: {error_msg}", model=request.model)
            raise AIModelError("groq", request.model, f"Groq streaming error: {error_msg}")


class HuggingFaceProvider(BaseLLMProvider):
    """HuggingFace Router API provider using OpenAI-compatible interface."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize HuggingFace provider.
        
        Args:
            api_key: HuggingFace API token (HF_TOKEN)
            base_url: Base URL for HuggingFace Router API
        """
        self.api_key = api_key or os.getenv("HF_TOKEN")
        self.base_url = base_url or "https://router.huggingface.co/v1"
        self.client = None
        self.logger = structlog.get_logger("huggingface_provider")
        
        if self.api_key and openai:
            try:
                self.client = AsyncOpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key
                )
                self.logger.info("HuggingFace provider initialized", base_url=self.base_url)
            except Exception as e:
                self.logger.warning(f"Failed to initialize HuggingFace client: {str(e)}")

    def validate_config(self) -> bool:
        """Validate that the provider is properly configured."""
        if not self.api_key:
            self.logger.warning("HuggingFace API token not configured")
            return False
        if not openai:
            self.logger.warning("OpenAI library not available for HuggingFace provider")
            return False
        return True

    def get_available_models(self) -> List[str]:
        """Get list of available models for this provider."""
        return [
            "moonshotai/Kimi-K2-Thinking:novita",
            "openai/gpt-oss-20b:groq",
            "meta-llama/Llama-3.3-70B-Instruct",
            "Qwen/Qwen2.5-72B-Instruct",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "google/gemma-2-9b-it",
            "microsoft/Phi-3-medium-4k-instruct"
        ]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM.
        
        Args:
            request: The LLM request containing messages and generation parameters
            
        Returns:
            LLMResponse containing the generated content and metadata
            
        Raises:
            AIModelError: If there's an error generating the response
        """
        if not self.client:
            raise AIModelError("huggingface", request.model, "HuggingFace client not initialized")

        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            
            messages.extend([
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ])

            response = await self.client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                finish_reason=response.choices[0].finish_reason,
                metadata={"provider": "huggingface"}
            )

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"HuggingFace API error: {error_msg}", model=request.model)
            raise AIModelError("huggingface", request.model, f"HuggingFace API error: {error_msg}")

    async def generate_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the LLM.
        
        Args:
            request: The LLM request containing messages and generation parameters
            
        Yields:
            Chunks of the generated response as they become available
            
        Raises:
            AIModelError: If there's an error generating the response
        """
        if not self.client:
            raise AIModelError("huggingface", request.model, "HuggingFace client not initialized")

        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            
            messages.extend([
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ])

            stream = await self.client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"HuggingFace streaming error: {error_msg}", model=request.model)
            raise AIModelError("huggingface", request.model, f"HuggingFace streaming error: {error_msg}")


class GeminiProvider(BaseLLMProvider):
    """Gemini LLM Provider using google-genai SDK."""

    def __init__(self, api_key: str = None, base_url: str = None):
        """Initialize Gemini provider.
        
        Args:
            api_key: Gemini API key (GEMINI_API_KEY environment variable)
            base_url: Not used for Gemini (kept for interface compatibility)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        self.default_model = "gemini-2.5-flash"
        self.logger = structlog.get_logger("gemini_provider")
        
        if self.api_key and genai:
            try:
                # Set API key in environment for genai client
                os.environ["GEMINI_API_KEY"] = self.api_key
                # Initialize the client (it will automatically use GEMINI_API_KEY from env)
                self.client = genai.Client()
                self.logger.info("Gemini provider initialized with google-genai SDK")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Gemini client: {str(e)}")
        elif not self.api_key:
            self.logger.warning("GEMINI_API_KEY not found in environment variables")
        elif not genai:
            self.logger.warning("google-genai library not available")

    def validate_config(self) -> bool:
        """Validate that the provider is properly configured."""
        if not self.api_key:
            self.logger.warning("Gemini API key not configured")
            return False
        if not genai:
            self.logger.warning("google-genai library not available")
            return False
        return True

    def get_available_models(self) -> List[str]:
        """Get list of available models for this provider."""
        return ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM.
        
        Args:
            request: The LLM request containing messages and generation parameters
            
        Returns:
            LLMResponse containing the generated content and metadata
            
        Raises:
            AIModelError: If there's an error generating the response
        """
        if not self.client:
            raise AIModelError("gemini", request.model, "Gemini client not initialized")
            
        model = request.model or self.default_model
        
        try:
            # Build the content string from messages
            contents = []
            system_instruction = None
            
            # Extract system prompt
            if request.system_prompt:
                system_instruction = request.system_prompt
            
            # Process messages
            for msg in request.messages:
                if msg.role == "system":
                    system_instruction = msg.content
                elif msg.role == "user":
                    contents.append(msg.content)
                elif msg.role == "assistant":
                    # For multi-turn conversations, we'd need to structure this differently
                    # For now, append as context
                    contents.append(f"Assistant: {msg.content}")
            
            # Combine all content
            combined_content = "\n\n".join(contents)
            
            # Add system instruction as prefix if provided
            if system_instruction:
                combined_content = f"{system_instruction}\n\n{combined_content}"
            
            # Generate content using the new SDK
            response = self.client.models.generate_content(
                model=model,
                contents=combined_content,
                config={
                    "temperature": request.temperature,
                    "max_output_tokens": request.max_tokens,
                    "top_p": 0.95,
                    "top_k": 40,
                }
            )
            
            # Extract the response text
            content = response.text
            
            # Estimate token usage (approximate)
            tokens_used = len(content.split()) + len(combined_content.split())
            
            return LLMResponse(
                content=content,
                model=model,
                tokens_used=tokens_used,
                finish_reason="stop",
                metadata={"provider": "gemini"}
            )
                
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Gemini API error: {error_msg}", model=model)
            raise AIModelError("gemini", model, f"Gemini API error: {error_msg}") from e
    
    async def generate_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the LLM.
        
        Args:
            request: The LLM request containing messages and generation parameters
            
        Yields:
            Chunks of the generated response as they become available
            
        Raises:
            AIModelError: If there's an error generating the response
        """
        if not self.client:
            raise AIModelError("gemini", request.model, "Gemini client not initialized")
            
        model = request.model or self.default_model
        
        try:
            # Build the content string from messages
            contents = []
            system_instruction = None
            
            # Extract system prompt
            if request.system_prompt:
                system_instruction = request.system_prompt
            
            # Process messages
            for msg in request.messages:
                if msg.role == "system":
                    system_instruction = msg.content
                elif msg.role == "user":
                    contents.append(msg.content)
                elif msg.role == "assistant":
                    contents.append(f"Assistant: {msg.content}")
            
            # Combine all content
            combined_content = "\n\n".join(contents)
            
            # Add system instruction as prefix if provided
            if system_instruction:
                combined_content = f"{system_instruction}\n\n{combined_content}"
            
            # Generate content with streaming
            response = self.client.models.generate_content_stream(
                model=model,
                contents=combined_content,
                config={
                    "temperature": request.temperature,
                    "max_output_tokens": request.max_tokens,
                    "top_p": 0.95,
                    "top_k": 40,
                }
            )
            
            # Stream the response chunks
            for chunk in response:
                if hasattr(chunk, 'text') and chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Gemini streaming error: {error_msg}", model=model)
            raise AIModelError("gemini", model, f"Gemini streaming error: {error_msg}") from e


class LLMService:
    """
    Unified LLM service supporting multiple providers
    
    Supports:
    - OpenAI (GPT-4, GPT-3.5-turbo, etc.)
    - Anthropic (Claude models)
    - Local Ollama models
    - Future extensibility for other providers
    """

    def __init__(self, default_system_prompt: Optional[str] = None, provider: Optional[str] = None):
        """Initialize the LLM service.
        
        Args:
            default_system_prompt: Optional default system prompt to use.
                                 If None, will be loaded from the Modelfile.
            provider: Preferred LLM provider to use (e.g., 'ollama', 'gemini').
                     If None, will use the first available provider.
        """
        self.logger = structlog.get_logger("llm_service")
        # Import here to avoid circular imports
        from app.utils.modelfile_loader import get_default_system_prompt
        self.default_system_prompt = default_system_prompt or get_default_system_prompt()
        self.preferred_provider = provider.lower() if provider else None
        self.providers: Dict[str, BaseLLMProvider] = {}
        self._initialize_providers()
        self.logger.info("LLM Service initialized", 
                       preferred_provider=self.preferred_provider or 'auto',
                       prompt_length=len(self.default_system_prompt))

    async def _load_provider_settings_from_db(self) -> Dict[str, Dict[str, Any]]:
        """Load provider settings from database."""
        try:
            from app.database.connection import get_db_session
            from app.models.llm_provider_settings import LLMProviderSettings
            from sqlalchemy import select
            
            async for db in get_db_session():
                result = await db.execute(
                    select(LLMProviderSettings).where(LLMProviderSettings.is_enabled == True)
                )
                providers = result.scalars().all()
                
                settings_map = {}
                for p in providers:
                    settings_map[p.provider_name] = {
                        "api_key": p.api_key,
                        "base_url": p.base_url,
                        "default_model": p.default_model,
                        "priority": p.priority,
                        "is_default": p.is_default
                    }
                
                self.logger.info(f"Loaded {len(settings_map)} provider settings from database")
                return settings_map
        except Exception as e:
            self.logger.warning(f"Failed to load provider settings from database: {str(e)}")
            return {}

    def _initialize_providers(self):
        """Initialize all available LLM providers"""
        # Try to load settings from database (async)
        import asyncio
        try:
            db_settings = asyncio.run(self._load_provider_settings_from_db())
        except Exception as e:
            self.logger.warning(f"Could not load DB settings, using environment variables: {str(e)}")
            db_settings = {}
        
        # Initialize providers in order of preference
        providers_to_init = [
            ("ollama", OllamaProvider),
            ("gemini", GeminiProvider),
            ("groq", GroqProvider),
            ("huggingface", HuggingFaceProvider),
            ("openai", OpenAIProvider),
            ("anthropic", AnthropicProvider)
        ]
        
        # If a preferred provider is specified, move it to the front of the list
        if self.preferred_provider:
            for i, (name, _) in enumerate(providers_to_init):
                if name == self.preferred_provider:
                    # Move preferred provider to the front
                    providers_to_init.insert(0, providers_to_init.pop(i))
                    break
        
        # Initialize providers
        for provider_name, provider_class in providers_to_init:
            try:
                # Get API key from database first, then fall back to environment
                db_config = db_settings.get(provider_name, {})
                api_key = db_config.get("api_key") or os.getenv(self._get_env_var_name(provider_name))
                base_url = db_config.get("base_url")
                
                if provider_name == "gemini":
                    if not api_key:
                        self.logger.warning(f"{provider_name}: API key not found in DB or environment")
                        continue
                    provider = provider_class(api_key=api_key, base_url=base_url)
                elif provider_name == "groq":
                    if not api_key:
                        self.logger.info(f"{provider_name}: API key not found in DB or environment, will skip")
                        continue
                    provider = provider_class(api_key=api_key)
                    self.logger.info(f"Groq provider initialized with API key from {'database' if db_config.get('api_key') else 'environment'}")
                elif provider_name == "huggingface":
                    if not api_key:
                        self.logger.warning(f"{provider_name}: API key not found in DB or environment")
                        continue
                    provider = provider_class(api_key=api_key, base_url=base_url)
                elif provider_name == "openai":
                    if not api_key:
                        self.logger.info(f"{provider_name}: API key not found, skipping")
                        continue
                    provider = provider_class(api_key=api_key)
                elif provider_name == "anthropic":
                    if not api_key:
                        self.logger.info(f"{provider_name}: API key not found, skipping")
                        continue
                    provider = provider_class(api_key=api_key)
                else:
                    provider = provider_class()
                
                if provider.validate_config():
                    self.providers[provider_name] = provider
                    self.logger.info(f"Initialized {provider_name} provider")
            except Exception as e:
                self.logger.warning(f"Failed to initialize {provider_name} provider: {str(e)}")
        
        if not self.providers:
            raise RuntimeError("No LLM providers could be initialized. Please check your configuration.")
        
        # Log available providers
        self.logger.info("Available LLM providers", providers=list(self.providers.keys()))
    
    def _get_env_var_name(self, provider_name: str) -> str:
        """Get environment variable name for a provider."""
        env_var_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "groq": "GROQ_API_KEY",
            "huggingface": "HF_TOKEN",
            "ollama": None
        }
        return env_var_map.get(provider_name)

    def get_available_providers(self) -> List[str]:
        """Get list of available providers"""
        return list(self.providers.keys())

    def get_available_models(self) -> Dict[str, List[str]]:
        """Get available models by provider"""
        models = {
            "openai": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini"],
            "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
            "gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
            "groq": [
                "llama-3.3-70b-versatile",
                "llama-3.3-70b-specdec",
                "llama-3.1-70b-versatile",
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768",
                "gemma2-9b-it",
                "openai/gpt-oss-20b"
            ],
            "huggingface": [
                "moonshotai/Kimi-K2-Thinking:novita",
                "meta-llama/Llama-3.3-70B-Instruct",
                "Qwen/Qwen2.5-72B-Instruct",
                "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "google/gemma-2-9b-it",
                "microsoft/Phi-3-medium-4k-instruct"
            ],
            "ollama": [
                "unibase-erp",  # Custom ERP model
            ]
        }
        
        # Filter by available providers
        return {provider: model_list for provider, model_list in models.items() 
                if provider in self.providers}

    def get_provider_for_model(self, model: str) -> Optional[str]:
        """Get the provider for a given model"""
        model_mapping = {
            # OpenAI models
            "gpt-4": "openai",
            "gpt-4-turbo": "openai",
            "gpt-3.5-turbo": "openai",
            "gpt-4o": "openai",
            "gpt-4o-mini": "openai",
            
            # Anthropic models
            "claude-3-5-sonnet-20241022": "anthropic",
            "claude-3-5-haiku-20241022": "anthropic",
            "claude-3-opus-20240229": "anthropic",
            
            # Groq models
            "llama-3.3-70b-versatile": "groq",
            "llama-3.3-70b-specdec": "groq",
            "llama-3.1-70b-versatile": "groq",
            "llama-3.1-8b-instant": "groq",
            "mixtral-8x7b-32768": "groq",
            "gemma2-9b-it": "groq",
            "openai/gpt-oss-20b": "groq",
            
            # HuggingFace models
            "moonshotai/Kimi-K2-Thinking:novita": "huggingface",
            "meta-llama/Llama-3.3-70B-Instruct": "huggingface",
            "Qwen/Qwen2.5-72B-Instruct": "huggingface",
            "mistralai/Mixtral-8x7B-Instruct-v0.1": "huggingface",
            "google/gemma-2-9b-it": "huggingface",
            "microsoft/Phi-3-medium-4k-instruct": "huggingface",
            
            # Ollama models (partial list)
            "unibase-erp": "ollama",  # Custom ERP model
            "llama2": "ollama",
            "llama3": "ollama",
            "llama3.1": "ollama",
            "llama3.2": "ollama",
            "codellama": "ollama",
            "mistral": "ollama",
            "mixtral": "ollama",
            "gemma": "ollama",
            "gemma2": "ollama",
            "qwen": "ollama",
            "qwen2": "ollama",
            "deepseek-coder": "ollama",
            "codestral": "ollama",
            "phi3": "ollama",
            "phi3.5": "ollama",
            
            # Gemini models
            "gemini-2.5-flash": "gemini",
            "gemini-2.5-pro": "gemini",
            "gemini-2.0-flash": "gemini",
            "gemini": "gemini",
        }
        
        return model_mapping.get(model)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using the appropriate provider
        
        Args:
            request: The LLM request containing messages and generation parameters
            
        Returns:
            LLMResponse containing the generated content and metadata
            
        Raises:
            AIModelError: If there's an error generating the response
        """
        provider_name = self.get_provider_for_model(request.model)
        
        if not provider_name:
            raise AIModelError("unknown", request.model, f"Unknown model: {request.model}")
            
        provider = self.providers.get(provider_name)
        if not provider:
            raise AIModelError(provider_name, request.model, 
                            f"Provider {provider_name} not available for model {request.model}")
        
        # Use provided system prompt or fall back to default
        if request.system_prompt is None:
            request.system_prompt = self.default_system_prompt

        self.logger.info(
            "Generating LLM response",
            provider=provider_name,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        try:
            return await provider.generate(request)
        except Exception as e:
            self.logger.error(
                "Error generating LLM response",
                error=str(e),
                provider=provider_name,
                model=request.model,
                exc_info=True,
            )
            
            # Try fallback providers for 503/overload errors
            if "503" in str(e) or "overloaded" in str(e).lower():
                return await self._try_fallback_providers(request, failed_provider=provider_name)
            
            raise AIModelError(provider_name, request.model, str(e)) from e

    async def generate_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Generate streaming response using the appropriate provider"""
        provider_name = self.get_provider_for_model(request.model)
        
        if not provider_name:
            raise AIModelError("unknown", request.model, f"Unknown model: {request.model}")
            
        provider = self.providers.get(provider_name)
        if not provider:
            raise AIModelError(provider_name, request.model, f"Provider {provider_name} not available for model {request.model}")

        async for chunk in provider.generate_stream(request):
            yield chunk

    async def _try_fallback_providers(self, request: LLMRequest, failed_provider: str) -> LLMResponse:
        """Try fallback providers when primary provider fails"""
        fallback_order = {
            "gemini": ["huggingface", "openai", "anthropic", "ollama"],
            "huggingface": ["gemini", "openai", "anthropic", "ollama"],
            "openai": ["huggingface", "anthropic", "gemini", "ollama"], 
            "anthropic": ["huggingface", "openai", "gemini", "ollama"],
            "ollama": ["huggingface", "openai", "anthropic", "gemini"]
        }
        
        fallback_models = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-haiku-20240307",
            "gemini": "gemini-pro",
            "huggingface": "meta-llama/Llama-3.3-70B-Instruct",
            "ollama": "llama3.2:3b"
        }
        
        fallbacks = fallback_order.get(failed_provider, ["openai", "anthropic", "ollama"])
        
        for fallback_provider in fallbacks:
            if fallback_provider in self.providers:
                try:
                    fallback_model = fallback_models.get(fallback_provider, request.model)
                    fallback_request = LLMRequest(
                        model=fallback_model,
                        messages=request.messages,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        system_prompt=request.system_prompt
                    )
                    
                    self.logger.info(f"Trying fallback provider {fallback_provider} with model {fallback_model}")
                    return await self.providers[fallback_provider].generate(fallback_request)
                    
                except Exception as fallback_error:
                    self.logger.warning(f"Fallback provider {fallback_provider} also failed: {str(fallback_error)}")
                    continue
        
        # If all fallbacks fail, return a graceful fallback response
        self.logger.error(f"All LLM providers failed for request, returning fallback response")
        return LLMResponse(
            content="I apologize, but I'm experiencing technical difficulties with all AI providers at the moment. Please try again in a few minutes. If the issue persists, please contact support.",
            model="fallback",
            tokens_used=0,
            metadata={
                "fallback_response": True,
                "failed_providers": [failed_provider] + fallbacks,
                "error_type": "all_providers_failed"
            }
        )

    async def health_check(self) -> Dict[str, bool]:
        """Health check for all providers"""
        health = {}
        
        for provider_name, provider in self.providers.items():
            try:
                health[provider_name] = provider.validate_config()
            except Exception as e:
                self.logger.warning(f"Provider {provider_name} health check failed", error=str(e))
                health[provider_name] = False
                
        return health


# Global LLM service instance
_llm_service: Optional[LLMService] = None

def get_llm_service() -> Optional[LLMService]:
    """Get the global LLM service instance."""
    return _llm_service

def initialize_llm_service(provider: Optional[str] = None) -> LLMService:
    """Initialize the global LLM service instance."""
    global _llm_service
    _llm_service = LLMService(provider=provider)
    return _llm_service