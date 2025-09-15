"""
Conversation Session Management Service

Handles conversation sessions, memory management, and context persistence
using MongoDB collections for scalable conversation history.
"""

from typing import Dict, List, Any, Optional, Tuple
import asyncio
import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.connection import get_mongodb, get_redis
from app.config.settings import get_settings

settings = get_settings()
from app.models.api import ConversationStatus, MessageRole

logger = logging.getLogger(__name__)


class ConversationService:
    """
    Conversation Session Management Service
    
    Features:
    - Session-based conversation management
    - MongoDB persistence for conversations and messages
    - Redis caching for active sessions
    - User-specific conversation history
    - Context and memory management
    - Conversation analytics
    """
    
    def __init__(self):
        self.mongodb: Optional[AsyncIOMotorDatabase] = None
        self.redis = None
        self.session_timeout = 3600  # 1 hour
        self.max_conversations_per_user = 100
        self.max_messages_per_conversation = 1000
        
    async def initialize(self):
        """Initialize database connections"""
        self.mongodb = await get_mongodb()
        try:
            self.redis = await get_redis()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed, continuing without cache: {e}")
            self.redis = None
        
    async def create_conversation(
        self, 
        user_id: str, 
        organization_id: str,
        title: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new conversation session
        
        Args:
            user_id: User identifier
            organization_id: Organization identifier
            title: Optional conversation title
            context: Initial conversation context
            metadata: Additional metadata
            
        Returns:
            Created conversation details
        """
        if self.mongodb is None:
            await self.initialize()
            
        # Check user conversation limit
        user_conversations = await self.get_user_conversations(user_id, organization_id)
        if len(user_conversations) >= self.max_conversations_per_user:
            # Archive oldest conversations
            await self._archive_old_conversations(user_id, organization_id)
        
        conversation_id = str(uuid4())
        now = datetime.utcnow()
        
        conversation_doc = {
            "conversation_id": conversation_id,
            "organization_id": organization_id,
            "user_id": user_id,
            "title": title or f"Conversation {now.strftime('%Y-%m-%d %H:%M')}",
            "status": ConversationStatus.ACTIVE.value,
            "context": context or {},
            "metadata": metadata or {},
            "message_count": 0,
            "created_at": now,
            "updated_at": now,
            "last_activity": now
        }
        
        # Insert into MongoDB
        result = await self.mongodb.conversations.insert_one(conversation_doc)
        
        # Cache in Redis for quick access
        cache_key = f"conversation:{conversation_id}"
        await self.redis.hset(cache_key, mapping={
            "conversation_id": conversation_id,
            "user_id": user_id,
            "organization_id": organization_id,
            "title": conversation_doc["title"],
            "status": conversation_doc["status"],
            "created_at": now.isoformat(),
            "context": json.dumps(context or {}),
            "message_count": "0"
        })
        await self.redis.expire(cache_key, self.session_timeout)
        
        # Add to user's conversation list
        user_conversations_key = f"user_conversations:{user_id}:{organization_id}"
        await self.redis.zadd(user_conversations_key, {conversation_id: now.timestamp()})
        
        logger.info(f"Created conversation {conversation_id} for user {user_id}")
        
        return {
            "conversation_id": conversation_id,
            "title": conversation_doc["title"],
            "status": conversation_doc["status"],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "message_count": 0,
            "context": context or {},
            "metadata": metadata or {}
        }
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get conversation details by ID
        
        Args:
            conversation_id: Conversation identifier
            
        Returns:
            Conversation details or None if not found
        """
        if self.mongodb is None:
            await self.initialize()
            
        # Try Redis cache first (if available)
        cache_key = f"conversation:{conversation_id}"
        try:
            if self.redis:
                cached_data = await self.redis.hgetall(cache_key)
            else:
                cached_data = None
            
            # Validate cache data has required fields
            required_fields = ["conversation_id", "user_id", "organization_id", "title", "status", "created_at"]
            if cached_data and all(field in cached_data for field in required_fields):
                return {
                    "conversation_id": cached_data["conversation_id"],
                    "user_id": cached_data["user_id"],
                    "organization_id": cached_data["organization_id"],
                    "title": cached_data["title"],
                    "status": cached_data["status"],
                    "created_at": cached_data["created_at"],
                    "updated_at": cached_data.get("updated_at", cached_data["created_at"]),
                    "context": json.loads(cached_data.get("context", "{}")),
                    "message_count": int(cached_data.get("message_count", 0))
                }
            elif cached_data:
                # Cache exists but is incomplete, clear it
                logger.warning(f"Incomplete cached data for conversation {conversation_id}, clearing cache")
                await self.redis.delete(cache_key)
        except Exception as e:
            logger.warning(f"Redis cache error for conversation {conversation_id}: {str(e)}")
            # Continue to MongoDB fallback
        
        # Fallback to MongoDB
        conversation = await self.mongodb.conversations.find_one(
            {"conversation_id": conversation_id}
        )
        
        if not conversation:
            return None
            
        # Update cache
        await self.redis.hset(cache_key, mapping={
            "conversation_id": conversation["conversation_id"],
            "user_id": conversation["user_id"],
            "organization_id": conversation["organization_id"],
            "title": conversation["title"],
            "status": conversation["status"],
            "created_at": conversation["created_at"].isoformat(),
            "context": json.dumps(conversation.get("context", {})),
            "message_count": str(conversation.get("message_count", 0))
        })
        await self.redis.expire(cache_key, self.session_timeout)
        
        return {
            "conversation_id": conversation["conversation_id"],
            "user_id": conversation["user_id"],
            "organization_id": conversation["organization_id"],
            "title": conversation["title"],
            "status": conversation["status"],
            "created_at": conversation["created_at"].isoformat(),
            "updated_at": conversation.get("updated_at", conversation["created_at"]).isoformat(),
            "context": conversation.get("context", {}),
            "metadata": conversation.get("metadata", {}),
            "message_count": conversation.get("message_count", 0)
        }
    
    async def get_user_conversations(
        self, 
        user_id: str, 
        organization_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get user's conversations with pagination
        
        Args:
            user_id: User identifier
            organization_id: Organization identifier
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            status: Optional status filter
            
        Returns:
            List of user's conversations
        """
        if self.mongodb is None:
            await self.initialize()
            
        query = {
            "user_id": user_id,
            "organization_id": organization_id
        }
        
        if status:
            query["status"] = status
            
        cursor = self.mongodb.conversations.find(query).sort("updated_at", -1)
        
        if offset:
            cursor = cursor.skip(offset)
        if limit:
            cursor = cursor.limit(limit)
            
        conversations = []
        async for doc in cursor:
            conversations.append({
                "id": doc["conversation_id"],
                "organization_id": doc["organization_id"],
                "user_id": doc["user_id"],
                "title": doc["title"],
                "status": doc["status"],
                "context": doc.get("context", {}),
                "metadata": doc.get("metadata", {}),
                "created_at": doc["created_at"].isoformat(),
                "updated_at": doc.get("updated_at", doc["created_at"]).isoformat(),
                "message_count": doc.get("message_count", 0),
                "last_message_at": doc.get("last_activity", doc["created_at"]).isoformat()
            })
        
        # Get total count for pagination
        total_count = await self.mongodb.conversations.count_documents(query)
            
        return {
            "conversations": conversations,
            "total": total_count
        }
    
    async def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        reasoning_steps: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Add a message to a conversation
        
        Args:
            conversation_id: Target conversation ID
            role: Message role (user, assistant, system)
            content: Message content
            user_id: User ID (for user messages)
            metadata: Additional message metadata
            reasoning_steps: AI reasoning steps if applicable
            
        Returns:
            Created message details
        """
        if self.mongodb is None:
            await self.initialize()
            
        message_id = str(uuid4())
        now = datetime.utcnow()
        
        message_doc = {
            "_id": ObjectId(),
            "message_id": message_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": role.value if hasattr(role, 'value') else role,
            "content": content,
            "metadata": metadata or {},
            "reasoning_steps": reasoning_steps or [],
            "created_at": now,
            "tokens_used": metadata.get("tokens_used", 0) if metadata else 0,
            "model_used": metadata.get("model_used") if metadata else None
        }
        
        # Insert message
        await self.mongodb.messages.insert_one(message_doc)
        
        # Update conversation
        await self.mongodb.conversations.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {"updated_at": now, "last_activity": now},
                "$inc": {"message_count": 1}
            }
        )
        
        # Update Redis cache
        cache_key = f"conversation:{conversation_id}"
        await self.redis.hincrby(cache_key, "message_count", 1)
        await self.redis.expire(cache_key, self.session_timeout)
        
        logger.info(f"Added message {message_id} to conversation {conversation_id}")
        
        return {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "role": message_doc["role"],
            "content": content,
            "created_at": now.isoformat(),
            "metadata": metadata or {},
            "reasoning_steps": reasoning_steps or []
        }
    
    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0,
        include_reasoning: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get messages for a conversation
        
        Args:
            conversation_id: Conversation identifier
            limit: Maximum number of messages to return
            offset: Number of messages to skip
            include_reasoning: Whether to include reasoning steps
            
        Returns:
            List of conversation messages
        """
        if self.mongodb is None:
            await self.initialize()
            
        cursor = self.mongodb.messages.find(
            {"conversation_id": conversation_id}
        ).sort("created_at", 1)
        
        if offset:
            cursor = cursor.skip(offset)
        if limit:
            cursor = cursor.limit(limit)
            
        messages = []
        async for doc in cursor:
            message_data = {
                "message_id": doc["message_id"],
                "conversation_id": doc["conversation_id"],
                "user_id": doc.get("user_id"),
                "role": doc["role"],
                "content": doc["content"],
                "created_at": doc["created_at"].isoformat(),
                "metadata": doc.get("metadata", {}),
                "tokens_used": doc.get("tokens_used", 0),
                "model_used": doc.get("model_used")
            }
            
            if include_reasoning and doc.get("reasoning_steps"):
                message_data["reasoning_steps"] = doc["reasoning_steps"]
                
            messages.append(message_data)
            
        return messages
    
    async def update_conversation_context(
        self,
        conversation_id: str,
        context_updates: Dict[str, Any]
    ) -> bool:
        """
        Update conversation context
        
        Args:
            conversation_id: Conversation identifier
            context_updates: Context data to merge
            
        Returns:
            True if successful
        """
        if self.mongodb is None:
            await self.initialize()
            
        # Update MongoDB
        result = await self.mongodb.conversations.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "context": context_updates,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            # Update Redis cache
            cache_key = f"conversation:{conversation_id}"
            await self.redis.hset(cache_key, "context", json.dumps(context_updates))
            return True
            
        return False
    
    async def archive_conversation(self, conversation_id: str) -> bool:
        """
        Archive a conversation
        
        Args:
            conversation_id: Conversation identifier
            
        Returns:
            True if successful
        """
        if self.mongodb is None:
            await self.initialize()
            
        result = await self.mongodb.conversations.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "status": ConversationStatus.ARCHIVED.value,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            # Remove from Redis cache
            cache_key = f"conversation:{conversation_id}"
            await self.redis.delete(cache_key)
            return True
            
        return False
    
    async def _archive_old_conversations(self, user_id: str, organization_id: str):
        """Archive old conversations to make room for new ones"""
        # Get oldest conversations
        old_conversations = await self.mongodb.conversations.find(
            {
                "user_id": user_id,
                "organization_id": organization_id,
                "status": ConversationStatus.ACTIVE.value
            }
        ).sort("updated_at", 1).limit(10).to_list(10)
        
        for conv in old_conversations:
            await self.archive_conversation(conv["conversation_id"])
            
        logger.info(f"Archived {len(old_conversations)} old conversations for user {user_id}")
    
    async def get_conversation_analytics(
        self,
        organization_id: str,
        user_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get conversation analytics
        
        Args:
            organization_id: Organization identifier
            user_id: Optional user filter
            days: Number of days to analyze
            
        Returns:
            Analytics data
        """
        if self.mongodb is None:
            await self.initialize()
            
        start_date = datetime.utcnow() - timedelta(days=days)
        
        match_query = {
            "organization_id": organization_id,
            "created_at": {"$gte": start_date}
        }
        
        if user_id:
            match_query["user_id"] = user_id
            
        pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$created_at"
                        }
                    },
                    "total_conversations": {"$sum": 1},
                    "active_conversations": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$status", ConversationStatus.ACTIVE.value]},
                                1,
                                0
                            ]
                        }
                    },
                    "avg_messages": {"$avg": "$message_count"}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        analytics = []
        async for doc in self.mongodb.conversations.aggregate(pipeline):
            analytics.append({
                "date": doc["_id"],
                "total_conversations": doc["total_conversations"],
                "active_conversations": doc["active_conversations"],
                "avg_messages": round(doc["avg_messages"], 2)
            })
            
        return {
            "period_days": days,
            "analytics": analytics,
            "generated_at": datetime.utcnow().isoformat()
        }


# Global conversation service instance
conversation_service = ConversationService()
