"""
LLM Service

Provides unified interface for interacting with various LLM providers:
- Local Ollama models
- OpenAI API (GPT-4, GPT-3.5-turbo, etc.)
- Anthropic API (Claude models)
- Future extensibility for other providers
"""

import os
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from abc import ABC, abstractmethod
import structlog
from pydantic import BaseModel
import httpx
import json

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
    system_prompt: Optional[str] = None


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

class GeminiProvider:
    """Gemini LLM Provider."""

    def __init__(self, api_key: str):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.default_model = "gemini-1.5-flash"  # Default to a known working model

    def _get_model_url(self, model: str) -> str:
        """Get the API URL for the specified model."""
        model_map = {
            "gemini": "gemini-1.5-flash",
            "gemini2.0:flash": "gemini-1.5-flash",
            "gemini2.5:pro": "gemini-1.5-pro"
        }
        model_name = model_map.get(model, model)
        return f"{self.base_url}/{model_name}:generateContent"

    async def generate_content(self, prompt: str, model: str = None) -> str:
        """Generate content using Gemini API."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required")
            
        model = model or self.default_model
        url = self._get_model_url(model)
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.95,
                "topK": 40,
                "maxOutputTokens": 2048,
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except httpx.HTTPStatusError as e:
            error_msg = f"API request failed with status {e.response.status_code}: {e.response.text}"
            raise AIModelError("gemini", model, error_msg) from e
        except Exception as e:
            raise AIModelError("gemini", model, str(e)) from e


class LLMService:
    """
    Unified LLM service supporting multiple providers
    
    Supports:
    - OpenAI (GPT-4, GPT-3.5-turbo, etc.)
    - Anthropic (Claude models)
    - Local Ollama models
    - Future extensibility for other providers
    """

    def __init__(self):
        self.logger = structlog.get_logger("llm_service")
        self.providers: Dict[str, BaseLLMProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize all available LLM providers"""
        # OpenAI
        openai_provider = OpenAIProvider()
        if openai_provider.validate_config():
            self.providers["openai"] = openai_provider
            self.logger.info("OpenAI provider initialized")

        # Anthropic
        anthropic_provider = AnthropicProvider()
        if anthropic_provider.validate_config():
            self.providers["anthropic"] = anthropic_provider
            self.logger.info("Anthropic provider initialized")

        # Ollama
        ollama_provider = OllamaProvider()
        if ollama_provider.validate_config():
            self.providers["ollama"] = ollama_provider
            self.logger.info("Ollama provider initialized")

        # Gemini
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            self.providers["gemini"] = GeminiProvider(gemini_api_key)
            self.logger.info("Gemini provider initialized")

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
        """Generate response using the appropriate provider"""
        provider_name = self.get_provider_for_model(request.model)
        
        if not provider_name:
            raise AIModelError("unknown", request.model, f"Unknown model: {request.model}")
            
        provider = self.providers.get(provider_name)
        if not provider:
            raise AIModelError(provider_name, request.model, f"Provider {provider_name} not available for model {request.model}")

        self.logger.info(
            "Generating LLM response",
            provider=provider_name,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        try:
            if provider_name == "openai":
                return await self._generate_openai(provider, request)
            elif provider_name == "anthropic":
                return await self._generate_anthropic(provider, request)
            elif provider_name == "ollama":
                return await self._generate_ollama(provider, request)
            elif provider_name == "gemini":
                # Combine all user messages into a single prompt
                prompt = "\n".join(
                    f"{m.role.upper()}: {m.content}" 
                    for m in request.messages
                )
                response = await provider.generate_content(
                    prompt=prompt,
                    model=request.model
                )
                return LLMResponse(
                    content=response,
                    model=request.model,
                    tokens_used=len(response.split()),
                    finish_reason="stop",
                    metadata={"provider": "gemini"}
                )
            else:
                raise AIModelError(provider_name, request.model, f"Unsupported provider: {provider_name}")
        except Exception as e:
            self.logger.error(
                "Error generating LLM response",
                error=str(e),
                provider=provider_name,
                model=request.model,
                exc_info=True,
            )
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
llm_service = LLMService()