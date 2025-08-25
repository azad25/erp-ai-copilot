"""RAG Service Module

This module provides the main RAG service that integrates all components
and provides the core functionality for document ingestion, search, and retrieval.
"""

from typing import Dict, List, Optional, Any, Union, Tuple
import asyncio
from datetime import datetime

import structlog
from pydantic import BaseModel

from app.config.settings import get_settings
from app.database.connection import DatabaseManager
from app.rag.models import Document, DocumentChunk, SearchQuery, SearchResult, SearchFilter
from app.rag.engine import RAGEngine
from app.rag.document_processor import DocumentProcessor
from app.rag.vector_store import VectorStore
from app.rag.embeddings import get_embedding_provider
from app.rag.cache import SearchCache, CacheManager
from app.rag.kafka_integration import KafkaManager

logger = structlog.get_logger(__name__)
settings = get_settings()


class RAGService:
    """Main service for RAG functionality."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize the RAG service.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self.mongo = db_manager.get_mongo_client()
        self.postgres = db_manager.get_postgres_client()
        
        # Initialize components
        self.document_processor = DocumentProcessor()
        self.vector_store = VectorStore(db_manager)
        self.embedding_provider = get_embedding_provider(settings.rag.embedding_model)
        self.engine = RAGEngine(db_manager, self.vector_store, self.embedding_provider)
        
        # Initialize cache
        self.document_cache = CacheManager(db_manager, Document, prefix="rag:doc")
        self.search_cache = SearchCache(db_manager)
        
        # Initialize Kafka manager
        self.kafka_manager = KafkaManager()
        
        # MongoDB collections
        self.documents_collection = self.mongo["rag"]["documents"]
        
        # Initialization flag
        self.initialized = False
    
    async def initialize(self):
        """Initialize the RAG service."""
        if self.initialized:
            return True
        
        try:
            # Initialize RAG engine
            await self.engine.initialize()
            
            # Initialize Kafka manager
            if settings.kafka.enabled:
                kafka_initialized = await self.kafka_manager.initialize()
                
                if kafka_initialized:
                    # Register Kafka handlers
                    await self.register_kafka_handlers()
            
            self.initialized = True
            logger.info("RAG service initialized")
            return True
            
        except Exception as e:
            logger.error("Failed to initialize RAG service", error=str(e))
            return False
    
    async def register_kafka_handlers(self):
        """Register Kafka message handlers."""
        # Register document ingestion handler
        await self.kafka_manager.register_consumer(
            self.kafka_manager.DOCUMENT_INGESTION_TOPIC,
            self._handle_document_ingestion_message
        )
        
        # Register document search handler
        await self.kafka_manager.register_consumer(
            self.kafka_manager.DOCUMENT_SEARCH_TOPIC,
            self._handle_document_search_message
        )
        
        # Register document update handler
        await self.kafka_manager.register_consumer(
            self.kafka_manager.DOCUMENT_UPDATE_TOPIC,
            self._handle_document_update_message
        )
        
        # Register document delete handler
        await self.kafka_manager.register_consumer(
            self.kafka_manager.DOCUMENT_DELETE_TOPIC,
            self._handle_document_delete_message
        )
    
    async def ingest_document(self, document: Document) -> Tuple[bool, Optional[str], Optional[List[str]]]:
        """Ingest a document into the RAG system.
        
        Args:
            document: Document to ingest
            
        Returns:
            Tuple of (success, document_id, vector_ids)
        """
        try:
            # Process document
            processed_document, chunks = self.document_processor.process_document(document)
            
            # Store document in MongoDB
            document_dict = processed_document.dict()
            await self.documents_collection.update_one(
                {"id": processed_document.id},
                {"$set": document_dict},
                upsert=True
            )
            
            # Store document chunks in vector database
            vector_ids = await self.engine.process_document(processed_document, chunks)
            
            # Cache document
            await self.document_cache.set(processed_document.id, processed_document)
            
            # Send Kafka message if enabled
            if settings.kafka.enabled:
                await self.kafka_manager.send_document_ingestion_message(processed_document)
            
            logger.info(
                "Document ingested",
                document_id=processed_document.id,
                title=processed_document.title,
                chunks=len(chunks),
                vectors=len(vector_ids) if vector_ids else 0
            )
            
            return True, processed_document.id, vector_ids
            
        except Exception as e:
            logger.error(
                "Document ingestion failed",
                document_id=document.id if document.id else "unknown",
                error=str(e)
            )
            return False, None, None
    
    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """Search for documents matching the query.
        
        Args:
            query: Search query
            
        Returns:
            List of search results
        """
        try:
            # Check cache first
            cached_results = await self.search_cache.get_search_results(
                query.query,
                query.filters.dict() if query.filters else None
            )
            
            if cached_results:
                logger.info(
                    "Search results retrieved from cache",
                    query=query.query_text,
                    results_count=len(cached_results)
                )
                return [SearchResult(**result) for result in cached_results]
            
            # Perform search
            results = await self.engine.search(
                query.query,
                filters=query.filters,
                limit=query.max_results or settings.rag.max_results,
                similarity_threshold=query.similarity_threshold or settings.rag.similarity_threshold
            )
            
            # Cache results
            await self.search_cache.set_search_results(
                query.query_text,
                [result.dict() for result in results],
                query.filters.dict() if query.filters else None
            )
            
            # Send Kafka message if enabled
            if settings.kafka.enabled:
                await self.kafka_manager.send_document_search_message(query)
            
            logger.info(
                "Search completed",
                query=query.query,
                results_count=len(results)
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "Search failed",
                query=query.query,
                error=str(e)
            )
            return []
    
    async def get_document(self, document_id: str) -> Optional[Document]:
        """Get a document by ID.
        
        Args:
            document_id: Document ID
            
        Returns:
            Document or None if not found
        """
        try:
            # Check cache first
            cached_document = await self.document_cache.get(document_id)
            
            if cached_document:
                return cached_document
            
            # Get from MongoDB
            document_dict = await self.documents_collection.find_one({"id": document_id})
            
            if not document_dict:
                return None
            
            # Convert to Document model
            document = Document(**document_dict)
            
            # Cache document
            await self.document_cache.set(document_id, document)
            
            return document
            
        except Exception as e:
            logger.error(
                "Error getting document",
                document_id=document_id,
                error=str(e)
            )
            return None
    
    async def update_document(self, document: Document) -> bool:
        """Update a document.
        
        Args:
            document: Document to update
            
        Returns:
            Success status
        """
        try:
            # Update timestamp
            document.updated_at = datetime.utcnow()
            
            # Process document
            processed_document, chunks = self.document_processor.process_document(document)
            
            # Update document in MongoDB
            document_dict = processed_document.dict()
            result = await self.documents_collection.update_one(
                {"id": processed_document.id},
                {"$set": document_dict}
            )
            
            if result.matched_count == 0:
                logger.warning(
                    "Document not found for update",
                    document_id=processed_document.id
                )
                return False
            
            # Delete existing vectors
            await self.engine.delete_document(processed_document.id)
            
            # Store document chunks in vector database
            vector_ids = await self.engine.process_document(processed_document, chunks)
            
            # Update cache
            await self.document_cache.set(processed_document.id, processed_document)
            await self.search_cache.invalidate_document_cache(processed_document.id)
            
            # Send Kafka message if enabled
            if settings.kafka.enabled:
                await self.kafka_manager.send_document_update_message(processed_document)
            
            logger.info(
                "Document updated",
                document_id=processed_document.id,
                title=processed_document.title,
                chunks=len(chunks),
                vectors=len(vector_ids) if vector_ids else 0
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Document update failed",
                document_id=document.id,
                error=str(e)
            )
            return False
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            Success status
        """
        try:
            # Delete from MongoDB
            result = await self.documents_collection.delete_one({"id": document_id})
            
            if result.deleted_count == 0:
                logger.warning(
                    "Document not found for deletion",
                    document_id=document_id
                )
                return False
            
            # Delete from vector database
            await self.engine.delete_document(document_id)
            
            # Delete from cache
            await self.document_cache.delete(document_id)
            await self.search_cache.invalidate_document_cache(document_id)
            
            # Send Kafka message if enabled
            if settings.kafka.enabled:
                await self.kafka_manager.send_document_delete_message(document_id)
            
            logger.info(
                "Document deleted",
                document_id=document_id
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Document deletion failed",
                document_id=document_id,
                error=str(e)
            )
            return False
    
    async def _handle_document_ingestion_message(self, message: Dict[str, Any]):
        """Handle document ingestion message from Kafka.
        
        Args:
            message: Kafka message
        """
        try:
            payload = message.get("payload", {})
            document = Document(**payload)
            
            # Process document
            await self.ingest_document(document)
            
        except Exception as e:
            logger.error(
                "Error handling document ingestion message",
                message_id=message.get("message_id"),
                error=str(e)
            )
    
    async def _handle_document_search_message(self, message: Dict[str, Any]):
        """Handle document search message from Kafka.
        
        Args:
            message: Kafka message
        """
        try:
            payload = message.get("payload", {})
            query = SearchQuery(**payload)
            
            # Perform search
            await self.search(query)
            
        except Exception as e:
            logger.error(
                "Error handling document search message",
                message_id=message.get("message_id"),
                error=str(e)
            )
    
    async def _handle_document_update_message(self, message: Dict[str, Any]):
        """Handle document update message from Kafka.
        
        Args:
            message: Kafka message
        """
        try:
            payload = message.get("payload", {})
            document = Document(**payload)
            
            # Update document
            await self.update_document(document)
            
        except Exception as e:
            logger.error(
                "Error handling document update message",
                message_id=message.get("message_id"),
                error=str(e)
            )
    
    async def _handle_document_delete_message(self, message: Dict[str, Any]):
        """Handle document delete message from Kafka.
        
        Args:
            message: Kafka message
        """
        try:
            payload = message.get("payload", {})
            document_id = payload.get("document_id")
            
            if document_id:
                # Delete document
                await self.delete_document(document_id)
            
        except Exception as e:
            logger.error(
                "Error handling document delete message",
                message_id=message.get("message_id"),
                error=str(e)
            )