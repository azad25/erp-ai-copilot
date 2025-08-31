"""
RAG LLM Service - wrapper around the main LLM service for RAG operations.
"""
from typing import Dict, Any, List, Optional
from app.services.llm_service import LLMService as BaseLLMService

class LLMService:
    """Wrapper around the main LLM service for RAG operations."""
    
    def __init__(self, base_llm_service: BaseLLMService):
        """Initialize with the base LLM service."""
        self.base_service = base_llm_service
    
    async def generate_response(self, prompt: str, context: str = "", **kwargs) -> str:
        """Generate a response using the LLM with optional context."""
        if context:
            full_prompt = f"Context: {context}\n\nQuestion: {prompt}"
        else:
            full_prompt = prompt
            
        response = await self.base_service.generate_response(
            prompt=full_prompt,
            **kwargs
        )
        return response
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embeddings for text (if supported by the base service)."""
        # For now, return a placeholder - this would need to be implemented
        # based on the actual embedding capabilities of the base service
        return []
