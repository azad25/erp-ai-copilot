"""
Agent Task Worker

Main worker process that consumes tasks and executes them using MCP.
Integrates task consumer, MCP client, and state management.
"""

import asyncio
import structlog
from typing import Dict, Any

logger = structlog.get_logger(__name__)


class AgentTaskWorker:
    """
    Main worker for executing agent tasks
    
    Consumes tasks from Kafka and executes them using MCP client.
    """
    
    def __init__(self):
        """Initialize agent task worker"""
        self.task_consumer = None
        self.mcp_client = None
        self.state_manager = None
    
    async def initialize(self):
        """Initialize worker components"""
        from app.services.task_consumer import get_task_consumer
        from mcp.client import get_mcp_client
        from app.services.task_state_manager import get_task_state_manager
        
        # Initialize components
        self.task_consumer = get_task_consumer()
        self.mcp_client = await get_mcp_client()
        self.state_manager = await get_task_state_manager()
        
        # Set task handler
        self.task_consumer.set_task_handler(self.execute_task)
        
        logger.info("Agent task worker initialized")
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single task
        
        Args:
            task: Task data from Kafka
            
        Returns:
            Execution result
        """
        task_id = task['task_id']
        agent_id = task['agent_id']
        organization_id = task['organization_id']
        
        logger.info(
            "Executing task",
            task_id=task_id,
            agent_id=agent_id,
            task_type=task['task_type']
        )
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Create task in database
            await self.state_manager.create_task(task)
            
            # Update status to running
            await self.state_manager.update_task_status(task_id, "running")
            
            # Build task description for MCP
            task_description = self._build_task_description(task)
            
            # Execute using MCP
            result = await self.mcp_client.execute_with_mcp(
                task_description=task_description,
                user_context={
                    "agent_id": agent_id,
                    "organization_id": organization_id,
                    "task_id": task_id,
                    "parameters": task.get('parameters', {})
                },
                agent_id=agent_id
            )
            
            # Calculate execution time
            execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            # Update task as completed
            await self.state_manager.update_task_status(
                task_id,
                "completed",
                result=result,
                execution_time_ms=execution_time_ms,
                tokens_used=result.get('tokens_used', 0),
                tools_called=result.get('tools_called', []),
                code_generated=result.get('code_generated')
            )
            
            logger.info(
                "Task completed successfully",
                task_id=task_id,
                execution_time_ms=execution_time_ms
            )
            
            return {
                "success": True,
                "result": result,
                "execution_time_ms": execution_time_ms
            }
            
        except Exception as e:
            execution_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            logger.error(
                "Task execution failed",
                task_id=task_id,
                error=str(e),
                execution_time_ms=execution_time_ms
            )
            
            # Update task as failed
            await self.state_manager.update_task_status(
                task_id,
                "failed",
                error_message=str(e),
                execution_time_ms=execution_time_ms
            )
            
            return {
                "success": False,
                "error": str(e),
                "execution_time_ms": execution_time_ms
            }
    
    def _build_task_description(self, task: Dict[str, Any]) -> str:
        """
        Build natural language task description for MCP
        
        Args:
            task: Task data
            
        Returns:
            Task description string
        """
        description_parts = []
        
        # Task name/type
        if task.get('task_name'):
            description_parts.append(f"Task: {task['task_name']}")
        else:
            description_parts.append(f"Task type: {task['task_type']}")
        
        # Description
        if task.get('description'):
            description_parts.append(f"Description: {task['description']}")
        
        # Instructions
        if task.get('instructions'):
            description_parts.append(f"Instructions: {task['instructions']}")
        
        # Parameters
        if task.get('parameters'):
            description_parts.append(f"Parameters: {task['parameters']}")
        
        # Context
        if task.get('context'):
            description_parts.append(f"Context: {task['context']}")
        
        return "\n".join(description_parts)
    
    async def start(self):
        """Start the worker"""
        await self.initialize()
        
        logger.info("Starting agent task worker...")
        
        # Start consuming tasks
        await self.task_consumer.start_consuming()
    
    def stop(self):
        """Stop the worker"""
        if self.task_consumer:
            self.task_consumer.stop()
        
        logger.info("Agent task worker stopped")


async def main():
    """Main entry point for worker process"""
    worker = AgentTaskWorker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        worker.stop()
    except Exception as e:
        logger.error("Worker error", error=str(e))
        raise


if __name__ == "__main__":
    # Run worker
    asyncio.run(main())
