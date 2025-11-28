"""
ERP Data Service

Service for querying real ERP data from PostgreSQL, MongoDB, and Redis.
Provides structured data access for AI agents to answer questions about actual ERP data.
"""

from typing import Dict, Any, List, Optional
import structlog
from datetime import datetime, timedelta

from app.database.connection import DatabaseManager

logger = structlog.get_logger(__name__)


class ERPDataService:
    """Service for accessing ERP data across databases"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.postgres = None
        self.mongo = None
        self.redis = None
        self._initialized = False
        self.rbac_service = None
    
    async def initialize(self):
        """Initialize database connections"""
        if self._initialized:
            return
        
        try:
            # Get database clients
            try:
                self.postgres = self.db_manager.get_postgres_client()
            except RuntimeError:
                logger.warning("PostgreSQL not available")
                self.postgres = None
            
            self.mongo = self.db_manager.get_mongo_client()
            self.redis = self.db_manager.get_redis_client()
            
            # Initialize RBAC service
            from app.services.rbac_service import get_rbac_service
            self.rbac_service = get_rbac_service()
            
            self._initialized = True
            logger.info("ERP Data Service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize ERP Data Service: {e}")
            raise
    
    async def get_system_overview(self) -> Dict[str, Any]:
        """Get overview of ERP system status and statistics"""
        overview = {
            "timestamp": datetime.utcnow().isoformat(),
            "databases": {},
            "services": {},
            "statistics": {}
        }
        
        # Check PostgreSQL
        if self.postgres:
            try:
                async with self.postgres.acquire() as conn:
                    # Get database size
                    result = await conn.fetchrow(
                        "SELECT pg_database_size(current_database()) as size"
                    )
                    overview["databases"]["postgresql"] = {
                        "status": "connected",
                        "size_bytes": result['size'] if result else 0
                    }
            except Exception as e:
                overview["databases"]["postgresql"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Check MongoDB
        if self.mongo:
            try:
                # Get database stats
                db_list = await self.mongo.list_database_names()
                overview["databases"]["mongodb"] = {
                    "status": "connected",
                    "databases": db_list
                }
            except Exception as e:
                overview["databases"]["mongodb"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Check Redis
        if self.redis:
            try:
                info = await self.redis.info()
                overview["databases"]["redis"] = {
                    "status": "connected",
                    "keys": info.get("db0", {}).get("keys", 0),
                    "memory_used": info.get("used_memory_human", "unknown")
                }
            except Exception as e:
                overview["databases"]["redis"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return overview
    
    async def search_users(
        self, 
        query: Optional[str] = None,
        limit: int = 10,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for users in the system with RBAC filtering
        
        Args:
            query: Search query
            limit: Maximum results
            user_context: User context with role, org_id, user_id
        """
        if not self.postgres:
            return []
        
        try:
            # Build base query
            base_query = """
                SELECT id, email, created_at, is_active, organization_id
                FROM users
            """
            
            where_clauses = []
            params = []
            param_count = 1
            
            # Add RBAC filter if user context provided
            if user_context and self.rbac_service:
                user_role = user_context.get("role", "user")
                user_org_id = user_context.get("organization_id")
                user_id = user_context.get("user_id")
                
                # Apply organization filter for non-super-admins
                if user_role.lower() != "super_admin":
                    if user_role.lower() in ["admin", "manager"]:
                        # Organization-level access
                        where_clauses.append(f"organization_id = ${param_count}")
                        params.append(user_org_id)
                        param_count += 1
                    else:
                        # User-level access (own data only)
                        where_clauses.append(f"id = ${param_count}")
                        params.append(user_id)
                        param_count += 1
            
            # Add search filter
            if query:
                where_clauses.append(f"(email ILIKE ${param_count} OR id::text ILIKE ${param_count})")
                params.append(f"%{query}%")
                param_count += 1
            
            # Build final query
            if where_clauses:
                base_query += " WHERE " + " AND ".join(where_clauses)
            
            base_query += f" ORDER BY created_at DESC LIMIT ${param_count}"
            params.append(limit)
            
            async with self.postgres.acquire() as conn:
                results = await conn.fetch(base_query, *params)
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return []
    
    async def get_user_statistics(self) -> Dict[str, Any]:
        """Get user statistics"""
        if not self.postgres:
            return {"error": "PostgreSQL not available"}
        
        try:
            async with self.postgres.acquire() as conn:
                # Total users
                total = await conn.fetchval("SELECT COUNT(*) FROM users")
                
                # Active users
                active = await conn.fetchval(
                    "SELECT COUNT(*) FROM users WHERE is_active = true"
                )
                
                # Recent signups (last 30 days)
                recent = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM users 
                    WHERE created_at > NOW() - INTERVAL '30 days'
                    """
                )
                
                return {
                    "total_users": total or 0,
                    "active_users": active or 0,
                    "recent_signups_30d": recent or 0,
                    "inactive_users": (total or 0) - (active or 0)
                }
                
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return {"error": str(e)}
    
    async def get_conversations_summary(self) -> Dict[str, Any]:
        """Get AI conversation statistics from MongoDB"""
        if not self.mongo:
            return {"error": "MongoDB not available"}
        
        try:
            conversations_col = self.mongo["ai_copilot"]["conversations"]
            
            # Total conversations
            total = await conversations_col.count_documents({})
            
            # Active conversations
            active = await conversations_col.count_documents({"status": "active"})
            
            # Recent conversations (last 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent = await conversations_col.count_documents({
                "created_at": {"$gte": week_ago}
            })
            
            # Get most active users
            pipeline = [
                {"$group": {
                    "_id": "$user_id",
                    "conversation_count": {"$sum": 1}
                }},
                {"$sort": {"conversation_count": -1}},
                {"$limit": 5}
            ]
            
            top_users = []
            async for doc in conversations_col.aggregate(pipeline):
                top_users.append({
                    "user_id": str(doc["_id"]),
                    "conversations": doc["conversation_count"]
                })
            
            return {
                "total_conversations": total,
                "active_conversations": active,
                "recent_conversations_7d": recent,
                "top_users": top_users
            }
            
        except Exception as e:
            logger.error(f"Error getting conversation summary: {e}")
            return {"error": str(e)}
    
    async def get_recent_messages(
        self, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent AI chat messages"""
        if not self.mongo:
            return []
        
        try:
            messages_col = self.mongo["ai_copilot"]["messages"]
            
            cursor = messages_col.find().sort("created_at", -1).limit(limit)
            
            messages = []
            async for doc in cursor:
                messages.append({
                    "message_id": str(doc.get("_id")),
                    "conversation_id": str(doc.get("conversation_id")),
                    "role": doc.get("role"),
                    "content": doc.get("content", "")[:100] + "...",  # Truncate
                    "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None
                })
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting recent messages: {e}")
            return []
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get Redis cache statistics"""
        if not self.redis:
            return {"error": "Redis not available"}
        
        try:
            info = await self.redis.info()
            
            return {
                "total_keys": info.get("db0", {}).get("keys", 0),
                "memory_used": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "uptime_days": info.get("uptime_in_days", 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
            
        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
            return {"error": str(e)}
    
    def _calculate_hit_rate(self, info: Dict) -> float:
        """Calculate cache hit rate"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return round((hits / total) * 100, 2)
    
    async def query_custom_sql(
        self, 
        query: str,
        params: Optional[List] = None
    ) -> List[Dict[str, Any]]:
        """Execute custom SQL query (with safety checks)"""
        if not self.postgres:
            return []
        
        # Safety check - only allow SELECT queries
        if not query.strip().upper().startswith("SELECT"):
            logger.warning(f"Rejected non-SELECT query: {query}")
            return []
        
        try:
            async with self.postgres.acquire() as conn:
                if params:
                    results = await conn.fetch(query, *params)
                else:
                    results = await conn.fetch(query)
                
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"Error executing custom query: {e}")
            return []
    
    async def get_data_summary(self, entity_type: str) -> Dict[str, Any]:
        """Get summary for specific entity type"""
        
        summaries = {
            "users": self.get_user_statistics,
            "conversations": self.get_conversations_summary,
            "cache": self.get_cache_statistics,
            "system": self.get_system_overview
        }
        
        handler = summaries.get(entity_type.lower())
        
        if handler:
            return await handler()
        else:
            return {
                "error": f"Unknown entity type: {entity_type}",
                "available_types": list(summaries.keys())
            }


# Global instance
_erp_data_service: Optional[ERPDataService] = None


async def get_erp_data_service() -> ERPDataService:
    """Get or create ERP data service instance"""
    global _erp_data_service
    
    if _erp_data_service is None:
        from app.database.connection import get_db_manager
        db_manager = await get_db_manager()
        _erp_data_service = ERPDataService(db_manager)
        await _erp_data_service.initialize()
    
    return _erp_data_service
