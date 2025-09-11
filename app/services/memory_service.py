"""
Memory and Context Management Service

Handles AI memory, context persistence, knowledge base management,
embeddings, and vector storage using MongoDB and Redis caching.
"""

from typing import Dict, List, Any, Optional, Tuple
import asyncio
import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4
import hashlib
from bson import ObjectId
import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.connection import get_mongodb, get_redis, get_qdrant
from app.core.config import settings

logger = logging.getLogger(__name__)


class MemoryService:
    """
    AI Memory and Context Management Service
    
    Features:
    - Long-term memory storage in MongoDB
    - Short-term context caching in Redis
    - Knowledge base management
    - Vector embeddings for semantic search
    - User-specific memory and preferences
    - ERP system context awareness
    """
    
    def __init__(self):
        self.mongodb: Optional[AsyncIOMotorDatabase] = None
        self.redis = None
        self.qdrant = None
        self.memory_retention_days = 90
        self.context_cache_ttl = 3600  # 1 hour
        self.max_context_size = 10000  # tokens
        
    async def initialize(self):
        """Initialize database connections"""
        self.mongodb = await get_mongodb()
        self.redis = await get_redis()
        self.qdrant = await get_qdrant()
        
    async def store_memory(
        self,
        user_id: str,
        organization_id: str,
        memory_type: str,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        embedding: Optional[List[float]] = None
    ) -> str:
        """
        Store a memory in long-term storage
        
        Args:
            user_id: User identifier
            organization_id: Organization identifier
            memory_type: Type of memory (conversation, fact, preference, etc.)
            content: Memory content
            context: Additional context data
            importance: Memory importance score (0.0 to 1.0)
            tags: Optional tags for categorization
            embedding: Optional vector embedding
            
        Returns:
            Memory ID
        """
        if self.mongodb is None:
            await self.initialize()
            
        memory_id = str(uuid4())
        now = datetime.utcnow()
        
        # Create content hash for deduplication
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Check for existing memory with same content
        existing = await self.mongodb.memories.find_one({
            "user_id": user_id,
            "organization_id": organization_id,
            "content_hash": content_hash
        })
        
        if existing:
            # Update existing memory
            await self.mongodb.memories.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "updated_at": now,
                        "access_count": existing.get("access_count", 0) + 1,
                        "importance": max(existing.get("importance", 0), importance)
                    }
                }
            )
            return existing["memory_id"]
        
        memory_doc = {
            "_id": ObjectId(),
            "memory_id": memory_id,
            "user_id": user_id,
            "organization_id": organization_id,
            "memory_type": memory_type,
            "content": content,
            "content_hash": content_hash,
            "context": context or {},
            "importance": importance,
            "tags": tags or [],
            "embedding": embedding,
            "access_count": 0,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(days=self.memory_retention_days)
        }
        
        await self.mongodb.memories.insert_one(memory_doc)
        
        # Store in vector database if embedding provided
        if embedding and self.qdrant:
            try:
                await self.qdrant.upsert(
                    collection_name="ai_memories",
                    points=[{
                        "id": memory_id,
                        "vector": embedding,
                        "payload": {
                            "user_id": user_id,
                            "organization_id": organization_id,
                            "memory_type": memory_type,
                            "content": content[:1000],  # Truncate for payload
                            "importance": importance,
                            "access_level": access_level,
                            "created_at": now.isoformat()
                        }
                    }]
                )
            except Exception as e:
                logger.warning(f"Failed to store memory in vector DB: {e}")
        
        logger.info(f"Stored memory {memory_id} for user {user_id}")
        return memory_id
    
    async def retrieve_memories(
        self,
        user_id: str,
        organization_id: str,
        memory_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        min_importance: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memories for a user
        
        Args:
            user_id: User identifier
            organization_id: Organization identifier
            memory_types: Optional memory type filters
            tags: Optional tag filters
            limit: Maximum number of memories to return
            min_importance: Minimum importance threshold
            
        Returns:
            List of memories
        """
        if self.mongodb is None:
            await self.initialize()
            
        query = {
            "user_id": user_id,
            "organization_id": organization_id,
            "importance": {"$gte": min_importance},
            "expires_at": {"$gt": datetime.utcnow()}
        }
        
        if memory_types:
            query["memory_type"] = {"$in": memory_types}
            
        if tags:
            query["tags"] = {"$in": tags}
            
        cursor = self.mongodb.memories.find(query).sort([
            ("importance", -1),
            ("updated_at", -1)
        ]).limit(limit)
        
        memories = []
        async for doc in cursor:
            memories.append({
                "memory_id": doc["memory_id"],
                "memory_type": doc["memory_type"],
                "content": doc["content"],
                "context": doc.get("context", {}),
                "importance": doc["importance"],
                "tags": doc.get("tags", []),
                "access_count": doc.get("access_count", 0),
                "created_at": doc["created_at"].isoformat(),
                "updated_at": doc["updated_at"].isoformat()
            })
            
        return memories
    
    async def search_memories_semantic(
        self,
        user_id: str,
        organization_id: str,
        query_embedding: List[float],
        limit: int = 10,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for memories using vector similarity
        
        Args:
            user_id: User identifier
            organization_id: Organization identifier
            query_embedding: Query vector embedding
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            
        Returns:
            List of similar memories with scores
        """
        if not self.qdrant:
            await self.initialize()
            
        try:
            search_result = await self.qdrant.search(
                collection_name="ai_memories",
                query_vector=query_embedding,
                query_filter={
                    "must": [
                        {"key": "user_id", "match": {"value": user_id}},
                        {"key": "organization_id", "match": {"value": organization_id}}
                    ]
                },
                limit=limit,
                score_threshold=score_threshold
            )
            
            memories = []
            for result in search_result:
                memories.append({
                    "memory_id": result.id,
                    "score": result.score,
                    "content": result.payload.get("content", ""),
                    "memory_type": result.payload.get("memory_type", ""),
                    "importance": result.payload.get("importance", 0.0),
                    "tags": result.payload.get("tags", []),
                    "created_at": result.payload.get("created_at", "")
                })
                
            return memories
            
        except Exception as e:
            logger.error(f"Semantic memory search failed: {e}")
            return []
    
    async def store_user_context(
        self,
        user_id: str,
        organization_id: str,
        context_type: str,
        context_data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store user context in Redis cache
        
        Args:
            user_id: User identifier
            organization_id: Organization identifier
            context_type: Type of context (session, preferences, etc.)
            context_data: Context data to store
            ttl: Time to live in seconds
            
        Returns:
            True if successful
        """
        if not self.redis:
            await self.initialize()
            
        cache_key = f"user_context:{user_id}:{organization_id}:{context_type}"
        
        try:
            await self.redis.set(
                cache_key,
                json.dumps(context_data, default=str),
                ex=ttl or self.context_cache_ttl
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store user context: {e}")
            return False
    
    async def get_user_context(
        self,
        user_id: str,
        organization_id: str,
        context_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve user context from cache
        
        Args:
            user_id: User identifier
            organization_id: Organization identifier
            context_type: Type of context to retrieve
            
        Returns:
            Context data or None if not found
        """
        if not self.redis:
            await self.initialize()
            
        cache_key = f"user_context:{user_id}:{organization_id}:{context_type}"
        
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.error(f"Failed to retrieve user context: {e}")
            
        return None
    
    async def store_knowledge(
        self,
        title: str,
        content: str,
        source: str,
        category: str = "documentation",
        metadata: Optional[Dict[str, Any]] = None,
        organization_id: str = "system",
        access_level: str = "all"
    ) -> str:
        """
        Store knowledge entry with automatic embedding generation and duplicate prevention
        
        Args:
            title: Knowledge entry title
            content: Knowledge content
            source: Source of the knowledge (file path, URL, etc.)
            category: Knowledge category
            metadata: Additional metadata
            organization_id: Organization identifier (defaults to system)
            access_level: Access level (all, admin, specific_roles)
            
        Returns:
            Knowledge entry ID
        """
        if self.mongodb is None:
            await self.initialize()
            
        # Create content hash for deduplication
        content_hash = hashlib.sha256(f"{title}{content}".encode()).hexdigest()
        
        # Check for existing entry with same content hash
        existing = await self.mongodb.knowledge_base.find_one({
            "content_hash": content_hash,
            "organization_id": organization_id
        })
        
        if existing:
            # Update existing entry metadata but keep existing embedding
            await self.mongodb.knowledge_base.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "updated_at": datetime.utcnow(),
                        "metadata": metadata or existing.get("metadata", {}),
                        "access_count": existing.get("access_count", 0) + 1
                    }
                }
            )
            logger.debug(f"Reusing existing knowledge entry (duplicate prevented): {existing['entry_id']}")
            return existing["entry_id"]
        
        # Check for similar content by source to prevent file-based duplicates
        source_existing = await self.mongodb.knowledge_base.find_one({
            "source": source,
            "organization_id": organization_id,
            "title": title
        })
        
        if source_existing:
            logger.debug(f"Knowledge entry already exists for source {source}, skipping duplicate")
            return source_existing["entry_id"]
        
        # Generate new entry
        entry_id = str(uuid4())
        now = datetime.utcnow()
        
        # Generate embedding for new content only
        embedding = await self._generate_embedding(f"{title}\n\n{content}")
        
        entry_doc = {
            "_id": ObjectId(),
            "entry_id": entry_id,
            "organization_id": organization_id,
            "category": category,
            "title": title,
            "content": content,
            "source": source,
            "content_hash": content_hash,
            "metadata": metadata or {},
            "embedding": embedding,
            "access_level": access_level,
            "access_count": 0,
            "version": "1.0",
            "created_at": now,
            "updated_at": now,
            "duplicate_check_performed": True
        }
        
        await self.mongodb.knowledge_base.insert_one(entry_doc)
        
        # Store in vector database
        if embedding and self.qdrant:
            try:
                await self.qdrant.upsert(
                    collection_name="erp_knowledge",
                    points=[{
                        "id": entry_id,
                        "vector": embedding,
                        "payload": {
                            "organization_id": organization_id,
                            "category": category,
                            "title": title,
                            "content": content[:1000],  # Truncate for payload
                            "source": source,
                            "access_level": access_level,
                            "created_at": now.isoformat(),
                            "metadata": metadata or {}
                        }
                    }]
                )
            except Exception as e:
                logger.warning(f"Failed to store knowledge entry in vector DB: {e}")
        
        logger.info(f"Stored new knowledge entry {entry_id}: {title}")
        return entry_id
    
    async def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        organization_id: str = "system",
        limit: int = 10,
        score_threshold: float = 0.6,
        similarity_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using semantic search
        
        Args:
            query: Search query text
            category: Optional category filter
            organization_id: Organization identifier
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            similarity_threshold: Alternative name for score_threshold (for compatibility)
            
        Returns:
            List of relevant knowledge entries
        """
        if not self.qdrant:
            await self.initialize()
            
        try:
            # Use similarity_threshold if provided, otherwise use score_threshold
            threshold = similarity_threshold if similarity_threshold is not None else score_threshold
            
            # Generate embedding for query
            query_embedding = await self._generate_embedding(query)
            
            query_filter = {
                "must": [
                    {"key": "organization_id", "match": {"value": organization_id}}
                ]
            }
            
            if category:
                query_filter["must"].append({
                    "key": "category",
                    "match": {"value": category}
                })
            
            search_result = await self.qdrant.search(
                collection_name="erp_knowledge",
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=limit,
                score_threshold=threshold
            )
            
            entries = []
            for result in search_result:
                entries.append({
                    "entry_id": result.id,
                    "score": result.score,
                    "title": result.payload.get("title", ""),
                    "content": result.payload.get("content", ""),
                    "category": result.payload.get("category", ""),
                    "source": result.payload.get("source", ""),
                    "created_at": result.payload.get("created_at", ""),
                    "metadata": result.payload.get("metadata", {})
                })
                
            return entries
            
        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            return []
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using the configured LLM service (Gemini by default)"""
        try:
            # First try to use the LLM service for embeddings (Gemini by default)
            from app.services.llm_service import get_llm_service
            
            llm_service = get_llm_service()
            if llm_service:
                try:
                    # Try to generate embedding using the LLM service
                    # Note: This is a placeholder - Gemini doesn't have a direct embedding API
                    # In practice, you might want to use a dedicated embedding model
                    logger.info("Using LLM service for embedding generation")
                    
                    # For now, use a deterministic hash-based approach
                    # In production, you could use sentence-transformers or similar
                    import hashlib
                    import struct
                    
                    # Create a deterministic embedding based on text hash and content
                    text_hash = hashlib.sha256(text.encode()).digest()
                    embedding = []
                    
                    # Use text content to create more meaningful embeddings
                    words = text.lower().split()[:100]  # Use first 100 words
                    word_hashes = [hashlib.md5(word.encode()).digest()[:4] for word in words]
                    
                    # Combine text hash with word hashes for better representation
                    combined_data = text_hash + b''.join(word_hashes)
                    
                    for i in range(0, min(len(combined_data), 1536 * 4), 4):
                        chunk = combined_data[i:i+4]
                        if len(chunk) == 4:
                            value = struct.unpack('f', chunk)[0]
                            # Normalize to reasonable range
                            embedding.append(float(value) / 1e6)
                        else:
                            embedding.append(0.0)
                    
                    # Pad or truncate to 1536 dimensions
                    while len(embedding) < 1536:
                        embedding.append(0.0)
                    
                    return embedding[:1536]
                    
                except Exception as e:
                    logger.warning(f"LLM service embedding failed: {e}")
            
            # Fallback to third-party service only if LLM service is not available
            try:
                from app.services.third_party_api_service import third_party_api_service
                embedding = await third_party_api_service.generate_embedding(text)
                if embedding:
                    logger.info("Using third-party service for embedding generation")
                    return embedding
            except Exception as e:
                logger.warning(f"Third-party embedding service failed: {e}")
            
            # Final fallback to deterministic hash-based embedding
            logger.info("Using fallback hash-based embedding generation")
            import hashlib
            import struct
            
            text_hash = hashlib.sha256(text.encode()).digest()
            embedding = []
            
            for i in range(0, min(len(text_hash), 1536 * 4), 4):
                chunk = text_hash[i:i+4]
                if len(chunk) == 4:
                    value = struct.unpack('f', chunk)[0]
                    embedding.append(float(value) / 1e6)  # Normalize
                else:
                    embedding.append(0.0)
            
            # Pad or truncate to 1536 dimensions
            while len(embedding) < 1536:
                embedding.append(0.0)
            
            return embedding[:1536]
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * 1536

    async def store_knowledge_base_entry(
        self,
        organization_id: str,
        document_type: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
        access_level: str = "all"
    ) -> str:
        """
        Store knowledge base entry
        
        Args:
            organization_id: Organization identifier
            document_type: Type of document (manual, faq, procedure, etc.)
            title: Document title
            content: Document content
            metadata: Additional metadata
            embedding: Vector embedding for semantic search
            access_level: Access level (all, admin, specific_roles)
            
        Returns:
            Knowledge base entry ID
        """
        if self.mongodb is None:
            await self.initialize()
            
        entry_id = str(uuid4())
        now = datetime.utcnow()
        
        # Create content hash for deduplication
        content_hash = hashlib.sha256(f"{title}{content}".encode()).hexdigest()
        
        entry_doc = {
            "_id": ObjectId(),
            "entry_id": entry_id,
            "organization_id": organization_id,
            "document_type": document_type,
            "title": title,
            "content": content,
            "content_hash": content_hash,
            "metadata": metadata or {},
            "embedding": embedding,
            "access_level": access_level,
            "version": "1.0",
            "created_at": now,
            "updated_at": now
        }
        
        await self.mongodb.knowledge_base.insert_one(entry_doc)
        
        # Store in vector database if embedding provided
        if embedding and self.qdrant:
            try:
                await self.qdrant.upsert(
                    collection_name="knowledge_base",
                    points=[{
                        "id": entry_id,
                        "vector": embedding,
                        "payload": {
                            "organization_id": organization_id,
                            "document_type": document_type,
                            "title": title,
                            "content": content[:1000],  # Truncate for payload
                            "access_level": access_level,
                            "created_at": now.isoformat()
                        }
                    }]
                )
            except Exception as e:
                logger.warning(f"Failed to store knowledge entry in vector DB: {e}")
        
        logger.info(f"Stored knowledge base entry {entry_id}")
        return entry_id
    
    async def search_knowledge_base(
        self,
        organization_id: str,
        query_embedding: List[float],
        document_types: Optional[List[str]] = None,
        access_level: str = "all",
        limit: int = 10,
        score_threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using semantic similarity
        
        Args:
            organization_id: Organization identifier
            query_embedding: Query vector embedding
            document_types: Optional document type filters
            access_level: Required access level
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            
        Returns:
            List of relevant knowledge base entries
        """
        if not self.qdrant:
            await self.initialize()
            
        try:
            query_filter = {
                "must": [
                    {"key": "organization_id", "match": {"value": organization_id}},
                    {"key": "access_level", "match": {"any": [access_level, "all"]}}
                ]
            }
            
            if document_types:
                query_filter["must"].append({
                    "key": "document_type",
                    "match": {"any": document_types}
                })
            
            search_result = await self.qdrant.search(
                collection_name="knowledge_base",
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=limit,
                score_threshold=score_threshold
            )
            
            entries = []
            for result in search_result:
                entries.append({
                    "entry_id": result.id,
                    "score": result.score,
                    "title": result.payload.get("title", ""),
                    "content": result.payload.get("content", ""),
                    "document_type": result.payload.get("document_type", ""),
                    "access_level": result.payload.get("access_level", ""),
                    "created_at": result.payload.get("created_at", "")
                })
                
            return entries
            
        except Exception as e:
            logger.error(f"Knowledge base search failed: {e}")
            return []
    
    async def store_user_preferences(
        self,
        user_id: str,
        organization_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """
        Store user preferences
        
        Args:
            user_id: User identifier
            organization_id: Organization identifier
            preferences: User preferences data
            
        Returns:
            True if successful
        """
        if self.mongodb is None:
            await self.initialize()
            
        try:
            await self.mongodb.user_preferences.update_one(
                {"user_id": user_id, "organization_id": organization_id},
                {
                    "$set": {
                        "preferences": preferences,
                        "updated_at": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "user_id": user_id,
                        "organization_id": organization_id,
                        "created_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            
            # Cache in Redis
            await self.store_user_context(
                user_id, organization_id, "preferences", preferences
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store user preferences: {e}")
            return False
    
    async def get_user_preferences(
        self,
        user_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Get user preferences
        
        Args:
            user_id: User identifier
            organization_id: Organization identifier
            
        Returns:
            User preferences
        """
        # Try cache first
        cached_prefs = await self.get_user_context(
            user_id, organization_id, "preferences"
        )
        if cached_prefs:
            return cached_prefs
            
        # Fallback to MongoDB
        if self.mongodb is None:
            await self.initialize()
            
        doc = await self.mongodb.user_preferences.find_one({
            "user_id": user_id,
            "organization_id": organization_id
        })
        
        preferences = doc.get("preferences", {}) if doc else {}
        
        # Cache for future use
        if preferences:
            await self.store_user_context(
                user_id, organization_id, "preferences", preferences
            )
            
        return preferences
    
    async def cleanup_expired_memories(self):
        """Clean up expired memories"""
        if self.mongodb is None:
            await self.initialize()
            
        now = datetime.utcnow()
        
        # Remove expired memories
        result = await self.mongodb.memories.delete_many({
            "expires_at": {"$lt": now}
        })
        
        if result.deleted_count > 0:
            logger.info(f"Cleaned up {result.deleted_count} expired memories")
    
    async def get_memory_statistics(
        self,
        organization_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get memory usage statistics
        
        Args:
            organization_id: Organization identifier
            user_id: Optional user filter
            
        Returns:
            Memory statistics
        """
        if self.mongodb is None:
            await self.initialize()
            
        match_query = {"organization_id": organization_id}
        if user_id:
            match_query["user_id"] = user_id
            
        pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": "$memory_type",
                    "count": {"$sum": 1},
                    "avg_importance": {"$avg": "$importance"},
                    "total_access": {"$sum": "$access_count"}
                }
            }
        ]
        
        stats = {}
        async for doc in self.mongodb.memories.aggregate(pipeline):
            stats[doc["_id"]] = {
                "count": doc["count"],
                "avg_importance": round(doc["avg_importance"], 2),
                "total_access": doc["total_access"]
            }
            
        return stats


# Global memory service instance
memory_service = MemoryService()
