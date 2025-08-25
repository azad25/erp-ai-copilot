"""Embedding Provider for RAG Engine

This module provides embedding generation functionality for the RAG engine,
converting text into vector representations for semantic search.
"""

from typing import Dict, List, Optional, Any, Union
import asyncio
from functools import lru_cache

import structlog
import numpy as np
from sentence_transformers import SentenceTransformer

from app.config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class EmbeddingProvider:
    """Embedding provider for generating vector embeddings."""
    
    def __init__(self, model_name: Optional[str] = None):
        """Initialize the embedding provider.
        
        Args:
            model_name: Optional model name override
        """
        self.model_name = model_name or settings.rag.embedding_model
        self._model = None
        self._vector_size = None
        self._distance_metric = "cosine"
        
        # Initialize model
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the embedding model."""
        try:
            # Load the model
            self._model = SentenceTransformer(self.model_name)
            
            # Get vector size from model
            self._vector_size = self._model.get_sentence_embedding_dimension()
            
            logger.info(
                "Embedding model initialized",
                model=self.model_name,
                vector_size=self._vector_size
            )
            
        except Exception as e:
            logger.error(
                "Failed to initialize embedding model",
                model=self.model_name,
                error=str(e)
            )
            raise
    
    @property
    def vector_size(self) -> int:
        """Get the vector size of the embedding model."""
        return self._vector_size
    
    @property
    def distance_metric(self) -> str:
        """Get the distance metric used by the embedding model."""
        return self._distance_metric
    
    async def get_embedding(self, text: str) -> List[float]:
        """Generate an embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Vector embedding
        """
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, self._generate_embedding, text
            )
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(
                "Failed to generate embedding",
                error=str(e)
            )
            raise
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of vector embeddings
        """
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None, self._generate_embeddings, texts
            )
            
            return [embedding.tolist() for embedding in embeddings]
            
        except Exception as e:
            logger.error(
                "Failed to generate embeddings",
                error=str(e)
            )
            raise
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding synchronously.
        
        Args:
            text: Text to embed
            
        Returns:
            Vector embedding
        """
        # Ensure model is initialized
        if self._model is None:
            self._initialize_model()
        
        # Generate embedding
        return self._model.encode(text, normalize_embeddings=True)
    
    def _generate_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings synchronously.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of vector embeddings
        """
        # Ensure model is initialized
        if self._model is None:
            self._initialize_model()
        
        # Generate embeddings
        return self._model.encode(texts, normalize_embeddings=True)
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Similarity score (0-1)
        """
        # Convert to numpy arrays
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Calculate cosine similarity
        similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        
        return float(similarity)


# Factory function to get embedding provider with caching
@lru_cache(maxsize=2)  # Cache up to 2 different model instances
def get_embedding_provider(model_name: Optional[str] = None) -> EmbeddingProvider:
    """Get an embedding provider instance with caching.
    
    Args:
        model_name: Optional model name override
        
    Returns:
        EmbeddingProvider instance
    """
    return EmbeddingProvider(model_name=model_name)