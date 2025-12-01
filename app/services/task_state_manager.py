"""
Task State Manager

Manages task state in PostgreSQL and Redis.
Provides fast access to task status and history.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import structlog
import asyncpg
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class TaskStateManager:
    """
    Manages task state across PostgreSQL and Redis
    
    - PostgreSQL: Persistent storage, full task history
    - Redis: Fast access to active tasks, caching
    """
    
    def __init__(
        self,
        postgres_dsn: str = None,
        redis_url: str = None
    ):
        """
        Initialize task state manager
        
        Args:
            postgres_dsn: PostgreSQL connection string
            redis_url: Redis connection URL
        """
        self.postgres_dsn = postgres_dsn or "postgresql://postgres:postgres@localhost:5432/erp_db"
        self.redis_url = redis_url or "redis://localhost:6379"
        self.pg_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
    
    async def initialize(self):
        """Initialize database connections"""
        # PostgreSQL connection pool
        try:
            self.pg_pool = await asyncpg.create_pool(
                self.postgres_dsn,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            logger.info("PostgreSQL pool created")
        except Exception as e:
            logger.error("Failed to create PostgreSQL pool", error=str(e))
            raise
        
        # Redis connection
        try:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Redis client connected")
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def create_task(self, task: Dict[str, Any]) -> str:
        """
        Create task in database
        
        Args:
            task: Task data
            
        Returns:
            Task ID
        """
        task_id = task['task_id']
        
        query = """
            INSERT INTO agent_tasks (
                task_id, agent_id, organization_id, task_type, task_name,
                description, instructions, parameters, context,
                priority, priority_score, scheduled_for, deadline,
                assigned_by, depends_on, recurrence_rule,
                status, created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                $14, $15, $16, $17, $18
            )
            RETURNING task_id
        """
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute(
                query,
                task_id,
                task['agent_id'],
                task['organization_id'],
                task['task_type'],
                task.get('task_name'),
                task.get('description'),
                task.get('instructions'),
                json.dumps(task.get('parameters', {})),
                json.dumps(task.get('context', {})),
                task.get('priority', 'normal'),
                task.get('priority_score', 0),
                datetime.fromisoformat(task['scheduled_for']) if task.get('scheduled_for') else None,
                datetime.fromisoformat(task['deadline']) if task.get('deadline') else None,
                task.get('assigned_by'),
                task.get('depends_on', []),
                task.get('recurrence_rule'),
                'pending',
                datetime.utcnow()
            )
        
        # Cache in Redis
        await self._cache_task(task_id, task)
        
        logger.info("Task created", task_id=task_id)
        return task_id
    
    async def update_task_status(
        self,
        task_id: str,
        status: str,
        **kwargs
    ):
        """
        Update task status
        
        Args:
            task_id: Task ID
            status: New status
            **kwargs: Additional fields to update
        """
        # Build update query dynamically
        set_clauses = ["status = $2", "updated_at = NOW()"]
        params = [task_id, status]
        param_idx = 3
        
        if status == "running" and "started_at" not in kwargs:
            set_clauses.append("started_at = NOW()")
        
        if status == "completed" and "completed_at" not in kwargs:
            set_clauses.append("completed_at = NOW()")
        
        if status == "paused" and "paused_at" not in kwargs:
            set_clauses.append("paused_at = NOW()")
        
        # Add additional fields
        for key, value in kwargs.items():
            if key in ['result', 'error_message', 'execution_time_ms', 'tokens_used', 
                       'tools_called', 'code_generated', 'execution_state', 'checkpoint_data']:
                set_clauses.append(f"{key} = ${param_idx}")
                if isinstance(value, (dict, list)):
                    params.append(json.dumps(value))
                else:
                    params.append(value)
                param_idx += 1
        
        query = f"""
            UPDATE agent_tasks
            SET {', '.join(set_clauses)}
            WHERE task_id = $1
        """
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute(query, *params)
        
        # Update cache
        await self.redis_client.hset(
            f"agent:task:{task_id}",
            mapping={
                "status": status,
                "updated_at": datetime.utcnow().isoformat()
            }
        )
        
        logger.info("Task status updated", task_id=task_id, status=status)
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task by ID
        
        Args:
            task_id: Task ID
            
        Returns:
            Task data or None
        """
        # Try cache first
        cached = await self.redis_client.hgetall(f"agent:task:{task_id}")
        if cached:
            return self._deserialize_task(cached)
        
        # Fetch from database
        query = """
            SELECT * FROM agent_tasks WHERE task_id = $1
        """
        
        async with self.pg_pool.acquire() as conn:
            row = await conn.fetchrow(query, task_id)
            
            if row:
                task = dict(row)
                await self._cache_task(task_id, task)
                return task
        
        return None
    
    async def get_agent_tasks(
        self,
        agent_id: str,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get tasks for an agent
        
        Args:
            agent_id: Agent ID
            status: Filter by status (optional)
            limit: Maximum results
            
        Returns:
            List of tasks
        """
        query = """
            SELECT * FROM agent_tasks
            WHERE agent_id = $1
        """
        params = [agent_id]
        
        if status:
            query += " AND status = $2"
            params.append(status)
        
        query += " ORDER BY priority_score DESC, created_at DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def get_pending_tasks(
        self,
        organization_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get pending tasks
        
        Args:
            organization_id: Filter by organization (optional)
            limit: Maximum results
            
        Returns:
            List of pending tasks
        """
        query = """
            SELECT * FROM agent_tasks
            WHERE status = 'pending'
        """
        params = []
        
        if organization_id:
            query += " AND organization_id = $1"
            params.append(organization_id)
        
        query += " ORDER BY priority_score DESC, created_at ASC LIMIT $" + str(len(params) + 1)
        params.append(limit)
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def cancel_task(self, task_id: str, reason: str):
        """
        Cancel a task
        
        Args:
            task_id: Task ID
            reason: Cancellation reason
        """
        await self.update_task_status(
            task_id,
            "cancelled",
            error_message=f"Cancelled: {reason}"
        )
        
        # Remove from cache
        await self.redis_client.delete(f"agent:task:{task_id}")
        
        logger.info("Task cancelled", task_id=task_id, reason=reason)
    
    async def _cache_task(self, task_id: str, task: Dict[str, Any]):
        """Cache task in Redis"""
        # Serialize task for Redis
        cache_data = {
            "task_id": task_id,
            "agent_id": task.get('agent_id'),
            "status": task.get('status'),
            "priority": task.get('priority'),
            "created_at": task.get('created_at', datetime.utcnow()).isoformat() if isinstance(task.get('created_at'), datetime) else task.get('created_at')
        }
        
        await self.redis_client.hset(
            f"agent:task:{task_id}",
            mapping=cache_data
        )
        
        # Set TTL (24 hours)
        await self.redis_client.expire(f"agent:task:{task_id}", 86400)
        
        # Add to agent's task list
        await self.redis_client.zadd(
            f"agent:tasks:{task.get('agent_id')}",
            {task_id: task.get('priority_score', 0)}
        )
    
    def _deserialize_task(self, cached: Dict) -> Dict[str, Any]:
        """Deserialize task from Redis"""
        return {
            "task_id": cached.get('task_id'),
            "agent_id": cached.get('agent_id'),
            "status": cached.get('status'),
            "priority": cached.get('priority'),
            "created_at": cached.get('created_at')
        }
    
    async def close(self):
        """Close connections"""
        if self.pg_pool:
            await self.pg_pool.close()
            logger.info("PostgreSQL pool closed")
        
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis client closed")


# Global instance
_task_state_manager: Optional[TaskStateManager] = None


async def get_task_state_manager() -> TaskStateManager:
    """Get or create task state manager instance"""
    global _task_state_manager
    
    if _task_state_manager is None:
        _task_state_manager = TaskStateManager()
        await _task_state_manager.initialize()
    
    return _task_state_manager
