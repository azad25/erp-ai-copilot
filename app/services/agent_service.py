"""
Agent Service

Core service for managing AI agents.
Handles CRUD operations, configuration, and agent lifecycle.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import structlog
import asyncpg
import json

logger = structlog.get_logger(__name__)


class AgentService:
    """
    Service for managing AI agents
    
    Provides CRUD operations and agent management functionality.
    """
    
    def __init__(self, postgres_dsn: str = None):
        """
        Initialize agent service
        
        Args:
            postgres_dsn: PostgreSQL connection string
        """
        self.postgres_dsn = postgres_dsn or "postgresql://postgres:postgres@localhost:5432/erp_db"
        self.pg_pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize database connection"""
        try:
            self.pg_pool = await asyncpg.create_pool(
                self.postgres_dsn,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            logger.info("Agent service initialized")
        except Exception as e:
            logger.error("Failed to initialize agent service", error=str(e))
            raise
    
    async def create_agent(
        self,
        organization_id: str,
        name: str,
        role: str,
        model_provider: str,
        model_name: str,
        created_by: str,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        personality: Optional[Dict] = None,
        allowed_tools: Optional[List[str]] = None,
        permissions: Optional[Dict] = None,
        triggers: Optional[Dict] = None,
        schedule: Optional[Dict] = None,
        memory_config: Optional[Dict] = None,
        max_parallel_tasks: int = 3,
        max_daily_tokens: Optional[int] = None
    ) -> str:
        """
        Create a new AI agent
        
        Args:
            organization_id: Organization ID
            name: Agent name
            role: Agent role (data_entry, accountant, pm, inventory, sales)
            model_provider: LLM provider (openai, anthropic, gemini, etc.)
            model_name: Model name
            created_by: User ID who created the agent
            description: Agent description
            system_prompt: Custom system prompt
            temperature: LLM temperature
            max_tokens: Max tokens per request
            personality: Personality configuration
            allowed_tools: List of allowed tool names
            permissions: RBAC permissions
            triggers: Event triggers configuration
            schedule: Scheduling configuration
            memory_config: Memory settings
            max_parallel_tasks: Max concurrent tasks
            max_daily_tokens: Daily token limit
            
        Returns:
            Agent ID
        """
        agent_id = str(uuid.uuid4())
        
        # Validate role
        valid_roles = ['data_entry', 'accountant', 'pm', 'inventory', 'sales', 'custom']
        if role not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {valid_roles}")
        
        # Check organization limits
        await self._check_organization_limits(organization_id)
        
        # Get role template if not custom
        if role != 'custom':
            from app.models.agent_roles import get_role_template
            template = get_role_template(role)
            
            # Apply template defaults if not provided
            if not system_prompt:
                system_prompt = template['default_prompt']
            if not allowed_tools:
                allowed_tools = template['allowed_tools']
            if not permissions:
                permissions = {p.value: True for p in template['permissions']}
        
        query = """
            INSERT INTO ai_agents (
                agent_id, organization_id, name, role, description,
                model_provider, model_name, temperature, max_tokens,
                system_prompt, personality, allowed_tools, permissions,
                triggers, schedule, state, memory_config,
                created_by, created_at, max_parallel_tasks, max_daily_tokens
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                $14, $15, $16, $17, $18, $19, $20, $21
            )
            RETURNING agent_id
        """
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute(
                query,
                agent_id,
                organization_id,
                name,
                role,
                description,
                model_provider,
                model_name,
                temperature,
                max_tokens,
                system_prompt,
                json.dumps(personality or {}),
                allowed_tools or [],
                json.dumps(permissions or {}),
                json.dumps(triggers or {}),
                json.dumps(schedule or {}),
                'active',
                json.dumps(memory_config or {}),
                created_by,
                datetime.utcnow(),
                max_parallel_tasks,
                max_daily_tokens
            )
        
        # Initialize agent memory
        await self._initialize_agent_memory(agent_id, organization_id)
        
        logger.info(
            "Agent created",
            agent_id=agent_id,
            organization_id=organization_id,
            name=name,
            role=role
        )
        
        return agent_id
    
    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent by ID
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent data or None
        """
        query = """
            SELECT * FROM ai_agents WHERE agent_id = $1
        """
        
        async with self.pg_pool.acquire() as conn:
            row = await conn.fetchrow(query, agent_id)
            
            if row:
                return dict(row)
        
        return None
    
    async def list_agents(
        self,
        organization_id: str,
        role: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List agents for an organization
        
        Args:
            organization_id: Organization ID
            role: Filter by role (optional)
            state: Filter by state (optional)
            limit: Maximum results
            
        Returns:
            List of agents
        """
        query = """
            SELECT * FROM ai_agents
            WHERE organization_id = $1
        """
        params = [organization_id]
        
        if role:
            query += " AND role = $2"
            params.append(role)
        
        if state:
            query += f" AND state = ${len(params) + 1}"
            params.append(state)
        
        query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1}"
        params.append(limit)
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def update_agent(
        self,
        agent_id: str,
        **updates
    ) -> bool:
        """
        Update agent configuration
        
        Args:
            agent_id: Agent ID
            **updates: Fields to update
            
        Returns:
            Success status
        """
        if not updates:
            return False
        
        # Build update query
        set_clauses = ["updated_at = NOW()"]
        params = [agent_id]
        param_idx = 2
        
        allowed_fields = [
            'name', 'description', 'model_provider', 'model_name',
            'temperature', 'max_tokens', 'system_prompt', 'personality',
            'allowed_tools', 'permissions', 'triggers', 'schedule',
            'state', 'memory_config', 'max_parallel_tasks', 'max_daily_tokens'
        ]
        
        for key, value in updates.items():
            if key in allowed_fields:
                set_clauses.append(f"{key} = ${param_idx}")
                
                # JSON fields
                if key in ['personality', 'permissions', 'triggers', 'schedule', 'memory_config']:
                    params.append(json.dumps(value))
                else:
                    params.append(value)
                
                param_idx += 1
        
        query = f"""
            UPDATE ai_agents
            SET {', '.join(set_clauses)}
            WHERE agent_id = $1
        """
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute(query, *params)
        
        logger.info("Agent updated", agent_id=agent_id, fields=list(updates.keys()))
        return True
    
    async def delete_agent(self, agent_id: str) -> bool:
        """
        Delete an agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Success status
        """
        # Archive instead of delete
        query = """
            UPDATE ai_agents
            SET state = 'archived', updated_at = NOW()
            WHERE agent_id = $1
        """
        
        async with self.pg_pool.acquire() as conn:
            await conn.execute(query, agent_id)
        
        logger.info("Agent archived", agent_id=agent_id)
        return True
    
    async def pause_agent(self, agent_id: str) -> bool:
        """
        Pause an agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Success status
        """
        return await self.update_agent(agent_id, state='paused')
    
    async def resume_agent(self, agent_id: str) -> bool:
        """
        Resume a paused agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Success status
        """
        return await self.update_agent(agent_id, state='active')
    
    async def get_agent_statistics(self, agent_id: str) -> Dict[str, Any]:
        """
        Get agent statistics
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Statistics dictionary
        """
        query = """
            SELECT
                COUNT(*) as total_tasks,
                COUNT(*) FILTER (WHERE status = 'completed') as completed_tasks,
                COUNT(*) FILTER (WHERE status = 'failed') as failed_tasks,
                AVG(execution_time_ms) as avg_execution_time,
                SUM(tokens_used) as total_tokens
            FROM agent_tasks
            WHERE agent_id = $1
        """
        
        async with self.pg_pool.acquire() as conn:
            row = await conn.fetchrow(query, agent_id)
            
            if row:
                return {
                    "total_tasks": row['total_tasks'] or 0,
                    "completed_tasks": row['completed_tasks'] or 0,
                    "failed_tasks": row['failed_tasks'] or 0,
                    "success_rate": (row['completed_tasks'] / row['total_tasks'] * 100) if row['total_tasks'] > 0 else 0,
                    "avg_execution_time_ms": float(row['avg_execution_time']) if row['avg_execution_time'] else 0,
                    "total_tokens": row['total_tokens'] or 0
                }
        
        return {}
    
    async def _check_organization_limits(self, organization_id: str):
        """Check if organization can create more agents"""
        query = """
            SELECT max_agents FROM organization_agent_limits
            WHERE organization_id = $1
        """
        
        async with self.pg_pool.acquire() as conn:
            row = await conn.fetchrow(query, organization_id)
            
            if row:
                max_agents = row['max_agents']
                
                # Count current agents
                count_query = """
                    SELECT COUNT(*) FROM ai_agents
                    WHERE organization_id = $1 AND state != 'archived'
                """
                count_row = await conn.fetchrow(count_query, organization_id)
                current_count = count_row['count']
                
                if current_count >= max_agents:
                    raise ValueError(f"Organization has reached maximum agent limit ({max_agents})")
    
    async def _initialize_agent_memory(self, agent_id: str, organization_id: str):
        """Initialize agent memory in MongoDB"""
        # TODO: Implement MongoDB memory initialization
        logger.info("Agent memory initialized", agent_id=agent_id)
    
    async def close(self):
        """Close database connections"""
        if self.pg_pool:
            await self.pg_pool.close()
            logger.info("Agent service closed")


# Global instance
_agent_service: Optional[AgentService] = None


async def get_agent_service() -> AgentService:
    """Get or create agent service instance"""
    global _agent_service
    
    if _agent_service is None:
        _agent_service = AgentService()
        await _agent_service.initialize()
    
    return _agent_service
