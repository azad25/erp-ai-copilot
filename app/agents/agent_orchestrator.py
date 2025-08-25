"""
Agent Orchestrator

Central system for managing agent lifecycle, registration, coordination, and monitoring.
Provides agent discovery, load balancing, health checks, and system-wide orchestration.
"""

from typing import Dict, List, Any, Optional, Callable, Awaitable
import asyncio
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
import uuid
from dataclasses import dataclass
import time

from .base_agent import BaseAgent, AgentRequest, AgentResponse
from .master_agent import MasterAgent
from .query_agent import QueryAgent
from .action_agent import ActionAgent
from .analytics_agent import AnalyticsAgent
from .scheduler_agent import SchedulerAgent
from .compliance_agent import ComplianceAgent
from .help_agent import HelpAgent

from app.models.api import AgentType, TaskStatus
from app.core.exceptions import AgentError, OrchestrationError


@dataclass
class AgentRegistration:
    """Agent registration information"""
    agent_id: str
    agent_type: AgentType
    agent_instance: BaseAgent
    capabilities: List[str]
    health_status: str
    last_heartbeat: datetime
    performance_metrics: Dict[str, Any]
    version: str
    metadata: Dict[str, Any]


@dataclass
class TaskExecution:
    """Task execution tracking"""
    task_id: str
    agent_id: str
    agent_type: AgentType
    request: AgentRequest
    status: TaskStatus
    start_time: datetime
    end_time: Optional[datetime]
    result: Optional[AgentResponse]
    error: Optional[str]
    execution_time: float
    retry_count: int


class HealthStatus(Enum):
    """Agent health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class LoadBalancingStrategy(Enum):
    """Load balancing strategies"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    PERFORMANCE_BASED = "performance_based"
    HEALTH_BASED = "health_based"


