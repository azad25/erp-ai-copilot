"""Vector Store Implementation for RAG Engine

This module provides the vector database integration for the RAG engine,
handling collection management, vector storage, and similarity search operations.
"""

from typing import Dict, List, Optional, Any, Union
import asyncio
import time
from datetime import datetime

import structlog
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config.settings import get_settings
from app.database.connection import DatabaseManager

logger = structlog.get_logger(__name__)
settings = get_settings()


class VectorStore:
    """Vector store implementation using Qdrant."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize the vector store.
        
        Args:
            db_manager: Database connection manager
        """
        self.db_manager = db_manager
        self.client = None
    
    async def initialize(self):
        """Initialize the vector store connection."""
        try:
            # Get Qdrant client from database manager
            self.client = await self.db_manager.get_qdrant_client()
            
            # Test connection
            collections = await self.client.get_collections()
            logger.info(
                "Vector store initialized", 
                collections_count=len(collections.collections)
            )
            
        except Exception as e:
            logger.error("Failed to initialize vector store", error=str(e))
            raise
    
    async def create_collection_if_not_exists(
        self, 
        collection_name: str,
        vector_size: int = 384,  # Default for all-MiniLM-L6-v2
        distance: str = "cosine"
    ) -> bool:
        """Create a collection if it doesn't exist.
        
        Args:
            collection_name: Name of the collection
            vector_size: Dimensionality of vectors
            distance: Distance metric (cosine, euclid, dot)
            
        Returns:
            True if collection was created, False if it already existed
        """
        try:
            # Check if collection exists
            collections = await self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if collection_name in collection_names:
                logger.info("Collection already exists", collection=collection_name)
                return False
            
            # Create collection
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=vector_size,
                    distance=distance
                )
            )
            
            # Create payload indexes for common fields to improve filtering performance
            await self.client.create_payload_index(
                collection_name=collection_name,
                field_name="document_id",
                field_schema=qdrant_models.PayloadSchemaType.KEYWORD
            )
            
            await self.client.create_payload_index(
                collection_name=collection_name,
                field_name="document_type",
                field_schema=qdrant_models.PayloadSchemaType.KEYWORD
            )
            
            await self.client.create_payload_index(
                collection_name=collection_name,
                field_name="metadata.access_level",
                field_schema=qdrant_models.PayloadSchemaType.KEYWORD
            )
            
            logger.info("Collection created", collection=collection_name)
            return True
            
        except Exception as e:
            logger.error(
                "Failed to create collection", 
                collection=collection_name, 
                error=str(e)
            )
            raise
    
    async def add_vector(
        self,
        collection_name: str,
        vector: List[float],
        payload: Dict[str, Any],
        id: Optional[str] = None
    ) -> str:
        """Add a vector to the collection.
        
        Args:
            collection_name: Name of the collection
            vector: Vector embedding
            payload: Metadata payload
            id: Optional vector ID
            
        Returns:
            ID of the added vector
        """
        try:
            # Add vector to collection
            result = await self.client.upsert(
                collection_name=collection_name,
                points=[
                    qdrant_models.PointStruct(
                        id=id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            
            # Get the ID of the added vector
            vector_id = result.upserted_points[0] if result.upserted_points else id
            
            logger.debug(
                "Vector added", 
                collection=collection_name, 
                vector_id=vector_id
            )
            
            return vector_id
            
        except Exception as e:
            logger.error(
                "Failed to add vector", 
                collection=collection_name, 
                error=str(e)
            )
            raise
    
    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        threshold: float = 0.7,
        filters: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors.
        
        Args:
            collection_name: Name of the collection
            query_vector: Query vector embedding
            limit: Maximum number of results
            threshold: Similarity threshold (0-1)
            filters: Optional filters for search
            
        Returns:
            List of search results with scores and payloads
        """
        try:
            # Convert filters to Qdrant filter format if provided
            filter_obj = None
            if filters and len(filters) > 0:
                filter_conditions = []
                
                for filter_item in filters:
                    field = filter_item.get("field")
                    value = filter_item.get("value")
                    operator = filter_item.get("operator", "==")
                    
                    if field and value is not None:
                        if operator == "==":
                            filter_conditions.append(
                                qdrant_models.FieldCondition(
                                    key=field,
                                    match=qdrant_models.MatchValue(value=value)
                                )
                            )
                        elif operator == "!=":
                            filter_conditions.append(
                                qdrant_models.FieldCondition(
                                    key=field,
                                    match=qdrant_models.MatchValue(value=value),
                                    match_value=False
                                )
                            )
                        elif operator == "in":
                            filter_conditions.append(
                                qdrant_models.FieldCondition(
                                    key=field,
                                    match=qdrant_models.MatchAny(any=value)
                                )
                            )
                        elif operator == "not_in":
                            filter_conditions.append(
                                qdrant_models.FieldCondition(
                                    key=field,
                                    match=qdrant_models.MatchAny(any=value),
                                    match_value=False
                                )
                            )
                
                if filter_conditions:
                    filter_obj = qdrant_models.Filter(
                        must=filter_conditions
                    )
            
            # Perform search
            search_results = await self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=threshold,
                query_filter=filter_obj,
                with_payload=True
            )
            
            # Format results
            results = []
            for result in search_results:
                results.append({
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload
                })
            
            logger.info(
                "Vector search completed", 
                collection=collection_name, 
                results_count=len(results),
                threshold=threshold
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "Vector search failed", 
                collection=collection_name, 
                error=str(e)
            )
            raise
    
    async def delete_vectors(
        self,
        collection_name: str,
        ids: List[str]
    ) -> int:
        """Delete vectors from the collection.
        
        Args:
            collection_name: Name of the collection
            ids: List of vector IDs to delete
            
        Returns:
            Number of deleted vectors
        """
        try:
            # Delete vectors
            result = await self.client.delete(
                collection_name=collection_name,
                points_selector=qdrant_models.PointIdsList(
                    points=ids
                )
            )
            
            deleted_count = len(ids)
            
            logger.info(
                "Vectors deleted", 
                collection=collection_name, 
                count=deleted_count
            )
            
            return deleted_count
            
        except Exception as e:
            logger.error(
                "Failed to delete vectors", 
                collection=collection_name, 
                error=str(e)
            )
            raise
    
    async def delete_collection(
        self,
        collection_name: str
    ) -> bool:
        """Delete a collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            True if collection was deleted
        """
        try:
            # Delete collection
            await self.client.delete_collection(
                collection_name=collection_name
            )
            
            logger.info("Collection deleted", collection=collection_name)
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete collection", 
                collection=collection_name, 
                error=str(e)
            )
            raise
    
    async def get_collection_info(
        self,
        collection_name: str
    ) -> Dict[str, Any]:
        """Get information about a collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Collection information
        """
        try:
            # Get collection info
            collection_info = await self.client.get_collection(
                collection_name=collection_name
            )
            
            # Format info
            info = {
                "name": collection_info.name,
                "vectors_count": collection_info.vectors_count,
                "points_count": collection_info.points_count,
                "status": collection_info.status,
                "vector_size": collection_info.config.params.vectors.size,
                "distance": collection_info.config.params.vectors.distance,
                "created_at": collection_info.created_at.isoformat() if collection_info.created_at else None
            }
            
            return info
            
        except Exception as e:
            logger.error(
                "Failed to get collection info", 
                collection=collection_name, 
                error=str(e)
            )
            raise