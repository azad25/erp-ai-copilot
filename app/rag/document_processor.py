"""Document Processor for RAG Engine

This module provides document processing functionality for the RAG engine,
including text extraction, chunking, and metadata handling.
"""

from typing import Dict, List, Optional, Any, Union, Tuple
import re
import uuid
from datetime import datetime

import structlog
from pydantic import BaseModel

from app.config.settings import get_settings
from app.rag.models import Document, DocumentChunk

logger = structlog.get_logger(__name__)
settings = get_settings()


class DocumentProcessor:
    """Document processor for RAG engine."""
    
    def __init__(self):
        """Initialize the document processor."""
        self.chunk_size = settings.rag.chunk_size
        self.chunk_overlap = settings.rag.chunk_overlap
    
    def process_document(self, document: Document) -> Tuple[Document, List[DocumentChunk]]:
        """Process a document for RAG.
        
        Args:
            document: Document to process
            
        Returns:
            Processed document and list of chunks
        """
        try:
            # Generate document ID if not provided
            if not document.id:
                document.id = str(uuid.uuid4())
            
            # Set timestamps if not provided
            if not document.created_at:
                document.created_at = datetime.utcnow()
            if not document.updated_at:
                document.updated_at = datetime.utcnow()
            
            # Extract and enhance metadata
            document = self._extract_metadata(document)
            
            # Split document into chunks
            chunks = self._chunk_document(document)
            
            logger.info(
                "Document processed",
                document_id=document.id,
                title=document.title,
                chunks=len(chunks)
            )
            
            return document, chunks
            
        except Exception as e:
            logger.error(
                "Document processing failed",
                document_id=document.id if document.id else "unknown",
                error=str(e)
            )
            raise
    
    def _extract_metadata(self, document: Document) -> Document:
        """Extract and enhance document metadata.
        
        Args:
            document: Document to process
            
        Returns:
            Document with enhanced metadata
        """
        # Initialize metadata if not present
        if not document.metadata:
            document.metadata = {}
        
        # Add basic metadata if not present
        if "title" not in document.metadata:
            document.metadata["title"] = document.title
        
        if "document_type" not in document.metadata:
            document.metadata["document_type"] = document.document_type
        
        if "access_level" not in document.metadata:
            document.metadata["access_level"] = document.access_level
        
        if "created_at" not in document.metadata:
            document.metadata["created_at"] = document.created_at.isoformat()
        
        if "updated_at" not in document.metadata:
            document.metadata["updated_at"] = document.updated_at.isoformat()
        
        if "version" not in document.metadata:
            document.metadata["version"] = document.version
        
        # Extract additional metadata based on content
        # This is a simple example - in a real system, this would be more sophisticated
        # and might use NLP techniques to extract entities, keywords, etc.
        
        # Extract potential keywords (simple approach)
        if "keywords" not in document.metadata:
            # Simple keyword extraction based on frequency
            words = re.findall(r'\b[a-zA-Z]{4,}\b', document.content.lower())
            word_freq = {}
            for word in words:
                if word not in word_freq:
                    word_freq[word] = 0
                word_freq[word] += 1
            
            # Get top keywords (excluding common words)
            common_words = {'about', 'above', 'after', 'again', 'against', 'their', 'them', 'then', 'there'}
            keywords = [
                word for word, count in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
                if word not in common_words
            ][:10]  # Top 10 keywords
            
            document.metadata["keywords"] = keywords
        
        # Estimate reading time
        if "reading_time_minutes" not in document.metadata:
            # Average reading speed: ~200 words per minute
            word_count = len(document.content.split())
            reading_time = max(1, round(word_count / 200))
            document.metadata["reading_time_minutes"] = reading_time
            document.metadata["word_count"] = word_count
        
        return document
    
    def _chunk_document(self, document: Document) -> List[DocumentChunk]:
        """Split document into chunks for processing.
        
        Args:
            document: Document to chunk
            
        Returns:
            List of document chunks
        """
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
                # Create chunk-specific metadata
                chunk_metadata = document.metadata.copy()
                chunk_metadata["chunk_index"] = chunk_index
                
                # Add position information
                if chunk_index == 0:
                    chunk_metadata["position"] = "start"
                elif end >= len(content):
                    chunk_metadata["position"] = "end"
                else:
                    chunk_metadata["position"] = "middle"
                
                chunks.append(DocumentChunk(
                    document_id=document.id,
                    content=chunk_content,
                    metadata=chunk_metadata,
                    document_type=document.document_type,
                    chunk_index=chunk_index
                ))
                chunk_index += 1
            
            # Move to next chunk with overlap
            start = end - chunk_overlap
            if start < end - chunk_overlap:
                start = end  # Avoid getting stuck in a loop
        
        return chunks
    
    def merge_chunks(self, chunks: List[DocumentChunk], max_tokens: int = 1500) -> str:
        """Merge chunks into a coherent text, respecting token limits.
        
        Args:
            chunks: List of document chunks
            max_tokens: Maximum number of tokens to include
            
        Returns:
            Merged text
        """
        # Sort chunks by index
        sorted_chunks = sorted(chunks, key=lambda x: x.chunk_index)
        
        # Merge chunks
        merged_text = ""
        estimated_tokens = 0
        
        for chunk in sorted_chunks:
            # Estimate tokens (rough approximation: 4 chars ≈ 1 token)
            chunk_tokens = len(chunk.content) // 4
            
            if estimated_tokens + chunk_tokens > max_tokens:
                # Would exceed token limit, stop adding chunks
                break
            
            # Add chunk with separator if not first chunk
            if merged_text:
                merged_text += "\n\n"
            
            merged_text += chunk.content
            estimated_tokens += chunk_tokens
        
        return merged_text