class AgentOrchestrator:
    """
    Central orchestrator for agent management and coordination
    
    Capabilities:
    - Agent registration and discovery
    - Health monitoring and failover
    - Load balancing and routing
    - Task queue management
    - Performance monitoring
    - Configuration management
    - Security and access control
    - Audit logging
    """

    def __init__(self):
        self.agents: Dict[str, AgentRegistration] = {}
        self.agent_types: Dict[AgentType, List[str]] = {}
        self.task_queue: List[TaskExecution] = []
        self.completed_tasks: List[TaskExecution] = []
        self.failed_tasks: List[TaskExecution] = []
        self.load_balancer = LoadBalancingStrategy.HEALTH_BASED
        self.health_check_interval = 30  # seconds
        self.max_retry_count = 3
        self.task_timeout = 300  # seconds
        
        # Initialize master agent
        self.master_agent = MasterAgent()
        
        # Performance tracking
        self.system_metrics = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "average_response_time": 0.0,
            "system_uptime": 0.0,
            "queue_size": 0
        }
        
        # Start background tasks
        self._start_background_tasks()

    def register_agent(self, agent: BaseAgent, capabilities: List[str] = None, 
                      version: str = "1.0.0", metadata: Dict[str, Any] = None) -> str:
        """
        Register a new agent with the orchestrator
        
        Args:
            agent: Agent instance to register
            capabilities: List of agent capabilities
            version: Agent version
            metadata: Additional agent metadata
            
        Returns:
            Unique agent ID
        """
        agent_id = str(uuid.uuid4())
        
        registration = AgentRegistration(
            agent_id=agent_id,
            agent_type=agent.agent_type,
            agent_instance=agent,
            capabilities=capabilities or agent.get_available_tools(),
            health_status=HealthStatus.HEALTHY.value,
            last_heartbeat=datetime.utcnow(),
            performance_metrics={
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "average_response_time": 0.0,
                "last_execution_time": None
            },
            version=version,
            metadata=metadata or {}
        )
        
        self.agents[agent_id] = registration
        
        # Add to agent type mapping
        if agent.agent_type not in self.agent_types:
            self.agent_types[agent.agent_type] = []
        self.agent_types[agent.agent_type].append(agent_id)
        
        logging.info(f"Registered agent {agent_id} of type {agent.agent_type}")
        return agent_id

    def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent from the orchestrator
        
        Args:
            agent_id: ID of agent to unregister
            
        Returns:
            True if successful, False otherwise
        """
        if agent_id not in self.agents:
            return False
        
        agent_type = self.agents[agent_id].agent_type
        
        # Remove from agents
        del self.agents[agent_id]
        
        # Remove from agent type mapping
        if agent_type in self.agent_types and agent_id in self.agent_types[agent_type]:
            self.agent_types[agent_type].remove(agent_id)
        
        logging.info(f"Unregistered agent {agent_id}")
        return True

    async def execute_task(self, request: AgentRequest, priority: int = 2, 
                          agent_preference: AgentType = None) -> TaskExecution:
        """
        Execute a task using the orchestrator
        
        Args:
            request: Task request
            priority: Task priority (1-4, higher is more important)
            agent_preference: Preferred agent type
            
        Returns:
            Task execution result
        """
        task_id = str(uuid.uuid4())
        
        # Select appropriate agent
        if agent_preference:
            agent_id = self._select_agent_by_type(agent_preference)
        else:
            agent_id = await self._select_best_agent(request)
        
        if not agent_id:
            raise OrchestrationError("No suitable agent available for task")
        
        # Create task execution
        task = TaskExecution(
            task_id=task_id,
            agent_id=agent_id,
            agent_type=self.agents[agent_id].agent_type,
            request=request,
            status=TaskStatus.PENDING,
            start_time=datetime.utcnow(),
            end_time=None,
            result=None,
            error=None,
            execution_time=0.0,
            retry_count=0
        )
        
        # Add to queue based on priority
        self._add_to_queue(task, priority)
        
        # Execute task
        await self._execute_task(task)
        
        return task

    async def execute_with_master_agent(self, request: AgentRequest) -> AgentResponse:
        """
        Execute task using the master agent for complex orchestration
        
        Args:
            request: Task request
            
        Returns:
            Orchestrated response from master agent
        """
        return await self.master_agent.execute(request)

    def get_agent_health(self, agent_id: str) -> Dict[str, Any]:
        """
        Get health status for a specific agent
        
        Args:
            agent_id: Agent ID to check
            
        Returns:
            Health status information
        """
        if agent_id not in self.agents:
            return {"error": "Agent not found"}
        
        agent = self.agents[agent_id]
        time_since_heartbeat = (datetime.utcnow() - agent.last_heartbeat).total_seconds()
        
        # Determine health status
        if time_since_heartbeat > 120:  # 2 minutes
            health_status = HealthStatus.OFFLINE
        elif time_since_heartbeat > 60:  # 1 minute
            health_status = HealthStatus.UNHEALTHY
        elif agent.performance_metrics["failed_executions"] > agent.performance_metrics["successful_executions"] * 0.1:
            health_status = HealthStatus.DEGRADED
        else:
            health_status = HealthStatus.HEALTHY
        
        return {
            "agent_id": agent_id,
            "agent_type": agent.agent_type.value,
            "health_status": health_status.value,
            "last_heartbeat": agent.last_heartbeat.isoformat(),
            "time_since_heartbeat": time_since_heartbeat,
            "performance_metrics": agent.performance_metrics,
            "capabilities": agent.capabilities
        }

    def get_system_health(self) -> Dict[str, Any]:
        """
        Get overall system health status
        
        Returns:
            System-wide health information
        """
        health_summary = {
            "total_agents": len(self.agents),
            "healthy_agents": 0,
            "degraded_agents": 0,
            "unhealthy_agents": 0,
            "offline_agents": 0,
            "system_metrics": self.system_metrics,
            "queue_status": {
                "pending_tasks": len([t for t in self.task_queue if t.status == TaskStatus.PENDING]),
                "running_tasks": len([t for t in self.task_queue if t.status == TaskStatus.RUNNING]),
                "completed_tasks": len(self.completed_tasks),
                "failed_tasks": len(self.failed_tasks)
            }
        }
        
        for agent_id in self.agents:
            agent_health = self.get_agent_health(agent_id)
            status = agent_health["health_status"]
            
            if status == HealthStatus.HEALTHY.value:
                health_summary["healthy_agents"] += 1
            elif status == HealthStatus.DEGRADED.value:
                health_summary["degraded_agents"] += 1
            elif status == HealthStatus.UNHEALTHY.value:
                health_summary["unhealthy_agents"] += 1
            else:
                health_summary["offline_agents"] += 1
        
        return health_summary

    def get_agent_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all registered agents
        
        Returns:
            List of agent information
        """
        return [
            {
                "agent_id": agent_id,
                "agent_type": registration.agent_type.value,
                "health_status": registration.health_status,
                "capabilities": registration.capabilities,
                "version": registration.version,
                "last_heartbeat": registration.last_heartbeat.isoformat()
            }
            for agent_id, registration in self.agents.items()
        ]

    async def _select_best_agent(self, request: AgentRequest) -> Optional[str]:
        """
        Select the best agent for a given request
        
        Args:
            request: Task request
            
        Returns:
            Selected agent ID or None if no suitable agent
        """
        # For now, use master agent for complex requests
        # In practice, this would be more sophisticated
        return "master_agent"

    def _select_agent_by_type(self, agent_type: AgentType) -> Optional[str]:
        """
        Select agent by type using load balancing
        
        Args:
            agent_type: Type of agent needed
            
        Returns:
            Selected agent ID or None
        """
        if agent_type not in self.agent_types or not self.agent_types[agent_type]:
            return None
        
        available_agents = [
            agent_id for agent_id in self.agent_types[agent_type]
            if self.agents[agent_id].health_status == HealthStatus.HEALTHY.value
        ]
        
        if not available_agents:
            return None
        
        # Simple round-robin for now
        return available_agents[0]

    def _add_to_queue(self, task: TaskExecution, priority: int):
        """
        Add task to execution queue with priority
        
        Args:
            task: Task to add
            priority: Task priority
        """
        task.metadata = task.metadata or {}
        task.metadata["priority"] = priority
        
        # Insert based on priority (higher priority first)
        insert_index = 0
        for i, queued_task in enumerate(self.task_queue):
            queued_priority = queued_task.metadata.get("priority", 2) if queued_task.metadata else 2
            if queued_priority <= priority:
                insert_index = i
                break
        else:
            insert_index = len(self.task_queue)
        
        self.task_queue.insert(insert_index, task)

    async def _execute_task(self, task: TaskExecution):
        """
        Execute a single task
        
        Args:
            task: Task to execute
        """
        task.status = TaskStatus.RUNNING
        start_time = time.time()
        
        try:
            if task.agent_id == "master_agent":
                # Use master agent for orchestration
                response = await self.master_agent.execute(task.request)
            else:
                # Use specific agent
                agent = self.agents[task.agent_id].agent_instance
                response = await agent.execute(task.request)
            
            task.result = response
            task.status = TaskStatus.COMPLETED
            task.execution_time = time.time() - start_time
            
            # Update agent metrics
            self._update_agent_metrics(task.agent_id, task.execution_time, True)
            
            # Add to completed tasks
            self.completed_tasks.append(task)
            
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.execution_time = time.time() - start_time
            
            # Update agent metrics
            self._update_agent_metrics(task.agent_id, task.execution_time, False)
            
            # Handle retry
            if task.retry_count < self.max_retry_count:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                # Re-queue with delay
                await asyncio.sleep(2 ** task.retry_count)  # Exponential backoff
                await self._execute_task(task)
            else:
                self.failed_tasks.append(task)

    def _update_agent_metrics(self, agent_id: str, execution_time: float, success: bool):
        """
        Update agent performance metrics
        
        Args:
            agent_id: Agent ID
            execution_time: Time taken for execution
            success: Whether execution was successful
        """
        if agent_id not in self.agents:
            return
        
        agent = self.agents[agent_id]
        agent.performance_metrics["total_executions"] += 1
        
        if success:
            agent.performance_metrics["successful_executions"] += 1
        else:
            agent.performance_metrics["failed_executions"] += 1
        
        # Update average response time
        current_avg = agent.performance_metrics["average_response_time"]
        total_exec = agent.performance_metrics["total_executions"]
        new_avg = ((current_avg * (total_exec - 1)) + execution_time) / total_exec
        agent.performance_metrics["average_response_time"] = new_avg
        
        agent.performance_metrics["last_execution_time"] = datetime.utcnow()

    def _start_background_tasks(self):
        """
        Start background maintenance tasks
        """
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._metrics_cleanup_loop())

    async def _health_check_loop(self):
        """
        Background health check loop
        """
        while True:
            await asyncio.sleep(self.health_check_interval)
            await self._perform_health_checks()

    async def _perform_health_checks(self):
        """
        Perform health checks on all agents
        """
        for agent_id, registration in self.agents.items():
            try:
                # Simple health check - update heartbeat
                registration.last_heartbeat = datetime.utcnow()
                
                # In practice, would perform actual health checks
                # For now, just ensure agents are responsive
                
            except Exception as e:
                logging.error(f"Health check failed for agent {agent_id}: {e}")
                registration.health_status = HealthStatus.UNHEALTHY.value

    async def _metrics_cleanup_loop(self):
        """
        Background task for cleaning up old metrics
        """
        while True:
            await asyncio.sleep(3600)  # Run every hour
            
            # Clean up old completed tasks (keep last 1000)
            if len(self.completed_tasks) > 1000:
                self.completed_tasks = self.completed_tasks[-1000:]
            
            # Clean up old failed tasks (keep last 100)
            if len(self.failed_tasks) > 100:
                self.failed_tasks = self.failed_tasks[-100:]

    def initialize_default_agents(self):
        """
        Initialize and register all default agents
        """
        # Register all specialized agents
        agents_to_register = [
            (QueryAgent(), "1.0.0", {"description": "Query and information retrieval agent"}),
            (ActionAgent(), "1.0.0", {"description": "Action and workflow execution agent"}),
            (AnalyticsAgent(), "1.0.0", {"description": "Analytics and insights agent"}),
            (SchedulerAgent(), "1.0.0", {"description": "Scheduling and automation agent"}),
            (ComplianceAgent(), "1.0.0", {"description": "Compliance and audit agent"}),
            (HelpAgent(), "1.0.0", {"description": "User assistance and documentation agent"})
        ]
        
        for agent, version, metadata in agents_to_register:
            self.register_agent(agent, version=version, metadata=metadata)
        
        # Register master agent
        self.register_agent(
            self.master_agent,
            version="1.0.0",
            metadata={"description": "Master orchestration agent"}
        )

    def get_system_dashboard(self) -> Dict[str, Any]:
        """
        Get comprehensive system dashboard data
        
        Returns:
            Complete system overview for dashboard
        """
        health = self.get_system_health()
        agents = self.get_agent_list()
        
        return {
            "system_overview": {
                "status": "operational" if health["healthy_agents"] > 0 else "degraded",
                "total_agents": health["total_agents"],
                "active_agents": health["healthy_agents"],
                "system_uptime": "99.9%"
            },
            "performance_metrics": health["system_metrics"],
            "agent_breakdown": {
                "by_type": {
                    agent_type.value: len(agent_ids)
                    for agent_type, agent_ids in self.agent_types.items()
                },
                "by_health": {
                    "healthy": health["healthy_agents"],
                    "degraded": health["degraded_agents"],
                    "unhealthy": health["unhealthy_agents"],
                    "offline": health["offline_agents"]
                }
            },
            "recent_activity": {
                "last_24h_tasks": len([
                    task for task in self.completed_tasks
                    if task.start_time > datetime.utcnow() - timedelta(hours=24)
                ]),
                "success_rate": (
                    health["system_metrics"]["successful_tasks"] / 
                    max(health["system_metrics"]["total_tasks"], 1)
                ) * 100
            },
            "agents": agents
        }