"""
Background Job Processing Service

Handles scheduled tasks, file monitoring, and background processing
for AI Copilot operations including knowledge base updates and chat processing.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import json
import hashlib
from uuid import uuid4

from app.database.connection import get_mongodb, get_redis
from app.services.kafka_integration_service import kafka_service as kafka_integration

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    """Job priority levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class BackgroundJob:
    """Background job definition"""
    job_id: str
    job_type: str
    function_name: str
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: JobPriority = JobPriority.MEDIUM
    status: JobStatus = JobStatus.PENDING
    scheduled_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)


class BackgroundJobService:
    """
    Background Job Processing Service
    
    Features:
    - Async job queue with priority handling
    - File system monitoring for docs folder
    - Scheduled knowledge base updates
    - Background chat processing optimization
    - Retry logic and error handling
    - Job persistence in MongoDB
    """
    
    # Add JobPriority as class attribute for external access
    JobPriority = JobPriority
    
    def __init__(self):
        self.job_queue: asyncio.Queue = asyncio.Queue()
        self.running_jobs: Dict[str, BackgroundJob] = {}
        self.job_registry: Dict[str, Callable] = {}
        self.worker_tasks: List[asyncio.Task] = []
        self.file_watchers: Dict[str, asyncio.Task] = {}
        self.is_running = False
        self.max_workers = 5
        
        # Register job handlers
        self._register_job_handlers()
    
    def _register_job_handlers(self):
        """Register available job handlers"""
        from app.services.knowledge_base_initialization_service import knowledge_base_init_service
        from app.services.memory_service import memory_service
        from app.services.service_discovery_service import service_discovery
        
        self.job_registry = {
            "process_new_documentation": self._process_new_documentation,
            "refresh_knowledge_base": knowledge_base_init_service.refresh_knowledge_base,
            "cleanup_expired_memories": memory_service.cleanup_expired_memories,
            "update_service_discovery": service_discovery.refresh_services,
            "process_kafka_events": self._process_kafka_events,
            "optimize_chat_context": self._optimize_chat_context,
            "sync_erp_documentation": self._sync_erp_documentation
        }
    
    async def start(self):
        """Start background job workers"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info(f"Starting {self.max_workers} background job workers")
        
        # Start worker tasks
        for i in range(self.max_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_tasks.append(task)
        
        # Start file monitoring
        await self._start_file_monitoring()
        
        logger.info("Background job service started successfully")
        await self._schedule_periodic_tasks()
        
        logger.info(f"Background job service started with {self.max_workers} workers")
    
    async def process_jobs(self):
        """Process jobs in the queue"""
        try:
            while self.is_running:
                # Get next job from queue
                job = await self._get_next_job()
                if not job:
                    await asyncio.sleep(1)
                    continue
                
                # Execute job
                await self._execute_job(job)
                
        except Exception as e:
            logger.error(f"Error in job processing: {e}")

    async def stop(self):
        """Stop background job processing"""
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("Stopping background job service")
        
        # Cancel worker tasks
        for task in self.worker_tasks:
            task.cancel()
        
        # Cancel file watchers
        for watcher in self.file_watchers.values():
            watcher.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        await asyncio.gather(*self.file_watchers.values(), return_exceptions=True)
        
        logger.info("Background job service stopped")
    
    async def _worker(self, worker_name: str):
        """Background job worker"""
        logger.info(f"Worker {worker_name} started")
        
        while self.is_running:
            try:
                # Get job from queue with timeout
                job = await asyncio.wait_for(self.job_queue.get(), timeout=1.0)
                
                if job.job_id in self.running_jobs:
                    continue  # Job already running
                
                # Execute job
                await self._execute_job(job, worker_name)
                
            except asyncio.TimeoutError:
                continue  # No jobs in queue, continue polling
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Worker {worker_name} stopped")
    
    async def _execute_job(self, job: BackgroundJob, worker_name: str):
        """Execute a background job"""
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        self.running_jobs[job.job_id] = job
        
        logger.info(f"Worker {worker_name} executing job {job.job_id}: {job.job_type}")
        
        try:
            # Get job handler
            handler = self.job_registry.get(job.function_name)
            if not handler:
                raise ValueError(f"Unknown job function: {job.function_name}")
            
            # Execute with timeout
            await asyncio.wait_for(
                handler(*job.args, **job.kwargs),
                timeout=job.timeout_seconds
            )
            
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            logger.info(f"Job {job.job_id} completed successfully")
            
        except asyncio.TimeoutError:
            job.status = JobStatus.FAILED
            job.error_message = "Job timed out"
            logger.error(f"Job {job.job_id} timed out")
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.retry_count += 1
            
            logger.error(f"Job {job.job_id} failed: {e}")
            
            # Retry if under limit
            if job.retry_count <= job.max_retries:
                job.status = JobStatus.PENDING
                job.scheduled_at = datetime.utcnow() + timedelta(minutes=job.retry_count * 2)
                await self.job_queue.put(job)
                logger.info(f"Job {job.job_id} scheduled for retry {job.retry_count}/{job.max_retries}")
        
        finally:
            # Save job status to MongoDB
            await self._save_job_status(job)
            
            # Remove from running jobs
            if job.job_id in self.running_jobs:
                del self.running_jobs[job.job_id]
    
    async def _start_file_monitoring(self):
        """Start monitoring docs folder for changes"""
        docs_path = Path("/Users/ferdousazad/Documents/erp-suite/erp-ai-copilot/docs")
        
        if docs_path.exists():
            watcher_task = asyncio.create_task(self._monitor_docs_folder(docs_path))
            self.file_watchers["docs_folder"] = watcher_task
            logger.info(f"Started monitoring docs folder: {docs_path}")
    
    async def _monitor_docs_folder(self, docs_path: Path):
        """Monitor docs folder for file changes"""
        last_check = {}
        
        while self.is_running:
            try:
                current_files = {}
                
                # Check all markdown files
                for md_file in docs_path.glob("*.md"):
                    if md_file.is_file():
                        stat = md_file.stat()
                        current_files[str(md_file)] = {
                            "size": stat.st_size,
                            "modified": stat.st_mtime
                        }
                
                # Check for new or modified files
                for file_path, file_info in current_files.items():
                    if file_path not in last_check:
                        # New file detected
                        logger.info(f"New documentation file detected: {file_path}")
                        await self.schedule_job(
                            job_type="process_new_documentation",
                            function_name="process_new_documentation",
                            args=[file_path],
                            priority=JobPriority.MEDIUM
                        )
                    elif file_info["modified"] > last_check[file_path]["modified"]:
                        # Modified file detected
                        logger.info(f"Modified documentation file detected: {file_path}")
                        await self.schedule_job(
                            job_type="process_new_documentation",
                            function_name="process_new_documentation",
                            args=[file_path],
                            priority=JobPriority.MEDIUM
                        )
                
                last_check = current_files
                
                # Check every 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"File monitoring error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _schedule_periodic_tasks(self):
        """Schedule periodic maintenance tasks"""
        # Schedule knowledge base refresh every 6 hours
        await self.schedule_job(
            job_type="refresh_knowledge_base",
            function_name="refresh_knowledge_base",
            priority=JobPriority.LOW,
            metadata={"recurring": True, "interval_hours": 6}
        )
        
        # Schedule memory cleanup every 24 hours
        await self.schedule_job(
            job_type="cleanup_expired_memories",
            function_name="cleanup_expired_memories",
            priority=JobPriority.LOW,
            metadata={"recurring": True, "interval_hours": 24}
        )
        
        # Schedule service discovery update every 2 hours
        await self.schedule_job(
            job_type="update_service_discovery",
            function_name="update_service_discovery",
            priority=JobPriority.MEDIUM,
            metadata={"recurring": True, "interval_hours": 2}
        )
    
    async def schedule_job(
        self,
        job_type: str,
        function_name: str,
        args: List[Any] = None,
        kwargs: Dict[str, Any] = None,
        priority: JobPriority = JobPriority.MEDIUM,
        delay_seconds: int = 0,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Schedule a background job
        
        Args:
            job_type: Type of job
            function_name: Function to execute
            args: Function arguments
            kwargs: Function keyword arguments
            priority: Job priority
            delay_seconds: Delay before execution
            metadata: Additional job metadata
            
        Returns:
            Job ID
        """
        job_id = str(uuid4())
        
        job = BackgroundJob(
            job_id=job_id,
            job_type=job_type,
            function_name=function_name,
            args=args or [],
            kwargs=kwargs or {},
            priority=priority,
            scheduled_at=datetime.utcnow() + timedelta(seconds=delay_seconds),
            metadata=metadata or {}
        )
        
        # Add to queue
        await self.job_queue.put(job)
        
        # Save to MongoDB for persistence
        await self._save_job_status(job)
        
        logger.info(f"Scheduled job {job_id}: {job_type}")
        return job_id
    
    async def _save_job_status(self, job: BackgroundJob):
        """Save job status to MongoDB"""
        try:
            mongodb = await get_mongodb()
            
            job_doc = {
                "job_id": job.job_id,
                "job_type": job.job_type,
                "function_name": job.function_name,
                "args": job.args,
                "kwargs": job.kwargs,
                "priority": job.priority.value,
                "status": job.status.value,
                "scheduled_at": job.scheduled_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "error_message": job.error_message,
                "retry_count": job.retry_count,
                "max_retries": job.max_retries,
                "timeout_seconds": job.timeout_seconds,
                "metadata": job.metadata
            }
            
            await mongodb.background_jobs.update_one(
                {"job_id": job.job_id},
                {"$set": job_doc},
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Failed to save job status: {e}")
    
    async def _process_new_documentation(self, file_path: str):
        """Process new documentation file"""
        try:
            from app.services.knowledge_base_initialization_service import knowledge_base_init_service
            await knowledge_base_init_service.add_new_documentation(file_path)
            logger.info(f"Processed new documentation: {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to process documentation {file_path}: {e}")
            raise
    
    async def _process_kafka_events(self):
        """Process pending Kafka events"""
        try:
            # Process any pending Kafka events
            await kafka_integration.process_pending_events()
            logger.info("Processed pending Kafka events")
            
        except Exception as e:
            logger.error(f"Failed to process Kafka events: {e}")
            raise
    
    async def _optimize_chat_context(self, user_id: str, organization_id: str):
        """Optimize chat context for user"""
        try:
            from app.services.memory_service import memory_service
            
            # Clean up old context
            redis = await get_redis()
            pattern = f"user_context*:{user_id}:{organization_id}:*"
            
            keys = await redis.keys(pattern)
            if keys:
                await redis.delete(*keys)
            
            # Rebuild optimized context
            await memory_service._get_user_context(user_id, organization_id)
            
            logger.info(f"Optimized chat context for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to optimize chat context: {e}")
            raise
    
    async def _sync_erp_documentation(self):
        """Sync ERP documentation from all services"""
        try:
            from app.services.service_discovery_service import service_discovery
            
            # Refresh service discovery
            await service_discovery.refresh_services()
            
            # Update documentation index
            await service_discovery.index_documentation()
            
            logger.info("Synced ERP documentation")
            
        except Exception as e:
            logger.error(f"Failed to sync ERP documentation: {e}")
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        try:
            # Check running jobs first
            if job_id in self.running_jobs:
                job = self.running_jobs[job_id]
                return {
                    "job_id": job.job_id,
                    "status": job.status.value,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "progress": "running"
                }
            
            # Check MongoDB
            mongodb = await get_mongodb()
            job_doc = await mongodb.background_jobs.find_one({"job_id": job_id})
            
            if job_doc:
                return {
                    "job_id": job_doc["job_id"],
                    "job_type": job_doc["job_type"],
                    "status": job_doc["status"],
                    "scheduled_at": job_doc["scheduled_at"].isoformat(),
                    "started_at": job_doc["started_at"].isoformat() if job_doc["started_at"] else None,
                    "completed_at": job_doc["completed_at"].isoformat() if job_doc["completed_at"] else None,
                    "error_message": job_doc.get("error_message"),
                    "retry_count": job_doc.get("retry_count", 0)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            return None
    
    async def get_job_queue_status(self) -> Dict[str, Any]:
        """Get job queue statistics"""
        try:
            mongodb = await get_mongodb()
            
            # Count jobs by status
            pipeline = [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            
            status_counts = {}
            async for doc in mongodb.background_jobs.aggregate(pipeline):
                status_counts[doc["_id"]] = doc["count"]
            
            return {
                "queue_size": self.job_queue.qsize(),
                "running_jobs": len(self.running_jobs),
                "workers": len(self.worker_tasks),
                "status_counts": status_counts,
                "is_running": self.is_running
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}")
            return {"error": str(e)}
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        try:
            # Cancel running job
            if job_id in self.running_jobs:
                job = self.running_jobs[job_id]
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.utcnow()
                await self._save_job_status(job)
                del self.running_jobs[job_id]
                return True
            
            # Cancel queued job
            mongodb = await get_mongodb()
            result = await mongodb.background_jobs.update_one(
                {"job_id": job_id, "status": JobStatus.PENDING.value},
                {"$set": {"status": JobStatus.CANCELLED.value, "completed_at": datetime.utcnow()}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False
    
    async def schedule_chat_processing_job(
        self,
        user_id: str,
        organization_id: str,
        conversation_id: str,
        message: str,
        context: Dict[str, Any]
    ) -> str:
        """Schedule background chat processing job for heavy operations"""
        return await self.schedule_job(
            job_type="optimize_chat_context",
            function_name="optimize_chat_context",
            args=[user_id, organization_id],
            priority=JobPriority.HIGH,
            metadata={
                "conversation_id": conversation_id,
                "message_preview": message[:100],
                "context_size": len(str(context))
            }
        )
    
    async def schedule_knowledge_base_update(self, file_path: str) -> str:
        """Schedule knowledge base update for new file"""
        return await self.schedule_job(
            job_type="process_new_documentation",
            function_name="process_new_documentation",
            args=[file_path],
            priority=JobPriority.MEDIUM,
            metadata={"file_path": file_path}
        )


# Global background job service instance
background_job_service = BackgroundJobService()
