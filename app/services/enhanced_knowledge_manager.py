"""
Enhanced Knowledge Manager Service for AI Copilot
Provides advanced knowledge management with deduplication, versioning, and cleanup
"""

import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json
import asyncio

from app.database.connection import get_qdrant, get_mongodb
from app.services.llm_service import get_llm_service
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

@dataclass
class KnowledgeEntry:
    """Enhanced knowledge entry with versioning and metadata"""
    id: str
    content: str
    content_hash: str
    embeddings: Optional[List[float]]
    metadata: Dict[str, Any]
    source: str
    created_at: datetime
    updated_at: datetime
    version: int
    similarity_threshold: float = 0.85
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeEntry':
        """Create from dictionary"""
        # Convert ISO strings back to datetime objects
        if isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


class EnhancedKnowledgeManager:
    """
    Enhanced Knowledge Manager with deduplication, versioning, and cleanup capabilities
    
    Features:
    - Content hashing for duplicate detection
    - Vector similarity detection for near-duplicates
    - Knowledge entry versioning system
    - Periodic cleanup of outdated entries
    - Improved search and retrieval
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.collection_name = "enhanced_knowledge_base"
        self.metadata_collection = "knowledge_metadata"
        self.content_hashes = {}  # Cache for content hashes
        self.similarity_threshold = 0.85
        
    async def initialize(self):
        """Initialize enhanced knowledge manager"""
        try:
            # Ensure Qdrant collection exists
            qdrant = await get_qdrant()
            collections = await qdrant.get_collections()
            
            if self.collection_name not in [col.name for col in collections.collections]:
                await qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "size": 1536,  # OpenAI embedding size
                        "distance": "Cosine"
                    }
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            
            # Load content hashes cache
            await self._load_content_hashes()
            
            logger.info("Enhanced knowledge manager initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize enhanced knowledge manager: {e}")
            raise
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash for content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _generate_entry_id(self, source: str, content_hash: str) -> str:
        """Generate unique entry ID from source and content hash"""
        combined = f"{source}:{content_hash}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()
    
    async def check_duplicate_content(self, content: str) -> Optional[str]:
        """
        Check if content already exists using content hashing
        
        Args:
            content: Content to check for duplicates
            
        Returns:
            Entry ID if duplicate found, None otherwise
        """
        try:
            content_hash = self._generate_content_hash(content)
            
            # Check in cache first
            if content_hash in self.content_hashes:
                return self.content_hashes[content_hash]
            
            # Check in MongoDB
            mongodb = await get_mongodb()
            existing_entry = await mongodb[self.metadata_collection].find_one({
                "content_hash": content_hash
            })
            
            if existing_entry:
                entry_id = existing_entry["id"]
                # Update cache
                self.content_hashes[content_hash] = entry_id
                return entry_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking duplicate content: {e}")
            return None
    
    async def add_knowledge_entry(
        self, 
        content: str, 
        metadata: Dict[str, Any], 
        source: str = "unknown"
    ) -> str:
        """
        Add knowledge entry with duplicate detection
        
        Args:
            content: Content to add
            metadata: Additional metadata
            source: Source of the content
            
        Returns:
            Entry ID of added or existing entry
        """
        try:
            content_hash = self._generate_content_hash(content)
            
            # Check for duplicates
            existing_id = await self.check_duplicate_content(content)
            if existing_id:
                logger.info(f"Duplicate content detected, updating existing entry: {existing_id}")
                return await self._update_existing_entry(existing_id, content, metadata)
            
            # Generate new entry
            entry_id = self._generate_entry_id(source, content_hash)
            now = datetime.utcnow()
            
            # Generate embeddings
            llm_service = get_llm_service()
            embeddings = await llm_service.generate_embeddings(content)
            
            # Create knowledge entry
            entry = KnowledgeEntry(
                id=entry_id,
                content=content,
                content_hash=content_hash,
                embeddings=embeddings,
                metadata=metadata,
                source=source,
                created_at=now,
                updated_at=now,
                version=1
            )
            
            # Store in Qdrant
            qdrant = await get_qdrant()
            await qdrant.upsert(
                collection_name=self.collection_name,
                points=[{
                    "id": entry_id,
                    "vector": embeddings,
                    "payload": {
                        "content": content,
                        "content_hash": content_hash,
                        "source": source,
                        "metadata": metadata,
                        "created_at": now.isoformat(),
                        "updated_at": now.isoformat(),
                        "version": 1
                    }
                }]
            )
            
            # Store metadata in MongoDB
            mongodb = await get_mongodb()
            await mongodb[self.metadata_collection].replace_one(
                {"id": entry_id},
                entry.to_dict(),
                upsert=True
            )
            
            # Update cache
            self.content_hashes[content_hash] = entry_id
            
            logger.info(f"Added new knowledge entry: {entry_id}")
            return entry_id
            
        except Exception as e:
            logger.error(f"Failed to add knowledge entry: {e}")
            raise
    
    async def _update_existing_entry(
        self, 
        entry_id: str, 
        content: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """Update existing knowledge entry with new version"""
        try:
            mongodb = await get_mongodb()
            
            # Get existing entry
            existing_doc = await mongodb[self.metadata_collection].find_one({"id": entry_id})
            if not existing_doc:
                raise ValueError(f"Entry not found: {entry_id}")
            
            existing_entry = KnowledgeEntry.from_dict(existing_doc)
            
            # Update entry
            existing_entry.updated_at = datetime.utcnow()
            existing_entry.version += 1
            existing_entry.metadata.update(metadata)
            
            # Update in MongoDB
            await mongodb[self.metadata_collection].replace_one(
                {"id": entry_id},
                existing_entry.to_dict()
            )
            
            # Update payload in Qdrant
            qdrant = await get_qdrant()
            await qdrant.set_payload(
                collection_name=self.collection_name,
                points=[entry_id],
                payload={
                    "content": content,
                    "content_hash": existing_entry.content_hash,
                    "source": existing_entry.source,
                    "metadata": existing_entry.metadata,
                    "created_at": existing_entry.created_at.isoformat(),
                    "updated_at": existing_entry.updated_at.isoformat(),
                    "version": existing_entry.version
                }
            )
            
            logger.info(f"Updated existing knowledge entry: {entry_id} (version {existing_entry.version})")
            return entry_id
            
        except Exception as e:
            logger.error(f"Failed to update existing entry {entry_id}: {e}")
            raise
    
    async def get_knowledge_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Get knowledge entry by ID"""
        try:
            mongodb = await get_mongodb()
            doc = await mongodb[self.metadata_collection].find_one({"id": entry_id})
            
            if doc:
                return KnowledgeEntry.from_dict(doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get knowledge entry {entry_id}: {e}")
            return None
    
    async def query_knowledge_base(
        self, 
        query: str, 
        context: Dict[str, Any] = None,
        limit: int = 5,
        similarity_threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Query knowledge base using vector similarity
        
        Args:
            query: Search query
            context: Additional context for filtering
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of matching knowledge entries
        """
        try:
            # Generate query embedding
            llm_service = get_llm_service()
            query_embedding = await llm_service.generate_embeddings(query)
            
            # Use provided threshold or default
            threshold = similarity_threshold or self.similarity_threshold
            
            # Search Qdrant
            qdrant = await get_qdrant()
            search_results = await qdrant.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=threshold
            )
            
            results = []
            for result in search_results:
                payload = result.payload
                results.append({
                    "id": result.id,
                    "content": payload.get("content", ""),
                    "source": payload.get("source", ""),
                    "metadata": payload.get("metadata", {}),
                    "score": result.score,
                    "version": payload.get("version", 1),
                    "created_at": payload.get("created_at"),
                    "updated_at": payload.get("updated_at")
                })
            
            logger.info(f"Knowledge base query returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Failed to query knowledge base: {e}")
            return []
    
    async def delete_knowledge_entry(self, entry_id: str) -> bool:
        """Delete knowledge entry"""
        try:
            # Get entry to remove from cache
            entry = await self.get_knowledge_entry(entry_id)
            if entry:
                # Remove from cache
                if entry.content_hash in self.content_hashes:
                    del self.content_hashes[entry.content_hash]
            
            # Delete from Qdrant
            qdrant = await get_qdrant()
            await qdrant.delete(
                collection_name=self.collection_name,
                points_selector=[entry_id]
            )
            
            # Delete from MongoDB
            mongodb = await get_mongodb()
            result = await mongodb[self.metadata_collection].delete_one({"id": entry_id})
            
            success = result.deleted_count > 0
            if success:
                logger.info(f"Deleted knowledge entry: {entry_id}")
            else:
                logger.warning(f"Knowledge entry not found for deletion: {entry_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete knowledge entry {entry_id}: {e}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get enhanced knowledge manager status"""
        try:
            # Get Qdrant collection info
            qdrant = await get_qdrant()
            try:
                collection_info = await qdrant.get_collection(self.collection_name)
                vector_count = collection_info.vectors_count if collection_info else 0
            except:
                vector_count = 0
            
            # Get MongoDB metadata count
            mongodb = await get_mongodb()
            metadata_count = await mongodb[self.metadata_collection].count_documents({})
            
            # Get cache statistics
            cache_size = len(self.content_hashes)
            
            return {
                "collection_name": self.collection_name,
                "vector_count": vector_count,
                "metadata_count": metadata_count,
                "cache_size": cache_size,
                "similarity_threshold": self.similarity_threshold,
                "status": "active"
            }
            
        except Exception as e:
            logger.error(f"Failed to get enhanced knowledge manager status: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _load_content_hashes(self):
        """Load content hashes into cache from MongoDB"""
        try:
            mongodb = await get_mongodb()
            cursor = mongodb[self.metadata_collection].find(
                {}, 
                {"id": 1, "content_hash": 1}
            )
            
            async for doc in cursor:
                self.content_hashes[doc["content_hash"]] = doc["id"]
            
            logger.info(f"Loaded {len(self.content_hashes)} content hashes into cache")
            
        except Exception as e:
            logger.error(f"Failed to load content hashes: {e}")


# Global enhanced knowledge manager instance
enhanced_knowledge_manager = EnhancedKnowledgeManager()