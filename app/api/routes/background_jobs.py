"""
Background Jobs API Routes

REST API endpoints for managing background jobs, file monitoring,
and system task scheduling for AI Copilot operations.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Any, Optional
import logging

from app.services.background_job_service import background_job_service, JobPriority
from app.services.file_watcher_service import file_watcher_service
from app.middleware.auth import get_current_user, require_admin
from app.models.api_models import StandardResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/background-jobs", tags=["background-jobs"])


@router.get("/status", response_model=StandardResponse)
async def get_job_queue_status(
    current_user: Dict = Depends(get_current_user)
):
    """Get background job queue status"""
    try:
        status = await background_job_service.get_job_queue_status()
        
        return StandardResponse(
            success=True,
            message="Job queue status retrieved successfully",
            data=status
        )
        
    except Exception as e:
        logger.error(f"Failed to get job queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/job/{job_id}", response_model=StandardResponse)
async def get_job_status(
    job_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Get specific job status"""
    try:
        status = await background_job_service.get_job_status(job_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return StandardResponse(
            success=True,
            message="Job status retrieved successfully",
            data=status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule", response_model=StandardResponse)
async def schedule_job(
    job_data: Dict[str, Any],
    current_user: Dict = Depends(require_admin)
):
    """Schedule a background job"""
    try:
        job_type = job_data.get("job_type")
        function_name = job_data.get("function_name")
        
        if not job_type or not function_name:
            raise HTTPException(
                status_code=400, 
                detail="job_type and function_name are required"
            )
        
        job_id = await background_job_service.schedule_job(
            job_type=job_type,
            function_name=function_name,
            args=job_data.get("args", []),
            kwargs=job_data.get("kwargs", {}),
            priority=JobPriority(job_data.get("priority", 2)),
            delay_seconds=job_data.get("delay_seconds", 0),
            metadata=job_data.get("metadata", {})
        )
        
        return StandardResponse(
            success=True,
            message="Job scheduled successfully",
            data={"job_id": job_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to schedule job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/job/{job_id}", response_model=StandardResponse)
async def cancel_job(
    job_id: str,
    current_user: Dict = Depends(require_admin)
):
    """Cancel a background job"""
    try:
        success = await background_job_service.cancel_job(job_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Job not found or cannot be cancelled")
        
        return StandardResponse(
            success=True,
            message="Job cancelled successfully",
            data={"job_id": job_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file-watcher/status", response_model=StandardResponse)
async def get_file_watcher_status(
    current_user: Dict = Depends(get_current_user)
):
    """Get file watcher monitoring status"""
    try:
        status = await file_watcher_service.get_monitoring_status()
        
        return StandardResponse(
            success=True,
            message="File watcher status retrieved successfully",
            data=status
        )
        
    except Exception as e:
        logger.error(f"Failed to get file watcher status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/file-watcher/rescan", response_model=StandardResponse)
async def force_file_rescan(
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(require_admin)
):
    """Force a complete rescan of documentation files"""
    try:
        # Schedule rescan as background task
        background_tasks.add_task(file_watcher_service.force_rescan)
        
        return StandardResponse(
            success=True,
            message="File rescan scheduled successfully",
            data={"status": "scheduled"}
        )
        
    except Exception as e:
        logger.error(f"Failed to schedule file rescan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge-base/refresh", response_model=StandardResponse)
async def refresh_knowledge_base(
    current_user: Dict = Depends(require_admin)
):
    """Schedule knowledge base refresh"""
    try:
        job_id = await background_job_service.schedule_job(
            job_type="refresh_knowledge_base",
            function_name="refresh_knowledge_base",
            priority=JobPriority.HIGH,
            metadata={"triggered_by": current_user.get("user_id")}
        )
        
        return StandardResponse(
            success=True,
            message="Knowledge base refresh scheduled",
            data={"job_id": job_id}
        )
        
    except Exception as e:
        logger.error(f"Failed to schedule knowledge base refresh: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize-context/{user_id}", response_model=StandardResponse)
async def optimize_user_context(
    user_id: str,
    current_user: Dict = Depends(require_admin)
):
    """Schedule user context optimization"""
    try:
        job_id = await background_job_service.schedule_job(
            job_type="optimize_chat_context",
            function_name="optimize_chat_context",
            args=[user_id, current_user.get("organization_id")],
            priority=JobPriority.MEDIUM,
            metadata={"triggered_by": current_user.get("user_id")}
        )
        
        return StandardResponse(
            success=True,
            message="User context optimization scheduled",
            data={"job_id": job_id}
        )
        
    except Exception as e:
        logger.error(f"Failed to schedule context optimization: {e}")
        raise HTTPException(status_code=500, detail=str(e))
