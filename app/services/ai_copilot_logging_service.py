"""
AI Copilot Logging Service

Service for logging all AI Copilot interactions to MongoDB.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.connection import get_mongodb
from app.models.ai_copilot_log import (
    AICopilotLogMongo,
    AICopilotLogResponse,
    AICopilotLogQuery,
    AICopilotLogStats,
    AIToolUsage,
    AIErrorLog
)
from app.services.rbac_service import rbac_service, Permission

logger = logging.getLogger(__name__)


class AICopilotLoggingService:
    """Service for AI Copilot audit logging"""
    
    def __init__(self):
        self.mongodb: Optional[AsyncIOMotorDatabase] = None
        self.collection_name = "ai_copilot_logs"
        
    async def initialize(self):
        """Initialize MongoDB connection and create indexes"""
        self.mongodb = await get_mongodb()
        
        # Create indexes for efficient querying
        collection = self.mongodb[self.collection_name]
        
        await collection.create_index("log_id", unique=True)
        await collection.create_index("organization_id")
        await collection.create_index("user_id")
        await collection.create_index("created_at")
        await collection.create_index([("organization_id", 1), ("created_at", -1)])
        await collection.create_index([("organization_id", 1), ("user_id", 1)])
        await collection.create_index([("organization_id", 1), ("status", 1)])
        await collection.create_index("prompt", name="prompt_text_index")
        
        logger.info("AI Copilot logging service initialized")
    
    async def log_interaction(
        self,
        user_id: str,
        organization_id: str,
        prompt: str,
        response: str,
        tools_used: List[AIToolUsage],
        errors: List[AIErrorLog],
        status: bool,
        conversation_id: Optional[str] = None,
        user_email: Optional[str] = None,
        user_role: Optional[str] = None,
        total_execution_time_ms: Optional[int] = None,
        llm_model_used: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        response_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        embedding_tokens: Optional[int] = None,
        status_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_source: Optional[str] = None
    ) -> str:
        """
        Log an AI Copilot interaction
        
        Args:
            user_id: User ID
            organization_id: Organization ID
            prompt: User's prompt
            response: AI's response
            tools_used: List of tools used
            errors: List of errors encountered
            status: Success status
            conversation_id: Optional conversation ID
            user_email: Optional user email
            user_role: Optional user role
            total_execution_time_ms: Total execution time
            llm_model_used: LLM model used
            response_tokens: Number of tokens in response
            status_message: Optional status message
            ip_address: User's IP address
            user_agent: User agent string
            request_source: Request source (web, mobile, api)
            
        Returns:
            Log ID
        """
        if self.mongodb is None:
            await self.initialize()
        
        log_entry = AICopilotLogMongo(
            user_id=user_id,
            organization_id=organization_id,
            user_email=user_email,
            user_role=user_role,
            prompt=prompt,
            response=response,
            conversation_id=conversation_id,
            tools_used=tools_used,
            errors=errors,
            status=status,
            status_message=status_message,
            total_execution_time_ms=total_execution_time_ms,
            llm_model_used=llm_model_used,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens,
            embedding_tokens=embedding_tokens,
            ip_address=ip_address,
            user_agent=user_agent,
            request_source=request_source
        )
        
        collection = self.mongodb[self.collection_name]
        result = await collection.insert_one(log_entry.model_dump(by_alias=True, exclude={"id"}))
        
        logger.info(f"Logged AI interaction: {log_entry.log_id} for user {user_id}")
        return log_entry.log_id
    
    async def get_logs(
        self,
        query: AICopilotLogQuery,
        requester_org_id: str,
        requester_role: str
    ) -> List[AICopilotLogResponse]:
        """
        Get AI Copilot logs with filtering
        
        Args:
            query: Query parameters
            requester_org_id: Organization ID of requester
            requester_role: Role of requester
            
        Returns:
            List of log entries
        """
        if self.mongodb is None:
            await self.initialize()
        
        # Build MongoDB query
        mongo_query: Dict[str, Any] = {}
        
        # Organization isolation - always filter by org
        if rbac_service.has_permission(requester_role, Permission.READ_ALL_DATA):
            # Admin can see all orgs if org_id not specified
            if query.organization_id:
                mongo_query["organization_id"] = query.organization_id
        else:
            # Non-admin can only see their org
            mongo_query["organization_id"] = requester_org_id
        
        # User filter
        if query.user_id:
            mongo_query["user_id"] = query.user_id
        
        # Status filter
        if query.status is not None:
            mongo_query["status"] = query.status
        
        # Date range filter
        if query.date_from or query.date_to:
            date_filter: Dict[str, Any] = {}
            if query.date_from:
                date_filter["$gte"] = query.date_from
            if query.date_to:
                date_filter["$lte"] = query.date_to
            mongo_query["created_at"] = date_filter
        
        # Text search in prompt
        if query.search_prompt:
            mongo_query["prompt"] = {"$regex": query.search_prompt, "$options": "i"}
        
        # Text search in response
        if query.search_response:
            mongo_query["response"] = {"$regex": query.search_response, "$options": "i"}
        
        # Tool filter
        if query.tool_name:
            mongo_query["tools_used.tool_name"] = query.tool_name
        
        collection = self.mongodb[self.collection_name]
        cursor = collection.find(mongo_query).sort("created_at", -1).skip(query.skip).limit(query.limit)
        
        logs = []
        async for doc in cursor:
            log = AICopilotLogResponse(
                log_id=doc["log_id"],
                user_id=doc["user_id"],
                organization_id=doc["organization_id"],
                user_email=doc.get("user_email"),
                user_role=doc.get("user_role"),
                prompt=doc["prompt"],
                response=doc["response"],
                prompt_tokens=doc.get("prompt_tokens"),
                response_tokens=doc.get("response_tokens"),
                total_tokens=doc.get("total_tokens"),
                embedding_tokens=doc.get("embedding_tokens"),
                tools_used=[AIToolUsage(**tool) for tool in doc.get("tools_used", [])],
                errors=[AIErrorLog(**error) for error in doc.get("errors", [])],
                status=doc["status"],
                status_message=doc.get("status_message"),
                total_execution_time_ms=doc.get("total_execution_time_ms"),
                llm_model_used=doc.get("llm_model_used"),
                created_at=doc["created_at"]
            )
            logs.append(log)
        
        return logs
    
    async def get_log_by_id(
        self,
        log_id: str,
        requester_org_id: str,
        requester_role: str
    ) -> Optional[AICopilotLogResponse]:
        """Get a specific log entry by ID"""
        if self.mongodb is None:
            await self.initialize()
        
        collection = self.mongodb[self.collection_name]
        doc = await collection.find_one({"log_id": log_id})
        
        if not doc:
            return None
        
        # Check organization access
        if not rbac_service.has_permission(requester_role, Permission.READ_ALL_DATA):
            if doc["organization_id"] != requester_org_id:
                logger.warning(f"User from org {requester_org_id} tried to access log from org {doc['organization_id']}")
                return None
        
        return AICopilotLogResponse(
            log_id=doc["log_id"],
            user_id=doc["user_id"],
            organization_id=doc["organization_id"],
            user_email=doc.get("user_email"),
            user_role=doc.get("user_role"),
            prompt=doc["prompt"],
            response=doc["response"],
            prompt_tokens=doc.get("prompt_tokens"),
            response_tokens=doc.get("response_tokens"),
            total_tokens=doc.get("total_tokens"),
            embedding_tokens=doc.get("embedding_tokens"),
            tools_used=[AIToolUsage(**tool) for tool in doc.get("tools_used", [])],
            errors=[AIErrorLog(**error) for error in doc.get("errors", [])],
            status=doc["status"],
            status_message=doc.get("status_message"),
            total_execution_time_ms=doc.get("total_execution_time_ms"),
            llm_model_used=doc.get("llm_model_used"),
            created_at=doc["created_at"]
        )
    
    async def get_stats(
        self,
        organization_id: str,
        user_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> AICopilotLogStats:
        """
        Get statistics for AI Copilot usage
        
        Args:
            organization_id: Organization ID
            user_id: Optional user ID filter
            date_from: Optional start date
            date_to: Optional end date
            
        Returns:
            Statistics object
        """
        if self.mongodb is None:
            await self.initialize()
        
        collection = self.mongodb[self.collection_name]
        
        # Build match query
        match_query: Dict[str, Any] = {"organization_id": organization_id}
        if user_id:
            match_query["user_id"] = user_id
        if date_from or date_to:
            date_filter: Dict[str, Any] = {}
            if date_from:
                date_filter["$gte"] = date_from
            if date_to:
                date_filter["$lte"] = date_to
            match_query["created_at"] = date_filter
        
        # Aggregation pipeline
        pipeline = [
            {"$match": match_query},
            {
                "$facet": {
                    "total": [{"$count": "count"}],
                    "successful": [{"$match": {"status": True}}, {"$count": "count"}],
                    "failed": [{"$match": {"status": False}}, {"$count": "count"}],
                    "tools": [
                        {"$unwind": "$tools_used"},
                        {"$group": {"_id": "$tools_used.tool_name", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                        {"$limit": 10}
                    ],
                    "errors": [
                        {"$unwind": "$errors"},
                        {"$count": "count"}
                    ],
                    "avg_time": [
                        {"$match": {"total_execution_time_ms": {"$ne": None}}},
                        {"$group": {"_id": None, "avg": {"$avg": "$total_execution_time_ms"}}}
                    ],
                    "token_stats": [
                        {"$match": {"total_tokens": {"$ne": None}}},
                        {"$group": {
                            "_id": None,
                            "total_tokens": {"$sum": "$total_tokens"},
                            "total_prompt_tokens": {"$sum": "$prompt_tokens"},
                            "total_response_tokens": {"$sum": "$response_tokens"},
                            "total_embedding_tokens": {"$sum": "$embedding_tokens"},
                            "avg_tokens": {"$avg": "$total_tokens"}
                        }}
                    ],
                    "models": [
                        {"$match": {"llm_model_used": {"$ne": None}}},
                        {"$group": {"_id": "$llm_model_used", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                        {"$limit": 10}
                    ],
                    "active_users": [
                        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                        {"$limit": 10}
                    ]
                }
            }
        ]
        
        result = await collection.aggregate(pipeline).to_list(1)
        
        if not result:
            return AICopilotLogStats(
                total_queries=0,
                successful_queries=0,
                failed_queries=0,
                total_tools_used=0,
                total_errors=0
            )
        
        data = result[0]
        
        # Extract token stats
        token_stats = data["token_stats"][0] if data["token_stats"] else {}
        
        return AICopilotLogStats(
            total_queries=data["total"][0]["count"] if data["total"] else 0,
            successful_queries=data["successful"][0]["count"] if data["successful"] else 0,
            failed_queries=data["failed"][0]["count"] if data["failed"] else 0,
            total_tools_used=sum(t["count"] for t in data["tools"]),
            total_errors=data["errors"][0]["count"] if data["errors"] else 0,
            avg_execution_time_ms=data["avg_time"][0]["avg"] if data["avg_time"] else None,
            total_tokens_used=token_stats.get("total_tokens", 0),
            total_prompt_tokens=token_stats.get("total_prompt_tokens", 0),
            total_response_tokens=token_stats.get("total_response_tokens", 0),
            total_embedding_tokens=token_stats.get("total_embedding_tokens", 0),
            avg_tokens_per_query=token_stats.get("avg_tokens"),
            most_used_tools=[{"tool": t["_id"], "count": t["count"]} for t in data["tools"]],
            most_active_users=[{"user_id": u["_id"], "count": u["count"]} for u in data["active_users"]],
            most_used_models=[{"model": m["_id"], "count": m["count"]} for m in data.get("models", [])]
        )
    
    async def get_recent_logs(
        self,
        organization_id: str,
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[AICopilotLogResponse]:
        """Get recent logs for organization or user"""
        query = AICopilotLogQuery(
            organization_id=organization_id,
            user_id=user_id,
            limit=limit,
            skip=0
        )
        
        return await self.get_logs(query, organization_id, "admin")


# Global instance
ai_copilot_logging_service = AICopilotLoggingService()
