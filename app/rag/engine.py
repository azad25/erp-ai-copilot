"""RAG Engine Core Implementation

This module provides the core RAG engine functionality, including document processing,
embedding, storage, and retrieval operations.
"""

from typing import Dict, List, Optional, Any, Tuple
import asyncio
import time
from datetime import datetime
import uuid

import structlog
from pydantic import BaseModel, Field

from app.config.settings import get_settings
from app.database.connection import DatabaseManager
from app.rag.models import (
    Document, 
    DocumentChunk, 
    SearchQuery, 
    SearchResult,
    SearchFilter
)
from app.rag.embeddings import EmbeddingProvider
from app.rag.vector_store import VectorStore

logger = structlog.get_logger(__name__)
settings = get_settings()


class RAGEngine:
    """RAG Engine for document processing and retrieval."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize the RAG engine.
        
        Args:
            db_manager: Database connection manager
        """
        self.db_manager = db_manager
        self.vector_store = VectorStore(db_manager)
        self.embedding_provider = EmbeddingProvider()
        self.collection_prefix = settings.rag.collection_prefix
        self.similarity_threshold = settings.rag.similarity_threshold
        self.max_results = settings.rag.max_results
        self.chunk_size = settings.rag.chunk_size
        self.chunk_overlap = settings.rag.chunk_overlap
    
    async def initialize(self):
        """Initialize the RAG engine and ensure collections exist."""
        try:
            # Initialize vector store
            await self.vector_store.initialize()
            
            # Create default collections if they don't exist
            default_collections = [
                f"{self.collection_prefix}_documents",
                f"{self.collection_prefix}_policies",
                f"{self.collection_prefix}_manuals",
                f"{self.collection_prefix}_faqs"
            ]
            
            for collection_name in default_collections:
                await self.vector_store.create_collection_if_not_exists(
                    collection_name=collection_name,
                    vector_size=self.embedding_provider.vector_size,
                    distance=self.embedding_provider.distance_metric
                )
            
            logger.info("RAG engine initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize RAG engine", error=str(e))
            raise
    
    async def process_document(
        self, 
        document: Document,
        collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a document for RAG.
        
        Args:
            document: Document to process
            collection_name: Optional collection name override
            
        Returns:
            Processing results including document ID and chunk IDs
        """
        start_time = time.time()
        
        try:
            # Determine collection name
            if not collection_name:
                collection_name = f"{self.collection_prefix}_documents"
                if document.document_type:
                    collection_name = f"{self.collection_prefix}_{document.document_type}s"
            
            # Generate document ID if not provided
            if not document.id:
                document.id = str(uuid.uuid4())
            
            # Split document into chunks
            chunks = self._chunk_document(document)
            
            # Generate embeddings for chunks
            chunk_embeddings = await self.embedding_provider.get_embeddings(
                [chunk.content for chunk in chunks]
            )
            
            # Store chunks in vector database
            chunk_ids = []
            for i, chunk in enumerate(chunks):
                chunk_id = await self.vector_store.add_vector(
                    collection_name=collection_name,
                    vector=chunk_embeddings[i],
                    payload=chunk.dict(),
                    id=str(uuid.uuid4())
                )
                chunk_ids.append(chunk_id)
            
            processing_time = time.time() - start_time
            
            result = {
                "document_id": document.id,
                "chunks_created": len(chunks),
                "embedding_model": self.embedding_provider.model_name,
                "vector_ids": chunk_ids,
                "processing_time_ms": round(processing_time * 1000, 2),
                "collection_name": collection_name
            }
            
            logger.info(
                "Document processed successfully",
                document_id=document.id,
                chunks=len(chunks),
                collection=collection_name,
                time_ms=round(processing_time * 1000, 2)
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Failed to process document",
                document_id=document.id if document.id else "unknown",
                error=str(e)
            )
            raise
    
    async def search(
        self,
        query: SearchQuery
    ) -> SearchResult:
        """Search for relevant documents.
        
        Args:
            query: Search query parameters
            
        Returns:
            Search results
        """
        start_time = time.time()
        
        try:
            # Determine collection name
            collection_name = query.collection_name
            if not collection_name:
                collection_name = f"{self.collection_prefix}_documents"
            
            # Generate query embedding
            query_embedding = await self.embedding_provider.get_embedding(query.query)
            
            # Set search parameters
            limit = query.max_results or self.max_results
            threshold = query.similarity_threshold or self.similarity_threshold
            
            # Perform vector search
            search_results = await self.vector_store.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=limit,
                threshold=threshold,
                filters=query.filters
            )
            
            # Process results
            results = []
            for result in search_results:
                results.append({
                    "chunk_id": result["id"],
                    "document_id": result["payload"].get("document_id"),
                    "content": result["payload"].get("content"),
                    "metadata": result["payload"].get("metadata", {}),
                    "similarity": result["score"]
                })
            
            search_time = time.time() - start_time
            
            return SearchResult(
                query=query.query,
                results=results,
                total_results=len(results),
                search_time_ms=round(search_time * 1000, 2),
                metadata={
                    "collection": collection_name,
                    "embedding_model": self.embedding_provider.model_name,
                    "threshold": threshold
                }
            )
            
        except Exception as e:
            logger.error(
                "Search failed",
                query=query.query,
                collection=query.collection_name,
                error=str(e)
            )
            raise
    
    def _chunk_document(self, document: Document) -> List[DocumentChunk]:
        """Split document into chunks for processing.
        
        Args:
            document: Document to chunk
            
        Returns:
            List of document chunks
        """
        # Simple chunking by character count
        # In a production system, this would use more sophisticated chunking
        # based on semantic boundaries, paragraphs, etc.
        
        content = document.content
        chunk_size = document.chunk_size or self.chunk_size
        chunk_overlap = document.chunk_overlap or self.chunk_overlap
        
        if len(content) <= chunk_size:
            # Document is smaller than chunk size, return as single chunk
            return [DocumentChunk(
                document_id=document.id,
                content=content,
                metadata=document.metadata,
                document_type=document.document_type,
                chunk_index=0
            )]
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(content):
            end = min(start + chunk_size, len(content))
            
            # Try to find a good boundary (period, newline, etc.)
            if end < len(content):
                # Look for a period or newline within the last 20% of the chunk
                boundary_search_start = max(start + int(chunk_size * 0.8), start)
                
                # Find the last period or newline in the chunk
                last_period = content.rfind(".", boundary_search_start, end)
                last_newline = content.rfind("\n", boundary_search_start, end)
                
                # Use the latest boundary found
                if last_period > boundary_search_start:
                    end = last_period + 1  # Include the period
                elif last_newline > boundary_search_start:
                    end = last_newline + 1  # Include the newline
            
            # Create chunk
            chunk_content = content[start:end].strip()
            if chunk_content:  # Only add non-empty chunks
                chunks.append(DocumentChunk(
                    document_id=document.id,
                    content=chunk_content,
                    metadata=document.metadata,
                    document_type=document.document_type,
                    chunk_index=chunk_index
                ))
                chunk_index += 1
            
            # Move to next chunk with overlap
            start = end - chunk_overlap
            if start < end - chunk_overlap:
                start = end  # Avoid getting stuck in a loop
        
        return chunks