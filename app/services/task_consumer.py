"""
Task Consumer Service

Consumes agent tasks from Kafka and executes them using MCP.
Implements parallel processing, error handling, and retry logic.
"""

from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import asyncio
import json
import structlog
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import signal
import sys

logger = structlog.get_logger(__name__)


class TaskConsumer:
    """
    Kafka-based task consumer for agent system
    
    Consumes tasks from Kafka topics and executes them using agents.
    Supports parallel processing, graceful shutdown, and error recovery.
    """
    
    def __init__(
        self,
        bootstrap_servers: List[str] = None,
        group_id: str = "agent-workers",
        max_workers: int = 10
    ):
        """
        Initialize task consumer
        
        Args:
            bootstrap_servers: List of Kafka broker addresses
            group_id: Consumer group ID
            max_workers: Maximum parallel workers
        """
        self.bootstrap_servers = bootstrap_servers or ['localhost:9092']
        self.group_id = group_id
        self.max_workers = max_workers
        self.consumer = None
        self.running = False
        self.worker_pool = []
        self.task_handler: Optional[Callable] = None
        
    def _initialize_consumer(self):
        """Initialize Kafka consumer with configuration"""
        try:
            self.consumer = KafkaConsumer(
                'agent.tasks.pending',
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='earliest',
                enable_auto_commit=False,  # Manual commit for reliability
                max_poll_records=self.max_workers,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            logger.info(
                "Task consumer initialized",
                group_id=self.group_id,
                servers=self.bootstrap_servers
            )
        except Exception as e:
            logger.error("Failed to initialize task consumer", error=str(e))
            raise
    
    def set_task_handler(self, handler: Callable):
        """
        Set the task execution handler
        
        Args:
            handler: Async function that executes tasks
                     Signature: async def handler(task: Dict) -> Dict
        """
        self.task_handler = handler
        logger.info("Task handler registered")
    
    async def start_consuming(self):
        """
        Start consuming tasks from Kafka
        
        This is the main consumer loop that:
        1. Polls for messages
        2. Distributes to worker pool
        3. Handles errors and retries
        4. Commits offsets
        """
        if not self.task_handler:
            raise RuntimeError("Task handler not set. Call set_task_handler() first.")
        
        self._initialize_consumer()
        self.running = True
        
        # Setup graceful shutdown
        self._setup_signal_handlers()
        
        logger.info("Starting task consumption", max_workers=self.max_workers)
        
        try:
            while self.running:
                # Poll for messages
                message_batch = self.consumer.poll(timeout_ms=1000)
                
                if not message_batch:
                    await asyncio.sleep(0.1)
                    continue
                
                # Process messages in parallel
                tasks = []
                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        task = asyncio.create_task(
                            self._process_message(message)
                        )
                        tasks.append(task)
                
                # Wait for all tasks to complete
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Commit offsets after successful processing
                    try:
                        self.consumer.commit()
                    except KafkaError as e:
                        logger.error("Failed to commit offsets", error=str(e))
                
        except Exception as e:
            logger.error("Consumer error", error=str(e))
            raise
        finally:
            await self._shutdown()
    
    async def _process_message(self, message):
        """
        Process a single Kafka message
        
        Args:
            message: Kafka message containing task data
        """
        task = message.value
        task_id = task.get('task_id')
        agent_id = task.get('agent_id')
        
        logger.info(
            "Processing task",
            task_id=task_id,
            agent_id=agent_id,
            task_type=task.get('task_type'),
            partition=message.partition,
            offset=message.offset
        )
        
        try:
            # Update task status to running
            await self._update_task_status(task_id, "running")
            
            # Execute task using handler
            result = await self.task_handler(task)
            
            # Publish result
            await self._publish_result(task, result, success=True)
            
            logger.info(
                "Task completed successfully",
                task_id=task_id,
                agent_id=agent_id
            )
            
        except Exception as e:
            logger.error(
                "Task execution failed",
                task_id=task_id,
                agent_id=agent_id,
                error=str(e)
            )
            
            # Handle retry logic
            await self._handle_task_failure(task, str(e))
    
    async def _update_task_status(self, task_id: str, status: str):
        """
        Update task status in database
        
        Args:
            task_id: Task ID
            status: New status
        """
        # TODO: Implement database update
        # For now, publish status update to Kafka
        from app.services.task_producer import get_task_producer
        
        producer = get_task_producer()
        status_message = {
            "task_id": task_id,
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        producer.producer.send(
            topic="agent.tasks.running" if status == "running" else "agent.status.updates",
            value=status_message
        )
    
    async def _publish_result(self, task: Dict, result: Dict, success: bool):
        """
        Publish task result to Kafka
        
        Args:
            task: Original task
            result: Execution result
            success: Whether task succeeded
        """
        from app.services.task_producer import get_task_producer
        
        producer = get_task_producer()
        
        result_message = {
            "task_id": task['task_id'],
            "agent_id": task['agent_id'],
            "organization_id": task['organization_id'],
            "task_type": task['task_type'],
            "success": success,
            "result": result,
            "completed_at": datetime.utcnow().isoformat(),
            "execution_time_ms": result.get('execution_time_ms', 0)
        }
        
        topic = "agent.tasks.completed" if success else "agent.tasks.failed"
        
        producer.producer.send(
            topic=topic,
            key=task['agent_id'],
            value=result_message
        )
        
        logger.info(
            "Task result published",
            task_id=task['task_id'],
            topic=topic,
            success=success
        )
    
    async def _handle_task_failure(self, task: Dict, error: str):
        """
        Handle task failure with retry logic
        
        Args:
            task: Failed task
            error: Error message
        """
        task_id = task['task_id']
        retry_count = task.get('retry_count', 0)
        max_retries = task.get('max_retries', 3)
        
        if retry_count < max_retries:
            # Retry task
            logger.info(
                "Retrying task",
                task_id=task_id,
                retry_count=retry_count + 1,
                max_retries=max_retries
            )
            
            from app.services.task_producer import get_task_producer
            producer = get_task_producer()
            
            # Update retry count
            task['retry_count'] = retry_count + 1
            task['last_error'] = error
            
            # Republish to pending queue
            producer.producer.send(
                topic="agent.tasks.pending",
                key=task['agent_id'],
                value=task
            )
        else:
            # Max retries exceeded, mark as failed
            logger.error(
                "Task failed after max retries",
                task_id=task_id,
                retry_count=retry_count
            )
            
            await self._publish_result(
                task,
                {"error": error, "retry_count": retry_count},
                success=False
            )
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown on SIGINT and SIGTERM"""
        def signal_handler(signum, frame):
            logger.info("Shutdown signal received", signal=signum)
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down task consumer...")
        
        # Wait for in-flight tasks to complete
        if self.worker_pool:
            logger.info("Waiting for in-flight tasks to complete...")
            await asyncio.gather(*self.worker_pool, return_exceptions=True)
        
        # Close consumer
        if self.consumer:
            self.consumer.close()
            logger.info("Consumer closed")
        
        logger.info("Task consumer shutdown complete")
    
    def stop(self):
        """Stop consuming tasks"""
        self.running = False


# Global instance
_task_consumer: Optional[TaskConsumer] = None


def get_task_consumer() -> TaskConsumer:
    """Get or create task consumer instance"""
    global _task_consumer
    
    if _task_consumer is None:
        _task_consumer = TaskConsumer()
    
    return _task_consumer
