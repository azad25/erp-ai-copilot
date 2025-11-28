"""
Background Tasks API Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.services.background_task_service import (
    background_task_service,
    TaskType,
    TaskStatus
)
from app.services.rbac_service import rbac_service, Permission

router = APIRouter()


class CreateTaskRequest(BaseModel):
    """Request to create a background task"""
    task_type: str
    parameters: Dict[str, Any]


class TaskResponse(BaseModel):
    """Task response"""
    task_id: str
    status: str
    message: str


@router.post("/create", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest):
    """
    Create a new background task
    
    Supported task types:
    - report_generation: Generate PDF/Excel reports
    - chart_generation: Create charts and visualizations
    - forecast_calculation: Calculate forecasts and predictions
    - data_analysis: Perform complex data analysis
    - bulk_export: Export large datasets
    """
    try:
        # TODO: Get user from JWT token
        user_id = "system"  # Placeholder
        user_role = "admin"  # Placeholder
        
        # Check permissions
        if not rbac_service.can_create_background_task(user_role, request.task_type):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions to create this task type"
            )
        
        # Validate task type
        try:
            task_type = TaskType(request.task_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid task type: {request.task_type}"
            )
        
        # Create task
        task_id = await background_task_service.create_task(
            task_type=task_type,
            user_id=user_id,
            parameters=request.parameters
        )
        
        return TaskResponse(
            task_id=task_id,
            status="pending",
            message="Task created successfully. You will be notified when it completes."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """Get status and result of a background task"""
    try:
        task = await background_task_service.get_task_status(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return task
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a pending or processing task"""
    try:
        success = await background_task_service.cancel_task(task_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Task cannot be cancelled (not found or already completed)"
            )
        
        return {"message": "Task cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_user_tasks(status: Optional[str] = None, limit: int = 20):
    """List user's background tasks"""
    try:
        # TODO: Get user from JWT token and filter by user_id
        # For now, return empty list
        return {
            "tasks": [],
            "total": 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
