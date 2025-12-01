"""
Task Producer Service

Publishes agent tasks to Kafka for distributed processing.
Handles task validation, priority assignment, and scheduling.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import uuid
import json
import structlog
from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = structlog.get_logger(__name__)


class TaskProducer:
    """
    Kafka-based task producer for agent system
    
    Publishes tasks to appropriate Kafka topics based on priority
    and handles task scheduling, validation, and deduplication.
    """
    
    def __init__(self, bootstrap_servers: List[str] = None):
        """
        Initialize task producer
        
        Args:
            bootstrap_servers: List of Kafka broker addresses
        """
        self.bootstrap_servers = bootstrap_servers or ['localhost:9092']
        self.producer = None
        self._initialize_producer()
        
    def _initialize_producer(self):
        """Initialize Kafka producer with configuration"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',  # Wait for all replicas
                retries=3,
                max_in_flight_requests_per_connection=1,  # Ensure ordering
                compression_type='snappy'
            )
            logger.info("Task producer initialized", servers=self.bootstrap_servers)
        except Exception as e:
            logger.error("Failed to initialize task producer", error=str(e))
            raise
    
    async def submit_task(
        self,
        agent_id: str,
        organization_id: str,
        task_type: str,
        parameters: Dict[str, Any],
        priority: str = "normal",
        scheduled_for: Optional[datetime] = None,
        deadline: Optional[datetime] = None,
        assigned_by: Optional[str] = None,
        task_name: Optional[str] = None,
        description: Optional[str] = None,
        instructions: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        depends_on: Optional[List[str]] = None,
        recurrence_rule: Optional[str] = None
    ) -> str:
        """
        Submit task to Kafka queue
        
        Args:
            agent_id: Target agent ID
            organization_id: Organization ID
            task_type: Type of task
            parameters: Task parameters
            priority: Task priority (critical, high, normal, low)
            scheduled_for: When to execute (None = immediate)
            deadline: Task deadline
            assigned_by: User who assigned the task
            task_name: Human-readable task name
            description: Task description
            instructions: Detailed instructions
            context: Additional context data
            depends_on: List of task IDs this depends on
            recurrence_rule: Cron expression for recurring tasks
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        
        # Validate task
        self._validate_task(agent_id, organization_id, task_type, parameters)
        
        # Calculate priority score
        priority_score = self._calculate_priority_score(
            priority=priority,
            deadline=deadline,
            depends_on=depends_on
        )
        
        # Build task message
        task_message = {
            "task_id": task_id,
            "agent_id": agent_id,
            "organization_id": organization_id,
            "task_type": task_type,
            "task_name": task_name or f"{task_type}_{task_id[:8]}",
            "description": description,
            "instructions": instructions,
            "parameters": parameters,
            "context": context or {},
            "priority": priority,
            "priority_score": priority_score,
            "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
            "deadline": deadline.isoformat() if deadline else None,
            "assigned_by": assigned_by,
            "depends_on": depends_on or [],
            "recurrence_rule": recurrence_rule,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "retry_count": 0,
            "max_retries": 3
        }
        
        # Determine topic based on scheduling
        if scheduled_for and scheduled_for > datetime.utcnow():
            # Scheduled task - will be moved to pending later
            topic = "agent.tasks.scheduled"
            logger.info(
                "Scheduling task",
                task_id=task_id,
                agent_id=agent_id,
                scheduled_for=scheduled_for.isoformat()
            )
        else:
            # Immediate task
            topic = "agent.tasks.pending"
            logger.info(
                "Submitting task",
                task_id=task_id,
                agent_id=agent_id,
                task_type=task_type,
                priority=priority
            )
        
        # Publish to Kafka
        try:
            # Use agent_id as key for partitioning
            future = self.producer.send(
                topic=topic,
                key=agent_id,
                value=task_message,
                partition=self._get_partition(priority)
            )
            
            # Wait for confirmation
            record_metadata = future.get(timeout=10)
            
            logger.info(
                "Task published to Kafka",
                task_id=task_id,
                topic=record_metadata.topic,
                partition=record_metadata.partition,
                offset=record_metadata.offset
            )
            
            return task_id
            
        except KafkaError as e:
            logger.error(
                "Failed to publish task to Kafka",
                task_id=task_id,
                error=str(e)
            )
            raise
    
    def _validate_task(
        self,
        agent_id: str,
        organization_id: str,
        task_type: str,
        parameters: Dict[str, Any]
    ):
        """Validate task before submission"""
        if not agent_id:
            raise ValueError("agent_id is required")
        
        if not organization_id:
            raise ValueError("organization_id is required")
        
        if not task_type:
            raise ValueError("task_type is required")
        
        if not isinstance(parameters, dict):
            raise ValueError("parameters must be a dictionary")
        
        # Check for duplicate task (basic deduplication)
        # TODO: Implement Redis-based deduplication
    
    def _calculate_priority_score(
        self,
        priority: str,
        deadline: Optional[datetime],
        depends_on: Optional[List[str]]
    ) -> int:
        """
        Calculate numeric priority score (0-100)
        
        Higher score = higher priority
        """
        score = 0
        
        # Base priority
        priority_map = {
            'critical': 40,
            'high': 30,
            'normal': 20,
            'low': 10
        }
        score += priority_map.get(priority, 20)
        
        # Urgency based on deadline
        if deadline:
            hours_until_deadline = (deadline - datetime.utcnow()).total_seconds() / 3600
            if hours_until_deadline < 1:
                score += 30  # Critical - less than 1 hour
            elif hours_until_deadline < 24:
                score += 25  # High urgency
            elif hours_until_deadline < 168:
                score += 15  # Medium urgency
            else:
                score += 5   # Low urgency
        
        # Blocking other tasks
        if depends_on:
            score += min(len(depends_on) * 5, 20)
        
        return min(score, 100)
    
    def _get_partition(self, priority: str) -> Optional[int]:
        """
        Get partition based on priority
        
        Partition 0: Critical/High priority
        Partition 1: Normal priority
        Partition 2: Low priority
        """
        if priority in ['critical', 'high']:
            return 0
        elif priority == 'normal':
            return 1
        else:
            return 2
    
    async def cancel_task(self, task_id: str, reason: str = "Cancelled by user"):
        """
        Cancel a pending task
        
        Args:
            task_id: Task ID to cancel
            reason: Cancellation reason
        """
        cancel_message = {
            "task_id": task_id,
            "action": "cancel",
            "reason": reason,
            "cancelled_at": datetime.utcnow().isoformat()
        }
        
        try:
            self.producer.send(
                topic="agent.tasks.control",
                value=cancel_message
            )
            logger.info("Task cancellation requested", task_id=task_id)
        except KafkaError as e:
            logger.error("Failed to cancel task", task_id=task_id, error=str(e))
            raise
    
    async def update_task_priority(self, task_id: str, new_priority: str):
        """
        Update priority of a pending task
        
        Args:
            task_id: Task ID
            new_priority: New priority level
        """
        update_message = {
            "task_id": task_id,
            "action": "update_priority",
            "new_priority": new_priority,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        try:
            self.producer.send(
                topic="agent.tasks.control",
                value=update_message
            )
            logger.info(
                "Task priority update requested",
                task_id=task_id,
                new_priority=new_priority
            )
        except KafkaError as e:
            logger.error("Failed to update task priority", task_id=task_id, error=str(e))
            raise
    
    def close(self):
        """Close Kafka producer"""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("Task producer closed")


# Global instance
_task_producer: Optional[TaskProducer] = None


def get_task_producer() -> TaskProducer:
    """Get or create task producer instance"""
    global _task_producer
    
    if _task_producer is None:
        _task_producer = TaskProducer()
    
    return _task_producer
