"""
Background Task Service

Handles async task processing for reports, charts, forecasts, and analytics.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import uuid

from app.services.kafka_service import kafka_service
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Task type enum"""
    REPORT_GENERATION = "report_generation"
    CHART_GENERATION = "chart_generation"
    FORECAST_CALCULATION = "forecast_calculation"
    DATA_ANALYSIS = "data_analysis"
    BULK_EXPORT = "bulk_export"


class BackgroundTaskService:
    """Service for managing background tasks"""
    
    def __init__(self):
        self.task_handlers: Dict[str, Callable] = {}
        self.redis_client = None
        
    async def initialize(self):
        """Initialize background task service"""
        self.redis_client = await get_redis_client()
        
        # Register task handlers
        self.register_handler(TaskType.REPORT_GENERATION, self._handle_report_generation)
        self.register_handler(TaskType.CHART_GENERATION, self._handle_chart_generation)
        self.register_handler(TaskType.FORECAST_CALCULATION, self._handle_forecast_calculation)
        self.register_handler(TaskType.DATA_ANALYSIS, self._handle_data_analysis)
        self.register_handler(TaskType.BULK_EXPORT, self._handle_bulk_export)
        
        # Start Kafka consumer for tasks
        await kafka_service.create_consumer(
            topic='ai-copilot-tasks',
            group_id='ai-copilot-task-workers',
            handler=self._process_task_event
        )
        
        logger.info("Background task service initialized")
    
    def register_handler(self, task_type: TaskType, handler: Callable):
        """Register a task handler"""
        self.task_handlers[task_type] = handler
        
    async def create_task(self, task_type: TaskType, user_id: str, 
                         organization_id: str, parameters: Dict[str, Any]) -> str:
        """
        Create a new background task with org isolation
        
        Args:
            task_type: Type of task to create
            user_id: User who created the task
            organization_id: Organization ID for isolation
            parameters: Task parameters
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        
        task_data = {
            'task_id': task_id,
            'task_type': task_type,
            'user_id': user_id,
            'organization_id': organization_id,  # Add org_id
            'parameters': parameters,
            'status': TaskStatus.PENDING,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Store task in Redis
        await self._store_task(task_id, task_data)
        
        # Send task event to Kafka
        await kafka_service.send_task_event(
            task_id=task_id,
            event_type='task_created',
            task_data=task_data
        )
        
        logger.info(f"Created background task: {task_id} ({task_type})")
        return task_id
    
    async def get_task_status(self, task_id: str, organization_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get task status and result with org validation"""
        if not self.redis_client:
            return None
        
        # If org_id provided, use it; otherwise try to extract from context
        if organization_id:
            task_key = f"task:{organization_id}:{task_id}"
        else:
            # Try default for backward compatibility (should be removed in production)
            task_key = f"task:default:{task_id}"
            
        task_data = await self.redis_client.get(task_key)
        
        if task_data:
            import json
            task = json.loads(task_data)
            
            # Validate org_id if provided
            if organization_id and task.get('organization_id') != organization_id:
                logger.warning(f"Org mismatch for task {task_id}: expected {organization_id}, got {task.get('organization_id')}")
                return None
                
            return task
        return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or processing task"""
        task = await self.get_task_status(task_id)
        
        if not task:
            return False
            
        if task['status'] in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False
            
        task['status'] = TaskStatus.CANCELLED
        task['updated_at'] = datetime.utcnow().isoformat()
        
        await self._store_task(task_id, task)
        
        await kafka_service.send_task_event(
            task_id=task_id,
            event_type='task_cancelled',
            task_data=task
        )
        
        return True
    
    async def _store_task(self, task_id: str, task_data: Dict[str, Any]):
        """Store task data in Redis with org isolation"""
        if not self.redis_client:
            return
            
        import json
        # Include org_id in key for isolation
        org_id = task_data.get('organization_id', 'default')
        task_key = f"task:{org_id}:{task_id}"
        await self.redis_client.setex(
            task_key,
            86400,  # 24 hours TTL
            json.dumps(task_data)
        )
    
    async def _process_task_event(self, event: Dict[str, Any]):
        """Process task event from Kafka"""
        event_type = event.get('event_type')
        data = event.get('data', {})
        task_id = data.get('task_id')
        
        if event_type == 'task_created':
            # Process the task
            await self._execute_task(task_id)
    
    async def _execute_task(self, task_id: str):
        """Execute a background task"""
        task = await self.get_task_status(task_id)
        
        if not task:
            logger.error(f"Task not found: {task_id}")
            return
            
        if task['status'] == TaskStatus.CANCELLED:
            logger.info(f"Task cancelled: {task_id}")
            return
            
        # Update status to processing
        task['status'] = TaskStatus.PROCESSING
        task['updated_at'] = datetime.utcnow().isoformat()
        await self._store_task(task_id, task)
        
        try:
            # Get handler for task type
            task_type = task['task_type']
            handler = self.task_handlers.get(task_type)
            
            if not handler:
                raise ValueError(f"No handler for task type: {task_type}")
            
            # Execute handler
            result = await handler(task)
            
            # Update task with result
            task['status'] = TaskStatus.COMPLETED
            task['result'] = result
            task['completed_at'] = datetime.utcnow().isoformat()
            task['updated_at'] = datetime.utcnow().isoformat()
            
            await self._store_task(task_id, task)
            
            # Send completion event
            await kafka_service.send_task_event(
                task_id=task_id,
                event_type='task_completed',
                task_data=task
            )
            
            # Send notification to user
            await kafka_service.send_notification_event(
                user_id=task['user_id'],
                notification={
                    'type': 'task_completed',
                    'task_id': task_id,
                    'task_type': task_type,
                    'result': result
                }
            )
            
            logger.info(f"Task completed: {task_id}")
            
        except Exception as e:
            logger.error(f"Task failed: {task_id} - {e}")
            
            task['status'] = TaskStatus.FAILED
            task['error'] = str(e)
            task['updated_at'] = datetime.utcnow().isoformat()
            
            await self._store_task(task_id, task)
            
            await kafka_service.send_task_event(
                task_id=task_id,
                event_type='task_failed',
                task_data=task
            )
    
    # Task Handlers
    
    async def _handle_report_generation(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle report generation task"""
        parameters = task['parameters']
        report_type = parameters.get('report_type', 'sales')
        date_range = parameters.get('date_range', {})
        
        # Simulate report generation
        await asyncio.sleep(2)  # Simulate processing time
        
        return {
            'type': 'report',
            'report_type': report_type,
            'format': 'pdf',
            'download_url': f'/api/v1/reports/download/{task["task_id"]}',
            'file_size': '2.5 MB',
            'pages': 15
        }
    
    async def _handle_chart_generation(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chart generation task"""
        parameters = task['parameters']
        chart_type = parameters.get('chart_type', 'line')
        data_source = parameters.get('data_source', 'sales')
        
        # Simulate chart generation
        await asyncio.sleep(1)
        
        return {
            'type': 'chart',
            'chart_type': chart_type,
            'data': {
                'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                'datasets': [{
                    'label': 'Sales',
                    'data': [12000, 19000, 15000, 25000, 22000, 30000]
                }]
            },
            'image_url': f'/api/v1/charts/{task["task_id"]}.png'
        }
    
    async def _handle_forecast_calculation(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle forecast calculation task"""
        parameters = task['parameters']
        metric = parameters.get('metric', 'revenue')
        periods = parameters.get('periods', 3)
        
        # Simulate forecast calculation
        await asyncio.sleep(3)
        
        return {
            'type': 'forecast',
            'metric': metric,
            'periods': periods,
            'predictions': [
                {'period': 'Q1 2024', 'value': 125000, 'confidence': 0.85},
                {'period': 'Q2 2024', 'value': 135000, 'confidence': 0.78},
                {'period': 'Q3 2024', 'value': 145000, 'confidence': 0.72}
            ],
            'chart_data': {
                'type': 'line',
                'labels': ['Q4 2023', 'Q1 2024', 'Q2 2024', 'Q3 2024'],
                'datasets': [
                    {'label': 'Actual', 'data': [115000, None, None, None]},
                    {'label': 'Forecast', 'data': [None, 125000, 135000, 145000]}
                ]
            }
        }
    
    async def _handle_data_analysis(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data analysis task"""
        parameters = task['parameters']
        analysis_type = parameters.get('analysis_type', 'sales_patterns')
        
        # Simulate data analysis
        await asyncio.sleep(4)
        
        return {
            'type': 'analysis',
            'analysis_type': analysis_type,
            'insights': [
                'Sales peak on Fridays (avg +35%)',
                'Top product category: Electronics (42% of revenue)',
                'Customer retention rate: 78%',
                'Average order value increased by 12% this quarter'
            ],
            'charts': [
                {'type': 'bar', 'title': 'Sales by Day of Week'},
                {'type': 'pie', 'title': 'Revenue by Category'}
            ]
        }
    
    async def _handle_bulk_export(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle bulk export task"""
        parameters = task['parameters']
        export_type = parameters.get('export_type', 'customers')
        format_type = parameters.get('format', 'csv')
        
        # Simulate bulk export
        await asyncio.sleep(5)
        
        return {
            'type': 'export',
            'export_type': export_type,
            'format': format_type,
            'download_url': f'/api/v1/exports/download/{task["task_id"]}.{format_type}',
            'record_count': 15420,
            'file_size': '8.3 MB'
        }


# Global instance
background_task_service = BackgroundTaskService()
