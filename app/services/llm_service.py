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

class GeminiProvider(BaseLLMProvider):
    """Gemini LLM Provider."""

    def __init__(self, api_key: str = None, base_url: str = None):
        """Initialize Gemini provider.
        
        Args:
            api_key: Gemini API key
            base_url: Base URL for Gemini API
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.base_url = base_url or "https://generativelanguage.googleapis.com/v1beta/models"
        self.default_model = "gemini-2.0-flash"  # Default to a known working model
        self.logger = structlog.get_logger("gemini_provider")
        
        if not self.api_key:
            self.logger.warning("GEMINI_API_KEY not found in environment variables")

    def validate_config(self) -> bool:
        """Validate that the provider is properly configured."""
        if not self.api_key:
            self.logger.warning("Gemini API key not configured")
            return False
        return True

    def get_available_models(self) -> List[str]:
        """Get list of available models for this provider."""
        return ["gemini-2.0-flash", "gemini-2.5-pro"]

    def _get_model_url(self, model: str) -> str:
        """Get the API URL for the specified model."""
        model_map = {
            "gemini": "gemini-2.0-flash",
            "gemini2.0:flash": "gemini-2.0-flash",
            "gemini2.5:pro": "gemini-2.5-pro"
        }
        model_name = model_map.get(model, model)
        return f"{self.base_url}/{model_name}:generateContent"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM.
        
        Args:
            request: The LLM request containing messages and generation parameters
            
        Returns:
            LLMResponse containing the generated content and metadata
            
        Raises:
            AIModelError: If there's an error generating the response
        """
        if not self.validate_config():
            raise AIModelError("gemini", request.model, "Gemini provider is not properly configured")
            
        model = request.model or self.default_model
        url = self._get_model_url(model)
        
        # Format messages for Gemini API
        prompt = ""
        system_instruction = None
        
        if request.system_prompt:
            system_instruction = request.system_prompt
            
        for msg in request.messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                prompt += f"\n\n{msg.content}"
            elif msg.role == "assistant":
                prompt += f"\n\nAssistant: {msg.content}"
            else:
                prompt += f"\n\n{msg.role}: {msg.content}"
        
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key
        }
        
        # Prepare the request payload
        payload = {
            "contents": [{"parts": [{"text": prompt.strip()}]}],
            "generationConfig": {
                "temperature": request.temperature,
                "topP": 0.95,
                "topK": 40,
                "maxOutputTokens": request.max_tokens,
            }
        }
        
        # Add system instruction if provided
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                if "candidates" not in data or not data["candidates"]:
                    raise AIModelError("gemini", model, "No candidates in response")
                
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                
                return LLMResponse(
                    content=content,
                    model=model,
                    tokens_used=len(content.split()),  # Approximate token count
                    finish_reason="stop",
                    metadata={"provider": "gemini"}
                )
                
        except httpx.HTTPStatusError as e:
            error_msg = f"API request failed with status {e.response.status_code}: {e.response.text}"
            raise AIModelError("gemini", model, error_msg) from e
        except Exception as e:
            raise AIModelError("gemini", model, str(e)) from e
    
    async def generate_stream(self, request: LLMRequest):
        """Generate a streaming response from the LLM.
        
        Args:
            request: The LLM request containing messages and generation parameters
            
        Yields:
            Chunks of the generated response as they become available
            
        Raises:
            AIModelError: If there's an error generating the response
        """
        if not self.validate_config():
            raise AIModelError("gemini", request.model, "Gemini provider is not properly configured")
            
        # Gemini's REST API doesn't support streaming, so we'll simulate it
        try:
            response = await self.generate(request)
            # Simulate streaming by yielding chunks of the response
            chunk_size = 10  # words per chunk
            words = response.content.split()
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i+chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "  # Add space if not the last chunk
                yield chunk
                await asyncio.sleep(0.05)  # Small delay between chunks
        except Exception as e:
            raise AIModelError("gemini", request.model, f"Streaming error: {str(e)}") from e


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

    def _initialize_providers(self):
        """Initialize all available LLM providers"""
        # Initialize providers in order of preference
        providers_to_init = [
            ("ollama", OllamaProvider),
            ("gemini", GeminiProvider),
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
                if provider_name == "gemini":
                    gemini_api_key = os.getenv("GEMINI_API_KEY")
                    if not gemini_api_key:
                        self.logger.warning("GEMINI_API_KEY not found in environment")
                        continue
                    provider = provider_class(api_key=gemini_api_key)
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

    def get_available_providers(self) -> List[str]:
        """Get list of available providers"""
        return list(self.providers.keys())

    def get_available_models(self) -> Dict[str, List[str]]:
        """Get available models by provider"""
        models = {
            "openai": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini"],
            "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
            "gemini": ["gemini2.0:flash", "gemini2.5:pro"],
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
            "gemini2.0:flash": "gemini",
            "gemini2.5:pro": "gemini",
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
            "gemini": ["openai", "anthropic", "ollama"],
            "openai": ["anthropic", "gemini", "ollama"], 
            "anthropic": ["openai", "gemini", "ollama"],
            "ollama": ["openai", "anthropic", "gemini"]
        }
        
        fallback_models = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-haiku-20240307",
            "gemini": "gemini-pro",
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